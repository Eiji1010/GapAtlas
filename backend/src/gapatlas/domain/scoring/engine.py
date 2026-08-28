"""スコアリングの統合点。docs/scoring.md 6章 Hard Rules と 7章 ステータス。

Need Gap Score と Evidence Confidence の状態遷移は両者に跨るため、
`evaluate_country` 1つの純粋関数で決める。呼び出し側でこの判定を再実装しない。
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from gapatlas.domain.models.classification import ClassifiedEvidence
from gapatlas.domain.models.common import (
    MODEL_CONFIG,
    CountryStatus,
    SourceName,
    ensure_utc,
)
from gapatlas.domain.models.normalized import NormalizedEvidence
from gapatlas.domain.models.query_profile import QueryProfile
from gapatlas.domain.models.scores import ConfidenceResult, NeedGapResult
from gapatlas.domain.scoring.confidence import compute_confidence
from gapatlas.domain.scoring.constants import (
    MULTIPLE_MISSING_CORE_SOURCES_THRESHOLD,
    SCORE_MAX,
    SCORE_MIN,
)
from gapatlas.domain.scoring.need_gap import compute_components, compute_need_gap
from gapatlas.domain.scoring.rounding import clip, round_half_up


class PublicComponents(BaseModel):
    """公開表現の4成分(0〜100 の整数)。算出不能なら None。"""

    model_config = MODEL_CONFIG

    demand: int | None = None
    pain: int | None = None
    solution_gap: int | None = None
    news_urgency: int | None = None


class CountryEvaluation(BaseModel):
    """1国分のスコアリング結果。内部 float 表現と公開 int 表現の両方を持つ。"""

    model_config = MODEL_CONFIG

    status: CountryStatus
    """`COMPLETED` または `INSUFFICIENT_EVIDENCE` のみ。`FAILED` は呼び出し側の責務。"""

    need_gap: NeedGapResult
    confidence: ConfidenceResult
    public_need_gap_score: int | None
    public_confidence: int
    """`INSUFFICIENT_EVIDENCE` でも必ず算出して返す。"""

    public_components: PublicComponents


def _to_public(value: float | None) -> int | None:
    if value is None:
        return None
    return round_half_up(clip(value, SCORE_MIN, SCORE_MAX))


def evaluate_country(
    evidence: NormalizedEvidence,
    classified: ClassifiedEvidence,
    profile: QueryProfile,
    scan_time: datetime,
) -> CountryEvaluation:
    """1国分の Need Gap Score と Evidence Confidence を算出する。

    処理順は docs/scoring.md 6章「Hard Rules」の順序に従う。

    1. 4成分を算出する
    2. 素の Need Gap Score を算出する
    3. Confidence を算出する(Hard Rules 3・4 は `compute_confidence` 内で適用)
    4. Hard Rule 1: `trends` が MISSING → `need_gap_score = None`
    5. Hard Rule 2: Core Source の MISSING が2つ以上 → `need_gap_score = None`
    6. `demand` が `None`(Trends は OK だが 12 点未満など)→ `need_gap_score = None`
    7. それ以外は `COMPLETED`
    8. 公開表現へ四捨五入する

    `INSUFFICIENT_EVIDENCE` はエラーではない。部分的な結果と Confidence を返し、
    ランキングからは除外する(除外は application 層の責務)。

    `scan_time` は引数で受け取る。関数内で現在時刻を取得しない。
    """
    scan_time = ensure_utc(scan_time)

    components = compute_components(evidence, classified, scan_time)
    need_gap = compute_need_gap(components)
    confidence = compute_confidence(evidence, profile, components, scan_time)

    missing_core_sources = evidence.missing_core_sources()
    trends_missing = SourceName.TRENDS in missing_core_sources
    multiple_missing = len(missing_core_sources) >= MULTIPLE_MISSING_CORE_SOURCES_THRESHOLD
    demand_missing = components.demand is None

    if trends_missing or multiple_missing or demand_missing:
        status = CountryStatus.INSUFFICIENT_EVIDENCE
        # Hard Rules によりスコアを取り消す。どの成分が計算できたかは
        # `components` と `components_used` に残す。
        need_gap = NeedGapResult(
            score=None,
            components=need_gap.components,
            components_used=need_gap.components_used,
        )
    else:
        status = CountryStatus.COMPLETED

    return CountryEvaluation(
        status=status,
        need_gap=need_gap,
        confidence=confidence,
        public_need_gap_score=_to_public(need_gap.score),
        public_confidence=round_half_up(clip(confidence.score, SCORE_MIN, SCORE_MAX)),
        public_components=PublicComponents(
            demand=_to_public(components.demand),
            pain=_to_public(components.pain),
            solution_gap=_to_public(components.solution_gap),
            news_urgency=_to_public(components.news_urgency),
        ),
    )
