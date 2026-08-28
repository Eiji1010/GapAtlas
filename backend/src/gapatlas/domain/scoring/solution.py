"""Solution Coverage Gap(weight 25%)。docs/scoring.md 4章。

これは「実際のサービス供給不足」ではなく **「検索上で見える Solution Coverage
の不足」** である。UI には必ずその旨を明示する(docs/methodology.md)。
"""

from __future__ import annotations

import math
from collections.abc import Sequence

from gapatlas.domain.models.classification import (
    CONFIDENCE_MAX,
    CONFIDENCE_MIN,
    ClassifiedSearchResult,
)
from gapatlas.domain.scoring.constants import (
    SCORE_MAX,
    SCORE_MIN,
    SCORE_SCALE,
    SOLUTION_COVERAGE_WEIGHTS,
    TOP_N,
)
from gapatlas.domain.scoring.rounding import clip


def _rank_weight(position: int) -> float:
    """`rank_weight = 1 / log2(position + 1)`。`position` は 1 始まり。

    `position >= 1` は `SearchResultItem` が保証するため `log2` の引数は
    2 以上になり、ゼロ除算も負の対数も起きない。
    """
    return 1.0 / math.log2(position + 1)


def compute_solution_gap(classified: Sequence[ClassifiedSearchResult]) -> float | None:
    """検索結果の分類結果から Solution Coverage Gap を算出する。

    `position` の昇順に並べ替えてから上位 `TOP_N` 件を対象とするため、
    入力順には依存しない(同順位は入力順を保つ安定ソート)。

    分母は対象 `TOP_N` 件 **すべて** の順位重みの合計であり、分類済みの件だけで
    割ってはいけない。`organic_results` が空の場合は `None`。
    """
    if not classified:
        return None

    top_results = sorted(classified, key=lambda entry: entry.item.position)[:TOP_N]

    numerator = 0.0
    denominator = 0.0
    for entry in top_results:
        rank_weight = _rank_weight(entry.item.position)
        coverage_weight = SOLUTION_COVERAGE_WEIGHTS[entry.classification.classification]
        confidence = clip(entry.classification.confidence, CONFIDENCE_MIN, CONFIDENCE_MAX)
        numerator += coverage_weight * confidence * rank_weight
        denominator += rank_weight

    solution_visibility = SCORE_SCALE * numerator / denominator
    return clip(SCORE_SCALE - solution_visibility, SCORE_MIN, SCORE_MAX)
