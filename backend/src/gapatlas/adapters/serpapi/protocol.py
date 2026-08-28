"""SerpApi クライアントの構造的インターフェース。

application 層は具体実装ではなくこの Protocol に依存する
(docs/architecture.md「依存の向き」)。
"""

from __future__ import annotations

from typing import Any, Protocol

from gapatlas.domain.models.common import SourceName
from gapatlas.domain.models.query_profile import QueryProfile


class SerpApiClient(Protocol):
    """SerpApi からの取得を担うクライアント。"""

    def fetch(self, source: SourceName, profile: QueryProfile) -> dict[str, Any]:
        """SerpApi の生レスポンスを dict のまま返す。

        生のまま返すのは S3 raw/ へ無加工で保存する要件があるため
        (docs/architecture.md)。正規化は normalize.py が担当する。

        Raises:
            SerpApiError 系。呼び出し側は 1 ソースの失敗で全体を止めない。
        """
        ...
