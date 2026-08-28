"""S3 へ書き出す `ScanArchive` 実装。

配置は `keys.py`(docs/architecture.md「S3 Data Lake」の正本)に従う。
**キーを自前で組み立てない。** Glue のパーティション射影(`athena.py`)が
`keys.py` の配置に依存しているため、組み立ては1箇所に閉じる。

**`raw/` は SerpApi のレスポンスを JSON のまま保存する。** キーの並び替え・
インデント・非 ASCII のエスケープを行わない。契約(`protocol.py`)が受け取るのは
`Mapping` であり元のバイト列ではないため再直列化は避けられないが、内容
(キー・順序・型)は変えない。

**`normalized/` と `curated/` は JSON Lines(1行1レコード)で書く。** Glue の
JSON SerDe が行区切りの JSON を前提にするため。1オブジェクト1レコードなので、
結果としてファイルは単一の JSON オブジェクトとしても読める。

docs/architecture.md は「`normalized/` `curated/` は可能なら Parquet」としているが、
Parquet ライブラリ(pyarrow 等)は依存に無く、承認なしに依存を追加しない
(AGENTS.md「禁止事項」)ため JSON Lines で実装している。

**実 AWS へ接続するのは `client` を注入しなかった場合だけ。** 単体テストは必ず
フェイクを渡すこと(AWS 認証情報が無い前提)。
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import datetime
from typing import Any, Final

from gapatlas.adapters.s3.errors import ArchiveError, ArchiveWriteError
from gapatlas.adapters.s3.keys import curated_key, normalized_key, raw_key
from gapatlas.config.settings import Settings
from gapatlas.domain.models.common import Country, SourceName, TopicId
from gapatlas.domain.models.normalized import NormalizedEvidence
from gapatlas.domain.models.result import CountryResult

CONTENT_TYPE_JSON: Final[str] = "application/json"
"""オブジェクトの `Content-Type`。キーの拡張子(`.json`)と一致させる。"""

SERVER_SIDE_ENCRYPTION: Final[str] = "AES256"
"""サーバサイド暗号化の方式(SSE-S3)。

バケット既定の暗号化に依存せず、**書き込み側でも保存時暗号化を明示する**。
既定設定が変わっても個々のオブジェクトで保証されるため。SSE-KMS ではなく
SSE-S3 を選ぶのは、Lambda の IAM へ `kms:Decrypt` / `kms:GenerateDataKey` を
足さずに済み(docs/architecture.md「Security」の Least Privilege)、KMS の
リクエスト課金も増やさないため。分析用の集計値と検索結果であり、顧客管理鍵を
必要とする個人情報は保存しない(AGENTS.md「個人情報を収集しない」)。
"""

MAX_OBJECT_BYTES: Final[int] = 8 * 1024 * 1024
"""1オブジェクトの本文の上限。

`adapters/serpapi/live_client.py` の `MAX_RESPONSE_BYTES` と同じ値。SerpApi の
実レスポンスは未検証(docs/serpapi-schema.md 7章)で、障害時に巨大な本文が
返りうる。上限が無いと boto3 が本文全体をバッファしてリトライまで行い、
「1オブジェクトの保存失敗」ではなく Lambda のメモリ枯渇になる
(docs/architecture.md「Reliability」)。

直列化したバイト列に対して判定するため直列化そのものの割り当ては防げないが、
**boto3 へ無制限の本文を渡さない**ための防御としては機能する。上限超過は
`ArchiveWriteError` にする。保存の失敗はスキャンを止めない契約であり、
プロセスごと落とすより 1件を捨てるほうが安全なため。
"""

_PROGRAMMING_ERRORS: Final[tuple[type[BaseException], ...]] = (
    AttributeError,
    TypeError,
    NameError,
    ImportError,
)
"""S3 の障害として扱ってはいけない例外。

boto3 のシグネチャ変更や属性名の誤りといった実装バグであり、
`ArchiveWriteError` へ変換すると呼び出し側が「保存に失敗したがスキャンは続行」
として握りつぶし、原因が追えなくなる。
"""


class S3ScanArchive:
    """S3 へ書き出す `ScanArchive`。"""

    def __init__(self, settings: Settings, *, client: Any | None = None) -> None:
        """アーカイブを組み立てる。

        Args:
            settings: `s3_bucket_name` と `aws_region` を読む。
            client: 注入する S3 クライアント。テストは必ずフェイクを渡すこと
                (単体テストで実 AWS を呼ばない。AWS 認証情報が無い前提)。

        Raises:
            ArchiveError: `client` 未指定で `boto3` が未インストールの場合。
        """
        self._bucket = settings.s3_bucket_name
        if client is not None:
            self._client: Any = client
            return
        self._client = _build_default_client(region=settings.aws_region)

    def put_raw(
        self,
        *,
        source: SourceName,
        topic_id: TopicId,
        country: Country,
        scan_time: datetime,
        scan_id: str,
        payload: Mapping[str, Any],
    ) -> str:
        """SerpApi の生レスポンスを無加工で保存する。

        Raises:
            ArchiveWriteError: 直列化・書き込みに失敗した場合。
        """
        key = raw_key(
            source=source,
            topic_id=topic_id,
            country=country,
            scan_time=scan_time,
            scan_id=scan_id,
        )
        # raw は無加工で保存する(docs/architecture.md)。sort_keys を使わず
        # 挿入順を保ち、ensure_ascii=False で非 ASCII をそのまま残す。
        return self._put(key, _dump_raw(payload, key=key))

    def put_normalized(
        self,
        *,
        topic_id: TopicId,
        country: Country,
        scan_time: datetime,
        scan_id: str,
        evidence: NormalizedEvidence,
    ) -> str:
        """正規化済み証拠データを保存する。

        Raises:
            ArchiveWriteError: 書き込みに失敗した場合。
        """
        key = normalized_key(
            topic_id=topic_id, country=country, scan_time=scan_time, scan_id=scan_id
        )
        return self._put(key, _as_json_line(evidence.model_dump_json()))

    def put_curated(
        self,
        *,
        topic_id: TopicId,
        country: Country,
        scan_time: datetime,
        scan_id: str,
        result: CountryResult,
    ) -> str:
        """スコアを保存する。Athena の分析対象(`athena.py`)。

        Raises:
            ArchiveWriteError: 書き込みに失敗した場合。
        """
        key = curated_key(topic_id=topic_id, country=country, scan_time=scan_time, scan_id=scan_id)
        return self._put(key, _as_json_line(result.model_dump_json()))

    def _put(self, key: str, body: str) -> str:
        """本文を UTF-8 の bytes として PUT する。戻り値はオブジェクトキー。

        **ACL は指定しない。** S3 の public access は禁止であり
        (docs/architecture.md「Security」)、`ACL` を渡すコードを置かないことで
        公開設定が事故で入る経路自体を作らない。公開ブロックはバケット側の
        Block Public Access(Phase 13)で担保する。

        Raises:
            ArchiveWriteError: 上限超過、または S3 の呼び出しが失敗した場合。
        """
        data = body.encode("utf-8")
        if len(data) > MAX_OBJECT_BYTES:
            raise ArchiveWriteError(
                f"object body for s3://{self._bucket}/{key} exceeds "
                f"{MAX_OBJECT_BYTES} bytes (got {len(data)} bytes)"
            )

        try:
            self._client.put_object(
                Bucket=self._bucket,
                Key=key,
                Body=data,
                ContentType=CONTENT_TYPE_JSON,
                ServerSideEncryption=SERVER_SIDE_ENCRYPTION,
            )
        except _PROGRAMMING_ERRORS:
            # 実装バグを S3 の障害として隠さない。そのまま上へ投げる。
            raise
        except Exception as exc:
            # 原因例外の本文は載せない(保存内容や URL が混ざりうるため)。
            raise ArchiveWriteError(
                f"failed to write s3://{self._bucket}/{key} ({type(exc).__name__})"
            ) from exc
        return key


def _dump_raw(payload: Mapping[str, Any], *, key: str) -> str:
    """生レスポンスを JSON 文字列にする。

    Raises:
        ArchiveWriteError: JSON へ直列化できない値が含まれる場合。
    """
    try:
        return json.dumps(dict(payload), ensure_ascii=False)
    except (TypeError, ValueError) as exc:
        # 直列化できない値は呼び出し側のバグだが、保存の失敗でスキャンを
        # 止めない契約に合わせて ArchiveWriteError へ寄せる。内容は載せない。
        raise ArchiveWriteError(
            f"raw payload for s3://…/{key} is not JSON-serializable ({type(exc).__name__})"
        ) from exc


def _as_json_line(document: str) -> str:
    """JSON Lines の1行にする(末尾に改行を付ける)。

    Glue の JSON SerDe は行区切りの JSON を読む(`athena.py`)。Pydantic の
    `model_dump_json()` は改行を含まないため、末尾の改行だけで1レコードになる。
    """
    return f"{document}\n"


def _build_default_client(*, region: str) -> Any:
    """`boto3` を遅延 import して S3 クライアントを作る。

    optional extra(`aws`)なので、未インストール環境で本モジュールの import
    自体が失敗しないよう、トップレベルでは import しない。

    Raises:
        ArchiveError: `boto3` が未インストールの場合。
    """
    try:
        import boto3  # noqa: PLC0415
    except ImportError as exc:
        message = (
            "the 'boto3' package is not installed; install the 'aws' optional extra to write to S3"
        )
        raise ArchiveError(message) from exc
    return boto3.client("s3", region_name=region)
