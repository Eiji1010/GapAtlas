"""Lambda の SQS イベントから `ScanJob` を復元する。

受信は Lambda のイベントとして届くため `JobQueue` Protocol には含めない
(`protocol.py`)。復元だけをこのモジュールが担当する。

Lambda が Worker へ渡すイベントの形:

```json
{"Records": [{"messageId": "...", "body": "{...ScanJob の JSON...}"}]}
```

**壊れた本文は `JobDecodeError`。** リトライしても直らないため、呼び出し側は
リトライせずに捨てる(DLQ へ送る)判断をしてよい(`errors.py`)。逆に、
例外を投げずに読み飛ばすと「処理できたことにして」黙って国が欠ける。
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Final

from pydantic import ValidationError

from gapatlas.adapters.sqs.errors import JobDecodeError
from gapatlas.application.jobs import ScanJob

RECORDS_KEY: Final[str] = "Records"
"""Lambda の SQS イベントで、メッセージの配列が入るキー。"""

MESSAGE_ID_KEY: Final[str] = "messageId"
BODY_KEY: Final[str] = "body"


def decode_job(body: str) -> ScanJob:
    """SQS メッセージ本文を `ScanJob` へ復元する。

    未知フィールドを含む本文も拒否する(`ScanJob` は `extra="forbid"`)。
    API と Worker の契約がずれたまま動き続けるより、DLQ で気付くほうがよい。

    Raises:
        JobDecodeError: JSON として壊れている、または `ScanJob` の制約を
            満たさない場合。

    **例外メッセージへ本文を載せない**(docs/architecture.md「Security」)。
    載せるのは不正だったフィールドの位置だけにする。
    """
    try:
        return ScanJob.model_validate_json(body)
    except ValidationError as exc:
        raise JobDecodeError(_validation_message(exc)) from exc


def decode_records(event: Mapping[str, Any]) -> list[tuple[str, ScanJob]]:
    """Lambda の SQS イベントを `(messageId, ScanJob)` の並びへ復元する。

    **`Records` が無い / 配列でない場合は `JobDecodeError` にする。** 空リストを
    返すと「メッセージが 0 件だった」と区別が付かず、トリガの誤配線
    (SQS 以外のイベントソースが繋がっている、テストイベントを流した)が
    成功として記録されてしまう。復元できない入力は必ず可視化する。

    `Records` が空配列の場合だけは `[]` を返す。SQS が空のバッチを渡すことは
    ないが、形として正しい入力を例外にはしない。

    **1件でも壊れていればバッチ全体を `JobDecodeError` にする。** MVP は
    `batchSize = 1` を前提とする(1メッセージ1国、`jobs.py`)ため、実際に
    巻き込まれる正常なメッセージは無い。戻り値は部分的な成功を表現できない
    ので、壊れた1件を黙って読み飛ばすほうが危険だと判断した。バッチサイズを
    増やす場合は `ReportBatchItemFailures` を有効にしたうえで、呼び出し側が
    record ごとに `decode_job` を呼ぶこと。

    Raises:
        JobDecodeError: イベントの形が想定と違う、またはいずれかの本文を
            復元できない場合。
    """
    records = event.get(RECORDS_KEY)
    if records is None:
        message = f"the event has no '{RECORDS_KEY}' key; it does not look like an SQS event"
        raise JobDecodeError(message)
    if not isinstance(records, list):
        message = (
            f"the event's '{RECORDS_KEY}' must be a list "
            f"(got {type(records).__name__}); it does not look like an SQS event"
        )
        raise JobDecodeError(message)

    return [_decode_record(index, record) for index, record in enumerate(records)]


# --- 内部 -----------------------------------------------------------------------------------


def _decode_record(index: int, record: Any) -> tuple[str, ScanJob]:
    if not isinstance(record, Mapping):
        message = f"record {index} must be an object (got {type(record).__name__})"
        raise JobDecodeError(message)

    message_id = record.get(MESSAGE_ID_KEY)
    if not isinstance(message_id, str) or not message_id:
        message = f"record {index} has no usable '{MESSAGE_ID_KEY}'"
        raise JobDecodeError(message)

    body = record.get(BODY_KEY)
    if not isinstance(body, str):
        message = f"record '{message_id}' has no string '{BODY_KEY}' (got {type(body).__name__})"
        raise JobDecodeError(message)

    try:
        return message_id, decode_job(body)
    except JobDecodeError as exc:
        # `messageId` は SQS が採番した識別子であり、本文を含まない。
        # どのメッセージを捨てたのかログから辿れるようにする。
        message = f"record '{message_id}' could not be decoded: {exc}"
        raise JobDecodeError(message) from exc


def _validation_message(exc: ValidationError) -> str:
    """`ValidationError` の要約。**値そのものは載せない。**

    `pydantic` のメッセージには入力値が混ざりうるため、フィールドの位置だけを
    使う(`config/settings.py` の方針をさらに厳しくしたもの)。
    """
    locations = sorted(
        {".".join(str(part) for part in error["loc"]) or "(body)" for error in exc.errors()}
    )
    return (
        f"the SQS message body could not be decoded into a ScanJob: "
        f"{exc.error_count()} validation error(s) at {', '.join(locations)}"
    )
