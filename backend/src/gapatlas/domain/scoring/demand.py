"""Demand Momentum(weight 40%)。docs/scoring.md 2章。

Google Trends の 0〜100 値は検索期間・地域内の相対値であるため、国同士の
絶対比較には使えない。ここでは **変化率のみ** を使い、水準を比較しない。
"""

from __future__ import annotations

from collections.abc import Sequence
from statistics import fmean, median

from gapatlas.domain.models.normalized import TrendsTimeseries
from gapatlas.domain.scoring.constants import (
    CHANGE_SENSITIVITY,
    PREVIOUS_WEEKS,
    RATIO_SCORE_WEIGHT,
    SCORE_MAX,
    SCORE_MIDPOINT,
    SCORE_MIN,
    SLOPE_SCORE_WEIGHT,
    SMOOTHING,
    WINDOW_WEEKS,
)
from gapatlas.domain.scoring.rounding import clip


def _ratio_score(window: Sequence[float]) -> float:
    """直近4週と前8週の比からスコアを出す。

    `SMOOTHING` により分母は常に 5 以上となるためゼロ除算は発生しない。
    """
    previous_mean = fmean(window[:PREVIOUS_WEEKS])
    recent_mean = fmean(window[PREVIOUS_WEEKS:])
    ratio = (recent_mean + SMOOTHING) / (previous_mean + SMOOTHING)
    return clip(SCORE_MIDPOINT + CHANGE_SENSITIVITY * (ratio - 1.0), SCORE_MIN, SCORE_MAX)


def _slope_score(window: Sequence[float]) -> float:
    """最小二乗法の傾きを窓全体の相対変化へ変換してスコアにする。

    `x` は 0..n-1 の定数列ではないので分母は常に正(n=12 のとき 143.0)。
    """
    n = len(window)
    x_mean = (n - 1) / 2.0
    y_mean = fmean(window)
    numerator = sum((index - x_mean) * (value - y_mean) for index, value in enumerate(window))
    denominator = sum((index - x_mean) ** 2 for index in range(n))
    slope = numerator / denominator
    relative_change = slope * (n - 1) / (y_mean + SMOOTHING)
    return clip(
        SCORE_MIDPOINT + CHANGE_SENSITIVITY * relative_change,
        SCORE_MIN,
        SCORE_MAX,
    )


def compute_query_demand_score(points: Sequence[float]) -> float | None:
    """1クエリ分の Demand Momentum。

    `points` は古い順(最後が最新)。末尾 `WINDOW_WEEKS` 点だけを使う。
    12 点未満の系列は計算不能として `None` を返す(0 で代替しない)。
    """
    if len(points) < WINDOW_WEEKS:
        return None
    window = list(points[-WINDOW_WEEKS:])
    score = RATIO_SCORE_WEIGHT * _ratio_score(window) + SLOPE_SCORE_WEIGHT * _slope_score(window)
    # 各項は clip 済みなので定義上 0〜100 に収まる。浮動小数誤差で
    # 100 をわずかに超えることがあるため最後にもう一度 clip する。
    return clip(score, SCORE_MIN, SCORE_MAX)


def compute_demand(trends: TrendsTimeseries | None) -> float | None:
    """複数 demand query の Demand Momentum を中央値で合成する。

    計算可能なクエリが1つも無い場合は `None`。
    """
    if trends is None:
        return None
    scores = [
        score
        for series in trends.series
        if (score := compute_query_demand_score([point.value for point in series.points]))
        is not None
    ]
    if not scores:
        return None
    return median(scores)
