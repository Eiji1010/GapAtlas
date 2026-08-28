"""Settings と load_settings のテスト。

`os.environ` には触らず、`env` 引数で検証する。
"""

from __future__ import annotations

import pytest

from gapatlas.config.errors import SettingsError
from gapatlas.config.settings import LlmMode, SerpApiMode, Settings, load_settings

FAKE_SERPAPI_KEY = "test-serpapi-key-not-real"
FAKE_ANTHROPIC_KEY = "test-anthropic-key-not-real"


def test_defaults_match_env_example():
    settings = load_settings(env={})
    assert settings.serpapi_mode is SerpApiMode.FIXTURE
    assert settings.serpapi_api_key is None
    assert settings.serpapi_timeout_seconds == 8.0
    assert settings.serpapi_max_retries == 2
    assert settings.llm_mode is LlmMode.STUB
    assert settings.anthropic_api_key is None
    assert settings.anthropic_model == "claude-sonnet-5"
    assert settings.aws_region == "ap-northeast-1"
    assert settings.dynamodb_table_name == "gapatlas"
    assert settings.s3_bucket_name == "gapatlas-data"
    assert settings.sqs_queue_url is None
    assert settings.log_level == "INFO"
    assert settings.cors_allowed_origins == ["http://localhost:5173"]


def test_empty_string_is_treated_as_unset():
    """`.env.example` は SERPAPI_API_KEY= のように空値で書かれている。"""
    settings = load_settings(env={"SERPAPI_API_KEY": "", "SQS_QUEUE_URL": "  "})
    assert settings.serpapi_api_key is None
    assert settings.sqs_queue_url is None


def test_reads_all_env_names_from_env_example():
    settings = load_settings(
        env={
            "SERPAPI_MODE": "live",
            "SERPAPI_API_KEY": FAKE_SERPAPI_KEY,
            "SERPAPI_TIMEOUT_SECONDS": "3.5",
            "SERPAPI_MAX_RETRIES": "0",
            "LLM_MODE": "anthropic",
            "ANTHROPIC_API_KEY": FAKE_ANTHROPIC_KEY,
            "ANTHROPIC_MODEL": "claude-opus-5",
            "AWS_REGION": "us-east-1",
            "DYNAMODB_TABLE_NAME": "custom-table",
            "S3_BUCKET_NAME": "custom-bucket",
            "SQS_QUEUE_URL": "https://sqs.example.com/queue",
            "LOG_LEVEL": "DEBUG",
            "CORS_ALLOWED_ORIGINS": "https://a.example.com, https://b.example.com",
        }
    )
    assert settings.serpapi_mode is SerpApiMode.LIVE
    assert settings.serpapi_api_key is not None
    assert settings.serpapi_api_key.get_secret_value() == FAKE_SERPAPI_KEY
    assert settings.serpapi_timeout_seconds == 3.5
    assert settings.serpapi_max_retries == 0
    assert settings.llm_mode is LlmMode.ANTHROPIC
    assert settings.anthropic_model == "claude-opus-5"
    assert settings.aws_region == "us-east-1"
    assert settings.dynamodb_table_name == "custom-table"
    assert settings.s3_bucket_name == "custom-bucket"
    assert settings.sqs_queue_url == "https://sqs.example.com/queue"
    assert settings.log_level == "DEBUG"
    assert settings.cors_allowed_origins == ["https://a.example.com", "https://b.example.com"]


def test_live_mode_without_serpapi_key_raises():
    with pytest.raises(SettingsError, match="SERPAPI_API_KEY"):
        load_settings(env={"SERPAPI_MODE": "live"})


def test_live_mode_with_blank_serpapi_key_raises():
    with pytest.raises(SettingsError, match="SERPAPI_API_KEY"):
        load_settings(env={"SERPAPI_MODE": "live", "SERPAPI_API_KEY": "   "})


def test_anthropic_mode_without_key_raises():
    with pytest.raises(SettingsError, match="ANTHROPIC_API_KEY"):
        load_settings(env={"LLM_MODE": "anthropic"})


def test_unknown_mode_raises():
    with pytest.raises(SettingsError, match="SERPAPI_MODE"):
        load_settings(env={"SERPAPI_MODE": "unknown"})


def test_non_numeric_timeout_raises():
    with pytest.raises(SettingsError, match="SERPAPI_TIMEOUT_SECONDS"):
        load_settings(env={"SERPAPI_TIMEOUT_SECONDS": "eight"})


def test_non_integer_retries_raises():
    with pytest.raises(SettingsError, match="SERPAPI_MAX_RETRIES"):
        load_settings(env={"SERPAPI_MAX_RETRIES": "many"})


def test_negative_retries_raises():
    with pytest.raises(SettingsError, match="serpapi_max_retries"):
        load_settings(env={"SERPAPI_MAX_RETRIES": "-1"})


def _settings_with_keys() -> Settings:
    return load_settings(
        env={
            "SERPAPI_MODE": "live",
            "SERPAPI_API_KEY": FAKE_SERPAPI_KEY,
            "LLM_MODE": "anthropic",
            "ANTHROPIC_API_KEY": FAKE_ANTHROPIC_KEY,
        }
    )


def test_str_does_not_leak_api_keys():
    settings = _settings_with_keys()
    assert FAKE_SERPAPI_KEY not in str(settings)
    assert FAKE_ANTHROPIC_KEY not in str(settings)


def test_repr_does_not_leak_api_keys():
    settings = _settings_with_keys()
    assert FAKE_SERPAPI_KEY not in repr(settings)
    assert FAKE_ANTHROPIC_KEY not in repr(settings)


def test_model_dump_does_not_leak_api_keys():
    settings = _settings_with_keys()
    assert FAKE_SERPAPI_KEY not in str(settings.model_dump())
    assert FAKE_SERPAPI_KEY not in str(settings.model_dump(mode="json"))
    assert FAKE_ANTHROPIC_KEY not in str(settings.model_dump_json())


def test_error_message_does_not_leak_api_keys():
    with pytest.raises(SettingsError) as excinfo:
        load_settings(
            env={
                "SERPAPI_MODE": "live",
                "SERPAPI_API_KEY": FAKE_SERPAPI_KEY,
                "SERPAPI_MAX_RETRIES": "-1",
            }
        )
    assert FAKE_SERPAPI_KEY not in str(excinfo.value)


def test_secret_value_is_still_accessible():
    settings = _settings_with_keys()
    assert settings.serpapi_api_key is not None
    assert settings.serpapi_api_key.get_secret_value() == FAKE_SERPAPI_KEY
