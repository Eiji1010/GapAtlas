"""分類結果の入力ハッシュキャッシュ。

docs/llm-prompts.md「分類結果は入力ハッシュでキャッシュする(同じ入力に同じ結果を返す)」。

キーは **`hashlib.sha256`** で作る。組み込みの `hash()` は文字列に対してプロセスごとに
異なる値を返すため使わない(Lambda の実行環境をまたいで再現しない)。

キー材料:

- 分類対象の内容(LLM へ実際に渡すペイロード。成長率・`position`・日付は含まれない)
- `QueryProfile` の `topic_id` / `version` / `country` / `language`
- `CLASSIFIER_VERSION` / `PROMPT_VERSION`

プロセス内メモリキャッシュで十分とする(永続キャッシュは別 Phase)。
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence

from gapatlas.adapters.llm.prompts import (
    ItemPayload,
    build_news_article_payload,
    build_rising_query_payload,
    build_search_result_payload,
)
from gapatlas.adapters.llm.protocol import LlmClassifier
from gapatlas.adapters.llm.versions import CLASSIFIER_VERSION, PROMPT_VERSION
from gapatlas.domain.models.classification import (
    NewsClassification,
    PainClassification,
    SolutionClassification,
)
from gapatlas.domain.models.normalized import NewsArticle, RisingQuery, SearchResultItem
from gapatlas.domain.models.query_profile import QueryProfile


def build_cache_key(kind: str, items: Sequence[ItemPayload], profile: QueryProfile) -> str:
    """分類対象とバージョン識別子から安定したキーを作る。"""
    material = json.dumps(
        {
            "kind": kind,
            "items": items,
            "topic_id": profile.topic_id.value,
            "country": profile.country.value,
            "language": profile.language,
            "query_profile_version": profile.version,
            "classifier_version": CLASSIFIER_VERSION,
            "prompt_version": PROMPT_VERSION,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


class CachingLlmClassifier:
    """`LlmClassifier` をプロセス内メモリキャッシュで包む。

    同じ入力に対して内側のクライアントを2度呼ばない。返すのは毎回新しいリストなので、
    呼び出し側がリストを組み替えてもキャッシュは壊れない。
    """

    def __init__(self, inner: LlmClassifier) -> None:
        self._inner = inner
        self._pain: dict[str, list[PainClassification]] = {}
        self._solution: dict[str, list[SolutionClassification]] = {}
        self._news: dict[str, list[NewsClassification]] = {}

    def classify_rising_queries(
        self, items: Sequence[RisingQuery], profile: QueryProfile
    ) -> list[PainClassification]:
        key = build_cache_key("rising_queries", build_rising_query_payload(items), profile)
        cached = self._pain.get(key)
        if cached is None:
            cached = self._inner.classify_rising_queries(items, profile)
            self._pain[key] = cached
        return list(cached)

    def classify_search_results(
        self, items: Sequence[SearchResultItem], profile: QueryProfile
    ) -> list[SolutionClassification]:
        key = build_cache_key("search_results", build_search_result_payload(items), profile)
        cached = self._solution.get(key)
        if cached is None:
            cached = self._inner.classify_search_results(items, profile)
            self._solution[key] = cached
        return list(cached)

    def classify_news_articles(
        self, items: Sequence[NewsArticle], profile: QueryProfile
    ) -> list[NewsClassification]:
        key = build_cache_key("news_articles", build_news_article_payload(items), profile)
        cached = self._news.get(key)
        if cached is None:
            cached = self._inner.classify_news_articles(items, profile)
            self._news[key] = cached
        return list(cached)
