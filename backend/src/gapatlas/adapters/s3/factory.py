"""`Settings` から `ScanArchive` を組み立てるファクトリ。

`PERSISTENCE_MODE` の分岐をここへ閉じ込め、application 層は `ScanArchive`
(Protocol)だけを見る。**既定は `memory`** で、外部通信ゼロで全機能が動く
状態を保つ(AGENTS.md 絶対ルール)。
"""

from __future__ import annotations

from typing import assert_never

from gapatlas.adapters.s3.client import S3ScanArchive
from gapatlas.adapters.s3.memory import InMemoryScanArchive
from gapatlas.adapters.s3.protocol import ScanArchive
from gapatlas.config.settings import PersistenceMode, Settings


def create_scan_archive(settings: Settings) -> ScanArchive:
    """`settings.persistence_mode` に応じたアーカイブを返す。

    モードを増やして `case` を書き忘れると、実行時ではなく **mypy が**
    気付く(`assert_never`)。
    """
    match settings.persistence_mode:
        case PersistenceMode.MEMORY:
            return InMemoryScanArchive()
        case PersistenceMode.AWS:
            return S3ScanArchive(settings)
        case unsupported:  # pragma: no cover - Enum を増やしたときに型検査で気付く
            assert_never(unsupported)
