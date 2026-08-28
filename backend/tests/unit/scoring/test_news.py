"""News Urgency のテスト。docs/scoring.md 5章。"""

from __future__ import annotations

import math
from datetime import datetime, timedelta

import pytest
from conftest import SCAN_TIME, make_news

from gapatlas.domain.models.classification import NewsRelevance
from gapatlas.domain.models.errors import InvalidTemporalValueError
from gapatlas.domain.scoring.constants import NEWS_RELEVANCE_WEIGHTS
from gapatlas.domain.scoring.news import compute_news_urgency


def test_relevance_weight_table_covers_all_members():
    assert set(NEWS_RELEVANCE_WEIGHTS) == set(NewsRelevance)


def test_empty_results_is_none():
    """`news_results` が空 → `news_urgency = None`(docs/scoring.md 9章)。"""
    assert compute_news_urgency([], SCAN_TIME) is None


def test_articles_without_published_at_only_is_none():
    """`iso_date` が無い記事のみ → `news_urgency = None`。"""
    articles = [make_news(None, position=index) for index in range(1, 5)]
    assert compute_news_urgency(articles, SCAN_TIME) is None


def test_articles_without_published_at_are_excluded():
    """日付の無い記事は除外され、日付のある記事だけで計算される。"""
    dated = [make_news(SCAN_TIME, position=1)]
    mixed = [*dated, make_news(None, position=2), make_news(None, position=3)]
    assert compute_news_urgency(mixed, SCAN_TIME) == pytest.approx(
        compute_news_urgency(dated, SCAN_TIME)
    )


def test_hand_calculated_single_same_day_article():
    """手計算: 完全に関連する当日の記事1本。

    recency = exp(0) = 1、news_mass = 1.0 * 1.0 * 1.0 = 1.0
    news_urgency = 100 * (1 - exp(-1/5)) = 18.12692469220182
    """
    articles = [make_news(SCAN_TIME)]
    assert compute_news_urgency(articles, SCAN_TIME) == pytest.approx(18.12692469220182)


def test_hand_calculated_five_same_day_articles():
    """docs/scoring.md の目安「当日の記事5本で約 63」。

    news_mass = 5 → 100 * (1 - exp(-1)) = 63.212055882855765
    """
    articles = [make_news(SCAN_TIME, position=index) for index in range(1, 6)]
    assert compute_news_urgency(articles, SCAN_TIME) == pytest.approx(63.212055882855765)


def test_hand_calculated_fifteen_same_day_articles():
    """docs/scoring.md の目安「15本で約 95」。100 * (1 - exp(-3))。"""
    articles = [make_news(SCAN_TIME, position=index) for index in range(1, 16)]
    assert compute_news_urgency(articles, SCAN_TIME) == pytest.approx(95.0212931632136)


def test_hand_calculated_thirty_day_old_article():
    """手計算: 30 日前の記事1本。

    recency = exp(-30/30) = exp(-1)、news_mass = exp(-1)
    news_urgency = 100 * (1 - exp(-exp(-1)/5)) = 7.093436203460735
    """
    articles = [make_news(SCAN_TIME - timedelta(days=30))]
    assert compute_news_urgency(articles, SCAN_TIME) == pytest.approx(7.093436203460735)


def test_relevance_weights_are_applied():
    """RELATED は DIRECTLY_RELEVANT の半分の質量になる。"""
    related = [make_news(SCAN_TIME, NewsRelevance.RELATED)]
    expected = 100.0 * (1.0 - math.exp(-0.5 / 5.0))
    assert compute_news_urgency(related, SCAN_TIME) == pytest.approx(expected)


def test_unrelated_articles_contribute_nothing_but_are_counted():
    """UNRELATED は重み 0 だが日付があるので `None` にはならない。"""
    articles = [make_news(SCAN_TIME, NewsRelevance.UNRELATED)]
    assert compute_news_urgency(articles, SCAN_TIME) == pytest.approx(0.0)


def test_future_article_is_clamped_to_zero_age():
    """未来日付の記事 → `age_days = 0` に丸められる → `recency_weight = 1.0`。"""
    future = [make_news(SCAN_TIME + timedelta(days=1.5))]
    same_day = [make_news(SCAN_TIME)]
    assert compute_news_urgency(future, SCAN_TIME) == pytest.approx(
        compute_news_urgency(same_day, SCAN_TIME)
    )


def test_confidence_scales_mass():
    articles = [make_news(SCAN_TIME, NewsRelevance.DIRECTLY_RELEVANT, confidence=0.5)]
    expected = 100.0 * (1.0 - math.exp(-0.5 / 5.0))
    assert compute_news_urgency(articles, SCAN_TIME) == pytest.approx(expected)


def test_naive_scan_time_raises():
    """naive な `scan_time` は `InvalidTemporalValueError` にする。"""
    naive = datetime(2026, 8, 28)
    with pytest.raises(InvalidTemporalValueError):
        compute_news_urgency([make_news(SCAN_TIME)], naive)


def test_naive_scan_time_raises_even_with_empty_articles():
    naive = datetime(2026, 8, 28)
    with pytest.raises(InvalidTemporalValueError):
        compute_news_urgency([], naive)


def test_saturation_never_exceeds_one_hundred():
    articles = [make_news(SCAN_TIME, position=index) for index in range(1, 200)]
    urgency = compute_news_urgency(articles, SCAN_TIME)
    assert urgency is not None
    assert 0.0 <= urgency <= 100.0
