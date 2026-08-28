"""永続化アダプタの例外。"""

from __future__ import annotations

from gapatlas.domain.models.errors import GapAtlasError


class RepositoryError(GapAtlasError):
    """永続化層の例外の基底。"""


class RepositoryWriteError(RepositoryError):
    """書き込みに失敗した場合。"""


class RepositoryReadError(RepositoryError):
    """読み取りに失敗した場合。

    「存在しない」は例外ではなく `None` で表す。この例外は通信障害や
    権限不足など、**結果を判定できなかった**場合に使う。
    """


class RepositoryDataError(RepositoryError):
    """保存されていた内容を契約のモデルへ復元できない場合。

    スキーマを変えた後に古い項目を読んだときなどに起きる。壊れた1件で
    全体を落とさないよう、呼び出し側は捕捉して「無かった」扱いにしてよい。
    """
