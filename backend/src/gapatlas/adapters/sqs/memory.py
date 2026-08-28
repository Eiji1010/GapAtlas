"""インメモリの `JobQueue`。

AWS へ接続せずに API と Worker を通しで動かすための実装
(AGENTS.md「fixture mode を常に維持する」)。
"""

from __future__ import annotations

from collections.abc import Sequence

from gapatlas.application.jobs import ScanJob


class InMemoryJobQueue:
    """投入されたジョブを保持するだけの `JobQueue`。"""

    def __init__(self) -> None:
        self.jobs: list[ScanJob] = []

    def enqueue(self, jobs: Sequence[ScanJob]) -> None:
        self.jobs.extend(jobs)

    def drain(self) -> list[ScanJob]:
        """保持しているジョブを取り出して空にする。テストとローカル実行用。"""
        drained = list(self.jobs)
        self.jobs.clear()
        return drained
