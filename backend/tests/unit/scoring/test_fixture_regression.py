"""fixture を使った回帰テスト。

`backend/tests/fixtures/README.md` の「各国の Trends の性質」表にある
`demand(median)` と `値が 0 の割合` を、実際の fixture JSON から再現する。

fixture の読み込みはテスト側で行う(`domain/scoring` に I/O を入れない)。
`scan_time` は fixture の基準日 `2026-08-28T00:00:00Z` を明示的に渡す。
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from conftest import SCAN_TIME

from gapatlas.domain.models.normalized import TrendPoint, TrendsSeries, TrendsTimeseries
from gapatlas.domain.scoring.constants import ZERO_RATIO_THRESHOLD
from gapatlas.domain.scoring.demand import compute_demand

FIXTURES_DIR = Path(__file__).resolve().parents[2] / "fixtures" / "serpapi"

# backend/tests/fixtures/README.md「各国の Trends の性質」表
EXPECTED_DEMAND_MEDIAN = {
    "JP": 84.6,
    "DE": 78.1,
    "IN": 68.1,
    "US": 54.5,
    "GB": 43.4,
}
EXPECTED_ZERO_RATIO_PERCENT = {
    "JP": 0.0,
    "DE": 0.0,
    "IN": 37.2,
    "US": 0.0,
    "GB": 0.0,
}


def _load(relative_path: str) -> dict:
    return json.loads((FIXTURES_DIR / relative_path).read_text(encoding="utf-8"))


def _timeseries_from_fixture(payload: dict) -> TrendsTimeseries:
    """SerpApi TIMESERIES の形から `TrendsTimeseries` を組み立てる。

    アダプタ相当の変換をテスト側で行う(トラック B の担当外のため最小限)。
    `values[]` は `query_index` 0..n-1 の順で各クエリの値を持つ。
    """
    timeline = payload["interest_over_time"]["timeline_data"]
    if not timeline:
        return TrendsTimeseries(series=[])

    queries = [value["query"] for value in timeline[0]["values"]]
    series = []
    for index, query in enumerate(queries):
        points = [
            TrendPoint(
                timestamp=datetime.fromtimestamp(int(entry["timestamp"]), tz=UTC),
                value=float(entry["values"][index]["extracted_value"]),
            )
            for entry in timeline
        ]
        series.append(TrendsSeries(query=query, points=points))
    return TrendsTimeseries(series=series)


def _country_timeseries(country: str) -> TrendsTimeseries:
    return _timeseries_from_fixture(_load(f"elder_care/{country}/trends_timeseries.json"))


def _zero_ratio_percent(trends: TrendsTimeseries) -> float:
    values = [point.value for series in trends.series for point in series.points]
    return 100.0 * sum(1 for value in values if value == 0.0) / len(values)


@pytest.mark.parametrize(("country", "expected"), sorted(EXPECTED_DEMAND_MEDIAN.items()))
def test_demand_matches_fixture_readme(country, expected):
    """README の `demand(median)` と小数第1位まで一致すること。"""
    demand = compute_demand(_country_timeseries(country))
    assert demand is not None
    assert round(demand, 1) == pytest.approx(expected)


@pytest.mark.parametrize(("country", "expected"), sorted(EXPECTED_ZERO_RATIO_PERCENT.items()))
def test_zero_ratio_matches_fixture_readme(country, expected):
    """README の「値が 0 の割合」と小数第1位まで一致すること。"""
    assert round(_zero_ratio_percent(_country_timeseries(country)), 1) == pytest.approx(expected)


def test_india_zero_ratio_does_not_trigger_hard_rule_4():
    """IN は 37.2% で Hard Rule 4(50% 以上)には達しない(README の意図)。"""
    ratio = _zero_ratio_percent(_country_timeseries("IN")) / 100.0
    assert ratio < ZERO_RATIO_THRESHOLD


def test_each_country_has_fifty_two_weekly_points_for_three_queries():
    """fixture の前提(週次 52 点 * 3 キーワード)を固定する。"""
    for country in EXPECTED_DEMAND_MEDIAN:
        trends = _country_timeseries(country)
        assert len(trends.series) == 3
        assert all(len(series.points) == 52 for series in trends.series)


def test_latest_timestamp_matches_the_reference_date():
    """最新週は基準日 `2026-08-28T00:00:00Z` を含む週(Aug 23, 2026 始まり)。"""
    trends = _country_timeseries("JP")
    latest = trends.series[0].latest_timestamp
    assert latest is not None
    assert latest == datetime(2026, 8, 23, tzinfo=UTC)
    assert latest < SCAN_TIME


def test_eleven_point_edge_case_fixture_is_not_computable():
    """`edge_cases/trends_timeseries_11_points.json` → `demand = None`。"""
    trends = _timeseries_from_fixture(_load("edge_cases/trends_timeseries_11_points.json"))
    assert all(len(series.points) == 11 for series in trends.series)
    assert compute_demand(trends) is None


def test_all_zero_edge_case_fixture_scores_fifty():
    """`edge_cases/trends_timeseries_all_zero.json` → `demand = 50`。"""
    trends = _timeseries_from_fixture(_load("edge_cases/trends_timeseries_all_zero.json"))
    assert compute_demand(trends) == pytest.approx(50.0)
    assert _zero_ratio_percent(trends) == pytest.approx(100.0)


def test_half_zero_edge_case_fixture_triggers_hard_rule_4():
    """`edge_cases/trends_timeseries_half_zero.json` → ゼロ率 50% 以上。"""
    trends = _timeseries_from_fixture(_load("edge_cases/trends_timeseries_half_zero.json"))
    assert _zero_ratio_percent(trends) / 100.0 >= ZERO_RATIO_THRESHOLD
    assert compute_demand(trends) is not None


def test_empty_edge_case_fixture_has_no_series():
    """`edge_cases/trends_timeseries_empty.json` → 系列なし → `demand = None`。"""
    trends = _timeseries_from_fixture(_load("edge_cases/trends_timeseries_empty.json"))
    assert trends.series == []
    assert compute_demand(trends) is None
