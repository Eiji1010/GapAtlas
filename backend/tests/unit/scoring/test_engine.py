"""`evaluate_country` のテスト。docs/scoring.md 6章 Hard Rules と 7章 ステータス。"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from conftest import (
    SCAN_TIME,
    make_classified,
    make_evidence,
    make_news,
    make_profile,
    make_rising,
    make_search,
    make_trends,
)

from gapatlas.domain.models.classification import (
    NewsRelevance,
    PainCategory,
    SolutionCategory,
)
from gapatlas.domain.models.common import CountryStatus, SourceName, SourceStatus
from gapatlas.domain.models.errors import InvalidTemporalValueError
from gapatlas.domain.scoring.constants import (
    CAP_MISSING_ONE_CORE_SOURCE,
    CAP_MULTIPLE_MISSING_CORE_SOURCES,
    CAP_TRENDS_MISSING,
    CAP_TRENDS_ZERO_RATIO,
    MISSING_ONE_CORE_SOURCE_CAP,
    TRENDS_ZERO_RATIO_CAP,
)
from gapatlas.domain.scoring.engine import CountryEvaluation, evaluate_country

RISING_SERIES = [10.0] * 8 + [12.0] * 4


def _classified(rising=None, search=None, news=None):
    return make_classified(
        rising_queries=rising
        if rising is not None
        else [make_rising(100.0, PainCategory.SHORTAGE, query=f"q{i}") for i in range(10)],
        search_results=search
        if search is not None
        else [make_search(position, SolutionCategory.INFORMATION) for position in range(1, 11)],
        news_articles=news
        if news is not None
        else [
            make_news(SCAN_TIME, NewsRelevance.DIRECTLY_RELEVANT, position=index)
            for index in range(1, 6)
        ],
    )


def _evaluate(trends=None, classified=None, statuses=None, profile=None):
    classified = classified if classified is not None else _classified()
    evidence = make_evidence(
        trends=trends if trends is not None else make_trends(RISING_SERIES, RISING_SERIES),
        rising_queries=[entry.item for entry in classified.rising_queries],
        search_results=[entry.item for entry in classified.search_results],
        news_articles=[entry.item for entry in classified.news_articles],
        statuses=statuses,
    )
    return evaluate_country(evidence, classified, profile or make_profile(), SCAN_TIME)


def test_completed_when_all_sources_are_ok():
    result = _evaluate()
    assert isinstance(result, CountryEvaluation)
    assert result.status is CountryStatus.COMPLETED
    assert result.public_need_gap_score is not None
    assert result.need_gap.score is not None


def test_public_representation_is_rounded_half_up():
    """公開表現は内部 float を四捨五入(round half up)した整数。"""
    result = _evaluate()
    assert result.need_gap.score is not None
    assert result.public_need_gap_score == pytest.approx(round(result.need_gap.score), abs=1)
    assert isinstance(result.public_need_gap_score, int)
    assert isinstance(result.public_confidence, int)
    assert 0 <= result.public_confidence <= 100


def test_public_components_mirror_internal_components():
    result = _evaluate()
    components = result.need_gap.components
    assert components.demand is not None
    assert result.public_components.demand is not None
    assert abs(result.public_components.demand - components.demand) <= 0.5


def test_hard_rule_1_missing_trends():
    """`trends` 欠損 → `need_gap_score = None`, `status = INSUFFICIENT_EVIDENCE`。"""
    result = _evaluate(statuses={SourceName.TRENDS: SourceStatus.MISSING})
    assert result.status is CountryStatus.INSUFFICIENT_EVIDENCE
    assert result.public_need_gap_score is None
    assert result.need_gap.score is None
    assert CAP_TRENDS_MISSING in result.confidence.applied_caps


def test_hard_rule_1_with_empty_trends_payload():
    """Trends の中身が空でも(ソースが MISSING なら)同じ扱いになる。"""
    result = _evaluate(
        trends=None,
        statuses={SourceName.TRENDS: SourceStatus.MISSING},
    )
    assert result.status is CountryStatus.INSUFFICIENT_EVIDENCE
    assert result.public_need_gap_score is None


def test_hard_rule_2_two_missing_core_sources():
    """Core Source 2つ欠損 → `status = INSUFFICIENT_EVIDENCE`。"""
    statuses = {
        SourceName.SEARCH: SourceStatus.MISSING,
        SourceName.NEWS: SourceStatus.MISSING,
    }
    result = _evaluate(statuses=statuses)
    assert result.status is CountryStatus.INSUFFICIENT_EVIDENCE
    assert result.public_need_gap_score is None
    assert CAP_MULTIPLE_MISSING_CORE_SOURCES in result.confidence.applied_caps


def test_hard_rule_3_one_missing_core_source_still_completes():
    """Core Source 1つ欠損 → スコアは出るが `confidence <= 69`。"""
    result = _evaluate(statuses={SourceName.NEWS: SourceStatus.MISSING})
    assert result.status is CountryStatus.COMPLETED
    assert result.public_need_gap_score is not None
    assert result.confidence.score <= MISSING_ONE_CORE_SOURCE_CAP
    assert result.public_confidence <= 69
    assert CAP_MISSING_ONE_CORE_SOURCE in result.confidence.applied_caps


def test_eleven_points_yields_insufficient_evidence():
    """Trends は OK でも 12 点未満 → `demand = None` → INSUFFICIENT_EVIDENCE。"""
    result = _evaluate(trends=make_trends([50.0] * 11))
    assert result.need_gap.components.demand is None
    assert result.status is CountryStatus.INSUFFICIENT_EVIDENCE
    assert result.public_need_gap_score is None


def test_all_zero_series_completes_with_capped_confidence():
    """全て 0 → `demand = 50` で COMPLETED、かつ Hard Rule 4 で `confidence <= 59`。"""
    result = _evaluate(trends=make_trends([0.0] * 52, [0.0] * 52))
    assert result.status is CountryStatus.COMPLETED
    assert result.need_gap.components.demand == pytest.approx(50.0)
    assert result.public_components.demand == 50
    assert result.confidence.score <= TRENDS_ZERO_RATIO_CAP
    assert result.public_confidence <= 59
    assert CAP_TRENDS_ZERO_RATIO in result.confidence.applied_caps


def test_confidence_is_returned_for_insufficient_evidence():
    """`INSUFFICIENT_EVIDENCE` でも Confidence は必ず算出して返す。"""
    statuses = {
        SourceName.TRENDS: SourceStatus.MISSING,
        SourceName.SEARCH: SourceStatus.MISSING,
    }
    result = _evaluate(statuses=statuses)
    assert result.status is CountryStatus.INSUFFICIENT_EVIDENCE
    assert result.public_need_gap_score is None
    assert result.public_confidence > 0


def test_components_are_kept_when_score_is_withdrawn():
    """Hard Rules でスコアを取り消しても、算出できた成分は残す。"""
    result = _evaluate(statuses={SourceName.TRENDS: SourceStatus.MISSING})
    assert result.need_gap.score is None
    assert result.need_gap.components.pain is not None
    assert result.public_components.pain is not None


def test_renormalization_is_visible_in_components_used():
    """`pain` が計算不能なら `components_used` から除かれる。"""
    result = _evaluate(classified=_classified(rising=[]))
    assert result.status is CountryStatus.COMPLETED
    assert result.need_gap.components.pain is None
    assert "pain" not in result.need_gap.components_used
    assert result.need_gap.components_used == ["demand", "solution_gap", "news_urgency"]


def test_status_is_never_failed():
    """`FAILED` はこの関数では返さない(想定外の例外は呼び出し側の責務)。"""
    for statuses in (
        None,
        {SourceName.NEWS: SourceStatus.MISSING},
        {SourceName.TRENDS: SourceStatus.MISSING},
    ):
        result = _evaluate(statuses=statuses)
        assert result.status in (
            CountryStatus.COMPLETED,
            CountryStatus.INSUFFICIENT_EVIDENCE,
        )


def test_hand_calculated_end_to_end():
    """手計算: 4成分をそれぞれ既知の値にして Need Gap Score を確かめる。

    demand      = 64.0469176213857  ([10]*8 + [12]*4 の系列2本の中央値)
    pain        = 100.0             (全て SHORTAGE、confidence 1.0)
    solution_gap= 100.0             (全て INFORMATION)
    news_urgency= 63.212055882855765(当日の DIRECTLY_RELEVANT 5本)
    NeedGap = 0.40*64.0469176213857 + 0.25*100 + 0.25*100 + 0.10*63.212055882855765
    """
    result = _evaluate()
    expected = 0.40 * 64.0469176213857 + 0.25 * 100.0 + 0.25 * 100.0 + 0.10 * 63.212055882855765
    assert expected == pytest.approx(81.93997263683985)
    assert result.need_gap.score == pytest.approx(expected)
    assert result.public_need_gap_score == 82


def test_evaluate_country_rejects_naive_scan_time():
    naive = datetime(2026, 8, 28)
    classified = _classified()
    evidence = make_evidence(trends=make_trends(RISING_SERIES))
    with pytest.raises(InvalidTemporalValueError):
        evaluate_country(evidence, classified, make_profile(), naive)


def test_scan_time_is_used_for_news_age():
    """`scan_time` を変えると News Urgency が変わる(現在時刻を取得していない)。"""
    classified = _classified()
    evidence = make_evidence(
        trends=make_trends(RISING_SERIES),
        news_articles=[entry.item for entry in classified.news_articles],
    )
    now = evaluate_country(evidence, classified, make_profile(), SCAN_TIME)
    later = evaluate_country(evidence, classified, make_profile(), SCAN_TIME + timedelta(days=60))
    assert now.need_gap.components.news_urgency is not None
    assert later.need_gap.components.news_urgency is not None
    assert later.need_gap.components.news_urgency < now.need_gap.components.news_urgency


def test_evaluation_is_deterministic():
    first = _evaluate()
    second = _evaluate()
    assert first.model_dump() == second.model_dump()
