"""スコア計算の定数。正本は docs/scoring.md。

この文書の計算定義・定数・重みを変えた場合は `SCORE_VERSION` を上げる
(docs/scoring.md 8章)。
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Final

from gapatlas.domain.models.classification import (
    NewsRelevance,
    PainCategory,
    SolutionCategory,
)
from gapatlas.domain.models.common import SourceName
from gapatlas.domain.models.query_profile import ReviewStatus

SCORE_VERSION: Final[str] = "gapatlas-score-v1"
"""結果へ記録するスコア定義のバージョン(docs/scoring.md 8章)。"""

SCORE_MIN: Final[float] = 0.0
SCORE_MAX: Final[float] = 100.0
"""公開スコアの値域。内部 float もこの範囲に clip する。"""

SCORE_SCALE: Final[float] = 100.0
"""0〜1 の比率を 0〜100 のスコアへ写す係数(docs/scoring.md の各式の `100 *`)。"""

SECONDS_PER_DAY: Final[float] = 86400.0

# --------------------------------------------------------------------------
# 1. Need Gap Signal Score
# --------------------------------------------------------------------------

COMPONENT_DEMAND: Final[str] = "demand"
COMPONENT_PAIN: Final[str] = "pain"
COMPONENT_SOLUTION_GAP: Final[str] = "solution_gap"
COMPONENT_NEWS_URGENCY: Final[str] = "news_urgency"
"""成分名。`ScoreComponents` のフィールド名と一致させること。"""

WEIGHT_DEMAND: Final[float] = 0.40
WEIGHT_PAIN: Final[float] = 0.25
WEIGHT_SOLUTION_GAP: Final[float] = 0.25
WEIGHT_NEWS_URGENCY: Final[float] = 0.10

NEED_GAP_WEIGHTS: Final[Mapping[str, float]] = {
    COMPONENT_DEMAND: WEIGHT_DEMAND,
    COMPONENT_PAIN: WEIGHT_PAIN,
    COMPONENT_SOLUTION_GAP: WEIGHT_SOLUTION_GAP,
    COMPONENT_NEWS_URGENCY: WEIGHT_NEWS_URGENCY,
}
"""Need Gap Score の成分重み。欠損成分を除いた合計で再正規化する。"""

# --------------------------------------------------------------------------
# 2. Demand Momentum
# --------------------------------------------------------------------------

WINDOW_WEEKS: Final[int] = 12
RECENT_WEEKS: Final[int] = 4
PREVIOUS_WEEKS: Final[int] = 8
SMOOTHING: Final[float] = 5.0

RATIO_SCORE_WEIGHT: Final[float] = 0.70
SLOPE_SCORE_WEIGHT: Final[float] = 0.30
"""`query_demand_score = 0.70 * ratio_score + 0.30 * slope_score`。"""

SCORE_MIDPOINT: Final[float] = 50.0
"""変化率 0 のときのスコア。±50% の変化で 100 / 0 になる感度。"""

CHANGE_SENSITIVITY: Final[float] = 100.0
"""変化率をスコアへ写す係数。`50 + 100 * (r - 1)` の 100。"""

# --------------------------------------------------------------------------
# 3. Pain Signal
# --------------------------------------------------------------------------

BREAKOUT_GROWTH_PERCENT: Final[float] = 5000.0
"""`"Breakout"` / `"Record"` / 未知文字列の代替値(正規化はアダプタ側で実施済み)。"""

GROWTH_CAP_PERCENT: Final[float] = 5000.0

PAIN_CATEGORY_WEIGHTS: Final[Mapping[PainCategory, float]] = {
    PainCategory.SHORTAGE: 1.00,
    PainCategory.WAIT_TIME: 1.00,
    PainCategory.ACCESS: 0.90,
    PainCategory.WORKFORCE: 0.80,
    PainCategory.COST: 0.70,
    PainCategory.QUALITY: 0.60,
    PainCategory.NEUTRAL: 0.00,
}
"""困りごと分類の重み(docs/scoring.md 3章)。全メンバーを網羅する。"""

# --------------------------------------------------------------------------
# 4. Solution Coverage Gap
# --------------------------------------------------------------------------

TOP_N: Final[int] = 10

SOLUTION_COVERAGE_WEIGHTS: Final[Mapping[SolutionCategory, float]] = {
    SolutionCategory.DIRECT_PROVIDER: 1.0,
    SolutionCategory.MARKETPLACE: 0.7,
    SolutionCategory.GOVERNMENT: 0.4,
    SolutionCategory.INFORMATION: 0.0,
    SolutionCategory.NEWS: 0.0,
    SolutionCategory.OTHER: 0.0,
}
"""解決策カバレッジ重み(docs/scoring.md 4章)。全メンバーを網羅する。"""

# --------------------------------------------------------------------------
# 5. News Urgency
# --------------------------------------------------------------------------

NEWS_SATURATION: Final[float] = 5.0

NEWS_RELEVANCE_WEIGHTS: Final[Mapping[NewsRelevance, float]] = {
    NewsRelevance.DIRECTLY_RELEVANT: 1.0,
    NewsRelevance.RELATED: 0.5,
    NewsRelevance.UNRELATED: 0.0,
}
"""ニュース関連性重み(docs/scoring.md 5章)。全メンバーを網羅する。"""

RECENCY_DECAY_DAYS: Final[float] = 30.0
"""`recency_weight = exp(-age_days / 30)`。"""

# --------------------------------------------------------------------------
# 6. Evidence Confidence
# --------------------------------------------------------------------------

CONFIDENCE_WEIGHT_DATA_COMPLETENESS: Final[float] = 0.30
CONFIDENCE_WEIGHT_SAMPLE_SUFFICIENCY: Final[float] = 0.25
CONFIDENCE_WEIGHT_LOCALIZATION_QUALITY: Final[float] = 0.20
CONFIDENCE_WEIGHT_SOURCE_AGREEMENT: Final[float] = 0.15
CONFIDENCE_WEIGHT_FRESHNESS: Final[float] = 0.10

SAMPLE_TARGETS: Final[Mapping[SourceName, int]] = {
    SourceName.TRENDS: 12,
    SourceName.RELATED_QUERIES: 10,
    SourceName.SEARCH: 10,
    SourceName.NEWS: 5,
}
"""Sample sufficiency の目標件数(docs/scoring.md 6章)。Core Source のみ。"""

LOCALIZATION_QUALITY_BY_REVIEW_STATUS: Final[Mapping[ReviewStatus, float]] = {
    ReviewStatus.MANUAL_REVIEWED: 100.0,
    ReviewStatus.LLM_GENERATED: 70.0,
}
"""Localization quality の基準値。全メンバーを網羅する。"""

NON_PRIMARY_LANGUAGE_PENALTY: Final[float] = 20.0
"""QueryProfile の `language` がその国の主要言語でない場合に減じる値(下限 0)。"""

MIN_AGREEMENT_COMPONENTS: Final[int] = 2
"""Source agreement を算出するのに必要な下位スコアの最小数。"""

AGREEMENT_SPREAD_FACTOR: Final[float] = 2.0
"""`100 * (1 - 2 * pstdev(s))` の 2。pstdev の最大 0.5 に対応する。"""

FRESHNESS_DECAY_DAYS: Final[float] = 30.0
"""`freshness_s = 100 * exp(-age_days / 30)`。"""

# --------------------------------------------------------------------------
# Hard Rules
# --------------------------------------------------------------------------

MULTIPLE_MISSING_CORE_SOURCES_THRESHOLD: Final[int] = 2
"""Hard Rule 2: Core Source の MISSING がこの数以上で INSUFFICIENT_EVIDENCE。"""

SINGLE_MISSING_CORE_SOURCE_COUNT: Final[int] = 1
"""Hard Rule 3: Core Source の MISSING がちょうどこの数のとき Confidence を制限。"""

MISSING_ONE_CORE_SOURCE_CAP: Final[float] = 69.0
TRENDS_ZERO_RATIO_CAP: Final[float] = 59.0

ZERO_RATIO_THRESHOLD: Final[float] = 0.5
"""Hard Rule 4: Trends 全データ点のゼロ率がこの値以上で Confidence を制限。"""

CAP_TRENDS_MISSING: Final[str] = "trends_missing"
"""Hard Rule 1。`need_gap_score = None`。Confidence の上限は課さない。"""

CAP_MULTIPLE_MISSING_CORE_SOURCES: Final[str] = "multiple_missing_core_sources"
"""Hard Rule 2。`need_gap_score = None`。Confidence の上限は課さない。"""

CAP_MISSING_ONE_CORE_SOURCE: Final[str] = "missing_one_core_source"
"""Hard Rule 3。`confidence = min(confidence, 69)`。"""

CAP_TRENDS_ZERO_RATIO: Final[str] = "trends_zero_ratio"
"""Hard Rule 4。`confidence = min(confidence, 59)`。"""
