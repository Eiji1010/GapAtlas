"""stub の分類品質を 5 か国の実 fixture で検証する。

期待値の正本は `backend/tests/fixtures/README.md` の「意図した分類分布」表である。
**fixture と README は変更せず、stub の規則を README に合わせる。**

README は件数の内訳しか与えていないため、一致率は**カテゴリ分布の重なり**
(多重集合の共通部分)で測る。

    match_rate = Σ_c min(predicted[c], intended[c]) / 件数

これは項目単位の正解率の上界であり、README だけから決定的に計算できる。

達成基準(依頼):

- rising queries: `NEUTRAL` の件数が一致し、一致率 75% 以上
- organic results: 一致率 70% 以上
- news: `UNRELATED` の件数が一致し、一致率 70% 以上
"""

from __future__ import annotations

import json
from collections import Counter
from enum import StrEnum
from pathlib import Path

import pytest

from gapatlas.adapters.llm.stub_client import StubLlmClient
from gapatlas.domain.models.classification import (
    NewsRelevance,
    PainCategory,
    SolutionCategory,
)
from gapatlas.domain.models.common import Country
from gapatlas.domain.models.normalized import NewsArticle, RisingQuery, SearchResultItem

FIXTURES = Path(__file__).resolve().parents[3] / "fixtures" / "serpapi" / "elder_care"

COUNTRIES = [Country.JP, Country.US, Country.GB, Country.DE, Country.IN]

LANGUAGES = {
    Country.JP: "ja",
    Country.US: "en",
    Country.GB: "en",
    Country.DE: "de",
    Country.IN: "en",
}

PAIN_MIN_MATCH_RATE = 0.75
SOLUTION_MIN_MATCH_RATE = 0.70
NEWS_MIN_MATCH_RATE = 0.70

# backend/tests/fixtures/README.md「各国 `rising` の Pain カテゴリ分布(意図)」
INTENDED_PAIN: dict[Country, dict[PainCategory, int]] = {
    Country.JP: {
        PainCategory.ACCESS: 2,
        PainCategory.SHORTAGE: 2,
        PainCategory.WAIT_TIME: 2,
        PainCategory.COST: 2,
        PainCategory.QUALITY: 1,
        PainCategory.WORKFORCE: 2,
        PainCategory.NEUTRAL: 1,
    },
    Country.US: {
        PainCategory.ACCESS: 2,
        PainCategory.SHORTAGE: 2,
        PainCategory.WAIT_TIME: 2,
        PainCategory.COST: 2,
        PainCategory.QUALITY: 1,
        PainCategory.WORKFORCE: 2,
        PainCategory.NEUTRAL: 1,
    },
    Country.GB: {
        PainCategory.ACCESS: 1,
        PainCategory.SHORTAGE: 3,
        PainCategory.WAIT_TIME: 3,
        PainCategory.COST: 2,
        PainCategory.QUALITY: 1,
        PainCategory.WORKFORCE: 1,
        PainCategory.NEUTRAL: 1,
    },
    Country.DE: {
        PainCategory.ACCESS: 2,
        PainCategory.SHORTAGE: 3,
        PainCategory.WAIT_TIME: 1,
        PainCategory.COST: 2,
        PainCategory.QUALITY: 1,
        PainCategory.WORKFORCE: 2,
        PainCategory.NEUTRAL: 1,
    },
    Country.IN: {
        PainCategory.ACCESS: 4,
        PainCategory.SHORTAGE: 1,
        PainCategory.WAIT_TIME: 1,
        PainCategory.COST: 2,
        PainCategory.QUALITY: 1,
        PainCategory.WORKFORCE: 1,
        PainCategory.NEUTRAL: 2,
    },
}

# backend/tests/fixtures/README.md「各国 `organic_results` の Solution カテゴリ分布(意図)」
INTENDED_SOLUTION: dict[Country, dict[SolutionCategory, int]] = {
    Country.JP: {
        SolutionCategory.DIRECT_PROVIDER: 2,
        SolutionCategory.MARKETPLACE: 1,
        SolutionCategory.GOVERNMENT: 3,
        SolutionCategory.INFORMATION: 3,
        SolutionCategory.NEWS: 1,
        SolutionCategory.OTHER: 0,
    },
    Country.US: {
        SolutionCategory.DIRECT_PROVIDER: 4,
        SolutionCategory.MARKETPLACE: 3,
        SolutionCategory.GOVERNMENT: 1,
        SolutionCategory.INFORMATION: 2,
        SolutionCategory.NEWS: 0,
        SolutionCategory.OTHER: 0,
    },
    Country.GB: {
        SolutionCategory.DIRECT_PROVIDER: 2,
        SolutionCategory.MARKETPLACE: 1,
        SolutionCategory.GOVERNMENT: 4,
        SolutionCategory.INFORMATION: 2,
        SolutionCategory.NEWS: 1,
        SolutionCategory.OTHER: 0,
    },
    Country.DE: {
        SolutionCategory.DIRECT_PROVIDER: 3,
        SolutionCategory.MARKETPLACE: 2,
        SolutionCategory.GOVERNMENT: 2,
        SolutionCategory.INFORMATION: 3,
        SolutionCategory.NEWS: 0,
        SolutionCategory.OTHER: 0,
    },
    Country.IN: {
        SolutionCategory.DIRECT_PROVIDER: 2,
        SolutionCategory.MARKETPLACE: 2,
        SolutionCategory.GOVERNMENT: 0,
        SolutionCategory.INFORMATION: 4,
        SolutionCategory.NEWS: 1,
        SolutionCategory.OTHER: 1,
    },
}

# backend/tests/fixtures/README.md「`news_results` の関連性分類(意図)」
INTENDED_NEWS: dict[Country, dict[NewsRelevance, int]] = {
    Country.JP: {
        NewsRelevance.DIRECTLY_RELEVANT: 7,
        NewsRelevance.RELATED: 2,
        NewsRelevance.UNRELATED: 0,
    },
    Country.US: {
        NewsRelevance.DIRECTLY_RELEVANT: 6,
        NewsRelevance.RELATED: 2,
        NewsRelevance.UNRELATED: 0,
    },
    Country.GB: {
        NewsRelevance.DIRECTLY_RELEVANT: 7,
        NewsRelevance.RELATED: 1,
        NewsRelevance.UNRELATED: 0,
    },
    Country.DE: {
        NewsRelevance.DIRECTLY_RELEVANT: 7,
        NewsRelevance.RELATED: 1,
        NewsRelevance.UNRELATED: 0,
    },
    Country.IN: {
        NewsRelevance.DIRECTLY_RELEVANT: 5,
        NewsRelevance.RELATED: 3,
        NewsRelevance.UNRELATED: 0,
    },
}


def _load(country: Country, name: str) -> dict:
    return json.loads((FIXTURES / country.value / name).read_text(encoding="utf-8"))


def load_rising_queries(country: Country) -> list[RisingQuery]:
    """fixture の `rising` を正規化モデルへ変換する(成長率は分類に使われない)。"""
    raw = _load(country, "trends_related_queries.json")["related_queries"]["rising"]
    return [RisingQuery(query=item["query"], growth_percent=0.0) for item in raw]


def load_search_results(country: Country) -> list[SearchResultItem]:
    raw = _load(country, "search.json")["organic_results"]
    return [
        SearchResultItem(
            position=item["position"],
            title=item["title"],
            link=item["link"],
            snippet=item.get("snippet"),
            displayed_link=item.get("displayed_link"),
            source=item.get("source"),
        )
        for item in raw
    ]


def load_news_articles(country: Country) -> list[NewsArticle]:
    raw = _load(country, "news.json")["news_results"]
    return [
        NewsArticle(
            position=item["position"],
            title=item["title"],
            link=item["link"],
            source_name=(item.get("source") or {}).get("name"),
        )
        for item in raw
    ]


def match_rate[CategoryT: StrEnum](
    predicted: list[CategoryT], intended: dict[CategoryT, int]
) -> float:
    """カテゴリ分布の重なり率。"""
    counts = Counter(predicted)
    overlap = sum(min(counts[category], expected) for category, expected in intended.items())
    return overlap / len(predicted)


@pytest.fixture(scope="module")
def client() -> StubLlmClient:
    return StubLlmClient()


@pytest.mark.parametrize("country", COUNTRIES)
def test_fixture_counts_match_the_readme(country):
    """前提の確認。README の件数と fixture の実件数が一致していること。"""
    assert len(load_rising_queries(country)) == sum(INTENDED_PAIN[country].values())
    assert len(load_search_results(country)) == sum(INTENDED_SOLUTION[country].values())
    assert len(load_news_articles(country)) == sum(INTENDED_NEWS[country].values())


@pytest.mark.parametrize("country", COUNTRIES)
def test_rising_query_distribution(client, make_query_profile, country):
    items = load_rising_queries(country)
    profile = make_query_profile(country=country, language=LANGUAGES[country])
    predicted = [result.classification for result in client.classify_rising_queries(items, profile)]

    neutral_count = predicted.count(PainCategory.NEUTRAL)
    assert neutral_count == INTENDED_PAIN[country][PainCategory.NEUTRAL], (
        f"{country.value}: NEUTRAL count differs"
    )

    rate = match_rate(predicted, INTENDED_PAIN[country])
    assert rate >= PAIN_MIN_MATCH_RATE, f"{country.value}: pain match rate {rate:.3f}"


@pytest.mark.parametrize(
    ("country", "expected_rate"),
    [
        (Country.JP, 1.0),
        (Country.US, 11 / 12),
        (Country.GB, 1.0),
        (Country.DE, 1.0),
        (Country.IN, 1.0),
    ],
)
def test_rising_query_match_rate_is_stable(client, make_query_profile, country, expected_rate):
    """実測値。規則を変えて悪化したら気づけるよう、実測値そのものを固定する。"""
    items = load_rising_queries(country)
    profile = make_query_profile(country=country, language=LANGUAGES[country])
    predicted = [result.classification for result in client.classify_rising_queries(items, profile)]
    assert match_rate(predicted, INTENDED_PAIN[country]) == pytest.approx(expected_rate)


@pytest.mark.parametrize("country", COUNTRIES)
def test_search_result_distribution(client, make_query_profile, country):
    items = load_search_results(country)
    profile = make_query_profile(country=country, language=LANGUAGES[country])
    predicted = [result.classification for result in client.classify_search_results(items, profile)]
    rate = match_rate(predicted, INTENDED_SOLUTION[country])
    assert rate >= SOLUTION_MIN_MATCH_RATE, f"{country.value}: solution match rate {rate:.3f}"


@pytest.mark.parametrize("country", COUNTRIES)
def test_search_result_match_rate_is_stable(client, make_query_profile, country):
    """5か国とも実測 100%。"""
    items = load_search_results(country)
    profile = make_query_profile(country=country, language=LANGUAGES[country])
    predicted = [result.classification for result in client.classify_search_results(items, profile)]
    assert match_rate(predicted, INTENDED_SOLUTION[country]) == pytest.approx(1.0)


@pytest.mark.parametrize("country", COUNTRIES)
def test_news_distribution(client, make_query_profile, country):
    items = load_news_articles(country)
    profile = make_query_profile(country=country, language=LANGUAGES[country])
    predicted = [result.classification for result in client.classify_news_articles(items, profile)]

    unrelated_count = predicted.count(NewsRelevance.UNRELATED)
    assert unrelated_count == INTENDED_NEWS[country][NewsRelevance.UNRELATED], (
        f"{country.value}: UNRELATED count differs"
    )

    rate = match_rate(predicted, INTENDED_NEWS[country])
    assert rate >= NEWS_MIN_MATCH_RATE, f"{country.value}: news match rate {rate:.3f}"


@pytest.mark.parametrize(
    ("country", "expected_rate"),
    [
        (Country.JP, 1.0),
        (Country.US, 1.0),
        (Country.GB, 1.0),
        (Country.DE, 1.0),
        (Country.IN, 7 / 8),
    ],
)
def test_news_match_rate_is_stable(client, make_query_profile, country, expected_rate):
    items = load_news_articles(country)
    profile = make_query_profile(country=country, language=LANGUAGES[country])
    predicted = [result.classification for result in client.classify_news_articles(items, profile)]
    assert match_rate(predicted, INTENDED_NEWS[country]) == pytest.approx(expected_rate)


@pytest.mark.parametrize("country", COUNTRIES)
def test_confidence_varies_within_a_country(client, make_query_profile, country):
    """1.0 固定でも単一値でもないこと(Confidence 計算を意味あるものにするため)。"""
    profile = make_query_profile(country=country, language=LANGUAGES[country])
    confidences = {
        result.confidence
        for result in client.classify_rising_queries(load_rising_queries(country), profile)
    }
    confidences |= {
        result.confidence
        for result in client.classify_search_results(load_search_results(country), profile)
    }
    assert len(confidences) >= 2
    assert 1.0 not in confidences
