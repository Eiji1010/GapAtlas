"""QueryProfile モデルの制約テスト。"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from gapatlas.domain.models.common import Country, TopicId
from gapatlas.domain.models.query_profile import QueryProfile, ReviewStatus, SerpApiParams


def _valid_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "topic_id": "elder_care",
        "country": "JP",
        "language": "ja",
        "version": "elder-care-jp-v1",
        "review_status": "LLM_GENERATED",
        "serpapi": {
            "geo": "JP",
            "gl": "jp",
            "hl": "ja",
            "google_domain": "google.co.jp",
        },
        "demand_queries": ["介護"],
        "related_query_seed": ["介護"],
        "solution_query": ["介護 サービス"],
        "news_query": ["介護 人手不足"],
        "maps_query": ["介護 サービス"],
        "maps_location": "@35.6812,139.7671,12z",
    }
    payload.update(overrides)
    return payload


def test_valid_profile():
    profile = QueryProfile.model_validate(_valid_payload())
    assert profile.topic_id is TopicId.ELDER_CARE
    assert profile.country is Country.JP
    assert profile.review_status is ReviewStatus.LLM_GENERATED
    assert profile.related_seed == "介護"
    assert profile.solution == "介護 サービス"
    assert profile.news == "介護 人手不足"
    assert profile.maps == "介護 サービス"
    assert profile.maps_location == "@35.6812,139.7671,12z"
    assert profile.is_primary_language is True


def test_is_primary_language_false_for_mismatched_language():
    profile = QueryProfile.model_validate(_valid_payload(language="en"))
    assert profile.is_primary_language is False


@pytest.mark.parametrize("count", [0, 6])
def test_demand_queries_count_constraint(count):
    with pytest.raises(ValidationError, match="demand_queries"):
        QueryProfile.model_validate(_valid_payload(demand_queries=[f"q{i}" for i in range(count)]))


@pytest.mark.parametrize("count", [1, 2, 3, 4, 5])
def test_demand_queries_accepts_one_to_five(count):
    profile = QueryProfile.model_validate(
        _valid_payload(demand_queries=[f"q{i}" for i in range(count)])
    )
    assert len(profile.demand_queries) == count


def test_demand_queries_rejects_blank_item():
    with pytest.raises(ValidationError, match="demand_queries"):
        QueryProfile.model_validate(_valid_payload(demand_queries=["介護", "   "]))


@pytest.mark.parametrize(
    "field", ["related_query_seed", "solution_query", "news_query", "maps_query"]
)
@pytest.mark.parametrize("count", [0, 2])
def test_single_item_fields_reject_wrong_count(field, count):
    with pytest.raises(ValidationError, match=field):
        QueryProfile.model_validate(_valid_payload(**{field: [f"q{i}" for i in range(count)]}))


@pytest.mark.parametrize("field", ["geo", "gl", "hl", "google_domain"])
def test_serpapi_params_reject_empty(field):
    params = {"geo": "JP", "gl": "jp", "hl": "ja", "google_domain": "google.co.jp"}
    params[field] = ""
    with pytest.raises(ValidationError):
        SerpApiParams.model_validate(params)


@pytest.mark.parametrize("field", ["geo", "gl", "hl", "google_domain"])
def test_serpapi_params_reject_whitespace_only(field):
    params = {"geo": "JP", "gl": "jp", "hl": "ja", "google_domain": "google.co.jp"}
    params[field] = "  "
    with pytest.raises(ValidationError):
        SerpApiParams.model_validate(params)


def test_profile_rejects_unknown_key():
    with pytest.raises(ValidationError):
        QueryProfile.model_validate(_valid_payload(unknown_field="x"))


def test_profile_rejects_unknown_country():
    with pytest.raises(ValidationError):
        QueryProfile.model_validate(_valid_payload(country="FR"))


@pytest.mark.parametrize(
    "value",
    [
        "@35.6812,139.7671,12z",
        "@-33.8688,151.2093,14z",
        "@0,0,1z",
        "@40.7455096,-74.0083012,14z",
        "@51.5074,-0.1278,12.5z",
    ],
)
def test_maps_location_accepts_ll_format(value):
    profile = QueryProfile.model_validate(_valid_payload(maps_location=value))
    assert profile.maps_location == value


@pytest.mark.parametrize(
    "value",
    [
        "35.6812,139.7671,12z",  # 先頭の @ が無い
        "@35.6812,139.7671",  # ズームが無い
        "@35.6812,139.7671,12",  # 末尾の z が無い
        "@35.6812;139.7671;12z",  # 区切りが , でない
        "@abc,def,12z",  # 数値でない
        "@35.6812,139.7671,12z ",  # 末尾に空白
        "",  # 空
        "@91.0,0.0,12z",  # 緯度が範囲外
        "@0.0,181.0,12z",  # 経度が範囲外
    ],
)
def test_maps_location_rejects_invalid_format(value):
    with pytest.raises(ValidationError, match="maps_location"):
        QueryProfile.model_validate(_valid_payload(maps_location=value))


def test_maps_query_rejects_blank_item():
    with pytest.raises(ValidationError, match="maps_query"):
        QueryProfile.model_validate(_valid_payload(maps_query=["   "]))
