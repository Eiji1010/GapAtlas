"""fixture -> 正規化 -> stub 分類 -> スコアリング を通した結合テスト。

各層の単体テストは緑でも、**接続部**は検証されていなかった。正規化の変更
(`query_index` の解決規則、点の並べ替え)が scoring 側の期待値を壊しても、
層ごとのテストだけでは気づけない。

docs/requirements.md「最優先は次の End-to-End を成立させること」の
`SerpApi Fixture -> Normalize -> Scoring -> Confidence` に対応する。

**基準日は `2026-08-28T00:00:00Z`**(backend/tests/fixtures/README.md)。
`scan_time` を明示的に渡さないと非決定的になる。
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from gapatlas.adapters.llm.stub_client import StubLlmClient
from gapatlas.adapters.serpapi.fixture_client import FixtureSerpApiClient
from gapatlas.adapters.serpapi.normalize import (
    normalize_maps_results,
    normalize_news_results,
    normalize_related_queries,
    normalize_search_results,
    normalize_trends_timeseries,
)
from gapatlas.config.query_profile_loader import load_query_profile
from gapatlas.domain.models.classification import (
    ClassifiedEvidence,
    ClassifiedNewsArticle,
    ClassifiedRisingQuery,
    ClassifiedSearchResult,
)
from gapatlas.domain.models.common import (
    CORE_SOURCES,
    Country,
    CountryStatus,
    SourceName,
    SourceStatus,
    TopicId,
)
from gapatlas.domain.models.normalized import NormalizedEvidence, SourceFetch
from gapatlas.domain.models.query_profile import QueryProfile
from gapatlas.domain.scoring.engine import CountryEvaluation, evaluate_country

SCAN_TIME = datetime(2026, 8, 28, tzinfo=UTC)
"""fixture の基準日。backend/tests/fixtures/README.md。"""

DEMAND_BY_COUNTRY = {
    Country.JP: 84.6,
    Country.DE: 78.1,
    Country.IN: 68.1,
    Country.US: 54.5,
    Country.GB: 43.4,
}
"""backend/tests/fixtures/README.md「各国の Trends の性質」の `demand(median)`。"""


def _load(country: Country) -> tuple[QueryProfile, NormalizedEvidence, ClassifiedEvidence]:
    """fixture を読み、正規化し、stub で分類するところまでを通す。"""
    profile = load_query_profile(TopicId.ELDER_CARE, country)
    client = FixtureSerpApiClient()
    stub = StubLlmClient()

    trends = normalize_trends_timeseries(
        client.fetch(SourceName.TRENDS, profile), profile.demand_queries
    )
    rising = normalize_related_queries(client.fetch(SourceName.RELATED_QUERIES, profile))
    search = normalize_search_results(client.fetch(SourceName.SEARCH, profile))
    news = normalize_news_results(client.fetch(SourceName.NEWS, profile))
    maps = normalize_maps_results(client.fetch(SourceName.MAPS, profile))

    evidence = NormalizedEvidence(
        trends=trends,
        rising_queries=rising,
        search_results=search,
        news_articles=news,
        maps_places=maps,
        fetches={
            source: SourceFetch(source=source, status=SourceStatus.OK, fetched_at=SCAN_TIME)
            for source in (*CORE_SOURCES, SourceName.MAPS)
        },
    )

    classified = ClassifiedEvidence(
        rising_queries=[
            ClassifiedRisingQuery(item=item, classification=classification)
            for item, classification in zip(
                rising, stub.classify_rising_queries(rising, profile), strict=True
            )
        ],
        search_results=[
            ClassifiedSearchResult(item=item, classification=classification)
            for item, classification in zip(
                search, stub.classify_search_results(search, profile), strict=True
            )
        ],
        news_articles=[
            ClassifiedNewsArticle(item=item, classification=classification)
            for item, classification in zip(
                news, stub.classify_news_articles(news, profile), strict=True
            )
        ],
    )
    return profile, evidence, classified


def _evaluate(country: Country) -> CountryEvaluation:
    profile, evidence, classified = _load(country)
    return evaluate_country(evidence, classified, profile, SCAN_TIME)


@pytest.mark.parametrize("country", list(Country))
def test_every_country_completes_through_the_whole_pipeline(country):
    """5か国すべてが fixture からスコアまで通り、COMPLETED になること。"""
    result = _evaluate(country)
    assert result.status is CountryStatus.COMPLETED
    assert result.public_need_gap_score is not None
    assert 0 <= result.public_need_gap_score <= 100
    assert 0 <= result.public_confidence <= 100
    for value in (
        result.public_components.demand,
        result.public_components.pain,
        result.public_components.solution_gap,
        result.public_components.news_urgency,
    ):
        assert value is not None
        assert 0 <= value <= 100


@pytest.mark.parametrize(("country", "expected"), sorted(DEMAND_BY_COUNTRY.items()))
def test_demand_matches_the_fixture_readme_through_the_real_adapter(country, expected):
    """README の `demand(median)` を**実アダプタ経由**で再現する。

    `test_fixture_regression.py` は JSON からテスト内で系列を組み立てており、
    正規化を通っていない。ここは `normalize_trends_timeseries` を通す。
    """
    result = _evaluate(country)
    demand = result.need_gap.components.demand
    assert demand is not None
    assert round(demand, 1) == pytest.approx(expected)


def test_ranking_order_follows_the_intended_fixture_stories():
    """fixture が意図した国ごとの需要トレンドの差がランキングに現れること。

    README:「JP=明確な上昇 / DE=ノイズの多い上昇 / IN=低ボリューム /
    US=横ばい / GB=緩やかな下降」。ここが崩れるとデモのランキングが壊れる。
    """
    demands = {country: _evaluate(country).need_gap.components.demand for country in Country}
    order = sorted(demands, key=lambda country: demands[country] or 0.0, reverse=True)
    assert order == [Country.JP, Country.DE, Country.IN, Country.US, Country.GB]


def test_india_zero_ratio_does_not_cap_confidence():
    """IN のゼロ率 37.2% は Hard Rule 4(50% 以上)に達しない。"""
    result = _evaluate(Country.IN)
    assert result.confidence.applied_caps == []


def test_pipeline_is_deterministic():
    """同じ fixture と `scan_time` なら何度実行しても同じ結果になる。"""
    first = _evaluate(Country.JP)
    second = _evaluate(Country.JP)
    assert first.model_dump() == second.model_dump()


def test_maps_is_not_part_of_the_core_score():
    """Maps を取得していても Core Source には入らない(docs/scoring.md 6章)。"""
    _, evidence, _ = _load(Country.JP)
    assert evidence.maps_places is not None
    assert SourceName.MAPS not in CORE_SOURCES
    assert evidence.source_status(SourceName.MAPS) is SourceStatus.OK
    assert evidence.missing_core_sources() == []
