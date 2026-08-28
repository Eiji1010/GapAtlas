"""スコア計算結果のモデル(内部表現)。

内部表現は float、公開表現は int。両者を型で区別するため、公開用の int は
`result.py` の `CountryResult` / `RankingEntry` 側で持つ。
正本は docs/scoring.md。
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from gapatlas.domain.models.common import MODEL_CONFIG

SCORE_MIN = 0.0
SCORE_MAX = 100.0


class ScoreComponents(BaseModel):
    """Need Gap Score の4成分(内部 float 表現)。None は「算出不能」。

    None を 0 で代替してはいけない(docs/scoring.md)。
    """

    model_config = MODEL_CONFIG

    demand: float | None = Field(default=None, ge=SCORE_MIN, le=SCORE_MAX)
    pain: float | None = Field(default=None, ge=SCORE_MIN, le=SCORE_MAX)
    solution_gap: float | None = Field(default=None, ge=SCORE_MIN, le=SCORE_MAX)
    news_urgency: float | None = Field(default=None, ge=SCORE_MIN, le=SCORE_MAX)


class NeedGapResult(BaseModel):
    """Need Gap Signal Score の算出結果。"""

    model_config = MODEL_CONFIG

    score: float | None = Field(default=None, ge=SCORE_MIN, le=SCORE_MAX)
    """0〜100。算出不能なら None。"""

    components: ScoreComponents
    components_used: list[str] = Field(default_factory=list)
    """再正規化に使った成分名(`score_components_used`)。"""


class ConfidenceBreakdown(BaseModel):
    """Evidence Confidence の内訳(内部 float 表現)。各要素 0〜100。"""

    model_config = MODEL_CONFIG

    data_completeness: float = Field(ge=SCORE_MIN, le=SCORE_MAX)
    sample_sufficiency: float = Field(ge=SCORE_MIN, le=SCORE_MAX)
    localization_quality: float = Field(ge=SCORE_MIN, le=SCORE_MAX)
    source_agreement: float = Field(ge=SCORE_MIN, le=SCORE_MAX)
    freshness: float = Field(ge=SCORE_MIN, le=SCORE_MAX)


class ConfidenceResult(BaseModel):
    """Evidence Confidence の算出結果。Need Gap Score とは完全に別のスコア。"""

    model_config = MODEL_CONFIG

    score: float = Field(ge=SCORE_MIN, le=SCORE_MAX)
    """Hard Rules 適用後の 0〜100。"""

    breakdown: ConfidenceBreakdown
    applied_caps: list[str] = Field(default_factory=list)
    """適用された Hard Rule の識別子。"""
