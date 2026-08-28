"""スコア内部表現モデルのテスト。"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from gapatlas.domain.models.scores import (
    ConfidenceBreakdown,
    ConfidenceResult,
    NeedGapResult,
    ScoreComponents,
)


def test_score_components_default_to_none():
    components = ScoreComponents()
    assert components.demand is None
    assert components.pain is None
    assert components.solution_gap is None
    assert components.news_urgency is None


@pytest.mark.parametrize("value", [-0.1, 100.1])
def test_score_components_reject_out_of_range(value):
    with pytest.raises(ValidationError):
        ScoreComponents(demand=value)


def test_need_gap_result_allows_none_score():
    result = NeedGapResult(score=None, components=ScoreComponents(demand=None))
    assert result.score is None
    assert result.components_used == []


def test_need_gap_result_records_components_used():
    result = NeedGapResult(
        score=72.5,
        components=ScoreComponents(demand=80.0, pain=60.0),
        components_used=["demand", "pain"],
    )
    assert result.components_used == ["demand", "pain"]


def _breakdown(**overrides: float) -> ConfidenceBreakdown:
    values: dict[str, float] = {
        "data_completeness": 100.0,
        "sample_sufficiency": 80.0,
        "localization_quality": 70.0,
        "source_agreement": 60.0,
        "freshness": 90.0,
    }
    values.update(overrides)
    return ConfidenceBreakdown(**values)


def test_confidence_breakdown_requires_all_components():
    with pytest.raises(ValidationError):
        ConfidenceBreakdown(data_completeness=100.0)


@pytest.mark.parametrize("value", [-1.0, 101.0])
def test_confidence_breakdown_rejects_out_of_range(value):
    with pytest.raises(ValidationError):
        _breakdown(freshness=value)


def test_confidence_result_holds_applied_caps():
    result = ConfidenceResult(
        score=59.0, breakdown=_breakdown(), applied_caps=["one_core_source_missing"]
    )
    assert result.applied_caps == ["one_core_source_missing"]


@pytest.mark.parametrize("value", [-1.0, 101.0])
def test_confidence_result_rejects_out_of_range_score(value):
    with pytest.raises(ValidationError):
        ConfidenceResult(score=value, breakdown=_breakdown())
