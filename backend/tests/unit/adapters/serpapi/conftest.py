"""SerpApi アダプタのテストで共有する fixture。

テストは決定的であること(現在時刻・乱数・ネットワークに依存しない)。
fixture の基準日は 2026-08-28T00:00:00Z(backend/tests/fixtures/README.md)。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from gapatlas.config.query_profile_loader import load_all_query_profiles
from gapatlas.domain.models.common import Country, SourceName, TopicId
from gapatlas.domain.models.query_profile import QueryProfile

# conftest.py = <repo>/backend/tests/unit/adapters/serpapi/conftest.py
#   parents[0] = .../tests/unit/adapters/serpapi
#   parents[1] = .../tests/unit/adapters
#   parents[2] = .../tests/unit
#   parents[3] = .../tests          <- backend/tests
FIXTURE_ROOT = Path(__file__).resolve().parents[3] / "fixtures" / "serpapi"
EDGE_CASES_DIR = FIXTURE_ROOT / "edge_cases"

ALL_SOURCES: tuple[SourceName, ...] = tuple(SourceName)
ALL_COUNTRIES: tuple[Country, ...] = tuple(Country)

SOURCE_FIXTURE_NAMES: dict[SourceName, str] = {
    SourceName.TRENDS: "trends_timeseries.json",
    SourceName.RELATED_QUERIES: "trends_related_queries.json",
    SourceName.SEARCH: "search.json",
    SourceName.NEWS: "news.json",
    SourceName.MAPS: "maps.json",
}


def read_json(path: Path) -> dict[str, Any]:
    """テスト側から fixture を素朴に読む(実装コードを介さない)。"""
    loaded = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict)
    return loaded


def read_edge_case(name: str) -> dict[str, Any]:
    """`edge_cases/<name>.json` を読む。"""
    return read_json(EDGE_CASES_DIR / f"{name}.json")


def country_fixture_path(country: Country, source: SourceName) -> Path:
    return FIXTURE_ROOT / TopicId.ELDER_CARE.value / country.value / SOURCE_FIXTURE_NAMES[source]


@pytest.fixture(scope="session")
def profiles() -> dict[Country, QueryProfile]:
    """実際の `config/query_profiles/elder_care/*.yaml` 5件。"""
    return load_all_query_profiles(TopicId.ELDER_CARE)
