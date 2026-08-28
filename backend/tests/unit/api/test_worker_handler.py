"""Worker 用 Lambda ハンドラのテスト。

SQS の再配信・DLQ の挙動に直結するため、**どの失敗で例外を投げるか**を固定する。
"""

from __future__ import annotations

import io
import json
import logging
from datetime import UTC, datetime
from typing import Any

import pytest

from gapatlas.adapters.dynamodb.memory import InMemoryScanRepository
from gapatlas.adapters.llm.stub_client import StubLlmClient
from gapatlas.adapters.s3.memory import InMemoryScanArchive
from gapatlas.adapters.serpapi.fixture_client import FixtureSerpApiClient
from gapatlas.api import worker_handler as module
from gapatlas.application.country_scan import CountryScanner
from gapatlas.application.jobs import ScanJob
from gapatlas.application.logging_context import configure_logging
from gapatlas.application.worker import ScanWorker
from gapatlas.domain.models.common import Country, ScanStatus, TopicId

SCAN_ID = "scan_worker_handler"
SCAN_TIME = datetime(2026, 8, 28, tzinfo=UTC)


@pytest.fixture(autouse=True)
def _restore(monkeypatch: pytest.MonkeyPatch):
    """`lru_cache` とログ設定をテストごとに戻す。"""
    module.get_worker.cache_clear()
    root = logging.getLogger()
    handlers = list(root.handlers)
    level = root.level
    yield
    module.get_worker.cache_clear()
    for handler in list(root.handlers):
        root.removeHandler(handler)
    for handler in handlers:
        root.addHandler(handler)
    root.setLevel(level)


def _event(jobs: list[ScanJob]) -> dict[str, Any]:
    return {
        "Records": [
            {"messageId": f"m{index}", "body": job.model_dump_json()}
            for index, job in enumerate(jobs)
        ]
    }


def _job(country: Country) -> ScanJob:
    return ScanJob(
        scan_id=SCAN_ID,
        topic_id=TopicId.ELDER_CARE,
        country=country,
        scan_time=SCAN_TIME,
        countries=list(Country),
    )


def _install(monkeypatch: pytest.MonkeyPatch, repository=None, archive=None) -> ScanWorker:
    worker = ScanWorker(
        CountryScanner(FixtureSerpApiClient(), StubLlmClient()),
        repository or InMemoryScanRepository(),
        archive or InMemoryScanArchive(),
        StubLlmClient(),
    )
    monkeypatch.setattr(module, "build_worker", lambda settings=None: worker)
    module.get_worker.cache_clear()
    return worker


def test_a_single_job_is_processed(monkeypatch: pytest.MonkeyPatch):
    repository = InMemoryScanRepository()
    _install(monkeypatch, repository=repository)

    response = module.worker_handler(_event([_job(Country.JP)]), None)

    assert response == {"batchItemFailures": []}
    stored = repository.get_country(SCAN_ID, Country.JP)
    assert stored is not None
    assert stored.need_gap_score == 75


def test_all_five_countries_complete_the_scan(monkeypatch: pytest.MonkeyPatch):
    repository = InMemoryScanRepository()
    _install(monkeypatch, repository=repository)

    for country in Country:
        module.worker_handler(_event([_job(country)]), None)

    summary = repository.get_scan(SCAN_ID)
    assert summary is not None
    assert summary.status is ScanStatus.COMPLETED
    assert summary.ranking[0].country is Country.JP
    assert summary.opportunity_brief is not None


def test_an_undecodable_message_is_dropped_without_raising(monkeypatch: pytest.MonkeyPatch):
    """リトライしても直らないメッセージで DLQ を消費しない。"""
    _install(monkeypatch)
    event = {"Records": [{"messageId": "m0", "body": "{not json"}]}

    assert module.worker_handler(event, None) == {"batchItemFailures": []}


def test_an_event_without_records_is_dropped(monkeypatch: pytest.MonkeyPatch):
    _install(monkeypatch)
    assert module.worker_handler({}, None) == {"batchItemFailures": []}


def test_an_unexpected_worker_error_is_reraised(monkeypatch: pytest.MonkeyPatch):
    """実装バグは握らない。再配信と DLQ で可視化する。"""

    class ExplodingWorker:
        def handle(self, job: ScanJob) -> None:
            message = "worker bug"
            raise RuntimeError(message)

    monkeypatch.setattr(module, "build_worker", lambda settings=None: ExplodingWorker())
    module.get_worker.cache_clear()

    with pytest.raises(RuntimeError, match="worker bug"):
        module.worker_handler(_event([_job(Country.JP)]), None)


def test_logs_carry_the_scan_context(monkeypatch: pytest.MonkeyPatch):
    stream = io.StringIO()
    _install(monkeypatch)
    configure_logging("INFO", stream=stream)

    module.worker_handler(_event([_job(Country.JP)]), None)

    lines = [json.loads(line) for line in stream.getvalue().strip().splitlines() if line]
    processing = [line for line in lines if line["message"] == "processing a scan job"]
    assert processing
    assert processing[0]["scan_id"] == SCAN_ID
    assert processing[0]["country"] == "JP"
    assert processing[0]["topic"] == "elder_care"
