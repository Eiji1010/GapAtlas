"""インメモリ `ScanRepository` のテスト。

**この振る舞いが `ScanRepository` の契約**であり、DynamoDB 実装は同じ
テストを満たすこと。
"""

from __future__ import annotations

from datetime import UTC, datetime

from gapatlas.adapters.dynamodb.memory import InMemoryScanRepository
from gapatlas.domain.models.common import Country, CountryStatus, ScanStatus, TopicId
from gapatlas.domain.models.result import (
    CountryResult,
    RankingEntry,
    ScanProgress,
    ScanSummary,
    Versions,
)
from gapatlas.domain.models.scores import ConfidenceBreakdown, ScoreComponents

SCAN_TIME = datetime(2026, 8, 28, tzinfo=UTC)
VERSIONS = Versions(
    query_profile_version="elder-care-jp-v2",
    score_version="gapatlas-score-v1",
    classifier_version="gapatlas-classifier-v1-stub",
    prompt_version="gapatlas-prompt-v1-stub",
)


def _country_result(country: Country, scan_id: str = "s1", score: int | None = 75) -> CountryResult:
    return CountryResult(
        scan_id=scan_id,
        topic_id=TopicId.ELDER_CARE,
        country=country,
        status=CountryStatus.COMPLETED if score is not None else CountryStatus.FAILED,
        need_gap_score=score,
        confidence=91,
        components=ScoreComponents(demand=84.6),
        confidence_breakdown=ConfidenceBreakdown(
            data_completeness=100.0,
            sample_sufficiency=97.0,
            localization_quality=70.0,
            source_agreement=88.0,
            freshness=92.0,
        ),
        versions=VERSIONS,
        computed_at=SCAN_TIME,
    )


def _summary(scan_id: str = "s1") -> ScanSummary:
    return ScanSummary(
        scan_id=scan_id,
        topic_id=TopicId.ELDER_CARE,
        status=ScanStatus.COMPLETED,
        progress=ScanProgress(total=1, completed=1),
        completed_countries=[Country.JP],
        ranking=[
            RankingEntry(
                country=Country.JP,
                status=CountryStatus.COMPLETED,
                need_gap_score=75,
                confidence=91,
            )
        ],
        versions=VERSIONS,
    )


def test_missing_scan_returns_none():
    """「存在しない」は例外ではなく None(404 は API 層が組み立てる)。"""
    assert InMemoryScanRepository().get_scan("nope") is None


def test_missing_country_returns_none():
    assert InMemoryScanRepository().get_country("nope", Country.JP) is None


def test_save_and_get_scan_round_trips():
    repository = InMemoryScanRepository()
    summary = _summary()
    repository.save_scan(summary)
    loaded = repository.get_scan("s1")
    assert loaded is not None
    assert loaded.model_dump() == summary.model_dump()


def test_save_and_get_country_round_trips():
    repository = InMemoryScanRepository()
    result = _country_result(Country.JP)
    repository.save_country(result)
    loaded = repository.get_country("s1", Country.JP)
    assert loaded is not None
    assert loaded.model_dump() == result.model_dump()


def test_saving_the_same_key_overwrites():
    repository = InMemoryScanRepository()
    repository.save_country(_country_result(Country.JP, score=75))
    repository.save_country(_country_result(Country.JP, score=60))
    loaded = repository.get_country("s1", Country.JP)
    assert loaded is not None
    assert loaded.need_gap_score == 60


def test_list_countries_is_sorted_by_country_code():
    repository = InMemoryScanRepository()
    for country in (Country.US, Country.JP, Country.DE):
        repository.save_country(_country_result(country))
    assert [result.country for result in repository.list_countries("s1")] == [
        Country.DE,
        Country.JP,
        Country.US,
    ]


def test_list_countries_isolates_scans():
    repository = InMemoryScanRepository()
    repository.save_country(_country_result(Country.JP, scan_id="s1"))
    repository.save_country(_country_result(Country.US, scan_id="s2"))
    assert [result.country for result in repository.list_countries("s1")] == [Country.JP]
    assert [result.country for result in repository.list_countries("s2")] == [Country.US]


def test_list_countries_for_an_unknown_scan_is_empty():
    assert InMemoryScanRepository().list_countries("nope") == []
