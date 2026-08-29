"""Athena で「国ごとの Need Gap Score 履歴」を取得するアダプタ。

`docs/architecture.md`「Athena」: **Web のリアルタイム表示には使わない。
履歴分析専用。** UI が読むのは DynamoDB であり、この経路は使わない。

Definition of Done「Athena で過去 Score 取得」に対応する。

**AWS 認証情報が無いため実 Athena との結合は未検証**(SerpApi live と同じ
状況。`docs/decisions/0003-fixture-first.md` の方針)。検証はフェイク
クライアントを注入した単体テストに留まる。

## クエリの実行モデル

Athena は非同期である。`StartQueryExecution` で開始し、`GetQueryExecution`
で状態を見て、`SUCCEEDED` になってから `GetQueryResults` を読む。ポーリング
間隔と上限を持たせ、**無限に待たない**。
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Final

from gapatlas.adapters.s3.athena import AthenaQuery, country_score_history_query
from gapatlas.adapters.s3.errors import ArchiveError, ArchiveReadError
from gapatlas.config.settings import Settings
from gapatlas.domain.models.common import Country, TopicId

_LOGGER: Final[logging.Logger] = logging.getLogger(__name__)

POLL_INTERVAL_SECONDS: Final[float] = 0.5
MAX_POLL_ATTEMPTS: Final[int] = 60
"""最大待ち時間 = 0.5秒 * 60 = 30秒。**無限には待たない。**"""

SUCCEEDED: Final[str] = "SUCCEEDED"
TERMINAL_STATES: Final[frozenset[str]] = frozenset({SUCCEEDED, "FAILED", "CANCELLED"})

_PROGRAMMING_ERRORS: Final[tuple[type[BaseException], ...]] = (
    AttributeError,
    TypeError,
    NameError,
    ImportError,
)
"""外部サービスの障害として扱ってはいけない例外(実装バグを隠さない)。"""


@dataclass(frozen=True, slots=True)
class ScoreHistoryRow:
    """履歴1行。`need_gap_score` は `None` になりうる。

    `INSUFFICIENT_EVIDENCE` / `FAILED` の日も履歴の一部として残す。行ごと
    落とすと「欠測」と「スコアを出せなかった」が区別できなくなる。
    """

    dt: str
    scan_id: str
    need_gap_score: int | None
    confidence: int | None
    status: str
    computed_at: str


def _build_default_client(*, region: str) -> Any:
    """`boto3` を遅延 import して Athena クライアントを作る。

    optional extra(`aws`)なので、未インストール環境で本モジュールの import
    自体が失敗しないようトップレベルでは import しない。
    """
    try:
        import boto3  # noqa: PLC0415
    except ImportError as exc:
        message = (
            "the 'boto3' package is not installed; install the 'aws' optional extra to query Athena"
        )
        raise ArchiveError(message) from exc
    return boto3.client("athena", region_name=region)


def _cell(row: Mapping[str, Any], index: int) -> str | None:
    """`GetQueryResults` の1セル。NULL は `Data` にキーが無い形で返る。"""
    data = row.get("Data")
    if not isinstance(data, Sequence) or index >= len(data):
        return None
    cell = data[index]
    if not isinstance(cell, Mapping):
        return None
    value = cell.get("VarCharValue")
    return value if isinstance(value, str) else None


def _optional_int(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        return None


class AthenaScoreHistory:
    """Athena から過去のスコアを読む。**書き込みは行わない。**"""

    def __init__(
        self,
        settings: Settings,
        *,
        client: Any | None = None,
        workgroup: str | None = None,
        sleep: Callable[[float], None] = time.sleep,
        max_poll_attempts: int = MAX_POLL_ATTEMPTS,
    ) -> None:
        """
        Args:
            client: 注入するクライアント。**テストは必ずフェイクを渡すこと**
                (実 AWS を呼ばない。認証情報は無い前提)。
            sleep: ポーリングの待機関数。テストが実時間を消費しないよう注入可能。
        """
        # **ワークグループ名は設定から取る。** ここに既定値を書くと
        # Terraform の名前(`${project}-${environment}`)と食い違い、
        # `WorkGroup not found` でクエリが必ず失敗する。
        self._workgroup = workgroup if workgroup is not None else settings.athena_workgroup
        self._sleep = sleep
        self._max_poll_attempts = max_poll_attempts
        self._client = (
            client if client is not None else _build_default_client(region=settings.aws_region)
        )

    def country_score_history(self, topic_id: TopicId, country: Country) -> list[ScoreHistoryRow]:
        """国ごとの Need Gap Score 履歴を古い順に返す。

        Raises:
            ArchiveReadError: クエリが失敗した、または待ち時間の上限に達した場合。
        """
        query = country_score_history_query(topic_id=topic_id, country=country)
        execution_id = self._start(query)
        self._wait(execution_id)
        return self._read(execution_id)

    # --- 内部 -------------------------------------------------------------------------

    def _start(self, query: AthenaQuery) -> str:
        try:
            response = self._client.start_query_execution(
                QueryString=query.sql,
                # **外部入力を SQL へ連結しない。** 実行時パラメータで渡す。
                ExecutionParameters=list(query.parameters),
                WorkGroup=self._workgroup,
            )
        except _PROGRAMMING_ERRORS:
            raise
        except Exception as exc:
            message = f"failed to start the Athena query ({type(exc).__name__})"
            raise ArchiveReadError(message) from exc

        execution_id = response.get("QueryExecutionId") if isinstance(response, Mapping) else None
        if not isinstance(execution_id, str) or not execution_id:
            message = "Athena did not return a QueryExecutionId"
            raise ArchiveReadError(message)
        return execution_id

    def _wait(self, execution_id: str) -> None:
        for _attempt in range(self._max_poll_attempts):
            state = self._state(execution_id)
            if state == SUCCEEDED:
                return
            if state in TERMINAL_STATES:
                # 失敗理由の本文は載せない(クエリ内容が混ざりうる)。
                message = f"the Athena query ended in state {state}"
                raise ArchiveReadError(message)
            self._sleep(POLL_INTERVAL_SECONDS)

        message = (
            f"the Athena query did not finish within {self._max_poll_attempts} polls; "
            "giving up instead of waiting forever"
        )
        raise ArchiveReadError(message)

    def _state(self, execution_id: str) -> str:
        try:
            response = self._client.get_query_execution(QueryExecutionId=execution_id)
        except _PROGRAMMING_ERRORS:
            raise
        except Exception as exc:
            message = f"failed to read the Athena query state ({type(exc).__name__})"
            raise ArchiveReadError(message) from exc

        execution = response.get("QueryExecution") if isinstance(response, Mapping) else None
        status = execution.get("Status") if isinstance(execution, Mapping) else None
        state = status.get("State") if isinstance(status, Mapping) else None
        return state if isinstance(state, str) else "UNKNOWN"

    def _read(self, execution_id: str) -> list[ScoreHistoryRow]:
        rows: list[ScoreHistoryRow] = []
        token: str | None = None
        first_page = True

        while True:
            arguments: dict[str, Any] = {"QueryExecutionId": execution_id}
            if token is not None:
                arguments["NextToken"] = token
            try:
                response = self._client.get_query_results(**arguments)
            except _PROGRAMMING_ERRORS:
                raise
            except Exception as exc:
                message = f"failed to read the Athena query results ({type(exc).__name__})"
                raise ArchiveReadError(message) from exc

            result_set = response.get("ResultSet") if isinstance(response, Mapping) else None
            raw_rows = result_set.get("Rows") if isinstance(result_set, Mapping) else None
            page = list(raw_rows) if isinstance(raw_rows, Sequence) else []
            if first_page:
                # 先頭ページの1行目は列名(Athena の仕様)。
                # **`page` が空でもフラグを倒すこと。** 空のまま残すと、
                # 次ページの先頭にある実データ行をヘッダとして捨てる。
                page = page[1:]
                first_page = False

            rows.extend(_to_row(row) for row in page if isinstance(row, Mapping))

            next_token = response.get("NextToken") if isinstance(response, Mapping) else None
            if not isinstance(next_token, str) or not next_token:
                break
            token = next_token

        _LOGGER.info("athena score history loaded", extra={"rows": len(rows)})
        return rows


def _to_row(row: Mapping[str, Any]) -> ScoreHistoryRow:
    """`COUNTRY_SCORE_HISTORY_SQL` の SELECT 順に合わせて1行を組み立てる。"""
    return ScoreHistoryRow(
        dt=_cell(row, 0) or "",
        scan_id=_cell(row, 1) or "",
        need_gap_score=_optional_int(_cell(row, 2)),
        confidence=_optional_int(_cell(row, 3)),
        status=_cell(row, 4) or "",
        computed_at=_cell(row, 5) or "",
    )
