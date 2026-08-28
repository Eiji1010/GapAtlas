"""`Settings` から `ScanArchive` を組み立てるファクトリ。

application 層は `ScanArchive`(Protocol)だけを見る
(docs/architecture.md「依存の向き」)。

**現時点では S3 実装しか返さない。** `Settings` に永続化のモードが無いため、
「AWS へ繋がない既定」(`SERPAPI_MODE=fixture` と同じ思想)へ切り替える判断が
できない。`InMemoryScanArchive` との切り替えは、設定項目を追加する統合担当が
この関数へ入れること。それまでは、AWS へ繋がない経路が必要な呼び出し側が
`InMemoryScanArchive` を直接組み立てる。
"""

from __future__ import annotations

from gapatlas.adapters.s3.client import S3ScanArchive
from gapatlas.adapters.s3.protocol import ScanArchive
from gapatlas.config.settings import Settings


def create_scan_archive(settings: Settings) -> ScanArchive:
    """S3 の `ScanArchive` を返す。

    Raises:
        ArchiveError: `boto3` が未インストールの場合。
    """
    return S3ScanArchive(settings)
