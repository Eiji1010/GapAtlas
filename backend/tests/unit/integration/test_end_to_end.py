"""E2E: API -> SQS -> Worker -> DynamoDB / S3 -> API。

`docs/requirements.md`「E2E demo が動く」に対応する。**外部通信ゼロ**で、
実際に使う4つのアダプタのインメモリ版・fixture 版だけを組み合わせて、
`POST /scans` から `GET /scans/{id}/countries/{country}` までを通す。

各層の単体テストが緑でも、**層の接続**は別問題である。ここが壊れたら
デモが動かない。

基準日は `2026-08-28T00:00:00Z`(backend/tests/fixtures/README.md)。
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

import pytest
from pydantic import BaseModel

from gapatlas.adapters.dynamodb.memory import InMemoryScanRepository
from gapatlas.adapters.dynamodb.serialization import from_attributes, to_attributes
from gapatlas.adapters.llm.stub_client import StubLlmClient
from gapatlas.adapters.s3.memory import InMemoryScanArchive
from gapatlas.adapters.serpapi.fixture_client import FixtureSerpApiClient
from gapatlas.adapters.sqs.decode import decode_job
from gapatlas.adapters.sqs.memory import InMemoryJobQueue
from gapatlas.api.errors import ScanNotFoundError
from gapatlas.api.handlers import ApiService
from gapatlas.application.country_scan import CountryScanner
from gapatlas.application.worker import ScanWorker
from gapatlas.config.settings import Settings
from gapatlas.domain.models.common import Country, CountryStatus
from gapatlas.domain.models.result import CountryResult, ScanSummary

SCAN_ID = "scan_e2e"
SCAN_TIME = datetime(2026, 8, 28, tzinfo=UTC)

EXPECTED_SCORES = {
    "JP": (75, 91),
    "DE": (67, 90),
    "IN": (66, 92),
    "GB": (58, 90),
    "US": (55, 90),
}
"""fixture に対する期待値。CLI の出力と一致すること。"""


def _round_trip[ModelT: BaseModel](model_type: type[ModelT], model: ModelT) -> ModelT:
    """DynamoDB の属性表現を実際に往復させる。"""
    return from_attributes(model_type, to_attributes(model))


class SerializingScanRepository:
    """保存のたびに**実際のシリアライズを通す**リポジトリ。

    インメモリ実装はモデルオブジェクトをそのまま返すため、E2E が
    `adapters/dynamodb/serialization.py` を1バイトも通らない。`CountryResult`
    の Screen 2 用フィールド(`trends` / `related_queries` / `search_results` /
    `news_results` / `maps_results`)が保存時に丸ごと落ちても気づけない。
    """

    def __init__(self) -> None:
        self._inner = InMemoryScanRepository()

    def save_scan(self, summary: ScanSummary) -> None:
        self._inner.save_scan(_round_trip(ScanSummary, summary))

    def save_scan_if_unfinished(self, summary: ScanSummary) -> bool:
        return self._inner.save_scan_if_unfinished(_round_trip(ScanSummary, summary))

    def save_country(self, result: CountryResult) -> None:
        self._inner.save_country(_round_trip(CountryResult, result))

    def get_scan(self, scan_id: str) -> ScanSummary | None:
        return self._inner.get_scan(scan_id)

    def get_country(self, scan_id: str, country: Country) -> CountryResult | None:
        return self._inner.get_country(scan_id, country)

    def list_countries(self, scan_id: str) -> list[CountryResult]:
        return self._inner.list_countries(scan_id)

    def list_country_statuses(self, scan_id: str) -> list[tuple[Country, CountryStatus]]:
        return self._inner.list_country_statuses(scan_id)


@pytest.fixture(params=["memory", "serializing"])
def stack(request: pytest.FixtureRequest):
    """デモで使う構成そのもの(fixture / stub)。

    リポジトリは**素のインメモリ**と**シリアライズを通すもの**の両方で回す。
    """
    repository: Any = (
        InMemoryScanRepository() if request.param == "memory" else SerializingScanRepository()
    )
    archive = InMemoryScanArchive()
    queue = InMemoryJobQueue()
    api = ApiService(repository, queue, Settings())
    worker = ScanWorker(
        CountryScanner(FixtureSerpApiClient(), StubLlmClient()),
        repository,
        archive,
        StubLlmClient(),
    )
    return api, worker, queue, repository, archive


def _drain(worker: ScanWorker, queue: InMemoryJobQueue) -> int:
    """キューのジョブを SQS メッセージ経由で処理する。"""
    jobs = queue.drain()
    for job in jobs:
        # SQS を通ったときと同じ経路にする(JSON へ落として復元する)。
        worker.handle(decode_job(job.model_dump_json()))
    return len(jobs)


def test_the_full_flow_produces_the_expected_ranking(stack):
    api, worker, queue, _repository, _archive = stack

    created = api.create_scan({"topic_id": "elder_care"}, scan_id=SCAN_ID, scan_time=SCAN_TIME)
    assert created == {"scan_id": SCAN_ID, "status": "processing"}
    assert len(queue.jobs) == len(Country)

    assert _drain(worker, queue) == len(Country)

    summary = api.get_scan(SCAN_ID)
    assert summary["status"] == "completed"
    assert summary["progress"] == {"total": 5, "completed": 5}
    actual = {
        entry["country"]: (entry["need_gap_score"], entry["confidence"])
        for entry in summary["ranking"]
    }
    assert actual == EXPECTED_SCORES
    assert [entry["country"] for entry in summary["ranking"]] == list(EXPECTED_SCORES)


def test_the_progress_advances_while_processing(stack):
    api, worker, queue, _repository, _archive = stack
    api.create_scan({"topic_id": "elder_care"}, scan_id=SCAN_ID, scan_time=SCAN_TIME)
    jobs = queue.drain()

    seen: list[int] = []
    for job in jobs:
        worker.handle(job)
        seen.append(api.get_scan(SCAN_ID)["progress"]["completed"])

    # 2秒 Polling で進捗が動くこと(docs/api.md)
    assert seen == [1, 2, 3, 4, 5]


def test_the_top_country_gets_a_brief_and_the_top_two_get_maps(stack):
    api, worker, queue, _repository, _archive = stack
    api.create_scan({"topic_id": "elder_care"}, scan_id=SCAN_ID, scan_time=SCAN_TIME)
    _drain(worker, queue)

    summary = api.get_scan(SCAN_ID)
    brief = summary["opportunity_brief"]
    assert brief is not None
    assert brief["cited_evidence_ids"]

    ranked = [entry["country"] for entry in summary["ranking"]]
    with_maps = [
        country
        for country in ranked
        if api.get_country(SCAN_ID, country)["maps_results"] is not None
    ]
    assert with_maps == ranked[:2]


def test_the_country_detail_carries_the_screen_two_data(stack):
    api, worker, queue, _repository, _archive = stack
    api.create_scan({"topic_id": "elder_care"}, scan_id=SCAN_ID, scan_time=SCAN_TIME)
    _drain(worker, queue)

    detail = api.get_country(SCAN_ID, "JP")
    assert detail["need_gap_score"] == 75
    assert detail["status"] == "completed"
    assert len(detail["trends"]["series"]) == 3
    assert len(detail["related_queries"]) == 12
    assert len(detail["search_results"]) == 10
    assert len(detail["news_results"]) == 9
    assert detail["evidence"][0]["id"] == "E1"
    assert detail["source_status"]["maps"] in {"ok", "not_requested"}
    assert detail["versions"]["score_version"] == "gapatlas-score-v1"
    # stub と実 LLM を版で区別できること
    assert detail["versions"]["classifier_version"].endswith("-stub")


def test_every_country_is_archived(stack):
    """Definition of Done「Raw JSON を S3 へ保存」。"""
    api, worker, queue, _repository, archive = stack
    api.create_scan({"topic_id": "elder_care"}, scan_id=SCAN_ID, scan_time=SCAN_TIME)
    _drain(worker, queue)

    raw_keys = [key for key in archive.objects if key.startswith("raw/")]
    assert len(raw_keys) == len(Country) * 4 + 2  # Core 4種 x 5か国 + Top2 の Maps
    for country in Country:
        assert any(f"country={country.value}" in key for key in raw_keys)
    assert all("dt=2026-08-28" in key for key in raw_keys)

    # raw は無加工で保存する
    jp_trends = next(key for key in raw_keys if "source=trends" in key and "country=JP" in key)
    payload = json.loads(archive.objects[jp_trends])
    assert "interest_over_time" in payload


def test_a_missing_scan_is_reported_as_not_found(stack):
    api, _worker, _queue, _repository, _archive = stack
    with pytest.raises(ScanNotFoundError):
        api.get_scan("scan_unknown")


def test_the_flow_is_deterministic(stack):
    api, worker, queue, _repository, _archive = stack
    api.create_scan({"topic_id": "elder_care"}, scan_id=SCAN_ID, scan_time=SCAN_TIME)
    _drain(worker, queue)
    first = api.get_country(SCAN_ID, "JP")

    api.create_scan({"topic_id": "elder_care"}, scan_id="scan_e2e_2", scan_time=SCAN_TIME)
    jobs = queue.drain()
    for job in jobs:
        worker.handle(job)
    second = api.get_country("scan_e2e_2", "JP")

    assert first | {"scan_id": "x"} == second | {"scan_id": "x"}


def test_a_single_country_scan_works(stack):
    api, worker, queue, _repository, _archive = stack
    api.create_scan(
        {"topic_id": "elder_care", "countries": ["DE"]}, scan_id=SCAN_ID, scan_time=SCAN_TIME
    )
    assert _drain(worker, queue) == 1

    summary = api.get_scan(SCAN_ID)
    assert summary["status"] == "completed"
    assert [entry["country"] for entry in summary["ranking"]] == ["DE"]
    # 1か国でも Top2 の枠内なので Maps を取る
    assert api.get_country(SCAN_ID, "DE")["source_status"]["maps"] == "ok"
    assert api.get_country(SCAN_ID, "DE")["maps_results"] is not None


def test_the_worker_is_idempotent(stack):
    """SQS は同じメッセージを再配信しうる。2回処理しても壊れないこと。"""
    api, worker, queue, _repository, _archive = stack
    api.create_scan({"topic_id": "elder_care"}, scan_id=SCAN_ID, scan_time=SCAN_TIME)
    jobs = queue.drain()
    for job in jobs:
        worker.handle(job)
    once = api.get_scan(SCAN_ID)

    worker.handle(jobs[0])
    twice = api.get_scan(SCAN_ID)

    assert once["ranking"] == twice["ranking"]
    assert once["progress"] == twice["progress"]
