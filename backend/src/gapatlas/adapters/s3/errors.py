"""S3 アーカイブアダプタの例外。

`GapAtlasError` を基底にすることで、呼び出し側は adapters 層由来の失敗を
`ArchiveError` として一括で捕捉できる。**書き込みの失敗でスキャンを止めない**
方針(`protocol.py` / docs/architecture.md「Reliability」)のため、application 層は
ここで定義した例外を捕捉してログへ残し、スコアの算出と返却は続ける。

**例外メッセージに保存内容そのものを載せない。** raw の SerpApi レスポンスには
API キーを含む URL が混ざりうるうえ、本文をそのまま連結すると障害時のログが
巨大化する。載せてよいのはバケット名・オブジェクトキー・原因例外の型名まで
(docs/architecture.md「Observability」/「Security」)。
"""

from __future__ import annotations

from gapatlas.domain.models.errors import GapAtlasError


class ArchiveError(GapAtlasError):
    """S3 アーカイブアダプタの例外の基底。

    設定不備(バケット名が不正、`boto3` 未インストール)もここに含める。
    """


class ArchiveWriteError(ArchiveError):
    """オブジェクトの書き込みに失敗した場合。

    通信障害・権限不足に加え、本文を JSON へ直列化できなかった場合と、
    本文がサイズ上限を超えた場合を含む。
    """


class ArchiveReadError(ArchiveError):
    """オブジェクトの読み取りに失敗した場合。

    「存在しない」は失敗ではない。この例外は通信障害や権限不足など、
    **結果を判定できなかった**場合に使う。

    MVP の `ScanArchive` は書き込みのみを契約に持つ(UI が読むのは DynamoDB、
    履歴は Athena が読む)。読み取り経路を追加する Phase 12 が使う。
    """
