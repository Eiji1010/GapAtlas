"""環境変数から読み込む設定。

**`os.environ` を直接参照するのはこのモジュールだけ**とする。他のモジュールは
`Settings` を引数で受け取る。環境変数名は `.env.example` と一致させている。

API キーは `SecretStr` で保持する。`repr()` / `str()` に実値を出さないため。
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from enum import StrEnum
from typing import Final, Self

from pydantic import BaseModel, ConfigDict, Field, SecretStr, ValidationError, model_validator

from gapatlas.config.errors import SettingsError

DEFAULT_CORS_ALLOWED_ORIGINS: Final[tuple[str, ...]] = ("http://localhost:5173",)


class SerpApiMode(StrEnum):
    """SerpApi の動作モード。"""

    FIXTURE = "fixture"
    """tests/fixtures 配下の保存済みレスポンスを使用(外部通信なし)。"""

    LIVE = "live"
    """SerpApi へ実際にリクエストする。"""


class LogLevel(StrEnum):
    """`logging` が受け付けるレベル名。"""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class LlmMode(StrEnum):
    """LLM の動作モード。"""

    STUB = "stub"
    """決定的なスタブ応答を返す(単体テスト・開発用)。"""

    ANTHROPIC = "anthropic"
    """Anthropic API を直接呼び出す。"""


class Settings(BaseModel):
    """アプリケーション設定。"""

    model_config = ConfigDict(extra="forbid")

    serpapi_mode: SerpApiMode = SerpApiMode.FIXTURE
    serpapi_api_key: SecretStr | None = None
    serpapi_timeout_seconds: float = Field(default=8.0, gt=0.0)
    serpapi_max_retries: int = Field(default=2, ge=0)

    llm_mode: LlmMode = LlmMode.STUB
    anthropic_api_key: SecretStr | None = None
    anthropic_model: str = Field(default="claude-sonnet-5", min_length=1)
    anthropic_timeout_seconds: float = Field(default=30.0, gt=0.0)
    """LLM 1リクエストの上限。SDK 既定(read 600秒)は SLO と2桁乖離するため明示する。"""

    anthropic_max_retries: int = Field(default=2, ge=0)
    """SDK のリトライ回数。SerpApi 側(既定2回)と方針を揃える。"""

    aws_region: str = Field(default="ap-northeast-1", min_length=1)
    dynamodb_table_name: str = Field(default="gapatlas", min_length=1)
    s3_bucket_name: str = Field(default="gapatlas-data", min_length=1)
    sqs_queue_url: str | None = None

    log_level: LogLevel = LogLevel.INFO
    """`logging` のレベル名。不正な値は起動時に弾く。

    自由文字列にすると `logging.setLevel` が `ValueError` を投げる。ログ設定の
    最中に落ちるため構造化ログにも残らず、原因が追えない。
    """

    cors_allowed_origins: list[str] = Field(
        default_factory=lambda: list(DEFAULT_CORS_ALLOWED_ORIGINS)
    )

    @model_validator(mode="after")
    def _check_credentials_present(self) -> Self:
        """live / anthropic モードで必要な資格情報が揃っているか確認する。

        値そのものはメッセージへ出さない。
        """
        if self.serpapi_mode is SerpApiMode.LIVE and self.serpapi_api_key is None:
            message = "SERPAPI_API_KEY is required when SERPAPI_MODE=live"
            raise ValueError(message)
        if self.llm_mode is LlmMode.ANTHROPIC and self.anthropic_api_key is None:
            message = "ANTHROPIC_API_KEY is required when LLM_MODE=anthropic"
            raise ValueError(message)
        return self


def _get(env: Mapping[str, str], key: str) -> str | None:
    """環境変数を取得する。空文字は未設定として扱う。"""
    value = env.get(key)
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _get_secret(env: Mapping[str, str], key: str) -> SecretStr | None:
    value = _get(env, key)
    return None if value is None else SecretStr(value)


def _get_enum[EnumT: StrEnum](
    env: Mapping[str, str], key: str, enum_type: type[EnumT], default: EnumT
) -> EnumT:
    value = _get(env, key)
    if value is None:
        return default
    try:
        return enum_type(value.lower())
    except ValueError as exc:
        allowed = ", ".join(member.value for member in enum_type)
        message = f"{key} must be one of: {allowed}"
        raise SettingsError(message) from exc


def _get_float(env: Mapping[str, str], key: str, default: float) -> float:
    value = _get(env, key)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError as exc:
        message = f"{key} must be a number"
        raise SettingsError(message) from exc


def _get_int(env: Mapping[str, str], key: str, default: int) -> int:
    value = _get(env, key)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError as exc:
        message = f"{key} must be an integer"
        raise SettingsError(message) from exc


def _get_log_level(env: Mapping[str, str]) -> LogLevel:
    """`LOG_LEVEL` を読む。大文字小文字は問わない。"""
    value = _get(env, "LOG_LEVEL")
    if value is None:
        return LogLevel.INFO
    try:
        return LogLevel(value.upper())
    except ValueError as exc:
        allowed = ", ".join(member.value for member in LogLevel)
        message = f"LOG_LEVEL must be one of: {allowed}"
        raise SettingsError(message) from exc


def _get_str_list(env: Mapping[str, str], key: str, default: tuple[str, ...]) -> list[str]:
    """カンマ区切りの文字列をリストへ変換する。"""
    value = _get(env, key)
    if value is None:
        return list(default)
    return [item.strip() for item in value.split(",") if item.strip()]


def load_settings(env: Mapping[str, str] | None = None) -> Settings:
    """環境変数から `Settings` を組み立てる。

    Args:
        env: 環境変数のマッピング。省略時は `os.environ`。
            テストから `os.environ` を触らずに検証できるよう引数で受け取る。

    Raises:
        SettingsError: 値の形式が不正、または必要な資格情報が欠けている場合。
    """
    source: Mapping[str, str] = os.environ if env is None else env

    try:
        return Settings(
            serpapi_mode=_get_enum(source, "SERPAPI_MODE", SerpApiMode, SerpApiMode.FIXTURE),
            serpapi_api_key=_get_secret(source, "SERPAPI_API_KEY"),
            serpapi_timeout_seconds=_get_float(source, "SERPAPI_TIMEOUT_SECONDS", 8.0),
            serpapi_max_retries=_get_int(source, "SERPAPI_MAX_RETRIES", 2),
            llm_mode=_get_enum(source, "LLM_MODE", LlmMode, LlmMode.STUB),
            anthropic_api_key=_get_secret(source, "ANTHROPIC_API_KEY"),
            anthropic_model=_get(source, "ANTHROPIC_MODEL") or "claude-sonnet-5",
            anthropic_timeout_seconds=_get_float(source, "ANTHROPIC_TIMEOUT_SECONDS", 30.0),
            anthropic_max_retries=_get_int(source, "ANTHROPIC_MAX_RETRIES", 2),
            aws_region=_get(source, "AWS_REGION") or "ap-northeast-1",
            dynamodb_table_name=_get(source, "DYNAMODB_TABLE_NAME") or "gapatlas",
            s3_bucket_name=_get(source, "S3_BUCKET_NAME") or "gapatlas-data",
            sqs_queue_url=_get(source, "SQS_QUEUE_URL"),
            log_level=_get_log_level(source),
            cors_allowed_origins=_get_str_list(
                source, "CORS_ALLOWED_ORIGINS", DEFAULT_CORS_ALLOWED_ORIGINS
            ),
        )
    except ValidationError as exc:
        # 例外メッセージに秘密情報の値が載らないよう、内容は要約のみを使う。
        details = "; ".join(
            f"{'.'.join(str(part) for part in error['loc'])}: {error['msg']}"
            for error in exc.errors()
        )
        message = f"invalid settings: {details}"
        raise SettingsError(message) from exc
