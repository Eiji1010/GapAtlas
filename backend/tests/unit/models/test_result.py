"""公開表現(API レスポンス相当)モデルのテスト。"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from gapatlas.domain.models.common import (
    Country,
    CountryStatus,
    ScanStatus,
    SourceName,
    SourceStatus,
    TopicId,
)
from gapatlas.domain.models.result import (
    CountryResult,
    Evidence,
    OpportunityBrief,
    RankingEntry,
    ScanMeta,
    ScanProgress,
    ScanSummary,
    Versions,
)
from gapatlas.domain.models.scores import ConfidenceBreakdown, ScoreComponents

COMPUTED_AT = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)

VERSIONS = Versions(
    query_profile_version="elder-care-jp-v1",
    score_version="gapatlas-score-v1",
    classifier_version="gapatlas-classifier-v1",
    prompt_version="gapatlas-prompt-v1",
)

BREAKDOWN = ConfidenceBreakdown(
    data_completeness=100.0,
    sample_sufficiency=95.0,
    localization_quality=70.0,
    source_agreement=88.0,
    freshness=92.0,
)


def _country_result(**overrides: object) -> CountryResult:
    values: dict[str, object] = {
        "scan_id": "scan_abc123",
        "topic_id": TopicId.ELDER_CARE,
        "country": Country.JP,
        "status": CountryStatus.COMPLETED,
        "need_gap_score": 86,
        "confidence": 92,
        "components": ScoreComponents(demand=91.0, pain=84.0),
        "confidence_breakdown": BREAKDOWN,
        "source_status": {SourceName.TRENDS: SourceStatus.OK},
        "evidence": [],
        "versions": VERSIONS,
        "computed_at": COMPUTED_AT,
    }
    values.update(overrides)
    return CountryResult(**values)


@pytest.mark.parametrize("evidence_id", ["E1", "E2", "E10", "E123"])
def test_evidence_id_accepts_valid_ids(evidence_id):
    evidence = Evidence(id=evidence_id, source=SourceName.TRENDS, summary="s")
    assert evidence.id == evidence_id
    assert evidence.url is None


@pytest.mark.parametrize("evidence_id", ["X1", "E0", "E", "1", "e1", "E01", "E1 ", " E1", "EE1"])
def test_evidence_id_rejects_invalid_ids(evidence_id):
    with pytest.raises(ValidationError):
        Evidence(id=evidence_id, source=SourceName.TRENDS, summary="s")


def test_country_result_completed_with_score():
    result = _country_result()
    assert result.need_gap_score == 86
    assert result.status is CountryStatus.COMPLETED


@pytest.mark.parametrize(
    "status",
    [CountryStatus.INSUFFICIENT_EVIDENCE, CountryStatus.FAILED],
)
def test_country_result_allows_none_score_for_scoreless_statuses(status):
    result = _country_result(need_gap_score=None, status=status)
    assert result.need_gap_score is None
    assert result.confidence == 92


@pytest.mark.parametrize(
    "status",
    [CountryStatus.COMPLETED, CountryStatus.PENDING, CountryStatus.PROCESSING],
)
def test_country_result_rejects_none_score_with_other_statuses(status):
    with pytest.raises(ValidationError, match="need_gap_score is None"):
        _country_result(need_gap_score=None, status=status)


@pytest.mark.parametrize("score", [-1, 101])
def test_country_result_rejects_out_of_range_scores(score):
    with pytest.raises(ValidationError):
        _country_result(need_gap_score=score)


def test_country_result_rejects_naive_computed_at():
    with pytest.raises(ValidationError):
        _country_result(computed_at=datetime.fromisoformat("2026-01-02T03:04:05"))


def test_ranking_entry_allows_missing_components():
    entry = RankingEntry(
        country=Country.DE, status=CountryStatus.INSUFFICIENT_EVIDENCE, confidence=40
    )
    assert entry.need_gap_score is None
    assert entry.demand is None


def test_scan_progress_rejects_completed_over_total():
    with pytest.raises(ValidationError, match="must not exceed total"):
        ScanProgress(total=5, completed=6)


def test_scan_meta_requires_at_least_one_country():
    with pytest.raises(ValidationError):
        ScanMeta(
            scan_id="scan_abc123",
            topic_id=TopicId.ELDER_CARE,
            countries=[],
            status=ScanStatus.PROCESSING,
            created_at=COMPUTED_AT,
            updated_at=COMPUTED_AT,
        )


def test_scan_summary_shape():
    summary = ScanSummary(
        scan_id="scan_abc123",
        topic_id=TopicId.ELDER_CARE,
        status=ScanStatus.PROCESSING,
        progress=ScanProgress(total=5, completed=2),
        completed_countries=[Country.JP, Country.US],
        ranking=[
            RankingEntry(
                country=Country.JP,
                status=CountryStatus.COMPLETED,
                need_gap_score=86,
                confidence=92,
                demand=91,
                pain=84,
                solution_gap=78,
                news_urgency=83,
            )
        ],
        opportunity_brief=None,
        versions=VERSIONS,
    )
    dumped = summary.model_dump(mode="json")
    assert dumped["status"] == "processing"
    assert dumped["ranking"][0]["country"] == "JP"
    assert dumped["opportunity_brief"] is None


def test_opportunity_brief_cites_evidence_ids():
    brief = OpportunityBrief(
        why_now="w",
        what_people_are_struggling_with="p",
        visible_solutions="s",
        what_this_does_not_prove="n",
        next_validation="v",
        cited_evidence_ids=["E1", "E2"],
    )
    assert brief.cited_evidence_ids == ["E1", "E2"]
