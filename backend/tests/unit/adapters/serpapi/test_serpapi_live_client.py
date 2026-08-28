"""`LiveSerpApiClient` のテスト。

API キー未取得のため実 API との結合は未検証(docs/decisions/0003-fixture-first.md)。
ここでは `httpx.MockTransport` を使い、**実際のネットワークへ一切出さずに**
リトライ方針とマスキングを検証する。`sleep` を注入するため実時間も消費しない。
"""

from __future__ import annotations

import httpx
import pytest
from pydantic import SecretStr

from gapatlas.adapters.serpapi.errors import (
    SerpApiError,
    SerpApiRequestError,
    SerpApiResponseError,
    SerpApiStatusError,
)
from gapatlas.adapters.serpapi.live_client import (
    RETRY_BASE_DELAY_SECONDS,
    SERPAPI_ENDPOINT,
    LiveSerpApiClient,
)
from gapatlas.adapters.serpapi.protocol import SerpApiClient
from gapatlas.config.settings import SerpApiMode, Settings
from gapatlas.domain.models.common import Country, SourceName
from gapatlas.domain.models.query_profile import QueryProfile

FAKE_API_KEY = "fake-serpapi-key-for-tests-only"
"""実在しないダミー値。実キーをテストデータへ書かない(AGENTS.md)。"""

SUCCESS_BODY = {"search_parameters": {"engine": "google"}, "organic_results": []}


class RecordingSleep:
    """バックオフの待機時間を記録するだけのスタブ。"""

    def __init__(self) -> None:
        self.delays: list[float] = []

    def __call__(self, seconds: float) -> None:
        self.delays.append(seconds)


def make_settings(*, max_retries: int = 2) -> Settings:
    return Settings(
        serpapi_mode=SerpApiMode.LIVE,
        serpapi_api_key=SecretStr(FAKE_API_KEY),
        serpapi_timeout_seconds=8.0,
        serpapi_max_retries=max_retries,
    )


def make_client(
    handler: object, *, max_retries: int = 2
) -> tuple[LiveSerpApiClient, RecordingSleep, list[httpx.Request]]:
    """MockTransport を積んだクライアントを組み立てる。"""
    requests: list[httpx.Request] = []

    def wrapped(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return handler(request)  # type: ignore[operator]

    sleep = RecordingSleep()
    transport = httpx.MockTransport(wrapped)
    client = LiveSerpApiClient(
        make_settings(max_retries=max_retries),
        client=httpx.Client(transport=transport),
        sleep=sleep,
    )
    return client, sleep, requests


def responder(*statuses: int) -> object:
    """呼ばれるたびに `statuses` を順に返し、最後の値を繰り返すハンドラ。"""
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        index = min(calls["n"], len(statuses) - 1)
        calls["n"] += 1
        status = statuses[index]
        body = SUCCESS_BODY if status == 200 else {"error": f"fixture error {status}"}
        return httpx.Response(status, json=body)

    return handler


def test_missing_api_key_is_rejected_at_construction() -> None:
    settings = Settings(serpapi_mode=SerpApiMode.FIXTURE, serpapi_api_key=None)

    with pytest.raises(SerpApiError):
        LiveSerpApiClient(settings)


def test_successful_request_returns_raw_payload(profiles: dict[Country, QueryProfile]) -> None:
    client, sleep, requests = make_client(responder(200))

    raw = client.fetch(SourceName.SEARCH, profiles[Country.JP])

    assert raw == SUCCESS_BODY
    assert sleep.delays == []
    assert len(requests) == 1
    assert str(requests[0].url).startswith(SERPAPI_ENDPOINT)


def test_request_carries_built_params_and_the_api_key(
    profiles: dict[Country, QueryProfile],
) -> None:
    client, _sleep, requests = make_client(responder(200))

    client.fetch(SourceName.NEWS, profiles[Country.DE])

    params = dict(requests[0].url.params)
    assert params["engine"] == "google_news"
    assert params["q"] == profiles[Country.DE].news_query[0]
    assert params["api_key"] == FAKE_API_KEY


@pytest.mark.parametrize("status", [429, 500, 503])
def test_retryable_statuses_are_retried_then_succeed(
    profiles: dict[Country, QueryProfile], status: int
) -> None:
    client, sleep, requests = make_client(responder(status, 200))

    raw = client.fetch(SourceName.SEARCH, profiles[Country.US])

    assert raw == SUCCESS_BODY
    assert len(requests) == 2
    assert sleep.delays == [RETRY_BASE_DELAY_SECONDS]


@pytest.mark.parametrize("status", [400, 401, 403, 404, 410])
def test_non_retryable_statuses_fail_immediately(
    profiles: dict[Country, QueryProfile], status: int
) -> None:
    client, sleep, requests = make_client(responder(status, 200))

    with pytest.raises(SerpApiStatusError) as excinfo:
        client.fetch(SourceName.SEARCH, profiles[Country.US])

    assert excinfo.value.status_code == status
    assert len(requests) == 1
    assert sleep.delays == []


def test_network_errors_are_retried(profiles: dict[Country, QueryProfile]) -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            raise httpx.ConnectError("connection refused", request=request)
        return httpx.Response(200, json=SUCCESS_BODY)

    client, sleep, requests = make_client(handler)

    assert client.fetch(SourceName.TRENDS, profiles[Country.GB]) == SUCCESS_BODY
    assert len(requests) == 2
    assert sleep.delays == [RETRY_BASE_DELAY_SECONDS]


def test_timeout_is_retried_and_finally_raises_request_error(
    profiles: dict[Country, QueryProfile],
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out", request=request)

    client, sleep, requests = make_client(handler)

    with pytest.raises(SerpApiRequestError):
        client.fetch(SourceName.TRENDS, profiles[Country.GB])

    assert len(requests) == 3
    assert sleep.delays == [0.5, 1.0]


def test_retry_budget_is_exhausted_and_the_last_error_is_raised(
    profiles: dict[Country, QueryProfile],
) -> None:
    client, sleep, requests = make_client(responder(503))

    with pytest.raises(SerpApiError) as excinfo:
        client.fetch(SourceName.SEARCH, profiles[Country.IN])

    assert isinstance(excinfo.value, SerpApiStatusError)
    assert excinfo.value.status_code == 503
    assert len(requests) == 3  # 初回 + リトライ2回
    assert sleep.delays == [0.5, 1.0]


def test_backoff_is_exponential(profiles: dict[Country, QueryProfile]) -> None:
    """遅延は base * 2**attempt の順に `sleep` へ渡される。"""
    client, sleep, requests = make_client(responder(500), max_retries=4)

    with pytest.raises(SerpApiStatusError):
        client.fetch(SourceName.SEARCH, profiles[Country.JP])

    assert len(requests) == 5
    assert sleep.delays == [0.5, 1.0, 2.0, 4.0]


def test_zero_retries_means_a_single_attempt(profiles: dict[Country, QueryProfile]) -> None:
    client, sleep, requests = make_client(responder(500), max_retries=0)

    with pytest.raises(SerpApiStatusError):
        client.fetch(SourceName.SEARCH, profiles[Country.JP])

    assert len(requests) == 1
    assert sleep.delays == []


def test_error_payload_on_http_200_is_not_retried(
    profiles: dict[Country, QueryProfile],
) -> None:
    """200 でも本文に `{"error": ...}` があれば失敗させる。リトライしない。"""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"error": "Invalid API key."})

    client, sleep, requests = make_client(handler)

    with pytest.raises(SerpApiResponseError):
        client.fetch(SourceName.SEARCH, profiles[Country.JP])

    assert len(requests) == 1
    assert sleep.delays == []


def test_non_json_body_raises_response_error(profiles: dict[Country, QueryProfile]) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="<html>gateway</html>")

    client, _sleep, requests = make_client(handler)

    with pytest.raises(SerpApiResponseError):
        client.fetch(SourceName.SEARCH, profiles[Country.JP])

    assert len(requests) == 1


def test_non_object_json_body_raises_response_error(
    profiles: dict[Country, QueryProfile],
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[1, 2, 3])

    client, _sleep, _requests = make_client(handler)

    with pytest.raises(SerpApiResponseError):
        client.fetch(SourceName.SEARCH, profiles[Country.JP])


@pytest.mark.parametrize("status", [400, 401, 429, 500])
def test_api_key_never_appears_in_exceptions(
    profiles: dict[Country, QueryProfile], status: int
) -> None:
    """例外メッセージにも repr にも API キーを出さない(AGENTS.md 禁止事項)。"""
    client, _sleep, _requests = make_client(responder(status), max_retries=0)

    with pytest.raises(SerpApiError) as excinfo:
        client.fetch(SourceName.SEARCH, profiles[Country.JP])

    error = excinfo.value
    assert FAKE_API_KEY not in str(error)
    assert FAKE_API_KEY not in repr(error)
    assert "api_key=***" in str(error)


def test_api_key_never_appears_in_network_error_messages(
    profiles: dict[Country, QueryProfile],
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError(f"failed to reach {request.url}", request=request)

    client, _sleep, _requests = make_client(handler, max_retries=0)

    with pytest.raises(SerpApiRequestError) as excinfo:
        client.fetch(SourceName.SEARCH, profiles[Country.JP])

    assert FAKE_API_KEY not in str(excinfo.value)
    assert FAKE_API_KEY not in repr(excinfo.value)


def test_live_client_satisfies_the_protocol() -> None:
    client: SerpApiClient = LiveSerpApiClient(make_settings())

    assert callable(client.fetch)
