"""SerpApi の生レスポンスを正規化した後のモデル。

生の dict を domain へ持ち込まないための境界。adapters 側が SerpApi の
レスポンスをここで定義した型へ変換してから domain へ渡す。
正本は docs/serpapi-schema.md。
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from gapatlas.domain.models.common import (
    CORE_SOURCES,
    MODEL_CONFIG,
    SourceName,
    SourceStatus,
    UtcDatetime,
)


class TrendPoint(BaseModel):
    """Trends TIMESERIES の1データ点。"""

    model_config = MODEL_CONFIG

    timestamp: UtcDatetime
    """`timeline_data[].timestamp`(Unix 秒の文字列)を UTC aware へ変換したもの。"""

    value: float
    """`timeline_data[].values[].extracted_value`。"""


class TrendsSeries(BaseModel):
    """1クエリ分の Trends 週次系列。`points` は必ず古い順に並ぶ。"""

    model_config = MODEL_CONFIG

    query: str
    points: list[TrendPoint] = Field(default_factory=list)
    """古い順(timestamp 昇順)。順序が崩れた入力は安定ソートで並べ替える。"""

    @field_validator("points")
    @classmethod
    def _sort_points_oldest_first(cls, points: list[TrendPoint]) -> list[TrendPoint]:
        """古い順であることを保証する。

        docs/scoring.md の Demand Momentum は「系列を古い順に並べ、末尾12点」を
        前提にしている。入力の順序に依存して誤ったスコアを出さないよう、
        ここで昇順へ正規化する(弾かずにソートする方針)。同一 timestamp の
        相対順序は安定ソートにより保たれる。
        """
        return sorted(points, key=lambda point: point.timestamp)

    @property
    def latest_timestamp(self) -> datetime | None:
        """最新データ点の timestamp。points が空なら None。"""
        if not self.points:
            return None
        return self.points[-1].timestamp


class TrendsTimeseries(BaseModel):
    """Trends TIMESERIES 全体。複数クエリ比較に対応する。"""

    model_config = MODEL_CONFIG

    series: list[TrendsSeries] = Field(default_factory=list)


class RisingQuery(BaseModel):
    """Trends RELATED_QUERIES の rising 要素。"""

    model_config = MODEL_CONFIG

    query: str
    growth_percent: float = Field(ge=0.0)
    """成長率(%)。"Breakout" / "Record" / 未知文字列は 5000.0 に正規化済み。"""

    is_breakout: bool = False
    """`value` を数値化できず上限値で代替した場合 True。"""

    raw_value: str | None = None
    """SerpApi の `value` 原文(監査用)。"""

    link: str | None = None


class SearchResultItem(BaseModel):
    """Google Search の organic_results 要素。"""

    model_config = MODEL_CONFIG

    position: int = Field(ge=1)
    """SerpApi の1始まりの順位。欠落時は配列添字で補完してから渡す。"""

    title: str
    link: str
    snippet: str | None = None
    displayed_link: str | None = None
    source: str | None = None


class NewsArticle(BaseModel):
    """Google News の news_results 要素。snippet は存在しない。"""

    model_config = MODEL_CONFIG

    position: int = Field(ge=1)
    title: str
    link: str
    source_name: str | None = None
    """`source.name`。関連性分類の入力は title と source_name のみ。"""

    published_at: UtcDatetime | None = None
    """`iso_date` 由来。パースできなければ None(推測で日付を補わない)。"""

    raw_date: str | None = None
    """`date` の原文(監査用)。"""


class MapsPlace(BaseModel):
    """Google Maps の local_results 要素。Core Score には使わない。"""

    model_config = MODEL_CONFIG

    position: int = Field(ge=1)
    title: str
    place_id: str | None = None
    rating: float | None = None
    reviews: int | None = Field(default=None, ge=0)
    place_type: str | None = None
    """SerpApi の `type`。Python の予約語的な名前を避けた命名。"""

    address: str | None = None
    link: str | None = None


class SourceFetch(BaseModel):
    """1ソースの取得結果メタデータ。Freshness / Data completeness の入力。"""

    model_config = MODEL_CONFIG

    source: SourceName
    status: SourceStatus
    error: str | None = None
    fetched_at: UtcDatetime
    cache_age_seconds: float = Field(default=0.0, ge=0.0)
    """キャッシュ経過時間(秒)。新規取得なら 0。"""


class NormalizedEvidence(BaseModel):
    """1国分の正規化済み証拠データ。"""

    model_config = MODEL_CONFIG

    trends: TrendsTimeseries | None = None
    rising_queries: list[RisingQuery] = Field(default_factory=list)
    search_results: list[SearchResultItem] = Field(default_factory=list)
    news_articles: list[NewsArticle] = Field(default_factory=list)
    maps_places: list[MapsPlace] | None = None
    """None = 取得していない(Top2 以外)。空リストは「取得したが0件」を意味する。"""

    fetches: dict[SourceName, SourceFetch] = Field(default_factory=dict)

    def source_status(self, source: SourceName) -> SourceStatus:
        """ソースの取得状態。`fetches` に無ければ NOT_REQUESTED。"""
        fetch = self.fetches.get(source)
        if fetch is None:
            return SourceStatus.NOT_REQUESTED
        return fetch.status

    def missing_core_sources(self) -> list[SourceName]:
        """Core Source のうち OK でないもの。CORE_SOURCES の順序を保つ。"""
        return [
            source for source in CORE_SOURCES if self.source_status(source) is not SourceStatus.OK
        ]

    def ok_core_sources(self) -> list[SourceName]:
        """Core Source のうち OK のもの。CORE_SOURCES の順序を保つ。"""
        return [source for source in CORE_SOURCES if self.source_status(source) is SourceStatus.OK]
