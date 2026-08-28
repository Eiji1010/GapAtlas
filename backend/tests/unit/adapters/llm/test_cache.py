"""`cache.py` のテスト。

同じ入力に同じ結果を返し、内側のクライアントが2回目に呼ばれないこと。
"""

from __future__ import annotations

from collections.abc import Sequence

import pytest

from gapatlas.adapters.llm.cache import CachingLlmClassifier, build_cache_key
from gapatlas.adapters.llm.prompts import build_rising_query_payload
from gapatlas.adapters.llm.stub_client import StubLlmClient
from gapatlas.domain.models.classification import (
    NewsClassification,
    NewsRelevance,
    PainCategory,
    PainClassification,
    SolutionCategory,
    SolutionClassification,
)
from gapatlas.domain.models.normalized import NewsArticle, RisingQuery, SearchResultItem
from gapatlas.domain.models.query_profile import QueryProfile

RISING = [RisingQuery(query="care home waiting list", growth_percent=200.0)]
OTHER_RISING = [RisingQuery(query="carer shortage", growth_percent=200.0)]
SEARCH = [SearchResultItem(position=1, title="t", link="https://example.com/")]
NEWS = [NewsArticle(position=1, title="Care home closures", link="https://example.com/n/")]


class CountingClassifier:
    """呼び出し回数を数えるだけの内側クライアント。"""

    def __init__(self) -> None:
        self.rising_calls = 0
        self.search_calls = 0
        self.news_calls = 0

    @property
    def classifier_version(self) -> str:
        return "counting-classifier"

    @property
    def prompt_version(self) -> str:
        return "counting-prompt"

    def classify_rising_queries(
        self, items: Sequence[RisingQuery], profile: QueryProfile
    ) -> list[PainClassification]:
        del profile
        self.rising_calls += 1
        return [
            PainClassification(classification=PainCategory.SHORTAGE, confidence=0.5) for _ in items
        ]

    def classify_search_results(
        self, items: Sequence[SearchResultItem], profile: QueryProfile
    ) -> list[SolutionClassification]:
        del profile
        self.search_calls += 1
        return [
            SolutionClassification(classification=SolutionCategory.NEWS, confidence=0.5)
            for _ in items
        ]

    def classify_news_articles(
        self, items: Sequence[NewsArticle], profile: QueryProfile
    ) -> list[NewsClassification]:
        del profile
        self.news_calls += 1
        return [
            NewsClassification(classification=NewsRelevance.RELATED, confidence=0.5) for _ in items
        ]


@pytest.fixture
def inner() -> CountingClassifier:
    return CountingClassifier()


def test_second_identical_call_does_not_reach_the_inner_client(inner, profile):
    cached = CachingLlmClassifier(inner)
    first = cached.classify_rising_queries(RISING, profile)
    second = cached.classify_rising_queries(RISING, profile)
    assert inner.rising_calls == 1
    assert first == second


def test_each_source_has_its_own_cache(inner, profile):
    cached = CachingLlmClassifier(inner)
    for _ in range(2):
        cached.classify_rising_queries(RISING, profile)
        cached.classify_search_results(SEARCH, profile)
        cached.classify_news_articles(NEWS, profile)
    assert (inner.rising_calls, inner.search_calls, inner.news_calls) == (1, 1, 1)


def test_different_input_is_not_served_from_the_cache(inner, profile):
    cached = CachingLlmClassifier(inner)
    cached.classify_rising_queries(RISING, profile)
    cached.classify_rising_queries(OTHER_RISING, profile)
    assert inner.rising_calls == 2


def test_a_different_query_profile_version_changes_the_key(inner, make_query_profile):
    cached = CachingLlmClassifier(inner)
    cached.classify_rising_queries(RISING, make_query_profile(version="v1"))
    cached.classify_rising_queries(RISING, make_query_profile(version="v2"))
    assert inner.rising_calls == 2


def test_cache_key_changes_with_the_query_profile_version(make_query_profile):
    payload = build_rising_query_payload(RISING)
    first = build_cache_key("rising_queries", payload, make_query_profile(version="v1"))
    second = build_cache_key("rising_queries", payload, make_query_profile(version="v2"))
    assert first != second


def test_cache_key_is_stable_for_the_same_input(profile):
    payload = build_rising_query_payload(RISING)
    assert build_cache_key("rising_queries", payload, profile) == build_cache_key(
        "rising_queries", payload, profile
    )


def test_cache_key_is_a_sha256_hex_digest(profile):
    key = build_cache_key("rising_queries", build_rising_query_payload(RISING), profile)
    assert len(key) == 64
    assert all(character in "0123456789abcdef" for character in key)


def test_cache_key_separates_the_source_kind(profile):
    payload = build_rising_query_payload(RISING)
    assert build_cache_key("rising_queries", payload, profile) != build_cache_key(
        "news_articles", payload, profile
    )


def test_returned_list_can_be_mutated_without_corrupting_the_cache(inner, profile):
    cached = CachingLlmClassifier(inner)
    first = cached.classify_rising_queries(RISING, profile)
    first.clear()
    assert len(cached.classify_rising_queries(RISING, profile)) == len(RISING)
    assert inner.rising_calls == 1


def test_wrapping_the_stub_preserves_its_results(profile):
    stub = StubLlmClient()
    cached = CachingLlmClassifier(stub)
    assert cached.classify_rising_queries(RISING, profile) == stub.classify_rising_queries(
        RISING, profile
    )
