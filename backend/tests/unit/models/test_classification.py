"""分類モデルのテスト。confidence の clip が中心。"""

from __future__ import annotations

import pytest

from gapatlas.domain.models.classification import (
    ClassifiedEvidence,
    ClassifiedNewsArticle,
    ClassifiedRisingQuery,
    ClassifiedSearchResult,
    NewsClassification,
    NewsRelevance,
    PainCategory,
    PainClassification,
    SolutionCategory,
    SolutionClassification,
)
from gapatlas.domain.models.normalized import NewsArticle, RisingQuery, SearchResultItem


@pytest.mark.parametrize(
    ("given", "expected"),
    [(1.5, 1.0), (-0.3, 0.0), (0.0, 0.0), (1.0, 1.0), (0.42, 0.42), (1e9, 1.0)],
)
def test_pain_confidence_is_clipped(given, expected):
    result = PainClassification(classification=PainCategory.SHORTAGE, confidence=given)
    assert result.confidence == expected


@pytest.mark.parametrize(("given", "expected"), [(1.5, 1.0), (-0.3, 0.0)])
def test_solution_confidence_is_clipped(given, expected):
    result = SolutionClassification(
        classification=SolutionCategory.DIRECT_PROVIDER, confidence=given
    )
    assert result.confidence == expected


@pytest.mark.parametrize(("given", "expected"), [(1.5, 1.0), (-0.3, 0.0)])
def test_news_confidence_is_clipped(given, expected):
    result = NewsClassification(classification=NewsRelevance.RELATED, confidence=given)
    assert result.confidence == expected


def test_out_of_range_confidence_does_not_raise():
    """LLM が範囲外を返しても処理を止めない。"""
    PainClassification(classification=PainCategory.NEUTRAL, confidence=99.0)
    PainClassification(classification=PainCategory.NEUTRAL, confidence=-99.0)


def test_classified_evidence_composition():
    evidence = ClassifiedEvidence(
        rising_queries=[
            ClassifiedRisingQuery(
                item=RisingQuery(query="q", growth_percent=120.0),
                classification=PainClassification(
                    classification=PainCategory.WAIT_TIME, confidence=0.8
                ),
            )
        ],
        search_results=[
            ClassifiedSearchResult(
                item=SearchResultItem(position=1, title="t", link="https://example.com"),
                classification=SolutionClassification(
                    classification=SolutionCategory.MARKETPLACE, confidence=0.9
                ),
            )
        ],
        news_articles=[
            ClassifiedNewsArticle(
                item=NewsArticle(position=1, title="t", link="https://example.com"),
                classification=NewsClassification(
                    classification=NewsRelevance.UNRELATED, confidence=0.5
                ),
            )
        ],
    )
    assert evidence.rising_queries[0].item.query == "q"
    assert evidence.search_results[0].classification.classification is SolutionCategory.MARKETPLACE
    assert evidence.news_articles[0].classification.confidence == 0.5


def test_classified_evidence_defaults_to_empty_lists():
    evidence = ClassifiedEvidence()
    assert evidence.rising_queries == []
    assert evidence.search_results == []
    assert evidence.news_articles == []


def test_pain_categories_match_scoring_spec():
    assert {member.value for member in PainCategory} == {
        "ACCESS",
        "SHORTAGE",
        "WAIT_TIME",
        "COST",
        "QUALITY",
        "WORKFORCE",
        "NEUTRAL",
    }


def test_solution_categories_match_scoring_spec():
    assert {member.value for member in SolutionCategory} == {
        "DIRECT_PROVIDER",
        "MARKETPLACE",
        "GOVERNMENT",
        "INFORMATION",
        "NEWS",
        "OTHER",
    }


def test_news_relevance_matches_scoring_spec():
    assert {member.value for member in NewsRelevance} == {
        "DIRECTLY_RELEVANT",
        "RELATED",
        "UNRELATED",
    }
