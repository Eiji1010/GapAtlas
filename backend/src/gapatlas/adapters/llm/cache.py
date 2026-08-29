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

from gapatlas.adapters.llm.models import EvidencePack
from gapatlas.adapters.llm.prompts import (
    ItemPayload,
    build_news_article_payload,
    build_rising_query_payload,
    build_search_result_payload,
)
from gapatlas.adapters.llm.protocol import BriefWriter, LlmClassifier
from gapatlas.adapters.llm.versions import CLASSIFIER_VERSION, PROMPT_VERSION
from gapatlas.domain.models.classification import (
    NewsClassification,
    PainClassification,
    SolutionClassification,
)
from gapatlas.domain.models.normalized import NewsArticle, RisingQuery, SearchResultItem
from gapatlas.domain.models.query_profile import QueryProfile
from gapatlas.domain.models.result import OpportunityBrief


def build_cache_key(
    kind: str,
    items: Sequence[ItemPayload],
    profile: QueryProfile,
    *,
    classifier_version: str = CLASSIFIER_VERSION,
    prompt_version: str = PROMPT_VERSION,
) -> str:
    """分類対象とバージョン識別子から安定したキーを作る。

    版は**実際の分類器のもの**を使う。stub と実 LLM で結果が変わるため、
    共通の定数でキーを作るとモードを跨いで誤ってヒットする。
    """
    material = json.dumps(
        {
            "kind": kind,
            "items": items,
            "topic_id": profile.topic_id.value,
            "country": profile.country.value,
            "language": profile.language,
            "query_profile_version": profile.version,
            "classifier_version": classifier_version,
            "prompt_version": prompt_version,
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
        self._key_versions = {
            "classifier_version": inner.classifier_version,
            "prompt_version": inner.prompt_version,
        }
        self._pain: dict[str, list[PainClassification]] = {}
        self._solution: dict[str, list[SolutionClassification]] = {}
        self._news: dict[str, list[NewsClassification]] = {}

    @property
    def classifier_version(self) -> str:
        return self._inner.classifier_version

    @property
    def prompt_version(self) -> str:
        return self._inner.prompt_version

    def classify_rising_queries(
        self, items: Sequence[RisingQuery], profile: QueryProfile
    ) -> list[PainClassification]:
        key = build_cache_key(
            "rising_queries", build_rising_query_payload(items), profile, **self._key_versions
        )
        cached = self._pain.get(key)
        if cached is None:
            cached = self._inner.classify_rising_queries(items, profile)
            self._pain[key] = cached
        return list(cached)

    def classify_search_results(
        self, items: Sequence[SearchResultItem], profile: QueryProfile
    ) -> list[SolutionClassification]:
        key = build_cache_key(
            "search_results", build_search_result_payload(items), profile, **self._key_versions
        )
        cached = self._solution.get(key)
        if cached is None:
            cached = self._inner.classify_search_results(items, profile)
            self._solution[key] = cached
        return list(cached)

    def classify_news_articles(
        self, items: Sequence[NewsArticle], profile: QueryProfile
    ) -> list[NewsClassification]:
        key = build_cache_key(
            "news_articles", build_news_article_payload(items), profile, **self._key_versions
        )
        cached = self._news.get(key)
        if cached is None:
            cached = self._inner.classify_news_articles(items, profile)
            self._news[key] = cached
        return list(cached)


def build_brief_cache_key(pack: EvidencePack) -> str:
    """Opportunity Brief のキャッシュキー。

    `docs/requirements.md`「Cache」の `| AI Insight | evidence hash が
    変わるまで |`。Evidence パックの内容(スコア・Evidence の要約・限界)から
    作る。**同じ根拠なら同じ Brief を返す。**

    Worker の「最後の1国」判定が競合すると確定処理が2回走りうる。実 LLM は
    決定的でないため、キャッシュが無いと2回目が別の文面で上書きし、
    2秒 Polling 中のユーザーには Brief が書き換わって見える。
    """
    material = json.dumps(
        {
            "pack": pack.model_dump(mode="json"),
            "prompt_version": PROMPT_VERSION,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


class CachingBriefWriter:
    """`BriefWriter` を Evidence ハッシュのキャッシュで包む。

    生成しない判断(`None`)もキャッシュする。検証に落ちた Brief を
    呼び出しのたびに作り直しても、同じ入力なら同じ結果になるためである。
    """

    def __init__(self, inner: BriefWriter) -> None:
        self._inner = inner
        self._briefs: dict[str, OpportunityBrief | None] = {}

    @property
    def prompt_version(self) -> str:
        return self._inner.prompt_version

    def write_brief(self, pack: EvidencePack) -> OpportunityBrief | None:
        key = build_brief_cache_key(pack)
        if key in self._briefs:
            return self._briefs[key]
        brief = self._inner.write_brief(pack)
        self._briefs[key] = brief
        return brief
