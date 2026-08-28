"""Pain Signal(weight 25%)。docs/scoring.md 3章。

rising query の **構成**(困りごと系の成長がどれだけの割合を占めるか)を測る。
件数の少なさは Pain ではなく Evidence Confidence の Sample sufficiency で扱う。
"""

from __future__ import annotations

import math
from collections.abc import Sequence

from gapatlas.domain.models.classification import (
    CONFIDENCE_MAX,
    CONFIDENCE_MIN,
    ClassifiedRisingQuery,
)
from gapatlas.domain.scoring.constants import (
    GROWTH_CAP_PERCENT,
    PAIN_CATEGORY_WEIGHTS,
    SCORE_MAX,
    SCORE_MIN,
    SCORE_SCALE,
)
from gapatlas.domain.scoring.rounding import clip


def compute_pain(classified: Sequence[ClassifiedRisingQuery]) -> float | None:
    """rising query の分類結果から Pain Signal を算出する。

    `RisingQuery.growth_percent` はアダプタ側で正規化済み("Breakout" 等は
    `BREAKOUT_GROWTH_PERCENT` になっている)。ここでは上限で clip し `log1p`
    で圧縮するだけである。

    `Σ(g_i) == 0`(rising が空、または全件の成長率が 0)の場合は `None`。
    全件が `NEUTRAL` の場合は `0.0` であり `None` ではない。
    """
    numerator = 0.0
    denominator = 0.0
    for entry in classified:
        growth = clip(entry.item.growth_percent, 0.0, GROWTH_CAP_PERCENT)
        compressed_growth = math.log1p(growth)
        category_weight = PAIN_CATEGORY_WEIGHTS[entry.classification.classification]
        confidence = clip(entry.classification.confidence, CONFIDENCE_MIN, CONFIDENCE_MAX)
        numerator += category_weight * confidence * compressed_growth
        denominator += compressed_growth

    if denominator == 0.0:
        return None
    # 定義上 0〜100 に収まるが、浮動小数誤差に備えて clip する。
    return clip(SCORE_SCALE * numerator / denominator, SCORE_MIN, SCORE_MAX)
