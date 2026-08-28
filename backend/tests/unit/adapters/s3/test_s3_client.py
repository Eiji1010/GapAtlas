"""`S3ScanArchive` のテスト。

**実 AWS は呼ばない。** すべてフェイククライアントで検証する
(AWS 認証情報が無い前提)。日時は固定値を使い、テストを決定的にする。
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import pytest
from botocore.exceptions import ClientError, EndpointConnectionError

from gapatlas.adapters.s3.client import (
    CONTENT_TYPE_JSON,
    MAX_OBJECT_BYTES,
    SERVER_SIDE_ENCRYPTION,
    S3ScanArchive,
)
from gapatlas.adapters.s3.errors import ArchiveError, ArchiveWriteError
from gapatlas.adapters.s3.factory import create_scan_archive
from gapatlas.adapters.s3.keys import curated_key, normalized_key, raw_key
from gapatlas.config.settings import Settings
from gapatlas.domain.models.common import (
    Country,
    CountryStatus,
    SourceName,
    SourceStatus,
    TopicId,
)
from gapatlas.domain.models.normalized import (
    NewsArticle,
    NormalizedEvidence,
    RisingQuery,
    SearchResultItem,
    SourceFetch,
    TrendPoint,
    TrendsSeries,
    TrendsTimeseries,
)
from gapatlas.domain.models.result import CountryResult, Evidence, Versions
from gapatlas.domain.models.scores import ConfidenceBreakdown, ScoreComponents

SCAN_TIME = datetime(2026, 8, 28, tzinfo=UTC)
SCAN_ID = "s1"
BUCKET = "gapatlas-data"

VERSIONS = Versions(
    query_profile_version="elder-care-jp-v2",
    score_version="gapatlas-score-v1",
    classifier_version="gapatlas-classifier-v1-stub",
    prompt_version="gapatlas-prompt-v1-stub",
)


@dataclass
class FakeS3Client:
    """`put_object` の呼び出しを記録するだけのフェイク。ネットワークを使わない。"""

    error: Exception | None = None
    calls: list[dict[str, Any]] = field(default_factory=list)

    def put_object(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return {"ETag": '"fake-etag"'}


def make_archive(error: Exception | None = None) -> tuple[S3ScanArchive, FakeS3Client]:
    client = FakeS3Client(error=error)
    settings = Settings(s3_bucket_name=BUCKET, aws_region="ap-northeast-1")
    return S3ScanArchive(settings, client=client), client


def make_evidence() -> NormalizedEvidence:
    return NormalizedEvidence(
        trends=TrendsTimeseries(
            series=[
                TrendsSeries(
                    query="介護 人手不足",
                    points=[
                        TrendPoint(timestamp=datetime(2026, 8, 21, tzinfo=UTC), value=51.0),
                        TrendPoint(timestamp=datetime(2026, 8, 28, tzinfo=UTC), value=73.5),
                    ],
                )
            ]
        ),
        rising_queries=[
            RisingQuery(
                query="介護 施設 空き",
                growth_percent=5000.0,
                is_breakout=True,
                raw_value="Breakout",
            )
        ],
        search_results=[
            SearchResultItem(position=1, title="Elder care", link="https://example.com/a")
        ],
        news_articles=[
            NewsArticle(
                position=1,
                title="Care home closures",
                link="https://example.com/n",
                published_at=datetime(2026, 8, 27, tzinfo=UTC),
            )
        ],
        maps_places=None,
        fetches={
            SourceName.TRENDS: SourceFetch(
                source=SourceName.TRENDS,
                status=SourceStatus.OK,
                fetched_at=SCAN_TIME,
            )
        },
    )


def make_result(country: Country = Country.JP) -> CountryResult:
    return CountryResult(
        scan_id=SCAN_ID,
        topic_id=TopicId.ELDER_CARE,
        country=country,
        status=CountryStatus.COMPLETED,
        need_gap_score=86,
        confidence=92,
        components=ScoreComponents(demand=91.4, pain=84.0, solution_gap=78.2, news_urgency=None),
        confidence_breakdown=ConfidenceBreakdown(
            data_completeness=100.0,
            sample_sufficiency=97.0,
            localization_quality=70.0,
            source_agreement=88.0,
            freshness=92.0,
        ),
        source_status={SourceName.TRENDS: SourceStatus.OK},
        evidence=[
            Evidence(
                id="E1",
                source=SourceName.TRENDS,
                summary="需要が上昇している",
                url="https://example.com/a",
            )
        ],
        versions=VERSIONS,
        computed_at=SCAN_TIME,
    )


# --- キー -------------------------------------------------------------------------------


@pytest.mark.parametrize("country", list(Country))
@pytest.mark.parametrize("source", list(SourceName))
def test_put_raw_writes_to_the_key_from_keys_module(country: Country, source: SourceName):
    """キーは `keys.py` の関数が返すものと一致すること(自前で組み立てない)。"""
    archive, client = make_archive()

    key = archive.put_raw(
        source=source,
        topic_id=TopicId.ELDER_CARE,
        country=country,
        scan_time=SCAN_TIME,
        scan_id=SCAN_ID,
        payload={"search_metadata": {"status": "Success"}},
    )

    expected = raw_key(
        source=source,
        topic_id=TopicId.ELDER_CARE,
        country=country,
        scan_time=SCAN_TIME,
        scan_id=SCAN_ID,
    )
    assert key == expected
    assert len(client.calls) == 1
    assert client.calls[0]["Key"] == expected
    assert client.calls[0]["Bucket"] == BUCKET


@pytest.mark.parametrize("country", list(Country))
def test_put_normalized_writes_to_the_key_from_keys_module(country: Country):
    archive, client = make_archive()

    key = archive.put_normalized(
        topic_id=TopicId.ELDER_CARE,
        country=country,
        scan_time=SCAN_TIME,
        scan_id=SCAN_ID,
        evidence=make_evidence(),
    )

    expected = normalized_key(
        topic_id=TopicId.ELDER_CARE, country=country, scan_time=SCAN_TIME, scan_id=SCAN_ID
    )
    assert key == expected
    assert client.calls[0]["Key"] == expected


@pytest.mark.parametrize("country", list(Country))
def test_put_curated_writes_to_the_key_from_keys_module(country: Country):
    archive, client = make_archive()

    key = archive.put_curated(
        topic_id=TopicId.ELDER_CARE,
        country=country,
        scan_time=SCAN_TIME,
        scan_id=SCAN_ID,
        result=make_result(country),
    )

    expected = curated_key(
        topic_id=TopicId.ELDER_CARE, country=country, scan_time=SCAN_TIME, scan_id=SCAN_ID
    )
    assert key == expected
    assert client.calls[0]["Key"] == expected


# --- 本文 -------------------------------------------------------------------------------


RAW_PAYLOAD: dict[str, Any] = {
    # 意図的にアルファベット順ではない。並べ替えられていないことを検出する。
    "search_metadata": {"status": "Success", "id": "abc"},
    "interest_over_time": {
        "timeline_data": [
            {"timestamp": "1756339200", "values": [{"extracted_value": 73, "value": "73"}]}
        ]
    },
    "related_queries": {"rising": [{"query": "介護 施設 空き", "value": "Breakout"}]},
    "flags": {"is_partial": True, "missing": None, "ratio": 0.5},
}


def test_raw_body_is_equivalent_to_the_input_json():
    """`raw/` は無加工。キーの欠落・型の変化・並べ替えが無いこと。"""
    archive, client = make_archive()

    archive.put_raw(
        source=SourceName.TRENDS,
        topic_id=TopicId.ELDER_CARE,
        country=Country.JP,
        scan_time=SCAN_TIME,
        scan_id=SCAN_ID,
        payload=RAW_PAYLOAD,
    )

    body = client.calls[0]["Body"]
    assert isinstance(body, bytes)
    text = body.decode("utf-8")
    loaded = json.loads(text)

    assert loaded == RAW_PAYLOAD
    assert list(loaded) == list(RAW_PAYLOAD), "トップレベルのキー順が保たれること"
    assert list(loaded["search_metadata"]) == list(RAW_PAYLOAD["search_metadata"])
    # 型が変わっていないこと(bool / None / int / float)。
    assert loaded["flags"]["is_partial"] is True
    assert loaded["flags"]["missing"] is None
    assert isinstance(loaded["flags"]["ratio"], float)
    value = loaded["interest_over_time"]["timeline_data"][0]["values"][0]["extracted_value"]
    assert isinstance(value, int)
    # 非 ASCII をエスケープしない(内容は同じだが、生の JSON として読めること)。
    assert "介護 施設 空き" in text


def test_normalized_body_round_trips_through_the_model():
    archive, client = make_archive()
    evidence = make_evidence()

    archive.put_normalized(
        topic_id=TopicId.ELDER_CARE,
        country=Country.JP,
        scan_time=SCAN_TIME,
        scan_id=SCAN_ID,
        evidence=evidence,
    )

    body = client.calls[0]["Body"].decode("utf-8")
    assert NormalizedEvidence.model_validate_json(body) == evidence


def test_curated_body_round_trips_through_the_model():
    archive, client = make_archive()
    result = make_result()

    archive.put_curated(
        topic_id=TopicId.ELDER_CARE,
        country=Country.JP,
        scan_time=SCAN_TIME,
        scan_id=SCAN_ID,
        result=result,
    )

    body = client.calls[0]["Body"].decode("utf-8")
    assert CountryResult.model_validate_json(body) == result


def test_normalized_and_curated_bodies_are_one_json_line():
    """Glue の JSON SerDe は行区切りの JSON を読む(1オブジェクト=1レコード)。"""
    archive, client = make_archive()

    archive.put_normalized(
        topic_id=TopicId.ELDER_CARE,
        country=Country.JP,
        scan_time=SCAN_TIME,
        scan_id=SCAN_ID,
        evidence=make_evidence(),
    )
    archive.put_curated(
        topic_id=TopicId.ELDER_CARE,
        country=Country.JP,
        scan_time=SCAN_TIME,
        scan_id=SCAN_ID,
        result=make_result(),
    )

    for call in client.calls:
        text = call["Body"].decode("utf-8")
        assert text.endswith("\n")
        assert len(text.splitlines()) == 1


# --- PUT の引数 -------------------------------------------------------------------------


def test_content_type_and_server_side_encryption_are_set():
    archive, client = make_archive()

    archive.put_raw(
        source=SourceName.NEWS,
        topic_id=TopicId.ELDER_CARE,
        country=Country.GB,
        scan_time=SCAN_TIME,
        scan_id=SCAN_ID,
        payload={"news_results": []},
    )
    archive.put_normalized(
        topic_id=TopicId.ELDER_CARE,
        country=Country.GB,
        scan_time=SCAN_TIME,
        scan_id=SCAN_ID,
        evidence=make_evidence(),
    )
    archive.put_curated(
        topic_id=TopicId.ELDER_CARE,
        country=Country.GB,
        scan_time=SCAN_TIME,
        scan_id=SCAN_ID,
        result=make_result(Country.GB),
    )

    assert len(client.calls) == 3
    for call in client.calls:
        assert call["ContentType"] == CONTENT_TYPE_JSON == "application/json"
        assert call["ServerSideEncryption"] == SERVER_SIDE_ENCRYPTION == "AES256"


def test_no_acl_is_ever_sent():
    """S3 の public access は禁止(docs/architecture.md「Security」)。"""
    archive, client = make_archive()

    archive.put_raw(
        source=SourceName.SEARCH,
        topic_id=TopicId.ELDER_CARE,
        country=Country.US,
        scan_time=SCAN_TIME,
        scan_id=SCAN_ID,
        payload={"organic_results": []},
    )

    assert "ACL" not in client.calls[0]
    assert "GrantRead" not in client.calls[0]


# --- 失敗の変換 -------------------------------------------------------------------------


@pytest.mark.parametrize(
    "error",
    [
        ClientError({"Error": {"Code": "AccessDenied", "Message": "denied"}}, "PutObject"),
        EndpointConnectionError(endpoint_url="https://s3.example.invalid/"),
    ],
)
def test_botocore_errors_become_archive_write_error(error: Exception):
    archive, _ = make_archive(error=error)

    with pytest.raises(ArchiveWriteError) as exc_info:
        archive.put_raw(
            source=SourceName.TRENDS,
            topic_id=TopicId.ELDER_CARE,
            country=Country.JP,
            scan_time=SCAN_TIME,
            scan_id=SCAN_ID,
            payload={"a": 1},
        )

    message = str(exc_info.value)
    assert type(error).__name__ in message
    assert "raw/source=trends/topic=elder_care/country=JP/dt=2026-08-28/s1.json" in message


def test_stored_content_never_appears_in_the_error_message():
    """例外メッセージに保存内容そのものを載せない。"""
    marker = "do-not-log-this-response-body"
    archive, _ = make_archive(
        error=ClientError({"Error": {"Code": "AccessDenied", "Message": "denied"}}, "PutObject")
    )

    with pytest.raises(ArchiveWriteError) as exc_info:
        archive.put_raw(
            source=SourceName.SEARCH,
            topic_id=TopicId.ELDER_CARE,
            country=Country.DE,
            scan_time=SCAN_TIME,
            scan_id=SCAN_ID,
            payload={"organic_results": [{"link": f"https://example.com/{marker}"}]},
        )

    assert marker not in str(exc_info.value)


def test_curated_content_never_appears_in_the_error_message():
    archive, _ = make_archive(
        error=ClientError({"Error": {"Code": "AccessDenied", "Message": "denied"}}, "PutObject")
    )

    with pytest.raises(ArchiveWriteError) as exc_info:
        archive.put_curated(
            topic_id=TopicId.ELDER_CARE,
            country=Country.IN,
            scan_time=SCAN_TIME,
            scan_id=SCAN_ID,
            result=make_result(Country.IN),
        )

    message = str(exc_info.value)
    assert "需要が上昇している" not in message
    assert "need_gap_score" not in message


def test_payload_that_is_not_json_serializable_becomes_archive_write_error():
    archive, client = make_archive()

    with pytest.raises(ArchiveWriteError):
        archive.put_raw(
            source=SourceName.TRENDS,
            topic_id=TopicId.ELDER_CARE,
            country=Country.JP,
            scan_time=SCAN_TIME,
            scan_id=SCAN_ID,
            payload={"when": object()},
        )

    assert client.calls == [], "直列化に失敗したら S3 を呼ばない"


def test_body_over_the_limit_is_rejected_without_calling_s3():
    """巨大な本文を boto3 へ渡さない(メモリ枯渇の防御)。"""
    archive, client = make_archive()
    oversized = "x" * (MAX_OBJECT_BYTES + 1)

    with pytest.raises(ArchiveWriteError) as exc_info:
        archive.put_raw(
            source=SourceName.TRENDS,
            topic_id=TopicId.ELDER_CARE,
            country=Country.JP,
            scan_time=SCAN_TIME,
            scan_id=SCAN_ID,
            payload={"body": oversized},
        )

    assert client.calls == []
    assert oversized not in str(exc_info.value)


def test_programming_errors_are_not_disguised_as_write_failures():
    """実装バグ(TypeError など)を握って「保存失敗」にしない。"""
    archive, _ = make_archive(error=TypeError("put_object() got an unexpected keyword argument"))

    with pytest.raises(TypeError):
        archive.put_raw(
            source=SourceName.TRENDS,
            topic_id=TopicId.ELDER_CARE,
            country=Country.JP,
            scan_time=SCAN_TIME,
            scan_id=SCAN_ID,
            payload={"a": 1},
        )


# --- boto3 の遅延 import ----------------------------------------------------------------


def test_missing_boto3_raises_a_clear_archive_error(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setitem(sys.modules, "boto3", None)
    settings = Settings(s3_bucket_name=BUCKET)

    with pytest.raises(ArchiveError) as exc_info:
        S3ScanArchive(settings)

    message = str(exc_info.value)
    assert "boto3" in message
    assert "aws" in message


def test_factory_also_reports_the_missing_dependency(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setitem(sys.modules, "boto3", None)

    with pytest.raises(ArchiveError):
        create_scan_archive(Settings(s3_bucket_name=BUCKET))


def test_factory_returns_the_s3_archive(monkeypatch: pytest.MonkeyPatch):
    """実 AWS へ繋がずにファクトリの分岐だけを検証する。"""

    def fake_builder(*, region: str) -> FakeS3Client:
        return FakeS3Client()

    monkeypatch.setattr("gapatlas.adapters.s3.client._build_default_client", fake_builder)

    assert isinstance(create_scan_archive(Settings(s3_bucket_name=BUCKET)), S3ScanArchive)


def test_injected_client_is_used_without_touching_boto3(monkeypatch: pytest.MonkeyPatch):
    """フェイクを注入した場合は boto3 を一切 import しない(=実 AWS を呼ばない)。"""
    monkeypatch.setitem(sys.modules, "boto3", None)
    client = FakeS3Client()
    archive = S3ScanArchive(Settings(s3_bucket_name=BUCKET), client=client)

    archive.put_raw(
        source=SourceName.MAPS,
        topic_id=TopicId.ELDER_CARE,
        country=Country.JP,
        scan_time=SCAN_TIME,
        scan_id=SCAN_ID,
        payload={"local_results": []},
    )
    archive.put_normalized(
        topic_id=TopicId.ELDER_CARE,
        country=Country.JP,
        scan_time=SCAN_TIME,
        scan_id=SCAN_ID,
        evidence=make_evidence(),
    )
    archive.put_curated(
        topic_id=TopicId.ELDER_CARE,
        country=Country.JP,
        scan_time=SCAN_TIME,
        scan_id=SCAN_ID,
        result=make_result(),
    )

    assert len(client.calls) == 3
