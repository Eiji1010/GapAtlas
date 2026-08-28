"""永続化アダプタのテストで共有する fixture とフェイク。

テストは決定的にする。現在時刻・乱数・ネットワークに依存しない。
**実 AWS へは接続しない。** DynamoDB 実装には必ずフェイクの `Table` を渡す。
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from copy import deepcopy
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import pytest

from gapatlas.adapters.dynamodb.client import DynamoDbScanRepository
from gapatlas.adapters.dynamodb.memory import InMemoryScanRepository
from gapatlas.adapters.dynamodb.protocol import ScanRepository
from gapatlas.adapters.dynamodb.table import (
    PARTITION_KEY_ATTRIBUTE,
    SORT_KEY_ATTRIBUTE,
)
from gapatlas.config.settings import Settings
from gapatlas.domain.models.common import Country, CountryStatus, ScanStatus, SourceName, TopicId
from gapatlas.domain.models.result import (
    CountryResult,
    Evidence,
    OpportunityBrief,
    RankingEntry,
    ScanProgress,
    ScanSummary,
    Versions,
)
from gapatlas.domain.models.scores import ConfidenceBreakdown, ScoreComponents

SCAN_TIME = datetime(2026, 8, 28, tzinfo=UTC)
"""結果に載る `computed_at`。固定値。"""

FIXED_NOW = datetime(2026, 8, 29, 12, 0, 0, tzinfo=UTC)
"""保存時刻として注入する現在時刻。TTL の算出基準。"""

TABLE_NAME = "gapatlas-test"

VERSIONS = Versions(
    query_profile_version="elder-care-jp-v2",
    score_version="gapatlas-score-v1",
    classifier_version="gapatlas-classifier-v1-stub",
    prompt_version="gapatlas-prompt-v1-stub",
)


def make_settings(table_name: str = TABLE_NAME) -> Settings:
    """テスト用の `Settings`。既定は fixture / stub モードのまま。"""
    return Settings(dynamodb_table_name=table_name)


def make_country_result(
    country: Country = Country.JP,
    *,
    scan_id: str = "s1",
    score: int | None = 75,
) -> CountryResult:
    """契約テスト用の `CountryResult`。float・int・None・ネストしたリストを含む。"""
    return CountryResult(
        scan_id=scan_id,
        topic_id=TopicId.ELDER_CARE,
        country=country,
        status=CountryStatus.COMPLETED if score is not None else CountryStatus.FAILED,
        need_gap_score=score,
        confidence=91,
        components=ScoreComponents(demand=84.6, pain=70.0, solution_gap=None, news_urgency=0.0),
        confidence_breakdown=ConfidenceBreakdown(
            data_completeness=100.0,
            sample_sufficiency=97.25,
            localization_quality=70.0,
            source_agreement=88.5,
            freshness=92.0,
        ),
        evidence=[
            Evidence(
                id="E1",
                source=SourceName.TRENDS,
                summary="rising interest in elder care",
                url="https://example.com/a",
            ),
            Evidence(id="E2", source=SourceName.NEWS, summary="staff shortage reported", url=None),
        ],
        versions=VERSIONS,
        computed_at=SCAN_TIME,
    )


def make_scan_summary(scan_id: str = "s1", *, with_brief: bool = False) -> ScanSummary:
    """契約テスト用の `ScanSummary`。`ranking` はネストしたリスト。"""
    return ScanSummary(
        scan_id=scan_id,
        topic_id=TopicId.ELDER_CARE,
        status=ScanStatus.COMPLETED,
        progress=ScanProgress(total=2, completed=2),
        completed_countries=[Country.JP, Country.US],
        ranking=[
            RankingEntry(
                country=Country.JP,
                status=CountryStatus.COMPLETED,
                need_gap_score=86,
                confidence=92,
                demand=91,
                pain=84,
                solution_gap=78,
                news_urgency=83,
            ),
            RankingEntry(
                country=Country.US,
                status=CountryStatus.FAILED,
                need_gap_score=None,
                confidence=0,
            ),
        ],
        opportunity_brief=(
            OpportunityBrief(
                why_now="search interest is rising",
                what_people_are_struggling_with="finding available caregivers",
                visible_solutions="a few national directories",
                what_this_does_not_prove="this is not a measure of actual supply",
                next_validation="interview local operators",
                cited_evidence_ids=["E1", "E2"],
            )
            if with_brief
            else None
        ),
        versions=VERSIONS,
    )


def _to_stored(value: object) -> object:
    """boto3 の resource インタフェースと同じ制約で値を保存形へ変換する。

    - `float` は受け付けず `TypeError`(boto3 の実挙動)
    - 数値はすべて `Decimal` として保持し、読み取り時に `Decimal` で返す
    """
    if value is None or isinstance(value, bool | str | Decimal):
        return value
    if isinstance(value, float):
        message = "Float types are not supported. Use Decimal types instead."
        raise TypeError(message)
    if isinstance(value, int):
        return Decimal(value)
    if isinstance(value, Mapping):
        return {str(key): _to_stored(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_to_stored(item) for item in value]
    message = f"unsupported type {type(value).__name__}"
    raise TypeError(message)


class FakeDynamoDbTable:
    """`boto3.resource("dynamodb").Table` の最小の模倣。

    実 DynamoDB の戻り値の形をそのまま再現する。

    - `get_item`: 見つかれば `{"Item": {...}}`、無ければ `{}`
    - `query`: `{"Items": [...]}`、続きがあれば `LastEvaluatedKey` を添える
    - 数値はすべて `Decimal` で返す
    - `float` の書き込みは `TypeError`
    """

    def __init__(
        self,
        *,
        page_size: int | None = None,
        put_error: Exception | None = None,
        get_error: Exception | None = None,
        query_error: Exception | None = None,
    ) -> None:
        self.items: dict[tuple[str, str], dict[str, Any]] = {}
        self.put_calls: list[dict[str, Any]] = []
        self.query_calls: list[dict[str, Any]] = []
        self.page_size = page_size
        self.put_error = put_error
        self.get_error = get_error
        self.query_error = query_error

    def put_item(self, *, Item: Mapping[str, Any]) -> dict[str, Any]:  # noqa: N803
        if self.put_error is not None:
            raise self.put_error
        self.put_calls.append(deepcopy(dict(Item)))
        stored = _to_stored(Item)
        assert isinstance(stored, dict)
        key = (str(stored[PARTITION_KEY_ATTRIBUTE]), str(stored[SORT_KEY_ATTRIBUTE]))
        self.items[key] = stored
        return {}

    def get_item(self, *, Key: Mapping[str, str]) -> dict[str, Any]:  # noqa: N803
        if self.get_error is not None:
            raise self.get_error
        stored = self.items.get((Key[PARTITION_KEY_ATTRIBUTE], Key[SORT_KEY_ATTRIBUTE]))
        if stored is None:
            return {}
        return {"Item": deepcopy(stored)}

    def query(self, **arguments: Any) -> dict[str, Any]:
        if self.query_error is not None:
            raise self.query_error
        self.query_calls.append(deepcopy(arguments))
        partition = arguments["ExpressionAttributeValues"][":pk"]
        matched = sorted(
            (item for item in self.items.values() if item[PARTITION_KEY_ATTRIBUTE] == partition),
            key=lambda item: str(item[SORT_KEY_ATTRIBUTE]),
        )
        start_key = arguments.get("ExclusiveStartKey")
        if start_key is not None:
            after = str(start_key[SORT_KEY_ATTRIBUTE])
            matched = [item for item in matched if str(item[SORT_KEY_ATTRIBUTE]) > after]
        if self.page_size is None or len(matched) <= self.page_size:
            return {"Items": [deepcopy(item) for item in matched]}
        page = matched[: self.page_size]
        last = page[-1]
        return {
            "Items": [deepcopy(item) for item in page],
            "LastEvaluatedKey": {
                PARTITION_KEY_ATTRIBUTE: last[PARTITION_KEY_ATTRIBUTE],
                SORT_KEY_ATTRIBUTE: last[SORT_KEY_ATTRIBUTE],
            },
        }

    def put_raw_item(self, item: Mapping[str, Any]) -> None:
        """検証を通さずに項目を置く。壊れた項目の再現に使う。"""
        stored = _to_stored(item)
        assert isinstance(stored, dict)
        key = (str(stored[PARTITION_KEY_ATTRIBUTE]), str(stored[SORT_KEY_ATTRIBUTE]))
        self.items[key] = stored


def make_dynamodb_repository(
    table: FakeDynamoDbTable,
    *,
    ttl_days: int = 30,
    now: datetime = FIXED_NOW,
) -> DynamoDbScanRepository:
    """フェイクの `Table` を注入した DynamoDB リポジトリ。"""
    return DynamoDbScanRepository(make_settings(), table=table, ttl_days=ttl_days, now=lambda: now)


@pytest.fixture
def fixed_now() -> datetime:
    """`make_dynamodb_repository` が注入する保存時刻。TTL の期待値の基準。"""
    return FIXED_NOW


@pytest.fixture
def fake_table() -> FakeDynamoDbTable:
    return FakeDynamoDbTable()


@pytest.fixture
def make_fake_table() -> type[FakeDynamoDbTable]:
    """フェイクの `Table` を作るクラス。ページ分割やエラー注入に使う。"""
    return FakeDynamoDbTable


@pytest.fixture
def make_repository() -> Callable[..., DynamoDbScanRepository]:
    return make_dynamodb_repository


@pytest.fixture
def dynamodb_repository(fake_table: FakeDynamoDbTable) -> DynamoDbScanRepository:
    return make_dynamodb_repository(fake_table)


@pytest.fixture
def settings() -> Settings:
    return make_settings()


@pytest.fixture
def country_result() -> CountryResult:
    return make_country_result()


@pytest.fixture
def make_result() -> Callable[..., CountryResult]:
    return make_country_result


@pytest.fixture
def scan_summary() -> ScanSummary:
    return make_scan_summary()


@pytest.fixture
def make_summary() -> Callable[..., ScanSummary]:
    return make_scan_summary


@pytest.fixture(params=["memory", "dynamodb"])
def repository(request: pytest.FixtureRequest) -> ScanRepository:
    """`ScanRepository` の全実装。契約テストはこれを使う。"""
    if request.param == "memory":
        return InMemoryScanRepository()
    return make_dynamodb_repository(FakeDynamoDbTable())
