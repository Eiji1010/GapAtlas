"""API レスポンス相当の結果モデル(公開表現)。

公開スコアは 0〜100 の **int**。内部 float は `scores.py` 側で保持する。
正本は docs/api.md と docs/scoring.md。
"""

from __future__ import annotations

from typing import Final, Self

from pydantic import BaseModel, Field, model_validator

from gapatlas.domain.models.classification import (
    ClassifiedNewsArticle,
    ClassifiedRisingQuery,
    ClassifiedSearchResult,
)
from gapatlas.domain.models.common import (
    MODEL_CONFIG,
    Country,
    CountryStatus,
    ScanStatus,
    SourceName,
    SourceStatus,
    TopicId,
    UtcDatetime,
)
from gapatlas.domain.models.errors import ModelConsistencyError
from gapatlas.domain.models.normalized import MapsPlace, TrendsTimeseries
from gapatlas.domain.models.scores import ConfidenceBreakdown, ScoreComponents

PUBLIC_SCORE_MIN: Final[int] = 0
PUBLIC_SCORE_MAX: Final[int] = 100

EVIDENCE_ID_PATTERN: Final[str] = r"^E[1-9][0-9]*$"
"""Evidence の識別子。"E1" 始まりの1始まり連番。"""

SCORELESS_STATUSES: Final[frozenset[CountryStatus]] = frozenset(
    {CountryStatus.INSUFFICIENT_EVIDENCE, CountryStatus.FAILED}
)
"""`need_gap_score` が None であることが許される status。"""


class Versions(BaseModel):
    """再現可能性のため結果に必ず含めるバージョン識別子。"""

    model_config = MODEL_CONFIG

    query_profile_version: str = Field(min_length=1)
    score_version: str = Field(min_length=1)
    classifier_version: str = Field(min_length=1)
    prompt_version: str = Field(min_length=1)


class Evidence(BaseModel):
    """UI へ提示する根拠1件。"""

    model_config = MODEL_CONFIG

    id: str = Field(pattern=EVIDENCE_ID_PATTERN)
    """"E1" 形式。"E0" や "X1" は不正。"""

    source: SourceName
    summary: str
    url: str | None = None
    """SerpApi のレスポンスに含まれていた URL のみ。LLM に生成させない。"""


class CountryResult(BaseModel):
    """国別の詳細結果(GET /api/v1/scans/{scan_id}/countries/{country} 相当)。"""

    model_config = MODEL_CONFIG

    scan_id: str = Field(min_length=1)
    topic_id: TopicId
    country: Country
    status: CountryStatus

    need_gap_score: int | None = Field(default=None, ge=PUBLIC_SCORE_MIN, le=PUBLIC_SCORE_MAX)
    """公開表現の 0〜100 整数。算出不能なら None。"""

    confidence: int = Field(ge=PUBLIC_SCORE_MIN, le=PUBLIC_SCORE_MAX)
    """INSUFFICIENT_EVIDENCE でも必ず返す。"""

    components: ScoreComponents
    confidence_breakdown: ConfidenceBreakdown
    source_status: dict[SourceName, SourceStatus] = Field(default_factory=dict)
    evidence: list[Evidence] = Field(default_factory=list)

    # --- Screen 2(Country Evidence)が表示する詳細 -----------------------------------
    #
    # docs/api.md の `GET /scans/{scan_id}/countries/{country}` が返す内容。
    # **分類結果ごと持つ**のは、UI が「この検索結果は DIRECT_PROVIDER と分類された」
    # を示すため(docs/requirements.md の Screen 2)。スコアの再計算には使わない
    # (数値計算は domain/scoring が済ませている)。

    trends: TrendsTimeseries | None = None
    """Trends の週次系列。取得できなかった場合は None。"""

    related_queries: list[ClassifiedRisingQuery] = Field(default_factory=list)
    search_results: list[ClassifiedSearchResult] = Field(default_factory=list)
    news_results: list[ClassifiedNewsArticle] = Field(default_factory=list)

    maps_results: list[MapsPlace] | None = None
    """**Top 2 countries のみ非 None。** None は「取得していない」を意味する。
    空リストは「取得したが0件」であり、意味が違う。"""

    versions: Versions
    computed_at: UtcDatetime

    @model_validator(mode="after")
    def _check_score_status_consistency(self) -> Self:
        """`need_gap_score` が None なら status は INSUFFICIENT_EVIDENCE か FAILED。

        docs/scoring.md 7章。スコアを出せなかったのに COMPLETED を返すと
        UI がランキングへ載せてしまうため、モデル境界で弾く。
        """
        if self.need_gap_score is None and self.status not in SCORELESS_STATUSES:
            allowed = ", ".join(sorted(status.value for status in SCORELESS_STATUSES))
            message = (
                f"need_gap_score is None but status is '{self.status.value}'; "
                f"status must be one of: {allowed}"
            )
            raise ModelConsistencyError(message)
        return self


class OpportunityBrief(BaseModel):
    """Top1 国について生成する説明文。Evidence に無い事実を断定しない。"""

    model_config = MODEL_CONFIG

    why_now: str
    what_people_are_struggling_with: str
    visible_solutions: str
    what_this_does_not_prove: str
    next_validation: str
    cited_evidence_ids: list[str] = Field(default_factory=list)
    """引用した Evidence の id。存在する id のみを指すこと。"""


class RankingEntry(BaseModel):
    """ランキング1行(公開表現)。"""

    model_config = MODEL_CONFIG

    country: Country
    status: CountryStatus
    need_gap_score: int | None = Field(default=None, ge=PUBLIC_SCORE_MIN, le=PUBLIC_SCORE_MAX)
    confidence: int = Field(ge=PUBLIC_SCORE_MIN, le=PUBLIC_SCORE_MAX)
    demand: int | None = Field(default=None, ge=PUBLIC_SCORE_MIN, le=PUBLIC_SCORE_MAX)
    pain: int | None = Field(default=None, ge=PUBLIC_SCORE_MIN, le=PUBLIC_SCORE_MAX)
    solution_gap: int | None = Field(default=None, ge=PUBLIC_SCORE_MIN, le=PUBLIC_SCORE_MAX)
    news_urgency: int | None = Field(default=None, ge=PUBLIC_SCORE_MIN, le=PUBLIC_SCORE_MAX)


class ScanProgress(BaseModel):
    """スキャンの進捗。"""

    model_config = MODEL_CONFIG

    total: int = Field(ge=0)
    completed: int = Field(ge=0)

    @model_validator(mode="after")
    def _check_completed_within_total(self) -> Self:
        if self.completed > self.total:
            message = f"completed ({self.completed}) must not exceed total ({self.total})"
            raise ModelConsistencyError(message)
        return self


class ScanMeta(BaseModel):
    """スキャンのメタデータ(永続化用)。"""

    model_config = MODEL_CONFIG

    scan_id: str = Field(min_length=1)
    topic_id: TopicId
    countries: list[Country] = Field(min_length=1)
    status: ScanStatus
    created_at: UtcDatetime
    updated_at: UtcDatetime


class ScanSummary(BaseModel):
    """スキャン概要(GET /api/v1/scans/{scan_id} 相当)。"""

    model_config = MODEL_CONFIG

    scan_id: str = Field(min_length=1)
    topic_id: TopicId
    status: ScanStatus
    progress: ScanProgress
    completed_countries: list[Country] = Field(default_factory=list)
    ranking: list[RankingEntry] = Field(default_factory=list)
    """`need_gap_score` の降順。None の国は末尾へ回す(並べ替えは application 層の責務)。"""

    opportunity_brief: OpportunityBrief | None = None
    versions: Versions
