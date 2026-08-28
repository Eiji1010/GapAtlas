"""`edge_cases/` 15ファイルすべての正規化挙動テスト。

期待値は backend/tests/fixtures/README.md「境界値・異常系ファイル一覧」の
「何を検証するか」列に対応する。スコア側の分岐(`demand = None` など)は
domain/scoring の担当で、ここでは**正規化がどこまで情報を残すか**を検証する。
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from conftest import EDGE_CASES_DIR, read_edge_case

from gapatlas.adapters.serpapi.errors import SerpApiResponseError
from gapatlas.adapters.serpapi.fixture_client import load_fixture
from gapatlas.adapters.serpapi.normalize import (
    BREAKOUT_GROWTH_PERCENT,
    normalize_maps_results,
    normalize_news_results,
    normalize_related_queries,
    normalize_search_results,
    normalize_trends_timeseries,
)

EDGE_QUERIES = ["elder care", "nursing home", "home care for seniors"]
"""異常系 fixture は US の QueryProfile で統一されている(fixture README)。"""

REFERENCE_DATE = datetime(2026, 8, 28, tzinfo=UTC)


# ----------------------------------------------------------------------------------
# trends_timeseries_*.json
# ----------------------------------------------------------------------------------


def test_trends_11_points_normalizes_to_three_short_series() -> None:
    """WINDOW_WEEKS=12 未満。正規化は成功し、点数がそのまま残ること。"""
    timeseries = normalize_trends_timeseries(
        read_edge_case("trends_timeseries_11_points"), EDGE_QUERIES
    )

    assert [series.query for series in timeseries.series] == EDGE_QUERIES
    assert [len(series.points) for series in timeseries.series] == [11, 11, 11]


def test_trends_all_zero_keeps_every_point() -> None:
    """全ゼロでも点を捨てない(ゼロ除算回避はスコア側の責務)。"""
    timeseries = normalize_trends_timeseries(
        read_edge_case("trends_timeseries_all_zero"), EDGE_QUERIES
    )

    assert [len(series.points) for series in timeseries.series] == [52, 52, 52]
    for series in timeseries.series:
        assert {point.value for point in series.points} == {0.0}


def test_trends_half_zero_keeps_zero_points() -> None:
    """0 の点を落とすと Hard Rule 4(0 が 50% 以上)が判定できなくなる。"""
    timeseries = normalize_trends_timeseries(
        read_edge_case("trends_timeseries_half_zero"), EDGE_QUERIES
    )

    assert [len(series.points) for series in timeseries.series] == [52, 52, 52]
    for series in timeseries.series:
        zeros = sum(1 for point in series.points if point.value == 0.0)
        assert zeros == 32


def test_trends_empty_returns_no_series() -> None:
    """`timeline_data` が空。空系列を合成せず、系列そのものを作らない。"""
    timeseries = normalize_trends_timeseries(
        read_edge_case("trends_timeseries_empty"), EDGE_QUERIES
    )

    assert timeseries.series == []


def test_trends_missing_key_does_not_raise() -> None:
    """`interest_over_time` キー自体が無くても例外にしない。"""
    assert normalize_trends_timeseries({}, EDGE_QUERIES).series == []


def test_trends_wrong_container_type_raises() -> None:
    """想定外の型は黙って空にせず例外にする。"""
    with pytest.raises(SerpApiResponseError):
        normalize_trends_timeseries(
            {"interest_over_time": {"timeline_data": "not-a-list"}}, EDGE_QUERIES
        )


def test_trends_unresolvable_values_are_dropped() -> None:
    """`query` も `query_index` も解決できない値は捨てる。"""
    raw = {
        "interest_over_time": {
            "timeline_data": [
                {
                    "timestamp": "1787443200",
                    "values": [
                        {"query": "unknown query", "extracted_value": 5},
                        {"query_index": 99, "extracted_value": 6},
                        {"query": "elder care", "query_index": 0, "extracted_value": 7},
                        {"query_index": 1, "extracted_value": "not-a-number"},
                    ],
                }
            ]
        }
    }

    timeseries = normalize_trends_timeseries(raw, EDGE_QUERIES)

    assert [series.query for series in timeseries.series] == ["elder care"]
    assert [point.value for point in timeseries.series[0].points] == [7.0]


def test_trends_resolves_series_by_query_index_when_query_is_absent() -> None:
    raw = {
        "interest_over_time": {
            "timeline_data": [
                {"timestamp": "1787443200", "values": [{"query_index": 2, "extracted_value": 3}]}
            ]
        }
    }

    timeseries = normalize_trends_timeseries(raw, EDGE_QUERIES)

    assert [series.query for series in timeseries.series] == ["home care for seniors"]


# ----------------------------------------------------------------------------------
# trends_related_queries_*.json
# ----------------------------------------------------------------------------------


def test_related_queries_empty_rising_returns_empty_list() -> None:
    assert normalize_related_queries(read_edge_case("trends_related_queries_empty")) == []


def test_related_queries_without_rising_key_returns_empty_list() -> None:
    """`rising` キー欠落で KeyError を出さない。"""
    assert normalize_related_queries(read_edge_case("trends_related_queries_no_rising")) == []


def test_related_queries_breakout_never_raises_and_resolves_in_order() -> None:
    """`extracted_value` 優先 -> `value` パース -> 5000.0 フォールバックの順。"""
    rising = normalize_related_queries(read_edge_case("trends_related_queries_breakout"))

    resolved = {
        item.query: (item.growth_percent, item.is_breakout, item.raw_value) for item in rising
    }

    assert len(rising) == 8
    # 1. extracted_value が数値ならそれを使う("Breakout" / "Record" でも)
    assert resolved["no caregivers available"] == (5000.0, False, "Breakout")
    assert resolved["nursing home waitlist 2026"] == (4500.0, False, "+4,500%")
    assert resolved["care home closure notice"] == (12000.0, False, "Record")
    assert resolved["home health aide shortage"] == (1200.0, False, "+1,200%")
    assert resolved["elder care cost increase"] == (90.0, False, "+90%")
    # 2. extracted_value が無い / null なら value をパースする
    assert resolved["respite care waiting list"] == (950.0, False, "+950%")
    assert resolved["senior day care near me"] == (75.0, False, "+75%")
    # 3. どちらも失敗したら BREAKOUT_GROWTH_PERCENT
    assert resolved["assisted living availability"] == (
        BREAKOUT_GROWTH_PERCENT,
        True,
        "Rekord",
    )


def test_related_queries_growth_is_never_negative() -> None:
    rising = normalize_related_queries(
        {"related_queries": {"rising": [{"query": "q", "value": "-30%"}]}}
    )

    assert rising[0].growth_percent == 0.0


def test_related_queries_skips_items_without_a_query() -> None:
    rising = normalize_related_queries(
        {"related_queries": {"rising": [{"value": "+10%"}, {"query": "ok", "value": "+10%"}]}}
    )

    assert [item.query for item in rising] == ["ok"]


def test_related_queries_wrong_container_type_raises() -> None:
    with pytest.raises(SerpApiResponseError):
        normalize_related_queries({"related_queries": {"rising": "not-a-list"}})


# ----------------------------------------------------------------------------------
# search_*.json
# ----------------------------------------------------------------------------------


def test_search_empty_returns_empty_list() -> None:
    assert normalize_search_results(read_edge_case("search_empty")) == []


def test_search_minimal_fields_normalizes_all_ten() -> None:
    results = normalize_search_results(read_edge_case("search_minimal_fields"))

    assert len(results) == 10
    for item in results:
        assert item.snippet is None
        assert item.displayed_link is None
        assert item.source is None


def test_search_missing_position_falls_back_to_array_index() -> None:
    """配列添字 2 / 4 / 5(0始まり)に `position` が無い。1始まりの添字で補う。"""
    results = normalize_search_results(read_edge_case("search_missing_position"))

    assert [item.position for item in results] == [1, 2, 3, 4, 5, 6]


def test_search_wrong_container_type_raises() -> None:
    with pytest.raises(SerpApiResponseError):
        normalize_search_results({"organic_results": "not-a-list"})


def test_search_skips_items_missing_title_or_link() -> None:
    results = normalize_search_results(
        {
            "organic_results": [
                {"position": 1, "title": "ok", "link": "https://example.com/1"},
                {"position": 2, "title": "no link"},
                {"position": 3, "link": "https://example.com/3"},
            ]
        }
    )

    assert [item.title for item in results] == ["ok"]


# ----------------------------------------------------------------------------------
# news_*.json
# ----------------------------------------------------------------------------------


def test_news_empty_returns_empty_list() -> None:
    assert normalize_news_results(read_edge_case("news_empty")) == []


def test_news_without_iso_date_keeps_articles_with_no_published_at() -> None:
    """`iso_date` が無い場合、ロケール依存の `date` から日付を推測しない。

    原文は `raw_date` に残し、除外の判断(記事を数えるか)はスコア側に委ねる。
    """
    articles = normalize_news_results(read_edge_case("news_no_iso_date"))

    assert len(articles) == 4
    assert all(article.published_at is None for article in articles)
    assert all(article.raw_date is not None for article in articles)
    assert [article.position for article in articles] == [1, 2, 3, 4]


def test_news_future_dates_are_preserved_as_is() -> None:
    """未来日付も正規化できる。0 への丸めはスコアリング側の責務。"""
    articles = normalize_news_results(read_edge_case("news_future_date"))

    assert len(articles) == 5
    published = [article.published_at for article in articles]
    assert all(stamp is not None for stamp in published)
    future = [stamp for stamp in published if stamp is not None and stamp > REFERENCE_DATE]
    assert len(future) == 2
    assert published[0] == datetime(2026, 8, 29, 12, 0, tzinfo=UTC)


def test_news_source_name_is_flattened() -> None:
    articles = normalize_news_results(read_edge_case("news_future_date"))

    assert articles[0].source_name == "Example Health Wire (fictional)"


def test_news_wrong_container_type_raises() -> None:
    with pytest.raises(SerpApiResponseError):
        normalize_news_results({"news_results": "not-a-list"})


def test_news_stories_nesting_is_flattened() -> None:
    """`stories` ネストは fixture に存在しないが、存在しても落ちないこと。"""
    raw = {
        "news_results": [
            {
                "position": 1,
                "stories": [
                    {
                        "title": "grouped a",
                        "link": "https://news.example.com/a",
                        "iso_date": "2026-08-27T00:00:00Z",
                        "source": {"name": "Example (fictional)"},
                    },
                    {"title": "grouped b", "link": "https://news.example.com/b"},
                ],
            },
            {
                "position": 2,
                "title": "flat",
                "link": "https://news.example.com/c",
                "iso_date": "2026-08-26T00:00:00Z",
            },
        ]
    }

    articles = normalize_news_results(raw)

    assert [article.title for article in articles] == ["grouped a", "grouped b", "flat"]
    assert articles[0].published_at == datetime(2026, 8, 27, tzinfo=UTC)
    assert articles[1].published_at is None
    assert articles[1].position == 2


def test_news_skips_items_missing_title_or_link() -> None:
    articles = normalize_news_results(
        {"news_results": [{"title": "no link"}, {"title": "ok", "link": "https://e.example.com"}]}
    )

    assert [article.title for article in articles] == ["ok"]


# ----------------------------------------------------------------------------------
# maps(専用の edge case fixture は無いため合成データで防御を検証する)
# ----------------------------------------------------------------------------------


def test_maps_empty_and_missing_key_return_empty_list() -> None:
    assert normalize_maps_results({}) == []
    assert normalize_maps_results({"local_results": []}) == []


def test_maps_non_numeric_rating_and_reviews_become_none() -> None:
    places = normalize_maps_results(
        {
            "local_results": [
                {
                    "title": "Example Care (fictional)",
                    "rating": "4.5",
                    "reviews": "48",
                    "type": "Home care service",
                }
            ]
        }
    )

    assert places[0].rating is None
    assert places[0].reviews is None
    assert places[0].place_type == "Home care service"
    assert places[0].position == 1


def test_maps_missing_position_falls_back_to_array_index() -> None:
    places = normalize_maps_results(
        {"local_results": [{"title": "a"}, {"position": 9, "title": "b"}, {"title": "c"}]}
    )

    assert [place.position for place in places] == [1, 9, 3]


def test_maps_skips_items_without_a_title() -> None:
    places = normalize_maps_results({"local_results": [{"place_id": "x"}, {"title": "ok"}]})

    assert [place.title for place in places] == ["ok"]


def test_maps_wrong_container_type_raises() -> None:
    with pytest.raises(SerpApiResponseError):
        normalize_maps_results({"local_results": "not-a-list"})


# ----------------------------------------------------------------------------------
# error_*.json
# ----------------------------------------------------------------------------------


@pytest.mark.parametrize("name", ["error_401", "error_429"])
def test_error_fixtures_are_rejected_before_normalization(name: str) -> None:
    """`{"error": "..."}` 本文は正規化へ進ませない。"""
    with pytest.raises(SerpApiResponseError):
        load_fixture(EDGE_CASES_DIR / f"{name}.json")
