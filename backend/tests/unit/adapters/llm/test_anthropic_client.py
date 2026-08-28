"""`anthropic_client.py` のテスト。

**実 API は呼ばない。** すべてフェイククライアントで検証する(API キーが無い前提)。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest
from pydantic import SecretStr

from gapatlas.adapters.llm.anthropic_client import (
    BRIEF_TOOL_NAME,
    CLASSIFICATION_TOOL_NAME,
    AnthropicLlmClient,
)
from gapatlas.adapters.llm.errors import LlmError, LlmRequestError, LlmResponseError
from gapatlas.config.settings import LlmMode, Settings
from gapatlas.domain.models.classification import (
    NewsRelevance,
    PainCategory,
    SolutionCategory,
)
from gapatlas.domain.models.normalized import NewsArticle, RisingQuery, SearchResultItem

FAKE_API_KEY = "test-anthropic-key-not-real"

RISING = [
    RisingQuery(query="care home waiting list", growth_percent=200.0),
    RisingQuery(query="carer shortage", growth_percent=280.0),
]
SEARCH = [SearchResultItem(position=1, title="t", link="https://example.com/")]
NEWS = [NewsArticle(position=1, title="Care home closures", link="https://example.com/n/")]


@dataclass
class FakeBlock:
    type: str
    name: str | None = None
    input: Any = None
    text: str | None = None


@dataclass
class FakeResponse:
    content: list[FakeBlock]


@dataclass
class FakeMessages:
    response: Any = None
    error: Exception | None = None
    calls: list[dict[str, Any]] = field(default_factory=list)

    def create(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return self.response


@dataclass
class FakeClient:
    messages: FakeMessages


def make_client(response=None, error=None) -> tuple[AnthropicLlmClient, FakeMessages]:
    messages = FakeMessages(response=response, error=error)
    settings = Settings(llm_mode=LlmMode.STUB, anthropic_model="claude-test-model")
    return AnthropicLlmClient(settings, client=FakeClient(messages=messages)), messages


def tool_response(payload: dict[str, Any], name: str = CLASSIFICATION_TOOL_NAME) -> FakeResponse:
    return FakeResponse(content=[FakeBlock(type="tool_use", name=name, input=payload)])


def text_response(text: str) -> FakeResponse:
    return FakeResponse(content=[FakeBlock(type="text", text=text)])


# --- (a) 正常系 -------------------------------------------------------------------------


def test_classifies_rising_queries(profile):
    payload = {
        "results": [
            {"index": 0, "classification": "WAIT_TIME", "confidence": 0.9},
            {"index": 1, "classification": "WORKFORCE", "confidence": 0.8},
        ]
    }
    client, _ = make_client(response=tool_response(payload))
    results = client.classify_rising_queries(RISING, profile)
    assert [item.classification for item in results] == [
        PainCategory.WAIT_TIME,
        PainCategory.WORKFORCE,
    ]
    assert [item.confidence for item in results] == [0.9, 0.8]


def test_classifies_search_results(profile):
    payload = {"results": [{"index": 0, "classification": "GOVERNMENT", "confidence": 0.7}]}
    client, _ = make_client(response=tool_response(payload))
    results = client.classify_search_results(SEARCH, profile)
    assert results[0].classification is SolutionCategory.GOVERNMENT


def test_classifies_news_articles(profile):
    payload = {"results": [{"index": 0, "classification": "RELATED", "confidence": 0.6}]}
    client, _ = make_client(response=tool_response(payload))
    results = client.classify_news_articles(NEWS, profile)
    assert results[0].classification is NewsRelevance.RELATED


_PARTIAL_RESULTS = {"results": [{"index": 0, "classification": "SHORTAGE", "confidence": 0.9}]}
"""index 0 だけ解決できる応答。全滅ではないので既定値の補完だけが起きる。"""


def _one_result(category: str) -> dict[str, object]:
    """index 0 だけを解決する応答を作る。全滅にならないようにするため。"""
    return {"results": [{"index": 0, "classification": category, "confidence": 0.9}]}


def test_forces_a_single_tool_and_uses_the_configured_model(profile):
    client, messages = make_client(response=tool_response(_PARTIAL_RESULTS))
    client.classify_rising_queries(RISING, profile)
    call = messages.calls[0]
    assert call["model"] == "claude-test-model"
    assert call["tool_choice"]["type"] == "tool"
    assert call["tool_choice"]["name"] == CLASSIFICATION_TOOL_NAME
    assert call["tool_choice"]["disable_parallel_tool_use"] is True
    assert len(call["tools"]) == 1


def test_the_request_carries_no_growth_position_or_date(profile):
    """プロンプトへ成長率・順位・日付を渡さない(分類をスコアへ汚染させないため)。"""
    calls = []
    for category, classify, items in [
        ("SHORTAGE", "classify_rising_queries", RISING),
        ("NEWS", "classify_search_results", SEARCH),
        ("RELATED", "classify_news_articles", NEWS),
    ]:
        client, messages = make_client(response=tool_response(_one_result(category)))
        getattr(client, classify)(items, profile)
        calls.extend(messages.calls)

    assert len(calls) == 3
    for call in calls:
        user_content = call["messages"][0]["content"]
        assert "growth" not in user_content
        assert "position" not in user_content
        assert "published_at" not in user_content


def test_missing_results_are_padded_to_the_input_length(profile):
    """一部だけ返ってきた場合、残りは既定値で埋めて入力と同数にする。"""
    client, _ = make_client(response=tool_response(_PARTIAL_RESULTS))
    results = client.classify_rising_queries(RISING, profile)
    assert len(results) == len(RISING)
    assert results[0].classification is PainCategory.SHORTAGE
    assert all(item.classification is PainCategory.NEUTRAL for item in results[1:])
    assert all(item.confidence == 0.0 for item in results[1:])


def test_a_total_fallback_raises_instead_of_returning_defaults(profile):
    """1件も分類できなければ例外にする。

    既定値で全件を埋めた結果を返すと、`pain = 0` や `solution_gap = 100` が
    実際の観測値としてスコアへ入り、Confidence にも反映されない
    (docs/llm-prompts.md「分類が全滅した場合、その成分は None(欠損)として扱う」)。
    """
    client, _ = make_client(response=tool_response({"results": []}))
    with pytest.raises(LlmResponseError):
        client.classify_rising_queries(RISING, profile)


def test_a_text_only_response_is_parsed_strictly(profile):
    client, _ = make_client(
        response=text_response('{"results": [{"index": 0, "classification": "COST"}]}')
    )
    results = client.classify_rising_queries(RISING, profile)
    assert results[0].classification is PainCategory.COST


# --- (b) API 例外 ------------------------------------------------------------------------


def test_api_error_becomes_llm_request_error(profile):
    client, _ = make_client(error=RuntimeError("connection reset"))
    with pytest.raises(LlmRequestError):
        client.classify_rising_queries(RISING, profile)


def test_api_error_is_chained_but_not_inlined(profile):
    client, _ = make_client(error=RuntimeError("connection reset"))
    with pytest.raises(LlmRequestError) as excinfo:
        client.classify_rising_queries(RISING, profile)
    assert "RuntimeError" in str(excinfo.value)
    assert "connection reset" not in str(excinfo.value)
    assert isinstance(excinfo.value.__cause__, RuntimeError)


# --- (c) 壊れた応答 ----------------------------------------------------------------------


def test_broken_json_text_becomes_llm_response_error(profile):
    client, _ = make_client(response=text_response('{"results": ['))
    with pytest.raises(LlmResponseError):
        client.classify_rising_queries(RISING, profile)


def test_an_empty_response_becomes_llm_response_error(profile):
    client, _ = make_client(response=FakeResponse(content=[]))
    with pytest.raises(LlmResponseError):
        client.classify_rising_queries(RISING, profile)


def test_a_response_without_content_becomes_llm_response_error(profile):
    client, _ = make_client(response=object())
    with pytest.raises(LlmResponseError):
        client.classify_rising_queries(RISING, profile)


def test_a_non_object_tool_input_becomes_llm_response_error(profile):
    client, _ = make_client(
        response=FakeResponse(
            content=[FakeBlock(type="tool_use", name=CLASSIFICATION_TOOL_NAME, input="oops")]
        )
    )
    with pytest.raises(LlmResponseError):
        client.classify_rising_queries(RISING, profile)


# --- (d) API キーが漏れない ---------------------------------------------------------------


def test_api_key_never_appears_in_exception_messages(profile):
    settings = Settings(llm_mode=LlmMode.ANTHROPIC, anthropic_api_key=SecretStr(FAKE_API_KEY))
    messages = FakeMessages(error=RuntimeError(f"auth failed for {FAKE_API_KEY}"))
    client = AnthropicLlmClient(settings, client=FakeClient(messages=messages))
    with pytest.raises(LlmRequestError) as excinfo:
        client.classify_rising_queries(RISING, profile)
    assert FAKE_API_KEY not in str(excinfo.value)
    assert FAKE_API_KEY not in repr(excinfo.value)


def test_a_missing_api_key_raises_llm_error_without_the_key_name_value():
    settings = Settings(llm_mode=LlmMode.STUB, anthropic_api_key=None)
    with pytest.raises(LlmError) as excinfo:
        AnthropicLlmClient(settings)
    assert "ANTHROPIC_API_KEY is required" in str(excinfo.value)


# --- Opportunity Brief -------------------------------------------------------------------


def brief_payload() -> dict[str, Any]:
    return {
        "why_now": "Demand accelerated [E1].",
        "what_people_are_struggling_with": "Shortage queries increased [E2].",
        "visible_solutions": "Few direct providers appeared [E1].",
        "what_this_does_not_prove": "This is a search-visible signal, not actual supply.",
        "next_validation": "Check official statistics.",
        "cited_evidence_ids": ["E1"],
    }


def test_write_brief_returns_a_validated_brief(pack):
    client, messages = make_client(response=tool_response(brief_payload(), BRIEF_TOOL_NAME))
    brief = client.write_brief(pack)
    assert brief is not None
    assert brief.cited_evidence_ids == ["E1", "E2"]
    assert messages.calls[0]["tool_choice"]["name"] == BRIEF_TOOL_NAME


def test_write_brief_returns_none_on_api_error(pack):
    client, _ = make_client(error=RuntimeError("boom"))
    assert client.write_brief(pack) is None


def test_write_brief_returns_none_on_broken_json(pack):
    client, _ = make_client(response=text_response("{"))
    assert client.write_brief(pack) is None


def test_write_brief_returns_none_when_a_field_is_missing(pack):
    payload = brief_payload()
    del payload["next_validation"]
    client, _ = make_client(response=tool_response(payload, BRIEF_TOOL_NAME))
    assert client.write_brief(pack) is None


def test_write_brief_returns_none_when_validation_fails(pack):
    payload = brief_payload()
    payload["why_now"] = "Demand accelerated."
    client, _ = make_client(response=tool_response(payload, BRIEF_TOOL_NAME))
    assert client.write_brief(pack) is None


def test_write_brief_strips_a_generated_url(pack):
    payload = brief_payload()
    payload["visible_solutions"] = "See https://example.com/x for providers [E1]."
    client, _ = make_client(response=tool_response(payload, BRIEF_TOOL_NAME))
    brief = client.write_brief(pack)
    assert brief is not None
    assert "https://" not in brief.visible_solutions
