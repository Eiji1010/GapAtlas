"""Need Gap Signal Score のテスト。docs/scoring.md 1章。"""

from __future__ import annotations

from datetime import datetime

import pytest
from conftest import (
    SCAN_TIME,
    make_classified,
    make_evidence,
    make_news,
    make_rising,
    make_search,
    make_trends,
)

from gapatlas.domain.models.classification import (
    NewsRelevance,
    PainCategory,
    SolutionCategory,
)
from gapatlas.domain.models.errors import InvalidTemporalValueError
from gapatlas.domain.models.scores import ScoreComponents
from gapatlas.domain.scoring.constants import (
    COMPONENT_DEMAND,
    COMPONENT_NEWS_URGENCY,
    COMPONENT_PAIN,
    COMPONENT_SOLUTION_GAP,
    NEED_GAP_WEIGHTS,
)
from gapatlas.domain.scoring.need_gap import compute_components, compute_need_gap


def test_component_names_match_score_components_fields():
    """成分名は `ScoreComponents` のフィールド名と一致すること(統合側の契約)。"""
    assert set(NEED_GAP_WEIGHTS) == set(ScoreComponents.model_fields)


def test_weights_sum_to_one():
    assert sum(NEED_GAP_WEIGHTS.values()) == pytest.approx(1.0)
    assert NEED_GAP_WEIGHTS[COMPONENT_DEMAND] == 0.40
    assert NEED_GAP_WEIGHTS[COMPONENT_PAIN] == 0.25
    assert NEED_GAP_WEIGHTS[COMPONENT_SOLUTION_GAP] == 0.25
    assert NEED_GAP_WEIGHTS[COMPONENT_NEWS_URGENCY] == 0.10


def test_hand_calculated_all_components_present():
    """手計算: 0.40*80 + 0.25*60 + 0.25*40 + 0.10*20 = 32 + 15 + 10 + 2 = 59.0。"""
    components = ScoreComponents(demand=80.0, pain=60.0, solution_gap=40.0, news_urgency=20.0)
    result = compute_need_gap(components)
    assert result.score == pytest.approx(59.0)
    assert result.components_used == [
        COMPONENT_DEMAND,
        COMPONENT_PAIN,
        COMPONENT_SOLUTION_GAP,
        COMPONENT_NEWS_URGENCY,
    ]


def test_missing_demand_yields_no_score():
    """`demand` が計算不能 → スコアを出さない(Trends は必須ソース)。"""
    components = ScoreComponents(demand=None, pain=100.0, solution_gap=100.0, news_urgency=100.0)
    result = compute_need_gap(components)
    assert result.score is None
    assert result.components_used == []


def test_renormalizes_when_pain_is_missing():
    """`pain` だけ欠損 → `(0.40*d + 0.25*sg + 0.10*nu) / 0.75`。"""
    components = ScoreComponents(demand=80.0, pain=None, solution_gap=40.0, news_urgency=20.0)
    expected = (0.40 * 80.0 + 0.25 * 40.0 + 0.10 * 20.0) / 0.75
    assert expected == pytest.approx(58.666666666666664)
    result = compute_need_gap(components)
    assert result.score == pytest.approx(expected)
    assert result.components_used == [
        COMPONENT_DEMAND,
        COMPONENT_SOLUTION_GAP,
        COMPONENT_NEWS_URGENCY,
    ]


def test_missing_component_is_not_treated_as_zero():
    """欠損を 0 として扱わない(欠損と「値が0」は別)。"""
    missing = ScoreComponents(demand=80.0, pain=None, solution_gap=40.0, news_urgency=20.0)
    zero = ScoreComponents(demand=80.0, pain=0.0, solution_gap=40.0, news_urgency=20.0)
    missing_score = compute_need_gap(missing).score
    zero_score = compute_need_gap(zero).score
    assert missing_score is not None
    assert zero_score is not None
    assert missing_score != pytest.approx(zero_score)
    assert zero_score == pytest.approx(0.40 * 80.0 + 0.25 * 40.0 + 0.10 * 20.0)


def test_demand_only_returns_demand():
    """`demand` 以外が全て欠損 → 再正規化により `demand` そのものになる。"""
    components = ScoreComponents(demand=72.0, pain=None, solution_gap=None, news_urgency=None)
    result = compute_need_gap(components)
    assert result.score == pytest.approx(72.0)
    assert result.components_used == [COMPONENT_DEMAND]


@pytest.mark.parametrize(
    ("missing_field", "expected_weight_sum"),
    [
        ("pain", 0.75),
        ("solution_gap", 0.75),
        ("news_urgency", 0.90),
    ],
)
def test_renormalization_denominator(missing_field, expected_weight_sum):
    values = {"demand": 100.0, "pain": 100.0, "solution_gap": 100.0, "news_urgency": 100.0}
    values[missing_field] = None
    result = compute_need_gap(ScoreComponents(**values))
    # 全成分 100 なら再正規化後も 100 になる(重みの合計で割るため)。
    assert result.score == pytest.approx(100.0)
    assert sum(NEED_GAP_WEIGHTS[name] for name in result.components_used) == pytest.approx(
        expected_weight_sum
    )


def test_compute_components_wires_each_source():
    """`compute_components` が4成分をそれぞれのソースから算出すること。"""
    classified = make_classified(
        rising_queries=[make_rising(100.0, PainCategory.SHORTAGE)],
        search_results=[make_search(1, SolutionCategory.INFORMATION)],
        news_articles=[make_news(SCAN_TIME, NewsRelevance.DIRECTLY_RELEVANT)],
    )
    evidence = make_evidence(trends=make_trends([10.0] * 8 + [12.0] * 4))
    components = compute_components(evidence, classified, SCAN_TIME)

    assert components.demand == pytest.approx(64.0469176213857)
    assert components.pain == pytest.approx(100.0)
    assert components.solution_gap == pytest.approx(100.0)
    assert components.news_urgency == pytest.approx(18.12692469220182)


def test_compute_components_returns_none_for_uncomputable_sources():
    evidence = make_evidence(trends=None)
    components = compute_components(evidence, make_classified(), SCAN_TIME)
    assert components.demand is None
    assert components.pain is None
    assert components.solution_gap is None
    assert components.news_urgency is None


def test_compute_components_rejects_naive_scan_time():
    naive = datetime(2026, 8, 28)
    with pytest.raises(InvalidTemporalValueError):
        compute_components(make_evidence(), make_classified(), naive)
