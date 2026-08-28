"""News Urgency(weight 10%)。docs/scoring.md 5章。

ニュースが少ないことを「問題が存在しない」と判断してはいけない。少なさは
Evidence Confidence の Sample sufficiency 側で扱う(docs/methodology.md)。
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from datetime import datetime

from gapatlas.domain.models.classification import (
    CONFIDENCE_MAX,
    CONFIDENCE_MIN,
    ClassifiedNewsArticle,
)
from gapatlas.domain.models.common import ensure_utc
from gapatlas.domain.scoring.constants import (
    NEWS_RELEVANCE_WEIGHTS,
    NEWS_SATURATION,
    RECENCY_DECAY_DAYS,
    SCORE_MAX,
    SCORE_MIN,
    SCORE_SCALE,
    SECONDS_PER_DAY,
)
from gapatlas.domain.scoring.rounding import clip


def _age_days(scan_time: datetime, published_at: datetime) -> float:
    """記事の古さ(日)。未来日付は 0 に丸める。"""
    return max(0.0, (scan_time - published_at).total_seconds() / SECONDS_PER_DAY)


def compute_news_urgency(
    classified: Sequence[ClassifiedNewsArticle], scan_time: datetime
) -> float | None:
    """ニュース記事の分類結果から News Urgency を算出する。

    `published_at` が `None` の記事は除外する(推測で日付を補わない)。
    記事が空、または日付を持つ記事が1件も無い場合は `None`。

    `scan_time` は引数で受け取る。関数内で現在時刻を取得しない。naive な
    datetime は `InvalidTemporalValueError` にする。
    """
    scan_time = ensure_utc(scan_time)

    news_mass = 0.0
    dated_count = 0
    for entry in classified:
        published_at = entry.item.published_at
        if published_at is None:
            continue
        dated_count += 1
        recency_weight = math.exp(-_age_days(scan_time, published_at) / RECENCY_DECAY_DAYS)
        relevance_weight = NEWS_RELEVANCE_WEIGHTS[entry.classification.classification]
        confidence = clip(entry.classification.confidence, CONFIDENCE_MIN, CONFIDENCE_MAX)
        news_mass += relevance_weight * confidence * recency_weight

    if dated_count == 0:
        return None

    # 飽和曲線のため定義上 100 を超えないが、浮動小数誤差に備えて clip する。
    return clip(
        SCORE_SCALE * (1.0 - math.exp(-news_mass / NEWS_SATURATION)),
        SCORE_MIN,
        SCORE_MAX,
    )
