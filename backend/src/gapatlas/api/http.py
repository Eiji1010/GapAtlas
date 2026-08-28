"""API Gateway HTTP API(payload format version 2.0)の入出力変換。

**この層は HTTP の形だけを扱う。** ユースケースは `handlers.py`、ルーティングは
`lambda_handlers.py` が持つ(AGENTS.md「api 層は HTTP ↔ ユースケースの変換のみ」)。

FastAPI / Flask は使わない。API Gateway HTTP API のイベントを直接受ける素の
Lambda ハンドラとして実装する(docs/architecture.md「API Gateway HTTP API →
Lambda API (Python)」)。
"""

from __future__ import annotations

import base64
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from http import HTTPStatus
from typing import Any, Final

from gapatlas.api.errors import ApiError, InvalidRequestError

JSON_CONTENT_TYPE: Final[str] = "application/json"

PREFLIGHT_METHOD: Final[str] = "OPTIONS"

CORS_ALLOWED_METHODS: Final[str] = "GET, POST, OPTIONS"
"""プリフライトへ返す許可メソッド。MVP の4エンドポイントは GET と POST のみ。"""

CORS_ALLOWED_HEADERS: Final[str] = "Content-Type"
"""MVP は認証しないため `Authorization` を許可しない(docs/api.md)。"""

CORS_MAX_AGE_SECONDS: Final[str] = "600"

ALLOW_ORIGIN_HEADER: Final[str] = "Access-Control-Allow-Origin"

WILDCARD_ORIGIN: Final[str] = "*"
"""決して返さない値(docs/requirements.md「CORS を Frontend origin へ限定」)。"""


@dataclass(frozen=True, slots=True)
class Request:
    """HTTP API イベントから取り出した最小限の要素。"""

    method: str
    """大文字に正規化済み。"""

    path: str
    path_parameters: Mapping[str, str]
    query: Mapping[str, str]

    headers: Mapping[str, str]
    """キーは小文字に正規化済み。HTTP ヘッダ名は大文字小文字を区別しない。"""

    body: str | None
    """base64 デコード済みの本文。本文が無ければ `None`。"""

    @property
    def origin(self) -> str | None:
        """`Origin` ヘッダ。CORS の判定にだけ使う。"""
        return self.headers.get("origin")

    @property
    def is_preflight(self) -> bool:
        return self.method == PREFLIGHT_METHOD


def _string_mapping(value: Any) -> dict[str, str]:
    """`None` を許すマッピングを `dict[str, str]` へ正規化する。

    API Gateway は `pathParameters` / `queryStringParameters` を、該当が無い
    ときに `null` で送る。
    """
    if not isinstance(value, Mapping):
        return {}
    return {str(key): str(item) for key, item in value.items() if item is not None}


def _header_mapping(value: Any) -> dict[str, str]:
    return {key.lower(): item for key, item in _string_mapping(value).items()}


def _decode_body(event: Mapping[str, Any]) -> str | None:
    """`body` を取り出す。`isBase64Encoded` なら復号する。

    Raises:
        InvalidRequestError: 本文が文字列でない、または base64 / UTF-8 として
            解釈できない場合。利用者の入力ミスなので 5xx にしない。
    """
    raw = event.get("body")
    if raw is None:
        return None
    if not isinstance(raw, str):
        message = "request body must be a string"
        raise InvalidRequestError(message)
    if not event.get("isBase64Encoded", False):
        return raw
    try:
        return base64.b64decode(raw, validate=True).decode("utf-8")
    except ValueError as exc:
        # binascii.Error と UnicodeDecodeError はどちらも ValueError の派生。
        message = "request body is not valid base64-encoded UTF-8"
        raise InvalidRequestError(message) from exc


def parse_request(event: Mapping[str, Any]) -> Request:
    """API Gateway HTTP API v2.0 のイベントを `Request` へ変換する。

    メソッドとパスは `requestContext.http` を正本とし、欠けていれば `rawPath`
    へ落とす。テストが最小のイベントを組み立てられるようにするため。

    Raises:
        InvalidRequestError: 本文を復号できない場合。
    """
    request_context = event.get("requestContext")
    http = request_context.get("http") if isinstance(request_context, Mapping) else None

    method = ""
    path = ""
    if isinstance(http, Mapping):
        method = str(http.get("method") or "")
        path = str(http.get("path") or "")
    if not path:
        path = str(event.get("rawPath") or "")

    return Request(
        method=method.upper(),
        path=path,
        path_parameters=_string_mapping(event.get("pathParameters")),
        query=_string_mapping(event.get("queryStringParameters")),
        headers=_header_mapping(event.get("headers")),
        body=_decode_body(event),
    )


def json_object_body(request: Request) -> Mapping[str, Any]:
    """本文を JSON オブジェクトとして読む。

    Raises:
        InvalidRequestError: 本文が無い、JSON として壊れている、または
            オブジェクトでない場合。
    """
    if request.body is None or not request.body.strip():
        message = "a JSON request body is required"
        raise InvalidRequestError(message)
    try:
        parsed = json.loads(request.body)
    except json.JSONDecodeError as exc:
        # 例外文言に本文の一部が載るため、そのままは使わない。
        message = "request body must be valid JSON"
        raise InvalidRequestError(message) from exc
    if not isinstance(parsed, dict):
        message = "request body must be a JSON object"
        raise InvalidRequestError(message)
    return parsed


def cors_headers(origin: str | None, allowed_origins: Sequence[str]) -> dict[str, str]:
    """CORS ヘッダを組み立てる。

    **許可された Origin のときだけ** `Access-Control-Allow-Origin` を返し、
    **ワイルドカードは決して返さない**(docs/requirements.md「CORS を Frontend
    origin へ限定」)。`CORS_ALLOWED_ORIGINS` に `*` が入っていても、実際の
    Origin 文字列と一致しないため反映されない。

    `Vary: Origin` は常に付ける。Origin ごとに応答が変わるため、これが無いと
    CDN やブラウザが別 Origin 向けの応答を再利用しうる。
    """
    headers = {"Vary": "Origin"}
    # `Origin: *` と `CORS_ALLOWED_ORIGINS=*` が同時に来ても `*` を返さない。
    if origin is not None and origin != WILDCARD_ORIGIN and origin in allowed_origins:
        headers[ALLOW_ORIGIN_HEADER] = origin
    return headers


def build_response(
    status_code: HTTPStatus | int,
    payload: Mapping[str, Any],
    *,
    extra_headers: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """JSON レスポンスを組み立てる(docs/api.md「レスポンスは JSON」)。"""
    headers = {"Content-Type": JSON_CONTENT_TYPE}
    if extra_headers is not None:
        headers.update(extra_headers)
    return {
        "statusCode": int(status_code),
        "headers": headers,
        "body": json.dumps(payload, ensure_ascii=False),
    }


def error_response(
    error: ApiError, *, extra_headers: Mapping[str, str] | None = None
) -> dict[str, Any]:
    """`{"error": {"code": ..., "message": ...}}` を返す。

    エラーでも CORS ヘッダを付ける。付けないとブラウザが本文を読めず、
    Frontend がエラーコードを表示できない。
    """
    headers = dict(error.headers)
    if extra_headers is not None:
        headers.update(extra_headers)
    return build_response(error.status_code, error.payload, extra_headers=headers)


def preflight_response(origin: str | None, allowed_origins: Sequence[str]) -> dict[str, Any]:
    """`OPTIONS` プリフライトへの応答。

    許可されていない Origin には CORS ヘッダを返さない。ステータス自体は 204 の
    ままにする。許可の有無をステータスで区別すると、許可 Origin の一覧を
    外部から総当たりで確認できてしまうため。
    """
    headers = cors_headers(origin, allowed_origins)
    if ALLOW_ORIGIN_HEADER in headers:
        headers["Access-Control-Allow-Methods"] = CORS_ALLOWED_METHODS
        headers["Access-Control-Allow-Headers"] = CORS_ALLOWED_HEADERS
        headers["Access-Control-Max-Age"] = CORS_MAX_AGE_SECONDS
    return {
        "statusCode": int(HTTPStatus.NO_CONTENT),
        "headers": headers,
        "body": "",
    }
