"""`build_params` のテスト。

最重要は「5か国 x 5ソースすべてで、生成したパラメータが fixture の
`search_parameters` と完全一致すること」。fixture は QueryProfile と厳密に
一致するよう作られている(backend/tests/fixtures/README.md「設計方針」2)ため、
これが一致していればリクエスト組み立ての正しさが担保される。
"""

from __future__ import annotations

import pytest
from conftest import ALL_COUNTRIES, ALL_SOURCES, country_fixture_path, read_json

from gapatlas.adapters.serpapi.params import (
    TRENDS_DATE_RANGE,
    build_params,
    demand_query_string,
)
from gapatlas.domain.models.common import Country, SourceName
from gapatlas.domain.models.query_profile import QueryProfile


@pytest.mark.parametrize("country", ALL_COUNTRIES, ids=lambda c: c.value)
@pytest.mark.parametrize("source", ALL_SOURCES, ids=lambda s: s.value)
def test_build_params_matches_fixture_search_parameters(
    profiles: dict[Country, QueryProfile], country: Country, source: SourceName
) -> None:
    profile = profiles[country]
    expected = read_json(country_fixture_path(country, source))["search_parameters"]

    assert build_params(source, profile) == expected


def test_api_key_is_never_included(profiles: dict[Country, QueryProfile]) -> None:
    """`api_key` は live クライアントが最後に足す。組み立て側では持たない。"""
    for profile in profiles.values():
        for source in ALL_SOURCES:
            assert "api_key" not in build_params(source, profile)


def test_trends_has_no_gl_or_google_domain(profiles: dict[Country, QueryProfile]) -> None:
    """Trends に `gl` / `google_domain` は存在しない(docs/serpapi-schema.md 5)。"""
    for profile in profiles.values():
        for source in (SourceName.TRENDS, SourceName.RELATED_QUERIES):
            params = build_params(source, profile)
            assert "gl" not in params
            assert "google_domain" not in params
            assert params["geo"] == profile.serpapi.geo


def test_news_has_no_google_domain(profiles: dict[Country, QueryProfile]) -> None:
    """Google News の `google_domain` はパラメータ表に現れない。"""
    for profile in profiles.values():
        assert "google_domain" not in build_params(SourceName.NEWS, profile)


def test_trends_date_range_is_fixed_to_12_months(
    profiles: dict[Country, QueryProfile],
) -> None:
    """週次データ点を得るため `today 12-m` に固定する。"""
    assert TRENDS_DATE_RANGE == "today 12-m"
    for profile in profiles.values():
        for source in (SourceName.TRENDS, SourceName.RELATED_QUERIES):
            assert build_params(source, profile)["date"] == TRENDS_DATE_RANGE


def test_timeseries_query_joins_all_demand_queries(
    profiles: dict[Country, QueryProfile],
) -> None:
    for profile in profiles.values():
        params = build_params(SourceName.TRENDS, profile)
        assert params["q"] == ",".join(profile.demand_queries)
        assert params["q"] == demand_query_string(profile)


def test_single_query_sources_use_their_own_query(
    profiles: dict[Country, QueryProfile],
) -> None:
    """RELATED_QUERIES / SEARCH / NEWS / MAPS はそれぞれ1クエリのみを使う。"""
    for profile in profiles.values():
        assert (
            build_params(SourceName.RELATED_QUERIES, profile)["q"] == profile.related_query_seed[0]
        )
        assert build_params(SourceName.SEARCH, profile)["q"] == profile.solution_query[0]
        assert build_params(SourceName.NEWS, profile)["q"] == profile.news_query[0]
        assert build_params(SourceName.MAPS, profile)["q"] == profile.maps_query[0]


def test_maps_uses_profile_location_verbatim(profiles: dict[Country, QueryProfile]) -> None:
    for profile in profiles.values():
        params = build_params(SourceName.MAPS, profile)
        assert params["ll"] == profile.maps_location
        assert params["type"] == "search"


def test_all_values_are_strings(profiles: dict[Country, QueryProfile]) -> None:
    """SerpApi はクエリ文字列で受け取るため、値はすべて文字列にする。"""
    for profile in profiles.values():
        for source in ALL_SOURCES:
            for key, value in build_params(source, profile).items():
                assert isinstance(key, str)
                assert isinstance(value, str)
