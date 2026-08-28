"""ログへ API キーが出ることを防ぐガード。

SerpApi は認証をクエリパラメータ(`api_key=...`)でしか受け付けないため、URL
そのものが秘密情報になる。httpx は**リクエストごとに完全な URL を INFO で
出力する**ので、自分が書くログをマスクするだけでは足りない
(`.env.example` の既定 `LOG_LEVEL=INFO` と Lambda ランタイムの既定設定で
条件が揃う)。

`docs/architecture.md`「Observability」の「ログ出力前にマスクする」を、
プロセスが出すログ全体に対して満たすため、外部ライブラリのロガーへ
マスク用のフィルタを装着する。
"""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from typing import Final

from gapatlas.adapters.serpapi.errors import mask_api_key

GUARDED_LOGGER_NAMES: Final[tuple[str, ...]] = ("httpx", "httpcore")
"""マスクを装着するロガー。URL を出力しうる外部ライブラリを列挙する。"""


def _mask(value: object) -> object:
    """ログ引数から API キーを取り除く。

    httpx は URL を `str` ではなく `httpx.URL` オブジェクトのまま引数へ渡す。
    文字列だけを見ていると素通りするため、`str()` した結果にキーが含まれる
    場合はマスク済みの文字列へ置き換える。含まれない引数は元の型のまま残す
    (`%d` などの書式指定を壊さないため)。
    """
    if isinstance(value, str):
        return mask_api_key(value)
    text = str(value)
    masked = mask_api_key(text)
    return masked if masked != text else value


class ApiKeyMaskingFilter(logging.Filter):
    """ログレコードのメッセージと引数から API キーを取り除くフィルタ。

    `logging.Filter` はレコードを書き換えてよい。ここで書き換えると、上位の
    ハンドラや `logging.exception` の出力にも反映される。
    """

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = mask_api_key(record.msg)
        args = record.args
        if isinstance(args, tuple):
            record.args = tuple(_mask(item) for item in args)
        elif isinstance(args, Mapping):
            record.args = {key: _mask(value) for key, value in args.items()}
        return True


def install_api_key_log_guard(
    logger_names: Sequence[str] = GUARDED_LOGGER_NAMES,
) -> None:
    """指定したロガーへマスクフィルタを装着する。多重装着はしない。

    live クライアントの生成時に呼ぶ。fixture モードでは外部通信が無いため
    不要だが、装着しても副作用は無い。
    """
    for name in logger_names:
        logger = logging.getLogger(name)
        if not any(isinstance(existing, ApiKeyMaskingFilter) for existing in logger.filters):
            logger.addFilter(ApiKeyMaskingFilter())
