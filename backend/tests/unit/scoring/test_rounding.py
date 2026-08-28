"""`round_half_up` / `clip` のテスト。docs/scoring.md 記法。"""

from __future__ import annotations

import pytest

from gapatlas.domain.scoring.rounding import clip, round_half_up


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (0.5, 1),
        (1.5, 2),
        (2.5, 3),
        (3.5, 4),
        (4.5, 5),
    ],
)
def test_half_values_round_up_not_to_even(value, expected):
    """0.5 は必ず切り上げる。Python 標準の `round()` は偶数丸めなので使わない。"""
    assert round_half_up(value) == expected


def test_builtin_round_would_disagree():
    """偶数丸めとの差を明示する(実装が `round()` に戻ったら落ちる)。"""
    assert round(2.5) == 2
    assert round_half_up(2.5) == 3


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (0.0, 0),
        (0.4999, 0),
        (0.5001, 1),
        (49.4, 49),
        (49.5, 50),
        (99.5, 100),
        (100.0, 100),
    ],
)
def test_round_half_up_basic(value, expected):
    assert round_half_up(value) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (-0.5, -1),
        (-2.5, -3),
        (-1.4, -1),
    ],
)
def test_round_half_up_negative_rounds_away_from_zero(value, expected):
    """負値は本仕様では発生しないが、定義は 0 から遠い側へ丸める。"""
    assert round_half_up(value) == expected


def test_round_half_up_returns_int():
    assert isinstance(round_half_up(1.2), int)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (-1.0, 0.0),
        (0.0, 0.0),
        (50.0, 50.0),
        (100.0, 100.0),
        (101.0, 100.0),
    ],
)
def test_clip(value, expected):
    assert clip(value, 0.0, 100.0) == expected
