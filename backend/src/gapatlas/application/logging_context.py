"""構造化ログのコンテキスト伝播。

`docs/architecture.md`「Observability」は **全ログに `scan_id` / `country` /
`topic` / `source` を含める**ことを要求する。しかし `scan_id` を知っているのは
application 層だけで、adapters 層は知りえない。アダプタの関数シグネチャへ
`scan_id` を足して回ると層の責務が壊れるため、`contextvars` で伝播させる。

`contextvars` を選んだ理由:

- アダプタ層のコードを一切変更せずに済む
- 値が意図せず他のスキャンへ漏れない(`LoggerAdapter` はロガーごとの
  ラップが必要で、外部ライブラリのロガーには効かない)
- `asyncio` のタスクは文脈を自動で引き継ぐ

**スレッドへは自動では伝わらない。** `ThreadPoolExecutor` のワーカーは親の
`Context` を継承しないため、Phase 8 で並列化する際は `submit_with_context`
を使って明示的に引き渡すこと。使わないと全ログの4フィールドが `null` になる。
- Lambda の1実行1リクエストという実行モデルと相性がよい

**API キーのマスクも同じハンドラで行う。** `adapters/serpapi/logging_guard.py`
はマスクの実装を持つが、ロガー単位のフィルタだけでは `httpx` / `httpcore` しか
覆えない。root ハンドラへ付けることで、どのライブラリのログも必ず通る
(docs/architecture.md「プロセスが出すログ全体に対する要件である」)。
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable, Iterator, Mapping
from concurrent.futures import Executor, Future
from contextlib import contextmanager
from contextvars import ContextVar, Token, copy_context
from types import MappingProxyType
from typing import Any, Final

from gapatlas.adapters.serpapi.errors import mask_api_key
from gapatlas.adapters.serpapi.logging_guard import ApiKeyMaskingFilter

CONTEXT_FIELDS: Final[tuple[str, ...]] = ("scan_id", "topic", "country", "source")
"""全ログへ含める文脈フィールド(docs/architecture.md「Observability」)。"""

_EMPTY_CONTEXT: Final[Mapping[str, str]] = MappingProxyType({})
"""不変の空文脈。`ContextVar` の既定値が可変だと共有される危険があるため。"""

_CONTEXT: ContextVar[Mapping[str, str]] = ContextVar("gapatlas_log_context", default=_EMPTY_CONTEXT)

_RESERVED_RECORD_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "args",
        "asctime",
        "created",
        "exc_info",
        "exc_text",
        "filename",
        "funcName",
        "levelname",
        "levelno",
        "lineno",
        "module",
        "msecs",
        "message",
        "msg",
        "name",
        "pathname",
        "process",
        "processName",
        "relativeCreated",
        "stack_info",
        "taskName",
        "thread",
        "threadName",
    }
)
"""`LogRecord` が元から持つ属性。JSON へ出す追加フィールドの判定に使う。"""


def current_context() -> Mapping[str, str]:
    """現在のログ文脈。テストと診断用。"""
    return _CONTEXT.get()


@contextmanager
def log_context(**fields: str | None) -> Iterator[None]:
    """ログ文脈を積む。`None` を渡したフィールドは無視する。

    入れ子にすると内側が外側を上書きする(国ごとの処理で `country` を足す、
    ソースごとの処理で `source` を足す、という使い方を想定)。
    """
    merged = dict(_CONTEXT.get())
    merged.update({key: value for key, value in fields.items() if value is not None})
    token: Token[Mapping[str, str]] = _CONTEXT.set(merged)
    try:
        yield
    finally:
        _CONTEXT.reset(token)


class ScanContextFilter(logging.Filter):
    """ログレコードへ現在の文脈フィールドを載せるフィルタ。

    値が無いフィールドは `None` を入れる。「取れていない」ことが後から
    分かるようにするため、キー自体は落とさない。
    """

    def filter(self, record: logging.LogRecord) -> bool:
        context = _CONTEXT.get()
        for field in CONTEXT_FIELDS:
            if not hasattr(record, field):
                setattr(record, field, context.get(field))
        return True


class JsonFormatter(logging.Formatter):
    """CloudWatch 向けの JSON 1行フォーマッタ(docs/architecture.md)。"""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for field in CONTEXT_FIELDS:
            payload[field] = getattr(record, field, None)
        for key, value in record.__dict__.items():
            if key not in _RESERVED_RECORD_FIELDS and key not in payload:
                # `extra=` 由来の値もマスクを通す。フィルタは `msg` と `args`
                # しか書き換えないため、ここを通さないと素通りする。
                payload[key] = mask_api_key(value) if isinstance(value, str) else value
        if record.exc_info is not None:
            # トレースバックの本文にも URL が現れうる。
            payload["exception"] = mask_api_key(self.formatException(record.exc_info))
        return json.dumps(payload, ensure_ascii=False, default=str)


def configure_logging(level: str = "INFO", *, stream: Any | None = None) -> None:
    """構造化ログを設定する。**アプリケーションの入口でだけ呼ぶこと。**

    既存のハンドラを置き換える。ライブラリとして import されただけの状態で
    ログ設定を触らないよう、`cli.py` や Lambda ハンドラからのみ呼ぶ。
    """
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonFormatter())
    handler.addFilter(ScanContextFilter())
    # プロセスが出す全ログが必ず通る唯一の場所。ここで API キーを落とす。
    handler.addFilter(ApiKeyMaskingFilter())

    root = logging.getLogger()
    for existing in list(root.handlers):
        root.removeHandler(existing)
    root.addHandler(handler)
    root.setLevel(level.upper())


def submit_with_context[T](
    executor: Executor, function: Callable[..., T], /, *args: Any, **kwargs: Any
) -> Future[T]:
    """現在のログ文脈を引き継いで `executor` へ投入する。

    `ThreadPoolExecutor` のワーカースレッドは親の `Context` を継承しない。
    素の `executor.submit` を使うと、ワーカーが出す全ログの `scan_id` /
    `topic` / `country` / `source` が `null` になる
    (docs/architecture.md「全ログに次を含める」に反する)。

    `asyncio` のタスクは文脈を自動で引き継ぐため、このヘルパは不要。
    """
    context = copy_context()
    return executor.submit(context.run, function, *args, **kwargs)
