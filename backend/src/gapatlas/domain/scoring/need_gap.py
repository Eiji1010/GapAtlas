"""Need Gap Signal Score。docs/scoring.md 1章。

```text
NeedGapScore = 0.40*demand + 0.25*pain + 0.25*solution_gap + 0.10*news_urgency
```

`demand` 以外の成分が欠損した場合は、欠損成分を除いた重みで再正規化する。
欠損を 0 として扱ってはいけない(欠損と「値が0」は別である)。
"""

from __future__ import annotations

from datetime import datetime

from gapatlas.domain.models.classification import ClassifiedEvidence
from gapatlas.domain.models.common import ensure_utc
from gapatlas.domain.models.normalized import NormalizedEvidence
from gapatlas.domain.models.scores import NeedGapResult, ScoreComponents
from gapatlas.domain.scoring.constants import (
    COMPONENT_DEMAND,
    COMPONENT_NEWS_URGENCY,
    COMPONENT_PAIN,
    COMPONENT_SOLUTION_GAP,
    NEED_GAP_WEIGHTS,
    SCORE_MAX,
    SCORE_MIN,
)
from gapatlas.domain.scoring.demand import compute_demand
from gapatlas.domain.scoring.news import compute_news_urgency
from gapatlas.domain.scoring.pain import compute_pain
from gapatlas.domain.scoring.rounding import clip
from gapatlas.domain.scoring.solution import compute_solution_gap


def compute_components(
    evidence: NormalizedEvidence,
    classified: ClassifiedEvidence,
    scan_time: datetime,
) -> ScoreComponents:
    """4つの下位スコアを算出する。算出不能な成分は `None`(0 で代替しない)。"""
    scan_time = ensure_utc(scan_time)
    return ScoreComponents(
        demand=compute_demand(evidence.trends),
        pain=compute_pain(classified.rising_queries),
        solution_gap=compute_solution_gap(classified.search_results),
        news_urgency=compute_news_urgency(classified.news_articles, scan_time),
    )


def _weighted_components(
    components: ScoreComponents,
) -> tuple[tuple[str, float, float | None], ...]:
    """`(成分名, 重み, 値)` の並び。成分名は `ScoreComponents` のフィールド名と一致する。"""
    return (
        (COMPONENT_DEMAND, NEED_GAP_WEIGHTS[COMPONENT_DEMAND], components.demand),
        (COMPONENT_PAIN, NEED_GAP_WEIGHTS[COMPONENT_PAIN], components.pain),
        (
            COMPONENT_SOLUTION_GAP,
            NEED_GAP_WEIGHTS[COMPONENT_SOLUTION_GAP],
            components.solution_gap,
        ),
        (
            COMPONENT_NEWS_URGENCY,
            NEED_GAP_WEIGHTS[COMPONENT_NEWS_URGENCY],
            components.news_urgency,
        ),
    )


def compute_need_gap(components: ScoreComponents) -> NeedGapResult:
    """成分から Need Gap Signal Score を算出する。

    `demand` が `None` の場合はスコアを出さない(Trends は必須ソース)。
    それ以外の欠損成分は重みから除外して再正規化し、使用した成分名を
    `components_used` に記録する。

    「Core Source が2つ以上欠損」の判定はここでは行わない。成分だけを見る
    関数であり、ソース状態に基づく Hard Rules は `engine.py` の責務である。
    """
    if components.demand is None:
        return NeedGapResult(score=None, components=components, components_used=[])

    components_used: list[str] = []
    weighted_sum = 0.0
    weight_sum = 0.0
    for name, weight, value in _weighted_components(components):
        if value is None:
            continue
        components_used.append(name)
        weighted_sum += weight * value
        weight_sum += weight

    score = clip(weighted_sum / weight_sum, SCORE_MIN, SCORE_MAX)
    return NeedGapResult(score=score, components=components, components_used=components_used)
