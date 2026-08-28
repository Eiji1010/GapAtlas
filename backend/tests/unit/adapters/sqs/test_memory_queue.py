"""インメモリ `JobQueue` と `ScanJob` の契約テスト。

**この振る舞いが `JobQueue` の契約**であり、SQS 実装も同じテストを満たすこと。
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from gapatlas.adapters.sqs.memory import InMemoryJobQueue
from gapatlas.application.jobs import ScanJob
from gapatlas.domain.models.common import Country, TopicId

SCAN_TIME = datetime(2026, 8, 28, tzinfo=UTC)


def _job(country: Country = Country.JP) -> ScanJob:
    return ScanJob(
        scan_id="scan_test",
        topic_id=TopicId.ELDER_CARE,
        country=country,
        scan_time=SCAN_TIME,
        countries=list(Country),
    )


def test_enqueue_keeps_order():
    queue = InMemoryJobQueue()
    queue.enqueue([_job(Country.JP), _job(Country.US)])
    assert [job.country for job in queue.jobs] == [Country.JP, Country.US]


def test_enqueue_appends():
    queue = InMemoryJobQueue()
    queue.enqueue([_job(Country.JP)])
    queue.enqueue([_job(Country.US)])
    assert len(queue.jobs) == 2


def test_drain_empties_the_queue():
    queue = InMemoryJobQueue()
    queue.enqueue([_job()])
    assert len(queue.drain()) == 1
    assert queue.drain() == []


def test_a_job_round_trips_through_json():
    """SQS メッセージ本文として往復できること。"""
    job = _job()
    restored = ScanJob.model_validate_json(job.model_dump_json())
    assert restored == job
    assert restored.scan_time == SCAN_TIME


def test_scan_time_must_be_timezone_aware():
    """naive datetime は弾く。国ごとに時刻の解釈がぶれないようにするため。"""
    with pytest.raises(ValidationError):
        ScanJob(
            scan_id="s",
            topic_id=TopicId.ELDER_CARE,
            country=Country.JP,
            scan_time=datetime(2026, 8, 28),
            countries=[Country.JP],
        )


def test_countries_must_not_be_empty():
    """最後の1国を判定できないジョブを作らせない。"""
    with pytest.raises(ValidationError):
        ScanJob(
            scan_id="s",
            topic_id=TopicId.ELDER_CARE,
            country=Country.JP,
            scan_time=SCAN_TIME,
            countries=[],
        )


def test_a_job_rejects_unknown_fields():
    with pytest.raises(ValidationError):
        ScanJob.model_validate(
            {
                "scan_id": "s",
                "topic_id": "elder_care",
                "country": "JP",
                "scan_time": "2026-08-28T00:00:00Z",
                "countries": ["JP"],
                "unexpected": 1,
            }
        )
