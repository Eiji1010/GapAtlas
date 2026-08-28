"""SerpApi へ渡すクエリパラメータの組み立て。

正本は docs/serpapi-schema.md。生成結果は
`backend/tests/fixtures/serpapi/**/search_parameters` と厳密に一致する
(単体テストで5か国 x 5ソースを突き合わせている)。

`api_key` はここでは付けない。live クライアントが最後に付与する。fixture モード
では不要であり、パラメータ組み立ての単体テストへ秘密情報を持ち込まないため。
"""

from __future__ import annotations

from typing import Final

from gapatlas.domain.models.common import SourceName
from gapatlas.domain.models.query_profile import QueryProfile

TRENDS_ENGINE: Final[str] = "google_trends"
SEARCH_ENGINE: Final[str] = "google"
NEWS_ENGINE: Final[str] = "google_news"
MAPS_ENGINE: Final[str] = "google_maps"

TIMESERIES_DATA_TYPE: Final[str] = "TIMESERIES"
RELATED_QUERIES_DATA_TYPE: Final[str] = "RELATED_QUERIES"

TRENDS_DATE_RANGE: Final[str] = "today 12-m"
"""週次データ点を得るための固定値(docs/serpapi-schema.md 1章)。

`today 12-m` 以外を指定すると点の粒度が変わり、docs/scoring.md の
Demand Momentum が前提とする「週次52点」が崩れる。
"""

SEARCH_DEVICE: Final[str] = "desktop"
"""Google Search の `device`。国ごとに変えず固定する(比較可能性のため)。"""

MAPS_SEARCH_TYPE: Final[str] = "search"
"""Google Maps の `type`。`place` ではなく検索を使う(docs/serpapi-schema.md 5章)。"""

DEMAND_QUERY_SEPARATOR: Final[str] = ","
"""Trends TIMESERIES の複数キーワード区切り(最大5語)。"""


def demand_query_string(profile: QueryProfile) -> str:
    """Trends TIMESERIES の `q`。`demand_queries` をカンマ区切りで連結する。"""
    return DEMAND_QUERY_SEPARATOR.join(profile.demand_queries)


def _trends_params(profile: QueryProfile) -> dict[str, str]:
    """Trends には `gl` / `google_domain` を入れない(Trends に存在しない)。"""
    return {
        "engine": TRENDS_ENGINE,
        "q": demand_query_string(profile),
        "hl": profile.serpapi.hl,
        "geo": profile.serpapi.geo,
        "date": TRENDS_DATE_RANGE,
        "data_type": TIMESERIES_DATA_TYPE,
    }


def _related_queries_params(profile: QueryProfile) -> dict[str, str]:
    """RELATED_QUERIES は1リクエスト1クエリのみ(docs/serpapi-schema.md 2章)。"""
    return {
        "engine": TRENDS_ENGINE,
        "q": profile.related_seed,
        "hl": profile.serpapi.hl,
        "geo": profile.serpapi.geo,
        "date": TRENDS_DATE_RANGE,
        "data_type": RELATED_QUERIES_DATA_TYPE,
    }


def _search_params(profile: QueryProfile) -> dict[str, str]:
    return {
        "engine": SEARCH_ENGINE,
        "q": profile.solution,
        "google_domain": profile.serpapi.google_domain,
        "hl": profile.serpapi.hl,
        "gl": profile.serpapi.gl,
        "device": SEARCH_DEVICE,
    }


def _news_params(profile: QueryProfile) -> dict[str, str]:
    """Google News には `google_domain` を入れない(パラメータ表に現れない)。"""
    return {
        "engine": NEWS_ENGINE,
        "q": profile.news,
        "hl": profile.serpapi.hl,
        "gl": profile.serpapi.gl,
    }


def _maps_params(profile: QueryProfile) -> dict[str, str]:
    return {
        "engine": MAPS_ENGINE,
        "q": profile.maps,
        "type": MAPS_SEARCH_TYPE,
        "ll": profile.maps_location,
        "google_domain": profile.serpapi.google_domain,
        "hl": profile.serpapi.hl,
        "gl": profile.serpapi.gl,
    }


def build_params(source: SourceName, profile: QueryProfile) -> dict[str, str]:
    """1ソース分のクエリパラメータを組み立てる。

    Args:
        source: 取得元データソース。
        profile: 国別クエリ定義。

    Returns:
        SerpApi へ渡すパラメータ。`api_key` は含まない。
    """
    match source:
        case SourceName.TRENDS:
            return _trends_params(profile)
        case SourceName.RELATED_QUERIES:
            return _related_queries_params(profile)
        case SourceName.SEARCH:
            return _search_params(profile)
        case SourceName.NEWS:
            return _news_params(profile)
        case SourceName.MAPS:
            return _maps_params(profile)
