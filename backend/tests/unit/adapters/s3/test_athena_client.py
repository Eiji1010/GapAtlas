"""Athena クライアントのテスト。

**実 AWS へは接続しない。** フェイククライアントを注入する
(認証情報が無く、`docs/decisions/0003-fixture-first.md` の方針)。
"""

from __future__ import annotations

from typing import Any

import pytest

from gapatlas.adapters.s3.athena import COUNTRY_SCORE_HISTORY_SQL
from gapatlas.adapters.s3.athena_client import (
    MAX_POLL_ATTEMPTS,
    AthenaScoreHistory,
    ScoreHistoryRow,
)
from gapatlas.adapters.s3.errors import ArchiveReadError
from gapatlas.config.settings import Settings
from gapatlas.domain.models.common import Country, TopicId

HEADER_ROW = {"Data": [{"VarCharValue": name} for name in ("dt", "scan_id", "s", "c", "st", "t")]}


def _row(dt: str, scan_id: str, score: str | None, confidence: str, status: str) -> dict[str, Any]:
    cells: list[dict[str, str]] = [{"VarCharValue": dt}, {"VarCharValue": scan_id}]
    # NULL は `VarCharValue` を持たないセルとして返る(Athena の仕様)。
    cells.append({} if score is None else {"VarCharValue": score})
    cells.extend(
        [
            {"VarCharValue": confidence},
            {"VarCharValue": status},
            {"VarCharValue": "2026-08-28 00:00:00.000"},
        ]
    )
    return {"Data": cells}


class FakeAthena:
    """`start` -> `get_query_execution` -> `get_query_results` を模す。"""

    def __init__(
        self,
        *,
        states: list[str] | None = None,
        pages: list[dict[str, Any]] | None = None,
        execution_id: str | None = "exec-1",
        start_error: Exception | None = None,
    ) -> None:
        self.states = states if states is not None else ["SUCCEEDED"]
        self.pages = pages if pages is not None else [{"ResultSet": {"Rows": [HEADER_ROW]}}]
        self.execution_id = execution_id
        self.start_error = start_error
        self.start_calls: list[dict[str, Any]] = []
        self.result_calls: list[dict[str, Any]] = []
        self.state_calls = 0

    def start_query_execution(self, **kwargs: Any) -> dict[str, Any]:
        self.start_calls.append(kwargs)
        if self.start_error is not None:
            raise self.start_error
        return {} if self.execution_id is None else {"QueryExecutionId": self.execution_id}

    def get_query_execution(self, **_kwargs: Any) -> dict[str, Any]:
        self.state_calls += 1
        state = self.states.pop(0) if len(self.states) > 1 else self.states[0]
        return {"QueryExecution": {"Status": {"State": state}}}

    def get_query_results(self, **kwargs: Any) -> dict[str, Any]:
        self.result_calls.append(kwargs)
        return self.pages[min(len(self.result_calls) - 1, len(self.pages) - 1)]


def _history(client: FakeAthena) -> AthenaScoreHistory:
    return AthenaScoreHistory(Settings(), client=client, sleep=lambda _seconds: None)


def test_the_query_uses_execution_parameters_not_string_interpolation():
    """外部入力を SQL へ連結しない(SQL インジェクション)。"""
    client = FakeAthena()
    _history(client).country_score_history(TopicId.ELDER_CARE, Country.JP)

    call = client.start_calls[0]
    assert call["QueryString"] == COUNTRY_SCORE_HISTORY_SQL
    assert call["ExecutionParameters"] == ["elder_care", "JP"]
    assert "JP" not in call["QueryString"]


def test_rows_are_mapped_in_select_order():
    pages = [
        {
            "ResultSet": {
                "Rows": [
                    HEADER_ROW,
                    _row("2026-08-27", "scan_a", "70", "88", "completed"),
                    _row("2026-08-28", "scan_b", "75", "91", "completed"),
                ]
            }
        }
    ]
    rows = _history(FakeAthena(pages=pages)).country_score_history(TopicId.ELDER_CARE, Country.JP)

    assert rows == [
        ScoreHistoryRow(
            dt="2026-08-27",
            scan_id="scan_a",
            need_gap_score=70,
            confidence=88,
            status="completed",
            computed_at="2026-08-28 00:00:00.000",
        ),
        ScoreHistoryRow(
            dt="2026-08-28",
            scan_id="scan_b",
            need_gap_score=75,
            confidence=91,
            status="completed",
            computed_at="2026-08-28 00:00:00.000",
        ),
    ]


def test_a_null_score_is_kept_as_none():
    """`INSUFFICIENT_EVIDENCE` の日も履歴に残す。

    行ごと落とすと「欠測」と「スコアを出せなかった」が区別できなくなる。
    """
    pages = [
        {
            "ResultSet": {
                "Rows": [
                    HEADER_ROW,
                    _row("2026-08-28", "scan_a", None, "64", "insufficient_evidence"),
                ]
            }
        }
    ]
    rows = _history(FakeAthena(pages=pages)).country_score_history(TopicId.ELDER_CARE, Country.JP)
    assert rows[0].need_gap_score is None
    assert rows[0].status == "insufficient_evidence"


def test_pagination_is_followed():
    pages = [
        {
            "ResultSet": {"Rows": [HEADER_ROW, _row("2026-08-27", "a", "70", "88", "completed")]},
            "NextToken": "t1",
        },
        {"ResultSet": {"Rows": [_row("2026-08-28", "b", "75", "91", "completed")]}},
    ]
    rows = _history(FakeAthena(pages=pages)).country_score_history(TopicId.ELDER_CARE, Country.JP)
    assert [row.scan_id for row in rows] == ["a", "b"]


def test_it_waits_until_the_query_succeeds():
    client = FakeAthena(states=["QUEUED", "RUNNING", "SUCCEEDED"])
    _history(client).country_score_history(TopicId.ELDER_CARE, Country.JP)
    assert client.result_calls


@pytest.mark.parametrize("state", ["FAILED", "CANCELLED"])
def test_a_terminal_failure_becomes_a_read_error(state):
    client = FakeAthena(states=[state])
    with pytest.raises(ArchiveReadError, match=state):
        _history(client).country_score_history(TopicId.ELDER_CARE, Country.JP)


def test_it_gives_up_instead_of_waiting_forever():
    """上限を外すと**ハングではなく失敗**として現れること。

    既定の上限に依存すると、上限を外す改変でテストが無限ループし、CI が
    タイムアウトするまで原因が分からない。**呼び出し回数を数える。**
    """
    client = FakeAthena(states=["RUNNING"])
    history = AthenaScoreHistory(
        Settings(), client=client, sleep=lambda _seconds: None, max_poll_attempts=3
    )
    with pytest.raises(ArchiveReadError, match="did not finish"):
        history.country_score_history(TopicId.ELDER_CARE, Country.JP)

    assert client.state_calls == 3


def test_the_default_poll_budget_is_bounded():
    """既定の上限もリテラルで固定する(0.5秒 x 60 = 30秒)。"""
    assert MAX_POLL_ATTEMPTS == 60


def test_a_missing_execution_id_is_an_error():
    with pytest.raises(ArchiveReadError, match="QueryExecutionId"):
        _history(FakeAthena(execution_id=None)).country_score_history(
            TopicId.ELDER_CARE, Country.JP
        )


def test_an_api_failure_becomes_a_read_error_without_leaking_the_message():
    detail = "arn:aws:athena:internal-detail"
    client = FakeAthena(start_error=RuntimeError(detail))
    with pytest.raises(ArchiveReadError) as excinfo:
        _history(client).country_score_history(TopicId.ELDER_CARE, Country.JP)
    assert detail not in str(excinfo.value)


def test_a_programming_error_is_not_hidden_as_a_service_failure():
    """実装バグを「Athena の障害」に見せない。"""
    client = FakeAthena(start_error=TypeError("bad arguments"))
    with pytest.raises(TypeError):
        _history(client).country_score_history(TopicId.ELDER_CARE, Country.JP)


def test_the_first_data_row_is_not_dropped_when_the_first_page_is_empty():
    """1ページ目が空でも、2ページ目の先頭をヘッダとして捨てないこと。"""
    pages = [
        {"ResultSet": {"Rows": []}, "NextToken": "t1"},
        {
            "ResultSet": {
                "Rows": [
                    _row("2026-08-27", "a", "70", "88", "completed"),
                    _row("2026-08-28", "b", "75", "91", "completed"),
                ]
            }
        },
    ]
    rows = _history(FakeAthena(pages=pages)).country_score_history(TopicId.ELDER_CARE, Country.JP)
    assert [row.scan_id for row in rows] == ["a", "b"]


def test_the_workgroup_comes_from_the_settings():
    """Terraform が作る名前と食い違うと WorkGroup not found で必ず失敗する。"""
    client = FakeAthena()
    history = AthenaScoreHistory(
        Settings(athena_workgroup="gapatlas-dev"), client=client, sleep=lambda _s: None
    )
    history.country_score_history(TopicId.ELDER_CARE, Country.JP)
    assert client.start_calls[0]["WorkGroup"] == "gapatlas-dev"
