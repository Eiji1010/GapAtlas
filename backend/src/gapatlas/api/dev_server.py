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
from collections.abc import Mapping
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Final
from urllib.parse import parse_qsl, urlsplit

from gapatlas.adapters.dynamodb.factory import create_scan_repository
from gapatlas.adapters.llm.factory import create_brief_writer, create_llm_classifier
from gapatlas.adapters.s3.factory import create_scan_archive
from gapatlas.adapters.serpapi.factory import create_serpapi_client
from gapatlas.api import lambda_handlers
from gapatlas.api.handlers import ApiService
from gapatlas.api.lambda_handlers import api_handler
from gapatlas.application.country_scan import CountryScanner
from gapatlas.application.jobs import ScanJob
from gapatlas.application.logging_context import log_context
from gapatlas.application.worker import ScanWorker
from gapatlas.config.settings import Settings

_LOGGER: Final[logging.Logger] = logging.getLogger(__name__)

DEFAULT_PORT: Final[int] = 8000
DEFAULT_HOST: Final[str] = "127.0.0.1"
MAX_BODY_BYTES: Final[int] = 1 * 1024 * 1024
"""受け付ける本文の上限。開発用でも無制限には読まない。"""


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


def _make_request_handler() -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        server_version = "GapAtlasDev"

        def log_message(self, format: str, *args: Any) -> None:
            # 既定の標準エラー出力ではなく、構造化ログへ載せる。
            _LOGGER.info("dev request", extra={"detail": format % args})

        def _respond(self, method: str) -> None:
            body = self._read_body()
            event = _to_event(self, method, body)
            with log_context(source="dev_server"):
                response = api_handler(event, None)

            payload = str(response.get("body") or "")
            encoded = payload.encode("utf-8")
            self.send_response(int(response.get("statusCode", 500)))
            headers = response.get("headers")
            if isinstance(headers, Mapping):
                for key, value in headers.items():
                    self.send_header(str(key), str(value))
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def _read_body(self) -> str | None:
            raw_length = self.headers.get("Content-Length")
            if raw_length is None:
                return None
            try:
                length = int(raw_length)
            except ValueError:
                return None
            if length <= 0:
                return None
            # 上限を超える本文は読み切らずに切り詰める(開発用でも無制限に
            # メモリを使わない)。
            return self.rfile.read(min(length, MAX_BODY_BYTES)).decode("utf-8")

        def do_GET(self) -> None:
            self._respond("GET")

        def do_POST(self) -> None:
            self._respond("POST")

        def do_OPTIONS(self) -> None:
            self._respond("OPTIONS")

    return Handler


def create_server(
    settings: Settings, *, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT
) -> tuple[HTTPServer, threading.Event]:
    """API とワーカーを組み立て、**待ち受け済み**のサーバーを返す。

    ワーカースレッドも起動する。停止は返り値の `Event` を set してから
    `server.server_close()` を呼ぶ。`port=0` を渡すと OS が空きポートを選ぶ
    (実際の値は `server.server_address[1]`)。

    `serve()` と分けているのは、**テストから実際に HTTP を往復させる**ため。
    起動処理を `serve_forever()` と同じ関数に閉じ込めると、テストは
    `HTTPServer` を差し替えるしかなくなる。
    """
    repository = create_scan_repository(settings)
    archive = create_scan_archive(settings)
    jobs = _DispatchingQueue()
    service = ApiService(repository, jobs, settings)

    # `api_handler` が使う依存を、ここで組み立てたものへ固定する。
    lambda_handlers.get_service.cache_clear()
    lambda_handlers.build_service = lambda _settings=None: service  # type: ignore[assignment]

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

    return HTTPServer((host, port), _make_request_handler()), stop


def serve(settings: Settings, *, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> None:
    """開発用サーバーを起動する。Ctrl-C で止まる。

    API とワーカーを**1プロセス**で動かす。フロントエンドは
    `VITE_API_MODE=live` / `VITE_API_BASE_URL=http://localhost:8000/api/v1`
    で繋がる。
    """
    server, stop = create_server(settings, host=host, port=port)
    bound_port = server.server_address[1]
    api_url = f"http://{host}:{bound_port}/api/v1"
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
        stop.set()
        server.server_close()
