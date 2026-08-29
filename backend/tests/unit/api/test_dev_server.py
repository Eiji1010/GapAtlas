"""ローカル開発用サーバー(`gapatlas serve`)の検証。

ここが守るのは**フロントエンドと繋がること**である。`VITE_API_MODE=live`
で叩く相手がこのサーバーなので、API Gateway HTTP API v2.0 のイベント形が
ずれると「ローカルでは動くが Lambda では動かない」(あるいはその逆)に
なる。実際に TCP ソケットを開いて HTTP で往復させる。
"""

from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from collections.abc import Iterator
from datetime import UTC, datetime

import pytest

from gapatlas.api import dev_server
from gapatlas.application.jobs import ScanJob
from gapatlas.config.settings import Settings
from gapatlas.domain.models.common import Country, TopicId

SCAN_TIME = datetime(2026, 8, 28, tzinfo=UTC)
"""fixture の基準日(backend/tests/fixtures/README.md)。"""


class _FakeHeaders(dict[str, str]):
    def items(self):  # type: ignore[override]
        return super().items()


class _FakeHandler:
    """`_to_event` が読む属性だけを持つ最小の代役。"""

    def __init__(self, path: str, headers: dict[str, str]) -> None:
        self.path = path
        self.headers = _FakeHeaders(headers)


def test_the_event_matches_the_api_gateway_v2_shape() -> None:
    handler = _FakeHandler("/api/v1/scans?limit=5&topic=elder_care", {"Content-Type": "app/json"})
    event = dev_server._to_event(handler, "POST", '{"topic_id":"elder_care"}')  # type: ignore[arg-type]

    assert event["version"] == "2.0"
    assert event["rawPath"] == "/api/v1/scans"
    assert event["rawQueryString"] == "limit=5&topic=elder_care"
    assert event["queryStringParameters"] == {"limit": "5", "topic": "elder_care"}
    # ヘッダ名は小文字で渡す(API Gateway HTTP API v2.0 の仕様)。
    assert event["headers"] == {"content-type": "app/json"}
    assert event["isBase64Encoded"] is False
    assert event["requestContext"]["http"] == {"method": "POST", "path": "/api/v1/scans"}


def test_the_query_string_is_empty_when_there_is_none() -> None:
    event = dev_server._to_event(_FakeHandler("/api/v1/scans/abc", {}), "GET", None)  # type: ignore[arg-type]

    assert event["rawQueryString"] == ""
    assert event["queryStringParameters"] == {}
    assert event["body"] is None


def _job(country: Country) -> ScanJob:
    return ScanJob(
        scan_id="s1",
        topic_id=TopicId("elder_care"),
        country=country,
        scan_time=SCAN_TIME,
        countries=[Country.JP, Country.US],
    )


def test_the_queue_hands_jobs_to_the_worker_one_at_a_time() -> None:
    jobs = dev_server._DispatchingQueue()
    first = _job(Country.JP)
    second = _job(Country.US)

    jobs.enqueue([first, second])

    assert jobs.enqueued == [first, second]
    assert jobs.take(timeout=0.1) == first
    assert jobs.take(timeout=0.1) == second
    # 空になったら待って None を返す(スレッドを回し続けるため)。
    assert jobs.take(timeout=0.01) is None


class _ExplodingWorker:
    def __init__(self) -> None:
        self.seen: list[ScanJob] = []

    def handle(self, job: ScanJob) -> None:
        self.seen.append(job)
        raise RuntimeError("boom")


def test_the_worker_thread_survives_a_failing_job() -> None:
    """1件の失敗でスレッドが死ぬと、以降の国が**無言で処理されなくなる**。"""
    jobs = dev_server._DispatchingQueue()
    worker = _ExplodingWorker()
    stop = threading.Event()
    thread = threading.Thread(
        target=lambda: dev_server._run_worker(worker, jobs, stop),  # type: ignore[arg-type]
        daemon=True,
    )
    thread.start()
    try:
        jobs.enqueue([_job(country) for country in (Country.JP, Country.US)])
        deadline = threading.Event()
        for _ in range(200):
            if len(worker.seen) == 2:
                break
            deadline.wait(0.02)
    finally:
        stop.set()
        thread.join(timeout=2)

    assert [job.country for job in worker.seen] == [Country.JP, Country.US]
    assert not thread.is_alive()


@pytest.fixture
def running_server() -> Iterator[str]:
    """実際にサーバーを起動して、その URL を返す。"""
    server, stop = dev_server.create_server(Settings(), host="127.0.0.1", port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}/api/v1"
    finally:
        stop.set()
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def _request(url: str, *, method: str = "GET", payload: dict[str, object] | None = None):
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(  # noqa: S310 - 自分で立てた localhost のみ
        url,
        data=data,
        method=method,
        headers={"Content-Type": "application/json", "Origin": "http://localhost:5173"},
    )
    with urllib.request.urlopen(request, timeout=15) as response:  # noqa: S310
        return response.status, dict(response.headers), response.read().decode("utf-8")


def test_a_scan_runs_from_end_to_end_over_http(running_server: str) -> None:
    status, _headers, body = _request(
        f"{running_server}/scans",
        method="POST",
        payload={"topic_id": "elder_care", "countries": ["JP"]},
    )
    assert status == 202
    scan_id = json.loads(body)["scan_id"]

    # ワーカースレッドが処理し終わるまで待つ(フロントの2秒 Polling と同じ)。
    summary: dict[str, object] = {}
    waiter = threading.Event()
    for _ in range(300):
        _status, _headers, body = _request(f"{running_server}/scans/{scan_id}")
        summary = json.loads(body)
        if summary["status"] != "processing":
            break
        waiter.wait(0.1)

    assert summary["status"] == "completed"
    assert summary["ranking"] == [
        {
            "country": "JP",
            "status": "completed",
            "need_gap_score": 75,
            "confidence": 91,
            "demand": 85,
            "pain": 73,
            "solution_gap": 65,
            "news_urgency": 63,
        }
    ]

    _status, _headers, body = _request(f"{running_server}/scans/{scan_id}/countries/JP")
    assert json.loads(body)["need_gap_score"] == 75


def test_the_browser_gets_cors_headers(running_server: str) -> None:
    """フロントは別オリジン(Vite の 5173)から叩くので、プリフライトが通ること。"""
    request = urllib.request.Request(  # noqa: S310 - 自分で立てた localhost のみ
        f"{running_server}/scans",
        method="OPTIONS",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    with urllib.request.urlopen(request, timeout=15) as response:  # noqa: S310
        assert response.status == 204
        allow_origin = response.headers.get("Access-Control-Allow-Origin")

    assert allow_origin in {"http://localhost:5173", "*"}


def test_a_missing_scan_is_a_404_with_the_documented_error_shape(running_server: str) -> None:
    with pytest.raises(urllib.error.HTTPError) as caught:
        _request(f"{running_server}/scans/scan_missing")

    assert caught.value.code == 404
    payload = json.loads(caught.value.read().decode("utf-8"))
    assert payload["error"]["code"] == "SCAN_NOT_FOUND"
