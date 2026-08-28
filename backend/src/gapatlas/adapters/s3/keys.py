"""S3 のオブジェクトキー。

配置は docs/architecture.md「S3 Data Lake」の正本に従う。Glue のパーティション
射影(Phase 12)がこの形に依存するため、**変更するときは Glue のテーブル定義と
Athena のクエリも同時に直すこと。**

```text
raw/source=trends/topic=elder_care/country=JP/dt=2026-08-28/{scan_id}.json
normalized/topic=elder_care/country=JP/dt=2026-08-28/{scan_id}.json
curated/gap_scores/topic=elder_care/country=JP/dt=2026-08-28/{scan_id}.json
```

パーティションキーは `topic` / `country` / `dt`。`raw/` はさらに `source` で
分ける(ソース単位で再取得・再処理できるようにするため)。
"""

from __future__ import annotations

from datetime import datetime
from typing import Final

from gapatlas.domain.models.common import Country, SourceName, TopicId

RAW_PREFIX: Final[str] = "raw"
NORMALIZED_PREFIX: Final[str] = "normalized"
CURATED_PREFIX: Final[str] = "curated"
CURATED_DATASET: Final[str] = "gap_scores"

DATE_FORMAT: Final[str] = "%Y-%m-%d"
"""`dt` パーティションの形式。**UTC の日付**を使う。"""


def partition_date(scan_time: datetime) -> str:
    """`dt` パーティションの値。`scan_time` は UTC aware であること。"""
    return scan_time.strftime(DATE_FORMAT)


def raw_key(
    *,
    source: SourceName,
    topic_id: TopicId,
    country: Country,
    scan_time: datetime,
    scan_id: str,
) -> str:
    """SerpApi の生レスポンスの保存先。"""
    return (
        f"{RAW_PREFIX}/source={source.value}/topic={topic_id.value}"
        f"/country={country.value}/dt={partition_date(scan_time)}/{scan_id}.json"
    )


def normalized_key(
    *, topic_id: TopicId, country: Country, scan_time: datetime, scan_id: str
) -> str:
    """正規化済み証拠データの保存先。"""
    return (
        f"{NORMALIZED_PREFIX}/topic={topic_id.value}/country={country.value}"
        f"/dt={partition_date(scan_time)}/{scan_id}.json"
    )


def curated_key(*, topic_id: TopicId, country: Country, scan_time: datetime, scan_id: str) -> str:
    """スコア(履歴分析用)の保存先。Athena が読むのはここ。"""
    return (
        f"{CURATED_PREFIX}/{CURATED_DATASET}/topic={topic_id.value}"
        f"/country={country.value}/dt={partition_date(scan_time)}/{scan_id}.json"
    )
