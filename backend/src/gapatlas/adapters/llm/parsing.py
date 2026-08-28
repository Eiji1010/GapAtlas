"""LLM の生応答から分類リストを取り出す。

正本は docs/llm-prompts.md「共通のレスポンス規約」。

期待する形:

```json
{"results": [{"index": 0, "classification": "SHORTAGE", "confidence": 0.94}]}
```

**LLM が入力と同数・同順で返すことを信用しない。** 必ず `index` で照合する。

ログには件数と index のみを出す。**分類対象の文字列そのものはログへ出さない**
(個人情報や検索語の混入を避けるため)。
"""

from __future__ import annotations

import json
import logging
import math
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Final

from gapatlas.adapters.llm.errors import LlmResponseError
from gapatlas.domain.models.classification import (
    CONFIDENCE_MAX,
    CONFIDENCE_MIN,
    NewsClassification,
    NewsRelevance,
    PainCategory,
    PainClassification,
    SolutionCategory,
    SolutionClassification,
)

logger = logging.getLogger(__name__)

RESULTS_KEY: Final[str] = "results"
INDEX_KEY: Final[str] = "index"
CLASSIFICATION_KEY: Final[str] = "classification"
CONFIDENCE_KEY: Final[str] = "confidence"

FALLBACK_CONFIDENCE: Final[float] = 0.0
"""既定値で補完した項目の confidence。スコアへ寄与させないため 0.0 とする。"""


@dataclass(frozen=True, slots=True)
class ParsedClassifications[CategoryT: StrEnum]:
    """分類結果と、そのうち何件が実際に LLM から解決できたか。

    `resolved_count == 0` は「分類が全滅した」状態を表す。既定値で埋めた結果を
    そのままスコアへ流すと、たとえば `solution_gap` が 100(最大値)として
    正規の観測値のように見えてしまう。呼び出し側が欠損として扱えるよう、
    件数を区別できる形で返す(docs/llm-prompts.md「共通のレスポンス規約」の
    「分類が全滅した場合、その成分は None(欠損)として扱い、Confidence へ反映する」)。
    """

    items: list[tuple[CategoryT, float]]
    resolved_count: int

    @property
    def is_total_fallback(self) -> bool:
        """1件も解決できなかったか。入力が空の場合は False。"""
        return bool(self.items) and self.resolved_count == 0


def _clip_confidence(value: object) -> float:
    """confidence を 0.0〜1.0 の float へ正規化する。

    数値でない、NaN、bool、範囲外はすべて丸める。例外にはしない
    (docs/llm-prompts.md「confidence が数値でない、または範囲外の場合は clip する」)。
    """
    if isinstance(value, bool) or not isinstance(value, int | float):
        return FALLBACK_CONFIDENCE
    number = float(value)
    if math.isnan(number):
        return FALLBACK_CONFIDENCE
    return max(CONFIDENCE_MIN, min(CONFIDENCE_MAX, number))


def _coerce_index(value: object) -> int | None:
    """`index` を int へ変換する。bool と数値でない値は None を返す。"""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    return None


def _decode_payload(payload: str | Mapping[str, Any]) -> Mapping[str, Any] | None:
    """生応答を Mapping へ変換する。

    Raises:
        LlmResponseError: `payload` が JSON として壊れている場合。
    """
    if isinstance(payload, Mapping):
        return payload
    try:
        decoded: object = json.loads(payload)
    except (json.JSONDecodeError, ValueError) as exc:
        message = "LLM response is not valid JSON"
        raise LlmResponseError(message) from exc
    if isinstance(decoded, Mapping):
        return decoded
    logger.warning("LLM response JSON is not an object; falling back to defaults")
    return None


def parse_classification_results[CategoryT: StrEnum](
    payload: str | Mapping[str, Any],
    *,
    expected_count: int,
    category: type[CategoryT],
    default: CategoryT,
) -> ParsedClassifications[CategoryT]:
    """分類結果を `expected_count` 件の `(category, confidence)` へ変換する。

    **必ず `expected_count` 件を返す。** 呼び出し側は入力と `zip` してよい。

    挙動(docs/llm-prompts.md「共通のレスポンス規約」):

    - `index` で照合する。同数・同順で返ってくることを前提にしない
    - 欠落した `index` は `default` + `confidence = 0.0` で補完する
    - 未知の `classification` 値は `default` + `confidence = 0.0` へフォールバックし警告を出す
    - `confidence` が数値でない・範囲外・NaN の場合は 0.0〜1.0 へ clip する
    - 範囲外の `index`、重複した `index`(2件目以降を無視)、要素が object でない、
      `results` が配列でない、トップレベルが object でない場合は
      **例外にせず既定値で埋める**(警告ログのみ)
    - **JSON 自体が壊れている場合のみ `LlmResponseError` を送出する。**
      構造が部分的に壊れているだけならスキャンを止めない

    Args:
        payload: LLM の生応答。JSON 文字列、または tool use の input(Mapping)。
        expected_count: 入力件数。負値は 0 として扱う。
        category: 対象の分類 Enum。
        default: 補完・フォールバックに使う既定値。

    Raises:
        LlmResponseError: `payload` が文字列で、JSON として解釈できない場合。
    """
    count = max(0, expected_count)
    parsed: list[tuple[CategoryT, float]] = [(default, FALLBACK_CONFIDENCE)] * count

    decoded = _decode_payload(payload)
    if decoded is None:
        return ParsedClassifications(parsed, 0)

    raw_results = decoded.get(RESULTS_KEY)
    if not isinstance(raw_results, list):
        logger.warning("LLM response has no '%s' array; filling %d defaults", RESULTS_KEY, count)
        return ParsedClassifications(parsed, 0)

    filled: set[int] = set()
    resolved_count = 0
    for entry in raw_results:
        if not isinstance(entry, Mapping):
            logger.warning("LLM result entry is not an object; ignored")
            continue
        index = _coerce_index(entry.get(INDEX_KEY))
        if index is None or not 0 <= index < count:
            logger.warning("LLM result has an out-of-range or non-integer index; ignored")
            continue
        if index in filled:
            logger.warning("LLM returned a duplicate index %d; keeping the first one", index)
            continue
        filled.add(index)
        value, confidence, resolved = _resolve_entry(entry, index, category, default)
        parsed[index] = (value, confidence)
        if resolved:
            resolved_count += 1

    missing = count - len(filled)
    if missing > 0:
        logger.warning("LLM omitted %d of %d results; filled with defaults", missing, count)
    return ParsedClassifications(parsed, resolved_count)


def _resolve_entry[CategoryT: StrEnum](
    entry: Mapping[str, Any], index: int, category: type[CategoryT], default: CategoryT
) -> tuple[CategoryT, float, bool]:
    """1件の結果を `(category, confidence, 解決できたか)` へ変換する。

    未知カテゴリ・非文字列カテゴリは既定値へフォールバックし、confidence は 0.0 にする
    (信用できない分類にスコア上の重みを与えないため)。3要素目は「LLM の値として
    解決できたか」で、既定値へのフォールバックは False になる。
    """
    raw = entry.get(CLASSIFICATION_KEY)
    if not isinstance(raw, str):
        logger.warning(
            "LLM returned a non-string %s at index %d; using %s",
            category.__name__,
            index,
            default.value,
        )
        return default, FALLBACK_CONFIDENCE, False
    try:
        resolved = category(raw.strip().upper())
    except ValueError:
        logger.warning(
            "LLM returned an unknown %s value at index %d; using %s",
            category.__name__,
            index,
            default.value,
        )
        return default, FALLBACK_CONFIDENCE, False
    return resolved, _clip_confidence(entry.get(CONFIDENCE_KEY)), True


def parse_pain_classifications(
    payload: str | Mapping[str, Any], expected_count: int
) -> list[PainClassification]:
    """rising query の分類結果へ変換する。既定値は `NEUTRAL`。"""
    parsed = parse_classification_results(
        payload,
        expected_count=expected_count,
        category=PainCategory,
        default=PainCategory.NEUTRAL,
    )
    _reject_total_fallback(parsed)
    return [
        PainClassification(classification=value, confidence=confidence)
        for value, confidence in parsed.items
    ]


def parse_solution_classifications(
    payload: str | Mapping[str, Any], expected_count: int
) -> list[SolutionClassification]:
    """検索結果の分類結果へ変換する。既定値は `OTHER`。"""
    parsed = parse_classification_results(
        payload,
        expected_count=expected_count,
        category=SolutionCategory,
        default=SolutionCategory.OTHER,
    )
    _reject_total_fallback(parsed)
    return [
        SolutionClassification(classification=value, confidence=confidence)
        for value, confidence in parsed.items
    ]


def parse_news_classifications(
    payload: str | Mapping[str, Any], expected_count: int
) -> list[NewsClassification]:
    """ニュース記事の分類結果へ変換する。既定値は `UNRELATED`。"""
    parsed = parse_classification_results(
        payload,
        expected_count=expected_count,
        category=NewsRelevance,
        default=NewsRelevance.UNRELATED,
    )
    _reject_total_fallback(parsed)
    return [
        NewsClassification(classification=value, confidence=confidence)
        for value, confidence in parsed.items
    ]


def _reject_total_fallback[CategoryT: StrEnum](parsed: ParsedClassifications[CategoryT]) -> None:
    """1件も分類できなかった場合に例外にする。

    既定値で全件を埋めた結果をスコアへ流すと、`solution_gap = 100`(最大値)や
    `pain = 0` が「実際に観測された値」として NeedGapScore へ入り、Evidence
    Confidence にも反映されない。docs/llm-prompts.md は「分類が全滅した場合、
    その成分は None(欠損)として扱い、Confidence へ反映する」と定めているため、
    application 層が該当ソースを MISSING として扱えるよう例外で知らせる。

    部分的な欠落(一部の index だけ埋めた場合)は例外にしない。既定値の
    confidence が 0.0 なのでスコアへ寄与せず、件数は Sample sufficiency で
    評価されるためである。

    Raises:
        LlmResponseError: 入力が1件以上あり、そのすべてが既定値だった場合。
    """
    if parsed.is_total_fallback:
        message = (
            f"LLM classification failed for all {len(parsed.items)} items; "
            "treat this source as missing"
        )
        raise LlmResponseError(message)
