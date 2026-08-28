"""Evidence Confidence のテスト。docs/scoring.md 6章。"""

from __future__ import annotations

import math
from datetime import datetime, timedelta

import pytest
from conftest import (
    SCAN_TIME,
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
from gapatlas.domain.models.common import Country, SourceName, SourceStatus
from gapatlas.domain.models.errors import InvalidTemporalValueError
from gapatlas.domain.models.normalized import TrendsTimeseries
from gapatlas.domain.models.query_profile import ReviewStatus
from gapatlas.domain.models.scores import ScoreComponents
from gapatlas.domain.scoring.confidence import (
    compute_confidence,
    compute_data_completeness,
    compute_freshness,
    compute_localization_quality,
    compute_sample_sufficiency,
    compute_source_agreement,
    compute_trends_zero_ratio,
)
from gapatlas.domain.scoring.constants import (
    CAP_MISSING_ONE_CORE_SOURCE,
    CAP_MULTIPLE_MISSING_CORE_SOURCES,
    CAP_TRENDS_MISSING,
    CAP_TRENDS_ZERO_RATIO,
    LOCALIZATION_QUALITY_BY_REVIEW_STATUS,
    MISSING_ONE_CORE_SOURCE_CAP,
    SAMPLE_TARGETS,
    TRENDS_ZERO_RATIO_CAP,
    ZERO_RATIO_THRESHOLD,
)

RISING_SERIES = [10.0] * 8 + [12.0] * 4


DEMAND_QUERIES = ["q0", "q1", "q2"]
"""`make_trends` が付ける系列名と一致させる。

Sample sufficiency の trends は「各 demand query の系列長のうち最小値」なので、
QueryProfile が要求するクエリ名と系列名が一致していないと 0 件になる。
"""


def _profile(**kwargs):
    """`_full_evidence` の trends と整合する QueryProfile。"""
    kwargs.setdefault("demand_queries", DEMAND_QUERIES)
    return make_profile(**kwargs)


def _full_evidence(**kwargs):
    """4ソースすべてが目標件数を満たす証拠データ。"""
    defaults = {
        "trends": make_trends(RISING_SERIES, RISING_SERIES, RISING_SERIES),
        "rising_queries": [
            make_rising(100.0, PainCategory.SHORTAGE, query=f"q{index}").item for index in range(10)
        ],
        "search_results": [
            make_search(position, SolutionCategory.INFORMATION).item for position in range(1, 11)
        ],
        "news_articles": [
            make_news(SCAN_TIME, NewsRelevance.DIRECTLY_RELEVANT, position=index).item
            for index in range(1, 6)
        ],
    }
    defaults.update(kwargs)
    return make_evidence(**defaults)


# --------------------------------------------------------------------------
# Data completeness
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("missing", "expected"),
    [
        ((), 100.0),
        ((SourceName.NEWS,), 75.0),
        ((SourceName.NEWS, SourceName.SEARCH), 50.0),
        ((SourceName.NEWS, SourceName.SEARCH, SourceName.RELATED_QUERIES), 25.0),
        (
            (
                SourceName.NEWS,
                SourceName.SEARCH,
                SourceName.RELATED_QUERIES,
                SourceName.TRENDS,
            ),
            0.0,
        ),
    ],
)
def test_data_completeness(missing, expected):
    """`100 * OK の Core Source 数 / 4`。"""
    statuses = dict.fromkeys(missing, SourceStatus.MISSING)
    assert compute_data_completeness(_full_evidence(statuses=statuses)) == pytest.approx(expected)


def test_maps_is_not_a_core_source():
    """Maps は Core Source に含まれない。"""
    evidence = _full_evidence(statuses={SourceName.MAPS: SourceStatus.MISSING})
    assert compute_data_completeness(evidence) == pytest.approx(100.0)


# --------------------------------------------------------------------------
# Sample sufficiency
# --------------------------------------------------------------------------


def test_sample_targets():
    assert SAMPLE_TARGETS[SourceName.TRENDS] == 12
    assert SAMPLE_TARGETS[SourceName.RELATED_QUERIES] == 10
    assert SAMPLE_TARGETS[SourceName.SEARCH] == 10
    assert SAMPLE_TARGETS[SourceName.NEWS] == 5


def test_sample_sufficiency_full():
    assert compute_sample_sufficiency(_full_evidence(), _profile()) == pytest.approx(100.0)


def test_sample_sufficiency_trends_uses_minimum_series_length():
    """trends の件数は各 demand query の系列長のうち **最小値**。

    3系列のうち1つが 11 点 → 件数 11 → ratio 11/12。
    残り3ソースは満点なので mean([11/12, 1, 1, 1]) * 100。
    """
    trends = make_trends([50.0] * 52, [50.0] * 11, [50.0] * 52)
    evidence = _full_evidence(trends=trends)
    expected = 100.0 * ((11 / 12) + 1 + 1 + 1) / 4
    assert compute_sample_sufficiency(evidence, _profile()) == pytest.approx(expected)


def test_sample_sufficiency_trends_without_series_is_zero():
    """系列が1つも無ければ 0。"""
    evidence = _full_evidence(trends=TrendsTimeseries(series=[]))
    assert compute_sample_sufficiency(evidence, _profile()) == pytest.approx(100.0 * 3 / 4)


def test_sample_sufficiency_missing_source_ratio_is_zero():
    """MISSING のソースは ratio 0。平均は常に4ソース固定で取る。"""
    evidence = _full_evidence(statuses={SourceName.NEWS: SourceStatus.MISSING})
    assert compute_sample_sufficiency(evidence, _profile()) == pytest.approx(75.0)


def test_sample_sufficiency_counts_only_dated_news():
    """news は `published_at` が None でない記事だけを数える。"""
    articles = [
        make_news(SCAN_TIME, position=1).item,
        make_news(SCAN_TIME, position=2).item,
        *[make_news(None, position=index).item for index in range(3, 10)],
    ]
    evidence = _full_evidence(news_articles=articles)
    expected = 100.0 * (1 + 1 + 1 + (2 / 5)) / 4
    assert compute_sample_sufficiency(evidence, _profile()) == pytest.approx(expected)


def test_sample_sufficiency_ratio_is_capped_at_one():
    """目標件数を超えても ratio は 1 を超えない。"""
    articles = [make_news(SCAN_TIME, position=index).item for index in range(1, 30)]
    evidence = _full_evidence(news_articles=articles)
    assert compute_sample_sufficiency(evidence, _profile()) == pytest.approx(100.0)


def test_sample_sufficiency_counts_a_requested_query_without_series_as_zero():
    """Trends が返さなかった demand query は系列長 0 として数える。

    Google Trends は検索ボリュームが閾値未満のキーワードを結果から落とす。
    現れた系列だけで最小値を取ると、そのクエリの Demand を計算できないのに
    Sample sufficiency が満点になり Confidence を過大評価する
    (docs/scoring.md 6章「各 demand query の系列長のうち最小値」)。
    """
    trends = make_trends([50.0] * 52, [50.0] * 52)  # q0 / q1 のみ。q2 は返らなかった
    evidence = _full_evidence(trends=trends)
    assert compute_sample_sufficiency(evidence, _profile()) == pytest.approx(100.0 * 3 / 4)
    # 要求クエリが2件だけなら満点に戻る
    two_queries = _profile(demand_queries=["q0", "q1"])
    assert compute_sample_sufficiency(evidence, two_queries) == pytest.approx(100.0)


# --------------------------------------------------------------------------
# Localization quality
# --------------------------------------------------------------------------


def test_localization_quality_table():
    assert LOCALIZATION_QUALITY_BY_REVIEW_STATUS[ReviewStatus.MANUAL_REVIEWED] == 100.0
    assert LOCALIZATION_QUALITY_BY_REVIEW_STATUS[ReviewStatus.LLM_GENERATED] == 70.0
    assert set(LOCALIZATION_QUALITY_BY_REVIEW_STATUS) == set(ReviewStatus)


@pytest.mark.parametrize(
    ("review_status", "language", "expected"),
    [
        (ReviewStatus.MANUAL_REVIEWED, "ja", 100.0),
        (ReviewStatus.LLM_GENERATED, "ja", 70.0),
        (ReviewStatus.MANUAL_REVIEWED, "en", 80.0),
        (ReviewStatus.LLM_GENERATED, "en", 50.0),
    ],
)
def test_localization_quality(review_status, language, expected):
    """`review_status` で 100 / 70。主要言語でなければさらに 20 減じる。"""
    profile = make_profile(country=Country.JP, language=language, review_status=review_status)
    assert compute_localization_quality(profile) == pytest.approx(expected)


def test_localization_quality_accepts_any_primary_language():
    """IN は `en` / `hi` の両方が主要言語。"""
    for language in ("en", "hi"):
        profile = make_profile(
            country=Country.IN, language=language, review_status=ReviewStatus.LLM_GENERATED
        )
        assert compute_localization_quality(profile) == pytest.approx(70.0)


# --------------------------------------------------------------------------
# Source agreement
# --------------------------------------------------------------------------


def test_source_agreement_requires_two_components():
    """下位スコアが1つしか無い → `source_agreement = 0`(docs/scoring.md 9章)。"""
    components = ScoreComponents(demand=50.0)
    assert compute_source_agreement(components) == pytest.approx(0.0)


def test_source_agreement_with_no_components_is_zero():
    assert compute_source_agreement(ScoreComponents()) == pytest.approx(0.0)


def test_source_agreement_identical_scores_is_one_hundred():
    components = ScoreComponents(demand=50.0, pain=50.0, solution_gap=50.0, news_urgency=50.0)
    assert compute_source_agreement(components) == pytest.approx(100.0)


def test_source_agreement_uses_population_stdev_not_sample_stdev():
    """母標準偏差(N で割る)であること。標本標準偏差なら値が変わる入力で検証。

    s = [0.6, 0.4] → pstdev = 0.1 → 100 * (1 - 2*0.1) = 80.0
    標本標準偏差なら 0.1414213562 → 71.71572875 になり一致しない。
    """
    components = ScoreComponents(demand=60.0, pain=40.0)
    population_expected = 100.0 * (1.0 - 2.0 * 0.1)
    sample_expected = 100.0 * (1.0 - 2.0 * math.sqrt(0.02))
    assert population_expected == pytest.approx(80.0)
    assert sample_expected == pytest.approx(71.71572875253811)
    assert compute_source_agreement(components) == pytest.approx(population_expected)
    assert compute_source_agreement(components) != pytest.approx(sample_expected)


def test_source_agreement_hand_calculated_four_components():
    """手計算: s = [0.8, 0.6, 0.4, 0.2] → pstdev = sqrt(0.05) = 0.2236068。

    source_agreement = 100 * (1 - 2*0.2236068) = 55.2786405
    """
    components = ScoreComponents(demand=80.0, pain=60.0, solution_gap=40.0, news_urgency=20.0)
    assert compute_source_agreement(components) == pytest.approx(55.2786404500042)


def test_source_agreement_is_clipped_at_zero():
    """最大に散らばった場合(pstdev = 0.5)は 0 になる。"""
    components = ScoreComponents(demand=100.0, pain=0.0)
    assert compute_source_agreement(components) == pytest.approx(0.0)


# --------------------------------------------------------------------------
# Freshness
# --------------------------------------------------------------------------


def test_freshness_all_fresh():
    assert compute_freshness(_full_evidence(), SCAN_TIME) == pytest.approx(100.0)


def test_freshness_hand_calculated_old_trends():
    """手計算: trends だけ 30 日前、他は 0 日。

    mean([100*exp(-1), 100, 100, 100]) = (36.7879441 + 300) / 4 = 84.19698603
    """
    trends = make_trends(RISING_SERIES, latest=SCAN_TIME - timedelta(days=30))
    evidence = _full_evidence(trends=trends)
    expected = (100.0 * math.exp(-1.0) + 300.0) / 4.0
    assert expected == pytest.approx(84.19698602928606)
    assert compute_freshness(evidence, SCAN_TIME) == pytest.approx(expected)


def test_freshness_uses_cache_age_for_related_queries_and_search():
    """related_queries / search は `cache_age_seconds` を日数へ換算する。"""
    evidence = _full_evidence(
        cache_age_seconds={
            SourceName.RELATED_QUERIES: 30 * 86400.0,
            SourceName.SEARCH: 30 * 86400.0,
        }
    )
    expected = (100.0 + 100.0 * math.exp(-1.0) + 100.0 * math.exp(-1.0) + 100.0) / 4.0
    assert compute_freshness(evidence, SCAN_TIME) == pytest.approx(expected)


def test_freshness_uses_newest_news_article():
    """news は最も新しい記事の `published_at` を使う。"""
    articles = [
        make_news(SCAN_TIME - timedelta(days=30), position=1).item,
        make_news(SCAN_TIME - timedelta(days=200), position=2).item,
    ]
    evidence = _full_evidence(news_articles=articles)
    expected = (300.0 + 100.0 * math.exp(-1.0)) / 4.0
    assert compute_freshness(evidence, SCAN_TIME) == pytest.approx(expected)


def test_freshness_only_averages_ok_sources():
    """`OK` の Core Source だけで平均を取る。"""
    trends = make_trends(RISING_SERIES, latest=SCAN_TIME - timedelta(days=30))
    evidence = _full_evidence(trends=trends, statuses={SourceName.NEWS: SourceStatus.MISSING})
    expected = (100.0 * math.exp(-1.0) + 200.0) / 3.0
    assert compute_freshness(evidence, SCAN_TIME) == pytest.approx(expected)


def test_freshness_is_zero_when_no_core_source_is_ok():
    statuses = dict.fromkeys(
        (
            SourceName.TRENDS,
            SourceName.RELATED_QUERIES,
            SourceName.SEARCH,
            SourceName.NEWS,
        ),
        SourceStatus.MISSING,
    )
    assert compute_freshness(_full_evidence(statuses=statuses), SCAN_TIME) == pytest.approx(0.0)


def test_freshness_does_not_crash_when_ok_trends_has_no_series():
    """trends が OK なのに系列が空でも落ちない(age を 0 として扱う)。"""
    evidence = _full_evidence(trends=TrendsTimeseries(series=[]))
    assert compute_freshness(evidence, SCAN_TIME) == pytest.approx(100.0)


def test_freshness_does_not_crash_when_ok_trends_is_none():
    evidence = _full_evidence(trends=None)
    assert compute_freshness(evidence, SCAN_TIME) == pytest.approx(100.0)


def test_freshness_does_not_crash_when_ok_news_has_no_dated_article():
    """news が OK なのに日付付き記事が0件でも落ちない(age を 0 として扱う)。"""
    articles = [make_news(None, position=index).item for index in range(1, 4)]
    evidence = _full_evidence(news_articles=articles)
    assert compute_freshness(evidence, SCAN_TIME) == pytest.approx(100.0)


def test_freshness_clamps_future_timestamps():
    """未来の timestamp は `max(0, age)` により 0 日として扱う。"""
    trends = make_trends(RISING_SERIES, latest=SCAN_TIME + timedelta(days=10))
    evidence = _full_evidence(trends=trends)
    assert compute_freshness(evidence, SCAN_TIME) == pytest.approx(100.0)


# --------------------------------------------------------------------------
# ゼロ率(Hard Rule 4)
# --------------------------------------------------------------------------


def test_zero_ratio_is_none_without_trends():
    assert compute_trends_zero_ratio(make_evidence(trends=None)) is None


def test_zero_ratio_is_none_without_points():
    assert compute_trends_zero_ratio(make_evidence(trends=TrendsTimeseries(series=[]))) is None


def test_zero_ratio_counts_all_series_and_points():
    """クエリごとではなく `(系列, データ点)` の全組で1つの比率を出す。

    52 点 * 3 系列のうち、1系列だけ全て 0 → 52/156 = 0.3333...
    """
    trends = make_trends([0.0] * 52, [50.0] * 52, [50.0] * 52)
    assert compute_trends_zero_ratio(make_evidence(trends=trends)) == pytest.approx(1 / 3)

    # クエリ単位で判定する実装だと、全ゼロの1系列が Hard Rule 4 を誤発動させる。
    # Hard Rule のレベルまで確認しないとその改変を検出できない。
    result = compute_confidence(
        _full_evidence(trends=trends), _profile(), ScoreComponents(), SCAN_TIME
    )
    assert CAP_TRENDS_ZERO_RATIO not in result.applied_caps


def test_zero_ratio_just_below_fifty_percent_does_not_trigger_hard_rule_4():
    """しきい値の**下側**を固定する。49% では発動しない。

    40% までしか試さないと、しきい値を 0.45 や 0.42 へ緩める改変を検出できない
    (docs/scoring.md 6章「ゼロ率が 50% 以上」)。
    """
    trends = make_trends([0.0] * 49 + [50.0] * 51)
    evidence = _full_evidence(trends=trends)
    assert compute_trends_zero_ratio(evidence) == pytest.approx(0.49)
    result = compute_confidence(
        evidence, _profile(demand_queries=["q0"]), ScoreComponents(), SCAN_TIME
    )
    assert CAP_TRENDS_ZERO_RATIO not in result.applied_caps


def test_zero_ratio_threshold_constant_matches_the_spec():
    """docs/scoring.md 6章 Hard Rule 4: ゼロ率 50% 以上。"""
    assert ZERO_RATIO_THRESHOLD == 0.5


def test_zero_ratio_forty_percent_does_not_trigger_hard_rule_4():
    """3系列 * 52 点のうち 0 が 40% → Hard Rule 4 は発動しない。"""
    zeros = [0.0] * 21 + [50.0] * 31  # 21/52 ≈ 40.4%
    trends = make_trends(zeros, zeros, zeros)
    evidence = _full_evidence(trends=trends)
    ratio = compute_trends_zero_ratio(evidence)
    assert ratio is not None
    assert 0.4 <= ratio < 0.5
    result = compute_confidence(evidence, _profile(), ScoreComponents(), SCAN_TIME)
    assert CAP_TRENDS_ZERO_RATIO not in result.applied_caps


def test_zero_ratio_exactly_fifty_percent_triggers_hard_rule_4():
    """ちょうど 50% でも発動する(`>=` 判定)。"""
    trends = make_trends([0.0] * 26 + [50.0] * 26)
    evidence = _full_evidence(trends=trends)
    assert compute_trends_zero_ratio(evidence) == pytest.approx(0.5)
    result = compute_confidence(evidence, _profile(), ScoreComponents(), SCAN_TIME)
    assert CAP_TRENDS_ZERO_RATIO in result.applied_caps
    assert result.score <= TRENDS_ZERO_RATIO_CAP


# --------------------------------------------------------------------------
# 合成と Hard Rules
# --------------------------------------------------------------------------


def test_confidence_hand_calculated_no_caps():
    """手計算: 全ソース OK、目標件数を満たし、手動レビュー済み・主要言語。

    data_completeness = 100、sample_sufficiency = 100、
    localization_quality = 100、freshness = 100、
    source_agreement = 55.2786405(s = [0.8, 0.6, 0.4, 0.2])
    confidence_raw = 30 + 25 + 20 + 0.15*55.2786405 + 10 = 93.2917961
    """
    components = ScoreComponents(demand=80.0, pain=60.0, solution_gap=40.0, news_urgency=20.0)
    result = compute_confidence(_full_evidence(), _profile(), components, SCAN_TIME)

    assert result.breakdown.data_completeness == pytest.approx(100.0)
    assert result.breakdown.sample_sufficiency == pytest.approx(100.0)
    assert result.breakdown.localization_quality == pytest.approx(100.0)
    assert result.breakdown.source_agreement == pytest.approx(55.2786404500042)
    assert result.breakdown.freshness == pytest.approx(100.0)
    assert result.score == pytest.approx(93.29179606750063)
    assert result.applied_caps == []


def test_confidence_is_capped_when_one_core_source_is_missing():
    """Core Source 1つ欠損 → `confidence <= 69`(docs/scoring.md 9章)。"""
    components = ScoreComponents(demand=80.0, pain=60.0, solution_gap=40.0)
    evidence = _full_evidence(statuses={SourceName.NEWS: SourceStatus.MISSING})
    result = compute_confidence(evidence, _profile(), components, SCAN_TIME)
    assert result.score <= MISSING_ONE_CORE_SOURCE_CAP
    assert result.score == pytest.approx(MISSING_ONE_CORE_SOURCE_CAP)
    assert result.applied_caps == [CAP_MISSING_ONE_CORE_SOURCE]


def test_confidence_records_multiple_missing_core_sources():
    """Hard Rule 2 は Confidence の上限を課さないが `applied_caps` に記録する。"""
    statuses = {
        SourceName.NEWS: SourceStatus.MISSING,
        SourceName.SEARCH: SourceStatus.MISSING,
    }
    evidence = _full_evidence(statuses=statuses)
    result = compute_confidence(evidence, _profile(), ScoreComponents(), SCAN_TIME)
    assert CAP_MULTIPLE_MISSING_CORE_SOURCES in result.applied_caps
    assert CAP_MISSING_ONE_CORE_SOURCE not in result.applied_caps


def test_confidence_records_missing_trends():
    """Hard Rule 1 も `applied_caps` に記録する。"""
    evidence = _full_evidence(statuses={SourceName.TRENDS: SourceStatus.MISSING})
    result = compute_confidence(evidence, _profile(), ScoreComponents(), SCAN_TIME)
    assert CAP_TRENDS_MISSING in result.applied_caps
    assert CAP_MISSING_ONE_CORE_SOURCE in result.applied_caps


def test_all_zero_series_caps_confidence_at_fifty_nine():
    """週次データ点が全て 0 → Hard Rule 4 により `confidence <= 59`。"""
    evidence = _full_evidence(trends=make_trends([0.0] * 52, [0.0] * 52, [0.0] * 52))
    components = ScoreComponents(demand=50.0, pain=50.0, solution_gap=50.0, news_urgency=50.0)
    result = compute_confidence(evidence, _profile(), components, SCAN_TIME)
    assert result.score <= TRENDS_ZERO_RATIO_CAP
    assert result.applied_caps == [CAP_TRENDS_ZERO_RATIO]


def test_hard_rules_are_applied_in_order():
    """Hard Rule 3 と 4 の両方に該当するときは、より厳しい 59 が残る。"""
    zeros = make_trends([0.0] * 52, [0.0] * 52)
    evidence = _full_evidence(trends=zeros, statuses={SourceName.NEWS: SourceStatus.MISSING})
    components = ScoreComponents(demand=50.0, pain=50.0, solution_gap=50.0)
    result = compute_confidence(evidence, _profile(), components, SCAN_TIME)
    assert result.score == pytest.approx(TRENDS_ZERO_RATIO_CAP)
    assert result.applied_caps == [CAP_MISSING_ONE_CORE_SOURCE, CAP_TRENDS_ZERO_RATIO]


def test_confidence_is_returned_even_when_everything_is_missing():
    """`INSUFFICIENT_EVIDENCE` でも Confidence は算出して返す。"""
    statuses = dict.fromkeys(
        (
            SourceName.TRENDS,
            SourceName.RELATED_QUERIES,
            SourceName.SEARCH,
            SourceName.NEWS,
        ),
        SourceStatus.MISSING,
    )
    evidence = make_evidence(trends=None, statuses=statuses)
    result = compute_confidence(evidence, _profile(), ScoreComponents(), SCAN_TIME)
    # localization だけが残る: 0.20 * 100 = 20
    assert result.score == pytest.approx(20.0)
    assert result.breakdown.data_completeness == pytest.approx(0.0)
    assert result.breakdown.freshness == pytest.approx(0.0)


def test_confidence_rejects_naive_scan_time():
    naive = datetime(2026, 8, 28)
    with pytest.raises(InvalidTemporalValueError):
        compute_confidence(_full_evidence(), _profile(), ScoreComponents(), naive)


def test_confidence_score_is_float_not_rounded():
    """`ConfidenceResult.score` は Hard Rules 適用後の float(丸めは engine の責務)。"""
    components = ScoreComponents(demand=80.0, pain=60.0, solution_gap=40.0, news_urgency=20.0)
    result = compute_confidence(_full_evidence(), _profile(), components, SCAN_TIME)
    assert isinstance(result.score, float)
    assert result.score != pytest.approx(round(result.score))
