"""DynamoDB を使う `ScanRepository`。

docs/architecture.md「DynamoDB」のアクセスパターンだけを実装する。

1. `GET /scans/{scan_id}` → PK 単一・SK `META` の GetItem
2. 進捗とランキング → PK 単一の Query(`SCAN#{id}` 配下すべて)
3. `GET /scans/{scan_id}/countries/{country}` → PK+SK の GetItem

**boto3 の resource インタフェース(`Table`)を使う。** client インタフェースと
違って型記述子(`{"S": ...}`)の組み立てが不要で、数値は `Decimal` として
往復する。`serialization.py` はその前提で書いてある。

**契約(`protocol.py`):**

- 「項目が存在しない」は例外ではなく `None` / `[]`。404 は API 層が組み立てる
- 通信・権限の失敗は `RepositoryWriteError` / `RepositoryReadError` へ変換する
- 保存内容を復元できない場合は `RepositoryDataError`

**例外メッセージへ項目の中身を載せない**(docs/architecture.md「Security」)。
操作名と例外の型名だけを載せる。原因の詳細は botocore の例外側に残る。

`boto3` は optional extra(`aws`)のため**モジュールトップで import しない**。
未インストール環境で本モジュールの import 自体が失敗しないようにする。
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from typing import Any, Final

from gapatlas.adapters.dynamodb.errors import (
    RepositoryError,
    RepositoryReadError,
    RepositoryWriteError,
)
from gapatlas.adapters.dynamodb.serialization import from_attributes, to_attributes
from gapatlas.adapters.dynamodb.table import (
    PARTITION_KEY_ATTRIBUTE,
    SORT_KEY_ATTRIBUTE,
    TTL_ATTRIBUTE,
    country_sort_key,
    is_country_sort_key,
    meta_sort_key,
    scan_partition_key,
)
from gapatlas.config.settings import Settings
from gapatlas.domain.models.common import Country
from gapatlas.domain.models.result import CountryResult, ScanSummary

DEFAULT_TTL_DAYS: Final[int] = 30
"""既定の保持日数。ハッカソンのデモ用途であり、長期保存は S3 が担当する。"""

_PARTITION_KEY_PLACEHOLDER: Final[str] = "#pk"
_PARTITION_VALUE_PLACEHOLDER: Final[str] = ":pk"


def _utc_now() -> datetime:
    return datetime.now(UTC)


class DynamoDbScanRepository:
    """DynamoDB 上の `ScanRepository`。"""

    def __init__(
        self,
        settings: Settings,
        *,
        table: Any | None = None,
        ttl_days: int = DEFAULT_TTL_DAYS,
        now: Callable[[], datetime] = _utc_now,
    ) -> None:
        """
        Args:
            settings: `dynamodb_table_name` と `aws_region` を読む。
            table: 使用する boto3 の `Table` 相当のオブジェクト。省略時は
                `boto3` から組み立てる。**テストは必ずフェイクを渡すこと**
                (単体テストで実 AWS を呼ばない。認証情報が無い前提)。
            ttl_days: 保存時刻から数えた保持日数。
            now: 現在時刻を返す関数。TTL の算出点であり、テストを決定的に
                するため注入可能にしている。

        Raises:
            RepositoryError: `ttl_days` が正でない場合、または `table` 未指定で
                `boto3` が未インストールの場合。
        """
        if ttl_days <= 0:
            message = f"ttl_days must be positive (got {ttl_days})"
            raise RepositoryError(message)

        self._table_name = settings.dynamodb_table_name
        self._ttl_days = ttl_days
        self._now = now
        self._table: Any = (
            table
            if table is not None
            else _build_default_table(
                table_name=settings.dynamodb_table_name, region=settings.aws_region
            )
        )

    # --- 書き込み ---------------------------------------------------------------------

    def save_scan(self, summary: ScanSummary) -> None:
        item = to_attributes(summary)
        item[PARTITION_KEY_ATTRIBUTE] = scan_partition_key(summary.scan_id)
        item[SORT_KEY_ATTRIBUTE] = meta_sort_key()
        item[TTL_ATTRIBUTE] = self._expires_at()
        self._put_item(item, operation="save scan")

    def save_country(self, result: CountryResult) -> None:
        item = to_attributes(result)
        item[PARTITION_KEY_ATTRIBUTE] = scan_partition_key(result.scan_id)
        item[SORT_KEY_ATTRIBUTE] = country_sort_key(result.country)
        item[TTL_ATTRIBUTE] = self._expires_at()
        self._put_item(item, operation="save country result")

    # --- 読み取り ---------------------------------------------------------------------

    def get_scan(self, scan_id: str) -> ScanSummary | None:
        item = self._get_item(
            {
                PARTITION_KEY_ATTRIBUTE: scan_partition_key(scan_id),
                SORT_KEY_ATTRIBUTE: meta_sort_key(),
            },
            operation="read scan",
        )
        if item is None:
            return None
        return from_attributes(ScanSummary, item)

    def get_country(self, scan_id: str, country: Country) -> CountryResult | None:
        item = self._get_item(
            {
                PARTITION_KEY_ATTRIBUTE: scan_partition_key(scan_id),
                SORT_KEY_ATTRIBUTE: country_sort_key(country),
            },
            operation="read country result",
        )
        if item is None:
            return None
        return from_attributes(CountryResult, item)

    def list_countries(self, scan_id: str) -> list[CountryResult]:
        """`SCAN#{scan_id}` 配下を Query し、`META` を除いて国コード昇順で返す。

        `LastEvaluatedKey` がある限り続きを取得する。1ページで打ち切ると、
        Evidence が増えて 1MB を超えた時点で国が無言で欠ける。
        """
        results = [
            from_attributes(CountryResult, item)
            for item in self._query_all(scan_partition_key(scan_id))
            if is_country_sort_key(str(item.get(SORT_KEY_ATTRIBUTE, "")))
        ]
        return sorted(results, key=lambda result: result.country.value)

    # --- 内部 -------------------------------------------------------------------------

    def _expires_at(self) -> int:
        """TTL 属性の値(Unix epoch 秒)。

        **`computed_at` ではなく「保存時刻」から算出する。** 理由は2つある。

        - `ScanSummary` には時刻フィールドが無く、`computed_at` を持つのは
          `CountryResult` だけである。基準を揃えられない
        - TTL の目的は「デモ後に自動削除する」ことであり、保持期間は
          **書いた時点から**数えるのが自然である。過去のスキャンを再保存した
          ときに即時削除されない
        """
        return int((self._now() + timedelta(days=self._ttl_days)).timestamp())

    def _put_item(self, item: Mapping[str, Any], *, operation: str) -> None:
        try:
            self._table.put_item(Item=dict(item))
        except _aws_error_types() as exc:
            raise RepositoryWriteError(self._failure_message(operation, exc)) from exc

    def _get_item(self, key: Mapping[str, str], *, operation: str) -> Mapping[str, Any] | None:
        try:
            response = self._table.get_item(Key=dict(key))
        except _aws_error_types() as exc:
            raise RepositoryReadError(self._failure_message(operation, exc)) from exc
        item: Mapping[str, Any] | None = response.get("Item")
        return item

    def _query_all(self, partition_key: str) -> list[Mapping[str, Any]]:
        items: list[Mapping[str, Any]] = []
        start_key: Mapping[str, Any] | None = None
        while True:
            arguments: dict[str, Any] = {
                "KeyConditionExpression": (
                    f"{_PARTITION_KEY_PLACEHOLDER} = {_PARTITION_VALUE_PLACEHOLDER}"
                ),
                "ExpressionAttributeNames": {_PARTITION_KEY_PLACEHOLDER: PARTITION_KEY_ATTRIBUTE},
                "ExpressionAttributeValues": {_PARTITION_VALUE_PLACEHOLDER: partition_key},
            }
            if start_key is not None:
                arguments["ExclusiveStartKey"] = dict(start_key)
            try:
                response = self._table.query(**arguments)
            except _aws_error_types() as exc:
                raise RepositoryReadError(
                    self._failure_message("list country results", exc)
                ) from exc
            items.extend(response.get("Items", []))
            start_key = response.get("LastEvaluatedKey")
            if start_key is None:
                return items

    def _failure_message(self, operation: str, exc: BaseException) -> str:
        """失敗の説明。**項目の中身は載せない。**"""
        return (
            f"failed to {operation} in DynamoDB table '{self._table_name}' ({type(exc).__name__})"
        )


@lru_cache(maxsize=1)
def _aws_error_types() -> tuple[type[BaseException], ...]:
    """`RepositoryError` へ変換すべき botocore の例外型。

    `botocore` も optional extra(`aws`)に付いてくるため遅延 import する。
    未インストールで、かつ `table` が注入されている場合は変換対象が無いので
    空タプルを返す(`except ()` は何も捕捉しない)。

    `Exception` を丸ごと捕捉しない。`AttributeError` などの実装バグまで
    「DynamoDB の障害」に見えてしまい、原因が追えなくなる。
    """
    try:
        from botocore.exceptions import BotoCoreError, ClientError  # noqa: PLC0415
    except ImportError:  # pragma: no cover - boto3 は aws extra として導入済み
        return ()
    return (BotoCoreError, ClientError)


def _build_default_table(*, table_name: str, region: str) -> Any:
    """`boto3` を遅延 import して `Table` を作る。

    Raises:
        RepositoryError: `boto3` パッケージが未インストールの場合。
    """
    try:
        import boto3  # noqa: PLC0415
    except ImportError as exc:
        message = (
            "the 'boto3' package is not installed; "
            "install the 'aws' optional extra to use DynamoDbScanRepository"
        )
        raise RepositoryError(message) from exc
    return boto3.resource("dynamodb", region_name=region).Table(table_name)
