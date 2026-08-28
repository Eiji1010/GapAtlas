"""SQS を受ける Lambda Worker のハンドラ。

```text
SQS ──(1メッセージ1国)──> Lambda Worker ──> CountryScanner ──> DynamoDB / S3
```

**このハンドラは HTTP ↔ ユースケースの変換と同じ役割**であり、スキャンの
中身は `application/worker.py` が持つ(AGENTS.md のディレクトリ役割)。

## 例外を投げる / 投げない

SQS は「例外を投げた = 処理失敗」とみなして再配信し、`maxReceiveCount = 3`
を超えたメッセージを DLQ へ送る(docs/architecture.md「非同期処理」)。

- **復元できないメッセージは捨てる**(例外を投げない)。`JobDecodeError` は
  リトライしても直らないため、3回再配信して DLQ へ送るのは待ち時間の無駄
- **`ScanWorker` が投げた例外はそのまま通す**。SerpApi / LLM / 永続化の失敗は
  `ScanWorker` の内側で吸収済みなので、ここまで届くのは実装バグ・権限設定の
  誤り・タイムアウトであり、再配信と DLQ による可視化に価値がある

`batchSize = 1` を前提にしている(`adapters/sqs/decode.py`)。増やす場合は
`ReportBatchItemFailures` と record ごとの失敗収集が必要。
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from functools import lru_cache
from typing import Any, Final

from gapatlas.adapters.dynamodb.factory import create_scan_repository
from gapatlas.adapters.llm.factory import create_brief_writer, create_llm_classifier
from gapatlas.adapters.s3.factory import create_scan_archive
from gapatlas.adapters.serpapi.factory import create_serpapi_client
from gapatlas.adapters.sqs.decode import decode_records
from gapatlas.adapters.sqs.errors import JobDecodeError
from gapatlas.application.country_scan import CountryScanner
from gapatlas.application.logging_context import configure_logging, log_context
from gapatlas.application.worker import ScanWorker
from gapatlas.config.settings import Settings, load_settings

_LOGGER: Final[logging.Logger] = logging.getLogger(__name__)


def build_worker(settings: Settings | None = None) -> ScanWorker:
    """依存を組み立てる。**テストはこの関数を monkeypatch する。**

    ログ設定はアプリケーションの入口でだけ行う(`configure_logging` の docstring)。
    """
    resolved = settings if settings is not None else load_settings()
    configure_logging(resolved.log_level.value)
    return ScanWorker(
        CountryScanner(create_serpapi_client(resolved), create_llm_classifier(resolved)),
        create_scan_repository(resolved),
        create_scan_archive(resolved),
        create_brief_writer(resolved),
    )


@lru_cache(maxsize=1)
def get_worker() -> ScanWorker:
    """Lambda の実行環境をまたいで使い回す。テストは `cache_clear()` で差し替える。"""
    return build_worker()


def worker_handler(event: Mapping[str, Any], context: Any) -> dict[str, Any]:
    """SQS イベントを処理する。

    Returns:
        `{"batchItemFailures": []}`。**部分バッチ応答の形は返すが、現在は
        常に空**(`batchSize = 1` で、失敗は例外として送出するため)。
    """
    del context

    try:
        records = decode_records(event)
    except JobDecodeError:
        # リトライしても直らない。DLQ を素通りさせて捨てる。
        _LOGGER.exception("dropping an undecodable SQS message")
        return {"batchItemFailures": []}

    worker = get_worker()
    for message_id, job in records:
        with log_context(scan_id=job.scan_id, topic=job.topic_id.value, country=job.country.value):
            _LOGGER.info("processing a scan job", extra={"message_id": message_id})
            worker.handle(job)
    return {"batchItemFailures": []}
