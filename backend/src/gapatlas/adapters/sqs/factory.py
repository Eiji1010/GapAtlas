"""`Settings` から `JobQueue` を組み立てるファクトリ。

`PERSISTENCE_MODE` の分岐をここへ閉じ込め、application 層は `JobQueue`
(Protocol)だけを見る(docs/architecture.md「依存の向き」)。

**既定は `memory`。** `SQS_QUEUE_URL` の有無から AWS 利用を推測してはいけない
(`adapters/dynamodb/factory.py` と同じ方針)。キュー URL が設定済みでも、
モードが `memory` ならインメモリ実装を返して外部通信ゼロを保つ。
"""

from __future__ import annotations

from typing import assert_never

from gapatlas.adapters.sqs.client import SqsJobQueue
from gapatlas.adapters.sqs.memory import InMemoryJobQueue
from gapatlas.adapters.sqs.protocol import JobQueue
from gapatlas.config.settings import PersistenceMode, Settings


def create_job_queue(settings: Settings) -> JobQueue:
    """`settings.persistence_mode` に応じたジョブキューを返す。

    モードを増やして `case` を書き忘れると、実行時ではなく **mypy が**
    気付く(`assert_never`)。
    """
    match settings.persistence_mode:
        case PersistenceMode.MEMORY:
            return InMemoryJobQueue()
        case PersistenceMode.AWS:
            return SqsJobQueue(settings)
        case unsupported:  # pragma: no cover - Enum を増やしたときに型検査で気付く
            assert_never(unsupported)
