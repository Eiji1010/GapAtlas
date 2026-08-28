"""Evidence と Evidence パックの組み立て。

**Evidence の `summary` はコード側が生成した事実**であり、LLM はこれを
言い換え・統合するだけで新しい事実を足さない(docs/llm-prompts.md 4章)。
`url` は **SerpApi のレスポンスに含まれていた URL のみ**を入れる。LLM に
URL を生成させない(AGENTS.md 絶対ルール)。
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Final

from gapatlas.adapters.llm.models import BriefComponents, EvidencePack, EvidenceSummary
from gapatlas.domain.models.classification import (
    ClassifiedEvidence,
    NewsRelevance,
    PainCategory,
    SolutionCategory,
)
from gapatlas.domain.models.common import Country, SourceName, SourceStatus, TopicId
from gapatlas.domain.models.normalized import NormalizedEvidence
from gapatlas.domain.models.result import Evidence
from gapatlas.domain.scoring.constants import PREVIOUS_WEEKS, RECENT_WEEKS, WINDOW_WEEKS
from gapatlas.domain.scoring.engine import CountryEvaluation

METHODOLOGY_LIMITATIONS: Final[tuple[str, ...]] = (
    "Solution Coverage は検索上の可視性であり、実際の供給量ではない",
    "Google Trends の値は期間・地域内の相対値であり、国同士の絶対的な需要の大小は比較していない",
    "報道量は媒体の関心と報道慣行に依存するため、ニュースが少ないことは問題の不在を意味しない",
    "Maps の件数は事業者数ではなく、Core Score にも使用していない",
    "このスコアは社会問題の客観的な深刻度を測定していない",
    "市場規模や TAM は算出していない",
    "将来予測は行っていない",
)
"""docs/methodology.md「何を示さないか」由来の限界。Brief へ必ず渡す。"""

PAIN_HIGHLIGHT_CATEGORIES: Final[tuple[PainCategory, ...]] = (
    PainCategory.SHORTAGE,
    PainCategory.WAIT_TIME,
    PainCategory.ACCESS,
    PainCategory.WORKFORCE,
)
"""Evidence の要約で件数を示す困りごとカテゴリ。"""

SOLUTION_PROVIDER_CATEGORIES: Final[tuple[SolutionCategory, ...]] = (
    SolutionCategory.DIRECT_PROVIDER,
    SolutionCategory.MARKETPLACE,
)
"""「実際に申し込める」側に分類された検索結果。"""


def _trend_change_percent(evidence: NormalizedEvidence) -> float | None:
    """第1系列の直近4週と前8週の平均変化率(%)。要約の文言に使う。

    スコアではなく**説明のための数値**。スコア計算は `domain/scoring` が行う。
    """
    if evidence.trends is None or not evidence.trends.series:
        return None
    points = [point.value for point in evidence.trends.series[0].points]
    if len(points) < WINDOW_WEEKS:
        return None
    window = points[-WINDOW_WEEKS:]
    previous = sum(window[:PREVIOUS_WEEKS]) / PREVIOUS_WEEKS
    recent = sum(window[-RECENT_WEEKS:]) / RECENT_WEEKS
    if previous == 0.0:
        return None
    return (recent - previous) / previous * 100.0


def _trends_summary(evidence: NormalizedEvidence) -> str:
    change = _trend_change_percent(evidence)
    if change is None:
        # Demand を計算できる系列が無い場合、そのソースは MISSING になり
        # Evidence 自体が作られない。到達するのは第1系列だけが短い場合など。
        # **点数を断定しない**(11点しか無いのに「12週」と書かない)。
        return "検索需要の週次推移を取得した"
    direction = "上昇" if change >= 0 else "低下"
    return (
        f"直近{RECENT_WEEKS}週の検索需要が前{PREVIOUS_WEEKS}週比で "
        f"{abs(change):.1f}% {direction}した"
    )


def _rising_summary(classified: ClassifiedEvidence) -> str:
    total = len(classified.rising_queries)
    highlighted = sum(
        1
        for entry in classified.rising_queries
        if entry.classification.classification in PAIN_HIGHLIGHT_CATEGORIES
    )
    return f"急上昇クエリ {total} 件のうち、不足・待機・到達困難に分類されたものが {highlighted} 件"


def _search_summary(classified: ClassifiedEvidence) -> str:
    total = len(classified.search_results)
    providers = sum(
        1
        for entry in classified.search_results
        if entry.classification.classification in SOLUTION_PROVIDER_CATEGORIES
    )
    return f"検索結果 上位{total}件のうち、直接申し込める提供者・仲介は {providers} 件"


def _news_summary(classified: ClassifiedEvidence) -> str:
    total = len(classified.news_articles)
    relevant = sum(
        1
        for entry in classified.news_articles
        if entry.classification.classification is NewsRelevance.DIRECTLY_RELEVANT
    )
    return f"報道 {total} 件のうち、この課題そのものを扱った記事が {relevant} 件"


def _maps_summary(evidence: NormalizedEvidence) -> str:
    places = evidence.maps_places or []
    return f"代表都市の周辺で {len(places)} 件の事業者が地図検索に現れた(供給量ではない)"


def _first_url(candidates: Sequence[str | None]) -> str | None:
    """SerpApi のレスポンス由来の URL を1つ選ぶ。無ければ None。"""
    for candidate in candidates:
        if candidate:
            return candidate
    return None


def build_evidence(evidence: NormalizedEvidence, classified: ClassifiedEvidence) -> list[Evidence]:
    """UI と Brief に渡す Evidence を組み立てる。

    ID は `E1` 始まりの連番。**OK のソースだけ**を対象にする(欠けている
    ソースについて根拠を作らない)。`url` は SerpApi のレスポンスに
    含まれていた URL のみ。
    """
    items: list[Evidence] = []

    def add(source: SourceName, summary: str, url: str | None = None) -> None:
        items.append(Evidence(id=f"E{len(items) + 1}", source=source, summary=summary, url=url))

    if evidence.source_status(SourceName.TRENDS) is SourceStatus.OK:
        add(SourceName.TRENDS, _trends_summary(evidence))
    if evidence.source_status(SourceName.RELATED_QUERIES) is SourceStatus.OK:
        add(
            SourceName.RELATED_QUERIES,
            _rising_summary(classified),
            _first_url([item.link for item in evidence.rising_queries]),
        )
    if evidence.source_status(SourceName.SEARCH) is SourceStatus.OK:
        add(
            SourceName.SEARCH,
            _search_summary(classified),
            _first_url([item.link for item in evidence.search_results]),
        )
    if evidence.source_status(SourceName.NEWS) is SourceStatus.OK:
        add(
            SourceName.NEWS,
            _news_summary(classified),
            _first_url([item.link for item in evidence.news_articles]),
        )
    if evidence.source_status(SourceName.MAPS) is SourceStatus.OK:
        add(
            SourceName.MAPS,
            _maps_summary(evidence),
            _first_url([place.link for place in (evidence.maps_places or [])]),
        )
    return items


def build_evidence_pack(
    country: Country,
    topic_id: TopicId,
    evaluation: CountryEvaluation,
    items: Sequence[Evidence],
) -> EvidencePack:
    """Opportunity Brief へ渡す入力を組み立てる。

    **生データを LLM へ渡さない。** 渡すのはコード側が算出した数値と、
    コード側が書いた Evidence の要約、そして方法論上の限界だけ。
    `url` は渡さない(LLM に URL を書かせないため)。
    """
    return EvidencePack(
        country=country,
        topic_id=topic_id,
        need_gap_score=evaluation.public_need_gap_score,
        confidence=evaluation.public_confidence,
        components=BriefComponents(
            demand=evaluation.public_components.demand,
            pain=evaluation.public_components.pain,
            solution_gap=evaluation.public_components.solution_gap,
            news_urgency=evaluation.public_components.news_urgency,
        ),
        evidence=[
            EvidenceSummary(id=item.id, source=item.source, summary=item.summary) for item in items
        ],
        limitations=list(METHODOLOGY_LIMITATIONS),
    )
