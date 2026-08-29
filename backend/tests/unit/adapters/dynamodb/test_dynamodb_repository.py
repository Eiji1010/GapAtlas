"""DynamoDB 実装に固有のテスト。

契約そのものは `test_scan_repository_contract.py` が両実装へ適用する。ここでは
キーの形・TTL・ページネーション・例外変換など**実装固有の振る舞い**だけを見る。

**実 AWS へ接続しない。** すべてフェイクの `Table` を注入する。
"""

from __future__ import annotations

import builtins
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import pytest
from botocore.exceptions import ClientError, EndpointConnectionError

from gapatlas.adapters.dynamodb.client import DynamoDbScanRepository
from gapatlas.adapters.dynamodb.errors import (
    RepositoryDataError,
    RepositoryError,
    RepositoryReadError,
    RepositoryWriteError,
)
from gapatlas.config.settings import Settings
from gapatlas.domain.models.common import Country

TTL_DAYS = 30
FIXED_NOW = datetime(2026, 8, 29, 12, 0, 0, tzinfo=UTC)
"""conftest の `fixed_now` fixture と同じ値。ずれていないことを検証する。"""

EXPECTED_TTL = int(datetime(2026, 9, 28, 12, 0, 0, tzinfo=UTC).timestamp())
"""`FIXED_NOW`(2026-08-29 12:00 UTC)から 30 日後の epoch 秒。"""


def test_the_injected_clock_matches_this_module(fixed_now):
    assert fixed_now == FIXED_NOW


def _client_error(operation: str) -> ClientError:
    return ClientError(
        {"Error": {"Code": "ProvisionedThroughputExceededException", "Message": "slow down"}},
        operation,
    )


# --- キーの形 -----------------------------------------------------------------------------


def test_save_country_writes_the_expected_keys(dynamodb_repository, fake_table, country_result):
    dynamodb_repository.save_country(country_result)
    item = fake_table.put_calls[0]
    assert item["PK"] == "SCAN#s1"
    assert item["SK"] == "COUNTRY#JP"


def test_save_scan_writes_the_meta_sort_key(dynamodb_repository, fake_table, scan_summary):
    dynamodb_repository.save_scan(scan_summary)
    item = fake_table.put_calls[0]
    assert item["PK"] == "SCAN#s1"
    assert item["SK"] == "META"


def test_country_attributes_are_expanded(dynamodb_repository, fake_table, country_result):
    """docs/architecture.md の COUNTRY item 例と同じ形で属性へ展開すること。"""
    dynamodb_repository.save_country(country_result)
    item = fake_table.put_calls[0]
    assert item["country"] == "JP"
    assert item["status"] == "completed"
    assert item["need_gap_score"] == 75
    assert item["confidence"] == 91


# --- TTL ----------------------------------------------------------------------------------


def test_country_item_has_a_ttl(dynamodb_repository, fake_table, country_result):
    dynamodb_repository.save_country(country_result)
    assert fake_table.put_calls[0]["ttl"] == EXPECTED_TTL


def test_scan_item_has_a_ttl(dynamodb_repository, fake_table, scan_summary):
    dynamodb_repository.save_scan(scan_summary)
    assert fake_table.put_calls[0]["ttl"] == EXPECTED_TTL


def test_ttl_is_derived_from_the_write_time_not_computed_at(
    make_repository, make_fake_table, country_result
):
    """`computed_at`(2026-08-28)ではなく保存時刻から算出すること。"""
    table = make_fake_table()
    later = datetime(2027, 1, 1, tzinfo=UTC)
    make_repository(table, now=later).save_country(country_result)
    assert table.put_calls[0]["ttl"] == int(datetime(2027, 1, 31, tzinfo=UTC).timestamp())


def test_ttl_days_is_configurable(make_repository, make_fake_table, country_result):
    table = make_fake_table()
    make_repository(table, ttl_days=1).save_country(country_result)
    assert table.put_calls[0]["ttl"] == int(datetime(2026, 8, 30, 12, 0, 0, tzinfo=UTC).timestamp())


def test_ttl_is_stored_as_a_number(dynamodb_repository, fake_table, country_result):
    """TTL は Number 属性でなければ DynamoDB が期限切れとして扱わない。"""
    dynamodb_repository.save_country(country_result)
    assert isinstance(fake_table.put_calls[0]["ttl"], int)
    assert isinstance(fake_table.items[("SCAN#s1", "COUNTRY#JP")]["ttl"], Decimal)


def test_ttl_is_not_restored_into_the_model(dynamodb_repository, country_result):
    """`ttl` を `extra="forbid"` のモデルへ渡さないこと。"""
    dynamodb_repository.save_country(country_result)
    assert dynamodb_repository.get_country("s1", Country.JP) is not None


@pytest.mark.parametrize("ttl_days", [0, -1])
def test_non_positive_ttl_days_is_rejected(fake_table, settings, ttl_days: int):
    with pytest.raises(RepositoryError, match="ttl_days"):
        DynamoDbScanRepository(settings, table=fake_table, ttl_days=ttl_days)


# --- Query とページネーション ---------------------------------------------------------------


def test_list_countries_queries_the_scan_partition(dynamodb_repository, fake_table, make_result):
    dynamodb_repository.save_country(make_result(Country.JP))
    dynamodb_repository.list_countries("s1")
    call = fake_table.query_calls[0]
    assert call["ExpressionAttributeValues"][":pk"] == "SCAN#s1"
    assert call["ExpressionAttributeNames"]["#pk"] == "PK"
    assert call["KeyConditionExpression"] == "#pk = :pk"


def test_list_countries_follows_pagination(
    make_repository, make_fake_table, make_result, make_summary
):
    """`LastEvaluatedKey` を2回返すフェイクで、全件が取れること。"""
    table = make_fake_table(page_size=2)
    repository = make_repository(table)
    repository.save_scan(make_summary())
    for country in (Country.JP, Country.US, Country.DE, Country.GB, Country.IN):
        repository.save_country(make_result(country))

    listed = repository.list_countries("s1")

    assert [result.country for result in listed] == [
        Country.DE,
        Country.GB,
        Country.IN,
        Country.JP,
        Country.US,
    ]
    assert len(table.query_calls) == 3
    assert "ExclusiveStartKey" not in table.query_calls[0]
    assert table.query_calls[1]["ExclusiveStartKey"]["SK"] == "COUNTRY#GB"
    assert table.query_calls[2]["ExclusiveStartKey"]["SK"] == "COUNTRY#JP"


def test_list_countries_ignores_unknown_sort_keys(dynamodb_repository, fake_table, country_result):
    """将来の項目種別が増えても既存の読み取りを落とさない。"""
    dynamodb_repository.save_country(country_result)
    fake_table.put_raw_item({"PK": "SCAN#s1", "SK": "BRIEF#JP", "anything": "at all"})
    assert [result.country for result in dynamodb_repository.list_countries("s1")] == [Country.JP]


# --- 例外変換 -----------------------------------------------------------------------------


def test_put_failure_becomes_a_write_error(make_repository, make_fake_table, country_result):
    repository = make_repository(make_fake_table(put_error=_client_error("PutItem")))
    with pytest.raises(RepositoryWriteError):
        repository.save_country(country_result)


def test_save_scan_failure_becomes_a_write_error(make_repository, make_fake_table, scan_summary):
    repository = make_repository(make_fake_table(put_error=_client_error("PutItem")))
    with pytest.raises(RepositoryWriteError):
        repository.save_scan(scan_summary)


def test_get_failure_becomes_a_read_error(make_repository, make_fake_table):
    repository = make_repository(make_fake_table(get_error=_client_error("GetItem")))
    with pytest.raises(RepositoryReadError):
        repository.get_scan("s1")


def test_query_failure_becomes_a_read_error(make_repository, make_fake_table):
    repository = make_repository(make_fake_table(query_error=_client_error("Query")))
    with pytest.raises(RepositoryReadError):
        repository.list_countries("s1")


def test_network_failure_becomes_a_read_error(make_repository, make_fake_table):
    """`ClientError` 以外の botocore 例外も変換すること。"""
    error = EndpointConnectionError(endpoint_url="https://dynamodb.example.invalid")
    repository = make_repository(make_fake_table(get_error=error))
    with pytest.raises(RepositoryReadError):
        repository.get_country("s1", Country.JP)


def test_programming_errors_are_not_disguised_as_repository_failures(
    make_repository, make_fake_table
):
    """実装バグ(`AttributeError` など)を DynamoDB の障害に見せかけない。"""
    repository = make_repository(make_fake_table(get_error=AttributeError("typo")))
    with pytest.raises(AttributeError):
        repository.get_scan("s1")


def test_write_error_message_does_not_contain_item_content(
    make_repository, make_fake_table, make_result
):
    """例外メッセージへ項目の中身を載せない(docs/architecture.md「Security」)。"""
    sensitive_value = "personally-identifiable-payload"
    result = make_result(Country.JP, scan_id=sensitive_value)
    repository = make_repository(make_fake_table(put_error=_client_error("PutItem")))
    with pytest.raises(RepositoryWriteError) as excinfo:
        repository.save_country(result)
    assert sensitive_value not in str(excinfo.value)
    assert "elder_care" not in str(excinfo.value)


# --- 壊れた項目 ---------------------------------------------------------------------------


def test_corrupt_item_raises_a_data_error(dynamodb_repository, fake_table):
    fake_table.put_raw_item({"PK": "SCAN#s1", "SK": "COUNTRY#JP", "country": "JP"})
    with pytest.raises(RepositoryDataError):
        dynamodb_repository.get_country("s1", Country.JP)


def test_corrupt_item_in_a_listing_raises_a_data_error(dynamodb_repository, fake_table):
    fake_table.put_raw_item({"PK": "SCAN#s1", "SK": "COUNTRY#JP", "country": "JP"})
    with pytest.raises(RepositoryDataError):
        dynamodb_repository.list_countries("s1")


def test_type_mismatch_raises_a_data_error(dynamodb_repository, fake_table, country_result):
    dynamodb_repository.save_country(country_result)
    stored = dict(fake_table.items[("SCAN#s1", "COUNTRY#JP")])
    stored["confidence"] = "ninety-one"
    fake_table.put_raw_item(stored)
    with pytest.raises(RepositoryDataError):
        dynamodb_repository.get_country("s1", Country.JP)


# --- boto3 未インストール ------------------------------------------------------------------


def test_missing_boto3_raises_a_clear_repository_error(monkeypatch: pytest.MonkeyPatch):
    """optional extra が入っていない環境で分かりやすい例外にすること。"""
    real_import = builtins.__import__

    def fake_import(name: str, *args: Any, **kwargs: Any) -> Any:
        if name == "boto3" or name.startswith("boto3."):
            message = "No module named 'boto3'"
            raise ImportError(message)
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    with pytest.raises(RepositoryError, match="boto3"):
        DynamoDbScanRepository(Settings())


def test_injected_table_does_not_need_boto3(monkeypatch: pytest.MonkeyPatch, fake_table, settings):
    """フェイクを注入する単体テストは boto3 を要求しない。"""
    real_import = builtins.__import__

    def fake_import(name: str, *args: Any, **kwargs: Any) -> Any:
        if name == "boto3" or name.startswith("boto3."):
            message = "No module named 'boto3'"
            raise ImportError(message)
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    assert DynamoDbScanRepository(settings, table=fake_table).get_scan("s1") is None


# --- 決定性 -------------------------------------------------------------------------------


def test_default_now_is_the_current_time(fake_table, settings, country_result):
    """`now` を省略しても動くこと(既定は実時刻。テストは範囲だけ確認する)。"""
    before = int(datetime.now(UTC).timestamp())
    DynamoDbScanRepository(settings, table=fake_table).save_country(country_result)
    ttl = fake_table.put_calls[0]["ttl"]
    assert ttl >= before + TTL_DAYS * 86_400 - 5


def test_injected_now_is_used(fake_table, settings, country_result):
    calls: list[int] = []

    def now() -> datetime:
        calls.append(1)
        return FIXED_NOW

    DynamoDbScanRepository(settings, table=fake_table, now=now).save_country(country_result)
    assert calls == [1]


def test_list_country_statuses_projects_only_the_needed_attributes(
    fake_table, dynamodb_repository, make_result
):
    """進捗を数えるためだけに 20KB の項目を全部読まないこと。

    `GET /scans/{id}` は2秒間隔で叩かれる。全属性を読むと、2.4KB の応答に
    100KB 超の読み取りが毎回発生する。
    """
    dynamodb_repository.save_country(make_result(Country.JP))

    dynamodb_repository.list_country_statuses("s1")

    projections = [call.get("ProjectionExpression") for call in fake_table.query_calls]
    assert projections and all(value is not None for value in projections)
    names = fake_table.query_calls[-1]["ExpressionAttributeNames"]
    assert set(names.values()) >= {"SK", "country", "status"}
