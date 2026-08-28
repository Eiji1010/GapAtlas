"""`CountryScanner` のテスト。

**1ソースの失敗で全体が落ちないこと**と、欠損が Evidence Confidence へ
正しく反映されることが中心(docs/requirements.md「Reliability」)。
"""

from __future__ import annotations

import pytest
from conftest import (
    SCAN_ID,
    SCAN_TIME,
    ExplodingSerpApiClient,
    FailingClassifier,
    FailingSerpApiClient,
    FixtureOverrideClient,
)

from gapatlas.adapters.llm.stub_client import StubLlmClient
from gapatlas.adapters.serpapi.fixture_client import FixtureSerpApiClient
from gapatlas.application.country_scan import CountryScanner
from gapatlas.config.query_profile_loader import load_query_profile
from gapatlas.domain.models.common import (
    Country,
    CountryStatus,
    SourceName,
    SourceStatus,
    TopicId,
)


def _profile(country: Country = Country.JP):
    return load_query_profile(TopicId.ELDER_CARE, country)


def _scan(serpapi=None, classifier=None, country: Country = Country.JP, include_maps=False):
    scanner = CountryScanner(serpapi or FixtureSerpApiClient(), classifier or StubLlmClient())
    return scanner.scan(
        _profile(country), scan_id=SCAN_ID, scan_time=SCAN_TIME, include_maps=include_maps
    )


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
    assert versions.classifier_version == "gapatlas-classifier-v1"
    assert versions.prompt_version == "gapatlas-prompt-v1"


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


def test_maps_is_not_fetched_by_default():
    """Maps は Top2 のみ。既定では取得しない(docs/requirements.md)。"""
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
    assert outcome.result.confidence >= 0


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


def test_include_maps_fetches_maps_during_the_scan():
    outcome = _scan(include_maps=True)
    assert outcome.result.source_status[SourceName.MAPS] is SourceStatus.OK
    assert outcome.evidence.maps_places


def test_attach_maps_on_a_failed_outcome_is_a_no_op():
    scanner = CountryScanner(ExplodingSerpApiClient(), StubLlmClient())
    outcome = scanner.scan(_profile(), scan_id=SCAN_ID, scan_time=SCAN_TIME)
    assert scanner.attach_maps(outcome, _profile(), scan_time=SCAN_TIME) is outcome
