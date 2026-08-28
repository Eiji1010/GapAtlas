"""ログへ API キーが出ないことの回帰テスト。

SerpApi は認証をクエリパラメータでしか受け付けないため URL 自体が秘密情報で、
httpx は**リクエストごとに完全な URL を INFO で出力する**。自前の例外メッセージ
だけをマスクしても、`LOG_LEVEL=INFO`(`.env.example` の既定)で運用すると
CloudWatch へ平文のキーが残る。ここはその経路を固定する。
"""

from __future__ import annotations

import io
import logging
import traceback

import httpx
import pytest
from pydantic import SecretStr

from gapatlas.adapters.serpapi.errors import SerpApiError, mask_api_key
from gapatlas.adapters.serpapi.live_client import MAX_RESPONSE_BYTES, LiveSerpApiClient
from gapatlas.adapters.serpapi.logging_guard import (
    GUARDED_LOGGER_NAMES,
    ApiKeyMaskingFilter,
    install_api_key_log_guard,
)
from gapatlas.config.query_profile_loader import load_query_profile
from gapatlas.config.settings import SerpApiMode, Settings
from gapatlas.domain.models.common import Country, SourceName, TopicId

FAKE_API_KEY = "test-serpapi-key-never-log-me"
"""テスト用のダミー値。実キーではない。"""


@pytest.fixture
def profile():
    return load_query_profile(TopicId.ELDER_CARE, Country.JP)


def _settings() -> Settings:
    return Settings(serpapi_mode=SerpApiMode.LIVE, serpapi_api_key=SecretStr(FAKE_API_KEY))


def _client(handler, sleep=lambda _delay: None) -> LiveSerpApiClient:
    return LiveSerpApiClient(
        _settings(), client=httpx.Client(transport=httpx.MockTransport(handler)), sleep=sleep
    )


def _capture_logs():
    buffer = io.StringIO()
    handler = logging.StreamHandler(buffer)
    root = logging.getLogger()
    previous_level = root.level
    root.addHandler(handler)
    root.setLevel(logging.INFO)
    return buffer, handler, previous_level


def test_httpx_info_log_does_not_contain_the_api_key(profile):
    """成功リクエストでもキーがログへ出ないこと。"""
    buffer, handler, previous_level = _capture_logs()
    try:
        client = _client(lambda _request: httpx.Response(200, json={"ok": True}))
        client.fetch(SourceName.SEARCH, profile)
    finally:
        logging.getLogger().removeHandler(handler)
        logging.getLogger().setLevel(previous_level)

    logged = buffer.getvalue()
    assert FAKE_API_KEY not in logged
    # マスク自体は効いており、ログが空になっただけではないこと
    assert "api_key=***" in logged


def test_the_api_key_does_not_appear_in_a_chained_traceback(profile):
    """`raise ... from exc` の原因例外経由でも漏れないこと。

    `str(exc)` は安全でも、`logger.exception` や未捕捉例外のトレースバックには
    原因例外のメッセージがそのまま現れる。
    """

    def handler(request: httpx.Request) -> httpx.Response:
        message = f"failed to reach {request.url}"
        raise httpx.ConnectError(message, request=request)

    with pytest.raises(SerpApiError) as excinfo:
        _client(handler).fetch(SourceName.SEARCH, profile)

    formatted = "".join(
        traceback.format_exception(type(excinfo.value), excinfo.value, excinfo.value.__traceback__)
    )
    assert FAKE_API_KEY not in formatted


@pytest.mark.parametrize(
    "text",
    [
        f"https://serpapi.com/search.json?q=x&api_key={FAKE_API_KEY}&hl=ja",
        f"https://serpapi.com/search.json?API_KEY={FAKE_API_KEY}",
        f"{{'api_key': '{FAKE_API_KEY}', 'q': 'x'}}",
        f'{{"api_key": "{FAKE_API_KEY}"}}',
    ],
    ids=["query", "uppercase-query", "dict-repr", "json"],
)
def test_mask_api_key_covers_url_and_mapping_notations(text):
    """URL だけでなく params dict の repr も捕捉すること。

    `params` dict は平文キーを保持している。`mask_api_key` の保護範囲が
    URL だけだと、後から dict をログへ載せる一行が入ったときに無言で漏れる。
    """
    masked = mask_api_key(text)
    assert FAKE_API_KEY not in masked
    assert "***" in masked


def test_the_filter_is_installed_once_per_logger():
    """多重装着しないこと。"""
    install_api_key_log_guard()
    install_api_key_log_guard()
    for name in GUARDED_LOGGER_NAMES:
        filters = [
            item
            for item in logging.getLogger(name).filters
            if isinstance(item, ApiKeyMaskingFilter)
        ]
        assert len(filters) == 1


def test_the_filter_keeps_non_string_arguments_intact():
    """キーを含まない引数は型を変えない(`%d` などの書式を壊さない)。"""
    record = logging.LogRecord("x", logging.INFO, __file__, 1, "count=%d", (42,), None)
    assert ApiKeyMaskingFilter().filter(record) is True
    assert record.args == (42,)
    assert record.getMessage() == "count=42"


def test_an_oversized_response_body_is_rejected(profile):
    """本文サイズに上限を設ける。

    上限が無いと、障害時の巨大な本文でメモリを使い切り「1ソースの失敗」では
    なくプロセス強制終了になる(docs/requirements.md「Reliability」)。
    """
    oversized = b"x" * (MAX_RESPONSE_BYTES + 1)
    with pytest.raises(SerpApiError, match="exceeds"):
        _client(lambda _request: httpx.Response(200, content=oversized)).fetch(
            SourceName.SEARCH, profile
        )
