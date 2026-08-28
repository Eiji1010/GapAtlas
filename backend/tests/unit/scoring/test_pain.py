"""Pain Signal のテスト。docs/scoring.md 3章。"""

from __future__ import annotations

import math

import pytest
from conftest import make_rising

from gapatlas.domain.models.classification import PainCategory
from gapatlas.domain.scoring.constants import (
    BREAKOUT_GROWTH_PERCENT,
    GROWTH_CAP_PERCENT,
    PAIN_CATEGORY_WEIGHTS,
)
from gapatlas.domain.scoring.pain import compute_pain


def test_category_weight_table_covers_all_members():
    """重み表が `PainCategory` の全メンバーを網羅していること。"""
    assert set(PAIN_CATEGORY_WEIGHTS) == set(PainCategory)


# docs/scoring.md 3章「カテゴリ重み」の表。**実装の定数を参照せずリテラルで書く。**
# 実装側を参照すると自己参照になり、値を書き換えても検出できない。
SPEC_PAIN_WEIGHTS = [
    (PainCategory.SHORTAGE, 1.00),
    (PainCategory.WAIT_TIME, 1.00),
    (PainCategory.ACCESS, 0.90),
    (PainCategory.WORKFORCE, 0.80),
    (PainCategory.COST, 0.70),
    (PainCategory.QUALITY, 0.60),
    (PainCategory.NEUTRAL, 0.00),
]


@pytest.mark.parametrize(("category", "weight"), SPEC_PAIN_WEIGHTS)
def test_each_category_weight_matches_the_spec_table(category, weight):
    """全7カテゴリの重みを実測で固定する。

    1件だけなら `g` が約分されるので `pain == 100 * w * c`(confidence 1.0)。
    """
    assert compute_pain([make_rising(300.0, category)]) == pytest.approx(100.0 * weight)


@pytest.mark.parametrize(("category", "weight"), SPEC_PAIN_WEIGHTS)
def test_constant_table_matches_the_spec_table(category, weight):
    """定数表そのものも仕様のリテラルと突き合わせる。"""
    assert PAIN_CATEGORY_WEIGHTS[category] == pytest.approx(weight)


def test_growth_cap_constant_matches_the_spec():
    """docs/scoring.md 3章 定数表: `GROWTH_CAP_PERCENT = 5000.0`。"""
    assert GROWTH_CAP_PERCENT == 5000.0
    assert BREAKOUT_GROWTH_PERCENT == 5000.0


def test_growth_above_the_cap_is_clipped_to_five_thousand():
    """上限超えの成長率が 5000 と同じ `g` になること。

    `edge_cases/trends_related_queries_breakout.json` には
    `extracted_value: 12000` が実在する。cap がずれると両者の重みが食い違い、
    SHORTAGE と NEUTRAL 各1件でも 50.0 にならない。
    """
    entries = [
        make_rising(12000.0, PainCategory.SHORTAGE),
        make_rising(5000.0, PainCategory.NEUTRAL),
    ]
    assert compute_pain(entries) == pytest.approx(50.0)


def test_empty_rising_is_none():
    """rising が空 → `pain = None`(docs/scoring.md 9章)。"""
    assert compute_pain([]) is None


def test_all_zero_growth_is_none():
    """`Σ(g_i) == 0` → `None`。`log1p(0) == 0` のため分母が 0 になる。"""
    entries = [make_rising(0.0, PainCategory.SHORTAGE), make_rising(0.0, PainCategory.COST)]
    assert compute_pain(entries) is None


def test_all_neutral_is_zero_not_none():
    """rising が全て `NEUTRAL` → `pain = 0`(`None` ではない)。"""
    entries = [make_rising(100.0, PainCategory.NEUTRAL), make_rising(250.0, PainCategory.NEUTRAL)]
    assert compute_pain(entries) == pytest.approx(0.0)


def test_single_entry_is_weight_times_confidence():
    """1件だけなら `100 * w * c`(g が約分されるため成長率に依存しない)。

    ACCESS の重み 0.90、confidence 0.5 → 100 * 0.90 * 0.5 = 45.0。
    """
    entries = [make_rising(300.0, PainCategory.ACCESS, confidence=0.5)]
    assert compute_pain(entries) == pytest.approx(45.0)


def test_equal_growth_mixes_by_category_weight():
    """同じ成長率の SHORTAGE(1.0) と NEUTRAL(0.0) → 50.0。手計算。

    pain = 100 * (1.0*1.0*ln(101) + 0.0) / (2*ln(101)) = 50.0
    """
    entries = [
        make_rising(100.0, PainCategory.SHORTAGE),
        make_rising(100.0, PainCategory.NEUTRAL),
    ]
    assert compute_pain(entries) == pytest.approx(50.0)


def test_hand_calculated_mixed_weights():
    """手計算の期待値と一致すること。

    g1 = ln(1+99) = ln(100)、g2 = ln(1+999) = ln(1000)
    w1 = 0.70 (COST) * c1 = 1.0、w2 = 0.60 (QUALITY) * c2 = 0.5
    pain = 100 * (0.70*ln(100) + 0.30*ln(1000)) / (ln(100) + ln(1000))
        = 100 * (0.70*2 + 0.30*3) * ln(10) / (5 * ln(10))
        = 100 * 2.3 / 5 = 46.0
    """
    entries = [
        make_rising(99.0, PainCategory.COST, confidence=1.0),
        make_rising(999.0, PainCategory.QUALITY, confidence=0.5),
    ]
    g1 = math.log(100.0)
    g2 = math.log(1000.0)
    assert 100.0 * (0.70 * g1 + 0.60 * 0.5 * g2) / (g1 + g2) == pytest.approx(46.0)
    assert compute_pain(entries) == pytest.approx(46.0)


def test_growth_is_capped():
    """`GROWTH_CAP_PERCENT` を超える成長率は clip される。

    上限値ちょうどのものと上限超えのものは同じ重みになるため、
    SHORTAGE 1件(上限超え)と NEUTRAL 1件(上限ちょうど)は 50.0 になる。
    """
    entries = [
        make_rising(GROWTH_CAP_PERCENT * 10, PainCategory.SHORTAGE),
        make_rising(GROWTH_CAP_PERCENT, PainCategory.NEUTRAL),
    ]
    assert compute_pain(entries) == pytest.approx(50.0)


def test_breakout_value_does_not_raise():
    """`"Breakout"` / `"Record"` / 未知文字列(= 5000.0 に正規化済み)で例外を投げない。"""
    entries = [make_rising(BREAKOUT_GROWTH_PERCENT, PainCategory.WAIT_TIME)]
    assert compute_pain(entries) == pytest.approx(100.0)


def test_all_maximum_weight_is_one_hundred():
    entries = [
        make_rising(100.0, PainCategory.SHORTAGE),
        make_rising(500.0, PainCategory.WAIT_TIME),
    ]
    assert compute_pain(entries) == pytest.approx(100.0)


def test_result_stays_within_bounds():
    entries = [
        make_rising(growth, category)
        for growth, category in [
            (30.0, PainCategory.ACCESS),
            (4500.0, PainCategory.WORKFORCE),
            (120.0, PainCategory.NEUTRAL),
            (450.0, PainCategory.SHORTAGE),
        ]
    ]
    pain = compute_pain(entries)
    assert pain is not None
    assert 0.0 <= pain <= 100.0
