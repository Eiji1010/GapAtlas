"""`ApiService` のテスト。HTTP から切り離したユースケースの契約。

docs/api.md のレスポンス例とキーが一致すること、`POST /scans` が重い処理を
しないことを確認する。
"""

from __future__ import annotations

import pytest
from conftest import (
    SCAN_ID,
    SCAN_TIME,
    ExplodingRepository,
    make_country_result,
    make_scan_summary,
    make_settings,
)

from gapatlas.adapters.dynamodb.memory import InMemoryScanRepository
from gapatlas.adapters.llm.stub_client import StubLlmClient
from gapatlas.adapters.serpapi.fixture_client import FixtureSerpApiClient
from gapatlas.adapters.serpapi.live_client import LiveSerpApiClient
from gapatlas.adapters.sqs.memory import InMemoryJobQueue
from gapatlas.api.errors import CountryNotFoundError, InvalidRequestError, ScanNotFoundError
from gapatlas.api.handlers import UNRESOLVED_VERSION, ApiService
from gapatlas.application.country_scan import CountryScanner
from gapatlas.config.query_profile_loader import load_query_profile
from gapatlas.config.settings import Settings
from gapatlas.domain.models.common import Country, CountryStatus, ScanStatus, TopicId
from gapatlas.domain.models.result import CountryResult
from gapatlas.domain.scoring.constants import SCORE_VERSION

# --- GET /api/v1/topics -----------------------------------------------------------------

TOPICS_KEYS = {"topic_id", "label", "countries"}
"""docs/api.md `GET /api/v1/topics` の topic ごとのキー。"""


def test_list_topics_matches_the_documented_shape(service: ApiService):
    payload = service.list_topics()

    assert list(payload) == ["topics"]
    topic = payload["topics"][0]
    assert set(topic) == TOPICS_KEYS
    assert topic["topic_id"] == "elder_care"
    assert topic["label"] == "Elder Care"


def test_list_topics_lists_the_five_mvp_countries(service: ApiService):
    countries = service.list_topics()["topics"][0]["countries"]

    assert countries == [
        {"country": "JP", "label": "Japan"},
        {"country": "US", "label": "United States"},
        {"country": "GB", "label": "United Kingdom"},
        {"country": "DE", "label": "Germany"},
        {"country": "IN", "label": "India"},
    ]


def test_list_topics_covers_every_topic_enum_member(service: ApiService):
    """ラベルをハードコードせず Enum から組み立てること。"""
    topics = service.list_topics()["topics"]

    assert [topic["topic_id"] for topic in topics] == [member.value for member in TopicId]


# --- POST /api/v1/scans -----------------------------------------------------------------


def test_create_scan_returns_scan_id_and_processing(service: ApiService):
    payload = service.create_scan({"topic_id": "elder_care"}, scan_id=SCAN_ID, scan_time=SCAN_TIME)

    assert payload == {"scan_id": SCAN_ID, "status": "processing"}


def test_create_scan_enqueues_one_job_per_country(service: ApiService, queue: InMemoryJobQueue):
    service.create_scan(
        {"topic_id": "elder_care", "countries": ["JP", "US", "GB", "DE", "IN"]},
        scan_id=SCAN_ID,
        scan_time=SCAN_TIME,
    )

    assert len(queue.jobs) == 5
    assert [job.country for job in queue.jobs] == list(Country)


def test_every_job_shares_the_scan_id_and_scan_time(service: ApiService, queue: InMemoryJobQueue):
    """国ごとに時刻が変わると Freshness と News Urgency が再現できない。"""
    service.create_scan({"topic_id": "elder_care"}, scan_id=SCAN_ID, scan_time=SCAN_TIME)

    assert {job.scan_id for job in queue.jobs} == {SCAN_ID}
    assert {job.scan_time for job in queue.jobs} == {SCAN_TIME}


def test_every_job_carries_the_full_country_list(service: ApiService, queue: InMemoryJobQueue):
    """Worker が「自分が最後の1国か」を判定できること。"""
    service.create_scan({"topic_id": "elder_care"}, scan_id=SCAN_ID, scan_time=SCAN_TIME)

    for job in queue.jobs:
        assert job.countries == list(Country)


def test_create_scan_defaults_to_every_country(service: ApiService, queue: InMemoryJobQueue):
    service.create_scan({"topic_id": "elder_care"}, scan_id=SCAN_ID, scan_time=SCAN_TIME)

    assert [job.country for job in queue.jobs] == list(Country)


def test_create_scan_accepts_a_subset_of_countries(service: ApiService, queue: InMemoryJobQueue):
    service.create_scan(
        {"topic_id": "elder_care", "countries": ["JP", "DE"]},
        scan_id=SCAN_ID,
        scan_time=SCAN_TIME,
    )

    assert [job.country for job in queue.jobs] == [Country.JP, Country.DE]


def test_create_scan_drops_duplicate_countries(service: ApiService, queue: InMemoryJobQueue):
    service.create_scan(
        {"topic_id": "elder_care", "countries": ["JP", "JP", "US"]},
        scan_id=SCAN_ID,
        scan_time=SCAN_TIME,
    )

    assert [job.country for job in queue.jobs] == [Country.JP, Country.US]


def test_create_scan_stores_the_scan_meta_as_processing(
    service: ApiService, repository: InMemoryScanRepository
):
    service.create_scan(
        {"topic_id": "elder_care", "countries": ["JP", "US"]},
        scan_id=SCAN_ID,
        scan_time=SCAN_TIME,
    )

    stored = repository.get_scan(SCAN_ID)
    assert stored is not None
    assert stored.status is ScanStatus.PROCESSING
    assert stored.progress.total == 2
    assert stored.progress.completed == 0
    assert stored.ranking == []
    assert stored.opportunity_brief is None


def test_the_initial_meta_records_the_known_score_version(
    service: ApiService, repository: InMemoryScanRepository
):
    """確定しているバージョンだけ実値、未確定は `pending`。推測で埋めない。"""
    service.create_scan({"topic_id": "elder_care"}, scan_id=SCAN_ID, scan_time=SCAN_TIME)

    stored = repository.get_scan(SCAN_ID)
    assert stored is not None
    assert stored.versions.score_version == SCORE_VERSION
    assert stored.versions.query_profile_version == UNRESOLVED_VERSION
    assert stored.versions.classifier_version == UNRESOLVED_VERSION


def test_create_scan_saves_the_meta_before_enqueueing(recording_service):
    """Worker が先に走ってもスキャンを読めるよう、保存が先。"""
    service, order = recording_service
    service.create_scan({"topic_id": "elder_care"}, scan_id=SCAN_ID, scan_time=SCAN_TIME)

    assert order == ["save_scan", "enqueue"]


@pytest.fixture
def recording_service():
    """保存とキュー投入の順序を記録する `ApiService`。"""
    order: list[str] = []

    class RecordingRepository(InMemoryScanRepository):
        def save_scan(self, summary):
            order.append("save_scan")
            super().save_scan(summary)

    class RecordingQueue(InMemoryJobQueue):
        def enqueue(self, jobs):
            order.append("enqueue")
            super().enqueue(jobs)

    return ApiService(RecordingRepository(), RecordingQueue(), make_settings()), order


def test_create_scan_does_not_touch_serpapi(
    service: ApiService, queue: InMemoryJobQueue, monkeypatch
):
    """重い処理をしない証明。SerpApi にも HTTP にも触れないこと。"""

    def explode(*args, **kwargs):
        message = "SerpApi must not be called from POST /scans"
        raise AssertionError(message)

    monkeypatch.setattr(FixtureSerpApiClient, "fetch", explode)
    monkeypatch.setattr(LiveSerpApiClient, "fetch", explode)
    monkeypatch.setattr("httpx.Client.send", explode)

    service.create_scan({"topic_id": "elder_care"}, scan_id=SCAN_ID, scan_time=SCAN_TIME)

    assert len(queue.jobs) == len(list(Country))


@pytest.mark.parametrize(
    "body",
    [
        pytest.param({}, id="missing topic_id"),
        pytest.param({"topic_id": None}, id="null topic_id"),
        pytest.param({"topic_id": "childcare"}, id="unknown topic"),
        pytest.param({"topic_id": 1}, id="non string topic"),
        pytest.param({"topic_id": "elder_care", "countries": ["ZZ"]}, id="unknown country"),
        pytest.param({"topic_id": "elder_care", "countries": []}, id="empty countries"),
        pytest.param({"topic_id": "elder_care", "countries": "JP"}, id="countries not a list"),
        pytest.param({"topic_id": "elder_care", "countries": [1]}, id="country not a string"),
        pytest.param({"topic_id": "elder_care", "country": "JP"}, id="misspelled countries"),
    ],
)
def test_create_scan_rejects_invalid_bodies(service: ApiService, body):
    with pytest.raises(InvalidRequestError):
        service.create_scan(body, scan_id=SCAN_ID, scan_time=SCAN_TIME)


def test_an_invalid_body_enqueues_nothing(service: ApiService, queue: InMemoryJobQueue):
    with pytest.raises(InvalidRequestError):
        service.create_scan({"topic_id": "childcare"}, scan_id=SCAN_ID, scan_time=SCAN_TIME)

    assert queue.jobs == []


# --- GET /api/v1/scans/{scan_id} --------------------------------------------------------

SCAN_KEYS = {
    "scan_id",
    "topic_id",
    "status",
    "progress",
    "completed_countries",
    "ranking",
    "opportunity_brief",
    "versions",
}
"""docs/api.md `GET /api/v1/scans/{scan_id}` のキー。"""


def test_get_scan_matches_the_documented_shape(
    service: ApiService, repository: InMemoryScanRepository
):
    repository.save_scan(make_scan_summary())

    payload = service.get_scan(SCAN_ID)

    assert set(payload) == SCAN_KEYS
    assert payload["scan_id"] == SCAN_ID
    assert payload["topic_id"] == "elder_care"
    assert set(payload["progress"]) == {"total", "completed"}
    assert set(payload["ranking"][0]) == {
        "country",
        "status",
        "need_gap_score",
        "confidence",
        "demand",
        "pain",
        "solution_gap",
        "news_urgency",
    }


def test_get_scan_raises_when_the_scan_is_missing(service: ApiService):
    with pytest.raises(ScanNotFoundError):
        service.get_scan("scan_missing")


def test_progress_is_derived_from_the_stored_countries(
    service: ApiService, repository: InMemoryScanRepository
):
    """概要の `progress` は処理中ずっと 0 のまま。実態を返すこと。"""
    repository.save_scan(make_scan_summary(total=5, completed=0))
    repository.save_country(make_country_result(Country.JP))
    repository.save_country(make_country_result(Country.US))

    payload = service.get_scan(SCAN_ID)

    assert payload["progress"] == {"total": 5, "completed": 2}
    assert payload["completed_countries"] == ["JP", "US"]


def test_progress_counts_insufficient_evidence_as_completed(
    service: ApiService, repository: InMemoryScanRepository
):
    """`INSUFFICIENT_EVIDENCE` はエラーではない(docs/api.md)。"""
    repository.save_scan(make_scan_summary())
    repository.save_country(
        make_country_result(Country.JP, status=CountryStatus.INSUFFICIENT_EVIDENCE, score=None)
    )

    payload = service.get_scan(SCAN_ID)

    assert payload["progress"]["completed"] == 1
    assert payload["completed_countries"] == ["JP"]


def test_a_failed_country_is_not_counted_as_completed(
    service: ApiService, repository: InMemoryScanRepository
):
    """`ScanService` が最終概要で使う定義と同じにする。"""
    repository.save_scan(make_scan_summary())
    repository.save_country(make_country_result(Country.JP))
    repository.save_country(
        make_country_result(Country.US, status=CountryStatus.FAILED, score=None)
    )

    payload = service.get_scan(SCAN_ID)

    assert payload["progress"]["completed"] == 1
    assert payload["completed_countries"] == ["JP"]


def test_progress_ignores_countries_of_another_scan(
    service: ApiService, repository: InMemoryScanRepository
):
    repository.save_scan(make_scan_summary())
    repository.save_country(make_country_result(Country.JP, scan_id="scan_other"))

    payload = service.get_scan(SCAN_ID)

    assert payload["progress"] == {"total": 5, "completed": 0}


def test_progress_never_exceeds_the_total(service: ApiService, repository: InMemoryScanRepository):
    """`total` より多く保存されていても 500 にしない。"""
    repository.save_scan(make_scan_summary(total=1))
    for country in Country:
        repository.save_country(make_country_result(country))

    payload = service.get_scan(SCAN_ID)

    assert payload["progress"] == {"total": 5, "completed": 5}


# --- GET /api/v1/scans/{scan_id}/countries/{country} -------------------------------------

COUNTRY_KEYS = {
    "scan_id",
    "topic_id",
    "country",
    "status",
    "need_gap_score",
    "confidence",
    "components",
    "confidence_breakdown",
    "source_status",
    "evidence",
    "trends",
    "related_queries",
    "search_results",
    "news_results",
    "maps_results",
    "versions",
    "computed_at",
}
"""docs/api.md の国別レスポンスのキー。

Screen 2 が表示する詳細も含む。`computed_at` は docs/api.md の例には
無いが `CountryResult` が持つため返す(docs/api.md に明記済み)。
"""


def test_get_country_matches_the_documented_shape(
    service: ApiService, repository: InMemoryScanRepository
):
    repository.save_country(make_country_result(Country.JP))

    payload = service.get_country(SCAN_ID, "JP")

    assert set(payload) == COUNTRY_KEYS
    assert payload["country"] == "JP"
    assert set(payload["components"]) == {"demand", "pain", "solution_gap", "news_urgency"}
    assert set(payload["confidence_breakdown"]) == {
        "data_completeness",
        "sample_sufficiency",
        "localization_quality",
        "source_agreement",
        "freshness",
    }
    assert set(payload["evidence"][0]) == {"id", "source", "summary", "url"}


def test_get_country_rounds_components_to_public_integers(
    service: ApiService, repository: InMemoryScanRepository
):
    """`ranking` と同じ丸め(round half up)を使うこと。"""
    repository.save_country(make_country_result(Country.JP))

    payload = service.get_country(SCAN_ID, "JP")

    assert payload["components"] == {
        "demand": 91,
        "pain": 84,
        "solution_gap": 78,
        "news_urgency": 83,
    }
    assert payload["confidence_breakdown"]["sample_sufficiency"] == 95


def test_get_country_returns_every_source_status(
    service: ApiService, repository: InMemoryScanRepository
):
    repository.save_country(make_country_result(Country.JP))

    payload = service.get_country(SCAN_ID, "JP")

    assert payload["source_status"] == {
        "trends": "ok",
        "related_queries": "ok",
        "search": "ok",
        "news": "ok",
        "maps": "not_requested",
    }


def test_get_country_accepts_lowercase_country_codes(
    service: ApiService, repository: InMemoryScanRepository
):
    repository.save_country(make_country_result(Country.JP))

    assert service.get_country(SCAN_ID, "jp")["country"] == "JP"


def test_get_country_raises_scan_not_found_when_the_scan_is_missing(service: ApiService):
    with pytest.raises(ScanNotFoundError):
        service.get_country("scan_missing", "JP")


def test_get_country_raises_country_not_found_when_only_the_country_is_missing(
    service: ApiService, repository: InMemoryScanRepository
):
    repository.save_scan(make_scan_summary())

    with pytest.raises(CountryNotFoundError):
        service.get_country(SCAN_ID, "DE")


def test_get_country_rejects_an_unknown_country(service: ApiService):
    with pytest.raises(InvalidRequestError):
        service.get_country(SCAN_ID, "ZZ")


def test_an_invalid_country_is_rejected_before_the_scan_is_looked_up(service: ApiService):
    """400 が 404 に優先すること。存在しないスキャンでも国の検証が先。"""
    with pytest.raises(InvalidRequestError):
        service.get_country("scan_missing", "ZZ")


# --- scan_id の検証 ---------------------------------------------------------------------


@pytest.mark.parametrize(
    "scan_id",
    [
        pytest.param("../../etc/passwd", id="path traversal"),
        pytest.param("scan/../other", id="embedded traversal"),
        pytest.param("", id="empty"),
        pytest.param("scan id", id="whitespace"),
        pytest.param("s" * 65, id="too long"),
    ],
)
def test_a_malformed_scan_id_is_reported_as_not_found(service: ApiService, scan_id):
    """パス区切りを含む値を下層のストレージキーへ渡さない。"""
    with pytest.raises(ScanNotFoundError):
        service.get_scan(scan_id)
    with pytest.raises(ScanNotFoundError):
        service.get_country(scan_id, "JP")


def test_a_malformed_scan_id_never_reaches_the_repository():
    """リポジトリが例外を投げる実装でも、検証で先に止まること。"""
    service = ApiService(ExplodingRepository(), InMemoryJobQueue(), make_settings())

    with pytest.raises(ScanNotFoundError):
        service.get_scan("../../etc/passwd")


def test_the_not_found_message_does_not_echo_the_requested_scan_id(service: ApiService):
    """任意入力をレスポンス本文へ反射させない。"""
    with pytest.raises(ScanNotFoundError) as excinfo:
        service.get_scan("../../etc/passwd")

    assert "etc/passwd" not in str(excinfo.value)


# --------------------------------------------------------------------------
# Screen 2 が表示する詳細(W7 の契約変更)
# --------------------------------------------------------------------------


def test_get_country_returns_the_screen_two_details(
    service: ApiService, repository: InMemoryScanRepository
):
    """fixture を通した実結果で、Screen 2 の表示に必要な内容が返ること。"""
    profile = load_query_profile(TopicId.ELDER_CARE, Country.JP)
    scanner = CountryScanner(FixtureSerpApiClient(), StubLlmClient())
    outcome = scanner.scan(profile, scan_id=SCAN_ID, scan_time=SCAN_TIME)
    repository.save_country(outcome.result)

    payload = service.get_country(SCAN_ID, "JP")

    assert payload["trends"] is not None
    assert len(payload["trends"]["series"]) == 3
    assert len(payload["trends"]["series"][0]["points"]) == 52
    assert len(payload["related_queries"]) == 12
    assert len(payload["search_results"]) == 10
    assert len(payload["news_results"]) == 9
    # 分類結果を添えて返す(UI が「DIRECT_PROVIDER と分類された」を示せる)
    assert payload["search_results"][0]["classification"]["classification"]
    assert payload["related_queries"][0]["item"]["query"]
    # Maps は Top2 のみ。ここでは取得していないので null
    assert payload["maps_results"] is None


def test_maps_results_distinguishes_not_requested_from_empty(
    service: ApiService, repository: InMemoryScanRepository
):
    """`null`(取得していない)と `[]`(取得したが0件)は意味が違う。"""
    repository.save_country(make_country_result(Country.JP))
    assert service.get_country(SCAN_ID, "JP")["maps_results"] is None

    result = make_country_result(Country.US)
    with_empty = CountryResult.model_validate(result.model_dump() | {"maps_results": []})
    repository.save_country(with_empty)
    assert service.get_country(SCAN_ID, "US")["maps_results"] == []


def test_a_country_result_stays_well_below_the_dynamodb_item_limit():
    """DynamoDB の項目上限は 400KB。詳細を持たせても余裕があること。"""
    profile = load_query_profile(TopicId.ELDER_CARE, Country.JP)
    scanner = CountryScanner(FixtureSerpApiClient(), StubLlmClient())
    outcome = scanner.scan(profile, scan_id=SCAN_ID, scan_time=SCAN_TIME)
    with_maps = scanner.attach_maps(outcome, profile, scan_time=SCAN_TIME)

    size = len(with_maps.result.model_dump_json().encode("utf-8"))
    assert size < 200 * 1024, f"CountryResult が {size} バイトに増えている"


def test_error_bodies_truncate_reflected_input(service: ApiService):
    """利用者入力を無制限に反射させない。

    5000文字の `topic_id` を送られると本文が 5KB になり、Lambda の
    レスポンス上限まで増幅できてしまう。
    """
    with pytest.raises(InvalidRequestError) as excinfo:
        service.create_scan({"topic_id": "x" * 5000}, scan_id=SCAN_ID, scan_time=SCAN_TIME)
    message = excinfo.value.payload["error"]["message"]
    assert len(message) < 200
    assert "truncated" in message


def test_unknown_field_errors_list_only_a_few_names(service: ApiService):
    body = {"topic_id": "elder_care", **{f"junk{index}": 1 for index in range(500)}}
    with pytest.raises(InvalidRequestError) as excinfo:
        service.create_scan(body, scan_id=SCAN_ID, scan_time=SCAN_TIME)
    message = excinfo.value.payload["error"]["message"]
    assert len(message) < 200
    assert "+495" in message


def test_an_enqueue_failure_does_not_leave_the_scan_processing(
    repository: InMemoryScanRepository,
):
    """ジョブを投入できなければ誰も処理しない。

    `processing` のまま残すと UI が終端状態へ到達できず、2秒 Polling を
    続ける。
    """

    class ExplodingQueue:
        def enqueue(self, jobs):
            del jobs
            message = "sqs down"
            raise RuntimeError(message)

    service = ApiService(repository, ExplodingQueue(), Settings())
    with pytest.raises(RuntimeError, match="sqs down"):
        service.create_scan({"topic_id": "elder_care"}, scan_id=SCAN_ID, scan_time=SCAN_TIME)

    stored = repository.get_scan(SCAN_ID)
    assert stored is not None
    assert stored.status is ScanStatus.PARTIALLY_FAILED
