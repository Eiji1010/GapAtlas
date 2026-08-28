"""`SqsJobQueue` のテスト。

**実 AWS へ接続しない。** すべてフェイクの SQS クライアントを注入する。
契約そのものは `test_memory_queue.py` が定義しており、ここでは
バッチ投入・部分失敗・例外変換など**実装固有の振る舞い**だけを見る。
"""

from __future__ import annotations

import builtins
from datetime import UTC, datetime
from typing import Any

import pytest
from botocore.exceptions import ClientError, EndpointConnectionError

from gapatlas.adapters.sqs.client import MAX_BATCH_SIZE, SqsJobQueue
from gapatlas.adapters.sqs.errors import JobEnqueueError, JobQueueError
from gapatlas.application.jobs import ScanJob
from gapatlas.config.settings import Settings
from gapatlas.domain.models.common import Country, TopicId

SCAN_TIME = datetime(2026, 8, 28, tzinfo=UTC)
QUEUE_URL = "https://sqs.ap-northeast-1.amazonaws.com/000000000000/gapatlas-jobs"


def _settings(queue_url: str | None = QUEUE_URL) -> Settings:
    return Settings(sqs_queue_url=queue_url)


def _job(country: Country = Country.JP) -> ScanJob:
    return ScanJob(
        scan_id="scan_test",
        topic_id=TopicId.ELDER_CARE,
        country=country,
        scan_time=SCAN_TIME,
        countries=list(Country),
    )


class FakeSqsClient:
    """`send_message_batch` の呼び出しを記録するフェイク。"""

    def __init__(
        self, *, failed: list[dict[str, Any]] | None = None, error: Exception | None = None
    ) -> None:
        self.calls: list[dict[str, Any]] = []
        self._failed = failed or []
        self._error = error

    def send_message_batch(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(kwargs)
        if self._error is not None:
            raise self._error
        entries = kwargs["Entries"]
        failed_ids = {entry["Id"] for entry in self._failed}
        return {
            "Successful": [
                {"Id": entry["Id"]} for entry in entries if entry["Id"] not in failed_ids
            ],
            "Failed": self._failed,
        }


def _queue(client: FakeSqsClient, queue_url: str | None = QUEUE_URL) -> SqsJobQueue:
    return SqsJobQueue(_settings(queue_url), client=client)


# --- バッチ投入 ---------------------------------------------------------------------------


def test_five_countries_are_sent_in_a_single_batch():
    """5か国を1回の `send_message_batch` で投入する。

    1件ずつ送ると往復が国数だけ増え、`POST /scans` の SLO(p95 < 800ms)を
    外部 API のレイテンシで押し上げる。
    """
    client = FakeSqsClient()
    _queue(client).enqueue([_job(country) for country in Country])

    assert len(client.calls) == 1
    assert len(client.calls[0]["Entries"]) == len(list(Country))
    assert client.calls[0]["QueueUrl"] == QUEUE_URL


def test_message_bodies_round_trip_as_scan_jobs():
    client = FakeSqsClient()
    jobs = [_job(country) for country in Country]
    _queue(client).enqueue(jobs)

    bodies = [entry["MessageBody"] for entry in client.calls[0]["Entries"]]
    assert [ScanJob.model_validate_json(body) for body in bodies] == jobs


def test_batch_entry_ids_are_unique():
    client = FakeSqsClient()
    _queue(client).enqueue([_job(country) for country in Country])

    ids = [entry["Id"] for entry in client.calls[0]["Entries"]]
    assert len(set(ids)) == len(ids)


def test_more_than_ten_jobs_are_split_into_batches():
    """バッチ上限は 10 件。超えた分を無言で切り捨てない。"""
    client = FakeSqsClient()
    jobs = [_job(Country.JP) for _ in range(MAX_BATCH_SIZE + 3)]
    _queue(client).enqueue(jobs)

    assert [len(call["Entries"]) for call in client.calls] == [MAX_BATCH_SIZE, 3]
    all_ids = [entry["Id"] for call in client.calls for entry in call["Entries"]]
    assert len(set(all_ids)) == len(jobs)


def test_an_empty_sequence_sends_nothing():
    """`Entries` が空の `SendMessageBatch` は AWS が拒否するため呼ばない。"""
    client = FakeSqsClient()
    _queue(client).enqueue([])
    assert client.calls == []


# --- 失敗の扱い ---------------------------------------------------------------------------


def test_a_partial_failure_raises():
    """`Failed` が返ったら握りつぶさず例外にする。

    `send_message_batch` は部分失敗でも HTTP 200 を返す。見逃すと、投入できな
    かった国があることが誰にも伝わらない。
    """
    client = FakeSqsClient(failed=[{"Id": "1", "Code": "InternalError", "SenderFault": False}])
    with pytest.raises(JobEnqueueError):
        _queue(client).enqueue([_job(Country.JP), _job(Country.US)])


def test_a_partial_failure_names_the_country_and_the_code():
    client = FakeSqsClient(failed=[{"Id": "1", "Code": "InternalError", "SenderFault": False}])
    with pytest.raises(JobEnqueueError) as exc_info:
        _queue(client).enqueue([_job(Country.JP), _job(Country.US)])

    message = str(exc_info.value)
    assert "US" in message
    assert "InternalError" in message


def test_a_later_batch_failure_stops_the_remaining_batches():
    client = FakeSqsClient(failed=[{"Id": "0", "Code": "InternalError"}])
    with pytest.raises(JobEnqueueError):
        _queue(client).enqueue([_job(Country.JP) for _ in range(MAX_BATCH_SIZE + 3)])
    assert len(client.calls) == 1


def test_botocore_errors_become_job_enqueue_errors():
    client = FakeSqsClient(error=EndpointConnectionError(endpoint_url="https://sqs.invalid"))
    with pytest.raises(JobEnqueueError):
        _queue(client).enqueue([_job()])


def test_client_errors_become_job_enqueue_errors():
    error = ClientError(
        {"Error": {"Code": "AccessDenied", "Message": "denied"}}, "SendMessageBatch"
    )
    client = FakeSqsClient(error=error)
    with pytest.raises(JobEnqueueError):
        _queue(client).enqueue([_job()])


def test_implementation_bugs_are_not_converted():
    """`TypeError` などの実装バグは変換せず素通しする。

    `Exception` を丸ごと捕捉すると、バグまで「SQS の障害」に見えてしまう。
    """
    client = FakeSqsClient(error=TypeError("keyword mismatch"))
    with pytest.raises(TypeError):
        _queue(client).enqueue([_job()])


def test_attribute_errors_are_not_converted():
    client = FakeSqsClient(error=AttributeError("typo"))
    with pytest.raises(AttributeError):
        _queue(client).enqueue([_job()])


# --- 設定と依存 ---------------------------------------------------------------------------


def test_a_missing_queue_url_is_reported_clearly():
    """`SQS_QUEUE_URL` は既定値を持たない。未設定なら分かりやすく落とす。"""
    with pytest.raises(JobQueueError, match="SQS_QUEUE_URL"):
        SqsJobQueue(_settings(None), client=FakeSqsClient())


def test_a_missing_boto3_is_reported_clearly(monkeypatch: pytest.MonkeyPatch):
    """`boto3` が無ければ分かりやすい `JobQueueError` になること。"""
    real_import = builtins.__import__

    def fake_import(name: str, *args: Any, **kwargs: Any) -> Any:
        if name == "boto3" or name.startswith("boto3."):
            message = "No module named 'boto3'"
            raise ImportError(message)
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    with pytest.raises(JobQueueError, match="boto3"):
        SqsJobQueue(_settings())


# --- Security -----------------------------------------------------------------------------


def test_failure_messages_do_not_contain_the_message_body():
    """例外メッセージへ本文を載せない(docs/architecture.md「Security」)。"""
    job = _job(Country.JP)
    client = FakeSqsClient(failed=[{"Id": "0", "Code": "InternalError", "Message": job.scan_id}])
    with pytest.raises(JobEnqueueError) as exc_info:
        _queue(client).enqueue([job])

    message = str(exc_info.value)
    assert job.model_dump_json() not in message
    assert "scan_test" not in message
    assert "2026-08-28" not in message


def test_transport_failure_messages_do_not_contain_the_message_body():
    job = _job(Country.JP)
    client = FakeSqsClient(error=EndpointConnectionError(endpoint_url="https://sqs.invalid"))
    with pytest.raises(JobEnqueueError) as exc_info:
        _queue(client).enqueue([job])

    message = str(exc_info.value)
    assert job.model_dump_json() not in message
    assert "scan_test" not in message
