"""Opportunity Brief 生成に渡す Evidence パックのモデル。

docs/llm-prompts.md 4章の JSON に対応する。**LLM へ生データを渡さない**ための境界で、
`summary` はコード側が生成済みの事実である。LLM はこれを言い換え・統合するだけで、
新しい事実や数値を足さない。

`EvidencePack` を組み立てるのは application 層の責務。このモジュールは受け取る側の
契約だけを定義する。
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from gapatlas.domain.models.common import MODEL_CONFIG, Country, SourceName, TopicId
from gapatlas.domain.models.result import (
    EVIDENCE_ID_PATTERN,
    PUBLIC_SCORE_MAX,
    PUBLIC_SCORE_MIN,
)


class EvidenceSummary(BaseModel):
    """Evidence 1件の要約。URL は渡さない(LLM に URL を書かせないため)。"""

    model_config = MODEL_CONFIG

    id: str = Field(pattern=EVIDENCE_ID_PATTERN)
    """`Evidence.id` と同じ "E1" 形式。本文中では `[E1]` として引用させる。"""

    source: SourceName
    summary: str


class BriefComponents(BaseModel):
    """成分スコアの公開表現(0〜100 の int)。算出不能な成分は None。"""

    model_config = MODEL_CONFIG

    demand: int | None = Field(default=None, ge=PUBLIC_SCORE_MIN, le=PUBLIC_SCORE_MAX)
    pain: int | None = Field(default=None, ge=PUBLIC_SCORE_MIN, le=PUBLIC_SCORE_MAX)
    solution_gap: int | None = Field(default=None, ge=PUBLIC_SCORE_MIN, le=PUBLIC_SCORE_MAX)
    news_urgency: int | None = Field(default=None, ge=PUBLIC_SCORE_MIN, le=PUBLIC_SCORE_MAX)


class EvidencePack(BaseModel):
    """Opportunity Brief 生成の唯一の入力。"""

    model_config = MODEL_CONFIG

    country: Country
    topic_id: TopicId
    need_gap_score: int | None = Field(default=None, ge=PUBLIC_SCORE_MIN, le=PUBLIC_SCORE_MAX)
    confidence: int = Field(ge=PUBLIC_SCORE_MIN, le=PUBLIC_SCORE_MAX)
    components: BriefComponents
    evidence: list[EvidenceSummary] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    """docs/methodology.md 由来の限界。`what_this_does_not_prove` の材料になる。"""

    @property
    def evidence_ids(self) -> list[str]:
        """入力 Evidence の id を入力順で返す。"""
        return [item.id for item in self.evidence]
