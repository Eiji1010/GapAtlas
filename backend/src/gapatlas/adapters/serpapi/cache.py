"""SerpApi レスポンスのソース別キャッシュ。

正本は `docs/requirements.md`「Cache」と `docs/architecture.md`「Cache」。

| Source | TTL |
|---|---:|
| Trends | 6h |
| Related Queries | 6h |
| Search | 6h |
| News | 1h |
| Maps | 24h |

**Cache Hit の場合は SerpApi を再度呼ばない。**

キーには `query_profile_version` を含める(`docs/architecture.md`)。クエリを
変えたのに古い結果を返さないため。

## キャッシュ経過時間と Evidence Confidence

`docs/scoring.md` の Freshness は、`related_queries` と `search` の古さを
**キャッシュ経過時間**で測ります。キャッシュを入れずに 0 を返し続けると、
6時間前の結果でも「今取得した」ものとして扱われます。そのため
`cache_age_seconds()` で経過時間を取り出せるようにし、application 層が
`SourceFetch` へ載せます。

## 保存先

プロセス内メモリを既定とします。Lambda の実行環境をまたぐ共有キャッシュ
(DynamoDB など)は本 MVP の範囲外です。**キャッシュが効かなくても結果は
正しく、外部呼び出しが増えるだけ**という設計にしてあります。
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Final, Protocol

from gapatlas.adapters.serpapi.params import build_params
from gapatlas.adapters.serpapi.protocol import SerpApiClient
from gapatlas.domain.models.common import SourceName
from gapatlas.domain.models.query_profile import QueryProfile

HOUR_SECONDS: Final[float] = 3600.0

SOURCE_TTL_SECONDS: Final[Mapping[SourceName, float]] = {
    SourceName.TRENDS: 6 * HOUR_SECONDS,
    SourceName.RELATED_QUERIES: 6 * HOUR_SECONDS,
    SourceName.SEARCH: 6 * HOUR_SECONDS,
    SourceName.NEWS: 1 * HOUR_SECONDS,
    SourceName.MAPS: 24 * HOUR_SECONDS,
}
"""docs/requirements.md「Cache」の TTL。**変更したら同表も直すこと。**"""


def _utc_now() -> datetime:
    return datetime.now(tz=UTC)


@dataclass(frozen=True, slots=True)
class CacheEntry:
    """キャッシュ1件。`stored_at` は UTC aware。"""

    payload: dict[str, Any]
    stored_at: datetime


class CacheStore(Protocol):
    """キャッシュの保存先。プロセス内メモリ以外へ差し替えられるようにする。"""

    def get(self, key: str) -> CacheEntry | None: ...

    def put(self, key: str, entry: CacheEntry) -> None: ...


class InMemoryCacheStore:
    """辞書に保持するだけの `CacheStore`。"""

    def __init__(self) -> None:
        self._entries: dict[str, CacheEntry] = {}

    def get(self, key: str) -> CacheEntry | None:
        return self._entries.get(key)

    def put(self, key: str, entry: CacheEntry) -> None:
        self._entries[key] = entry


def build_cache_key(source: SourceName, profile: QueryProfile) -> str:
    """ソースと実際のリクエストパラメータから安定したキーを作る。

    `query_profile_version` を含める(`docs/architecture.md`)。パラメータ
    そのものも含めるため、版を上げ忘れてクエリだけ変えた場合でも取り違えない。
    `hashlib.sha256` を使う(`hash()` はプロセスごとに変わる)。
    """
    material = json.dumps(
        {
            "source": source.value,
            "topic_id": profile.topic_id.value,
            "country": profile.country.value,
            "query_profile_version": profile.version,
            "params": build_params(source, profile),
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def cache_age_seconds(client: object, source: SourceName, profile: QueryProfile) -> float:
    """直前の取得がキャッシュ由来なら、その経過秒数を返す。

    キャッシュに対応しないクライアント(fixture / live の素の実装)では 0.0。
    `SourceFetch.cache_age_seconds` の既定と同じ意味になる。
    """
    getter = getattr(client, "cache_age_seconds", None)
    if callable(getter):
        return float(getter(source, profile))
    return 0.0


class CachingSerpApiClient:
    """`SerpApiClient` を TTL 付きキャッシュで包む。

    **失敗をキャッシュしない。** 例外はそのまま通す(1回の失敗を TTL のあいだ
    引きずらない)。
    """

    def __init__(
        self,
        inner: SerpApiClient,
        *,
        store: CacheStore | None = None,
        ttl_seconds: Mapping[SourceName, float] = SOURCE_TTL_SECONDS,
        now: Callable[[], datetime] = _utc_now,
    ) -> None:
        self._inner = inner
        self._store = store if store is not None else InMemoryCacheStore()
        self._ttl = ttl_seconds
        self._now = now
        self._last_age: dict[str, float] = {}

    def fetch(self, source: SourceName, profile: QueryProfile) -> dict[str, Any]:
        key = build_cache_key(source, profile)
        now = self._now()
        entry = self._store.get(key)
        if entry is not None:
            age = (now - entry.stored_at).total_seconds()
            if 0.0 <= age < self._ttl.get(source, 0.0):
                self._last_age[key] = age
                return entry.payload

        payload = self._inner.fetch(source, profile)
        self._store.put(key, CacheEntry(payload=payload, stored_at=now))
        self._last_age[key] = 0.0
        return payload

    def cache_age_seconds(self, source: SourceName, profile: QueryProfile) -> float:
        """直前の `fetch` が使ったキャッシュの経過秒数。新規取得なら 0.0。"""
        return self._last_age.get(build_cache_key(source, profile), 0.0)
