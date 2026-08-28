"""正規化の正常系テスト(5か国)。

件数は backend/tests/fixtures/README.md の表と一致させる。
rising 12件 / organic 10件 / news 8〜9件 / maps 6件 / trends 3系列 x 52点。
"""

from __future__ import annotations

from datetime import UTC, datetime
from itertools import pairwise

import pytest
from conftest import country_fixture_path, read_json

from gapatlas.adapters.serpapi.normalize import (
    normalize_maps_results,
    normalize_news_results,
    normalize_related_queries,
    normalize_search_results,
    normalize_trends_timeseries,
)
from gapatlas.domain.models.common import Country, SourceName
from gapatlas.domain.models.query_profile import QueryProfile

WEEK_SECONDS = 604800
EXPECTED_TRENDS_POINTS = 52
EXPECTED_RISING = 12
EXPECTED_ORGANIC = 10
EXPECTED_MAPS = 6
EXPECTED_NEWS: dict[Country, int] = {
    Country.JP: 9,
    Country.US: 8,
    Country.GB: 8,
    Country.DE: 8,
    Country.IN: 8,
}

ALL = tuple(Country)


def _raw(country: Country, source: SourceName) -> dict[str, object]:
    return read_json(country_fixture_path(country, source))


@pytest.mark.parametrize("country", ALL, ids=lambda c: c.value)
def test_trends_has_three_series_of_52_points(
    profiles: dict[Country, QueryProfile], country: Country
) -> None:
    profile = profiles[country]
    timeseries = normalize_trends_timeseries(
        _raw(country, SourceName.TRENDS), profile.demand_queries
    )

    assert [series.query for series in timeseries.series] == profile.demand_queries
    for series in timeseries.series:
        assert len(series.points) == EXPECTED_TRENDS_POINTS


@pytest.mark.parametrize("country", ALL, ids=lambda c: c.value)
def test_trends_timestamps_are_weekly_utc(
    profiles: dict[Country, QueryProfile], country: Country
) -> None:
    """`timestamp` 文字列が UTC datetime になり、隣接点の差が 604800 秒であること。"""
    timeseries = normalize_trends_timeseries(
        _raw(country, SourceName.TRENDS), profiles[country].demand_queries
    )

    for series in timeseries.series:
        timestamps = [point.timestamp for point in series.points]
        assert all(stamp.tzinfo is UTC for stamp in timestamps)
        deltas = {int((later - earlier).total_seconds()) for earlier, later in pairwise(timestamps)}
        assert deltas == {WEEK_SECONDS}


def test_trends_latest_point_is_the_reference_week(
    profiles: dict[Country, QueryProfile],
) -> None:
    """最新週は基準日 2026-08-28 を含む週(Aug 23 - Aug 29, 2026)。"""
    timeseries = normalize_trends_timeseries(
        _raw(Country.JP, SourceName.TRENDS), profiles[Country.JP].demand_queries
    )

    for series in timeseries.series:
        assert series.latest_timestamp == datetime(2026, 8, 23, tzinfo=UTC)


def test_trends_points_are_sorted_oldest_first_even_if_input_is_reversed(
    profiles: dict[Country, QueryProfile],
) -> None:
    raw = _raw(Country.US, SourceName.TRENDS)
    timeline = raw["interest_over_time"]["timeline_data"]  # type: ignore[index]
    queries = profiles[Country.US].demand_queries

    forward = normalize_trends_timeseries(raw, queries)
    reversed_raw = {
        "interest_over_time": {"timeline_data": list(reversed(timeline))},
    }
    backward = normalize_trends_timeseries(reversed_raw, queries)

    assert [p.timestamp for p in forward.series[0].points] == sorted(
        p.timestamp for p in forward.series[0].points
    )
    assert [(p.timestamp, p.value) for p in forward.series[0].points] == [
        (p.timestamp, p.value) for p in backward.series[0].points
    ]


def test_trends_series_order_follows_the_queries_argument(
    profiles: dict[Country, QueryProfile],
) -> None:
    """系列の順序は引数 `queries` の順に揃える。"""
    profile = profiles[Country.DE]
    swapped = list(reversed(profile.demand_queries))

    timeseries = normalize_trends_timeseries(_raw(Country.DE, SourceName.TRENDS), swapped)

    assert [series.query for series in timeseries.series] == swapped


@pytest.mark.parametrize("country", ALL, ids=lambda c: c.value)
def test_related_queries_has_twelve_rising(country: Country) -> None:
    rising = normalize_related_queries(_raw(country, SourceName.RELATED_QUERIES))

    assert len(rising) == EXPECTED_RISING
    assert all(item.growth_percent >= 0 for item in rising)
    assert all(item.raw_value is not None for item in rising)


@pytest.mark.parametrize("country", ALL, ids=lambda c: c.value)
def test_related_queries_contains_exactly_one_breakout_value(country: Country) -> None:
    """各国 1 件だけ `"Breakout"` を含む(fixture README)。

    `extracted_value: 5000` が付いているため `is_breakout` は False のまま
    (数値化に失敗した場合だけ True になる契約)。
    """
    rising = normalize_related_queries(_raw(country, SourceName.RELATED_QUERIES))

    breakout = [item for item in rising if item.raw_value == "Breakout"]
    assert len(breakout) == 1
    assert breakout[0].growth_percent == 5000.0
    assert breakout[0].is_breakout is False


@pytest.mark.parametrize("country", ALL, ids=lambda c: c.value)
def test_search_has_ten_results_with_ascending_positions(country: Country) -> None:
    results = normalize_search_results(_raw(country, SourceName.SEARCH))

    assert len(results) == EXPECTED_ORGANIC
    assert [item.position for item in results] == list(range(1, EXPECTED_ORGANIC + 1))
    assert all(item.title and item.link for item in results)


@pytest.mark.parametrize("country", ALL, ids=lambda c: c.value)
def test_search_keeps_minimal_items_without_optional_keys(country: Country) -> None:
    """各国 2 件は最小項目版(`position`/`title`/`link` のみ)で、欠落キーは None になる。"""
    results = normalize_search_results(_raw(country, SourceName.SEARCH))

    minimal = [
        item
        for item in results
        if item.snippet is None and item.displayed_link is None and item.source is None
    ]
    assert len(minimal) == 2
    assert all(item.title and item.link for item in minimal)


@pytest.mark.parametrize("country", ALL, ids=lambda c: c.value)
def test_news_counts_match_the_fixture_table(country: Country) -> None:
    articles = normalize_news_results(_raw(country, SourceName.NEWS))

    assert len(articles) == EXPECTED_NEWS[country]
    assert all(article.published_at is not None for article in articles)
    assert all(article.source_name for article in articles)
    assert all(article.raw_date for article in articles)


@pytest.mark.parametrize("country", ALL, ids=lambda c: c.value)
def test_news_published_at_is_utc_and_within_the_fixture_window(country: Country) -> None:
    """基準日から過去 0.4〜28.9 日に分散している(fixture README)。"""
    reference = datetime(2026, 8, 28, tzinfo=UTC)
    articles = normalize_news_results(_raw(country, SourceName.NEWS))

    for article in articles:
        assert article.published_at is not None
        assert article.published_at.tzinfo is UTC
        age_days = (reference - article.published_at).total_seconds() / 86400
        assert 0.0 <= age_days <= 29.0


@pytest.mark.parametrize("country", ALL, ids=lambda c: c.value)
def test_maps_has_six_places(country: Country) -> None:
    places = normalize_maps_results(_raw(country, SourceName.MAPS))

    assert len(places) == EXPECTED_MAPS
    assert [place.position for place in places] == list(range(1, EXPECTED_MAPS + 1))
    for place in places:
        assert place.title
        assert place.place_id is not None
        assert place.place_type is not None
        assert place.rating is not None
        assert place.reviews is not None
        assert place.reviews >= 0
