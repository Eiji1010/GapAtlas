"""SerpApi アダプタの例外。

`GapAtlasError` を基底にすることで、呼び出し側は adapters 層由来の失敗を
`SerpApiError` として一括で捕捉できる。1ソースの失敗で全体を止めない方針
(docs/architecture.md「Reliability」)のため、application 層はここで定義した
例外を捕捉して該当ソースを `MISSING` として扱う。

**例外メッセージへ API キーを入れてはいけない**(docs/architecture.md
「Observability」/「Security」)。URL を載せる場合は `mask_api_key` を通す。
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any, Final

from gapatlas.domain.models.errors import GapAtlasError

_API_KEY_QUERY_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"(api_key=)[^&\s]*", flags=re.IGNORECASE
)
"""クエリ文字列中の `api_key=...` を捕捉する。"""

API_KEY_MASK: Final[str] = "***"


def mask_api_key(text: str) -> str:
    """文字列中の `api_key=...` の値をマスクする。

    URL をそのまま例外メッセージやログへ載せると API キーが漏れる。載せる必要が
    ある場合は必ずこの関数を通す。
    """
    return _API_KEY_QUERY_PATTERN.sub(rf"\1{API_KEY_MASK}", text)


class SerpApiError(GapAtlasError):
    """SerpApi アダプタの例外の基底。"""


class SerpApiRequestError(SerpApiError):
    """ネットワーク障害・タイムアウトなど、レスポンスを受け取れなかった場合。

    リトライ対象(docs/serpapi-schema.md 6章)。
    """


class SerpApiStatusError(SerpApiError):
    """HTTP ステータス由来の失敗。

    `status_code` を保持し、呼び出し側がリトライ可否を判断できるようにする。
    """

    def __init__(self, message: str, *, status_code: int) -> None:
        super().__init__(message)
        self.status_code = status_code


class SerpApiResponseError(SerpApiError):
    """レスポンス本文が不正な場合。

    `{"error": "..."}` 本文、JSON として解析できない本文、想定外の型が該当する。
    HTTP 200 で返ることがあるため、ステータスとは独立に判定する。
    """


class FixtureNotFoundError(SerpApiError):
    """fixture ファイルが存在しない場合。"""


def raise_for_error_payload(payload: Mapping[str, Any]) -> None:
    """SerpApi のエラー本文(`{"error": "..."}`)を検出して例外にする。

    SerpApi は HTTP 200 でも本文に `error` を返すことがある
    (docs/serpapi-schema.md 6章)。fixture / live の両方で同じ判定を使う。
    """
    if "error" not in payload:
        return
    detail = payload["error"]
    message = detail if isinstance(detail, str) else repr(detail)
    raise SerpApiResponseError(f"SerpApi returned an error payload: {mask_api_key(message)}")
