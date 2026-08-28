"""`Settings` から `ScanRepository` を組み立てるファクトリ。

`PERSISTENCE_MODE` の分岐をここへ閉じ込め、application 層は `ScanRepository`
(Protocol)だけを見る(docs/architecture.md「依存の向き」)。

**既定は `memory`。** テーブル名から AWS 利用を推測してはいけない
(`dynamodb_table_name` は既定値を持つ必須項目なので「未設定」を表現できず、
開発者が意図せず AWS へ繋がる事故になる)。
"""

from __future__ import annotations

from typing import assert_never

from gapatlas.adapters.dynamodb.client import DynamoDbScanRepository
from gapatlas.adapters.dynamodb.memory import InMemoryScanRepository
from gapatlas.adapters.dynamodb.protocol import ScanRepository
from gapatlas.config.settings import PersistenceMode, Settings


def create_scan_repository(settings: Settings) -> ScanRepository:
    """`settings.persistence_mode` に応じたリポジトリを返す。

    モードを増やして `case` を書き忘れると、実行時ではなく **mypy が**
    気付く(`assert_never`)。
    """
    match settings.persistence_mode:
        case PersistenceMode.MEMORY:
            return InMemoryScanRepository()
        case PersistenceMode.AWS:
            return DynamoDbScanRepository(settings)
        case unsupported:  # pragma: no cover - Enum を増やしたときに型検査で気付く
            assert_never(unsupported)
