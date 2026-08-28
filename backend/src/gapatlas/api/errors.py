"""API 層の例外と HTTP ステータスの対応。

正本は docs/api.md「エラー」。エラー本文は必ず
`{"error": {"code": "...", "message": "..."}}` の形にする。

**外部 API の失敗をここへ持ち込まない。** 1つのソースが失敗しても 5xx にせず、
国単位の `status` と Evidence Confidence で表現する
(docs/requirements.md「Reliability」)。
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from enum import StrEnum
from http import HTTPStatus
from typing import Any, ClassVar, Final

from gapatlas.domain.models.errors import GapAtlasError


class ApiErrorCode(StrEnum):
    """レスポンス本文の `error.code`。

    `INVALID_REQUEST` / `SCAN_NOT_FOUND` / `COUNTRY_NOT_FOUND` /
    `INTERNAL_ERROR` は docs/api.md のエラー表そのもの。`ROUTE_NOT_FOUND` と
    `METHOD_NOT_ALLOWED` はルータが返す必要があるが表に無いため、この2つは
    docs/api.md への追記が必要(完了報告に記載)。
    """

    INVALID_REQUEST = "INVALID_REQUEST"
    SCAN_NOT_FOUND = "SCAN_NOT_FOUND"
    COUNTRY_NOT_FOUND = "COUNTRY_NOT_FOUND"
    ROUTE_NOT_FOUND = "ROUTE_NOT_FOUND"
    METHOD_NOT_ALLOWED = "METHOD_NOT_ALLOWED"
    INTERNAL_ERROR = "INTERNAL_ERROR"


STATUS_BY_CODE: Final[Mapping[ApiErrorCode, HTTPStatus]] = {
    ApiErrorCode.INVALID_REQUEST: HTTPStatus.BAD_REQUEST,
    ApiErrorCode.SCAN_NOT_FOUND: HTTPStatus.NOT_FOUND,
    ApiErrorCode.COUNTRY_NOT_FOUND: HTTPStatus.NOT_FOUND,
    ApiErrorCode.ROUTE_NOT_FOUND: HTTPStatus.NOT_FOUND,
    ApiErrorCode.METHOD_NOT_ALLOWED: HTTPStatus.METHOD_NOT_ALLOWED,
    ApiErrorCode.INTERNAL_ERROR: HTTPStatus.INTERNAL_SERVER_ERROR,
}
"""docs/api.md のエラー表。コードを増やしたらここも増やす。"""

INTERNAL_ERROR_MESSAGE: Final[str] = "an unexpected error occurred"
"""500 の固定文言。

**例外の内容とトレースバックをレスポンスへ出さない。** 内部構造が漏れるため
(docs/requirements.md「Security」)。原因は構造化ログにのみ残す。
"""


class ApiError(GapAtlasError):
    """HTTP ステータスとエラーコードを持つ例外。

    `GapAtlasError` を継承しているため、既存の例外階層と同じ扱いができる。
    """

    code: ClassVar[ApiErrorCode] = ApiErrorCode.INTERNAL_ERROR

    @property
    def status_code(self) -> HTTPStatus:
        return STATUS_BY_CODE[self.code]

    @property
    def payload(self) -> dict[str, Any]:
        """docs/api.md のエラー本文。"""
        return {"error": {"code": self.code.value, "message": str(self)}}

    @property
    def headers(self) -> dict[str, str]:
        """このエラー固有の追加ヘッダ。既定では無い。"""
        return {}


class InvalidRequestError(ApiError):
    """topic_id / country / 本文が不正な場合(400)。"""

    code: ClassVar[ApiErrorCode] = ApiErrorCode.INVALID_REQUEST


class ScanNotFoundError(ApiError):
    """`scan_id` が存在しない場合(404)。

    **要求された `scan_id` を本文へ反射させない。** 利用者が送った任意文字列
    (`../` を含むパスなど)をそのまま返さないため。値は構造化ログにのみ残す。
    """

    code: ClassVar[ApiErrorCode] = ApiErrorCode.SCAN_NOT_FOUND

    def __init__(self) -> None:
        super().__init__("the requested scan does not exist")


class CountryNotFoundError(ApiError):
    """そのスキャンに該当国が無い場合(404)。"""

    code: ClassVar[ApiErrorCode] = ApiErrorCode.COUNTRY_NOT_FOUND

    def __init__(self, country: str) -> None:
        # `country` は `Country` へ変換済みの値だけを渡すこと。
        super().__init__(f"the scan has no result for country: {country}")


class RouteNotFoundError(ApiError):
    """未知のパス(404)。"""

    code: ClassVar[ApiErrorCode] = ApiErrorCode.ROUTE_NOT_FOUND

    def __init__(self) -> None:
        # 要求されたパスを本文へ反射させない。反射型の情報漏えいを避ける。
        super().__init__("the requested path does not exist")


class MethodNotAllowedError(ApiError):
    """既知のパスに対する未知のメソッド(405)。"""

    code: ClassVar[ApiErrorCode] = ApiErrorCode.METHOD_NOT_ALLOWED

    def __init__(self, allowed_methods: Sequence[str]) -> None:
        self.allowed_methods: tuple[str, ...] = tuple(allowed_methods)
        allowed = ", ".join(self.allowed_methods)
        super().__init__(f"method not allowed; allowed methods: {allowed}")

    @property
    def headers(self) -> dict[str, str]:
        """RFC 9110 が 405 に必須とする `Allow`。"""
        return {"Allow": ", ".join(self.allowed_methods)}


class InternalError(ApiError):
    """想定外の例外(500)。文言は固定で、原因を本文へ出さない。"""

    code: ClassVar[ApiErrorCode] = ApiErrorCode.INTERNAL_ERROR

    def __init__(self) -> None:
        super().__init__(INTERNAL_ERROR_MESSAGE)
