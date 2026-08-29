"""API Gateway HTTP API から呼ばれる Lambda ハンドラ。

```text
API Gateway HTTP API -> api_handler -> ApiService -> ScanRepository / JobQueue
```

ルーティング(メソッド + パス)と例外の HTTP 化だけを担当する。ユースケースは
`handlers.py`、HTTP の形は `http.py`(AGENTS.md「api 層は HTTP ↔ ユースケースの
変換のみ」)。

Worker 用のハンドラ(SQS イベントを受ける)はこのモジュールに無い。`ScanWorker`
が別トラックで作成中のため、完成後に別ファイルとして追加する。
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from functools import lru_cache
from http import HTTPStatus
from typing import Any, Final

from gapatlas.adapters.dynamodb.factory import create_scan_repository
from gapatlas.adapters.sqs.factory import create_job_queue
from gapatlas.adapters.sqs.protocol import JobQueue
from gapatlas.api.errors import (
    ApiError,
    InternalError,
    MethodNotAllowedError,
    RouteNotFoundError,
)
from gapatlas.api.handlers import ApiService
from gapatlas.api.http import (
    Request,
    build_response,
    cors_headers,
    error_response,
    json_object_body,
    parse_request,
    preflight_response,
)
from gapatlas.application.logging_context import configure_logging, log_context
from gapatlas.config.settings import Settings, load_settings

_LOGGER: Final[logging.Logger] = logging.getLogger(__name__)

API_PREFIX: Final[tuple[str, ...]] = ("api", "v1")
"""Base path(docs/api.md `/api/v1`)。"""

MAX_PREFIX_OFFSET: Final[int] = 1
"""`API_PREFIX` の前に許すセグメント数。

API Gateway のステージ名が付く場合(`/prod/api/v1/...`)に対応する。
`$default` ステージなら 0。
"""

SCAN_ID_LENGTH: Final[int] = 12
"""生成する `scan_id` の 16 進文字数。`cli.py` の `--scan-id` 既定と同じ。"""


def new_scan_id() -> str:
    """`scan_id` を生成する。`cli.py` と同じ形にする。"""
    return f"scan_{uuid.uuid4().hex[:SCAN_ID_LENGTH]}"


def build_job_queue(settings: Settings) -> JobQueue:
    """ジョブキューを組み立てる。

    `PERSISTENCE_MODE` で切り替わる。既定の `memory` では**プロセスをまたいで
    ジョブが届かない**(ローカル実行と単体テスト用)。Lambda では
    `PERSISTENCE_MODE=aws` と `SQS_QUEUE_URL` が必要。
    """
    return create_job_queue(settings)


def build_service(settings: Settings | None = None) -> ApiService:
    """依存を組み立てる。**テストはこの関数を monkeypatch する。**

    ログ設定はアプリケーションの入口でだけ行う(`logging_context.configure_logging`
    の約束)。Lambda ではこの関数が入口にあたる。

    Args:
        settings: 省略時は環境変数から読む。
    """
    resolved = load_settings() if settings is None else settings
    configure_logging(resolved.log_level.value)
    return ApiService(create_scan_repository(resolved), build_job_queue(resolved), resolved)


@lru_cache(maxsize=1)
def get_service() -> ApiService:
    """組み立て済みの `ApiService` を返す。

    Lambda の実行環境は再利用されるため、初回呼び出しの結果を使い回す。
    テストは `build_service` を差し替えてから `get_service.cache_clear()` を
    呼ぶ。
    """
    return build_service()


def _route_segments(path: str) -> tuple[str, ...] | None:
    """パスから `/api/v1` 以降のセグメントを取り出す。

    見つからなければ `None`(未知のパス)。末尾の `/` は無視する。
    """
    segments = tuple(segment for segment in path.split("/") if segment)
    for offset in range(MAX_PREFIX_OFFSET + 1):
        if segments[offset : offset + len(API_PREFIX)] == API_PREFIX:
            return segments[offset + len(API_PREFIX) :]
    return None


def _path_scan_id(segments: Sequence[str]) -> str | None:
    """ログ文脈へ載せる `scan_id` をパスから取り出す。"""
    match segments:
        case ["scans", scan_id, *_]:
            return scan_id
        case _:
            return None


def _is_create_scan(request: Request, segments: Sequence[str]) -> bool:
    return request.method == "POST" and tuple(segments) == ("scans",)


def _require_method(request: Request, allowed: Sequence[str]) -> None:
    """許可されていないメソッドを 405 にする。

    Raises:
        MethodNotAllowedError: メソッドが一致しない場合。
    """
    if request.method not in allowed:
        raise MethodNotAllowedError(allowed)


def _dispatch(
    service: ApiService,
    request: Request,
    segments: tuple[str, ...],
    *,
    scan_id: str | None,
    scan_time: datetime,
) -> tuple[HTTPStatus, dict[str, Any]]:
    """メソッド + パスでユースケースを選ぶ。

    Raises:
        ApiError: ルート未定義、メソッド不許可、または各ユースケースの検証失敗。
    """
    match segments:
        case ("topics",):
            _require_method(request, ("GET",))
            return HTTPStatus.OK, service.list_topics()
        case ("scans",):
            _require_method(request, ("POST",))
            return HTTPStatus.ACCEPTED, service.create_scan(
                json_object_body(request),
                # 通常は `api_handler` が生成済みの値を渡す。ここでの生成は
                # ルート判定を変えたときに ID 無しで落ちないための保険。
                scan_id=scan_id if scan_id is not None else new_scan_id(),
                scan_time=scan_time,
            )
        case ("scans", path_scan_id):
            _require_method(request, ("GET",))
            return HTTPStatus.OK, service.get_scan(path_scan_id)
        case ("scans", path_scan_id, "countries", country):
            _require_method(request, ("GET",))
            return HTTPStatus.OK, service.get_country(path_scan_id, country)
        case _:
            raise RouteNotFoundError()


def _rejected(
    error: ApiError, origin: str | None, allowed_origins: Sequence[str], request_id: str | None
) -> dict[str, Any]:
    """想定内のエラー(400 / 404 / 405)を返す。"""
    _LOGGER.warning(
        "request rejected",
        extra={
            "code": error.code.value,
            "status": int(error.status_code),
            "request_id": request_id,
        },
    )
    return error_response(error, extra_headers=cors_headers(origin, allowed_origins))


def _unhandled(
    origin: str | None, allowed_origins: Sequence[str], request_id: str | None
) -> dict[str, Any]:
    """想定外の例外を 500 + `INTERNAL_ERROR` にする。

    **例外の内容とトレースバックを本文へ出さない。** 原因はこのログにだけ残す
    (docs/requirements.md「Security」)。
    """
    _LOGGER.exception("unhandled error", extra={"request_id": request_id})
    return error_response(InternalError(), extra_headers=cors_headers(origin, allowed_origins))


def api_handler(
    event: Mapping[str, Any], context: Any, *, service: ApiService | None = None
) -> dict[str, Any]:
    """API Gateway HTTP API(payload format version 2.0)の入口。

    エラー応答も含めて**すべてのログを `scan_id` 付きで出す**ため、例外の捕捉を
    `log_context` の内側にも置く(docs/architecture.md「Observability」)。

    Args:
        event: API Gateway のイベント。
        context: Lambda のコンテキスト。`aws_request_id` をログの相関 ID に使う。
        service: 使う `ApiService`。**Lambda からは渡さない**(省略時は
            `get_service()` が組み立てる)。ローカル開発サーバー
            (`api/dev_server.py`)が自分で組み立てた依存を渡すための注入点で、
            これが無いと `build_service` をモジュールごと差し替えるしかなく、
            同一プロセスの後続処理(特にテスト)へ差し替えが漏れる。
    """
    request_id = getattr(context, "aws_request_id", None)
    allowed_origins: Sequence[str] = ()
    origin: str | None = None

    try:
        service = get_service() if service is None else service
        allowed_origins = service.settings.cors_allowed_origins
        request = parse_request(event)
        origin = request.origin

        if request.is_preflight:
            return preflight_response(origin, allowed_origins)

        segments = _route_segments(request.path)
        if segments is None:
            raise RouteNotFoundError()

        scan_id = _path_scan_id(segments)
        if scan_id is None and _is_create_scan(request, segments):
            scan_id = new_scan_id()

        with log_context(scan_id=scan_id):
            try:
                status, payload = _dispatch(
                    service, request, segments, scan_id=scan_id, scan_time=datetime.now(tz=UTC)
                )
            except ApiError as exc:
                return _rejected(exc, origin, allowed_origins, request_id)
            except Exception:
                return _unhandled(origin, allowed_origins, request_id)
            _LOGGER.info(
                "request handled",
                extra={
                    "method": request.method,
                    "path": request.path,
                    "status": int(status),
                    "request_id": request_id,
                },
            )
            return build_response(
                status, payload, extra_headers=cors_headers(origin, allowed_origins)
            )
    except ApiError as exc:
        # ルーティングへ入る前(依存の組み立て・イベント解釈)の失敗。
        return _rejected(exc, origin, allowed_origins, request_id)
    except Exception:
        return _unhandled(origin, allowed_origins, request_id)
