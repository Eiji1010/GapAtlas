"""`FixtureSerpApiClient` のテスト。

fixture モードは外部通信ゼロで全機能が動くことが要件
(AGENTS.md / docs/decisions/0003-fixture-first.md)。ここでは 5か国 x 5ソースの
全 fixture が読めることを確認する。
"""

from __future__ import annotations

from pathlib import Path

import pytest
from conftest import ALL_COUNTRIES, ALL_SOURCES, EDGE_CASES_DIR, country_fixture_path

from gapatlas.adapters.serpapi.errors import FixtureNotFoundError, SerpApiResponseError
from gapatlas.adapters.serpapi.fixture_client import (
    DEFAULT_FIXTURE_DIR,
    FIXTURE_FILE_NAMES,
    FixtureSerpApiClient,
    load_fixture,
)
from gapatlas.adapters.serpapi.protocol import SerpApiClient
from gapatlas.domain.models.common import Country, SourceName
from gapatlas.domain.models.query_profile import QueryProfile


def test_default_fixture_dir_points_at_backend_tests() -> None:
    assert DEFAULT_FIXTURE_DIR.is_dir()
    assert DEFAULT_FIXTURE_DIR.name == "serpapi"
    assert (DEFAULT_FIXTURE_DIR / "elder_care").is_dir()
    assert (DEFAULT_FIXTURE_DIR / "edge_cases").is_dir()


def test_file_name_mapping_covers_every_source() -> None:
    assert set(FIXTURE_FILE_NAMES) == set(SourceName)


@pytest.mark.parametrize("country", ALL_COUNTRIES, ids=lambda c: c.value)
@pytest.mark.parametrize("source", ALL_SOURCES, ids=lambda s: s.value)
def test_fetch_reads_every_country_and_source(
    profiles: dict[Country, QueryProfile], country: Country, source: SourceName
) -> None:
    client = FixtureSerpApiClient()
    raw = client.fetch(source, profiles[country])

    assert isinstance(raw, dict)
    assert raw["search_parameters"]["engine"].startswith("google")


@pytest.mark.parametrize("country", ALL_COUNTRIES, ids=lambda c: c.value)
@pytest.mark.parametrize("source", ALL_SOURCES, ids=lambda s: s.value)
def test_fixture_path_layout(
    profiles: dict[Country, QueryProfile], country: Country, source: SourceName
) -> None:
    """`<base_dir>/<topic_id>/<COUNTRY>/<file>.json` の配置になっていること。"""
    client = FixtureSerpApiClient()

    assert client.fixture_path(source, profiles[country]) == country_fixture_path(country, source)


def test_base_dir_can_be_injected(profiles: dict[Country, QueryProfile], tmp_path: Path) -> None:
    """デプロイ先で既定パスが解決できない場合に備えた注入点。"""
    target = tmp_path / "elder_care" / "JP"
    target.mkdir(parents=True)
    (target / "search.json").write_text('{"organic_results": []}', encoding="utf-8")

    client = FixtureSerpApiClient(base_dir=tmp_path)

    assert client.base_dir == tmp_path.resolve()
    assert client.fetch(SourceName.SEARCH, profiles[Country.JP]) == {"organic_results": []}


def test_missing_fixture_raises_not_found(
    profiles: dict[Country, QueryProfile], tmp_path: Path
) -> None:
    client = FixtureSerpApiClient(base_dir=tmp_path)

    with pytest.raises(FixtureNotFoundError):
        client.fetch(SourceName.NEWS, profiles[Country.US])


def test_broken_json_raises_response_error(
    profiles: dict[Country, QueryProfile], tmp_path: Path
) -> None:
    target = tmp_path / "elder_care" / "DE"
    target.mkdir(parents=True)
    (target / "news.json").write_text("{not json", encoding="utf-8")

    client = FixtureSerpApiClient(base_dir=tmp_path)

    with pytest.raises(SerpApiResponseError):
        client.fetch(SourceName.NEWS, profiles[Country.DE])


def test_non_object_json_raises_response_error(
    profiles: dict[Country, QueryProfile], tmp_path: Path
) -> None:
    target = tmp_path / "elder_care" / "GB"
    target.mkdir(parents=True)
    (target / "maps.json").write_text("[1, 2, 3]", encoding="utf-8")

    client = FixtureSerpApiClient(base_dir=tmp_path)

    with pytest.raises(SerpApiResponseError):
        client.fetch(SourceName.MAPS, profiles[Country.GB])


@pytest.mark.parametrize("name", ["error_401", "error_429"])
def test_error_payload_fixture_raises_response_error(name: str) -> None:
    """`{"error": ...}` 本文は HTTP ステータスと無関係に例外にする。"""
    with pytest.raises(SerpApiResponseError):
        load_fixture(EDGE_CASES_DIR / f"{name}.json")


def test_error_payload_fixture_can_be_served_by_the_client(
    profiles: dict[Country, QueryProfile], tmp_path: Path
) -> None:
    """`edge_cases/error_401.json` を読ませたときの挙動。"""
    target = tmp_path / "elder_care" / "IN"
    target.mkdir(parents=True)
    (target / "trends_timeseries.json").write_text(
        (EDGE_CASES_DIR / "error_401.json").read_text(encoding="utf-8"), encoding="utf-8"
    )

    client = FixtureSerpApiClient(base_dir=tmp_path)

    with pytest.raises(SerpApiResponseError):
        client.fetch(SourceName.TRENDS, profiles[Country.IN])


def test_fixture_client_satisfies_the_protocol() -> None:
    """`SerpApiClient` Protocol を構造的に満たすこと(mypy でも検証される)。"""
    client: SerpApiClient = FixtureSerpApiClient()

    assert callable(client.fetch)
