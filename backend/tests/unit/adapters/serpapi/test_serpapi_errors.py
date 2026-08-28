"""例外階層と API キーのマスキングのテスト。"""

from __future__ import annotations

import pytest

from gapatlas.adapters.serpapi.errors import (
    FixtureNotFoundError,
    SerpApiError,
    SerpApiRequestError,
    SerpApiResponseError,
    SerpApiStatusError,
    mask_api_key,
    raise_for_error_payload,
)
from gapatlas.domain.models.errors import GapAtlasError


@pytest.mark.parametrize(
    "error_type",
    [SerpApiRequestError, SerpApiResponseError, FixtureNotFoundError],
)
def test_errors_derive_from_the_shared_base(error_type: type[SerpApiError]) -> None:
    error = error_type("boom")

    assert isinstance(error, SerpApiError)
    assert isinstance(error, GapAtlasError)


def test_status_error_keeps_the_status_code() -> None:
    error = SerpApiStatusError("boom", status_code=429)

    assert isinstance(error, SerpApiError)
    assert error.status_code == 429


def test_mask_api_key_replaces_the_value_only() -> None:
    masked = mask_api_key("https://serpapi.com/search.json?q=x&api_key=secret-value&hl=ja")

    assert "secret-value" not in masked
    assert masked == "https://serpapi.com/search.json?q=x&api_key=***&hl=ja"


def test_mask_api_key_handles_a_trailing_key() -> None:
    assert mask_api_key("...&api_key=secret-value") == "...&api_key=***"


def test_mask_api_key_leaves_unrelated_text_untouched() -> None:
    assert mask_api_key("no key here") == "no key here"


def test_raise_for_error_payload_accepts_normal_payloads() -> None:
    raise_for_error_payload({"organic_results": []})


def test_raise_for_error_payload_rejects_error_payloads() -> None:
    with pytest.raises(SerpApiResponseError) as excinfo:
        raise_for_error_payload({"error": "Invalid API key."})

    assert "Invalid API key." in str(excinfo.value)


def test_raise_for_error_payload_handles_non_string_error_values() -> None:
    with pytest.raises(SerpApiResponseError):
        raise_for_error_payload({"error": {"code": 401}})


def test_raise_for_error_payload_masks_keys_inside_the_message() -> None:
    with pytest.raises(SerpApiResponseError) as excinfo:
        raise_for_error_payload({"error": "bad request: api_key=secret-value"})

    assert "secret-value" not in str(excinfo.value)
