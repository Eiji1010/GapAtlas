"""LLM アダプタの Protocol。

ADR 0002 のとおり、LLM 呼び出しはこの Protocol の背後に隔離する。Bedrock などへ
差し替える場合も、実装を1つ追加するだけで済む。

**戻り値は必ず入力と同数・同順**とする。欠落・未知値は既定値(`NEUTRAL` / `OTHER` /
`UNRELATED`)で補完する。呼び出し側は `zip(items, classifications)` で対応付けてよい。

**分類が全滅した場合(1件も解決できなかった場合)は `LlmError` を送出する。**
既定値で全件を埋めた結果を返すと、`solution_gap = 100`(最大値)や `pain = 0` が
実際の観測値として NeedGapScore に入り、Evidence Confidence にも反映されない。
application 層はこの例外を捕捉して該当ソースを `MISSING` として扱うこと
(docs/llm-prompts.md「分類が全滅した場合、その成分は None(欠損)として扱い、
Confidence へ反映する」)。部分的な欠落は例外にしない(既定値の confidence が
0.0 のためスコアへ寄与せず、件数は Sample sufficiency で評価される)。

`runtime_checkable` は付けない。構造的部分型の実行時チェックはメソッド名の有無しか
見ないため、契約の保証にならない。
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from gapatlas.adapters.llm.models import EvidencePack
from gapatlas.domain.models.classification import (
    NewsClassification,
    PainClassification,
    SolutionClassification,
)
from gapatlas.domain.models.normalized import NewsArticle, RisingQuery, SearchResultItem
from gapatlas.domain.models.query_profile import QueryProfile
from gapatlas.domain.models.result import OpportunityBrief


class LlmClassifier(Protocol):
    """分類だけを行う。スコア計算は行わない(AGENTS.md 絶対ルール)。"""

    def classify_rising_queries(
        self, items: Sequence[RisingQuery], profile: QueryProfile
    ) -> list[PainClassification]:
        """rising query を Pain カテゴリへ分類する。入力と同数・同順を返す。"""
        ...

    def classify_search_results(
        self, items: Sequence[SearchResultItem], profile: QueryProfile
    ) -> list[SolutionClassification]:
        """検索結果を Solution カテゴリへ分類する。入力と同数・同順を返す。"""
        ...

    def classify_news_articles(
        self, items: Sequence[NewsArticle], profile: QueryProfile
    ) -> list[NewsClassification]:
        """ニュース記事を関連性カテゴリへ分類する。入力と同数・同順を返す。"""
        ...


class BriefWriter(Protocol):
    """Opportunity Brief を生成する。"""

    def write_brief(self, pack: EvidencePack) -> OpportunityBrief | None:
        """Brief を生成する。検証に通らない場合は None(誤った断定を出さない)。"""
        ...
