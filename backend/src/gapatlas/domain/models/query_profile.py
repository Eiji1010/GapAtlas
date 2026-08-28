"""QueryProfile モデル。

正本は docs/query-profiles.md。件数制約はここで強制する。
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field, field_validator

from gapatlas.domain.models.common import MODEL_CONFIG, Country, TopicId
from gapatlas.domain.models.errors import DomainValidationError

MAX_DEMAND_QUERIES = 5
"""Trends TIMESERIES はカンマ区切りで最大5語まで比較可能(docs/serpapi-schema.md)。"""


class ReviewStatus(StrEnum):
    """QueryProfile のレビュー状態。Localization quality に直結する。"""

    LLM_GENERATED = "LLM_GENERATED"
    MANUAL_REVIEWED = "MANUAL_REVIEWED"


def _require_non_blank_items(values: list[str], field_name: str) -> list[str]:
    for index, value in enumerate(values):
        if not value.strip():
            message = f"{field_name}[{index}] must not be empty or whitespace-only"
            raise DomainValidationError(message)
    return values


def _require_exactly_one(values: list[str], field_name: str) -> list[str]:
    if len(values) != 1:
        message = f"{field_name} must contain exactly 1 item, got {len(values)}"
        raise DomainValidationError(message)
    return _require_non_blank_items(values, field_name)


class SerpApiParams(BaseModel):
    """SerpApi へ渡す地域・言語パラメータ。すべて必須・非空。"""

    model_config = MODEL_CONFIG

    geo: str = Field(min_length=1)
    """Google Trends の地域指定(Trends には gl / google_domain が無い)。"""

    gl: str = Field(min_length=1)
    """Google Search / News / Maps の国指定。GB は "uk" のように geo と異なる。"""

    hl: str = Field(min_length=1)
    """言語指定。"""

    google_domain: str = Field(min_length=1)
    """Google Search / Maps 用のドメイン。"""

    @field_validator("geo", "gl", "hl", "google_domain")
    @classmethod
    def _reject_blank(cls, value: str) -> str:
        if not value.strip():
            message = "serpapi parameter must not be whitespace-only"
            raise DomainValidationError(message)
        return value


class QueryProfile(BaseModel):
    """国別クエリ定義。`config/query_profiles/<topic_id>/<COUNTRY>.yaml` に対応する。"""

    model_config = MODEL_CONFIG

    topic_id: TopicId
    country: Country
    language: str = Field(min_length=1)
    """ISO 639-1。Localization quality の判定に使う。"""

    version: str = Field(min_length=1)
    """結果の `query_profile_version` として記録される。"""

    review_status: ReviewStatus
    serpapi: SerpApiParams

    demand_queries: list[str]
    """Trends TIMESERIES 用。1〜5件。"""

    related_query_seed: list[str]
    """Trends RELATED_QUERIES 用。ちょうど1件(1リクエスト1クエリのみ)。"""

    solution_query: list[str]
    """Google Search 用。ちょうど1件。"""

    news_query: list[str]
    """Google News 用。ちょうど1件。"""

    @field_validator("demand_queries")
    @classmethod
    def _validate_demand_queries(cls, values: list[str]) -> list[str]:
        if not 1 <= len(values) <= MAX_DEMAND_QUERIES:
            message = (
                f"demand_queries must contain between 1 and {MAX_DEMAND_QUERIES} items, "
                f"got {len(values)}"
            )
            raise DomainValidationError(message)
        return _require_non_blank_items(values, "demand_queries")

    @field_validator("related_query_seed")
    @classmethod
    def _validate_related_query_seed(cls, values: list[str]) -> list[str]:
        return _require_exactly_one(values, "related_query_seed")

    @field_validator("solution_query")
    @classmethod
    def _validate_solution_query(cls, values: list[str]) -> list[str]:
        return _require_exactly_one(values, "solution_query")

    @field_validator("news_query")
    @classmethod
    def _validate_news_query(cls, values: list[str]) -> list[str]:
        return _require_exactly_one(values, "news_query")

    @property
    def related_seed(self) -> str:
        """RELATED_QUERIES に渡す唯一のクエリ。"""
        return self.related_query_seed[0]

    @property
    def solution(self) -> str:
        """Google Search に渡す唯一のクエリ。"""
        return self.solution_query[0]

    @property
    def news(self) -> str:
        """Google News に渡す唯一のクエリ。"""
        return self.news_query[0]

    @property
    def is_primary_language(self) -> bool:
        """`language` がその国の主要言語か(docs/scoring.md Localization quality)。"""
        return self.country.is_primary_language(self.language)
