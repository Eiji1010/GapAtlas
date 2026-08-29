"""`cache.py` のテスト。

同じ入力に同じ結果を返し、内側のクライアントが2回目に呼ばれないこと。
"""

from __future__ import annotations

from collections.abc import Sequence

import pytest

from gapatlas.adapters.llm.cache import (
    CachingBriefWriter,
    CachingLlmClassifier,
    build_cache_key,
)
from gapatlas.adapters.llm.models import BriefComponents, EvidencePack, EvidenceSummary
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
from gapatlas.domain.models.common import Country, SourceName, TopicId
from gapatlas.domain.models.normalized import NewsArticle, RisingQuery, SearchResultItem
from gapatlas.domain.models.query_profile import QueryProfile
from gapatlas.domain.models.result import OpportunityBrief

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


# --------------------------------------------------------------------------
# Opportunity Brief のキャッシュ(docs/requirements.md「AI Insight」)
# --------------------------------------------------------------------------


class CountingBriefWriter:
    """呼び出し回数を数え、毎回違う文面を返す(実 LLM の非決定性を模す)。"""

    def __init__(self) -> None:
        self.calls = 0

    @property
    def prompt_version(self) -> str:
        return "counting-prompt"

    def write_brief(self, pack: EvidencePack) -> OpportunityBrief:
        self.calls += 1
        return OpportunityBrief(
            why_now=f"call {self.calls} [E1]",
            what_people_are_struggling_with="x [E1]",
            visible_solutions="y [E1]",
            what_this_does_not_prove="検索上の可視性であり実際の供給量ではない",
            next_validation="一次調査",
            cited_evidence_ids=["E1"],
        )


def _pack(country: Country = Country.JP, summary: str = "需要が上昇") -> EvidencePack:
    return EvidencePack(
        country=country,
        topic_id=TopicId.ELDER_CARE,
        need_gap_score=75,
        confidence=91,
        components=BriefComponents(demand=85, pain=73, solution_gap=65, news_urgency=63),
        evidence=[EvidenceSummary(id="E1", source=SourceName.TRENDS, summary=summary)],
        limitations=["検索上の可視性であり実際の供給量ではない"],
    )


def test_the_same_evidence_returns_the_same_brief():
    """同じ根拠なら同じ Brief。

    Worker の「最後の1国」判定が競合すると確定処理が2回走りうる。実 LLM は
    決定的でないため、キャッシュが無いと2回目が別の文面で上書きする。
    """
    inner = CountingBriefWriter()
    writer = CachingBriefWriter(inner)

    first = writer.write_brief(_pack())
    second = writer.write_brief(_pack())

    assert inner.calls == 1
    assert first == second


def test_different_evidence_is_not_served_from_the_cache():
    inner = CountingBriefWriter()
    writer = CachingBriefWriter(inner)
    writer.write_brief(_pack(summary="需要が上昇"))
    writer.write_brief(_pack(summary="需要が低下"))
    assert inner.calls == 2


def test_a_different_country_is_not_served_from_the_cache():
    inner = CountingBriefWriter()
    writer = CachingBriefWriter(inner)
    writer.write_brief(_pack(Country.JP))
    writer.write_brief(_pack(Country.US))
    assert inner.calls == 2


def test_a_none_result_is_cached_too():
    """生成しない判断もキャッシュする(同じ入力なら同じ結果になるため)。"""

    class NullWriter:
        def __init__(self) -> None:
            self.calls = 0

        @property
        def prompt_version(self) -> str:
            return "null"

        def write_brief(self, pack: EvidencePack) -> OpportunityBrief | None:
            del pack
            self.calls += 1
            return None

    inner = NullWriter()
    writer = CachingBriefWriter(inner)
    assert writer.write_brief(_pack()) is None
    assert writer.write_brief(_pack()) is None
    assert inner.calls == 1


def test_the_prompt_version_is_delegated():
    assert CachingBriefWriter(CountingBriefWriter()).prompt_version == "counting-prompt"
