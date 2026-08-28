"""`ScanWorker` のテスト。

**非同期版(1メッセージ1国)が同期版(`ScanService`)と同じ成果物を作ること**
が最重要の性質である。`test_the_worker_matches_the_scan_service` がそれを見る。

`scan_time` は必ず明示的に渡す(fixture の基準日は `2026-08-28T00:00:00Z`)。
実 AWS へは接続せず、インメモリのアダプタと fixture / stub だけを使う。
"""

from __future__ import annotations

import shutil
from collections.abc import Sequence

import pytest
from conftest import SCAN_ID, SCAN_TIME, TOPIC, RecordingBriefWriter, RecordingSerpApiClient

from gapatlas.adapters.dynamodb.memory import InMemoryScanRepository
from gapatlas.adapters.llm.stub_client import StubLlmClient
from gapatlas.adapters.s3.memory import InMemoryScanArchive
from gapatlas.adapters.serpapi.fixture_client import FixtureSerpApiClient
from gapatlas.application.country_scan import CountryScanner
from gapatlas.application.jobs import ScanJob
from gapatlas.application.scan_service import MAPS_COUNTRY_LIMIT, ScanService
from gapatlas.application.worker import ScanWorker, public_evaluation_from_result
from gapatlas.config.query_profile_loader import DEFAULT_QUERY_PROFILES_DIR
from gapatlas.domain.models.common import (
    Country,
    CountryStatus,
    ScanStatus,
    SourceName,
    SourceStatus,
)
from gapatlas.domain.models.result import CountryResult, ScanSummary

REPO_PROFILES_DIR = DEFAULT_QUERY_PROFILES_DIR

SHUFFLED_ORDER = [Country.DE, Country.IN, Country.JP, Country.GB, Country.US]
"""`list(Country)` とは違う処理順。順序に依存しないことを確認するために使う。"""


def _jobs(countries: Sequence[Country] | None = None, *, scan_id: str = SCAN_ID) -> list[ScanJob]:
    """`countries` の並び順どおりに処理するジョブ列。`countries` は全国分を渡す。"""
    ordered = list(countries) if countries is not None else list(Country)
    return [
        ScanJob(
            scan_id=scan_id,
            topic_id=TOPIC,
            country=country,
            scan_time=SCAN_TIME,
            countries=ordered,
        )
        for country in ordered
    ]


def _worker(
    repository,
    *,
    archive=None,
    brief_writer=None,
    serpapi=None,
    classifier=None,
    profiles_dir=None,
) -> ScanWorker:
    scanner = CountryScanner(serpapi or FixtureSerpApiClient(), classifier or StubLlmClient())
    return ScanWorker(
        scanner,
        repository,
        archive,
        brief_writer if brief_writer is not None else StubLlmClient(),
        profiles_dir=profiles_dir,
    )


def _run_all(worker: ScanWorker, jobs: Sequence[ScanJob]) -> None:
    for job in jobs:
        worker.handle(job)


def _scores(summary: ScanSummary) -> list[tuple[str, int | None, int]]:
    return [
        (entry.country.value, entry.need_gap_score, entry.confidence) for entry in summary.ranking
    ]


# --- 完了判定 -----------------------------------------------------------------------------


def test_the_summary_is_written_only_after_the_last_country():
    """4件目までは概要を書かない。5件目で書く。"""
    repository = InMemoryScanRepository()
    worker = _worker(repository)
    jobs = _jobs()

    for job in jobs[:-1]:
        worker.handle(job)
        assert repository.get_scan(SCAN_ID) is None

    worker.handle(jobs[-1])
    assert repository.get_scan(SCAN_ID) is not None


def test_every_country_is_saved():
    repository = InMemoryScanRepository()
    _run_all(_worker(repository), _jobs())

    saved = repository.list_countries(SCAN_ID)
    assert {result.country for result in saved} == set(Country)


def test_the_last_country_writes_the_ranking():
    repository = InMemoryScanRepository()
    _run_all(_worker(repository), _jobs())

    summary = repository.get_scan(SCAN_ID)
    assert summary is not None
    assert len(summary.ranking) == len(list(Country))
    assert summary.status is ScanStatus.COMPLETED
    assert summary.progress.total == len(list(Country))
    assert summary.progress.completed == len(list(Country))


def test_a_scan_with_a_single_country_completes_immediately():
    """`countries` が1件なら最初のジョブが最後のジョブでもある。"""
    repository = InMemoryScanRepository()
    _run_all(_worker(repository), _jobs([Country.JP]))

    summary = repository.get_scan(SCAN_ID)
    assert summary is not None
    assert [entry.country for entry in summary.ranking] == [Country.JP]


def test_another_scan_id_does_not_complete_this_one():
    """完了判定は `scan_id` 単位。他のスキャンの国を数えない。"""
    repository = InMemoryScanRepository()
    worker = _worker(repository)

    for job in _jobs(scan_id="other")[:4]:
        worker.handle(job)
    worker.handle(_jobs()[0])

    assert repository.get_scan(SCAN_ID) is None


# --- Top2 Maps / Top1 Brief ---------------------------------------------------------------


def test_maps_are_fetched_for_the_top_two_countries_only():
    """Maps はランキング確定後に Top2 だけ取得する(docs/architecture.md)。"""
    client = RecordingSerpApiClient()
    repository = InMemoryScanRepository()
    _run_all(_worker(repository, serpapi=client), _jobs())

    maps_calls = [country for country, source in client.calls if source == SourceName.MAPS.value]
    assert len(maps_calls) == MAPS_COUNTRY_LIMIT

    summary = repository.get_scan(SCAN_ID)
    assert summary is not None
    assert set(maps_calls) == {entry.country.value for entry in summary.ranking[:2]}


def test_maps_are_fetched_after_every_country_has_been_scanned():
    """順序の保証。ランキングが決まる前に Maps を取らない。"""
    client = RecordingSerpApiClient()
    _run_all(_worker(InMemoryScanRepository(), serpapi=client), _jobs())

    first_maps = next(
        index for index, (_, source) in enumerate(client.calls) if source == SourceName.MAPS.value
    )
    trends_after_maps = [
        source for _, source in client.calls[first_maps:] if source == SourceName.TRENDS.value
    ]
    assert trends_after_maps == []


def test_the_top_two_countries_are_saved_again_with_maps():
    repository = InMemoryScanRepository()
    _run_all(_worker(repository), _jobs())

    summary = repository.get_scan(SCAN_ID)
    assert summary is not None
    for entry in summary.ranking[:MAPS_COUNTRY_LIMIT]:
        stored = repository.get_country(SCAN_ID, entry.country)
        assert stored is not None
        assert stored.source_status[SourceName.MAPS] is SourceStatus.OK
        assert [item.source for item in stored.evidence].count(SourceName.MAPS) == 1


def test_the_other_countries_keep_maps_as_not_requested():
    repository = InMemoryScanRepository()
    _run_all(_worker(repository), _jobs())

    summary = repository.get_scan(SCAN_ID)
    assert summary is not None
    for entry in summary.ranking[MAPS_COUNTRY_LIMIT:]:
        stored = repository.get_country(SCAN_ID, entry.country)
        assert stored is not None
        assert stored.source_status[SourceName.MAPS] is SourceStatus.NOT_REQUESTED


def test_evidence_ids_stay_sequential_after_maps_is_attached():
    repository = InMemoryScanRepository()
    _run_all(_worker(repository), _jobs())

    summary = repository.get_scan(SCAN_ID)
    assert summary is not None
    stored = repository.get_country(SCAN_ID, summary.ranking[0].country)
    assert stored is not None
    assert [item.id for item in stored.evidence] == [
        f"E{index + 1}" for index in range(len(stored.evidence))
    ]


def test_the_brief_is_written_for_the_top_country():
    repository = InMemoryScanRepository()
    writer = RecordingBriefWriter()
    _run_all(_worker(repository, brief_writer=writer), _jobs())

    summary = repository.get_scan(SCAN_ID)
    assert summary is not None
    assert summary.opportunity_brief is not None
    assert len(writer.packs) == 1
    assert writer.packs[0].country is summary.ranking[0].country


def test_the_brief_cites_the_maps_evidence_of_the_top_country():
    """Brief には Maps を足した後の Evidence を渡す(同期版と同じ)。"""
    writer = RecordingBriefWriter()
    _run_all(_worker(InMemoryScanRepository(), brief_writer=writer), _jobs())

    sources = [item.source for item in writer.packs[0].evidence]
    assert SourceName.MAPS in sources


def test_no_brief_writer_means_no_brief():
    repository = InMemoryScanRepository()
    scanner = CountryScanner(FixtureSerpApiClient(), StubLlmClient())
    worker = ScanWorker(scanner, repository)
    _run_all(worker, _jobs())

    summary = repository.get_scan(SCAN_ID)
    assert summary is not None
    assert summary.opportunity_brief is None
    assert len(summary.ranking) == len(list(Country))


# --- 処理順への非依存 ---------------------------------------------------------------------


def test_the_result_does_not_depend_on_the_processing_order():
    """どの国が最後になっても最終結果は同じであること。"""
    in_order = InMemoryScanRepository()
    _run_all(_worker(in_order), _jobs())

    shuffled = InMemoryScanRepository()
    _run_all(_worker(shuffled), _jobs(SHUFFLED_ORDER))

    assert in_order.get_scan(SCAN_ID) == shuffled.get_scan(SCAN_ID)


def test_every_country_result_is_identical_across_orders():
    in_order = InMemoryScanRepository()
    _run_all(_worker(in_order), _jobs())

    shuffled = InMemoryScanRepository()
    _run_all(_worker(shuffled), _jobs(SHUFFLED_ORDER))

    assert in_order.list_countries(SCAN_ID) == shuffled.list_countries(SCAN_ID)


# --- 同期版との一致(最重要) --------------------------------------------------------------


def test_the_worker_matches_the_scan_service():
    """`ScanService` を通した5か国スキャンと、Worker で5国を処理した結果が一致する。

    ランキング(順序・スコア・Confidence)と各国のスコアを突き合わせる。
    非同期化で結果が変わらないことが、このトラックの目的そのものである。
    """
    service_repository = InMemoryScanRepository()
    ScanService(
        FixtureSerpApiClient(),
        StubLlmClient(),
        StubLlmClient(),
        repository=service_repository,
    ).scan(TOPIC, list(Country), scan_id=SCAN_ID, scan_time=SCAN_TIME)

    worker_repository = InMemoryScanRepository()
    _run_all(_worker(worker_repository), _jobs())

    expected = service_repository.get_scan(SCAN_ID)
    actual = worker_repository.get_scan(SCAN_ID)
    assert expected is not None
    assert actual is not None
    assert _scores(actual) == _scores(expected)
    assert actual.ranking == expected.ranking
    assert actual.status is expected.status
    assert actual.completed_countries == expected.completed_countries
    assert actual.versions == expected.versions


def test_the_worker_produces_the_same_country_results_as_the_scan_service():
    service_repository = InMemoryScanRepository()
    ScanService(
        FixtureSerpApiClient(),
        StubLlmClient(),
        StubLlmClient(),
        repository=service_repository,
    ).scan(TOPIC, list(Country), scan_id=SCAN_ID, scan_time=SCAN_TIME)

    worker_repository = InMemoryScanRepository()
    _run_all(_worker(worker_repository), _jobs())

    assert worker_repository.list_countries(SCAN_ID) == service_repository.list_countries(SCAN_ID)


def test_the_worker_produces_the_same_brief_as_the_scan_service():
    service_repository = InMemoryScanRepository()
    ScanService(
        FixtureSerpApiClient(),
        StubLlmClient(),
        StubLlmClient(),
        repository=service_repository,
    ).scan(TOPIC, list(Country), scan_id=SCAN_ID, scan_time=SCAN_TIME)

    worker_repository = InMemoryScanRepository()
    _run_all(_worker(worker_repository), _jobs())

    expected = service_repository.get_scan(SCAN_ID)
    actual = worker_repository.get_scan(SCAN_ID)
    assert expected is not None
    assert actual is not None
    assert actual.opportunity_brief == expected.opportunity_brief


# --- 部分的な失敗 -------------------------------------------------------------------------


def test_one_unreadable_profile_fails_only_that_country(tmp_path):
    """1か国の YAML が欠けても、残りの国は完走する。"""
    profiles_dir = tmp_path / "query_profiles"
    shutil.copytree(REPO_PROFILES_DIR, profiles_dir)
    (profiles_dir / "elder_care" / "GB.yaml").unlink()

    repository = InMemoryScanRepository()
    _run_all(_worker(repository, profiles_dir=profiles_dir), _jobs())

    failed = repository.get_country(SCAN_ID, Country.GB)
    assert failed is not None
    assert failed.status is CountryStatus.FAILED
    assert failed.versions.query_profile_version == "unknown"
    for country in (Country.JP, Country.US, Country.DE, Country.IN):
        result = repository.get_country(SCAN_ID, country)
        assert result is not None
        assert result.status is CountryStatus.COMPLETED

    summary = repository.get_scan(SCAN_ID)
    assert summary is not None
    assert summary.status is ScanStatus.PARTIALLY_FAILED
    assert Country.GB not in summary.completed_countries
    assert summary.ranking[-1].country is Country.GB
    assert summary.opportunity_brief is not None


def test_a_failed_country_still_completes_the_scan(tmp_path):
    """`FAILED` の国も「処理済み」として数える。でないと概要が永久に書かれない。"""
    profiles_dir = tmp_path / "query_profiles"
    shutil.copytree(REPO_PROFILES_DIR, profiles_dir)
    (profiles_dir / "elder_care" / "IN.yaml").unlink()

    repository = InMemoryScanRepository()
    # `IN` を最後に処理する。失敗した国が完了判定を止めないことを見る。
    order = [Country.JP, Country.US, Country.GB, Country.DE, Country.IN]
    _run_all(_worker(repository, profiles_dir=profiles_dir), _jobs(order))

    assert repository.get_scan(SCAN_ID) is not None


# --- 永続化の失敗 -------------------------------------------------------------------------


class BrokenRepository(InMemoryScanRepository):
    """保存だけが失敗するリポジトリ。読み取りは通常どおり動く。"""

    def __init__(self, *, fail_country: bool = False, fail_scan: bool = False) -> None:
        super().__init__()
        self._fail_country = fail_country
        self._fail_scan = fail_scan

    def save_country(self, result: CountryResult) -> None:
        if self._fail_country:
            message = "simulated country write failure"
            raise RuntimeError(message)
        super().save_country(result)

    def save_scan(self, summary: ScanSummary) -> None:
        if self._fail_scan:
            message = "simulated scan write failure"
            raise RuntimeError(message)
        super().save_scan(summary)


class UnreadableRepository(InMemoryScanRepository):
    """`list_countries` が失敗するリポジトリ。完了判定ができない状況を作る。"""

    def list_countries(self, scan_id: str) -> list[CountryResult]:
        message = "simulated read failure"
        raise RuntimeError(message)


class BrokenArchive(InMemoryScanArchive):
    """すべての書き出しが失敗するアーカイブ。"""

    def put_raw(self, **kwargs):
        message = "simulated raw failure"
        raise RuntimeError(message)

    def put_normalized(self, **kwargs):
        message = "simulated normalized failure"
        raise RuntimeError(message)

    def put_curated(self, **kwargs):
        message = "simulated curated failure"
        raise RuntimeError(message)


def test_a_failing_country_write_does_not_fail_the_job():
    """算出済みの結果を捨てない(docs/requirements.md「Reliability」)。"""
    worker = _worker(BrokenRepository(fail_country=True))
    outcome = worker.handle(_jobs()[0])
    assert outcome.result.status is CountryStatus.COMPLETED


def test_a_failing_summary_write_does_not_fail_the_job():
    repository = BrokenRepository(fail_scan=True)
    _run_all(_worker(repository), _jobs())
    assert repository.get_scan(SCAN_ID) is None


def test_a_failing_archive_does_not_fail_the_job():
    repository = InMemoryScanRepository()
    _run_all(_worker(repository, archive=BrokenArchive()), _jobs())

    summary = repository.get_scan(SCAN_ID)
    assert summary is not None
    assert len(summary.ranking) == len(list(Country))


def test_an_unreadable_repository_does_not_fail_the_job():
    """完了判定ができないだけで、その国の結果は保存済みのまま返す。"""
    worker = _worker(UnreadableRepository())
    outcome = worker.handle(_jobs()[0])
    assert outcome.result.status is CountryStatus.COMPLETED


def test_the_archive_receives_every_layer():
    archive = InMemoryScanArchive()
    _run_all(_worker(InMemoryScanRepository(), archive=archive), _jobs())

    assert any(key.startswith("raw/") for key in archive.objects)
    assert any(key.startswith("normalized/") for key in archive.objects)
    assert any(key.startswith("curated/") for key in archive.objects)
    assert any("source=maps" in key for key in archive.objects)


# --- 冪等性 -------------------------------------------------------------------------------


def test_reprocessing_the_same_job_keeps_the_result_intact():
    """SQS の再配信で同じジョブが2回届いても壊れない。"""
    repository = InMemoryScanRepository()
    worker = _worker(repository)
    jobs = _jobs()
    _run_all(worker, jobs)

    before_summary = repository.get_scan(SCAN_ID)
    before_countries = repository.list_countries(SCAN_ID)

    worker.handle(jobs[-1])

    assert repository.get_scan(SCAN_ID) == before_summary
    assert repository.list_countries(SCAN_ID) == before_countries


def test_reprocessing_does_not_duplicate_the_maps_evidence():
    repository = InMemoryScanRepository()
    worker = _worker(repository)
    jobs = _jobs()
    _run_all(worker, jobs)

    summary = repository.get_scan(SCAN_ID)
    assert summary is not None
    top = summary.ranking[0].country
    worker.handle(next(job for job in jobs if job.country is top))

    stored = repository.get_country(SCAN_ID, top)
    assert stored is not None
    assert [item.source for item in stored.evidence].count(SourceName.MAPS) == 1


def test_reprocessing_does_not_fetch_maps_again_for_untouched_countries():
    repository = InMemoryScanRepository()
    client = RecordingSerpApiClient()
    worker = _worker(repository, serpapi=client)
    jobs = _jobs()
    _run_all(worker, jobs)

    summary = repository.get_scan(SCAN_ID)
    assert summary is not None
    # ランキング2位の国を再処理する。1位は再スキャンされないので Maps も取り直さない。
    second = summary.ranking[1].country
    before = [call for call in client.calls if call[1] == SourceName.MAPS.value]
    worker.handle(next(job for job in jobs if job.country is second))
    after = [call for call in client.calls if call[1] == SourceName.MAPS.value]

    assert [country for country, _ in after[len(before) :]] == [second.value]


# --- public_evaluation_from_result ---------------------------------------------------------


def test_the_rehydrated_evaluation_keeps_the_public_values():
    repository = InMemoryScanRepository()
    _run_all(_worker(repository), _jobs())
    stored = repository.get_country(SCAN_ID, Country.JP)
    assert stored is not None

    evaluation = public_evaluation_from_result(stored)
    assert evaluation.public_need_gap_score == stored.need_gap_score
    assert evaluation.public_confidence == stored.confidence
    assert evaluation.status is stored.status
    assert evaluation.confidence.breakdown == stored.confidence_breakdown


def test_the_rehydrated_evaluation_matches_the_scanner_evaluation():
    """公開表現は元の `CountryEvaluation` と一致する。"""
    worker = _worker(InMemoryScanRepository())
    outcome = worker.handle(_jobs()[0])
    assert outcome.evaluation is not None

    rehydrated = public_evaluation_from_result(outcome.result)
    assert rehydrated.public_need_gap_score == outcome.evaluation.public_need_gap_score
    assert rehydrated.public_confidence == outcome.evaluation.public_confidence
    assert rehydrated.public_components == outcome.evaluation.public_components


@pytest.mark.parametrize("country", list(Country))
def test_every_country_can_be_the_last_one(country):
    """どの国が最後になっても概要が書かれること。"""
    order = [other for other in Country if other is not country] + [country]
    repository = InMemoryScanRepository()
    _run_all(_worker(repository), _jobs(order))
    assert repository.get_scan(SCAN_ID) is not None
