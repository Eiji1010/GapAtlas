"""Solution Coverage Gap のテスト。docs/scoring.md 4章。"""

from __future__ import annotations

import math

import pytest
from conftest import make_search

from gapatlas.domain.models.classification import SolutionCategory
from gapatlas.domain.scoring.constants import SOLUTION_COVERAGE_WEIGHTS, TOP_N
from gapatlas.domain.scoring.solution import compute_solution_gap


def test_coverage_weight_table_covers_all_members():
    assert set(SOLUTION_COVERAGE_WEIGHTS) == set(SolutionCategory)


# docs/scoring.md 4章「カバレッジ重み」の表。**実装の定数を参照せずリテラルで書く。**
SPEC_COVERAGE_WEIGHTS = [
    (SolutionCategory.DIRECT_PROVIDER, 1.0),
    (SolutionCategory.MARKETPLACE, 0.7),
    (SolutionCategory.GOVERNMENT, 0.4),
    (SolutionCategory.INFORMATION, 0.0),
    (SolutionCategory.NEWS, 0.0),
    (SolutionCategory.OTHER, 0.0),
]


@pytest.mark.parametrize(("category", "weight"), SPEC_COVERAGE_WEIGHTS)
def test_each_coverage_weight_matches_the_spec_table(category, weight):
    """全6カテゴリの重みを実測で固定する。

    position 1 の1件のみなら分母と順位重みが約分され
    `solution_gap == 100 * (1 - w)`。
    """
    entries = [make_search(1, category)]
    assert compute_solution_gap(entries) == pytest.approx(100.0 * (1.0 - weight))


@pytest.mark.parametrize(("category", "weight"), SPEC_COVERAGE_WEIGHTS)
def test_constant_table_matches_the_spec_table(category, weight):
    assert SOLUTION_COVERAGE_WEIGHTS[category] == pytest.approx(weight)


def test_empty_results_is_none():
    """`organic_results` が空 → `solution_gap = None`(docs/scoring.md 9章)。"""
    assert compute_solution_gap([]) is None


def test_all_direct_provider_full_confidence_is_zero():
    """全て `DIRECT_PROVIDER` かつ confidence 1.0 → `solution_gap = 0`。"""
    entries = [make_search(position, SolutionCategory.DIRECT_PROVIDER) for position in range(1, 11)]
    assert compute_solution_gap(entries) == pytest.approx(0.0)


def test_all_information_is_one_hundred():
    """解決策でない分類のみ → visibility 0 → `solution_gap = 100`。"""
    entries = [make_search(position, SolutionCategory.INFORMATION) for position in range(1, 11)]
    assert compute_solution_gap(entries) == pytest.approx(100.0)


def test_hand_calculated_two_results():
    """手計算: position 1 が DIRECT_PROVIDER、position 3 が INFORMATION。

    rank_weight(1) = 1/log2(2) = 1.0、rank_weight(3) = 1/log2(4) = 0.5
    visibility = 100 * (1.0*1.0*1.0) / (1.0 + 0.5) = 200/3 = 66.6666...
    solution_gap = 100 - 200/3 = 100/3 = 33.3333...
    """
    entries = [
        make_search(1, SolutionCategory.DIRECT_PROVIDER),
        make_search(3, SolutionCategory.INFORMATION),
    ]
    assert compute_solution_gap(entries) == pytest.approx(100 / 3)


def test_hand_calculated_mixed_categories():
    """手計算: MARKETPLACE(0.7) と GOVERNMENT(0.4) を順位重み込みで合成する。

    positions 1 / 3 / 7 → rank_weight 1.0 / 0.5 / 1/3
    visibility = 100 * (0.7*1.0 + 0.4*0.5 + 0.0*(1/3)) / (1.0 + 0.5 + 1/3)
    """
    entries = [
        make_search(1, SolutionCategory.MARKETPLACE),
        make_search(3, SolutionCategory.GOVERNMENT),
        make_search(7, SolutionCategory.NEWS),
    ]
    weights = (1.0, 0.5, 1 / 3)
    expected = 100.0 - 100.0 * (0.7 * 1.0 + 0.4 * 0.5) / sum(weights)
    assert compute_solution_gap(entries) == pytest.approx(expected)


def test_rank_weight_for_position_ten():
    """`position = 10` の順位重みは約 0.289(1/log2(11))。"""
    entries = [
        make_search(10, SolutionCategory.DIRECT_PROVIDER),
        make_search(1, SolutionCategory.INFORMATION),
    ]
    rank_ten = 1 / math.log2(11)
    assert rank_ten == pytest.approx(0.2890648)
    expected = 100.0 - 100.0 * rank_ten / (1.0 + rank_ten)
    assert compute_solution_gap(entries) == pytest.approx(expected)


def test_denominator_uses_all_top_n_results_not_only_classified_ones():
    """分母は対象 10 件すべての順位重みの合計(重み 0 の分類も分母に入る)。"""
    provider_only = [make_search(1, SolutionCategory.DIRECT_PROVIDER)]
    with_information = [
        make_search(1, SolutionCategory.DIRECT_PROVIDER),
        make_search(2, SolutionCategory.INFORMATION),
    ]
    assert compute_solution_gap(provider_only) == pytest.approx(0.0)
    gap = compute_solution_gap(with_information)
    assert gap is not None
    # 分母は 1/log2(2) + 1/log2(3) = 1 + 0.63093。分子は DIRECT_PROVIDER の 1.0 のみ。
    expected = 100.0 - 100.0 * 1.0 / (1.0 + 1.0 / math.log2(3.0))
    assert expected == pytest.approx(38.685281)
    assert gap == pytest.approx(expected)


def test_only_top_n_results_are_used():
    """上位 `TOP_N` 件だけを対象にする。11 件目以降は無視される。"""
    top = [make_search(position, SolutionCategory.DIRECT_PROVIDER) for position in range(1, 11)]
    extra = [make_search(position, SolutionCategory.INFORMATION) for position in range(11, 21)]
    assert len(top) == TOP_N
    assert compute_solution_gap([*top, *extra]) == pytest.approx(0.0)


def test_input_order_does_not_matter():
    """`position` 昇順に並べ替えるため、入力順に依存しない。"""
    entries = [
        make_search(
            position,
            SolutionCategory.DIRECT_PROVIDER if position <= 5 else SolutionCategory.INFORMATION,
        )
        for position in range(1, 13)
    ]
    forward = compute_solution_gap(entries)
    backward = compute_solution_gap(list(reversed(entries)))
    assert forward is not None
    assert forward == pytest.approx(backward)


def test_confidence_scales_visibility():
    """confidence 0.5 の DIRECT_PROVIDER 1件のみ → visibility 50 → gap 50。"""
    entries = [make_search(1, SolutionCategory.DIRECT_PROVIDER, confidence=0.5)]
    assert compute_solution_gap(entries) == pytest.approx(50.0)


def test_result_stays_within_bounds():
    entries = [
        make_search(1, SolutionCategory.DIRECT_PROVIDER),
        make_search(2, SolutionCategory.MARKETPLACE),
        make_search(3, SolutionCategory.GOVERNMENT),
        make_search(4, SolutionCategory.INFORMATION),
        make_search(5, SolutionCategory.NEWS),
        make_search(6, SolutionCategory.OTHER),
    ]
    gap = compute_solution_gap(entries)
    assert gap is not None
    assert 0.0 <= gap <= 100.0
