"""`Settings` から `ScanRepository` を組み立てるファクトリ。

application 層は `ScanRepository`(Protocol)だけを見る
(docs/architecture.md「依存の向き」)。

**ここは DynamoDB 実装を返すだけである。** `SERPAPI_MODE=fixture` /
`LLM_MODE=stub` に相当する「AWS へ繋がない既定」を選ぶための設定が
`Settings` にまだ無いためである(`PERSISTENCE_MODE` の追加が必要)。

`settings.dynamodb_table_name` の有無から暗黙にモードを推測する実装は
**入れていない**。既定値 `"gapatlas"` があり `min_length=1` で必須のため
「未設定」を表現できず、判定が「テーブル名が既定値かどうか」という
別の意味にすり替わる。開発者が意図せず AWS へ繋がる事故のほうが危険である。

インメモリ実装が必要な場面では `InMemoryScanRepository` を直接組み立てること。
"""

from __future__ import annotations

from gapatlas.adapters.dynamodb.client import DynamoDbScanRepository
from gapatlas.adapters.dynamodb.protocol import ScanRepository
from gapatlas.config.settings import Settings


def create_scan_repository(settings: Settings) -> ScanRepository:
    """DynamoDB の `ScanRepository` を作る。

    Raises:
        RepositoryError: `boto3` パッケージが未インストールの場合。
    """
    return DynamoDbScanRepository(settings)
