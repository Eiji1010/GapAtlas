"""`api_handler` のテスト。ルーティング、エラー表、CORS、ログ。

**実 AWS へは接続しない。** `build_service` を差し替えてインメモリ実装だけを使う。
"""

from __future__ import annotations

import base64
import json
import logging
from datetime import UTC, datetime
from io import StringIO

import pytest
from conftest import (
    ALLOWED_ORIGIN,
    OTHER_ORIGIN,
    SCAN_ID,
    ExplodingRepository,
    make_country_result,
    make_event,
    make_scan_summary,
    make_settings,
    response_body,
)

from gapatlas.adapters.dynamodb.memory import InMemoryScanRepository
from gapatlas.adapters.sqs.memory import InMemoryJobQueue
from gapatlas.api import lambda_handlers
from gapatlas.api.errors import INTERNAL_ERROR_MESSAGE
from gapatlas.api.handlers import ApiService
from gapatlas.api.http import ALLOW_ORIGIN_HEADER
from gapatlas.application.logging_context import configure_logging
from gapatlas.domain.models.common import Country


class FakeLambdaContext:
    """Lambda コンテキストの最小形。相関 ID をログへ載せるためだけに使う。"""

    aws_request_id = "req-1"


@pytest.fixture(autouse=True)
def _reset_service_cache():
    """テスト間で `get_service` のキャッシュを持ち越さない。"""
    lambda_handlers.get_service.cache_clear()
    yield
    lambda_handlers.get_service.cache_clear()


@pytest.fixture
def installed(monkeypatch, repository: InMemoryScanRepository, queue: InMemoryJobQueue):
    """インメモリ依存の `ApiService` を `api_handler` へ差し込む。"""
    service = ApiService(repository, queue, make_settings())
    monkeypatch.setattr(lambda_handlers, "build_service", lambda: service)
    return service


def invoke(event):
    return lambda_handlers.api_handler(event, FakeLambdaContext())


# --- ルーティング(正常系) ---------------------------------------------------------------


def test_get_topics_returns_200(installed):
    response = invoke(make_event("GET", "/api/v1/topics"))

    assert response["statusCode"] == 200
    assert response_body(response)["topics"][0]["topic_id"] == "elder_care"


def test_post_scans_returns_202(installed, queue: InMemoryJobQueue):
    response = invoke(
        make_event("POST", "/api/v1/scans", body=json.dumps({"topic_id": "elder_care"}))
    )

    assert response["statusCode"] == 202
    body = response_body(response)
    assert body["status"] == "processing"
    assert body["scan_id"].startswith("scan_")
    assert len(queue.jobs) == 5


def test_post_scans_uses_one_generated_scan_id_for_every_job(installed, queue: InMemoryJobQueue):
    response = invoke(
        make_event("POST", "/api/v1/scans", body=json.dumps({"topic_id": "elder_care"}))
    )

    assert {job.scan_id for job in queue.jobs} == {response_body(response)["scan_id"]}
    assert len({job.scan_time for job in queue.jobs}) == 1


def test_post_scans_generates_a_new_scan_id_each_time(installed):
    first = response_body(
        invoke(make_event("POST", "/api/v1/scans", body=json.dumps({"topic_id": "elder_care"})))
    )
    second = response_body(
        invoke(make_event("POST", "/api/v1/scans", body=json.dumps({"topic_id": "elder_care"})))
    )

    assert first["scan_id"] != second["scan_id"]


def test_get_scan_returns_200(installed, repository: InMemoryScanRepository):
    repository.save_scan(make_scan_summary())

    response = invoke(make_event("GET", f"/api/v1/scans/{SCAN_ID}"))

    assert response["statusCode"] == 200
    assert response_body(response)["scan_id"] == SCAN_ID


def test_get_country_returns_200(installed, repository: InMemoryScanRepository):
    repository.save_country(make_country_result(Country.JP))

    response = invoke(make_event("GET", f"/api/v1/scans/{SCAN_ID}/countries/JP"))

    assert response["statusCode"] == 200
    assert response_body(response)["country"] == "JP"


def test_the_stage_prefix_is_tolerated(installed):
    """`$default` 以外のステージでは `/prod/api/v1/...` が届く。"""
    response = invoke(make_event("GET", "/prod/api/v1/topics"))

    assert response["statusCode"] == 200


def test_a_trailing_slash_is_tolerated(installed):
    assert invoke(make_event("GET", "/api/v1/topics/"))["statusCode"] == 200


# --- ルーティング(異常系) ---------------------------------------------------------------


@pytest.mark.parametrize(
    "path",
    [
        pytest.param("/api/v1/unknown", id="unknown resource"),
        pytest.param("/api/v1", id="base path only"),
        pytest.param("/healthz", id="outside the base path"),
        pytest.param("/api/v2/topics", id="unknown version"),
        pytest.param("/api/v1/scans/s1/countries/JP/extra", id="too many segments"),
    ],
)
def test_an_unknown_path_returns_404(installed, path):
    response = invoke(make_event("GET", path))

    assert response["statusCode"] == 404
    assert response_body(response)["error"]["code"] == "ROUTE_NOT_FOUND"


@pytest.mark.parametrize(
    ("method", "path"),
    [
        pytest.param("POST", "/api/v1/topics", id="post topics"),
        pytest.param("GET", "/api/v1/scans", id="get scans"),
        pytest.param("DELETE", "/api/v1/scans/scan_abc123", id="delete a scan"),
        pytest.param("PUT", "/api/v1/scans/scan_abc123/countries/JP", id="put a country"),
    ],
)
def test_an_unknown_method_returns_405(installed, method, path):
    response = invoke(make_event(method, path))

    assert response["statusCode"] == 405
    assert response_body(response)["error"]["code"] == "METHOD_NOT_ALLOWED"
    assert "Allow" in response["headers"]


def test_the_requested_path_is_not_echoed_in_the_404_body(installed):
    response = invoke(make_event("GET", "/api/v1/<script>alert(1)</script>"))

    assert "script" not in response["body"]


# --- docs/api.md のエラー表 --------------------------------------------------------------


def test_an_invalid_topic_returns_400(installed):
    response = invoke(
        make_event("POST", "/api/v1/scans", body=json.dumps({"topic_id": "childcare"}))
    )

    assert response["statusCode"] == 400
    assert response_body(response)["error"]["code"] == "INVALID_REQUEST"


def test_an_invalid_country_returns_400(installed):
    response = invoke(
        make_event(
            "POST",
            "/api/v1/scans",
            body=json.dumps({"topic_id": "elder_care", "countries": ["ZZ"]}),
        )
    )

    assert response["statusCode"] == 400
    assert response_body(response)["error"]["code"] == "INVALID_REQUEST"


def test_an_unknown_country_in_the_path_returns_400(installed):
    response = invoke(make_event("GET", f"/api/v1/scans/{SCAN_ID}/countries/ZZ"))

    assert response["statusCode"] == 400
    assert response_body(response)["error"]["code"] == "INVALID_REQUEST"


def test_a_missing_scan_returns_404_scan_not_found(installed):
    response = invoke(make_event("GET", "/api/v1/scans/scan_missing"))

    assert response["statusCode"] == 404
    assert response_body(response)["error"]["code"] == "SCAN_NOT_FOUND"


def test_a_missing_country_returns_404_country_not_found(
    installed, repository: InMemoryScanRepository
):
    repository.save_scan(make_scan_summary())

    response = invoke(make_event("GET", f"/api/v1/scans/{SCAN_ID}/countries/DE"))

    assert response["statusCode"] == 404
    assert response_body(response)["error"]["code"] == "COUNTRY_NOT_FOUND"


def test_an_unexpected_exception_returns_500(monkeypatch, queue: InMemoryJobQueue):
    service = ApiService(ExplodingRepository(), queue, make_settings())
    monkeypatch.setattr(lambda_handlers, "build_service", lambda: service)

    response = invoke(make_event("GET", f"/api/v1/scans/{SCAN_ID}"))

    assert response["statusCode"] == 500
    assert response_body(response)["error"]["code"] == "INTERNAL_ERROR"


def test_the_500_body_hides_the_traceback(monkeypatch, queue: InMemoryJobQueue):
    """内部構造をレスポンスへ露出させない(docs/requirements.md Security)。"""
    service = ApiService(ExplodingRepository(), queue, make_settings())
    monkeypatch.setattr(lambda_handlers, "build_service", lambda: service)

    response = invoke(make_event("GET", f"/api/v1/scans/{SCAN_ID}"))
    body = response["body"]

    assert response_body(response)["error"]["message"] == INTERNAL_ERROR_MESSAGE
    assert ExplodingRepository.LEAK_MARKER not in body
    assert "Traceback" not in body
    assert "RuntimeError" not in body
    assert "gapatlas" not in body


def test_a_failing_service_build_returns_500(monkeypatch):
    """設定の読み込みに失敗しても素の例外を漏らさない。"""

    def explode():
        message = "SERPAPI_API_KEY is required"
        raise RuntimeError(message)

    monkeypatch.setattr(lambda_handlers, "build_service", explode)

    response = invoke(make_event("GET", "/api/v1/topics"))

    assert response["statusCode"] == 500
    assert "SERPAPI_API_KEY" not in response["body"]


# --- 本文の異常 -------------------------------------------------------------------------


@pytest.mark.parametrize(
    "body",
    [
        pytest.param(None, id="no body"),
        pytest.param("", id="empty body"),
        pytest.param("{not json", id="broken json"),
        pytest.param("[]", id="json array"),
    ],
)
def test_a_malformed_body_returns_400(installed, queue: InMemoryJobQueue, body):
    response = invoke(make_event("POST", "/api/v1/scans", body=body))

    assert response["statusCode"] == 400
    assert response_body(response)["error"]["code"] == "INVALID_REQUEST"
    assert queue.jobs == []


def test_a_base64_body_is_accepted(installed, queue: InMemoryJobQueue):
    raw = json.dumps({"topic_id": "elder_care", "countries": ["JP"]})
    event = make_event(
        "POST",
        "/api/v1/scans",
        body=base64.b64encode(raw.encode()).decode(),
        is_base64_encoded=True,
    )

    assert invoke(event)["statusCode"] == 202
    assert [job.country for job in queue.jobs] == [Country.JP]


# --- パストラバーサル -------------------------------------------------------------------


@pytest.mark.parametrize(
    "scan_id",
    [
        pytest.param("..", id="parent"),
        pytest.param("%2e%2e", id="encoded parent"),
        pytest.param("scan_..etc", id="dots inside"),
    ],
)
def test_a_traversal_like_scan_id_is_a_clean_404(installed, scan_id):
    response = invoke(make_event("GET", f"/api/v1/scans/{scan_id}"))

    assert response["statusCode"] == 404
    assert response_body(response)["error"]["code"] == "SCAN_NOT_FOUND"


def test_a_traversal_path_never_reaches_the_repository(monkeypatch, queue: InMemoryJobQueue):
    service = ApiService(ExplodingRepository(), queue, make_settings())
    monkeypatch.setattr(lambda_handlers, "build_service", lambda: service)

    response = invoke(make_event("GET", "/api/v1/scans/..%2f..%2fetc%2fpasswd"))

    assert response["statusCode"] == 404


# --- CORS -------------------------------------------------------------------------------


def test_an_allowed_origin_gets_the_cors_header(installed):
    response = invoke(make_event("GET", "/api/v1/topics", headers={"Origin": ALLOWED_ORIGIN}))

    assert response["headers"][ALLOW_ORIGIN_HEADER] == ALLOWED_ORIGIN


def test_a_disallowed_origin_gets_no_cors_header(installed):
    response = invoke(make_event("GET", "/api/v1/topics", headers={"Origin": OTHER_ORIGIN}))

    assert ALLOW_ORIGIN_HEADER not in response["headers"]
    assert response["statusCode"] == 200


def test_no_response_ever_carries_a_wildcard_origin(monkeypatch, repository, queue):
    """設定が `*` でもワイルドカードを返さない。"""
    service = ApiService(repository, queue, make_settings(cors_allowed_origins=["*"]))
    monkeypatch.setattr(lambda_handlers, "build_service", lambda: service)

    response = invoke(make_event("GET", "/api/v1/topics", headers={"Origin": OTHER_ORIGIN}))

    assert response["headers"].get(ALLOW_ORIGIN_HEADER) != "*"


def test_error_responses_carry_the_cors_header(installed):
    """CORS ヘッダが無いとブラウザがエラーコードを読めない。"""
    response = invoke(
        make_event("GET", "/api/v1/scans/scan_missing", headers={"Origin": ALLOWED_ORIGIN})
    )

    assert response["statusCode"] == 404
    assert response["headers"][ALLOW_ORIGIN_HEADER] == ALLOWED_ORIGIN


def test_the_500_response_carries_the_cors_header(monkeypatch, queue: InMemoryJobQueue):
    service = ApiService(ExplodingRepository(), queue, make_settings())
    monkeypatch.setattr(lambda_handlers, "build_service", lambda: service)

    response = invoke(
        make_event("GET", f"/api/v1/scans/{SCAN_ID}", headers={"Origin": ALLOWED_ORIGIN})
    )

    assert response["statusCode"] == 500
    assert response["headers"][ALLOW_ORIGIN_HEADER] == ALLOWED_ORIGIN


def test_a_preflight_is_answered_without_routing(installed):
    response = invoke(make_event("OPTIONS", "/api/v1/scans", headers={"Origin": ALLOWED_ORIGIN}))

    assert response["statusCode"] == 204
    assert response["headers"][ALLOW_ORIGIN_HEADER] == ALLOWED_ORIGIN
    assert "Access-Control-Allow-Methods" in response["headers"]


def test_a_preflight_for_an_unknown_path_is_still_204(installed):
    response = invoke(make_event("OPTIONS", "/api/v1/unknown", headers={"Origin": ALLOWED_ORIGIN}))

    assert response["statusCode"] == 204


def test_a_preflight_from_a_disallowed_origin_gets_no_cors_header(installed):
    response = invoke(make_event("OPTIONS", "/api/v1/scans", headers={"Origin": OTHER_ORIGIN}))

    assert ALLOW_ORIGIN_HEADER not in response["headers"]


# --- ログ -------------------------------------------------------------------------------


@pytest.fixture
def log_stream():
    """構造化ログを捕まえる。テスト後にログ設定を元へ戻す。"""
    stream = StringIO()
    configure_logging("INFO", stream=stream)
    yield stream
    for handler in list(logging.getLogger().handlers):
        logging.getLogger().removeHandler(handler)


def _log_records(stream: StringIO) -> list[dict]:
    return [json.loads(line) for line in stream.getvalue().splitlines() if line]


def test_every_log_line_of_a_scan_lookup_carries_the_scan_id(
    installed, repository: InMemoryScanRepository, log_stream
):
    repository.save_scan(make_scan_summary())

    invoke(make_event("GET", f"/api/v1/scans/{SCAN_ID}"))

    records = _log_records(log_stream)
    assert records
    assert all(record["scan_id"] == SCAN_ID for record in records)


def test_the_created_scan_id_is_logged(installed, log_stream):
    response = invoke(
        make_event("POST", "/api/v1/scans", body=json.dumps({"topic_id": "elder_care"}))
    )

    scan_id = response_body(response)["scan_id"]
    records = _log_records(log_stream)
    assert records
    assert all(record["scan_id"] == scan_id for record in records)
    assert any(record["topic"] == "elder_care" for record in records)


def test_a_rejected_request_is_logged_with_its_scan_id(installed, log_stream):
    invoke(make_event("GET", "/api/v1/scans/scan_missing"))

    records = _log_records(log_stream)
    assert any(
        record["scan_id"] == "scan_missing" and record["code"] == "SCAN_NOT_FOUND"
        for record in records
    )


def test_the_traceback_stays_in_the_logs(monkeypatch, queue: InMemoryJobQueue, log_stream):
    """本文には出さないが、原因はログに残すこと。"""
    service = ApiService(ExplodingRepository(), queue, make_settings())
    monkeypatch.setattr(lambda_handlers, "build_service", lambda: service)

    invoke(make_event("GET", f"/api/v1/scans/{SCAN_ID}"))

    records = _log_records(log_stream)
    assert any(ExplodingRepository.LEAK_MARKER in record.get("exception", "") for record in records)


def test_the_lambda_request_id_is_logged(installed, log_stream):
    invoke(make_event("GET", "/api/v1/topics"))

    records = _log_records(log_stream)
    assert any(record.get("request_id") == FakeLambdaContext.aws_request_id for record in records)


# --- サービスの組み立て -----------------------------------------------------------------


def test_the_service_is_built_once_per_container(monkeypatch, repository, queue):
    calls: list[int] = []

    def build():
        calls.append(1)
        return ApiService(repository, queue, make_settings())

    monkeypatch.setattr(lambda_handlers, "build_service", build)

    invoke(make_event("GET", "/api/v1/topics"))
    invoke(make_event("GET", "/api/v1/topics"))

    assert len(calls) == 1


def test_build_service_uses_the_in_memory_defaults():
    """既定の `PERSISTENCE_MODE=memory` では AWS へ接続しない。"""
    service = lambda_handlers.build_service(make_settings())

    payload = service.create_scan(
        {"topic_id": "elder_care"},
        scan_id="scan_build",
        scan_time=datetime(2026, 8, 28, tzinfo=UTC),
    )

    assert payload["status"] == "processing"
