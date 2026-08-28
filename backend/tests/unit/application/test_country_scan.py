"""`CountryScanner` のテスト。

**1ソースの失敗で全体が落ちないこと**と、欠損が Evidence Confidence へ
正しく反映されることが中心(docs/requirements.md「Reliability」)。
"""

from __future__ import annotations

import inspect

import pytest
from conftest import (
    SCAN_ID,
    SCAN_TIME,
    ExplodingSerpApiClient,
    FailingClassifier,
    FailingSerpApiClient,
    FixtureOverrideClient,
    ShortClassifier,
)

from gapatlas.adapters.llm.stub_client import StubLlmClient
from gapatlas.adapters.serpapi.fixture_client import FixtureSerpApiClient
from gapatlas.application.country_scan import CountryScanner
from gapatlas.config.query_profile_loader import load_query_profile
from gapatlas.domain.models.common import (
    CORE_SOURCES,
    Country,
    CountryStatus,
    SourceName,
    SourceStatus,
    TopicId,
)


def _profile(country: Country = Country.JP):
    return load_query_profile(TopicId.ELDER_CARE, country)


def _scan(serpapi=None, classifier=None, country: Country = Country.JP):
    scanner = CountryScanner(serpapi or FixtureSerpApiClient(), classifier or StubLlmClient())
    return scanner.scan(_profile(country), scan_id=SCAN_ID, scan_time=SCAN_TIME)


# --- 正常系 -------------------------------------------------------------------------


@pytest.mark.parametrize("country", list(Country))
def test_every_country_completes(country):
    outcome = _scan(country=country)
    assert outcome.result.status is CountryStatus.COMPLETED
    assert outcome.result.need_gap_score is not None
    assert outcome.result.scan_id == SCAN_ID
    assert outcome.result.computed_at == SCAN_TIME


def test_versions_are_recorded():
    """再現可能性のため4バージョンを必ず含める(docs/scoring.md 8章)。"""
    versions = _scan().result.versions
    assert versions.query_profile_version == "elder-care-jp-v2"
    assert versions.score_version == "gapatlas-score-v1"
    # stub は実 LLM と結果が変わるため、版で区別できること
    assert versions.classifier_version == "gapatlas-classifier-v1-stub"
    assert versions.prompt_version == "gapatlas-prompt-v1-stub"


def test_raw_payloads_are_kept_unmodified():
    """S3 raw/ へ無加工で保存するため、生レスポンスを保持する。"""
    outcome = _scan()
    assert set(outcome.raw.payloads) == {
        SourceName.TRENDS,
        SourceName.RELATED_QUERIES,
        SourceName.SEARCH,
        SourceName.NEWS,
    }
    assert "interest_over_time" in outcome.raw.payloads[SourceName.TRENDS]


def test_maps_is_not_fetched_during_the_scan():
    """Maps は Top2 のみ。スキャン中には取得しない(docs/requirements.md)。"""
    outcome = _scan()
    assert outcome.evidence.maps_places is None
    assert outcome.result.source_status[SourceName.MAPS] is SourceStatus.NOT_REQUESTED
    assert SourceName.MAPS not in outcome.raw.payloads


def test_evidence_ids_are_sequential_and_urls_come_from_serpapi():
    """Evidence の ID は E1 始まりの連番。URL は SerpApi 由来のみ。"""
    outcome = _scan()
    items = outcome.result.evidence
    assert [item.id for item in items] == [f"E{index}" for index in range(1, len(items) + 1)]
    links = {item.link for item in outcome.evidence.search_results}
    search_evidence = next(item for item in items if item.source is SourceName.SEARCH)
    assert search_evidence.url in links


def test_scan_is_deterministic():
    first = _scan().result.model_dump()
    second = _scan().result.model_dump()
    assert first == second


# --- 部分障害 -----------------------------------------------------------------------


def test_one_failing_source_does_not_stop_the_scan():
    """1ソースが落ちても評価は完了し、Confidence が 69 以下に制限される。"""
    outcome = _scan(serpapi=FailingSerpApiClient([SourceName.NEWS]))
    assert outcome.result.status is CountryStatus.COMPLETED
    assert outcome.result.source_status[SourceName.NEWS] is SourceStatus.MISSING
    assert outcome.result.components.news_urgency is None
    assert outcome.result.confidence <= 69


def test_two_failing_sources_yield_insufficient_evidence():
    outcome = _scan(serpapi=FailingSerpApiClient([SourceName.NEWS, SourceName.SEARCH]))
    assert outcome.result.status is CountryStatus.INSUFFICIENT_EVIDENCE
    assert outcome.result.need_gap_score is None
    # INSUFFICIENT_EVIDENCE でも Confidence は返す(docs/scoring.md 6章)
    assert 0 < outcome.result.confidence <= 69


def test_failing_trends_removes_the_score():
    outcome = _scan(serpapi=FailingSerpApiClient([SourceName.TRENDS]))
    assert outcome.result.status is CountryStatus.INSUFFICIENT_EVIDENCE
    assert outcome.result.need_gap_score is None


def test_empty_trends_payload_is_treated_as_missing():
    """取得できても中身が空なら MISSING(docs/scoring.md 6章の Core Source 定義)。"""
    client = FixtureOverrideClient({SourceName.TRENDS: "trends_timeseries_empty"})
    outcome = _scan(serpapi=client)
    assert outcome.result.source_status[SourceName.TRENDS] is SourceStatus.MISSING
    assert outcome.result.need_gap_score is None


def test_news_without_parsable_dates_is_missing():
    """日付をパースできる記事が0件なら News Urgency を出せないので MISSING。"""
    client = FixtureOverrideClient({SourceName.NEWS: "news_no_iso_date"})
    outcome = _scan(serpapi=client)
    assert outcome.result.source_status[SourceName.NEWS] is SourceStatus.MISSING
    assert outcome.result.components.news_urgency is None


def test_empty_rising_queries_is_missing_but_scan_completes():
    client = FixtureOverrideClient({SourceName.RELATED_QUERIES: "trends_related_queries_empty"})
    outcome = _scan(serpapi=client)
    assert outcome.result.source_status[SourceName.RELATED_QUERIES] is SourceStatus.MISSING
    assert outcome.result.components.pain is None
    assert outcome.result.status is CountryStatus.COMPLETED


def test_unexpected_exception_becomes_failed():
    """想定外の例外は FAILED。呼び出し元を 5xx にしない(docs/api.md)。"""
    outcome = _scan(serpapi=ExplodingSerpApiClient())
    assert outcome.result.status is CountryStatus.FAILED
    assert outcome.result.need_gap_score is None
    assert outcome.result.confidence == 0
    assert outcome.evaluation is None


# --- 分類の失敗 ---------------------------------------------------------------------


def test_total_classification_failure_marks_the_source_missing():
    """分類が全滅したソースは MISSING。

    既定値で埋めた結果を流すと `solution_gap = 100`(最大値)が観測値として
    スコアへ入る(docs/llm-prompts.md「共通のレスポンス規約」)。
    """
    outcome = _scan(classifier=FailingClassifier(search=True))
    assert outcome.result.source_status[SourceName.SEARCH] is SourceStatus.MISSING
    assert outcome.result.components.solution_gap is None
    assert outcome.classified.search_results == []
    assert outcome.result.status is CountryStatus.COMPLETED
    assert outcome.result.confidence <= 69


def test_solution_gap_is_not_silently_maxed_out_on_classification_failure():
    """回帰: 分類全滅時に solution_gap が 100 にならないこと。"""
    failed = _scan(classifier=FailingClassifier(search=True)).result
    healthy = _scan().result
    assert failed.components.solution_gap is None
    assert healthy.components.solution_gap is not None
    assert healthy.components.solution_gap < 100.0


def test_two_failing_classifications_yield_insufficient_evidence():
    outcome = _scan(classifier=FailingClassifier(search=True, news=True))
    assert outcome.result.status is CountryStatus.INSUFFICIENT_EVIDENCE
    assert outcome.result.need_gap_score is None


# --- Maps -------------------------------------------------------------------------


def test_attach_maps_adds_evidence_without_changing_the_score():
    """Maps は Core Source ではないのでスコアを変えない。"""
    scanner = CountryScanner(FixtureSerpApiClient(), StubLlmClient())
    outcome = scanner.scan(_profile(), scan_id=SCAN_ID, scan_time=SCAN_TIME)
    with_maps = scanner.attach_maps(outcome, _profile(), scan_time=SCAN_TIME)

    assert with_maps.result.need_gap_score == outcome.result.need_gap_score
    assert with_maps.result.confidence == outcome.result.confidence
    assert with_maps.result.source_status[SourceName.MAPS] is SourceStatus.OK
    assert with_maps.evidence.maps_places is not None
    assert len(with_maps.result.evidence) == len(outcome.result.evidence) + 1


def test_the_scanner_has_no_way_to_fetch_maps_during_the_scan():
    """Maps はランキング確定**後**にしか取れないこと。

    docs/architecture.md「Maps は5か国のランキング確定後、Top 2 についてのみ
    取得する」。スキャン中に取る経路を公開すると、この順序規則を呼び出し側が
    破れてしまう。
    """

    parameters = inspect.signature(CountryScanner.scan).parameters
    assert "include_maps" not in parameters
    assert set(parameters) == {"self", "profile", "scan_id", "scan_time"}


def test_attach_maps_on_a_failed_outcome_is_a_no_op():
    scanner = CountryScanner(ExplodingSerpApiClient(), StubLlmClient())
    outcome = scanner.scan(_profile(), scan_id=SCAN_ID, scan_time=SCAN_TIME)
    assert scanner.attach_maps(outcome, _profile(), scan_time=SCAN_TIME) is outcome


# --------------------------------------------------------------------------
# 第三者レビューの指摘(trends の OK 判定 / 分類器の契約違反 / 正規化の失敗)
# --------------------------------------------------------------------------


def test_trends_with_fewer_than_twelve_points_is_missing():
    """Demand を1つも計算できない Trends は `MISSING`。

    `OK` の定義は「取得に成功し、**下位スコアの計算に使える内容があった**」
    (docs/scoring.md 6章)。1点でもあれば OK とすると、スコアを出せないのに
    `data_completeness = 100` になり、**Confidence が正常系より高くなる**。
    """
    client = FixtureOverrideClient({SourceName.TRENDS: "trends_timeseries_11_points"})
    outcome = _scan(serpapi=client)

    assert outcome.result.source_status[SourceName.TRENDS] is SourceStatus.MISSING
    assert outcome.result.status is CountryStatus.INSUFFICIENT_EVIDENCE
    assert outcome.result.need_gap_score is None
    # Hard Rule 1(trends 欠損)と 3(1ソース欠損)が記録され、上限が効く
    assert outcome.result.confidence <= 69
    assert outcome.result.confidence_breakdown.data_completeness == pytest.approx(75.0)
    # 使えない Trends を根拠として提示しない
    assert all(item.source is not SourceName.TRENDS for item in outcome.result.evidence)


def test_trends_is_ok_when_at_least_one_query_has_a_full_window():
    """1クエリでも12点あれば Demand を出せるので `OK`(docs/scoring.md 9章)。"""
    outcome = _scan()
    assert outcome.result.source_status[SourceName.TRENDS] is SourceStatus.OK
    assert outcome.result.components.demand is not None


def test_a_classifier_that_returns_the_wrong_count_only_loses_that_source():
    """Protocol 違反(件数不一致)で国全体を `FAILED` にしない。

    1ソースの分類器のバグで、健全な3ソースの結果まで捨てるのは
    docs/architecture.md「他のソースの結果でスコアを算出する」に反する。
    """
    outcome = _scan(classifier=ShortClassifier())
    assert outcome.result.status is CountryStatus.COMPLETED
    assert outcome.result.source_status[SourceName.SEARCH] is SourceStatus.MISSING
    assert outcome.result.components.solution_gap is None
    assert outcome.result.components.demand is not None
    assert outcome.result.confidence > 0


def test_a_broken_response_shape_only_loses_that_source():
    """正規化が `SerpApiResponseError` を投げても、そのソースだけ落とす。"""

    class BrokenSearchClient:
        def __init__(self):
            self._inner = FixtureSerpApiClient()

        def fetch(self, source, profile):
            if source is SourceName.SEARCH:
                return {"organic_results": "not-a-list"}
            return self._inner.fetch(source, profile)

    outcome = _scan(serpapi=BrokenSearchClient())
    assert outcome.result.source_status[SourceName.SEARCH] is SourceStatus.MISSING
    assert outcome.result.status is CountryStatus.COMPLETED
    assert outcome.result.confidence <= 69


def test_failed_source_status_has_every_source_key():
    """`FAILED` でも正常系と同じ5キーを返す(docs/api.md の source_status)。"""
    outcome = _scan(serpapi=ExplodingSerpApiClient())
    assert set(outcome.result.source_status) == {*CORE_SOURCES, SourceName.MAPS}
    assert outcome.result.source_status[SourceName.MAPS] is SourceStatus.NOT_REQUESTED


def test_insufficient_evidence_still_reports_a_meaningful_confidence():
    """スコアを出せなくても「何がどれだけ欠けているか」を示す値を返す。"""
    outcome = _scan(serpapi=FailingSerpApiClient([SourceName.NEWS, SourceName.SEARCH]))
    assert outcome.result.status is CountryStatus.INSUFFICIENT_EVIDENCE
    assert 0 < outcome.result.confidence <= 69
    assert outcome.result.confidence_breakdown.data_completeness == pytest.approx(50.0)


@pytest.mark.parametrize(
    ("country", "expected_score", "expected_confidence"),
    [("JP", 75, 91), ("US", 55, 90), ("GB", 58, 90), ("DE", 67, 90), ("IN", 66, 92)],
)
def test_expected_scores_per_country(country, expected_score, expected_confidence):
    """fixture に対する期待値を国別にも固定する。"""
    outcome = _scan(country=Country(country))
    assert outcome.result.need_gap_score == expected_score
    assert outcome.result.confidence == expected_confidence
