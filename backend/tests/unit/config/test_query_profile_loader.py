"""QueryProfile ローダーのテスト。

最重要は「`config/query_profiles/elder_care/*.yaml` の実ファイル5件が
そのままロードできること」。実物と型が一致していることの証明になる。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from gapatlas.config import query_profile_loader
from gapatlas.config.errors import QueryProfileNotFoundError, QueryProfileValidationError
from gapatlas.config.query_profile_loader import (
    DEFAULT_QUERY_PROFILES_DIR,
    load_all_query_profiles,
    load_query_profile,
)
from gapatlas.domain.models.common import Country, TopicId
from gapatlas.domain.models.query_profile import ReviewStatus

VALID_YAML = """\
topic_id: elder_care
country: JP
language: ja
version: elder-care-jp-v1
review_status: LLM_GENERATED

serpapi:
  geo: JP
  gl: jp
  hl: ja
  google_domain: google.co.jp

demand_queries:
  - 介護

related_query_seed:
  - 介護

solution_query:
  - 介護 サービス

news_query:
  - 介護 人手不足

maps_query:
  - 介護 サービス

maps_location: "@35.6812,139.7671,12z"
"""


def test_default_profiles_dir_points_at_repository_root():
    assert DEFAULT_QUERY_PROFILES_DIR.is_dir()
    assert DEFAULT_QUERY_PROFILES_DIR.name == "query_profiles"
    assert (DEFAULT_QUERY_PROFILES_DIR / "elder_care").is_dir()


@pytest.mark.parametrize("country", list(Country))
def test_real_profile_loads(country):
    """実ファイル5件すべてが QueryProfile として読み込めること。"""
    profile = load_query_profile(TopicId.ELDER_CARE, country)
    assert profile.topic_id is TopicId.ELDER_CARE
    assert profile.country is country
    assert 1 <= len(profile.demand_queries) <= 5
    assert len(profile.related_query_seed) == 1
    assert len(profile.solution_query) == 1
    assert len(profile.news_query) == 1
    assert len(profile.maps_query) == 1
    assert profile.maps_location.startswith("@")
    assert profile.version
    assert profile.serpapi.geo and profile.serpapi.gl
    assert profile.serpapi.hl and profile.serpapi.google_domain


@pytest.mark.parametrize("country", list(Country))
def test_real_profile_uses_primary_language(country):
    profile = load_query_profile(TopicId.ELDER_CARE, country)
    assert profile.is_primary_language is True


def test_real_profiles_are_all_llm_generated():
    """docs/query-profiles.md「現在の5か国はすべて LLM_GENERATED」と一致すること。"""
    profiles = load_all_query_profiles(TopicId.ELDER_CARE)
    assert set(profiles) == set(Country)
    for profile in profiles.values():
        assert profile.review_status is ReviewStatus.LLM_GENERATED


def test_gb_geo_and_gl_differ():
    """英国は geo=GB / gl=uk(docs/serpapi-schema.md)。"""
    profile = load_query_profile(TopicId.ELDER_CARE, Country.GB)
    assert profile.serpapi.geo == "GB"
    assert profile.serpapi.gl == "uk"


@pytest.mark.parametrize("country", list(Country))
def test_real_profile_maps_fields_match_maps_fixture(country):
    """QueryProfile の maps_query / maps_location が maps fixture と一致すること。

    ずれると Top2 の Local Evidence が fixture と別の場所・別のクエリを指す
    (backend/tests/fixtures/README.md)。
    """
    profile = load_query_profile(TopicId.ELDER_CARE, country)
    fixture_path = (
        Path(__file__).resolve().parents[2]
        / "fixtures"
        / "serpapi"
        / "elder_care"
        / country.value
        / "maps.json"
    )
    parameters = json.loads(fixture_path.read_text(encoding="utf-8"))["search_parameters"]
    assert profile.maps == parameters["q"]
    assert profile.maps_location == parameters["ll"]


def test_load_all_query_profiles_returns_every_country():
    profiles = load_all_query_profiles(TopicId.ELDER_CARE)
    assert len(profiles) == len(Country)
    assert profiles[Country.DE].language == "de"


def test_missing_profile_raises_not_found(tmp_path):
    (tmp_path / "elder_care").mkdir()
    with pytest.raises(QueryProfileNotFoundError, match="query profile not found"):
        load_query_profile(TopicId.ELDER_CARE, Country.US, base_dir=tmp_path)


def test_missing_topic_directory_raises_not_found(tmp_path):
    with pytest.raises(QueryProfileNotFoundError):
        load_query_profile(TopicId.ELDER_CARE, Country.JP, base_dir=tmp_path)


def test_load_all_raises_not_found_when_any_country_is_missing(tmp_path):
    topic_dir = tmp_path / "elder_care"
    topic_dir.mkdir()
    (topic_dir / "JP.yaml").write_text(VALID_YAML, encoding="utf-8")
    with pytest.raises(QueryProfileNotFoundError):
        load_all_query_profiles(TopicId.ELDER_CARE, base_dir=tmp_path)


def _write(tmp_path, filename: str, content: str):
    topic_dir = tmp_path / "elder_care"
    topic_dir.mkdir(exist_ok=True)
    (topic_dir / filename).write_text(content, encoding="utf-8")
    return topic_dir


def test_country_mismatch_between_filename_and_yaml(tmp_path):
    _write(tmp_path, "US.yaml", VALID_YAML)
    with pytest.raises(QueryProfileValidationError, match="country mismatch"):
        load_query_profile(TopicId.ELDER_CARE, Country.US, base_dir=tmp_path)


def test_valid_profile_loads_from_custom_base_dir(tmp_path):
    _write(tmp_path, "JP.yaml", VALID_YAML)
    profile = load_query_profile(TopicId.ELDER_CARE, Country.JP, base_dir=tmp_path)
    assert profile.related_seed == "介護"


def test_invalid_yaml_raises_validation_error(tmp_path):
    _write(tmp_path, "JP.yaml", "topic_id: [unclosed\n")
    with pytest.raises(QueryProfileValidationError, match="failed to parse"):
        load_query_profile(TopicId.ELDER_CARE, Country.JP, base_dir=tmp_path)


def test_non_mapping_yaml_raises_validation_error(tmp_path):
    _write(tmp_path, "JP.yaml", "- a\n- b\n")
    with pytest.raises(QueryProfileValidationError, match="must be a YAML mapping"):
        load_query_profile(TopicId.ELDER_CARE, Country.JP, base_dir=tmp_path)


def test_constraint_violation_in_file_raises_validation_error(tmp_path):
    broken = VALID_YAML.replace("related_query_seed:\n  - 介護\n", "related_query_seed: []\n")
    _write(tmp_path, "JP.yaml", broken)
    with pytest.raises(QueryProfileValidationError, match="related_query_seed"):
        load_query_profile(TopicId.ELDER_CARE, Country.JP, base_dir=tmp_path)


def test_yaml_load_is_not_used():
    """`yaml.safe_load` のみを使うこと(任意オブジェクト構築を許さない)。"""
    source = Path(query_profile_loader.__file__).read_text(encoding="utf-8")
    assert "yaml.safe_load" in source
    assert "yaml.load(" not in source
