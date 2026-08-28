"""`SERPAPI_MODE=fixture` 用の SerpApi クライアント。

保存済みレスポンスを読むだけで、**外部通信を一切行わない**
(AGENTS.md「fixture mode を常に維持する」/ docs/decisions/0003-fixture-first.md)。

ファイル配置: `<base_dir>/<topic_id>/<COUNTRY>/<file>.json`
既定の `base_dir` は `backend/tests/fixtures/serpapi`。
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Final, cast

from gapatlas.adapters.serpapi.errors import (
    FixtureNotFoundError,
    SerpApiResponseError,
    raise_for_error_payload,
)
from gapatlas.domain.models.common import SourceName
from gapatlas.domain.models.query_profile import QueryProfile

_MODULE_PATH: Final[Path] = Path(__file__).resolve()

# _MODULE_PATH = <repo>/backend/src/gapatlas/adapters/serpapi/fixture_client.py
#   parents[0] = <repo>/backend/src/gapatlas/adapters/serpapi
#   parents[1] = <repo>/backend/src/gapatlas/adapters
#   parents[2] = <repo>/backend/src/gapatlas
#   parents[3] = <repo>/backend/src
#   parents[4] = <repo>/backend          ← backend ルート
_BACKEND_ROOT: Final[Path] = _MODULE_PATH.parents[4]

DEFAULT_FIXTURE_DIR: Final[Path] = _BACKEND_ROOT / "tests" / "fixtures" / "serpapi"
"""既定の fixture 格納ディレクトリ。

デプロイパッケージには `tests/` を含めないため、Lambda 上ではこのパスが解決
できない可能性がある(既知の持ち越し課題)。その場合は `base_dir` を注入する。
"""

FIXTURE_FILE_NAMES: Final[Mapping[SourceName, str]] = {
    SourceName.TRENDS: "trends_timeseries.json",
    SourceName.RELATED_QUERIES: "trends_related_queries.json",
    SourceName.SEARCH: "search.json",
    SourceName.NEWS: "news.json",
    SourceName.MAPS: "maps.json",
}
"""ソース名と fixture ファイル名の対応(backend/tests/fixtures/README.md の命名規約)。"""


def load_fixture(path: Path) -> dict[str, Any]:
    """1件の fixture JSON を読み込み、SerpApi のエラー本文なら例外にする。

    Raises:
        FixtureNotFoundError: ファイルが存在しない場合。
        SerpApiResponseError: JSON として解析できない、オブジェクトでない、
            または `{"error": ...}` を含む場合。
    """
    if not path.is_file():
        raise FixtureNotFoundError(f"serpapi fixture not found: path={path}")

    text = path.read_text(encoding="utf-8")
    try:
        loaded: object = json.loads(text)
    except json.JSONDecodeError as exc:
        raise SerpApiResponseError(f"serpapi fixture is not valid JSON: path={path}") from exc

    if not isinstance(loaded, dict):
        raise SerpApiResponseError(
            f"serpapi fixture must be a JSON object: path={path}, got {type(loaded).__name__}"
        )

    payload = cast(dict[str, Any], loaded)
    raise_for_error_payload(payload)
    return payload


class FixtureSerpApiClient:
    """保存済みレスポンスを返す SerpApi クライアント。"""

    def __init__(self, base_dir: Path | None = None) -> None:
        """
        Args:
            base_dir: fixture 格納ディレクトリ。省略時は `DEFAULT_FIXTURE_DIR`。
        """
        self._base_dir = (base_dir or DEFAULT_FIXTURE_DIR).resolve()

    @property
    def base_dir(self) -> Path:
        """解決済みの fixture 格納ディレクトリ。"""
        return self._base_dir

    def fixture_path(self, source: SourceName, profile: QueryProfile) -> Path:
        """fixture のパスを組み立て、`base_dir` の外を指さないことを保証する。

        `source` / `topic_id` / `country` はいずれも Enum のため任意文字列は
        入らないが、`base_dir` 自体がシンボリックリンク等を含む場合に備えて
        解決後のパスを再確認する(config/query_profile_loader.py と同じ防御)。
        """
        candidate = (
            self._base_dir
            / profile.topic_id.value
            / profile.country.value
            / FIXTURE_FILE_NAMES[source]
        ).resolve()
        if not candidate.is_relative_to(self._base_dir):
            raise SerpApiResponseError(
                f"resolved fixture path escapes base_dir: source={source.value}"
            )
        return candidate

    def fetch(self, source: SourceName, profile: QueryProfile) -> dict[str, Any]:
        """保存済みの生レスポンスを返す。

        Raises:
            FixtureNotFoundError: 該当 fixture が存在しない場合。
            SerpApiResponseError: JSON が壊れている、またはエラー本文の場合。
        """
        return load_fixture(self.fixture_path(source, profile))
