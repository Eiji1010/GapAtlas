"""`stub_client.py` のテスト。

docs/llm-prompts.md「stub モードの要件」を検証する。

- ネットワークに一切アクセスしない
- 同じ入力に対して常に同じ出力を返す
- すべて同じカテゴリ・同じ confidence を返すような無意味な stub でない
"""

from __future__ import annotations

import inspect
from datetime import UTC, datetime

import pytest

from gapatlas.adapters.llm import stub_client
from gapatlas.adapters.llm.brief_validation import validate_brief
from gapatlas.adapters.llm.stub_client import StubLlmClient
from gapatlas.domain.models.classification import (
    NewsRelevance,
    PainCategory,
    SolutionCategory,
)
from gapatlas.domain.models.normalized import NewsArticle, RisingQuery, SearchResultItem

RISING = [
    RisingQuery(query="care home waiting list", growth_percent=200.0),
    RisingQuery(query="no carers available in my area", growth_percent=5000.0, is_breakout=True),
    RisingQuery(query="carer shortage", growth_percent=280.0),
    RisingQuery(query="care home fees per week", growth_percent=120.0),
    RisingQuery(query="care home poor inspection rating", growth_percent=55.0),
    RisingQuery(query="rural care home access", growth_percent=65.0),
    RisingQuery(query="what is social care", growth_percent=30.0),
]

SEARCH = [
    SearchResultItem(
        position=1,
        title="Adult social care and support | Example Borough Council",
        link="https://council.example.co.uk/adult-social-care/",
        snippet="Council page describing home care.",
    ),
    SearchResultItem(
        position=2,
        title="Search care homes near you | Example Care Directory",
        link="https://directory.example.co.uk/search/",
        snippet="Directory listing providers with vacancies.",
    ),
    SearchResultItem(
        position=3,
        title="Home care visits | Example Willow Home Care",
        link="https://willowcare.example.co.uk/",
        snippet="Domiciliary care agency providing personal care visits.",
    ),
    SearchResultItem(
        position=4,
        title="Types of elderly care explained | Example Care Advice",
        link="https://advice.example.co.uk/elderly-care-types/",
        snippet="Advice article comparing residential care and home care.",
    ),
    SearchResultItem(
        position=5,
        title="Councils warn of rising waiting lists | Example Daily Report",
        link="https://news.example.co.uk/social-care-waiting-lists/",
    ),
    SearchResultItem(
        position=6,
        title="Elder care - community discussion thread | Example Forum",
        link="https://forum.example.co.uk/threads/elder-care/",
    ),
]

NEWS = [
    NewsArticle(
        position=1,
        title="Care providers hand back contracts as staff shortages bite",
        link="https://news.example.co.uk/1/",
        source_name="Example Daily Report",
        published_at=datetime(2026, 8, 20, tzinfo=UTC),
    ),
    NewsArticle(
        position=2,
        title="Council social care budgets face record overspend",
        link="https://news.example.co.uk/2/",
        source_name="Example Local Government News",
    ),
    NewsArticle(
        position=3,
        title="Cricket final draws record television audience",
        link="https://news.example.co.uk/3/",
        source_name="Example Sports Wire",
    ),
]


@pytest.fixture
def client() -> StubLlmClient:
    return StubLlmClient()


def test_source_makes_no_network_calls():
    """stub のソースにネットワーク系ライブラリが現れないこと。"""
    source = inspect.getsource(stub_client)
    for forbidden in ("httpx", "requests", "anthropic", "urllib", "socket", "boto3"):
        assert forbidden not in source


def test_rising_query_classification_is_deterministic(client, profile):
    first = client.classify_rising_queries(RISING, profile)
    second = client.classify_rising_queries(RISING, profile)
    assert first == second


def test_search_result_classification_is_deterministic(client, profile):
    assert client.classify_search_results(SEARCH, profile) == client.classify_search_results(
        SEARCH, profile
    )


def test_news_classification_is_deterministic(client, profile):
    assert client.classify_news_articles(NEWS, profile) == client.classify_news_articles(
        NEWS, profile
    )


def test_a_fresh_instance_returns_the_same_result(profile):
    assert StubLlmClient().classify_rising_queries(
        RISING, profile
    ) == StubLlmClient().classify_rising_queries(RISING, profile)


def test_results_have_the_same_length_and_order_as_the_input(client, profile):
    assert len(client.classify_rising_queries(RISING, profile)) == len(RISING)
    assert len(client.classify_search_results(SEARCH, profile)) == len(SEARCH)
    assert len(client.classify_news_articles(NEWS, profile)) == len(NEWS)


def test_empty_input_returns_an_empty_list(client, profile):
    assert client.classify_rising_queries([], profile) == []
    assert client.classify_search_results([], profile) == []
    assert client.classify_news_articles([], profile) == []


def test_rising_queries_are_not_all_neutral(client, profile):
    results = client.classify_rising_queries(RISING, profile)
    categories = {result.classification for result in results}
    assert PainCategory.NEUTRAL in categories
    assert len(categories) >= 5


def test_search_results_are_not_all_one_category(client, profile):
    categories = {
        result.classification for result in client.classify_search_results(SEARCH, profile)
    }
    assert len(categories) >= 5


def test_news_results_are_not_all_one_category(client, profile):
    categories = {result.classification for result in client.classify_news_articles(NEWS, profile)}
    assert categories == {
        NewsRelevance.DIRECTLY_RELEVANT,
        NewsRelevance.RELATED,
        NewsRelevance.UNRELATED,
    }


def test_confidence_is_not_a_fixed_value(client, profile):
    confidences = {result.confidence for result in client.classify_rising_queries(RISING, profile)}
    confidences |= {result.confidence for result in client.classify_search_results(SEARCH, profile)}
    confidences |= {result.confidence for result in client.classify_news_articles(NEWS, profile)}
    assert len(confidences) >= 3
    assert 1.0 not in confidences


def test_specific_rules_produce_the_expected_categories(client, profile):
    pain = [result.classification for result in client.classify_rising_queries(RISING, profile)]
    assert pain == [
        PainCategory.WAIT_TIME,
        PainCategory.SHORTAGE,
        PainCategory.WORKFORCE,
        PainCategory.COST,
        PainCategory.QUALITY,
        PainCategory.ACCESS,
        PainCategory.NEUTRAL,
    ]
    solution = [result.classification for result in client.classify_search_results(SEARCH, profile)]
    assert solution == [
        SolutionCategory.GOVERNMENT,
        SolutionCategory.MARKETPLACE,
        SolutionCategory.DIRECT_PROVIDER,
        SolutionCategory.INFORMATION,
        SolutionCategory.NEWS,
        SolutionCategory.OTHER,
    ]


def test_fallback_uses_a_lower_confidence_than_an_explicit_match(client, profile):
    results = client.classify_rising_queries(RISING, profile)
    neutral = results[-1]
    explicit = results[0]
    assert neutral.confidence < explicit.confidence


def test_write_brief_cites_every_evidence_id(make_evidence_pack):
    brief = StubLlmClient().write_brief(make_evidence_pack(evidence_count=4))
    assert brief is not None
    assert brief.cited_evidence_ids == ["E1", "E2", "E3", "E4"]
    for evidence_id in ("E1", "E2", "E3", "E4"):
        assert f"[{evidence_id}]" in brief.why_now


def test_write_brief_is_deterministic(make_evidence_pack):
    pack = make_evidence_pack(evidence_count=3)
    assert StubLlmClient().write_brief(pack) == StubLlmClient().write_brief(pack)


def test_write_brief_contains_no_url(make_evidence_pack):
    brief = StubLlmClient().write_brief(make_evidence_pack())
    assert brief is not None
    for section in brief.model_dump().values():
        assert "http://" not in str(section)
        assert "https://" not in str(section)


def test_write_brief_states_a_methodology_limitation(make_evidence_pack):
    brief = StubLlmClient().write_brief(make_evidence_pack())
    assert brief is not None
    assert "search-visible" in brief.what_this_does_not_prove
    assert "severity" in brief.what_this_does_not_prove


def test_write_brief_passes_its_own_validation(make_evidence_pack):
    pack = make_evidence_pack(evidence_count=3)
    brief = StubLlmClient().write_brief(pack)
    assert brief is not None
    assert validate_brief(brief, pack) is not None


def test_write_brief_returns_none_without_evidence(make_evidence_pack):
    assert StubLlmClient().write_brief(make_evidence_pack(evidence_count=0)) is None
