"""config 層で使用する例外。

呼び出し元が「設定不備」「プロファイル未存在」「プロファイル内容不正」を
区別できるよう型を分ける。
"""

from __future__ import annotations

from gapatlas.domain.models.errors import GapAtlasError


class ConfigError(GapAtlasError):
    """config 層で発生する例外の基底。"""


class SettingsError(ConfigError):
    """環境変数から Settings を組み立てられない場合。

    メッセージに秘密情報の値を含めないこと。
    """


class QueryProfileError(ConfigError):
    """QueryProfile の読み込みに関する例外の基底。"""


class QueryProfileNotFoundError(QueryProfileError):
    """指定した topic_id / country の YAML が存在しない場合。"""


class QueryProfileValidationError(QueryProfileError):
    """YAML の内容が QueryProfile の制約を満たさない場合。"""
