"""`SERPAPI_MODE=live` 用の SerpApi クライアント。

**API キーが未取得のため実 API との結合は未検証**
(docs/decisions/0003-fixture-first.md)。検証は httpx をモックした単体テストに
留まる。

リトライ方針は docs/architecture.md「Reliability」および
docs/serpapi-schema.md 6章に従う。**リトライ対象は 429 / 500 / 503 と
ネットワークエラーのみ。** その他の 4xx はリトライしない。

API キーはログにも例外メッセージにも出さない(docs/architecture.md
「Observability」)。URL を載せる場合は `mask_api_key` を通す。
"""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Callable
from typing import Any, Final, cast

import httpx

from gapatlas.adapters.serpapi.errors import (
    SerpApiError,
    SerpApiRequestError,
    SerpApiResponseError,
    SerpApiStatusError,
    mask_api_key,
    raise_for_error_payload,
)
from gapatlas.adapters.serpapi.params import build_params
from gapatlas.config.settings import Settings
from gapatlas.domain.models.common import SourceName
from gapatlas.domain.models.query_profile import QueryProfile

_LOGGER: Final[logging.Logger] = logging.getLogger(__name__)

SERPAPI_ENDPOINT: Final[str] = "https://serpapi.com/search.json"
"""SerpApi の JSON エンドポイント。"""

API_KEY_PARAM: Final[str] = "api_key"

RETRY_BASE_DELAY_SECONDS: Final[float] = 0.5
"""Exponential backoff の基準遅延。遅延 = base * 2**attempt(0.5, 1.0, 2.0, ...)。"""

RETRYABLE_STATUS_CODES: Final[frozenset[int]] = frozenset({429, 500, 503})
"""リトライしてよい HTTP ステータス。429 以外の 4xx はリトライしない。"""

HTTP_STATUS_OK: Final[int] = 200


def _is_retryable(error: SerpApiRequestError | SerpApiStatusError) -> bool:
    """リトライしてよい失敗か。

    ネットワーク障害(`SerpApiRequestError`)と 429 / 500 / 503 のみ。
    その他の 4xx はリトライしない(docs/serpapi-schema.md 6章)。
    """
    if isinstance(error, SerpApiStatusError):
        return error.status_code in RETRYABLE_STATUS_CODES
    return True


class LiveSerpApiClient:
    """SerpApi へ実際にリクエストするクライアント。"""

    def __init__(
        self,
        settings: Settings,
        *,
        client: httpx.Client | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        """
        Args:
            settings: `serpapi_api_key` / `serpapi_timeout_seconds` /
                `serpapi_max_retries` を参照する。
            client: 使用する httpx クライアント。省略時はリクエストごとに生成する。
                テストは `httpx.MockTransport` を積んだクライアントを渡す。
            sleep: バックオフの待機関数。テストが実時間を消費しないよう注入可能にする。

        Raises:
            SerpApiError: API キーが設定されていない場合。
        """
        if settings.serpapi_api_key is None:
            raise SerpApiError("SERPAPI_API_KEY is required for live mode")

        self._api_key = settings.serpapi_api_key
        self._timeout = settings.serpapi_timeout_seconds
        self._max_retries = settings.serpapi_max_retries
        self._client = client
        self._sleep = sleep

    def fetch(self, source: SourceName, profile: QueryProfile) -> dict[str, Any]:
        """SerpApi の生レスポンスを返す。

        Raises:
            SerpApiRequestError: ネットワーク障害・タイムアウトでリトライ上限に達した場合。
            SerpApiStatusError: HTTP ステータス由来の失敗(リトライ上限到達を含む)。
            SerpApiResponseError: 本文が JSON でない、またはエラー本文の場合。
        """
        params = build_params(source, profile)
        params[API_KEY_PARAM] = self._api_key.get_secret_value()

        attempts = self._max_retries + 1

        for attempt in range(attempts):
            try:
                return self._request(params)
            except (SerpApiRequestError, SerpApiStatusError) as exc:
                if not _is_retryable(exc) or attempt == attempts - 1:
                    raise
                delay = RETRY_BASE_DELAY_SECONDS * (2**attempt)
                _LOGGER.warning(
                    "serpapi retry scheduled",
                    extra={
                        "source": source.value,
                        "country": profile.country.value,
                        "topic": profile.topic_id.value,
                        "attempt": attempt + 1,
                        "delay_seconds": delay,
                    },
                )
                self._sleep(delay)

        # `attempts` は 1 以上(`serpapi_max_retries` は 0 以上)のため、ループは必ず
        # return するか raise する。型チェッカのために終端を置く。
        raise SerpApiError("serpapi retry loop ended without a result")

    def _request(self, params: dict[str, str]) -> dict[str, Any]:
        """1回分のリクエストを実行する。リトライはしない。"""
        if self._client is not None:
            return self._send(self._client, params)
        with httpx.Client(timeout=self._timeout) as client:
            return self._send(client, params)

    def _send(self, client: httpx.Client, params: dict[str, str]) -> dict[str, Any]:
        try:
            response = client.get(SERPAPI_ENDPOINT, params=params, timeout=self._timeout)
        except httpx.RequestError as exc:
            # 例外の文言をそのまま連結しない。URL を含む実装があり API キーが漏れうる。
            raise SerpApiRequestError(f"serpapi request failed: {type(exc).__name__}") from exc

        if response.status_code != HTTP_STATUS_OK:
            raise SerpApiStatusError(
                f"serpapi returned HTTP {response.status_code}: "
                f"url={mask_api_key(str(response.request.url))}",
                status_code=response.status_code,
            )

        return _parse_json_object(response)


def _parse_json_object(response: httpx.Response) -> dict[str, Any]:
    """レスポンス本文を JSON オブジェクトとして解釈する。

    HTTP 200 でも本文に `{"error": ...}` が返ることがある
    (docs/serpapi-schema.md 6章)。この場合はリトライせず即失敗させる。
    """
    try:
        loaded: object = json.loads(response.text)
    except json.JSONDecodeError as exc:
        raise SerpApiResponseError("serpapi response body is not valid JSON") from exc

    if not isinstance(loaded, dict):
        raise SerpApiResponseError(
            f"serpapi response body must be a JSON object, got {type(loaded).__name__}"
        )

    payload = cast(dict[str, Any], loaded)
    raise_for_error_payload(payload)
    return payload
