"""SerpApi キャッシュのテスト。

正本は docs/requirements.md「Cache」の TTL 表と
「**Cache Hit の場合は SerpApi を再度呼ばない**」。
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from gapatlas.adapters.serpapi.cache import (
    HOUR_SECONDS,
    SOURCE_TTL_SECONDS,
    CachingSerpApiClient,
    InMemoryCacheStore,
    build_cache_key,
    cache_age_seconds,
)
from gapatlas.adapters.serpapi.errors import SerpApiStatusError
from gapatlas.adapters.serpapi.fixture_client import FixtureSerpApiClient
from gapatlas.config.query_profile_loader import load_query_profile
from gapatlas.domain.models.common import Country, SourceName, TopicId
from gapatlas.domain.models.query_profile import QueryProfile

START = datetime(2026, 8, 28, tzinfo=UTC)


class CountingClient:
    """呼び出し回数を数えるだけの内側クライアント。"""

    def __init__(self) -> None:
        self.calls: list[tuple[SourceName, Country]] = []

    def fetch(self, source: SourceName, profile: QueryProfile) -> dict[str, Any]:
        self.calls.append((source, profile.country))
        return {"source": source.value, "country": profile.country.value}


class ExplodingClient:
    def fetch(self, source: SourceName, profile: QueryProfile) -> dict[str, Any]:
        del profile
        message = f"boom for {source.value}"
        raise SerpApiStatusError(message, status_code=503)


class Clock:
    def __init__(self, start: datetime = START) -> None:
        self.now = start

    def __call__(self) -> datetime:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += timedelta(seconds=seconds)


@pytest.fixture
def profile() -> QueryProfile:
    return load_query_profile(TopicId.ELDER_CARE, Country.JP)


def _client(inner: Any, clock: Clock) -> CachingSerpApiClient:
    return CachingSerpApiClient(inner, store=InMemoryCacheStore(), now=clock)


def test_the_documented_ttls_are_used():
    """docs/requirements.md「Cache」の表と一致すること。**リテラルで固定する。**"""
    assert SOURCE_TTL_SECONDS[SourceName.TRENDS] == 6 * HOUR_SECONDS
    assert SOURCE_TTL_SECONDS[SourceName.RELATED_QUERIES] == 6 * HOUR_SECONDS
    assert SOURCE_TTL_SECONDS[SourceName.SEARCH] == 6 * HOUR_SECONDS
    assert SOURCE_TTL_SECONDS[SourceName.NEWS] == 1 * HOUR_SECONDS
    assert SOURCE_TTL_SECONDS[SourceName.MAPS] == 24 * HOUR_SECONDS
    assert set(SOURCE_TTL_SECONDS) == set(SourceName)


def test_a_cache_hit_does_not_call_serpapi_again(profile):
    inner = CountingClient()
    client = _client(inner, Clock())

    first = client.fetch(SourceName.SEARCH, profile)
    second = client.fetch(SourceName.SEARCH, profile)

    assert first == second
    assert len(inner.calls) == 1


@pytest.mark.parametrize("source", list(SourceName))
def test_the_entry_expires_exactly_at_the_ttl(source, profile):
    inner = CountingClient()
    clock = Clock()
    client = _client(inner, clock)

    client.fetch(source, profile)
    clock.advance(SOURCE_TTL_SECONDS[source] - 1)
    client.fetch(source, profile)
    assert len(inner.calls) == 1

    clock.advance(1)  # ちょうど TTL
    client.fetch(source, profile)
    assert len(inner.calls) == 2


def test_news_expires_before_trends(profile):
    """News は 1h、Trends は 6h(docs/requirements.md)。"""
    inner = CountingClient()
    clock = Clock()
    client = _client(inner, clock)

    client.fetch(SourceName.NEWS, profile)
    client.fetch(SourceName.TRENDS, profile)
    clock.advance(2 * HOUR_SECONDS)
    client.fetch(SourceName.NEWS, profile)
    client.fetch(SourceName.TRENDS, profile)

    sources = [source for source, _country in inner.calls]
    assert sources.count(SourceName.NEWS) == 2
    assert sources.count(SourceName.TRENDS) == 1


def test_different_countries_do_not_share_an_entry(profile):
    inner = CountingClient()
    client = _client(inner, Clock())

    client.fetch(SourceName.SEARCH, profile)
    client.fetch(SourceName.SEARCH, load_query_profile(TopicId.ELDER_CARE, Country.US))
    assert len(inner.calls) == 2


def test_the_key_includes_the_query_profile_version(profile):
    """docs/architecture.md「キャッシュキーには query_profile_version を含める」。"""
    other = profile.model_copy(update={"version": "elder-care-jp-v99"})
    assert build_cache_key(SourceName.SEARCH, profile) != build_cache_key(SourceName.SEARCH, other)


def test_the_key_changes_when_the_query_changes(profile):
    """版を上げ忘れてクエリだけ変えても取り違えない。"""
    other = profile.model_copy(update={"solution_query": ["別のクエリ"]})
    assert build_cache_key(SourceName.SEARCH, profile) != build_cache_key(SourceName.SEARCH, other)


def test_sources_do_not_share_an_entry(profile):
    keys = {build_cache_key(source, profile) for source in SourceName}
    assert len(keys) == len(SourceName)


def test_failures_are_not_cached(profile):
    """1回の失敗を TTL のあいだ引きずらない。"""
    client = _client(ExplodingClient(), Clock())
    with pytest.raises(SerpApiStatusError):
        client.fetch(SourceName.SEARCH, profile)
    with pytest.raises(SerpApiStatusError):
        client.fetch(SourceName.SEARCH, profile)


def test_cache_age_is_zero_on_a_fresh_fetch(profile):
    client = _client(CountingClient(), Clock())
    client.fetch(SourceName.SEARCH, profile)
    assert client.cache_age_seconds(SourceName.SEARCH, profile) == 0.0


def test_cache_age_reports_the_elapsed_time_on_a_hit(profile):
    """Freshness がキャッシュ経過時間を使う(docs/scoring.md 6章)。"""
    clock = Clock()
    client = _client(CountingClient(), clock)
    client.fetch(SourceName.SEARCH, profile)
    clock.advance(3 * HOUR_SECONDS)
    client.fetch(SourceName.SEARCH, profile)

    assert client.cache_age_seconds(SourceName.SEARCH, profile) == 3 * HOUR_SECONDS


def test_the_helper_returns_zero_for_a_client_without_a_cache(profile):
    """fixture / live の素の実装ではキャッシュ経過時間は 0。"""
    assert cache_age_seconds(FixtureSerpApiClient(), SourceName.SEARCH, profile) == 0.0


def test_the_helper_reads_the_age_from_a_caching_client(profile):
    clock = Clock()
    client = _client(CountingClient(), clock)
    client.fetch(SourceName.NEWS, profile)
    clock.advance(600)
    client.fetch(SourceName.NEWS, profile)

    assert cache_age_seconds(client, SourceName.NEWS, profile) == 600.0


def test_a_cached_payload_is_returned_unchanged(profile):
    """fixture の内容がキャッシュ経由でも変わらないこと。"""
    inner = FixtureSerpApiClient()
    client = _client(inner, Clock())

    direct = inner.fetch(SourceName.TRENDS, profile)
    cached = client.fetch(SourceName.TRENDS, profile)
    assert cached == direct
    assert client.fetch(SourceName.TRENDS, profile) == direct
