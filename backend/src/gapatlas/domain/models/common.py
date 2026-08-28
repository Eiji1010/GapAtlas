"""全モデルが共有する列挙型・定数・共通型。

この層は他のどの層にも依存しない。
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from enum import StrEnum
from typing import Annotated, Final

from pydantic import AfterValidator, ConfigDict

from gapatlas.domain.models.errors import InvalidTemporalValueError

MODEL_CONFIG: Final[ConfigDict] = ConfigDict(extra="forbid")
"""domain モデル共通の Pydantic 設定。未知のキーは契約違反として弾く。"""


class Country(StrEnum):
    """MVP 対象国。ISO 3166-1 alpha-2。"""

    JP = "JP"
    US = "US"
    GB = "GB"
    DE = "DE"
    IN = "IN"

    @property
    def label(self) -> str:
        """英語の国名ラベル。"""
        return COUNTRY_LABELS[self]

    @property
    def primary_languages(self) -> frozenset[str]:
        """その国の主要言語(ISO 639-1、小文字)。"""
        return PRIMARY_LANGUAGES[self]

    def is_primary_language(self, language: str) -> bool:
        """`language` がその国の主要言語か。大文字小文字と前後空白は無視する。"""
        return language.strip().lower() in self.primary_languages


class TopicId(StrEnum):
    """MVP のトピック。Elder Care のみ。"""

    ELDER_CARE = "elder_care"


class SourceName(StrEnum):
    """取得元データソース。"""

    TRENDS = "trends"
    RELATED_QUERIES = "related_queries"
    SEARCH = "search"
    NEWS = "news"
    MAPS = "maps"


class SourceStatus(StrEnum):
    """ソース単位の取得結果。"""

    OK = "ok"
    MISSING = "missing"
    NOT_REQUESTED = "not_requested"


class CountryStatus(StrEnum):
    """国単位の処理状態。"""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    FAILED = "failed"


class ScanStatus(StrEnum):
    """スキャン全体の状態。"""

    PROCESSING = "processing"
    COMPLETED = "completed"
    PARTIALLY_FAILED = "partially_failed"


CORE_SOURCES: Final[tuple[SourceName, ...]] = (
    SourceName.TRENDS,
    SourceName.RELATED_QUERIES,
    SourceName.SEARCH,
    SourceName.NEWS,
)
"""Evidence Confidence の Core Source。Maps は含まない(docs/scoring.md 6章)。"""

COUNTRY_LABELS: Final[Mapping[Country, str]] = {
    Country.JP: "Japan",
    Country.US: "United States",
    Country.GB: "United Kingdom",
    Country.DE: "Germany",
    Country.IN: "India",
}

PRIMARY_LANGUAGES: Final[Mapping[Country, frozenset[str]]] = {
    Country.JP: frozenset({"ja"}),
    Country.US: frozenset({"en"}),
    Country.GB: frozenset({"en"}),
    Country.DE: frozenset({"de"}),
    Country.IN: frozenset({"en", "hi"}),
}
"""Localization quality の判定に使う国別主要言語(docs/scoring.md 6章)。"""


def ensure_utc(value: datetime) -> datetime:
    """timezone-aware であることを確認し、UTC へ正規化する。

    naive datetime は例外にする。時刻の解釈を暗黙に決めないため。
    """
    if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
        message = "datetime must be timezone-aware (naive datetime is not allowed)"
        raise InvalidTemporalValueError(message)
    return value.astimezone(UTC)


UtcDatetime = Annotated[datetime, AfterValidator(ensure_utc)]
"""timezone-aware かつ UTC へ正規化された datetime。"""
