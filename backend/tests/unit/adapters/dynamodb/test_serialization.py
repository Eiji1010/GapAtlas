"""モデル ↔ DynamoDB 項目の変換テスト。

**数値の往復**が中心。DynamoDB は数値を `Decimal` で返し、boto3 は `float` の
書き込みを拒否する。
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from gapatlas.adapters.dynamodb.errors import RepositoryDataError
from gapatlas.adapters.dynamodb.serialization import (
    _to_dynamodb_value,
    from_attributes,
    to_attributes,
)
from gapatlas.domain.models.common import Country
from gapatlas.domain.models.result import CountryResult, ScanSummary


def _to_stored(value: object) -> object:
    """DynamoDB が返す形(数値はすべて `Decimal`)へ寄せる。"""
    if value is None or isinstance(value, bool | str | Decimal):
        return value
    if isinstance(value, int):
        return Decimal(value)
    if isinstance(value, dict):
        return {key: _to_stored(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_to_stored(item) for item in value]
    raise AssertionError(f"unexpected type {type(value).__name__}")


def test_no_float_is_written(country_result: CountryResult):
    """`float` を残すと boto3 が TypeError を投げる。すべて Decimal になること。"""
    item = to_attributes(country_result)
    stack: list[object] = [item]
    while stack:
        value = stack.pop()
        assert not isinstance(value, float)
        if isinstance(value, dict):
            stack.extend(value.values())
        elif isinstance(value, list):
            stack.extend(value)


def test_float_becomes_an_exact_decimal(country_result: CountryResult):
    """`Decimal(str(x))` を使う。`Decimal(float)` だと桁が汚れて boto3 が落ちる。"""
    item = to_attributes(country_result)
    assert item["components"]["demand"] == Decimal("84.6")
    assert item["confidence_breakdown"]["sample_sufficiency"] == Decimal("97.25")


def test_int_stays_an_integer(country_result: CountryResult):
    assert to_attributes(country_result)["need_gap_score"] == 75


def test_none_is_preserved(country_result: CountryResult):
    item = to_attributes(country_result)
    assert item["components"]["solution_gap"] is None
    assert item["evidence"][1]["url"] is None


def test_datetime_is_stored_as_iso8601(country_result: CountryResult):
    stored = to_attributes(country_result)["computed_at"]
    assert isinstance(stored, str)
    assert stored.startswith("2026-08-28T00:00:00")


def test_country_result_round_trips_through_decimals(country_result: CountryResult):
    """float / int / None / ネストしたリストが往復で壊れないこと。"""
    stored = _to_stored(to_attributes(country_result))
    assert isinstance(stored, dict)
    restored = from_attributes(CountryResult, stored)
    assert restored.model_dump() == country_result.model_dump()
    assert restored.components.demand == 84.6
    assert restored.confidence_breakdown.sample_sufficiency == 97.25
    assert restored.need_gap_score == 75
    assert [item.url for item in restored.evidence] == ["https://example.com/a", None]


def test_nested_ranking_list_round_trips(make_summary):
    """`ranking` のようなネストしたリストも往復すること。"""
    summary = make_summary(with_brief=True)
    stored = _to_stored(to_attributes(summary))
    assert isinstance(stored, dict)
    restored = from_attributes(ScanSummary, stored)
    assert restored.model_dump() == summary.model_dump()
    assert [entry.country for entry in restored.ranking] == [Country.JP, Country.US]
    assert restored.ranking[1].need_gap_score is None


def test_integral_decimal_restores_int_fields(country_result: CountryResult):
    """整数値の `Decimal` を int フィールドへ復元できること。"""
    item = _to_stored(to_attributes(country_result))
    assert isinstance(item, dict)
    assert item["confidence"] == Decimal("91")
    assert from_attributes(CountryResult, item).confidence == 91


def test_reserved_attributes_are_stripped(country_result: CountryResult):
    """`PK` / `SK` / `ttl` は `extra="forbid"` のモデルへ渡さない。"""
    item = dict(to_attributes(country_result))
    item["PK"] = "SCAN#s1"
    item["SK"] = "COUNTRY#JP"
    item["ttl"] = Decimal(1_700_000_000)
    assert from_attributes(CountryResult, item).country is Country.JP


def test_to_attributes_omits_key_attributes(country_result: CountryResult):
    item = to_attributes(country_result)
    assert "PK" not in item
    assert "SK" not in item
    assert "ttl" not in item


def test_missing_required_attribute_raises_data_error(country_result: CountryResult):
    item = dict(to_attributes(country_result))
    del item["versions"]
    with pytest.raises(RepositoryDataError, match="versions"):
        from_attributes(CountryResult, item)


def test_type_mismatch_raises_data_error(country_result: CountryResult):
    item = dict(to_attributes(country_result))
    item["need_gap_score"] = "not-a-number"
    with pytest.raises(RepositoryDataError):
        from_attributes(CountryResult, item)


def test_data_error_does_not_leak_the_stored_value(country_result: CountryResult):
    """例外メッセージへ項目の中身を載せない(docs/architecture.md「Security」)。"""
    sensitive_value = "personally-identifiable-payload"
    item = dict(to_attributes(country_result))
    item["need_gap_score"] = sensitive_value
    with pytest.raises(RepositoryDataError) as excinfo:
        from_attributes(CountryResult, item)
    assert sensitive_value not in str(excinfo.value)
    # 原因例外を連鎖させない。`ValidationError` の文字列表現は入力値を含む。
    assert excinfo.value.__cause__ is None


def test_unsupported_attribute_type_raises_data_error(country_result: CountryResult):
    item = dict(to_attributes(country_result))
    item["confidence"] = {b"binary"}
    with pytest.raises(RepositoryDataError, match="unsupported attribute type"):
        from_attributes(CountryResult, item)


def test_non_finite_float_is_rejected():
    with pytest.raises(RepositoryDataError, match="non-finite"):
        _to_dynamodb_value(float("inf"))
