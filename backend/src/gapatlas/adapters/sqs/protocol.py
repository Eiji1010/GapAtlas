"""ジョブキューの Protocol。

application 層はこの Protocol だけを見る。SQS 実装とインメモリ実装を
差し替えられるようにする(docs/architecture.md「依存の向き」)。

`runtime_checkable` は付けない。
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from gapatlas.application.jobs import ScanJob


class JobQueue(Protocol):
    """スキャンジョブの投入。

    **受信は Lambda のイベントとして届く**ため、この Protocol には含めない
    (docs/architecture.md: SQS → Lambda Worker)。復元は
    `decode_job` が担当する。
    """

    def enqueue(self, jobs: Sequence[ScanJob]) -> None:
        """ジョブを投入する。

        Raises:
            JobEnqueueError: 送信に失敗した場合。**部分的に成功した場合も
                例外にする**(投入できなかった国がある事実を隠さない)。
        """
        ...
