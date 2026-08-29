"""非同期処理のジョブ契約。

`POST /scans` は即座に `scan_id` を返し、重い SerpApi 処理は Worker で行う
(docs/requirements.md「重い SerpApi 処理を HTTP Request 内で実行してはいけない」)。
API と Worker は**このモデルだけ**で会話する。

```text
POST /scans -> SCAN META を作成 -> 国ごとに ScanJob を SQS へ投入
            -> Lambda Worker が 1メッセージ 1国 を処理
```

**1メッセージ1国**にするのは、1国の失敗が他国を巻き込まないようにするため
(docs/architecture.md「非同期処理」)。`maxReceiveCount = 3` を超えたメッセージ
は DLQ へ落ちる。

`scan_time` をジョブへ含めるのは、**同じスキャンの全国で同じ基準時刻を使う**
ため。Worker ごとに現在時刻を取ると、Freshness と News Urgency が国によって
わずかに変わり、結果が再現できなくなる。
"""

from __future__ import annotations

from typing import Final

from pydantic import BaseModel, Field

from gapatlas.domain.models.common import MODEL_CONFIG, Country, TopicId, UtcDatetime

SCAN_ID_PATTERN: Final[str] = r"^[A-Za-z0-9_-]{1,64}$"
"""`scan_id` に許す形。

DynamoDB のパーティションキーと S3 のオブジェクトキーになるため、パス区切りを
含む任意文字列を通さない。API の読み取り経路(`api/handlers.py`)だけで検証
していると、書き込み経路(SQS -> Worker -> S3 / DynamoDB)が素通しになる。
"""


class ScanJob(BaseModel):
    """1国分のスキャン指示。SQS メッセージの本文になる。"""

    model_config = MODEL_CONFIG

    scan_id: str = Field(pattern=SCAN_ID_PATTERN)
    topic_id: TopicId
    country: Country
    scan_time: UtcDatetime
    """スキャン全体で共有する基準時刻。Worker はこれを使い、現在時刻を取らない。"""

    countries: list[Country] = Field(min_length=1)
    """このスキャンの対象国すべて。

    Worker が「自分が最後の1国か」を判定し、最後の国がランキング確定・
    Top2 Maps・Top1 Brief・概要の保存を行うために必要。
    """
