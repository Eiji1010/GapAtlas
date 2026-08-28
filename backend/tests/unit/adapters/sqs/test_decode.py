"""`decode_job` / `decode_records` のテスト。

壊れた本文はリトライしても直らない。呼び出し側が捨てられるよう
`JobDecodeError` になること、そして黙って読み飛ばさないことを確認する。
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

from gapatlas.adapters.sqs.decode import decode_job, decode_records
from gapatlas.adapters.sqs.errors import JobDecodeError
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


def _record(job: ScanJob, message_id: str = "m1") -> dict[str, str]:
    return {"messageId": message_id, "body": job.model_dump_json()}


# --- decode_job ---------------------------------------------------------------------------


def test_a_job_round_trips():
    job = _job()
    assert decode_job(job.model_dump_json()) == job


def test_the_scan_time_keeps_its_timezone():
    """国ごとに基準時刻がぶれると結果を再現できない(`jobs.py`)。"""
    assert decode_job(_job().model_dump_json()).scan_time == SCAN_TIME


def test_broken_json_raises():
    with pytest.raises(JobDecodeError):
        decode_job("{not json")


def test_an_empty_body_raises():
    with pytest.raises(JobDecodeError):
        decode_job("")


def test_a_missing_field_raises():
    with pytest.raises(JobDecodeError):
        decode_job('{"scan_id": "s", "topic_id": "elder_care", "country": "JP"}')


def test_an_unknown_field_raises():
    """契約がずれたまま動き続けるより DLQ で気付くほうがよい。"""
    payload = _job().model_dump(mode="json") | {"unexpected": 1}
    with pytest.raises(JobDecodeError):
        decode_job(_dumps(payload))


def test_an_empty_countries_list_raises():
    """最後の1国を判定できないジョブを受け付けない。"""
    payload = _job().model_dump(mode="json") | {"countries": []}
    with pytest.raises(JobDecodeError):
        decode_job(_dumps(payload))


def test_the_error_message_does_not_contain_the_body():
    """本文を例外へ載せない(docs/architecture.md「Security」)。"""
    payload = _job().model_dump(mode="json") | {"scan_id": ""}
    body = _dumps(payload)
    with pytest.raises(JobDecodeError) as exc_info:
        decode_job(body)
    assert body not in str(exc_info.value)
    assert "scan_test" not in str(exc_info.value)


def test_the_error_message_names_the_offending_field():
    payload = _job().model_dump(mode="json") | {"scan_id": ""}
    with pytest.raises(JobDecodeError, match="scan_id"):
        decode_job(_dumps(payload))


# --- decode_records -----------------------------------------------------------------------


def test_records_are_decoded_with_their_message_ids():
    jobs = [_job(Country.JP), _job(Country.US)]
    event = {"Records": [_record(jobs[0], "m1"), _record(jobs[1], "m2")]}
    assert decode_records(event) == [("m1", jobs[0]), ("m2", jobs[1])]


def test_an_empty_records_list_is_allowed():
    """形として正しい入力を例外にはしない。"""
    assert decode_records({"Records": []}) == []


def test_a_missing_records_key_raises():
    """トリガの誤配線を成功として記録しない。"""
    with pytest.raises(JobDecodeError, match="Records"):
        decode_records({"body": "{}"})


def test_records_that_are_not_a_list_raise():
    with pytest.raises(JobDecodeError, match="Records"):
        decode_records({"Records": {"messageId": "m1", "body": "{}"}})


def test_a_record_that_is_not_an_object_raises():
    with pytest.raises(JobDecodeError):
        decode_records({"Records": ["not an object"]})


def test_a_record_without_a_message_id_raises():
    with pytest.raises(JobDecodeError, match="messageId"):
        decode_records({"Records": [{"body": _job().model_dump_json()}]})


def test_a_record_with_a_non_string_body_raises():
    with pytest.raises(JobDecodeError, match="body"):
        decode_records({"Records": [{"messageId": "m1", "body": {"scan_id": "s"}}]})


def test_one_broken_record_fails_the_whole_batch():
    """壊れた1件を黙って読み飛ばさない。MVP は `batchSize = 1` を前提とする。"""
    event = {"Records": [_record(_job(), "m1"), {"messageId": "m2", "body": "{not json"}]}
    with pytest.raises(JobDecodeError, match="m2"):
        decode_records(event)


def _dumps(payload: dict[str, object]) -> str:
    return json.dumps(payload)
