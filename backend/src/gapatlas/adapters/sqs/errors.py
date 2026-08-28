"""ジョブキューの例外。"""

from __future__ import annotations

from gapatlas.domain.models.errors import GapAtlasError


class JobQueueError(GapAtlasError):
    """ジョブキューの例外の基底。"""


class JobEnqueueError(JobQueueError):
    """メッセージの送信に失敗した場合。"""


class JobDecodeError(JobQueueError):
    """メッセージ本文を `ScanJob` へ復元できない場合。

    壊れたメッセージをリトライし続けても直らないため、呼び出し側は
    **リトライせずに捨てる**(DLQ へ送る)判断をしてよい。
    """
