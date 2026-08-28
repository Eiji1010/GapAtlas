"""LLM アダプタの例外。

呼び出し元が「再試行してよい失敗」と「応答内容の失敗」を区別できるよう階層を分ける。

**例外メッセージに API キーを書かない。** 外部 SDK の例外を包むときも、原因例外の
本文をメッセージへ展開せず、型名だけを載せて `raise ... from exc` で連結する。
"""

from __future__ import annotations

from gapatlas.domain.models.errors import GapAtlasError


class LlmError(GapAtlasError):
    """LLM アダプタで発生する例外の基底。"""


class LlmRequestError(LlmError):
    """ネットワーク・タイムアウト・API 障害など、応答を得られなかった場合。"""


class LlmResponseError(LlmError):
    """応答は得られたが、JSON が壊れている・想定外の構造である場合。"""
