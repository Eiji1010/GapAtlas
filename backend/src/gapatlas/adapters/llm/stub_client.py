"""`LLM_MODE=stub` 用の決定的な分類器。

**ネットワークに一切アクセスしない。** 乱数も現在時刻も使わない。同じ入力に対して
常に同じ出力を返す(docs/llm-prompts.md「stub モードの要件」)。

分類は言語ごとのキーワード一致表による規則ベースで行う。すべて `NEUTRAL` を返すような
無意味な stub にはしない(スコアリングのテストが意味を失うため)。規則は
`backend/tests/fixtures/README.md` の「意図した分類分布」に近い結果を返すよう調整して
あり、その一致率は `tests/unit/adapters/llm/test_stub_classification_quality.py` で
検証している。

規則の位置づけ:

- **stub の分類規則はプロンプト仕様の一部ではない。** コードとテストで管理する
  (docs/llm-prompts.md「stub モードの要件」)
- 判定は「先に一致した規則が勝つ」。規則の順序そのものが仕様である
- `confidence` は規則の確からしさに応じて決定的に決める。1.0 固定にはしない
  (Evidence Confidence 側の計算が意味を持たなくなるため)
"""

from __future__ import annotations

from collections.abc import Sequence
from enum import StrEnum
from typing import Final

from gapatlas.adapters.llm.models import EvidencePack
from gapatlas.adapters.llm.versions import CLASSIFIER_VERSION, PROMPT_VERSION
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
from gapatlas.domain.models.result import OpportunityBrief

STRONG_CONFIDENCE: Final[float] = 0.9
"""明示的なキーワードに一致した場合。"""

FORUM_CONFIDENCE: Final[float] = 0.8
"""フォーラム等、`OTHER` を積極的に選べる場合。"""

MODERATE_CONFIDENCE: Final[float] = 0.7
"""間接的な手がかり(地理的な言及、隣接トピックへの降格)による判定。"""

WEAK_CONFIDENCE: Final[float] = 0.6
"""明示的な手がかりが無く、消去法で選んだ場合。"""

ADJACENT_CONFIDENCE: Final[float] = 0.5
"""トピック語が無く、隣接語だけが見つかった場合。"""

DEFAULT_CONFIDENCE: Final[float] = 0.4
"""どの規則にも一致せず、既定カテゴリへ落ちた場合。"""

type _Rules[CategoryT: StrEnum] = tuple[tuple[CategoryT, float, tuple[str, ...]], ...]

# --- Pain(rising query)---------------------------------------------------------------
# 順序が重要。例: 「人手不足」は SHORTAGE ではなく WORKFORCE として扱いたいので、
# WORKFORCE を SHORTAGE より先に評価する。
_PAIN_RULES: Final[_Rules[PainCategory]] = (
    (
        PainCategory.WORKFORCE,
        STRONG_CONFIDENCE,
        (
            # ja
            "人手不足",
            "人材不足",
            "人材確保",
            "担い手",
            "離職",
            "職員不足",
            # en(「人の不足」は SHORTAGE ではなく WORKFORCE)
            "understaffed",
            "staff shortage",
            "staffing shortage",
            "aide shortage",
            "carer shortage",
            "caregiver shortage",
            "nurse shortage",
            "attendant shortage",
            "worker shortage",
            "burnout",
            "turnover",
            "recruitment",
            "workforce",
            # de
            "kräftemangel",
            "personalmangel",
            "überlastet",
            "überlastung",
        ),
    ),
    (
        PainCategory.WAIT_TIME,
        STRONG_CONFIDENCE,
        (
            "待機",
            "順番待ち",
            "順番",
            "waiting",
            "waitlist",
            "wait time",
            "delay",
            "backlog",
            "wartezeit",
            "warteliste",
        ),
    ),
    (
        PainCategory.SHORTAGE,
        STRONG_CONFIDENCE,
        (
            # ja
            "空きがない",
            "空きなし",
            "満床",
            "少ない",
            "不足",
            "見つからない",
            # en
            "not available",
            "unavailable",
            "availability",
            "available",
            "shortage",
            "scarce",
            "no beds",
            "no vacancies",
            "fully booked",
            # de
            "kein platz",
            "keinen platz",
            "platz frei",
            "keine plätze",
            "ausgebucht",
            "aufnahmestopp",
            "dringend",
        ),
    ),
    (
        PainCategory.ACCESS,
        STRONG_CONFIDENCE,
        (
            "断られ",
            "取れない",
            "受け入れ拒否",
            "can't find",
            "cannot find",
            "turned away",
            "refused",
            "denied",
            "admission",
            "eligibility",
            "access",
            "nimmt keine neuen",
            "abgewiesen",
            "abgelehnt",
        ),
    ),
    (
        # 地理・孤立の言及は「到達できない」の間接的な手がかり。確信度を下げる。
        PainCategory.ACCESS,
        MODERATE_CONFIDENCE,
        (
            "地方",
            "rural",
            "tier 2",
            "tier-2",
            "in my city",
            "living alone",
            "auf dem land",
            "ländlich",
        ),
    ),
    (
        PainCategory.COST,
        STRONG_CONFIDENCE,
        (
            "費用",
            "料金",
            "自己負担",
            "払えない",
            "相場",
            "補助金",
            "cost",
            "fee",
            "price",
            "paying",
            "pay for",
            "afford",
            "charges",
            "funding",
            "expensive",
            "kosten",
            "eigenanteil",
            "zuzahlung",
            "teuer",
            "zu hoch",
        ),
    ),
    (
        PainCategory.QUALITY,
        STRONG_CONFIDENCE,
        (
            "悪い",
            "苦情",
            "事故",
            "虐待",
            "評判",
            "neglect",
            "abuse",
            "complaint",
            "poor",
            "quality",
            "rating",
            "scandal",
            "schlechte",
            "beschwerde",
            "mängel",
        ),
    ),
)

# --- Solution(検索結果)---------------------------------------------------------------
# 「その URL の先で実際にサービスを申し込めるか」が判断基準(docs/llm-prompts.md 2章)。
# 報道・フォーラム・公的機関を先に除いてから、申し込み系(MARKETPLACE / DIRECT_PROVIDER)
# を判定する。解説記事は DIRECT_PROVIDER より先に評価する(事業者名を含む解説記事を
# 事業者サイトと誤判定しないため)。
_SOLUTION_RULES: Final[_Rules[SolutionCategory]] = (
    (
        SolutionCategory.NEWS,
        STRONG_CONFIDENCE,
        ("news.", "/news/", "報道", "ニュース", "daily report", "business report", "nachrichten"),
    ),
    (
        SolutionCategory.OTHER,
        FORUM_CONFIDENCE,
        ("forum", "/threads/", "discussion thread", "掲示板", "知恵袋"),
    ),
    (
        SolutionCategory.GOVERNMENT,
        STRONG_CONFIDENCE,
        (
            ".go.jp",
            ".lg.jp",
            ".gov",
            "自治体",
            "市役所",
            "区役所",
            "厚生労働省",
            "council",
            "borough",
            "public agency",
            "public service",
            "regulator",
            "sozialamt",
            "landkreis",
            "behörde",
            "ministerium",
        ),
    ),
    (
        SolutionCategory.MARKETPLACE,
        STRONG_CONFIDENCE,
        (
            "検索",
            "ナビ",
            "問い合わせ",
            "一括",
            "比較サイト",
            "directory",
            "marketplace",
            "finder",
            "match",
            "platform",
            "comparison site",
            "portal",
            "vergleich",
            "suchplattform",
        ),
    ),
    (
        SolutionCategory.INFORMATION,
        STRONG_CONFIDENCE,
        (
            "解説",
            "まとめ",
            "ガイド",
            "目安",
            "選び方",
            "情報室",
            "相談室",
            "guide",
            "advice",
            "explained",
            "explainer",
            "checklist",
            "how much",
            "how to",
            "what is",
            "blog",
            "journal",
            "tips",
            "faq",
            "ratgeber",
            "erklärt",
            "wissen",
            "worauf achten",
            "was macht",
        ),
    ),
    (
        SolutionCategory.DIRECT_PROVIDER,
        STRONG_CONFIDENCE,
        (
            "事業所です",
            "ステーション",
            "を提供しています",
            "provider",
            "agency",
            "operator",
            "care homes",
            "clinic",
            "pflegedienst",
        ),
    ),
)

_SOLUTION_SERVICE_TERMS: Final[tuple[str, ...]] = (
    "care",
    "nursing",
    "senior",
    "elder",
    "介護",
    "老人ホーム",
    "pflege",
)
"""どの規則にも一致しなかったブランドページ用。サービス語があれば事業者サイトとみなす。"""

# --- News(関連性)----------------------------------------------------------------------
_NEWS_TOPIC_TERMS: Final[tuple[str, ...]] = (
    # ja
    "介護",
    "老人ホーム",
    "ケアマネ",
    "高齢者施設",
    # en
    "elder",
    "home care",
    "nursing home",
    "care home",
    "care provider",
    "care package",
    "care vacancies",
    "caregiver",
    "caretaker",
    "carer",
    "aide",
    "assisted living",
    "old age home",
    "home nursing",
    "geriatric",
    "social care",
    "day care",
    "adult day",
    "attendant",
    "respite",
    # de
    "pflege",
)
"""その国のその課題(Elder Care)そのものを指す語。"""

_NEWS_ADJACENT_MARKERS: Final[tuple[str, ...]] = (
    "報酬改定",
    "ロボット",
    "lawmaker",
    "immigration",
    "insurance",
    "startup",
    "market",
    "budget",
    "overspend",
    "ausbildung",
)
"""トピック語を含んでいても、記事の主題が隣接領域(制度・財政・技術・教育・市場)の場合。"""

_NEWS_ADJACENT_TERMS: Final[tuple[str, ...]] = (
    "高齢",
    "医療",
    "年金",
    "社会保障",
    "ageing",
    "aging",
    "senior",
    "elderly",
    "hospital",
    "health",
    "senioren",
    "rente",
    "gesundheit",
)
"""トピック語が無くても、高齢化・医療・社会保障など隣接する話題であることを示す語。"""


def _normalize(*parts: str | None) -> str:
    """一致判定用に小文字化して連結する。"""
    return " ".join(part for part in parts if part).casefold()


def _contains_any(text: str, keywords: tuple[str, ...]) -> bool:
    return any(keyword in text for keyword in keywords)


def _match[CategoryT: StrEnum](
    text: str, rules: _Rules[CategoryT], default: CategoryT
) -> tuple[CategoryT, float]:
    """先に一致した規則を返す。一致しなければ既定カテゴリ。"""
    for category, confidence, keywords in rules:
        if _contains_any(text, keywords):
            return category, confidence
    return default, DEFAULT_CONFIDENCE


class StubLlmClient:
    """`LLM_MODE=stub` の分類器兼 Brief 生成器。

    `LlmClassifier` と `BriefWriter` の両方を満たす。状態を持たないため使い回してよい。
    """

    @property
    def classifier_version(self) -> str:
        """stub の規則ベース分類であることを版に残す。

        実 LLM とは結果が変わるため、同じ識別子を名乗ってはいけない
        (docs/llm-prompts.md「バージョン管理」)。
        """
        return f"{CLASSIFIER_VERSION}-stub"

    @property
    def prompt_version(self) -> str:
        """stub はプロンプトを使わないが、識別のため版を返す。"""
        return f"{PROMPT_VERSION}-stub"

    def classify_rising_queries(
        self, items: Sequence[RisingQuery], profile: QueryProfile
    ) -> list[PainClassification]:
        """rising query を Pain カテゴリへ分類する。

        `profile` は署名互換のために受け取るが、規則は多言語のキーワード表で
        統一しているため参照しない。**成長率(`growth_percent`)は使わない**
        (重要度の判断をスコアから分離するため)。
        """
        del profile
        results: list[PainClassification] = []
        for item in items:
            category, confidence = _match(_normalize(item.query), _PAIN_RULES, PainCategory.NEUTRAL)
            results.append(PainClassification(classification=category, confidence=confidence))
        return results

    def classify_search_results(
        self, items: Sequence[SearchResultItem], profile: QueryProfile
    ) -> list[SolutionClassification]:
        """検索結果を Solution カテゴリへ分類する。**`position` は使わない。**"""
        del profile
        results: list[SolutionClassification] = []
        for item in items:
            text = _normalize(item.title, item.link, item.displayed_link, item.snippet, item.source)
            category, confidence = _match(text, _SOLUTION_RULES, SolutionCategory.OTHER)
            # 手がかりが無いブランドページ。サービス語があれば事業者サイトとみなす。
            fell_through = category is SolutionCategory.OTHER and confidence == DEFAULT_CONFIDENCE
            if fell_through and _contains_any(text, _SOLUTION_SERVICE_TERMS):
                category, confidence = SolutionCategory.DIRECT_PROVIDER, WEAK_CONFIDENCE
            results.append(SolutionClassification(classification=category, confidence=confidence))
        return results

    def classify_news_articles(
        self, items: Sequence[NewsArticle], profile: QueryProfile
    ) -> list[NewsClassification]:
        """ニュース記事を関連性カテゴリへ分類する。**日付は使わない。**

        `title` を主、`source_name` を従として見る。隣接領域(制度・財政・技術・教育・
        市場)を主題とする見出しは、トピック語を含んでいても `RELATED` へ落とす。
        """
        del profile
        results: list[NewsClassification] = []
        for item in items:
            title = _normalize(item.title)
            full = _normalize(item.title, item.source_name)
            category, confidence = _classify_news_text(title, full)
            results.append(NewsClassification(classification=category, confidence=confidence))
        return results

    def write_brief(self, pack: EvidencePack) -> OpportunityBrief | None:
        """入力 Evidence ID をすべて引用した固定文面を返す。

        Evidence が1件も無い場合は `None`(引用できない Brief は出さない)。
        `what_this_does_not_prove` には docs/methodology.md 由来の限界を必ず含める。
        """
        ids = pack.evidence_ids
        if not ids:
            return None
        citations = " ".join(f"[{evidence_id}]" for evidence_id in ids)
        return OpportunityBrief(
            why_now=(
                "Stub mode: this brief is assembled in code, without a language model. "
                f"The signals observed for {pack.topic_id.value} in {pack.country.label} "
                f"during the scanned window are listed as evidence below. {citations}"
            ),
            what_people_are_struggling_with=(
                "The recorded difficulties are exactly the ones summarised in the evidence; "
                f"read each entry rather than this sentence. {citations}"
            ),
            visible_solutions=(
                "What the search results made visible for this country is described in the "
                f"same evidence entries. {citations}"
            ),
            what_this_does_not_prove=(
                "This is a search-visible signal only. It does not measure the objective "
                "severity of the problem. Low visible solution coverage is not the same as "
                "low actual supply of services. Google Trends values are relative within the "
                "requested period and region, so demand levels are not compared across "
                "countries. Media coverage volume reflects editorial attention, not the "
                "presence or absence of the problem."
            ),
            next_validation=(
                "Treat this as a starting point: check official statistics and regulation for "
                "the country, then run local interviews with providers and families before "
                "drawing any conclusion."
            ),
            cited_evidence_ids=list(ids),
        )


def _classify_news_text(title: str, full: str) -> tuple[NewsRelevance, float]:
    """見出し(と媒体名)から関連性を決める。"""
    if _contains_any(full, _NEWS_TOPIC_TERMS):
        if _contains_any(title, _NEWS_ADJACENT_MARKERS):
            return NewsRelevance.RELATED, MODERATE_CONFIDENCE
        return NewsRelevance.DIRECTLY_RELEVANT, STRONG_CONFIDENCE
    if _contains_any(full, _NEWS_ADJACENT_TERMS):
        return NewsRelevance.RELATED, ADJACENT_CONFIDENCE
    return NewsRelevance.UNRELATED, DEFAULT_CONFIDENCE
