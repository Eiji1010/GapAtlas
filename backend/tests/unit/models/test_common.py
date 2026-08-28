"""common.py の列挙型・定数・共通型のテスト。"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

import pytest
from pydantic import BaseModel, ValidationError

from gapatlas.domain.models.common import (
    CORE_SOURCES,
    COUNTRY_LABELS,
    PRIMARY_LANGUAGES,
    Country,
    SourceName,
    UtcDatetime,
    ensure_utc,
)
from gapatlas.domain.models.errors import InvalidTemporalValueError

NAIVE_DATETIME = datetime.fromisoformat("2026-01-02T09:00:00")


def test_core_sources_excludes_maps():
    assert CORE_SOURCES == (
        SourceName.TRENDS,
        SourceName.RELATED_QUERIES,
        SourceName.SEARCH,
        SourceName.NEWS,
    )
    assert SourceName.MAPS not in CORE_SOURCES


def test_country_labels_cover_all_countries():
    assert set(COUNTRY_LABELS) == set(Country)
    assert COUNTRY_LABELS[Country.GB] == "United Kingdom"
    assert Country.JP.label == "Japan"


def test_primary_languages_cover_all_countries():
    assert set(PRIMARY_LANGUAGES) == set(Country)
    assert PRIMARY_LANGUAGES[Country.IN] == frozenset({"en", "hi"})


@pytest.mark.parametrize(
    ("country", "language", "expected"),
    [
        (Country.JP, "ja", True),
        (Country.JP, "en", False),
        (Country.US, "en", True),
        (Country.GB, "EN", True),
        (Country.DE, "de", True),
        (Country.DE, "en", False),
        (Country.IN, "hi", True),
        (Country.IN, "de", False),
    ],
)
def test_is_primary_language(country, language, expected):
    assert country.is_primary_language(language) is expected


class _Sample(BaseModel):
    when: UtcDatetime


def test_ensure_utc_normalizes_offset_to_utc():
    jst = timezone(timedelta(hours=9))
    value = datetime(2026, 1, 2, 9, 0, tzinfo=jst)
    assert ensure_utc(value) == datetime(2026, 1, 2, 0, 0, tzinfo=UTC)
    assert ensure_utc(value).tzinfo is UTC


def test_ensure_utc_rejects_naive_datetime():
    with pytest.raises(InvalidTemporalValueError):
        ensure_utc(NAIVE_DATETIME)


def test_model_rejects_naive_datetime():
    with pytest.raises(ValidationError):
        _Sample(when=NAIVE_DATETIME)


def test_model_rejects_naive_datetime_string():
    with pytest.raises(ValidationError):
        _Sample.model_validate({"when": "2026-01-02T09:00:00"})


def test_model_accepts_aware_datetime_string():
    sample = _Sample.model_validate({"when": "2026-01-02T09:00:00+09:00"})
    assert sample.when == datetime(2026, 1, 2, 0, 0, tzinfo=UTC)
