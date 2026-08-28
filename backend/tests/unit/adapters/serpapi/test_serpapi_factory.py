"""`create_serpapi_client` のテスト。"""

from __future__ import annotations

import pytest
from pydantic import SecretStr

from gapatlas.adapters.serpapi.errors import SerpApiError
from gapatlas.adapters.serpapi.factory import create_serpapi_client
from gapatlas.adapters.serpapi.fixture_client import FixtureSerpApiClient
from gapatlas.adapters.serpapi.live_client import LiveSerpApiClient
from gapatlas.config.settings import SerpApiMode, Settings, load_settings


def test_default_settings_produce_a_fixture_client() -> None:
    """既定は fixture(外部通信ゼロ)。"""
    settings = load_settings({})

    assert settings.serpapi_mode is SerpApiMode.FIXTURE
    assert isinstance(create_serpapi_client(settings), FixtureSerpApiClient)


def test_live_mode_produces_a_live_client() -> None:
    settings = Settings(
        serpapi_mode=SerpApiMode.LIVE,
        serpapi_api_key=SecretStr("fake-serpapi-key-for-tests-only"),
    )

    assert isinstance(create_serpapi_client(settings), LiveSerpApiClient)


def test_live_mode_without_a_key_is_rejected_by_settings() -> None:
    """`Settings` 側で弾かれるため、ファクトリまで到達しない。"""
    with pytest.raises(ValueError, match="SERPAPI_API_KEY"):
        Settings(serpapi_mode=SerpApiMode.LIVE, serpapi_api_key=None)


def test_live_client_rejects_a_missing_key_defensively() -> None:
    """`Settings` を経由せず組み立てた場合でもキー無しでは作らせない。"""
    settings = Settings.model_construct(
        serpapi_mode=SerpApiMode.LIVE,
        serpapi_api_key=None,
        serpapi_timeout_seconds=8.0,
        serpapi_max_retries=2,
    )

    with pytest.raises(SerpApiError):
        create_serpapi_client(settings)
