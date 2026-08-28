"""SerpApi の生レスポンスを正規化モデルへ変換する純粋関数群。

生の dict を domain へ流さないための境界(AGENTS.md / docs/architecture.md)。
I/O・現在時刻取得・乱数を持たない。

## 欠損への方針

- **任意キーの欠落・空配列・キー自体の不在で例外を投げない。** 空リスト / 空系列を返す。
  「取得できたが中身が空」の判定は application 層と docs/scoring.md の Hard Rule が行う
- コンテナの**型**が想定外(例: `organic_results` がリストでなく文字列)なら
  `SerpApiResponseError`。壊れたレスポンスを黙って空として扱わないため
- 個々の要素が壊れていて必須項目(`title` / `link` など)を取り出せない場合は、
  **その要素だけスキップ**する(全体を落とさない)
"""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any, Final

from gapatlas.adapters.serpapi.errors import SerpApiResponseError
from gapatlas.domain.models.normalized import (
    MapsPlace,
    NewsArticle,
    RisingQuery,
    SearchResultItem,
    TrendPoint,
    TrendsSeries,
    TrendsTimeseries,
)

_LOGGER: Final[logging.Logger] = logging.getLogger(__name__)

BREAKOUT_GROWTH_PERCENT: Final[float] = 5000.0
"""`value` を数値化できない場合に使う成長率(%)。

`"Breakout"` / `"Record"` / 未知文字列がこれに該当する
(docs/serpapi-schema.md 2章)。

**docs/scoring.md の同名定数(5000.0)と一致させること。** domain/scoring 側にも
同じ定数が置かれるため、片方だけ変更すると Pain Signal の意味が崩れる。
"""

_GROWTH_TEXT_STRIP: Final[str] = "+,% \t "
"""`value` から取り除く文字。`"+4,500%"` → `"4500"`。"""

_ISO_UTC_SUFFIX: Final[str] = "Z"


# --------------------------------------------------------------------------------------
# 共通ヘルパ
# --------------------------------------------------------------------------------------


def _get_mapping(container: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    """入れ子オブジェクトを取り出す。欠落・null は空マッピング、型違いは例外。"""
    value = container.get(key)
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise SerpApiResponseError(
            f"serpapi response field '{key}' must be an object, got {type(value).__name__}"
        )
    return value


def _get_list(container: Mapping[str, Any], key: str) -> list[Any]:
    """配列を取り出す。欠落・null は空リスト、型違いは例外。"""
    value = container.get(key)
    if value is None:
        return []
    if not isinstance(value, list):
        raise SerpApiResponseError(
            f"serpapi response field '{key}' must be an array, got {type(value).__name__}"
        )
    return value


def _mappings(items: Sequence[Any]) -> list[Mapping[str, Any]]:
    """配列要素のうちオブジェクトのものだけを残す(壊れた要素はスキップ)。"""
    return [item for item in items if isinstance(item, Mapping)]


def _optional_str(container: Mapping[str, Any], key: str) -> str | None:
    """文字列フィールド。欠落・型違いは None。空白のみも None。"""
    value = container.get(key)
    if not isinstance(value, str) or not value.strip():
        return None
    return value


def _optional_number(value: Any) -> float | None:
    """数値フィールド。bool は数値として扱わない(JSON の true/false 対策)。"""
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return float(value)
    return None


def _optional_position(value: Any) -> int | None:
    """1 以上の整数のみ受け付ける。それ以外は None(添字で代替させる)。"""
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value if value >= 1 else None


def _optional_review_count(value: Any) -> int | None:
    """レビュー件数。0 以上の整数に丸められる数値のみ受け付ける。"""
    number = _optional_number(value)
    if number is None or number < 0 or number != int(number):
        return None
    return int(number)


def _parse_unix_timestamp(value: Any) -> datetime | None:
    """Unix 秒(**文字列**または数値)を UTC aware datetime へ変換する。

    Trends の `timeline_data[].timestamp` は文字列(docs/serpapi-schema.md 1章)。
    """
    if isinstance(value, bool):
        return None
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            seconds = int(text)
        except ValueError:
            return None
    elif isinstance(value, int | float):
        seconds = int(value)
    else:
        return None

    try:
        return datetime.fromtimestamp(seconds, tz=UTC)
    except (OverflowError, OSError, ValueError):
        return None


def _parse_iso_datetime(value: Any) -> datetime | None:
    """ISO 8601 文字列を UTC aware datetime へ変換する。

    受け付けるのは **オフセットを持つ ISO 8601 のみ**(末尾 `Z` を含む)。

    Google News の `date`(`"01/02/2026, 10:30 PM, +0700 +07"`)はロケール依存の
    人間可読表記で、タイムゾーン略称の解釈が実行環境に依存する。**推測で日付を
    補わない**方針(docs/serpapi-schema.md 3章、backend/tests/fixtures/README.md)
    のため、この形式は解釈せず `published_at=None` とし、原文を `raw_date` に残す。
    """
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    if text.endswith(_ISO_UTC_SUFFIX):
        text = f"{text[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        # naive はタイムゾーンを推測しない。
        return None
    return parsed.astimezone(UTC)


# --------------------------------------------------------------------------------------
# Trends TIMESERIES
# --------------------------------------------------------------------------------------


def _resolve_series_index(
    value: Mapping[str, Any], query_indexes: Mapping[str, int], series_count: int
) -> int | None:
    """`values[]` の要素がどの系列に属するかを解決する。

    まず `query` の文字列一致、解決できなければ `query_index` を `queries` の
    添字として扱う。どちらでも解決できなければ None(その値は捨てる)。
    """
    query = _optional_str(value, "query")
    if query is not None and query in query_indexes:
        return query_indexes[query]

    index = value.get("query_index")
    if isinstance(index, bool) or not isinstance(index, int):
        return None
    if 0 <= index < series_count:
        return index
    return None


def normalize_trends_timeseries(raw: Mapping[str, Any], queries: Sequence[str]) -> TrendsTimeseries:
    """Trends TIMESERIES を正規化する。

    Args:
        raw: SerpApi の生レスポンス。
        queries: リクエストで指定したクエリ(`demand_queries` と同じ順序)。
            `values[].query_index` の解決と系列の並び順に使う。

    Returns:
        `queries` の順に並んだ系列。**レスポンスに現れないクエリの空系列は
        合成しない**(docs/scoring.md の Evidence Confidence が「系列長の最小値」を
        見るため、合成すると意味が変わる)。
    """
    ordered_queries = list(queries)
    query_indexes: dict[str, int] = {}
    for index, query in enumerate(ordered_queries):
        query_indexes.setdefault(query, index)

    collected: dict[int, list[TrendPoint]] = {}
    timeline = _get_list(_get_mapping(raw, "interest_over_time"), "timeline_data")

    for entry in _mappings(timeline):
        timestamp = _parse_unix_timestamp(entry.get("timestamp"))
        if timestamp is None:
            continue
        for value in _mappings(_get_list(entry, "values")):
            series_index = _resolve_series_index(value, query_indexes, len(ordered_queries))
            if series_index is None:
                continue
            extracted = _optional_number(value.get("extracted_value"))
            if extracted is None:
                continue
            collected.setdefault(series_index, []).append(
                TrendPoint(timestamp=timestamp, value=extracted)
            )

    return TrendsTimeseries(
        series=[
            TrendsSeries(query=ordered_queries[index], points=points)
            for index, points in sorted(collected.items())
        ]
    )


# --------------------------------------------------------------------------------------
# Trends RELATED_QUERIES
# --------------------------------------------------------------------------------------


def _parse_growth_text(raw_value: str | None) -> float | None:
    """`"+4,500%"` のようなパーセント文字列を数値化する。失敗したら None。"""
    if raw_value is None:
        return None
    text = raw_value.strip(_GROWTH_TEXT_STRIP).replace(",", "")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _resolve_growth(extracted: Any, raw_value: str | None) -> tuple[float, bool]:
    """成長率(%)と breakout フラグを求める(docs/scoring.md 3章の手順)。

    1. `extracted_value` が数値ならそれを使う
    2. `value` から `+` `,` `%` を除去して数値化を試みる
    3. どちらも失敗したら `BREAKOUT_GROWTH_PERCENT`(is_breakout=True)

    負値は 0 へ切り上げる(rising に負値は本来現れない)。
    """
    number = _optional_number(extracted)
    if number is not None:
        return max(number, 0.0), False

    parsed = _parse_growth_text(raw_value)
    if parsed is not None:
        return max(parsed, 0.0), False

    return BREAKOUT_GROWTH_PERCENT, True


def normalize_related_queries(raw: Mapping[str, Any]) -> list[RisingQuery]:
    """Trends RELATED_QUERIES の `rising` を正規化する。

    `related_queries` / `rising` のキーが無い場合も空リストを返す
    (`edge_cases/trends_related_queries_no_rising.json`)。
    `"Breakout"` / `"Record"` / `"Rekord"` / `extracted_value: null` /
    `extracted_value` キー欠落のいずれでも例外を投げない。
    """
    rising = _get_list(_get_mapping(raw, "related_queries"), "rising")

    results: list[RisingQuery] = []
    for item in _mappings(rising):
        query = _optional_str(item, "query")
        if query is None:
            continue
        raw_value = _optional_str(item, "value")
        growth_percent, is_breakout = _resolve_growth(item.get("extracted_value"), raw_value)
        results.append(
            RisingQuery(
                query=query,
                growth_percent=growth_percent,
                is_breakout=is_breakout,
                raw_value=raw_value,
                link=_optional_str(item, "link"),
            )
        )
    return results


# --------------------------------------------------------------------------------------
# Google Search
# --------------------------------------------------------------------------------------


def normalize_search_results(raw: Mapping[str, Any]) -> list[SearchResultItem]:
    """Google Search の `organic_results` を正規化する。

    `position` が無い要素は**配列内の1始まりの添字**で代替する
    (`edge_cases/search_missing_position.json`)。
    """
    results: list[SearchResultItem] = []
    for index, item in enumerate(_get_list(raw, "organic_results"), start=1):
        if not isinstance(item, Mapping):
            continue
        title = _optional_str(item, "title")
        link = _optional_str(item, "link")
        if title is None or link is None:
            continue
        position = _optional_position(item.get("position"))
        results.append(
            SearchResultItem(
                position=index if position is None else position,
                title=title,
                link=link,
                snippet=_optional_str(item, "snippet"),
                displayed_link=_optional_str(item, "displayed_link"),
                source=_optional_str(item, "source"),
            )
        )
    return results


# --------------------------------------------------------------------------------------
# Google News
# --------------------------------------------------------------------------------------


def _flatten_news_entries(items: Sequence[Any]) -> list[Mapping[str, Any]]:
    """`stories` によるグループ化を平坦化する。

    `stories` ネストが `engine=google_news` で発生するかは未確認
    (docs/serpapi-schema.md 7章)。fixture には存在しないが、**存在しても落ちない**
    よう防御的に扱う。
    """
    flattened: list[Mapping[str, Any]] = []
    for item in _mappings(items):
        stories = _mappings(_get_list(item, "stories"))
        if stories:
            # 実構造が推定と違えば、ここで記事が無言で落ちる。live 移行時に
            # 最初に確認する項目なので警告を残す(docs/serpapi-schema.md 7章)。
            _LOGGER.warning(
                "google news response contains a 'stories' group (%d entries); "
                "the nested structure is unverified",
                len(stories),
            )
            flattened.extend(stories)
        else:
            flattened.append(item)
    return flattened


def _news_source_name(item: Mapping[str, Any]) -> str | None:
    """`source.name` を取り出す。`source` が文字列の場合はそれ自体を使う。"""
    source = item.get("source")
    if isinstance(source, Mapping):
        return _optional_str(source, "name")
    if isinstance(source, str) and source.strip():
        return source
    return None


def normalize_news_results(raw: Mapping[str, Any]) -> list[NewsArticle]:
    """Google News の `news_results` を正規化する。

    `snippet` は存在しない(docs/serpapi-schema.md 4章)。`published_at` は
    `iso_date` から求め、解釈できなければ None(推測で日付を補わない)。原文は
    `raw_date` に保持する。
    """
    entries = _flatten_news_entries(_get_list(raw, "news_results"))

    articles: list[NewsArticle] = []
    for index, item in enumerate(entries, start=1):
        title = _optional_str(item, "title")
        link = _optional_str(item, "link")
        if title is None or link is None:
            continue
        position = _optional_position(item.get("position"))
        published_at = _parse_iso_datetime(item.get("iso_date"))
        if published_at is None:
            published_at = _parse_iso_datetime(item.get("date"))
        articles.append(
            NewsArticle(
                position=index if position is None else position,
                title=title,
                link=link,
                source_name=_news_source_name(item),
                published_at=published_at,
                raw_date=_optional_str(item, "date"),
            )
        )
    return articles


# --------------------------------------------------------------------------------------
# Google Maps
# --------------------------------------------------------------------------------------


def normalize_maps_results(raw: Mapping[str, Any]) -> list[MapsPlace]:
    """Google Maps の `local_results` を正規化する。

    Maps は Core Score に使わず、Top 2 countries の Local Evidence 表示のみ
    (docs/requirements.md)。**件数を実際の供給量として扱ってはいけない。**
    """
    places: list[MapsPlace] = []
    for index, item in enumerate(_get_list(raw, "local_results"), start=1):
        if not isinstance(item, Mapping):
            continue
        title = _optional_str(item, "title")
        if title is None:
            continue
        position = _optional_position(item.get("position"))
        places.append(
            MapsPlace(
                position=index if position is None else position,
                title=title,
                place_id=_optional_str(item, "place_id"),
                rating=_optional_number(item.get("rating")),
                reviews=_optional_review_count(item.get("reviews")),
                place_type=_optional_str(item, "type"),
                address=_optional_str(item, "address"),
                link=_optional_str(item, "link"),
            )
        )
    return places
