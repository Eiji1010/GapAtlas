"""application 層のテスト用ヘルパ。

fixture の基準日は `2026-08-28T00:00:00Z`。`scan_time` を明示的に渡さないと
非決定的になる(backend/tests/fixtures/README.md)。
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

from gapatlas.adapters.llm.errors import LlmResponseError
from gapatlas.adapters.llm.stub_client import StubLlmClient
from gapatlas.adapters.serpapi.errors import SerpApiResponseError, SerpApiStatusError
from gapatlas.adapters.serpapi.fixture_client import FixtureSerpApiClient, load_fixture
from gapatlas.domain.models.classification import (
    NewsClassification,
    PainClassification,
    SolutionClassification,
)
from gapatlas.domain.models.common import Country, SourceName, TopicId
from gapatlas.domain.models.normalized import NewsArticle, RisingQuery, SearchResultItem
from gapatlas.domain.models.query_profile import QueryProfile

SCAN_TIME = datetime(2026, 8, 28, tzinfo=UTC)
SCAN_ID = "scan_test"
TOPIC = TopicId.ELDER_CARE


class FailingSerpApiClient:
    """指定したソースだけ失敗する SerpApi クライアント。"""

    def __init__(self, failing: Sequence[SourceName], *, status_code: int = 429) -> None:
        self._inner = FixtureSerpApiClient()
        self._failing = set(failing)
        self._status_code = status_code

    def fetch(self, source: SourceName, profile: QueryProfile) -> dict[str, Any]:
        if source in self._failing:
            message = f"simulated failure for {source.value}"
            raise SerpApiStatusError(message, status_code=self._status_code)
        return self._inner.fetch(source, profile)


class FixtureOverrideClient:
    """特定のソースを別の fixture ファイルへ差し替えるクライアント。"""

    def __init__(self, overrides: dict[SourceName, str]) -> None:
        self._inner = FixtureSerpApiClient()
        self._overrides = overrides

    def fetch(self, source: SourceName, profile: QueryProfile) -> dict[str, Any]:
        name = self._overrides.get(source)
        if name is None:
            return self._inner.fetch(source, profile)
        return load_fixture(self._inner.base_dir / "edge_cases" / f"{name}.json")


class TrendsKillClient:
    """指定した国だけ Trends を失敗させる。スコア有無が混在する状況を作る。"""

    def __init__(self, countries: Sequence[Country]) -> None:
        self._inner = FixtureSerpApiClient()
        self._countries = set(countries)

    def fetch(self, source: SourceName, profile: QueryProfile) -> dict[str, Any]:
        if source is SourceName.TRENDS and profile.country in self._countries:
            message = f"simulated trends failure for {profile.country.value}"
            raise SerpApiStatusError(message, status_code=503)
        return self._inner.fetch(source, profile)


class RecordingSerpApiClient:
    """呼び出し順を記録するクライアント。Maps の取得タイミングを検証する。"""

    def __init__(self) -> None:
        self._inner = FixtureSerpApiClient()
        self.calls: list[tuple[str, str]] = []

    def fetch(self, source: SourceName, profile: QueryProfile) -> dict[str, Any]:
        self.calls.append((profile.country.value, source.value))
        return self._inner.fetch(source, profile)


class ShortClassifier:
    """Protocol 違反(返却件数が入力と違う)の分類器。"""

    def __init__(self) -> None:
        self._inner = StubLlmClient()

    @property
    def classifier_version(self) -> str:
        return self._inner.classifier_version

    @property
    def prompt_version(self) -> str:
        return self._inner.prompt_version

    def classify_rising_queries(
        self, items: Sequence[RisingQuery], profile: QueryProfile
    ) -> list[PainClassification]:
        return self._inner.classify_rising_queries(items, profile)

    def classify_search_results(
        self, items: Sequence[SearchResultItem], profile: QueryProfile
    ) -> list[SolutionClassification]:
        return self._inner.classify_search_results(items, profile)[:-1]

    def classify_news_articles(
        self, items: Sequence[NewsArticle], profile: QueryProfile
    ) -> list[NewsClassification]:
        return self._inner.classify_news_articles(items, profile)


class ExplodingBriefWriter:
    """Brief 生成で例外を投げる。完成済みの結果が失われないことを確認する。"""

    def __init__(self, error: Exception | None = None) -> None:
        self._error = error or RuntimeError("brief writer blew up")

    @property
    def prompt_version(self) -> str:
        return "test-prompt"

    def write_brief(self, pack: Any) -> Any:
        raise self._error


class NullBriefWriter:
    """検証に落ちた想定で `None` を返す。"""

    @property
    def prompt_version(self) -> str:
        return "test-prompt"

    def write_brief(self, pack: Any) -> Any:
        return None


class ExplodingSerpApiClient:
    """想定外の例外を投げるクライアント。`FAILED` への遷移を確認する。"""

    def fetch(self, source: SourceName, profile: QueryProfile) -> dict[str, Any]:
        message = "unexpected failure"
        raise RuntimeError(message)


class FailingClassifier:
    """指定した種類の分類だけ失敗する分類器。"""

    def __init__(self, *, rising: bool = False, search: bool = False, news: bool = False) -> None:
        self._inner = StubLlmClient()
        self._rising = rising
        self._search = search
        self._news = news

    @property
    def classifier_version(self) -> str:
        return self._inner.classifier_version

    @property
    def prompt_version(self) -> str:
        return self._inner.prompt_version

    def classify_rising_queries(
        self, items: Sequence[RisingQuery], profile: QueryProfile
    ) -> list[PainClassification]:
        if self._rising:
            raise LlmResponseError("simulated total fallback")
        return self._inner.classify_rising_queries(items, profile)

    def classify_search_results(
        self, items: Sequence[SearchResultItem], profile: QueryProfile
    ) -> list[SolutionClassification]:
        if self._search:
            raise LlmResponseError("simulated total fallback")
        return self._inner.classify_search_results(items, profile)

    def classify_news_articles(
        self, items: Sequence[NewsArticle], profile: QueryProfile
    ) -> list[NewsClassification]:
        if self._news:
            raise LlmResponseError("simulated total fallback")
        return self._inner.classify_news_articles(items, profile)


class RecordingBriefWriter:
    """Brief 生成の呼び出しを記録する。"""

    def __init__(self, brief: Any | None = None) -> None:
        self.packs: list[Any] = []
        self._brief = brief
        self._inner = StubLlmClient()

    @property
    def prompt_version(self) -> str:
        return self._inner.prompt_version

    def write_brief(self, pack: Any) -> Any:
        self.packs.append(pack)
        if self._brief is not None:
            return self._brief
        return self._inner.write_brief(pack)


__all__ = [
    "SCAN_ID",
    "SCAN_TIME",
    "TOPIC",
    "Country",
    "ExplodingBriefWriter",
    "ExplodingSerpApiClient",
    "FailingClassifier",
    "FailingSerpApiClient",
    "FixtureOverrideClient",
    "NullBriefWriter",
    "RecordingBriefWriter",
    "RecordingSerpApiClient",
    "SerpApiResponseError",
    "ShortClassifier",
    "TrendsKillClient",
]
