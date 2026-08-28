"""scoring テスト共通のビルダー。

テストを決定的にするため、`scan_time` は必ず明示的に渡す。基準日は
`backend/tests/fixtures/README.md` に合わせて `2026-08-28T00:00:00Z`。
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from datetime import UTC, datetime, timedelta

from gapatlas.domain.models.classification import (
    ClassifiedEvidence,
    ClassifiedNewsArticle,
    ClassifiedRisingQuery,
    ClassifiedSearchResult,
    NewsClassification,
    NewsRelevance,
    PainCategory,
    PainClassification,
    SolutionCategory,
    SolutionClassification,
)
from gapatlas.domain.models.common import (
    CORE_SOURCES,
    Country,
    SourceName,
    SourceStatus,
    TopicId,
)
from gapatlas.domain.models.normalized import (
    NewsArticle,
    NormalizedEvidence,
    RisingQuery,
    SearchResultItem,
    SourceFetch,
    TrendPoint,
    TrendsSeries,
    TrendsTimeseries,
)
from gapatlas.domain.models.query_profile import QueryProfile, ReviewStatus, SerpApiParams

SCAN_TIME = datetime(2026, 8, 28, tzinfo=UTC)
"""fixture の基準日(backend/tests/fixtures/README.md)。"""

WEEK = timedelta(weeks=1)


def make_series(
    values: Sequence[float], query: str = "q", latest: datetime = SCAN_TIME
) -> TrendsSeries:
    """週次系列を作る。最新点の timestamp が `latest` になる。"""
    points = [
        TrendPoint(timestamp=latest - WEEK * (len(values) - 1 - index), value=float(value))
        for index, value in enumerate(values)
    ]
    return TrendsSeries(query=query, points=points)


def make_trends(*value_lists: Sequence[float], latest: datetime = SCAN_TIME) -> TrendsTimeseries:
    """複数 demand query の Trends を作る。"""
    return TrendsTimeseries(
        series=[
            make_series(values, query=f"q{index}", latest=latest)
            for index, values in enumerate(value_lists)
        ]
    )


def make_rising(
    growth_percent: float,
    category: PainCategory,
    confidence: float = 1.0,
    query: str = "rising",
) -> ClassifiedRisingQuery:
    return ClassifiedRisingQuery(
        item=RisingQuery(query=query, growth_percent=growth_percent),
        classification=PainClassification(classification=category, confidence=confidence),
    )


def make_search(
    position: int,
    category: SolutionCategory,
    confidence: float = 1.0,
) -> ClassifiedSearchResult:
    return ClassifiedSearchResult(
        item=SearchResultItem(
            position=position,
            title=f"result {position}",
            link=f"https://example.com/{position}",
        ),
        classification=SolutionClassification(classification=category, confidence=confidence),
    )


def make_news(
    published_at: datetime | None,
    relevance: NewsRelevance = NewsRelevance.DIRECTLY_RELEVANT,
    confidence: float = 1.0,
    position: int = 1,
) -> ClassifiedNewsArticle:
    return ClassifiedNewsArticle(
        item=NewsArticle(
            position=position,
            title=f"article {position}",
            link=f"https://example.com/news/{position}",
            published_at=published_at,
        ),
        classification=NewsClassification(classification=relevance, confidence=confidence),
    )


def make_fetches(
    statuses: Mapping[SourceName, SourceStatus] | None = None,
    cache_age_seconds: Mapping[SourceName, float] | None = None,
    fetched_at: datetime = SCAN_TIME,
) -> dict[SourceName, SourceFetch]:
    """Core Source 4つ分の取得メタデータ。既定は全て OK・キャッシュ 0 秒。"""
    resolved = dict.fromkeys(CORE_SOURCES, SourceStatus.OK)
    if statuses is not None:
        resolved.update(statuses)
    ages = dict(cache_age_seconds or {})
    return {
        source: SourceFetch(
            source=source,
            status=status,
            fetched_at=fetched_at,
            cache_age_seconds=ages.get(source, 0.0),
        )
        for source, status in resolved.items()
    }


def make_evidence(
    *,
    trends: TrendsTimeseries | None = None,
    rising_queries: Iterable[RisingQuery] = (),
    search_results: Iterable[SearchResultItem] = (),
    news_articles: Iterable[NewsArticle] = (),
    statuses: Mapping[SourceName, SourceStatus] | None = None,
    cache_age_seconds: Mapping[SourceName, float] | None = None,
) -> NormalizedEvidence:
    return NormalizedEvidence(
        trends=trends,
        rising_queries=list(rising_queries),
        search_results=list(search_results),
        news_articles=list(news_articles),
        fetches=make_fetches(statuses, cache_age_seconds),
    )


def evidence_from_classified(
    classified: ClassifiedEvidence,
    trends: TrendsTimeseries | None,
    statuses: Mapping[SourceName, SourceStatus] | None = None,
    cache_age_seconds: Mapping[SourceName, float] | None = None,
) -> NormalizedEvidence:
    """分類済みデータと同じ中身を持つ `NormalizedEvidence` を作る。"""
    return make_evidence(
        trends=trends,
        rising_queries=[entry.item for entry in classified.rising_queries],
        search_results=[entry.item for entry in classified.search_results],
        news_articles=[entry.item for entry in classified.news_articles],
        statuses=statuses,
        cache_age_seconds=cache_age_seconds,
    )


def make_classified(
    rising_queries: Iterable[ClassifiedRisingQuery] = (),
    search_results: Iterable[ClassifiedSearchResult] = (),
    news_articles: Iterable[ClassifiedNewsArticle] = (),
) -> ClassifiedEvidence:
    return ClassifiedEvidence(
        rising_queries=list(rising_queries),
        search_results=list(search_results),
        news_articles=list(news_articles),
    )


def make_profile(
    country: Country = Country.JP,
    language: str = "ja",
    review_status: ReviewStatus = ReviewStatus.MANUAL_REVIEWED,
    demand_queries: Sequence[str] | None = None,
) -> QueryProfile:
    return QueryProfile(
        topic_id=TopicId.ELDER_CARE,
        country=country,
        language=language,
        version="elder-care-test-v1",
        review_status=review_status,
        serpapi=SerpApiParams(geo="JP", gl="jp", hl="ja", google_domain="google.co.jp"),
        demand_queries=list(demand_queries) if demand_queries else ["介護"],
        related_query_seed=["介護"],
        solution_query=["介護 サービス"],
        news_query=["介護"],
        maps_query=["介護施設"],
        maps_location="@35.6812,139.7671,12z",
    )
