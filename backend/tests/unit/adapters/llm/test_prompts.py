"""`prompts.py` のテスト。

**LLM へ渡してはいけないもの**が本当に渡っていないことを検証する
(docs/llm-prompts.md 1〜3章)。

- rising query に成長率を渡さない
- 検索結果に `position` を渡さない
- ニュースに日付を渡さない
"""

from __future__ import annotations

from datetime import UTC, datetime

from gapatlas.adapters.llm.prompts import (
    SYSTEM_PROMPT_BRIEF,
    SYSTEM_PROMPT_NEWS_ARTICLES,
    SYSTEM_PROMPT_RISING_QUERIES,
    SYSTEM_PROMPT_SEARCH_RESULTS,
    build_brief_prompt,
    build_evidence_pack_payload,
    build_news_article_payload,
    build_news_article_prompt,
    build_rising_query_payload,
    build_rising_query_prompt,
    build_search_result_payload,
    build_search_result_prompt,
)
from gapatlas.domain.models.normalized import NewsArticle, RisingQuery, SearchResultItem

RISING = [
    RisingQuery(query="care home waiting list", growth_percent=1234.0, raw_value="+1,234%"),
    RisingQuery(
        query="no carers available", growth_percent=5000.0, is_breakout=True, raw_value="Breakout"
    ),
]

SEARCH = [
    SearchResultItem(
        position=7,
        title="Adult social care",
        link="https://council.example.co.uk/adult-social-care/",
        snippet="Council page about home care.",
        displayed_link="council.example.co.uk",
        source="Example Council",
    )
]

NEWS = [
    NewsArticle(
        position=3,
        title="Care home closures leave rural areas without beds",
        link="https://news.example.co.uk/closures/",
        source_name="Example Daily Report",
        published_at=datetime(2026, 8, 20, 9, 30, tzinfo=UTC),
        raw_date="08/20/2026, 09:30 AM, +0000 UTC",
    )
]


def test_rising_query_payload_omits_growth():
    payload = build_rising_query_payload(RISING)
    assert payload == [
        {"index": 0, "query": "care home waiting list"},
        {"index": 1, "query": "no carers available"},
    ]
    for entry in payload:
        assert set(entry) == {"index", "query"}


def test_rising_query_prompt_contains_no_growth_signal(profile):
    prompt = build_rising_query_prompt(RISING, profile)
    for forbidden in ("1234", "+1,234%", "5000", "Breakout", "growth", "is_breakout"):
        assert forbidden not in prompt


def test_search_result_payload_omits_position():
    payload = build_search_result_payload(SEARCH)
    assert "position" not in payload[0]
    assert set(payload[0]) == {"index", "title", "link", "snippet", "displayed_link"}


def test_search_result_prompt_contains_no_position(profile):
    prompt = build_search_result_prompt(SEARCH, profile)
    assert "position" not in prompt
    assert '"index": 0' in prompt


def test_search_result_payload_omits_absent_optional_fields():
    minimal = [SearchResultItem(position=1, title="t", link="https://example.com/")]
    assert build_search_result_payload(minimal) == [
        {"index": 0, "title": "t", "link": "https://example.com/"}
    ]


def test_news_payload_omits_dates():
    payload = build_news_article_payload(NEWS)
    assert payload == [
        {
            "index": 0,
            "title": "Care home closures leave rural areas without beds",
            "source_name": "Example Daily Report",
        }
    ]
    assert "position" not in payload[0]


def test_news_prompt_contains_no_date(profile):
    prompt = build_news_article_prompt(NEWS, profile)
    for forbidden in ("2026", "08/20", "09:30", "published_at", "iso_date", "raw_date"):
        assert forbidden not in prompt


def test_prompts_state_the_country_and_language(profile):
    for prompt in (
        build_rising_query_prompt(RISING, profile),
        build_search_result_prompt(SEARCH, profile),
        build_news_article_prompt(NEWS, profile),
    ):
        assert profile.country.value in prompt
        assert profile.language in prompt


def test_system_prompts_forbid_scoring():
    for prompt in (
        SYSTEM_PROMPT_RISING_QUERIES,
        SYSTEM_PROMPT_SEARCH_RESULTS,
        SYSTEM_PROMPT_NEWS_ARTICLES,
    ):
        assert "You are a classifier" in prompt
        assert "must not compute, estimate, rank" in prompt
        assert '"results"' in prompt


def test_system_prompts_state_the_fallback_category():
    assert "choose NEUTRAL and lower the confidence" in SYSTEM_PROMPT_RISING_QUERIES
    assert "choose OTHER and lower the confidence" in SYSTEM_PROMPT_SEARCH_RESULTS
    assert "choose RELATED and lower the confidence" in SYSTEM_PROMPT_NEWS_ARTICLES


def test_system_prompts_use_a_single_example():
    for prompt in (
        SYSTEM_PROMPT_RISING_QUERIES,
        SYSTEM_PROMPT_SEARCH_RESULTS,
        SYSTEM_PROMPT_NEWS_ARTICLES,
    ):
        assert prompt.count("Example input:") == 1


def test_brief_system_prompt_states_every_hard_rule():
    for rule in (
        "Do not state any fact that is not in the evidence pack",
        "Do not invent, derive, or restate new numbers",
        "Do not write any URL",
        "Avoid assertions",
        "what_this_does_not_prove must never be empty",
    ):
        assert rule in SYSTEM_PROMPT_BRIEF


def test_brief_payload_carries_only_the_evidence_pack(pack):
    payload = build_evidence_pack_payload(pack)
    assert set(payload) == {
        "country",
        "topic",
        "need_gap_score",
        "confidence",
        "components",
        "evidence",
        "limitations",
    }
    assert payload["evidence"][0]["id"] == "E1"
    assert "url" not in payload["evidence"][0]


def test_brief_prompt_contains_no_url(pack):
    prompt = build_brief_prompt(pack)
    assert "http://" not in prompt
    assert "https://" not in prompt
