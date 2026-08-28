"""api 層のテストで共有する fixture とヘルパ。

テストは決定的にする。`scan_id` と `scan_time` は必ず明示的に渡す。
**実 AWS へは接続しない。** リポジトリとキューはインメモリ実装のみを使う。
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

import pytest

from gapatlas.adapters.dynamodb.memory import InMemoryScanRepository
from gapatlas.adapters.sqs.memory import InMemoryJobQueue
from gapatlas.api.handlers import ApiService
from gapatlas.config.settings import Settings
from gapatlas.domain.models.common import (
    Country,
    CountryStatus,
    ScanStatus,
    SourceName,
    SourceStatus,
    TopicId,
)
from gapatlas.domain.models.result import (
    CountryResult,
    Evidence,
    RankingEntry,
    ScanProgress,
    ScanSummary,
    Versions,
)
from gapatlas.domain.models.scores import ConfidenceBreakdown, ScoreComponents

SCAN_ID = "scan_abc123"
SCAN_TIME = datetime(2026, 8, 28, tzinfo=UTC)
"""スキャン全体の基準時刻。fixture の基準日に合わせた固定値。"""

ALLOWED_ORIGIN = "https://gapatlas.example"
OTHER_ORIGIN = "https://evil.example"

VERSIONS = Versions(
    query_profile_version="elder-care-jp-v2",
    score_version="gapatlas-score-v1",
    classifier_version="gapatlas-classifier-v1-stub",
    prompt_version="gapatlas-prompt-v1-stub",
)


def make_settings(**overrides: Any) -> Settings:
    """テスト用の `Settings`。既定は fixture / stub / memory モードのまま。"""
    values: dict[str, Any] = {"cors_allowed_origins": [ALLOWED_ORIGIN]}
    values.update(overrides)
    return Settings(**values)


def make_country_result(
    country: Country = Country.JP,
    *,
    scan_id: str = SCAN_ID,
    status: CountryStatus = CountryStatus.COMPLETED,
    score: int | None = 86,
) -> CountryResult:
    """docs/api.md の国別レスポンス例に近い `CountryResult`。"""
    return CountryResult(
        scan_id=scan_id,
        topic_id=TopicId.ELDER_CARE,
        country=country,
        status=status,
        need_gap_score=score,
        confidence=92,
        components=ScoreComponents(demand=91.4, pain=83.5, solution_gap=78.0, news_urgency=82.6),
        confidence_breakdown=ConfidenceBreakdown(
            data_completeness=100.0,
            sample_sufficiency=94.5,
            localization_quality=100.0,
            source_agreement=88.0,
            freshness=92.0,
        ),
        source_status={
            SourceName.TRENDS: SourceStatus.OK,
            SourceName.RELATED_QUERIES: SourceStatus.OK,
            SourceName.SEARCH: SourceStatus.OK,
            SourceName.NEWS: SourceStatus.OK,
            SourceName.MAPS: SourceStatus.NOT_REQUESTED,
        },
        evidence=[
            Evidence(
                id="E1",
                source=SourceName.TRENDS,
                summary="直近4週の平均が前8週比で上昇",
                url=None,
            )
        ],
        versions=VERSIONS,
        computed_at=SCAN_TIME,
    )


def make_scan_summary(
    scan_id: str = SCAN_ID,
    *,
    status: ScanStatus = ScanStatus.PROCESSING,
    total: int = 5,
    completed: int = 0,
) -> ScanSummary:
    """保存済みの `ScanSummary`。既定は `POST /scans` 直後の状態。"""
    return ScanSummary(
        scan_id=scan_id,
        topic_id=TopicId.ELDER_CARE,
        status=status,
        progress=ScanProgress(total=total, completed=completed),
        completed_countries=[],
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
            )
        ],
        versions=VERSIONS,
    )


class ExplodingRepository:
    """すべての読み取りで想定外の例外を投げるリポジトリ。500 の確認に使う。"""

    LEAK_MARKER = "internal-detail-that-must-not-leak"
    """本文へ現れてはいけない目印。"""

    def save_scan(self, summary: ScanSummary) -> None:
        raise RuntimeError(self.LEAK_MARKER)

    def save_country(self, result: CountryResult) -> None:
        raise RuntimeError(self.LEAK_MARKER)

    def get_scan(self, scan_id: str) -> ScanSummary | None:
        raise RuntimeError(self.LEAK_MARKER)

    def get_country(self, scan_id: str, country: Country) -> CountryResult | None:
        raise RuntimeError(self.LEAK_MARKER)

    def list_countries(self, scan_id: str) -> list[CountryResult]:
        raise RuntimeError(self.LEAK_MARKER)


@pytest.fixture
def repository() -> InMemoryScanRepository:
    return InMemoryScanRepository()


@pytest.fixture
def queue() -> InMemoryJobQueue:
    return InMemoryJobQueue()


@pytest.fixture
def settings() -> Settings:
    return make_settings()


@pytest.fixture
def service(
    repository: InMemoryScanRepository, queue: InMemoryJobQueue, settings: Settings
) -> ApiService:
    return ApiService(repository, queue, settings)


def make_event(
    method: str = "GET",
    path: str = "/api/v1/topics",
    *,
    body: str | None = None,
    headers: Mapping[str, str] | None = None,
    is_base64_encoded: bool = False,
    query: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """API Gateway HTTP API(payload format version 2.0)の最小イベント。"""
    return {
        "version": "2.0",
        "rawPath": path,
        "rawQueryString": "",
        "headers": dict(headers or {}),
        "queryStringParameters": dict(query) if query else None,
        "requestContext": {"http": {"method": method, "path": path}},
        "body": body,
        "isBase64Encoded": is_base64_encoded,
    }


def response_body(response: Mapping[str, Any]) -> Any:
    """レスポンス本文を JSON として読む。"""
    return json.loads(response["body"])
