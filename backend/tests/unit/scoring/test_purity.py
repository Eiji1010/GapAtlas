"""`domain/scoring` が純粋関数のみであることをソースから検証する。

AGENTS.md / docs/scoring.md の絶対条件:
「ネットワーク、ファイルI/O、現在時刻の取得、乱数を持ち込まない。
現在時刻は引数で受け取る」。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from gapatlas.domain import scoring

FORBIDDEN_TOKENS = (
    "datetime.now",
    "time.time",
    "random",
    "open(",
    "requests",
    "httpx",
    "utcnow",
    "Path(",
)

EXPECTED_MODULES = frozenset(
    {
        "__init__.py",
        "constants.py",
        "rounding.py",
        "demand.py",
        "pain.py",
        "solution.py",
        "news.py",
        "need_gap.py",
        "confidence.py",
        "engine.py",
    }
)


def _scoring_dir() -> Path:
    package_file = scoring.__file__
    assert package_file is not None
    return Path(package_file).parent


def _source_files() -> list[Path]:
    return sorted(_scoring_dir().glob("*.py"))


def test_module_layout_is_as_specified():
    """統合担当と他トラックが前提にするファイル分割を固定する。"""
    assert {path.name for path in _source_files()} == EXPECTED_MODULES


def test_package_init_is_empty():
    """`__init__.py` は空ファイル(再エクスポートで循環依存を作らない)。"""
    assert (_scoring_dir() / "__init__.py").read_text(encoding="utf-8") == ""


@pytest.mark.parametrize("token", FORBIDDEN_TOKENS)
def test_no_io_time_or_randomness_in_sources(token):
    """I/O・現在時刻取得・乱数を示すトークンがソースに現れないこと。"""
    offenders = [path.name for path in _source_files() if token in path.read_text(encoding="utf-8")]
    assert offenders == [], f"{token!r} found in {offenders}"


def test_no_forbidden_imports():
    """禁止モジュールを import していないこと。"""
    forbidden_imports = ("import random", "import time", "import httpx", "import requests")
    for path in _source_files():
        source = path.read_text(encoding="utf-8")
        for statement in forbidden_imports:
            assert statement not in source, f"{statement!r} found in {path.name}"


def test_scan_time_is_received_as_an_argument():
    """現在時刻を扱う関数は `scan_time` を引数で受け取ること。"""
    for module_name in ("news.py", "need_gap.py", "confidence.py", "engine.py"):
        source = (_scoring_dir() / module_name).read_text(encoding="utf-8")
        assert "scan_time: datetime" in source, module_name
