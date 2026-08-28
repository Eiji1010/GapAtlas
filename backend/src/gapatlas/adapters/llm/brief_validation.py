"""Opportunity Brief のコード側検証。

正本は docs/llm-prompts.md「コード側の検証(必須)」。**生成結果をそのまま採用しない。**

1. 本文中の `[E<n>]` がすべて入力 Evidence ID に存在すること(無い ID は引用を除去する)
2. `why_now` / `what_people_are_struggling_with` / `visible_solutions` の各節に
   最低1つの Evidence 引用があること(無ければ Brief を出さない)
3. 本文に URL が含まれていないこと(含まれていたら除去する)
4. `what_this_does_not_prove` が空でなく、docs/methodology.md 由来の限界を
   最低1つ含むこと
5. `cited_evidence_ids` を本文から再抽出して上書きすること(LLM の自己申告を信用しない)

**修復できない場合は `None` を返す。** 誤った断定を出すより出さないほうが安全である。
"""

from __future__ import annotations

import logging
import re
from typing import Final

from gapatlas.adapters.llm.models import EvidencePack
from gapatlas.domain.models.result import OpportunityBrief

logger = logging.getLogger(__name__)

CITATION_PATTERN: Final[re.Pattern[str]] = re.compile(r"\[(E[1-9][0-9]*)\]")
"""`[E1]` 形式の引用。ID の形式は `domain/models/result.py` の EVIDENCE_ID_PATTERN と同じ。"""

URL_PATTERN: Final[re.Pattern[str]] = re.compile(r"https?://\S*")
"""LLM が書いた URL。SerpApi 由来の URL はコード側が `Evidence.url` へ入れる。"""

_WHITESPACE_PATTERN: Final[re.Pattern[str]] = re.compile(r"[ \t]{2,}")

CITED_SECTIONS: Final[tuple[str, ...]] = (
    "why_now",
    "what_people_are_struggling_with",
    "visible_solutions",
)
"""最低1つの Evidence 引用が必須な節。"""

TEXT_SECTIONS: Final[tuple[str, ...]] = (
    *CITED_SECTIONS,
    "what_this_does_not_prove",
    "next_validation",
)
"""URL 除去と引用抽出の対象になる全テキスト節。"""

METHODOLOGY_LIMITATION_KEYWORDS: Final[tuple[str, ...]] = (
    # ja(docs/methodology.md の表現)
    "検索上",
    "可視性",
    "供給量",
    "深刻度",
    "相対値",
    "報道量",
    "測定していない",
    # en
    "search-visible",
    "search visible",
    "visibility",
    "actual supply",
    "severity",
    "relative",
    "media coverage",
    "does not measure",
    "not a measure",
)
"""`what_this_does_not_prove` が方法論上の限界に触れているかの判定語。

日本語・英語のどちらで生成されても判定できるよう両方を持つ。追加・変更する場合は
docs/methodology.md「何を示さないか」と対応させること。
"""


def _strip_urls(text: str) -> str:
    """URL を除去し、余分な空白を畳む。"""
    return _tidy(URL_PATTERN.sub("", text))


def _tidy(text: str) -> str:
    return _WHITESPACE_PATTERN.sub(" ", text).strip()


def _strip_unknown_citations(text: str, valid_ids: frozenset[str]) -> str:
    """入力 Evidence に存在しない ID の引用だけを除去する。"""

    def replace(match: re.Match[str]) -> str:
        return match.group(0) if match.group(1) in valid_ids else ""

    return _tidy(CITATION_PATTERN.sub(replace, text))


def _cited_ids(text: str) -> set[str]:
    return set(CITATION_PATTERN.findall(text))


def validate_brief(brief: OpportunityBrief, pack: EvidencePack) -> OpportunityBrief | None:
    """Brief を検証・修復する。修復できなければ `None` を返す。

    修復するもの: 存在しない Evidence ID の引用、本文中の URL、`cited_evidence_ids`。
    修復できないもの: 引用がゼロになった必須節、空または限界に触れていない
    `what_this_does_not_prove`。

    Args:
        brief: LLM(または stub)が生成した Brief。
        pack: 生成に使った Evidence パック。ID の正当性はこれで判定する。

    Returns:
        修復済みの新しい `OpportunityBrief`。採用できない場合は `None`。
    """
    valid_ids = frozenset(pack.evidence_ids)
    cleaned: dict[str, str] = {}
    for field in TEXT_SECTIONS:
        raw = str(getattr(brief, field))
        cleaned[field] = _strip_unknown_citations(_strip_urls(raw), valid_ids)

    for field in CITED_SECTIONS:
        if not _cited_ids(cleaned[field]):
            logger.warning("opportunity brief rejected: section '%s' cites no evidence", field)
            return None

    disclaimer = cleaned["what_this_does_not_prove"]
    if not disclaimer:
        logger.warning("opportunity brief rejected: 'what_this_does_not_prove' is empty")
        return None
    lowered = disclaimer.casefold()
    if not any(keyword.casefold() in lowered for keyword in METHODOLOGY_LIMITATION_KEYWORDS):
        logger.warning(
            "opportunity brief rejected: 'what_this_does_not_prove' states no known limitation"
        )
        return None

    # LLM の自己申告は捨て、本文から再抽出する。入力 Evidence の順序を保つ。
    mentioned: set[str] = set()
    for field in TEXT_SECTIONS:
        mentioned |= _cited_ids(cleaned[field])
    recited = [evidence_id for evidence_id in pack.evidence_ids if evidence_id in mentioned]

    return brief.model_copy(update={**cleaned, "cited_evidence_ids": recited})
