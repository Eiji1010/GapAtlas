"""Demand Momentum のテスト。docs/scoring.md 2章。

期待値は仕様の式から手で導いた定数であり、実装を写したものではない。
"""

from __future__ import annotations

import pytest
from conftest import make_series, make_trends

from gapatlas.domain.models.normalized import TrendsSeries, TrendsTimeseries
from gapatlas.domain.scoring.demand import compute_demand, compute_query_demand_score

# --- 手計算の基準系列 -------------------------------------------------------
# y = [10]*8 + [12]*4
#   previous_mean = 10, recent_mean = 12
#   r = (12 + 5) / (10 + 5) = 17/15
#   ratio_score = 50 + 100 * (17/15 - 1) = 50 + 100 * 2/15 = 190/3 = 63.333333...
#   y_mean = (80 + 48) / 12 = 32/3
#   Σ((x-5.5)(y-ymean)) = (-2/3)*(-16) + (4/3)*16 = 32/3 + 64/3 = 32
#   Σ((x-5.5)^2) = 143  →  slope = 32/143
#   relative_change = (32/143) * 11 / (32/3 + 5) = (352/143) / (47/3) = 96/611
#   slope_score = 50 + 100 * 96/611 = 40150/611 = 65.711947626841...
#   query_demand_score = 0.70 * 190/3 + 0.30 * 40150/611 = 64.0469176213857
RISING_SERIES = [10.0] * 8 + [12.0] * 4
RISING_RATIO_SCORE = 190 / 3
RISING_SLOPE_SCORE = 40150 / 611
RISING_QUERY_SCORE = 0.70 * RISING_RATIO_SCORE + 0.30 * RISING_SLOPE_SCORE


def test_hand_calculated_query_demand_score():
    """既知の12点系列に対する値を、仕様の式から手で導いた定数と比較する。"""
    assert pytest.approx(63.333333333333336) == RISING_RATIO_SCORE
    assert pytest.approx(65.71194762684124) == RISING_SLOPE_SCORE
    assert compute_query_demand_score(RISING_SERIES) == pytest.approx(64.0469176213857)


def test_eleven_points_is_not_computable():
    """週次データ点が 11 点 → 計算不能(docs/scoring.md 9章)。"""
    assert compute_query_demand_score([50.0] * 11) is None


def test_exactly_twelve_points_is_computable():
    assert compute_query_demand_score([50.0] * 12) is not None


def test_only_last_twelve_points_are_used():
    """末尾 12 点だけを使う。先頭に別の値を足しても結果は変わらない。"""
    long_series = [0.0, 999.0, 3.0, *RISING_SERIES]
    assert compute_query_demand_score(long_series) == pytest.approx(RISING_QUERY_SCORE)


def test_all_zero_series_scores_fifty():
    """全て 0 → r = 1 → ratio_score = 50、slope = 0 → slope_score = 50、demand = 50。

    ゼロ除算が起きないこと(`SMOOTHING` により分母は常に 5 以上)。
    """
    assert compute_query_demand_score([0.0] * 12) == pytest.approx(50.0)


def test_flat_series_scores_fifty_at_any_level():
    """水準に依存しない性質: 平坦な系列はどの水準でも必ず 50 になる。"""
    for level in (0.0, 1.0, 10.0, 100.0, 1e6):
        assert compute_query_demand_score([level] * 12) == pytest.approx(50.0)


def test_score_is_scale_invariant_in_the_high_volume_limit():
    """`SMOOTHING` の影響が無視できる水準では、定数倍しても同じスコアになる。

    docs/scoring.md の Demand Momentum は変化率のみを見る設計だが、
    `SMOOTHING = 5.0` を分母に足すため、値が小さい領域では厳密な定数倍不変
    にはならない(低ボリュームの跳ねを抑えるための意図的な減衰)。
    """
    base = [10.0] * 8 + [12.0] * 4
    large = [value * 1e6 for value in base]
    larger = [value * 1e7 for value in base]
    assert compute_query_demand_score(large) == pytest.approx(
        compute_query_demand_score(larger), abs=1e-4
    )


def test_smoothing_damps_low_volume_series():
    """低水準では `SMOOTHING` により変化が控えめに評価される。"""
    low = compute_query_demand_score([10.0] * 8 + [12.0] * 4)
    high = compute_query_demand_score([1000.0] * 8 + [1200.0] * 4)
    assert low is not None
    assert high is not None
    assert 50.0 < low < high


def test_ratio_clip_upper_bound():
    """`r` が非常に大きいとき clip が効く(0〜100 を超えない)。"""
    score = compute_query_demand_score([0.0] * 8 + [10000.0] * 4)
    assert score == pytest.approx(100.0)


def test_ratio_clip_lower_bound():
    """`r` が非常に小さいとき clip が効く。"""
    score = compute_query_demand_score([10000.0] * 8 + [0.0] * 4)
    assert score == pytest.approx(0.0)


def test_zero_previous_and_recent_mean_does_not_divide_by_zero():
    """`previous_mean = 0`, `recent_mean = 0` でゼロ除算しない。"""
    assert compute_query_demand_score([0.0] * 12) == pytest.approx(50.0)


def test_points_are_read_oldest_first():
    """モデルが古い順へ整列するため、入力順を逆にしても同じ結果になる。"""
    series = make_series(RISING_SERIES)
    shuffled = TrendsSeries(query=series.query, points=list(reversed(series.points)))
    assert compute_demand(TrendsTimeseries(series=[shuffled])) == pytest.approx(RISING_QUERY_SCORE)


def test_compute_demand_returns_none_for_none_trends():
    assert compute_demand(None) is None


def test_compute_demand_returns_none_when_no_series():
    assert compute_demand(TrendsTimeseries(series=[])) is None


def test_compute_demand_returns_none_when_all_series_too_short():
    assert compute_demand(make_trends([50.0] * 11, [50.0] * 5)) is None


def test_compute_demand_is_median_of_computable_queries():
    """3件のうち1件だけ 11 点 → そのクエリを除外し、残り2件の中央値を使う。"""
    rising = RISING_SERIES
    falling = [12.0] * 8 + [10.0] * 4
    trends = make_trends(rising, [50.0] * 11, falling)

    rising_score = compute_query_demand_score(rising)
    falling_score = compute_query_demand_score(falling)
    assert rising_score is not None
    assert falling_score is not None

    expected = (rising_score + falling_score) / 2
    assert compute_demand(trends) == pytest.approx(expected)


def test_compute_demand_median_of_three():
    trends = make_trends([0.0] * 8 + [10000.0] * 4, RISING_SERIES, [10000.0] * 8 + [0.0] * 4)
    assert compute_demand(trends) == pytest.approx(RISING_QUERY_SCORE)
