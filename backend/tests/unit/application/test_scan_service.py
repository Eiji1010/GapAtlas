"""`ScanService` のテスト。ランキング整列・Top2 Maps・Top1 Brief。"""

from __future__ import annotations

import pytest
from conftest import (
    SCAN_ID,
    SCAN_TIME,
    TOPIC,
    ExplodingSerpApiClient,
    FailingSerpApiClient,
    RecordingBriefWriter,
)

from gapatlas.adapters.llm.stub_client import StubLlmClient
from gapatlas.adapters.serpapi.fixture_client import FixtureSerpApiClient
from gapatlas.application.scan_service import MAPS_COUNTRY_LIMIT, ScanService
from gapatlas.domain.models.common import (
    Country,
    CountryStatus,
    ScanStatus,
    SourceName,
    SourceStatus,
)


def _service(serpapi=None, classifier=None, brief_writer=None):
    return ScanService(
        serpapi or FixtureSerpApiClient(),
        classifier or StubLlmClient(),
        brief_writer or StubLlmClient(),
    )


def _run(service=None, countries=None):
    return (service or _service()).scan(
        TOPIC, countries or list(Country), scan_id=SCAN_ID, scan_time=SCAN_TIME
    )


def test_all_countries_are_scanned():
    output = _run()
    assert set(output.outcomes) == set(Country)
    assert output.summary.status is ScanStatus.COMPLETED
    assert output.summary.progress.total == len(Country)
    assert output.summary.progress.completed == len(Country)


def test_ranking_is_sorted_by_need_gap_score_descending():
    ranking = _run().summary.ranking
    scores = [entry.need_gap_score for entry in ranking if entry.need_gap_score is not None]
    assert scores == sorted(scores, reverse=True)


def test_countries_without_a_score_are_pushed_to_the_end():
    """`need_gap_score` が None の国は末尾へ回す(docs/api.md)。"""
    service = _service(serpapi=FailingSerpApiClient([SourceName.TRENDS]))
    # trends が全国で失敗するので全件 None。順序が国コード昇順で決定的になること
    ranking = _run(service).summary.ranking
    assert all(entry.need_gap_score is None for entry in ranking)
    assert [entry.country for entry in ranking] == sorted(Country, key=lambda c: c.value)


def test_ranking_mixes_scored_and_unscored_countries_correctly():
    output = _run(countries=[Country.JP, Country.US])
    scored = output.summary.ranking
    assert scored[0].need_gap_score is not None
    assert scored[0].need_gap_score >= (scored[1].need_gap_score or 0)


def test_maps_is_fetched_only_for_the_top_two_countries():
    output = _run()
    with_maps = [
        country
        for country, outcome in output.outcomes.items()
        if outcome.result.source_status[SourceName.MAPS] is SourceStatus.OK
    ]
    assert len(with_maps) == MAPS_COUNTRY_LIMIT
    top_two = [entry.country for entry in output.summary.ranking[:MAPS_COUNTRY_LIMIT]]
    assert sorted(with_maps, key=lambda c: c.value) == sorted(top_two, key=lambda c: c.value)


def test_other_countries_have_no_maps():
    output = _run()
    rest = [entry.country for entry in output.summary.ranking[MAPS_COUNTRY_LIMIT:]]
    for country in rest:
        assert output.outcomes[country].evidence.maps_places is None


def test_brief_is_generated_for_the_top_country_only():
    writer = RecordingBriefWriter()
    output = _run(_service(brief_writer=writer))
    assert len(writer.packs) == 1
    assert writer.packs[0].country is output.summary.ranking[0].country
    assert output.summary.opportunity_brief is not None


def test_the_evidence_pack_carries_no_urls():
    """LLM に URL を渡さない・生成させない(AGENTS.md 絶対ルール)。"""
    writer = RecordingBriefWriter()
    _run(_service(brief_writer=writer))
    pack = writer.packs[0]
    for item in pack.evidence:
        assert not hasattr(item, "url")
        assert "http" not in item.summary
    assert pack.limitations


def test_brief_citations_reference_existing_evidence_ids():
    output = _run()
    brief = output.summary.opportunity_brief
    assert brief is not None
    top_country = output.summary.ranking[0].country
    valid = {item.id for item in output.outcomes[top_country].result.evidence}
    assert set(brief.cited_evidence_ids) <= valid
    assert brief.cited_evidence_ids


def test_a_failed_country_marks_the_scan_partially_failed():
    output = _run(_service(serpapi=ExplodingSerpApiClient()))
    assert output.summary.status is ScanStatus.PARTIALLY_FAILED
    assert output.summary.completed_countries == []
    assert output.summary.opportunity_brief is None


def test_versions_join_every_scanned_query_profile():
    versions = _run().summary.versions
    assert versions.query_profile_version.count(",") == len(Country) - 1
    assert "elder-care-jp-v2" in versions.query_profile_version
    assert versions.score_version == "gapatlas-score-v1"


def test_scan_is_deterministic():
    first = _run().summary.model_dump()
    second = _run().summary.model_dump()
    assert first == second


def test_empty_country_list_is_rejected():
    with pytest.raises(ValueError, match="countries"):
        _service().scan(TOPIC, [], scan_id=SCAN_ID, scan_time=SCAN_TIME)


def test_single_country_scan_works():
    output = _run(countries=[Country.DE])
    assert set(output.outcomes) == {Country.DE}
    assert output.summary.ranking[0].country is Country.DE
    assert output.outcomes[Country.DE].result.status is CountryStatus.COMPLETED
    # 1か国でも Top2 の枠内なので Maps を取る
    assert output.outcomes[Country.DE].evidence.maps_places is not None
