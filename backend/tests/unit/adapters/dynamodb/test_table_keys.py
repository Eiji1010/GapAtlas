"""キー設計のテスト。

**キーの形をリテラルで固定する。** Terraform / Athena / 将来のマイグレーションが
この形に依存するため、変更を無言で通さない。
"""

from __future__ import annotations

import pytest

from gapatlas.adapters.dynamodb.table import (
    PARTITION_KEY_ATTRIBUTE,
    SORT_KEY_ATTRIBUTE,
    TTL_ATTRIBUTE,
    country_sort_key,
    is_country_sort_key,
    meta_sort_key,
    scan_partition_key,
)
from gapatlas.domain.models.common import Country


def test_key_attribute_names_are_fixed():
    assert PARTITION_KEY_ATTRIBUTE == "PK"
    assert SORT_KEY_ATTRIBUTE == "SK"


def test_ttl_attribute_name_is_fixed():
    """Terraform の `ttl { attribute_name = ... }` と一致させる。"""
    assert TTL_ATTRIBUTE == "ttl"


def test_scan_partition_key():
    assert scan_partition_key("scan_abc123") == "SCAN#scan_abc123"


def test_meta_sort_key():
    assert meta_sort_key() == "META"


@pytest.mark.parametrize(
    ("country", "expected"),
    [
        (Country.JP, "COUNTRY#JP"),
        (Country.US, "COUNTRY#US"),
        (Country.GB, "COUNTRY#GB"),
        (Country.DE, "COUNTRY#DE"),
        (Country.IN, "COUNTRY#IN"),
    ],
)
def test_country_sort_key(country: Country, expected: str):
    assert country_sort_key(country) == expected


def test_country_sort_keys_sort_by_country_code():
    """SK の辞書順が国コード昇順と一致する(Query の既定順で並ぶ)。"""
    keys = [country_sort_key(country) for country in (Country.US, Country.DE, Country.JP)]
    assert sorted(keys) == ["COUNTRY#DE", "COUNTRY#JP", "COUNTRY#US"]


def test_meta_sorts_after_country_items():
    """`META` は `COUNTRY#` より後ろに来る(`C` < `M`)。

    Query の既定順(SK 昇順)がこの前提で決まる。`list_countries` は SK の順に
    依存せず国コードで並べ直すが、ページ分割の境界を読むときにこの順序が要る。
    """
    assert country_sort_key(Country.DE) < meta_sort_key()


@pytest.mark.parametrize(
    ("sort_key", "expected"),
    [
        ("COUNTRY#JP", True),
        ("META", False),
        ("", False),
        ("COUNTRY", False),
        ("BRIEF#JP", False),
    ],
)
def test_is_country_sort_key(sort_key: str, expected: bool):
    assert is_country_sort_key(sort_key) is expected
