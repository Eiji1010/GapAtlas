"""インメモリの `ScanArchive`。

AWS へ接続せずに全機能を動かすための実装(AGENTS.md「fixture mode を常に維持
する」)。保存内容はキーと JSON 文字列の辞書として持つ。
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import datetime
from typing import Any

from gapatlas.adapters.s3.keys import curated_key, normalized_key, raw_key
from gapatlas.domain.models.common import Country, SourceName, TopicId
from gapatlas.domain.models.normalized import NormalizedEvidence
from gapatlas.domain.models.result import CountryResult


class InMemoryScanArchive:
    """辞書に保持するだけの `ScanArchive`。"""

    def __init__(self) -> None:
        self.objects: dict[str, str] = {}

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
        key = raw_key(
            source=source,
            topic_id=topic_id,
            country=country,
            scan_time=scan_time,
            scan_id=scan_id,
        )
        # raw は無加工で保存する(docs/architecture.md)。
        self.objects[key] = json.dumps(dict(payload), ensure_ascii=False)
        return key

    def put_normalized(
        self,
        *,
        topic_id: TopicId,
        country: Country,
        scan_time: datetime,
        scan_id: str,
        evidence: NormalizedEvidence,
    ) -> str:
        key = normalized_key(
            topic_id=topic_id, country=country, scan_time=scan_time, scan_id=scan_id
        )
        self.objects[key] = evidence.model_dump_json()
        return key

    def put_curated(
        self,
        *,
        topic_id: TopicId,
        country: Country,
        scan_time: datetime,
        scan_id: str,
        result: CountryResult,
    ) -> str:
        key = curated_key(topic_id=topic_id, country=country, scan_time=scan_time, scan_id=scan_id)
        self.objects[key] = result.model_dump_json()
        return key
