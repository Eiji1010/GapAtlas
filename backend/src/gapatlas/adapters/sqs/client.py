"""SQS を使う `JobQueue`。

`POST /scans` は SCAN META を作ってから 5か国分の `ScanJob` を投入し、即座に
`scan_id` を返す(docs/architecture.md「非同期処理」)。**投入は 1回の
`send_message_batch` で行う。** 1件ずつ `send_message` を呼ぶと国数だけ
往復が増え、`POST /scans` の SLO(p95 < 800ms、docs/requirements.md
「Performance SLO」)を外部 API のレイテンシで押し上げる。

**部分的な失敗を握りつぶさない。** `send_message_batch` は成功と失敗を
`Successful` / `Failed` の2配列で返し、**HTTP 自体は 200 を返す**。`Failed` を
見ないと「投入できなかった国がある」事実が誰にも伝わらず、そのスキャンは
永久に `processing` のまま残る。1件でも失敗したら `JobEnqueueError` にする
(`protocol.py` の契約)。

**例外メッセージへメッセージ本文を載せない**(docs/architecture.md「Security」)。
載せるのは操作名・国コード・SQS のエラーコードだけにする。

`boto3` / `botocore` は optional extra(`aws`)のため**モジュールトップで
import しない**。未インストール環境で本モジュールの import 自体が失敗しない
ようにする(`adapters/dynamodb/client.py` と同じ作法)。
"""

from __future__ import annotations

from collections.abc import Sequence
from functools import lru_cache
from typing import Any, Final

from gapatlas.adapters.sqs.errors import JobEnqueueError, JobQueueError
from gapatlas.application.jobs import ScanJob
from gapatlas.config.settings import Settings

MAX_BATCH_SIZE: Final[int] = 10
"""`SendMessageBatch` の 1 リクエストあたりのエントリ上限(AWS の仕様)。

MVP は 5か国なので常に 1 バッチで収まるが、超えた場合に無言で切り捨てない
よう分割する。
"""


class SqsJobQueue:
    """SQS 上の `JobQueue`。"""

    def __init__(self, settings: Settings, *, client: Any | None = None) -> None:
        """
        Args:
            settings: `sqs_queue_url` と `aws_region` を読む。
            client: 使用する boto3 の SQS クライアント相当のオブジェクト。省略時は
                `boto3` から組み立てる。**テストは必ずフェイクを渡すこと**
                (単体テストで実 AWS を呼ばない。認証情報が無い前提)。

        Raises:
            JobQueueError: `SQS_QUEUE_URL` が未設定の場合、または `client` 未指定で
                `boto3` が未インストールの場合。
        """
        queue_url = settings.sqs_queue_url
        if queue_url is None:
            message = (
                "SQS_QUEUE_URL is not set; it is required to enqueue scan jobs. "
                "Set PERSISTENCE_MODE=memory to run without AWS."
            )
            raise JobQueueError(message)

        self._queue_url = queue_url
        self._client: Any = (
            client if client is not None else _build_default_client(region=settings.aws_region)
        )

    def enqueue(self, jobs: Sequence[ScanJob]) -> None:
        """ジョブをバッチで投入する。

        空の `jobs` は何もしない。`Entries` が空の `SendMessageBatch` は AWS が
        `EmptyBatchRequest` で拒否するため、呼び出し側に無意味な例外を見せない。

        Raises:
            JobEnqueueError: 送信に失敗した場合。**部分的に成功した場合も例外に
                する。** 先頭のバッチが失敗した時点で残りのバッチは送らない
                (投入済みの国は SQS 上に残る。Worker 側は 1メッセージ1国で
                独立しているため、途中まで進んだ状態は害にならない)。
        """
        for start in range(0, len(jobs), MAX_BATCH_SIZE):
            self._send_batch(jobs[start : start + MAX_BATCH_SIZE], offset=start)

    # --- 内部 -------------------------------------------------------------------------

    def _send_batch(self, jobs: Sequence[ScanJob], *, offset: int) -> None:
        if not jobs:
            return
        # `Id` はバッチ内で一意であればよい。全体での通し番号にしておくと、
        # 分割された 2 つ目以降のバッチでも失敗箇所を特定しやすい。
        ids = {str(offset + index): job.country.value for index, job in enumerate(jobs)}
        entries = [
            {"Id": str(offset + index), "MessageBody": job.model_dump_json()}
            for index, job in enumerate(jobs)
        ]
        try:
            response = self._client.send_message_batch(QueueUrl=self._queue_url, Entries=entries)
        except _aws_error_types() as exc:
            raise JobEnqueueError(self._failure_message(list(ids.values()), exc)) from exc

        failed: Sequence[Any] = response.get("Failed", [])
        if failed:
            raise JobEnqueueError(self._partial_failure_message(failed, ids))

    def _failure_message(self, countries: Sequence[str], exc: BaseException) -> str:
        """送信そのものが失敗したときの説明。**メッセージ本文は載せない。**"""
        return (
            f"failed to enqueue scan jobs for {', '.join(countries)} "
            f"to the SQS queue ({type(exc).__name__})"
        )

    def _partial_failure_message(self, failed: Sequence[Any], ids: dict[str, str]) -> str:
        """`Failed` 配列の説明。国コードと SQS のエラーコードだけを載せる。

        `Message`(SQS が返す自由文)は載せない。本文の一部が echo される可能性が
        あり、そこまで検証できないため。
        """
        details = ", ".join(
            f"{ids.get(str(entry.get('Id')), 'unknown')}={entry.get('Code', 'unknown')}"
            for entry in failed
        )
        return (
            f"{len(failed)} of {len(ids)} scan jobs could not be enqueued to the SQS queue "
            f"({details})"
        )


@lru_cache(maxsize=1)
def _aws_error_types() -> tuple[type[BaseException], ...]:
    """`JobEnqueueError` へ変換すべき botocore の例外型。

    `botocore` も optional extra(`aws`)に付いてくるため遅延 import する。
    未インストールで、かつ `client` が注入されている場合は変換対象が無いので
    空タプルを返す(`except ()` は何も捕捉しない)。

    **`Exception` を丸ごと捕捉しない。** `AttributeError` や `TypeError` などの
    実装バグまで「SQS の障害」に見えてしまい、原因が追えなくなる
    (`adapters/dynamodb/client.py` と同じ方針)。
    """
    try:
        from botocore.exceptions import BotoCoreError, ClientError  # noqa: PLC0415
    except ImportError:  # pragma: no cover - boto3 は aws extra として導入済み
        return ()
    return (BotoCoreError, ClientError)


def _build_default_client(*, region: str) -> Any:
    """`boto3` を遅延 import して SQS クライアントを作る。

    Raises:
        JobQueueError: `boto3` パッケージが未インストールの場合。
    """
    try:
        import boto3  # noqa: PLC0415
    except ImportError as exc:
        message = (
            "the 'boto3' package is not installed; "
            "install the 'aws' optional extra to use SqsJobQueue"
        )
        raise JobQueueError(message) from exc
    return boto3.client("sqs", region_name=region)
