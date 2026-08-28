"""正規化モデルのテスト。"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from gapatlas.domain.models.common import SourceName, SourceStatus
from gapatlas.domain.models.normalized import (
    MapsPlace,
    NewsArticle,
    NormalizedEvidence,
    RisingQuery,
    SearchResultItem,
    SourceFetch,
    TrendPoint,
    TrendsSeries,
    TrendsTimeseries,
)

BASE_TIME = datetime(2026, 1, 1, tzinfo=UTC)


def _point(week: int, value: float) -> TrendPoint:
    return TrendPoint(timestamp=BASE_TIME + timedelta(weeks=week), value=value)


def _fetch(source: SourceName, status: SourceStatus) -> SourceFetch:
    return SourceFetch(source=source, status=status, fetched_at=BASE_TIME)


def test_trends_series_sorts_points_oldest_first():
    """順序が崩れた入力は昇順へ並べ替える(弾かずにソートする方針)。"""
    series = TrendsSeries(query="q", points=[_point(2, 30.0), _point(0, 10.0), _point(1, 20.0)])
    assert [point.value for point in series.points] == [10.0, 20.0, 30.0]
    assert series.points[0].timestamp < series.points[-1].timestamp


def test_trends_series_keeps_already_sorted_points():
    series = TrendsSeries(query="q", points=[_point(0, 1.0), _point(1, 2.0)])
    assert [point.value for point in series.points] == [1.0, 2.0]


def test_trends_series_latest_timestamp():
    series = TrendsSeries(query="q", points=[_point(1, 2.0), _point(0, 1.0)])
    assert series.latest_timestamp == BASE_TIME + timedelta(weeks=1)
    assert TrendsSeries(query="q").latest_timestamp is None


def test_trend_point_rejects_naive_timestamp():
    with pytest.raises(ValidationError):
        TrendPoint(timestamp=datetime.fromisoformat("2026-01-01T00:00:00"), value=1.0)


def test_rising_query_rejects_negative_growth():
    with pytest.raises(ValidationError):
        RisingQuery(query="q", growth_percent=-1.0)


def test_rising_query_breakout_fields():
    item = RisingQuery(
        query="q", growth_percent=5000.0, is_breakout=True, raw_value="Breakout", link=None
    )
    assert item.is_breakout is True
    assert item.raw_value == "Breakout"


@pytest.mark.parametrize("position", [0, -1])
def test_search_result_rejects_non_positive_position(position):
    with pytest.raises(ValidationError):
        SearchResultItem(position=position, title="t", link="https://example.com")


def test_search_result_minimal_payload():
    item = SearchResultItem.model_validate(
        {"position": 1, "title": "t", "link": "https://example.com"}
    )
    assert item.snippet is None
    assert item.displayed_link is None
    assert item.source is None


def test_news_article_allows_missing_published_at():
    article = NewsArticle(position=1, title="t", link="https://example.com", raw_date="bad date")
    assert article.published_at is None


def test_news_article_rejects_naive_published_at():
    with pytest.raises(ValidationError):
        NewsArticle(
            position=1,
            title="t",
            link="https://example.com",
            published_at=datetime.fromisoformat("2026-01-01T00:00:00"),
        )


def test_maps_place_uses_place_type_field():
    place = MapsPlace.model_validate(
        {"position": 1, "title": "t", "place_type": "Nursing home", "rating": 4.2, "reviews": 10}
    )
    assert place.place_type == "Nursing home"


def test_source_fetch_rejects_negative_cache_age():
    with pytest.raises(ValidationError):
        SourceFetch(
            source=SourceName.SEARCH,
            status=SourceStatus.OK,
            fetched_at=BASE_TIME,
            cache_age_seconds=-1.0,
        )


def test_source_status_defaults_to_not_requested():
    evidence = NormalizedEvidence()
    assert evidence.source_status(SourceName.TRENDS) is SourceStatus.NOT_REQUESTED
    assert evidence.source_status(SourceName.MAPS) is SourceStatus.NOT_REQUESTED


def test_missing_and_ok_core_sources():
    evidence = NormalizedEvidence(
        trends=TrendsTimeseries(series=[TrendsSeries(query="q", points=[_point(0, 1.0)])]),
        fetches={
            SourceName.TRENDS: _fetch(SourceName.TRENDS, SourceStatus.OK),
            SourceName.SEARCH: _fetch(SourceName.SEARCH, SourceStatus.OK),
            SourceName.NEWS: _fetch(SourceName.NEWS, SourceStatus.MISSING),
            SourceName.MAPS: _fetch(SourceName.MAPS, SourceStatus.OK),
        },
    )
    # related_queries は fetches に無いので NOT_REQUESTED → OK ではない
    assert evidence.missing_core_sources() == [SourceName.RELATED_QUERIES, SourceName.NEWS]
    assert evidence.ok_core_sources() == [SourceName.TRENDS, SourceName.SEARCH]
    # MAPS は Core Source ではないので、どちらの結果にも現れない
    assert SourceName.MAPS not in evidence.ok_core_sources()


def test_maps_places_none_means_not_requested():
    evidence = NormalizedEvidence()
    assert evidence.maps_places is None
    assert NormalizedEvidence(maps_places=[]).maps_places == []
