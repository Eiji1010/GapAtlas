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
from collections.abc import Sequence
from typing import Final

from gapatlas.adapters.serpapi.errors import mask_api_key

GUARDED_LOGGER_NAMES: Final[tuple[str, ...]] = ("httpx", "httpcore")
"""マスクを装着するロガー。URL を出力しうる外部ライブラリを列挙する。"""


class ApiKeyMaskingFilter(logging.Filter):
    """ログレコードから API キーを取り除くフィルタ。

    **書式を適用したあとの文字列**をマスクする。`msg` と `args` を別々に
    書き換えると、次の2つの経路で漏れる/壊れる。

    - httpx は URL を `str` ではなく `httpx.URL` のまま `args` へ渡すため、
      文字列だけを見ていると素通りする
    - 書式指定子(`%s`)を含む `msg` をマスクすると指定子ごと消える場合があり、
      `msg % args` が `TypeError` になる

    `logging.Filter` はレコードを書き換えてよい。ここで書き換えると、上位の
    ハンドラや `logging.exception` の出力にも反映される。二重に適用されても
    結果は変わらない(冪等)。
    """

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            message = record.getMessage()
        except (TypeError, ValueError):
            # 書式と引数が食い違うレコードは、ここで落とさず素通りさせる
            # (ログの不整合でアプリを止めない)。
            return True
        record.msg = mask_api_key(message)
        record.args = None
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
