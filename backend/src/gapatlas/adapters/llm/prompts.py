"""分類と Opportunity Brief のプロンプト。

正本は docs/llm-prompts.md 1〜4章。

**このファイルのプロンプト文面を変更したら `versions.PROMPT_VERSION` を上げること。**
モデル ID を変えた場合も同様(docs/llm-prompts.md「バージョン管理」)。文面を変えたのに
バージョンを据え置くと、過去の結果を再現できなくなる。

LLM へ渡してはいけないもの(意図的な省略):

- rising query の**成長率**。重要度を判断させるとスコアが分類へ汚染される
- 検索結果の **`position`**。順位重みはコード側(`domain/scoring`)で計算する
- ニュースの**日付**。recency はコード側で `iso_date` から計算する
  (Google News に `snippet` は存在しないため `title` と `source.name` のみ渡す)
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Final

from gapatlas.adapters.llm.models import EvidencePack
from gapatlas.domain.models.normalized import NewsArticle, RisingQuery, SearchResultItem
from gapatlas.domain.models.query_profile import QueryProfile

JsonValue = str | int | None
ItemPayload = dict[str, JsonValue]

_RESPONSE_CONTRACT: Final[str] = """\
Return one result per input item, using the item's "index" value.
Output must be structured JSON of exactly this shape and nothing else:
{"results": [{"index": <int>, "classification": "<CATEGORY>", "confidence": <0.0-1.0>}]}
Never embed the JSON inside prose. Never add fields. Never reorder or drop items."""

_NO_SCORING_RULE: Final[str] = """\
You are a classifier. You must not compute, estimate, rank, or comment on any score,
priority, or importance. Numeric scoring is done in code, not by you. Your only job is
to assign one category per item and a calibrated confidence."""

SYSTEM_PROMPT_RISING_QUERIES: Final[str] = f"""\
{_NO_SCORING_RULE}

You classify rising search queries about elder care into "pain" categories.

Category definitions:
- ACCESS: cannot reach or get into a service or public scheme
- SHORTAGE: supply is missing, no vacancy, nothing found
- WAIT_TIME: waiting period, queue, backlog, "when will it be my turn"
- COST: money, fees, affordability, subsidies, economic barriers
- QUALITY: poor quality, incidents, distrust, complaints
- WORKFORCE: lack of staff or carers, working conditions of care workers
- NEUTRAL: none of the above (general information seeking, proper nouns, unrelated words)

Rules:
- If you are unsure, choose NEUTRAL and lower the confidence. Do not force a query into a
  pain category.
- Judge only the query string. No other signal is provided, and none should be assumed.

{_RESPONSE_CONTRACT}

Example input: [{{"index": 0, "query": "care home waiting list"}}]
Example output: {{"results": [{{"index": 0, "classification": "WAIT_TIME", "confidence": 0.9}}]}}"""

SYSTEM_PROMPT_SEARCH_RESULTS: Final[str] = f"""\
{_NO_SCORING_RULE}

You classify Google Search organic results about elder care by what the page actually is.

Category definitions:
- DIRECT_PROVIDER: the site of a business or facility that provides the service itself
- MARKETPLACE: a platform that compares, searches, or brokers multiple providers
- GOVERNMENT: a government, municipal, or public authority site
- INFORMATION: explainer articles, round-ups, blogs, dictionaries, Q&A
- NEWS: a news report
- OTHER: none of the above

Rules:
- The decisive question is: "can a user actually arrange or apply for the service at the
  end of this URL?" If yes, it is DIRECT_PROVIDER or MARKETPLACE.
- Do not judge from the domain name alone. Read the title and snippet together.
- If you are unsure, choose OTHER and lower the confidence.
- Ranking position is deliberately not provided. Do not ask for it or infer it.

{_RESPONSE_CONTRACT}

Example input: [{{"index": 0, "title": "Compare home care agencies", "link": \
"https://example.com/compare", "snippet": "Compare rates of local agencies."}}]
Example output: {{"results": [{{"index": 0, "classification": "MARKETPLACE", \
"confidence": 0.85}}]}}"""

SYSTEM_PROMPT_NEWS_ARTICLES: Final[str] = f"""\
{_NO_SCORING_RULE}

You classify news headlines by how directly they relate to the target topic in the
target country.

Category definitions:
- DIRECTLY_RELEVANT: the article is about that topic in that country itself
- RELATED: the article is about an adjacent topic (ageing in general, healthcare,
  social security, care financing, care policy, care workforce training)
- UNRELATED: not related

Rules:
- Only the headline and the publisher name are provided. Publication dates are
  deliberately withheld; recency is handled in code. Do not infer or request dates.
- If the headline alone is not enough to decide, choose RELATED and lower the confidence.

{_RESPONSE_CONTRACT}

Example input: [{{"index": 0, "title": "Care home closures leave rural areas without beds",\
 "source_name": "Example Daily"}}]
Example output: {{"results": [{{"index": 0, "classification": "DIRECTLY_RELEVANT", \
"confidence": 0.9}}]}}"""

SYSTEM_PROMPT_BRIEF: Final[str] = """\
You write a short Opportunity Brief from a pre-computed evidence pack. You are an
explainer, not an analyst: every number in the pack was computed in code.

Hard rules:
- Do not state any fact that is not in the evidence pack.
- Do not invent, derive, or restate new numbers. Do not recompute or rank anything.
- Do not write any URL. Never output "http://" or "https://".
- Avoid assertions. Write what was observed ("search demand rose", not "demand is high").
- Cite evidence inline as [E1], [E2]. Use only ids present in the pack.
- why_now, what_people_are_struggling_with and visible_solutions must each contain at
  least one citation.
- what_this_does_not_prove must never be empty. It must state the limitations given in
  the pack: this is a search-visible signal, not a measure of the objective severity of
  the problem, and low visible solution coverage is not the same as low actual supply.
- next_validation must be a concrete next action (primary research, official statistics,
  regulation review, local interviews), not a restatement of the findings.

Output must be structured JSON of exactly this shape and nothing else:
{"why_now": "...", "what_people_are_struggling_with": "...", "visible_solutions": "...",
 "what_this_does_not_prove": "...", "next_validation": "...",
 "cited_evidence_ids": ["E1"]}"""


def build_rising_query_payload(items: Sequence[RisingQuery]) -> list[ItemPayload]:
    """rising query の入力ペイロード。**成長率を含めない。**"""
    return [{"index": index, "query": item.query} for index, item in enumerate(items)]


def build_search_result_payload(items: Sequence[SearchResultItem]) -> list[ItemPayload]:
    """検索結果の入力ペイロード。**`position` を含めない。**"""
    payload: list[ItemPayload] = []
    for index, item in enumerate(items):
        entry: ItemPayload = {"index": index, "title": item.title, "link": item.link}
        if item.snippet is not None:
            entry["snippet"] = item.snippet
        if item.displayed_link is not None:
            entry["displayed_link"] = item.displayed_link
        payload.append(entry)
    return payload


def build_news_article_payload(items: Sequence[NewsArticle]) -> list[ItemPayload]:
    """ニュース記事の入力ペイロード。**日付を含めない。** `title` と `source_name` のみ。"""
    payload: list[ItemPayload] = []
    for index, item in enumerate(items):
        entry: ItemPayload = {"index": index, "title": item.title}
        if item.source_name is not None:
            entry["source_name"] = item.source_name
        payload.append(entry)
    return payload


def build_evidence_pack_payload(pack: EvidencePack) -> dict[str, object]:
    """Opportunity Brief の入力ペイロード(docs/llm-prompts.md 4章)。"""
    return {
        "country": pack.country.value,
        "topic": pack.topic_id.value,
        "need_gap_score": pack.need_gap_score,
        "confidence": pack.confidence,
        "components": pack.components.model_dump(),
        "evidence": [
            {"id": item.id, "source": item.source.value, "summary": item.summary}
            for item in pack.evidence
        ],
        "limitations": list(pack.limitations),
    }


def _dumps(payload: object) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=False)


def _country_context(profile: QueryProfile) -> str:
    return (
        f"Target country: {profile.country.value} ({profile.country.label}). "
        f"Target language: {profile.language}. "
        f"Target topic: {profile.topic_id.value}. "
        f"The items below are written in the language of that country; "
        f"judge them in that language, not in translation."
    )


def build_rising_query_prompt(items: Sequence[RisingQuery], profile: QueryProfile) -> str:
    """rising query 分類のユーザープロンプト。"""
    return (
        f"{_country_context(profile)}\n"
        f"Classify each of the {len(items)} rising search queries below.\n"
        f"{_dumps(build_rising_query_payload(items))}"
    )


def build_search_result_prompt(items: Sequence[SearchResultItem], profile: QueryProfile) -> str:
    """検索結果分類のユーザープロンプト。"""
    return (
        f"{_country_context(profile)}\n"
        f"Classify each of the {len(items)} search results below.\n"
        f"{_dumps(build_search_result_payload(items))}"
    )


def build_news_article_prompt(items: Sequence[NewsArticle], profile: QueryProfile) -> str:
    """ニュース記事分類のユーザープロンプト。"""
    return (
        f"{_country_context(profile)}\n"
        f"Classify each of the {len(items)} news headlines below.\n"
        f"{_dumps(build_news_article_payload(items))}"
    )


def build_brief_prompt(pack: EvidencePack) -> str:
    """Opportunity Brief のユーザープロンプト。"""
    return (
        "Write the Opportunity Brief for the evidence pack below. "
        "Use only what it contains.\n"
        f"{_dumps(build_evidence_pack_payload(pack))}"
    )
