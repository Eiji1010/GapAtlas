"""CLI のテスト。

`make scan COUNTRY=JP` が依頼書 §31 の出力形を返すことが最重要。
**結果は標準出力へ JSON、ログは標準エラーへ**という分離も固定する。
"""

from __future__ import annotations

import json
import logging

import pytest

from gapatlas.cli import EXIT_ERROR, EXIT_OK, main

BASE_ARGS = [
    "scan",
    "--topic",
    "elder_care",
    "--mode",
    "fixture",
    "--llm-mode",
    "stub",
    "--scan-time",
    "2026-08-28T00:00:00Z",
    "--scan-id",
    "scan_cli_test",
]

REQUIRED_KEYS = {
    "country",
    "topic",
    "demand",
    "pain",
    "solution_gap",
    "need_gap_score",
    "confidence",
}
"""依頼書 §31 が求めるキー。"""


@pytest.fixture(autouse=True)
def _restore_logging():
    """CLI が root ロガーを差し替えるため、テスト後に元へ戻す。"""
    root = logging.getLogger()
    handlers = list(root.handlers)
    level = root.level
    yield
    for handler in list(root.handlers):
        root.removeHandler(handler)
    for handler in handlers:
        root.addHandler(handler)
    root.setLevel(level)


def _run(capsys, *extra):
    exit_code = main([*BASE_ARGS, *extra])
    captured = capsys.readouterr()
    return exit_code, captured


def test_single_country_scan_matches_the_required_shape(capsys):
    exit_code, captured = _run(capsys, "--country", "JP")
    assert exit_code == EXIT_OK
    payload = json.loads(captured.out)
    assert set(payload) >= REQUIRED_KEYS
    assert payload["country"] == "JP"
    assert payload["topic"] == "elder_care"
    assert payload["status"] == "completed"
    assert 0 <= payload["need_gap_score"] <= 100
    assert 0 <= payload["confidence"] <= 100


def test_country_defaults_to_jp(capsys):
    _, captured = _run(capsys)
    assert json.loads(captured.out)["country"] == "JP"


@pytest.mark.parametrize("country", ["JP", "US", "GB", "DE", "IN"])
def test_every_country_can_be_scanned(capsys, country):
    exit_code, captured = _run(capsys, "--country", country)
    assert exit_code == EXIT_OK
    assert json.loads(captured.out)["country"] == country


def test_logs_go_to_stderr_and_results_to_stdout(capsys):
    _, captured = _run(capsys, "--country", "JP")
    json.loads(captured.out)  # 標準出力は JSON だけ
    log_lines = [line for line in captured.err.strip().splitlines() if line]
    assert log_lines
    for line in log_lines:
        payload = json.loads(line)
        assert {"scan_id", "topic", "country", "source"} <= set(payload)


def test_all_countries_produces_a_ranking(capsys):
    exit_code, captured = _run(capsys, "--all")
    assert exit_code == EXIT_OK
    payload = json.loads(captured.out)
    assert len(payload["ranking"]) == 5
    scores = [entry["need_gap_score"] for entry in payload["ranking"]]
    assert scores == sorted(scores, key=lambda value: -1 if value is None else -value)
    assert payload["opportunity_brief"] is not None


def test_full_output_contains_the_complete_result(capsys):
    _, captured = _run(capsys, "--country", "JP", "--full")
    payload = json.loads(captured.out)
    assert "summary" in payload
    country = payload["countries"]["JP"]
    assert country["versions"]["score_version"] == "gapatlas-score-v1"
    assert country["confidence_breakdown"]["data_completeness"] == 100.0
    assert country["evidence"][0]["id"] == "E1"


def test_output_is_deterministic(capsys):
    _, first = _run(capsys, "--country", "JP")
    _, second = _run(capsys, "--country", "JP")
    assert first.out == second.out


def test_an_unknown_country_is_rejected():
    with pytest.raises(SystemExit):
        main([*BASE_ARGS, "--country", "FR"])


def test_country_and_all_are_mutually_exclusive():
    with pytest.raises(SystemExit):
        main([*BASE_ARGS, "--country", "JP", "--all"])


def test_live_mode_without_a_key_fails_cleanly(capsys, monkeypatch):
    """API キーが無い live モードは例外で落ちず、エラー JSON を返す。"""
    monkeypatch.delenv("SERPAPI_API_KEY", raising=False)
    exit_code = main([*BASE_ARGS, "--country", "JP", "--mode", "live"])
    captured = capsys.readouterr()
    assert exit_code == EXIT_ERROR
    assert "error" in json.loads(captured.err.strip().splitlines()[-1])


def test_the_api_key_never_appears_in_the_output(capsys, monkeypatch):
    monkeypatch.setenv("SERPAPI_API_KEY", "cli-test-key-do-not-log")
    _, captured = _run(capsys, "--country", "JP")
    assert "cli-test-key-do-not-log" not in captured.out
    assert "cli-test-key-do-not-log" not in captured.err


# --------------------------------------------------------------------------
# 第三者レビューの指摘(不正入力で JSON エラー契約を破らないこと)
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "value", ["not-a-date", "2026-13-01", "", "2026-08-28T99:00:00Z"], ids=lambda v: v or "empty"
)
def test_an_invalid_scan_time_returns_an_error_json(capsys, value):
    """生のトレースバックを出さず `{"error": ...}` を返すこと。"""
    exit_code = main([*BASE_ARGS[:-4], "--country", "JP", "--scan-time", value])
    captured = capsys.readouterr()
    assert exit_code == EXIT_ERROR
    assert captured.out == ""
    payload = json.loads(captured.err.strip().splitlines()[-1])
    assert "scan-time" in payload["error"]


@pytest.mark.parametrize("value", ["../../etc/passwd", "scan id", "a" * 65, "scan/1"])
def test_an_invalid_scan_id_returns_an_error_json(capsys, value):
    """scan_id は Phase 7 でストレージキーになるため、任意文字列を通さない。"""
    exit_code = main([*BASE_ARGS[:-2], "--country", "JP", "--scan-id", value])
    captured = capsys.readouterr()
    assert exit_code == EXIT_ERROR
    assert "scan-id" in json.loads(captured.err.strip().splitlines()[-1])["error"]


def test_an_invalid_log_level_returns_an_error_json(capsys, monkeypatch):
    """ログ設定の最中に落ちると原因が構造化ログにも残らない。"""
    monkeypatch.setenv("LOG_LEVEL", "verbose")
    exit_code = main([*BASE_ARGS, "--country", "JP"])
    captured = capsys.readouterr()
    assert exit_code == EXIT_ERROR
    assert "LOG_LEVEL" in json.loads(captured.err.strip().splitlines()[-1])["error"]


def test_a_generated_scan_id_is_used_when_omitted(capsys):
    exit_code = main([*BASE_ARGS[:-2], "--country", "JP", "--full"])
    captured = capsys.readouterr()
    assert exit_code == EXIT_OK
    assert json.loads(captured.out)["summary"]["scan_id"].startswith("scan_")


def test_a_single_country_summary_does_not_trigger_maps_or_brief(capsys):
    """表示しない Maps と Brief のために外部 API を呼ばない。"""
    _, captured = _run(capsys, "--country", "JP")
    sources = {json.loads(line).get("source") for line in captured.err.strip().splitlines() if line}
    assert "maps" not in sources


def test_full_output_includes_maps_and_brief(capsys):
    _, captured = _run(capsys, "--country", "JP", "--full")
    payload = json.loads(captured.out)
    assert payload["summary"]["opportunity_brief"] is not None
    assert payload["countries"]["JP"]["source_status"]["maps"] == "ok"


def test_expected_scores_are_stable(capsys):
    """CLI 出力の期待値を固定する。"""
    _, captured = _run(capsys, "--all")
    ranking = {
        entry["country"]: (entry["need_gap_score"], entry["confidence"])
        for entry in json.loads(captured.out)["ranking"]
    }
    assert ranking == {
        "JP": (75, 91),
        "DE": (67, 90),
        "IN": (66, 92),
        "GB": (58, 90),
        "US": (55, 90),
    }
