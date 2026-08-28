"""LLM 分類結果のモデル。

LLM は分類だけを行い `{"classification": ..., "confidence": ...}` を返す。
スコア計算は行わせない(AGENTS.md 絶対ルール)。
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field, field_validator

from gapatlas.domain.models.common import MODEL_CONFIG
from gapatlas.domain.models.normalized import NewsArticle, RisingQuery, SearchResultItem

CONFIDENCE_MIN = 0.0
CONFIDENCE_MAX = 1.0


class PainCategory(StrEnum):
    """rising query の困りごと分類(docs/scoring.md 3章)。"""

    ACCESS = "ACCESS"
    SHORTAGE = "SHORTAGE"
    WAIT_TIME = "WAIT_TIME"
    COST = "COST"
    QUALITY = "QUALITY"
    WORKFORCE = "WORKFORCE"
    NEUTRAL = "NEUTRAL"


class SolutionCategory(StrEnum):
    """検索結果の解決策カバレッジ分類(docs/scoring.md 4章)。"""

    DIRECT_PROVIDER = "DIRECT_PROVIDER"
    MARKETPLACE = "MARKETPLACE"
    GOVERNMENT = "GOVERNMENT"
    INFORMATION = "INFORMATION"
    NEWS = "NEWS"
    OTHER = "OTHER"


class NewsRelevance(StrEnum):
    """ニュース記事の関連性分類(docs/scoring.md 5章)。"""

    DIRECTLY_RELEVANT = "DIRECTLY_RELEVANT"
    RELATED = "RELATED"
    UNRELATED = "UNRELATED"


def _clip_confidence(value: float) -> float:
    """0.0〜1.0 へ clip する。

    LLM が範囲外を返しても処理を止めないため、例外にせず丸める
    (docs/scoring.md「confidence が範囲外の場合は clip する」)。
    """
    return max(CONFIDENCE_MIN, min(CONFIDENCE_MAX, value))


class PainClassification(BaseModel):
    """rising query 1件の分類結果。"""

    model_config = MODEL_CONFIG

    classification: PainCategory
    confidence: float = Field(default=CONFIDENCE_MAX)
    """0.0〜1.0。範囲外は clip される。"""

    @field_validator("confidence")
    @classmethod
    def _clip(cls, value: float) -> float:
        return _clip_confidence(value)


class SolutionClassification(BaseModel):
    """検索結果1件の分類結果。"""

    model_config = MODEL_CONFIG

    classification: SolutionCategory
    confidence: float = Field(default=CONFIDENCE_MAX)

    @field_validator("confidence")
    @classmethod
    def _clip(cls, value: float) -> float:
        return _clip_confidence(value)


class NewsClassification(BaseModel):
    """ニュース記事1件の分類結果。"""

    model_config = MODEL_CONFIG

    classification: NewsRelevance
    confidence: float = Field(default=CONFIDENCE_MAX)

    @field_validator("confidence")
    @classmethod
    def _clip(cls, value: float) -> float:
        return _clip_confidence(value)


class ClassifiedRisingQuery(BaseModel):
    """rising query と分類結果の組。"""

    model_config = MODEL_CONFIG

    item: RisingQuery
    classification: PainClassification


class ClassifiedSearchResult(BaseModel):
    """検索結果と分類結果の組。"""

    model_config = MODEL_CONFIG

    item: SearchResultItem
    classification: SolutionClassification


class ClassifiedNewsArticle(BaseModel):
    """ニュース記事と分類結果の組。"""

    model_config = MODEL_CONFIG

    item: NewsArticle
    classification: NewsClassification


class ClassifiedEvidence(BaseModel):
    """1国分の分類済み証拠データ。スコア計算の直接の入力になる。"""

    model_config = MODEL_CONFIG

    rising_queries: list[ClassifiedRisingQuery] = Field(default_factory=list)
    search_results: list[ClassifiedSearchResult] = Field(default_factory=list)
    news_articles: list[ClassifiedNewsArticle] = Field(default_factory=list)
