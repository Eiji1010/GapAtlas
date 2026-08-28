"""S3 への書き出し Protocol。

`raw/` は SerpApi のレスポンスを **JSON のまま**保存する
(docs/architecture.md「S3 Data Lake」)。`normalized/` と `curated/` は
正規化済み・算出済みの内容を保存し、Glue → Athena で履歴分析に使う。

**Athena を Web のリアルタイム表示に使わない。** UI が読むのは DynamoDB。
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Any, Protocol

from gapatlas.domain.models.common import Country, SourceName, TopicId
from gapatlas.domain.models.normalized import NormalizedEvidence
from gapatlas.domain.models.result import CountryResult


class ScanArchive(Protocol):
    """スキャンの成果物を保存する。戻り値は保存先のオブジェクトキー。

    **書き込みの失敗でスキャンを止めない。** 呼び出し側は例外を捕捉して
    ログへ残し、スコアの算出と返却は続ける(docs/requirements.md「Reliability」)。
    """

    def put_raw(
        self,
        *,
        source: SourceName,
        topic_id: TopicId,
        country: Country,
        scan_time: datetime,
        scan_id: str,
        payload: Mapping[str, Any],
    ) -> str:
        """SerpApi の生レスポンスを無加工で保存する。"""
        ...

    def put_normalized(
        self,
        *,
        topic_id: TopicId,
        country: Country,
        scan_time: datetime,
        scan_id: str,
        evidence: NormalizedEvidence,
    ) -> str:
        """正規化済み証拠データを保存する。"""
        ...

    def put_curated(
        self,
        *,
        topic_id: TopicId,
        country: Country,
        scan_time: datetime,
        scan_id: str,
        result: CountryResult,
    ) -> str:
        """スコアを保存する。Athena の分析対象。"""
        ...
