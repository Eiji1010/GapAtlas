"""`Settings` から SerpApi クライアントを組み立てるファクトリ。

`SERPAPI_MODE` の分岐をここへ閉じ込め、application 層は `SerpApiClient`
(Protocol)だけを見る(docs/architecture.md「依存の向き」)。
"""

from __future__ import annotations

from gapatlas.adapters.serpapi.errors import SerpApiError
from gapatlas.adapters.serpapi.fixture_client import FixtureSerpApiClient
from gapatlas.adapters.serpapi.live_client import LiveSerpApiClient
from gapatlas.adapters.serpapi.protocol import SerpApiClient
from gapatlas.config.settings import SerpApiMode, Settings


def create_serpapi_client(settings: Settings) -> SerpApiClient:
    """`settings.serpapi_mode` に応じたクライアントを返す。

    既定は fixture(docs/decisions/0003-fixture-first.md)。

    Raises:
        SerpApiError: live モードで API キーが設定されていない場合。
    """
    match settings.serpapi_mode:
        case SerpApiMode.FIXTURE:
            return FixtureSerpApiClient()
        case SerpApiMode.LIVE:
            return LiveSerpApiClient(settings)
        case _:
            # モードを追加して case を書き忘れたときに無言で None を返さない。
            raise SerpApiError(f"unsupported serpapi mode: {settings.serpapi_mode}")
