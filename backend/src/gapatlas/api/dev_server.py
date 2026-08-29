"""ローカル開発用の HTTP サーバー。

**本番では使わない。** 本番の入口は API Gateway HTTP API + Lambda
(`api/lambda_handlers.py`)であり、このモジュールはそのハンドラを標準
ライブラリの `http.server` で包むだけの薄い殻である。

## なぜ必要か

API を Lambda ハンドラとして実装しているため、`frontend` を
`VITE_API_MODE=live` で動かす相手がローカルに存在しなかった。フロントと
バックエンドを繋いだ状態を手元で確認できないと、`docs/api.md` の契約が
実際に噛み合っているかを目で確かめられない。

## 本番と違う点(意図的)

- **1プロセス。** SQS の代わりにインメモリのキューを使い、**バックグラウンド
  スレッドが1件ずつ**ジョブを処理する。1メッセージ1国という単位は同じなので、
  2秒 Polling で進捗が進む様子も再現できる
- 認証・レート制限・並列度の制御をしない
- `http.server` はシングルスレッドのため、同時接続をさばかない

依存は追加しない(標準ライブラリのみ)。`SERPAPI_MODE=fixture` /
`LLM_MODE=stub` / `PERSISTENCE_MODE=memory` の既定で、外部通信ゼロで動く。
"""

from __future__ import annotations

import json
import logging
import queue
import threading
from collections.abc import Callable, Mapping
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Final
from urllib.parse import parse_qsl, urlsplit

from gapatlas.adapters.dynamodb.factory import create_scan_repository
from gapatlas.adapters.llm.factory import create_brief_writer, create_llm_classifier
from gapatlas.adapters.s3.factory import create_scan_archive
from gapatlas.adapters.serpapi.factory import create_serpapi_client
from gapatlas.api.errors import InvalidRequestError
from gapatlas.api.handlers import ApiService
from gapatlas.api.http import error_response
from gapatlas.api.lambda_handlers import api_handler
from gapatlas.application.country_scan import CountryScanner
from gapatlas.application.jobs import ScanJob
from gapatlas.application.logging_context import log_context
from gapatlas.application.worker import ScanWorker
from gapatlas.config.errors import ConfigError
from gapatlas.config.settings import Settings

_LOGGER: Final[logging.Logger] = logging.getLogger(__name__)

DEFAULT_PORT: Final[int] = 8000
DEFAULT_HOST: Final[str] = "127.0.0.1"
MAX_BODY_BYTES: Final[int] = 1 * 1024 * 1024
"""受け付ける本文の上限。開発用でも無制限には読まない。

超えたら**読まずに 400 を返す**。以前は切り詰めていたが、マルチバイト文字の
途中で切ると `decode` が例外を投げ、応答を返さないまま接続が切れていた。
"""

# `do_*` は `Handler` に個別に定義する。**未定義のメソッドを `http.server` の
# 既定へ落とさない。** 落とすと 501 + HTML になり、本番(API Gateway ->
# `_require_method`)の 405 + JSON と食い違う。

LOOPBACK_HOSTS: Final[frozenset[str]] = frozenset({"127.0.0.1", "localhost", "::1"})
"""警告なしで待ち受けてよいホスト。"""

WORKER_JOIN_TIMEOUT_SECONDS: Final[float] = 10.0
"""停止時にワーカーの処理を待つ上限。

デーモンスレッドを待たずにプロセスを終えると、`worker.handle()` の途中で
強制終了する。既定の `PERSISTENCE_MODE=memory` なら害は無いが、`aws` で
起動していた場合は中途半端な国別結果が DynamoDB / S3 に残りうる。
"""


MAX_DRAIN_BYTES: Final[int] = 8 * 1024 * 1024
"""上限超過の本文を読み捨てる上限。

**応答の前に読み捨てる必要がある。** 送信中のクライアントを待たずに応答して
接続を閉じると、クライアント側は 400 ではなく `Connection reset by peer` を
受け取り、原因が分からなくなる。読み捨て自体は無制限にしない。
"""

DRAIN_CHUNK_BYTES: Final[int] = 64 * 1024


class _TooLarge:
    """本文が上限を超えたことを表す番兵。`None`(本文なし)と区別する。"""


_TOO_LARGE: Final[_TooLarge] = _TooLarge()

_Shutdown = Callable[[], None]


class _DispatchingQueue:
    """投入されたジョブをワーカースレッドへ渡すキュー。

    `JobQueue` を満たす。SQS の代わりであり、**1件ずつ順に処理する**
    (本番の `batch_size = 1` と同じ単位)。
    """

    def __init__(self) -> None:
        self._pending: queue.Queue[ScanJob] = queue.Queue()
        self.enqueued: list[ScanJob] = []

    def enqueue(self, jobs: Any) -> None:
        for job in jobs:
            self.enqueued.append(job)
            self._pending.put(job)

    def take(self, timeout: float) -> ScanJob | None:
        try:
            return self._pending.get(timeout=timeout)
        except queue.Empty:
            return None


def _run_worker(worker: ScanWorker, jobs: _DispatchingQueue, stop: threading.Event) -> None:
    """ジョブを1件ずつ処理する。**例外でスレッドを止めない。**"""
    while not stop.is_set():
        job = jobs.take(timeout=0.2)
        if job is None:
            continue
        try:
            worker.handle(job)
        except Exception:
            # 本番では SQS が再配信するが、開発用サーバーは落とさず続ける。
            _LOGGER.exception("the dev worker failed to process a job")


def _to_event(handler: BaseHTTPRequestHandler, method: str, body: str | None) -> dict[str, Any]:
    """HTTP リクエストを API Gateway HTTP API v2.0 のイベントへ変換する。

    **本番と同じ形にする。** ここでずれると、ローカルで動いても Lambda で
    動かない(あるいはその逆)ことになる。
    """
    parts = urlsplit(handler.path)
    return {
        "version": "2.0",
        "rawPath": parts.path,
        "rawQueryString": parts.query,
        "queryStringParameters": dict(parse_qsl(parts.query)),
        "headers": {key.lower(): value for key, value in handler.headers.items()},
        "body": body,
        "isBase64Encoded": False,
        "requestContext": {"http": {"method": method, "path": parts.path}},
    }


def _make_request_handler(service: ApiService) -> type[BaseHTTPRequestHandler]:
    """`service` を使うリクエストハンドラを作る。

    `api_handler` へ `service` を明示的に渡す。モジュール属性を差し替えると
    同一プロセスの後続処理へ漏れるため(`lambda_handlers.api_handler` の
    `service` 引数の説明を参照)。
    """

    class Handler(BaseHTTPRequestHandler):
        server_version = "GapAtlasDev"

        def log_message(self, format: str, *args: Any) -> None:
            # 既定の標準エラー出力ではなく、構造化ログへ載せる。
            _LOGGER.info("dev request", extra={"detail": format % args})

        def _respond(self, method: str) -> None:
            body = self._read_body()
            if isinstance(body, _TooLarge):
                response = error_response(
                    InvalidRequestError(f"request body must be at most {MAX_BODY_BYTES} bytes")
                )
            else:
                event = _to_event(self, method, body)
                with log_context(source="dev_server"):
                    response = api_handler(event, None, service=service)

            payload = str(response.get("body") or "")
            encoded = payload.encode("utf-8")
            self.send_response(int(response.get("statusCode", 500)))
            headers = response.get("headers")
            if isinstance(headers, Mapping):
                for key, value in headers.items():
                    self.send_header(str(key), str(value))
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            # HEAD にはヘッダだけを返す(RFC 9110)。
            if method != "HEAD":
                self.wfile.write(encoded)

        def _drain(self, length: int) -> None:
            """読まない本文を捨てる。応答を届けるために最後まで受け取る。"""
            remaining = min(length, MAX_DRAIN_BYTES)
            while remaining > 0:
                chunk = self.rfile.read(min(DRAIN_CHUNK_BYTES, remaining))
                if not chunk:
                    return
                remaining -= len(chunk)

        def do_GET(self) -> None:
            self._respond("GET")

        def do_POST(self) -> None:
            self._respond("POST")

        def do_OPTIONS(self) -> None:
            self._respond("OPTIONS")

        def do_HEAD(self) -> None:
            self._respond("HEAD")

        def do_PUT(self) -> None:
            self._respond("PUT")

        def do_PATCH(self) -> None:
            self._respond("PATCH")

        def do_DELETE(self) -> None:
            self._respond("DELETE")

        def _read_body(self) -> str | _TooLarge | None:
            raw_length = self.headers.get("Content-Length")
            if raw_length is None:
                return None
            try:
                length = int(raw_length)
            except ValueError:
                return None
            if length <= 0:
                return None
            if length > MAX_BODY_BYTES:
                # **切り詰めない。** 途中で切ると壊れた JSON やマルチバイトの
                # 断片になり、原因の分からない失敗になる。
                self._drain(length)
                return _TOO_LARGE
            try:
                return self.rfile.read(length).decode("utf-8")
            except UnicodeDecodeError:
                # UTF-8 でない本文は API の契約外。500 ではなく 400 にする。
                return _TOO_LARGE

    return Handler


def create_server(
    settings: Settings, *, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT
) -> tuple[HTTPServer, _Shutdown]:
    """API とワーカーを組み立て、**待ち受け済み**のサーバーを返す。

    ワーカースレッドも起動する。停止は返り値の `_Shutdown` を呼ぶ。`port=0` を
    渡すと OS が空きポートを選ぶ(実際の値は `server.server_address[1]`)。

    `serve()` と分けているのは、**テストから実際に HTTP を往復させる**ため。
    起動処理を `serve_forever()` と同じ関数に閉じ込めると、テストは
    `HTTPServer` を差し替えるしかなくなる。

    Raises:
        ConfigError: 指定のホスト・ポートで待ち受けられない場合。生の `OSError`
            を素通しさせない(CLI の出力契約に合わせる)。
    """
    repository = create_scan_repository(settings)
    archive = create_scan_archive(settings)
    jobs = _DispatchingQueue()
    service = ApiService(repository, jobs, settings)

    # **待ち受けを先に確保する。** ワーカースレッドを先に起動すると、
    # ポート衝突で失敗したときにスレッドだけが残る。
    try:
        server = HTTPServer((host, port), _make_request_handler(service))
    except OSError as exc:
        message = f"cannot listen on {host}:{port}: {exc}"
        raise ConfigError(message) from exc

    worker = ScanWorker(
        CountryScanner(create_serpapi_client(settings), create_llm_classifier(settings)),
        repository,
        archive,
        create_brief_writer(settings),
        profiles_dir=settings.query_profiles_dir,
    )

    stop = threading.Event()
    thread = threading.Thread(
        target=lambda: _run_worker(worker, jobs, stop), name="gapatlas-dev-worker", daemon=True
    )
    thread.start()

    def shutdown() -> None:
        """ワーカーを止め、**処理中のジョブを待ってから**サーバーを閉じる。"""
        stop.set()
        thread.join(timeout=WORKER_JOIN_TIMEOUT_SECONDS)
        if thread.is_alive():
            _LOGGER.warning("the dev worker did not stop in time")
        server.server_close()

    return server, shutdown


def serve(settings: Settings, *, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> None:
    """開発用サーバーを起動する。Ctrl-C で止まる。

    API とワーカーを**1プロセス**で動かす。フロントエンドは
    `VITE_API_MODE=live` / `VITE_API_BASE_URL=http://localhost:8000/api/v1`
    で繋がる。
    """
    server, shutdown = create_server(settings, host=host, port=port)
    bound_port = server.server_address[1]
    if host not in LOOPBACK_HOSTS:
        # 認証もレート制限も無い API を LAN へ晒すことになる。
        _LOGGER.warning(
            "the dev server is listening on a non-loopback address; "
            "it has no authentication and no rate limiting",
            extra={"host": host},
        )
    # 0.0.0.0 はブラウザへ貼れないので、繋がる URL を出す。
    display_host = "127.0.0.1" if host in {"0.0.0.0", "::"} else host  # noqa: S104
    api_url = f"http://{display_host}:{bound_port}/api/v1"
    _LOGGER.info("dev server started", extra={"url": api_url})
    print(  # noqa: T201
        json.dumps(
            {
                "message": "GapAtlas dev server",
                "api": api_url,
                "serpapi_mode": settings.serpapi_mode.value,
                "llm_mode": settings.llm_mode.value,
                "persistence_mode": settings.persistence_mode.value,
                "frontend": f"VITE_API_MODE=live VITE_API_BASE_URL={api_url} npm run dev",
            },
            ensure_ascii=False,
            indent=2,
        ),
        # パイプやログファイルへ流しても起動直後に見えるようにする
        # (既定のブロックバッファでは、止めるまで何も出てこない)。
        flush=True,
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        shutdown()
