"""`LLM_MODE=anthropic` 用のクライアント。

ADR 0002 のとおり **Anthropic API を直接呼ぶ**(Bedrock ではない)。モデル ID は
`Settings.anthropic_model`、API キーは `Settings.anthropic_api_key` から読む。

**Structured JSON の取得方式: tool use を使い、`tool_choice` で1つのツールを強制する。**
自由文の中に JSON を埋める形式を避けるため(docs/llm-prompts.md「出力は必ず Structured
JSON」)。ツール定義には `strict` を付けず、応答は `parsing.py` の寛容なパーサで受ける。
モデルがツールを使わずテキストで返した場合に備え、テキストブロックを連結して JSON
として解釈するフォールバックも持つ(その場合 JSON が壊れていれば `LlmResponseError`)。

**エラー方針(呼び出し側との契約):**

- 分類メソッドは失敗を握りつぶさず `LlmRequestError` / `LlmResponseError`
  (どちらも `LlmError`)を送出する。application 層がそのソースを `MISSING` として扱い、
  Evidence Confidence へ反映する。**スキャン全体を止めるのは呼び出し側の責務ではない。**
- `write_brief` は例外を投げず `None` を返す。Brief は出さないほうが安全であり、
  戻り値の型がすでに `| None` であるため(docs/llm-prompts.md 4章)。

**API キーを例外メッセージ・ログへ出さない。** 外部 SDK の例外は型名だけを載せて包む。
"""

from __future__ import annotations

import json
import logging
from collections.abc import Mapping, Sequence
from typing import Any, Final

from gapatlas.adapters.llm.brief_validation import validate_brief
from gapatlas.adapters.llm.errors import LlmError, LlmRequestError, LlmResponseError
from gapatlas.adapters.llm.models import EvidencePack
from gapatlas.adapters.llm.parsing import (
    parse_news_classifications,
    parse_pain_classifications,
    parse_solution_classifications,
)
from gapatlas.adapters.llm.prompts import (
    SYSTEM_PROMPT_BRIEF,
    SYSTEM_PROMPT_NEWS_ARTICLES,
    SYSTEM_PROMPT_RISING_QUERIES,
    SYSTEM_PROMPT_SEARCH_RESULTS,
    build_brief_prompt,
    build_news_article_prompt,
    build_rising_query_prompt,
    build_search_result_prompt,
)
from gapatlas.config.settings import Settings
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

logger = logging.getLogger(__name__)

CLASSIFICATION_TOOL_NAME: Final[str] = "record_classifications"
BRIEF_TOOL_NAME: Final[str] = "record_opportunity_brief"

CLASSIFICATION_MAX_TOKENS: Final[int] = 4096
BRIEF_MAX_TOKENS: Final[int] = 4096

_CONFIDENCE_SCHEMA: Final[dict[str, Any]] = {
    "type": "number",
    "minimum": 0.0,
    "maximum": 1.0,
    "description": "How certain the classification is. Lower it when unsure.",
}


def _classification_tool(name: str, categories: Sequence[str]) -> dict[str, Any]:
    """`{"results": [{index, classification, confidence}]}` を強制するツール定義。"""
    return {
        "name": name,
        "description": (
            "Record one classification per input item. Use the item's index value. "
            "Return every item exactly once."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "results": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "index": {"type": "integer", "minimum": 0},
                            "classification": {"type": "string", "enum": list(categories)},
                            "confidence": _CONFIDENCE_SCHEMA,
                        },
                        "required": ["index", "classification", "confidence"],
                        "additionalProperties": False,
                    },
                }
            },
            "required": ["results"],
            "additionalProperties": False,
        },
    }


_BRIEF_TOOL: Final[dict[str, Any]] = {
    "name": BRIEF_TOOL_NAME,
    "description": (
        "Record the Opportunity Brief. Cite evidence inline as [E1]. Never write a URL. "
        "Never state a fact that is not in the evidence pack."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "why_now": {"type": "string"},
            "what_people_are_struggling_with": {"type": "string"},
            "visible_solutions": {"type": "string"},
            "what_this_does_not_prove": {"type": "string"},
            "next_validation": {"type": "string"},
            "cited_evidence_ids": {"type": "array", "items": {"type": "string"}},
        },
        "required": [
            "why_now",
            "what_people_are_struggling_with",
            "visible_solutions",
            "what_this_does_not_prove",
            "next_validation",
            "cited_evidence_ids",
        ],
        "additionalProperties": False,
    },
}


class AnthropicLlmClient:
    """Anthropic Messages API を使う分類器兼 Brief 生成器。

    `LlmClassifier` と `BriefWriter` の両方を満たす。
    """

    def __init__(self, settings: Settings, *, client: Any | None = None) -> None:
        """クライアントを組み立てる。

        Args:
            settings: `anthropic_model` と `anthropic_api_key` を読む。
            client: 注入するクライアント。テストは必ずフェイクを渡すこと
                (単体テストで実 API を呼ばない。API キーが無い前提)。

        Raises:
            LlmError: `client` 未指定で API キーが無い、または `anthropic` パッケージが
                未インストールの場合。
        """
        self._model = settings.anthropic_model
        if client is not None:
            self._client: Any = client
            return
        api_key = settings.anthropic_api_key
        if api_key is None:
            message = "ANTHROPIC_API_KEY is required when LLM_MODE=anthropic"
            raise LlmError(message)
        self._client = _build_default_client(api_key.get_secret_value())

    # --- 分類 -------------------------------------------------------------------------

    def classify_rising_queries(
        self, items: Sequence[RisingQuery], profile: QueryProfile
    ) -> list[PainClassification]:
        """rising query を Pain カテゴリへ分類する。**成長率は渡さない。**"""
        payload = self._request_classification(
            system=SYSTEM_PROMPT_RISING_QUERIES,
            user=build_rising_query_prompt(items, profile),
            categories=[member.value for member in PainCategory],
        )
        return parse_pain_classifications(payload, len(items))

    def classify_search_results(
        self, items: Sequence[SearchResultItem], profile: QueryProfile
    ) -> list[SolutionClassification]:
        """検索結果を Solution カテゴリへ分類する。**`position` は渡さない。**"""
        payload = self._request_classification(
            system=SYSTEM_PROMPT_SEARCH_RESULTS,
            user=build_search_result_prompt(items, profile),
            categories=[member.value for member in SolutionCategory],
        )
        return parse_solution_classifications(payload, len(items))

    def classify_news_articles(
        self, items: Sequence[NewsArticle], profile: QueryProfile
    ) -> list[NewsClassification]:
        """ニュース記事を関連性カテゴリへ分類する。**日付は渡さない。**"""
        payload = self._request_classification(
            system=SYSTEM_PROMPT_NEWS_ARTICLES,
            user=build_news_article_prompt(items, profile),
            categories=[member.value for member in NewsRelevance],
        )
        return parse_news_classifications(payload, len(items))

    # --- Opportunity Brief -------------------------------------------------------------

    def write_brief(self, pack: EvidencePack) -> OpportunityBrief | None:
        """Brief を生成し、`validate_brief` を通してから返す。

        API 障害・応答不正・検証失敗のいずれでも `None` を返す(例外を上へ投げない)。
        """
        try:
            payload = self._call(
                system=SYSTEM_PROMPT_BRIEF,
                user=build_brief_prompt(pack),
                tool=_BRIEF_TOOL,
                tool_name=BRIEF_TOOL_NAME,
                max_tokens=BRIEF_MAX_TOKENS,
            )
        except LlmError:
            logger.warning("opportunity brief skipped: the LLM request or response failed")
            return None
        if isinstance(payload, str):
            # ツールを使わずテキストで返された場合。壊れていれば Brief を出さない。
            try:
                decoded: object = json.loads(payload)
            except ValueError:
                logger.warning("opportunity brief skipped: the response was not valid JSON")
                return None
            payload = decoded if isinstance(decoded, Mapping) else {}
        try:
            brief = OpportunityBrief.model_validate(dict(payload))
        except ValueError:
            logger.warning("opportunity brief skipped: the response did not match the contract")
            return None
        return validate_brief(brief, pack)

    # --- 内部 -------------------------------------------------------------------------

    def _request_classification(
        self, *, system: str, user: str, categories: Sequence[str]
    ) -> Mapping[str, Any] | str:
        return self._call(
            system=system,
            user=user,
            tool=_classification_tool(CLASSIFICATION_TOOL_NAME, categories),
            tool_name=CLASSIFICATION_TOOL_NAME,
            max_tokens=CLASSIFICATION_MAX_TOKENS,
        )

    def _call(
        self,
        *,
        system: str,
        user: str,
        tool: dict[str, Any],
        tool_name: str,
        max_tokens: int,
    ) -> Mapping[str, Any] | str:
        """1回の Messages API 呼び出しを行い、構造化ペイロードを取り出す。

        Raises:
            LlmRequestError: 応答を得られなかった場合。
            LlmResponseError: 応答から構造化ペイロードを取り出せなかった場合。
        """
        try:
            response = self._client.messages.create(
                model=self._model,
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": user}],
                tools=[tool],
                tool_choice={
                    "type": "tool",
                    "name": tool_name,
                    "disable_parallel_tool_use": True,
                },
            )
        except Exception as exc:
            # 原因例外の本文は載せない(秘密情報が混ざらないようにする)。
            message = f"Anthropic Messages API request failed ({type(exc).__name__})"
            raise LlmRequestError(message) from exc
        return _extract_payload(response, tool_name)


def _build_default_client(api_key: str) -> Any:
    """`anthropic` を遅延 import してクライアントを作る。

    optional extra(`llm`)なので、未インストール環境で本モジュールの import 自体が
    失敗しないよう、トップレベルでは import しない。

    Raises:
        LlmError: `anthropic` パッケージが未インストールの場合。
    """
    try:
        import anthropic  # noqa: PLC0415
    except ImportError as exc:
        message = (
            "the 'anthropic' package is not installed; "
            "install the 'llm' optional extra to use LLM_MODE=anthropic"
        )
        raise LlmError(message) from exc
    return anthropic.Anthropic(api_key=api_key)


def _extract_payload(response: Any, tool_name: str) -> Mapping[str, Any] | str:
    """応答から tool use の input を取り出す。無ければテキストを返す。

    Raises:
        LlmResponseError: tool use もテキストも取り出せなかった場合。
    """
    blocks = getattr(response, "content", None)
    if not isinstance(blocks, Sequence) or isinstance(blocks, str | bytes):
        message = "Anthropic response has no content blocks"
        raise LlmResponseError(message)

    texts: list[str] = []
    for block in blocks:
        block_type = getattr(block, "type", None)
        if block_type == "tool_use" and getattr(block, "name", None) == tool_name:
            tool_input = getattr(block, "input", None)
            if isinstance(tool_input, Mapping):
                return tool_input
            message = "Anthropic tool_use block has a non-object input"
            raise LlmResponseError(message)
        if block_type == "text":
            text = getattr(block, "text", None)
            if isinstance(text, str):
                texts.append(text)

    if texts:
        # ツールを使わずテキストで返された場合のフォールバック。壊れた JSON なら
        # parsing 側が LlmResponseError にする。
        logger.warning("Anthropic response used no tool; falling back to strict text parsing")
        return "".join(texts)

    message = "Anthropic response contains neither a tool_use block nor text"
    raise LlmResponseError(message)
