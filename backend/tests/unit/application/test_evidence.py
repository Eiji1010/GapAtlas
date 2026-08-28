"""Evidence と Evidence パックの組み立てのテスト。

`summary` は**コード側が生成した事実**であり、`url` は SerpApi のレスポンスに
含まれていたものだけ(AGENTS.md 絶対ルール)。
"""

from __future__ import annotations

from conftest import SCAN_ID, SCAN_TIME, FailingSerpApiClient

from gapatlas.adapters.llm.stub_client import StubLlmClient
from gapatlas.adapters.serpapi.fixture_client import FixtureSerpApiClient
from gapatlas.application.country_scan import CountryScanner
from gapatlas.application.evidence import (
    METHODOLOGY_LIMITATIONS,
    build_evidence,
    build_evidence_pack,
)
from gapatlas.config.query_profile_loader import load_query_profile
from gapatlas.domain.models.common import Country, SourceName, TopicId


def _outcome(serpapi=None, country: Country = Country.JP, include_maps: bool = False):
    scanner = CountryScanner(serpapi or FixtureSerpApiClient(), StubLlmClient())
    return scanner.scan(
        load_query_profile(TopicId.ELDER_CARE, country),
        scan_id=SCAN_ID,
        scan_time=SCAN_TIME,
        include_maps=include_maps,
    )


def test_one_evidence_per_ok_source():
    outcome = _outcome()
    sources = [item.source for item in outcome.result.evidence]
    assert sources == [
        SourceName.TRENDS,
        SourceName.RELATED_QUERIES,
        SourceName.SEARCH,
        SourceName.NEWS,
    ]


def test_missing_sources_produce_no_evidence():
    """欠けているソースについて根拠を作らない。"""
    outcome = _outcome(serpapi=FailingSerpApiClient([SourceName.NEWS]))
    sources = [item.source for item in outcome.result.evidence]
    assert SourceName.NEWS not in sources
    assert [item.id for item in outcome.result.evidence] == ["E1", "E2", "E3"]


def test_maps_evidence_appears_when_requested():
    outcome = _outcome(include_maps=True)
    maps_evidence = [item for item in outcome.result.evidence if item.source is SourceName.MAPS]
    assert len(maps_evidence) == 1
    assert "供給量ではない" in maps_evidence[0].summary


def test_trends_summary_states_the_observed_change():
    outcome = _outcome()
    trends = next(item for item in outcome.result.evidence if item.source is SourceName.TRENDS)
    # JP fixture は明確な上昇トレンド(README「各国の Trends の性質」)
    assert "上昇" in trends.summary
    assert trends.url is None


def test_evidence_urls_come_from_the_serpapi_response():
    outcome = _outcome()
    search_links = {item.link for item in outcome.evidence.search_results}
    news_links = {item.link for item in outcome.evidence.news_articles}
    for item in outcome.result.evidence:
        if item.url is None:
            continue
        assert item.url in search_links | news_links | {
            entry.link for entry in outcome.evidence.rising_queries
        }


def test_build_evidence_is_pure():
    """同じ入力なら同じ結果。"""
    outcome = _outcome()
    first = build_evidence(outcome.evidence, outcome.classified)
    second = build_evidence(outcome.evidence, outcome.classified)
    assert [item.model_dump() for item in first] == [item.model_dump() for item in second]


def test_evidence_pack_carries_scores_summaries_and_limitations():
    outcome = _outcome()
    assert outcome.evaluation is not None
    pack = build_evidence_pack(
        Country.JP, TopicId.ELDER_CARE, outcome.evaluation, outcome.result.evidence
    )
    assert pack.need_gap_score == outcome.result.need_gap_score
    assert pack.confidence == outcome.result.confidence
    assert pack.evidence_ids == [item.id for item in outcome.result.evidence]
    assert list(METHODOLOGY_LIMITATIONS) == pack.limitations


def test_evidence_pack_summaries_contain_no_urls():
    """LLM へ URL を渡さない。"""
    outcome = _outcome()
    assert outcome.evaluation is not None
    pack = build_evidence_pack(
        Country.JP, TopicId.ELDER_CARE, outcome.evaluation, outcome.result.evidence
    )
    for item in pack.evidence:
        assert "http" not in item.summary


def test_limitations_cover_the_methodology_document():
    """docs/methodology.md「何を示さないか」の主要項目を含むこと。"""
    joined = " ".join(METHODOLOGY_LIMITATIONS)
    for keyword in ("供給量", "相対値", "報道量", "深刻度", "Maps"):
        assert keyword in joined
