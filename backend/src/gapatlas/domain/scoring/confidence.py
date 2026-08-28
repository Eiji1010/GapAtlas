"""Evidence Confidence。docs/scoring.md 6章。

**Need Gap Score とは完全に別のスコアである。** スコアと確信度を混ぜると
「データが乏しいので低い」のか「データは十分で本当に低い」のかが区別できなく
なるため分離している(docs/methodology.md)。
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from datetime import datetime
from statistics import fmean, pstdev

from gapatlas.domain.models.common import (
    CORE_SOURCES,
    SourceName,
    ensure_utc,
)
from gapatlas.domain.models.normalized import NormalizedEvidence
from gapatlas.domain.models.query_profile import QueryProfile
from gapatlas.domain.models.scores import (
    ConfidenceBreakdown,
    ConfidenceResult,
    ScoreComponents,
)
from gapatlas.domain.scoring.constants import (
    AGREEMENT_SPREAD_FACTOR,
    CAP_MISSING_ONE_CORE_SOURCE,
    CAP_MULTIPLE_MISSING_CORE_SOURCES,
    CAP_TRENDS_MISSING,
    CAP_TRENDS_ZERO_RATIO,
    CONFIDENCE_WEIGHT_DATA_COMPLETENESS,
    CONFIDENCE_WEIGHT_FRESHNESS,
    CONFIDENCE_WEIGHT_LOCALIZATION_QUALITY,
    CONFIDENCE_WEIGHT_SAMPLE_SUFFICIENCY,
    CONFIDENCE_WEIGHT_SOURCE_AGREEMENT,
    FRESHNESS_DECAY_DAYS,
    LOCALIZATION_QUALITY_BY_REVIEW_STATUS,
    MIN_AGREEMENT_COMPONENTS,
    MISSING_ONE_CORE_SOURCE_CAP,
    MULTIPLE_MISSING_CORE_SOURCES_THRESHOLD,
    NON_PRIMARY_LANGUAGE_PENALTY,
    SAMPLE_TARGETS,
    SCORE_MAX,
    SCORE_MIN,
    SCORE_SCALE,
    SECONDS_PER_DAY,
    SINGLE_MISSING_CORE_SOURCE_COUNT,
    TRENDS_ZERO_RATIO_CAP,
    ZERO_RATIO_THRESHOLD,
)
from gapatlas.domain.scoring.rounding import clip

NO_DATA_AGE_DAYS = 0.0
"""age を決められないときに使う値。

`trends` が OK なのに系列が空、`news` が OK なのに日付付き記事が0件、といった
状態は本来 MISSING として扱われるべきだが、ソース状態の判定はアダプタ側の
責務であり、ここで例外にすると Confidence 自体が返せなくなる。そのソースの
age を 0(=最新)として扱い、欠けている事実は Sample sufficiency と
Data completeness が別途反映する。
"""


def compute_data_completeness(evidence: NormalizedEvidence) -> float:
    """`100 * (OK の Core Source 数) / 4`。"""
    return SCORE_SCALE * len(evidence.ok_core_sources()) / len(CORE_SOURCES)


def _sample_count(evidence: NormalizedEvidence, source: SourceName) -> int:
    """Sample sufficiency で数える件数。"""
    if source is SourceName.TRENDS:
        # 各 demand query の系列長のうち最小値。1系列でも 12 点未満なら
        # そのクエリの Demand が計算できないため、最小値を代表値にする。
        if evidence.trends is None or not evidence.trends.series:
            return 0
        return min(len(series.points) for series in evidence.trends.series)
    if source is SourceName.RELATED_QUERIES:
        return len(evidence.rising_queries)
    if source is SourceName.SEARCH:
        return len(evidence.search_results)
    if source is SourceName.NEWS:
        return sum(1 for article in evidence.news_articles if article.published_at is not None)
    return 0


def compute_sample_sufficiency(evidence: NormalizedEvidence) -> float:
    """`100 * mean([clip(count_s / target_s, 0, 1) for s in 4つの Core Source])`。

    MISSING(= OK でない)のソースは ratio 0。平均は常に4ソース固定で取る。
    """
    ok_sources = set(evidence.ok_core_sources())
    ratios = [
        clip(_sample_count(evidence, source) / SAMPLE_TARGETS[source], 0.0, 1.0)
        if source in ok_sources
        else 0.0
        for source in CORE_SOURCES
    ]
    return SCORE_SCALE * fmean(ratios)


def compute_localization_quality(profile: QueryProfile) -> float:
    """`review_status` から決まる基準値。主要言語でなければ 20 減じる(下限 0)。"""
    quality = LOCALIZATION_QUALITY_BY_REVIEW_STATUS[profile.review_status]
    if not profile.is_primary_language:
        quality -= NON_PRIMARY_LANGUAGE_PENALTY
    return clip(quality, SCORE_MIN, SCORE_MAX)


def compute_source_agreement(components: ScoreComponents) -> float:
    """下位スコアの散らばりが小さいほど高い。

    `None` でない成分が2つ未満なら 0。`pstdev` は **母標準偏差**(N で割る)。
    標本標準偏差(N-1)を使ってはいけない。
    """
    values = [
        value / SCORE_SCALE
        for value in (
            components.demand,
            components.pain,
            components.solution_gap,
            components.news_urgency,
        )
        if value is not None
    ]
    if len(values) < MIN_AGREEMENT_COMPONENTS:
        return SCORE_MIN
    spread = pstdev(values)
    return clip(
        SCORE_SCALE * (1.0 - AGREEMENT_SPREAD_FACTOR * spread),
        SCORE_MIN,
        SCORE_MAX,
    )


def _cache_age_days(evidence: NormalizedEvidence, source: SourceName) -> float:
    """キャッシュ経過時間(日)。`fetches` に無ければ 0(新規取得扱い)。"""
    fetch = evidence.fetches.get(source)
    if fetch is None:
        return NO_DATA_AGE_DAYS
    return fetch.cache_age_seconds / SECONDS_PER_DAY


def _latest_trends_timestamp(evidence: NormalizedEvidence) -> datetime | None:
    if evidence.trends is None:
        return None
    timestamps = [
        series.latest_timestamp
        for series in evidence.trends.series
        if series.latest_timestamp is not None
    ]
    if not timestamps:
        return None
    return max(timestamps)


def _latest_news_published_at(evidence: NormalizedEvidence) -> datetime | None:
    published = [
        article.published_at
        for article in evidence.news_articles
        if article.published_at is not None
    ]
    if not published:
        return None
    return max(published)


def _source_age_days(
    evidence: NormalizedEvidence, source: SourceName, scan_time: datetime
) -> float:
    """根拠データの古さ(日)。"""
    if source is SourceName.TRENDS:
        latest = _latest_trends_timestamp(evidence)
        if latest is None:
            return NO_DATA_AGE_DAYS
        return (scan_time - latest).total_seconds() / SECONDS_PER_DAY
    if source is SourceName.NEWS:
        latest = _latest_news_published_at(evidence)
        if latest is None:
            return NO_DATA_AGE_DAYS
        return (scan_time - latest).total_seconds() / SECONDS_PER_DAY
    return _cache_age_days(evidence, source)


def compute_freshness(evidence: NormalizedEvidence, scan_time: datetime) -> float:
    """`mean([100 * exp(-max(0, age_days_s) / 30) for s in OK の Core Source])`。

    `OK` の Core Source が0件の場合は 0。
    """
    ok_sources = evidence.ok_core_sources()
    if not ok_sources:
        return SCORE_MIN
    scores = [
        SCORE_SCALE
        * math.exp(-max(0.0, _source_age_days(evidence, source, scan_time)) / FRESHNESS_DECAY_DAYS)
        for source in ok_sources
    ]
    return clip(fmean(scores), SCORE_MIN, SCORE_MAX)


def compute_trends_zero_ratio(evidence: NormalizedEvidence) -> float | None:
    """Trends 全 demand query 系列の **全データ点** に対する 0 の割合。

    クエリごとに個別判定せず、Trends データ全体で1つの比率を出す
    (docs/scoring.md 6章 Hard Rule 4)。データ点が1つも無い場合は
    分母 0 のため評価しない(`None`)。
    """
    if evidence.trends is None:
        return None
    values = [point.value for series in evidence.trends.series for point in series.points]
    if not values:
        return None
    return sum(1 for value in values if value == 0.0) / len(values)


def _apply_hard_rules(
    confidence_raw: float,
    missing_core_sources: Sequence[SourceName],
    zero_ratio: float | None,
) -> tuple[float, list[str]]:
    """Hard Rules をこの順に適用し、適用した規則の識別子を返す。

    Hard Rules 1・2 は `status` に関する規則なので Confidence の上限は課さない
    (status の決定は `engine.py` の責務)。ただし「何が起きたか」を利用者へ
    示すため `applied_caps` には記録する。
    """
    applied_caps: list[str] = []
    confidence = confidence_raw

    # Hard Rule 1: trends が MISSING
    if SourceName.TRENDS in missing_core_sources:
        applied_caps.append(CAP_TRENDS_MISSING)

    # Hard Rule 2: Core Source の MISSING が2つ以上
    if len(missing_core_sources) >= MULTIPLE_MISSING_CORE_SOURCES_THRESHOLD:
        applied_caps.append(CAP_MULTIPLE_MISSING_CORE_SOURCES)

    # Hard Rule 3: Core Source の MISSING がちょうど1つ
    if len(missing_core_sources) == SINGLE_MISSING_CORE_SOURCE_COUNT:
        confidence = min(confidence, MISSING_ONE_CORE_SOURCE_CAP)
        applied_caps.append(CAP_MISSING_ONE_CORE_SOURCE)

    # Hard Rule 4: Trends のゼロ率が 50% 以上
    if zero_ratio is not None and zero_ratio >= ZERO_RATIO_THRESHOLD:
        confidence = min(confidence, TRENDS_ZERO_RATIO_CAP)
        applied_caps.append(CAP_TRENDS_ZERO_RATIO)

    return confidence, applied_caps


def compute_confidence(
    evidence: NormalizedEvidence,
    profile: QueryProfile,
    components: ScoreComponents,
    scan_time: datetime,
) -> ConfidenceResult:
    """Evidence Confidence を算出し Hard Rules 3・4 を適用する。

    `ConfidenceResult.score` は Hard Rules 適用後の **float**。公開表現への
    丸めは `engine.py` が行う。

    `scan_time` は引数で受け取る。関数内で現在時刻を取得しない。naive な
    datetime は `InvalidTemporalValueError` にする。
    """
    scan_time = ensure_utc(scan_time)

    breakdown = ConfidenceBreakdown(
        data_completeness=compute_data_completeness(evidence),
        sample_sufficiency=compute_sample_sufficiency(evidence),
        localization_quality=compute_localization_quality(profile),
        source_agreement=compute_source_agreement(components),
        freshness=compute_freshness(evidence, scan_time),
    )

    confidence_raw = (
        CONFIDENCE_WEIGHT_DATA_COMPLETENESS * breakdown.data_completeness
        + CONFIDENCE_WEIGHT_SAMPLE_SUFFICIENCY * breakdown.sample_sufficiency
        + CONFIDENCE_WEIGHT_LOCALIZATION_QUALITY * breakdown.localization_quality
        + CONFIDENCE_WEIGHT_SOURCE_AGREEMENT * breakdown.source_agreement
        + CONFIDENCE_WEIGHT_FRESHNESS * breakdown.freshness
    )

    confidence, applied_caps = _apply_hard_rules(
        confidence_raw,
        evidence.missing_core_sources(),
        compute_trends_zero_ratio(evidence),
    )

    return ConfidenceResult(
        score=clip(confidence, SCORE_MIN, SCORE_MAX),
        breakdown=breakdown,
        applied_caps=applied_caps,
    )
