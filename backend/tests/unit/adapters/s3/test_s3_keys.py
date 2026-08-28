"""S3 のオブジェクトキーのテスト。

Glue のパーティション射影(Phase 12)がこの形に依存する。**リテラルで固定する。**
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from gapatlas.adapters.s3.keys import curated_key, normalized_key, partition_date, raw_key
from gapatlas.domain.models.common import Country, SourceName, TopicId

SCAN_TIME = datetime(2026, 8, 28, tzinfo=UTC)


def test_partition_date_is_the_utc_date():
    assert partition_date(SCAN_TIME) == "2026-08-28"
    assert partition_date(datetime(2026, 1, 2, 23, 59, tzinfo=UTC)) == "2026-01-02"


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        (SourceName.TRENDS, "raw/source=trends/topic=elder_care/country=JP/dt=2026-08-28/s1.json"),
        (
            SourceName.RELATED_QUERIES,
            "raw/source=related_queries/topic=elder_care/country=JP/dt=2026-08-28/s1.json",
        ),
        (SourceName.MAPS, "raw/source=maps/topic=elder_care/country=JP/dt=2026-08-28/s1.json"),
    ],
)
def test_raw_key_layout(source, expected):
    key = raw_key(
        source=source,
        topic_id=TopicId.ELDER_CARE,
        country=Country.JP,
        scan_time=SCAN_TIME,
        scan_id="s1",
    )
    assert key == expected


def test_normalized_key_layout():
    assert (
        normalized_key(
            topic_id=TopicId.ELDER_CARE,
            country=Country.DE,
            scan_time=SCAN_TIME,
            scan_id="s1",
        )
        == "normalized/topic=elder_care/country=DE/dt=2026-08-28/s1.json"
    )


def test_curated_key_layout():
    assert (
        curated_key(
            topic_id=TopicId.ELDER_CARE,
            country=Country.IN,
            scan_time=SCAN_TIME,
            scan_id="s1",
        )
        == "curated/gap_scores/topic=elder_care/country=IN/dt=2026-08-28/s1.json"
    )


def test_keys_never_start_with_a_slash():
    """S3 のキーは先頭にスラッシュを付けない(空のディレクトリ階層ができる)。"""
    for key in (
        raw_key(
            source=SourceName.NEWS,
            topic_id=TopicId.ELDER_CARE,
            country=Country.US,
            scan_time=SCAN_TIME,
            scan_id="s1",
        ),
        normalized_key(
            topic_id=TopicId.ELDER_CARE, country=Country.US, scan_time=SCAN_TIME, scan_id="s1"
        ),
        curated_key(
            topic_id=TopicId.ELDER_CARE, country=Country.US, scan_time=SCAN_TIME, scan_id="s1"
        ),
    ):
        assert not key.startswith("/")
        assert "//" not in key
