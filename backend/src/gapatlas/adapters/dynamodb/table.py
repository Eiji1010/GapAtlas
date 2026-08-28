"""DynamoDB のキー設計。

正本は docs/architecture.md「DynamoDB」の表である。

| PK | SK | 内容 |
|---|---|---|
| `SCAN#{scan_id}` | `META` | スキャン全体の状態・進捗・ランキング・Brief |
| `SCAN#{scan_id}` | `COUNTRY#{country}` | 国別の結果と Evidence |

ここは**純粋関数と定数だけ**を置く。I/O を持ち込まない。

**キーの形を変えるときは Terraform のテーブル定義と、保存済み項目のマイグレーション
を同時に用意すること。** 単体テストはキーをリテラルで固定しており、形が変われば
テストが落ちるようにしてある。
"""

from __future__ import annotations

from typing import Final

from gapatlas.domain.models.common import Country

PARTITION_KEY_ATTRIBUTE: Final[str] = "PK"
"""パーティションキーの属性名。Terraform の `hash_key` と一致させること。"""

SORT_KEY_ATTRIBUTE: Final[str] = "SK"
"""ソートキーの属性名。Terraform の `range_key` と一致させること。"""

TTL_ATTRIBUTE: Final[str] = "ttl"
"""TTL 属性の名前。Terraform の `ttl { attribute_name = ... }` と一致させること。

docs/architecture.md「TTL 属性を持たせ、デモ後に自動削除できるようにする」。
"""

SCAN_KEY_PREFIX: Final[str] = "SCAN#"
META_SORT_KEY: Final[str] = "META"
COUNTRY_KEY_PREFIX: Final[str] = "COUNTRY#"


def scan_partition_key(scan_id: str) -> str:
    """スキャン1件のパーティションキー(`SCAN#{scan_id}`)。"""
    return f"{SCAN_KEY_PREFIX}{scan_id}"


def meta_sort_key() -> str:
    """スキャン概要項目のソートキー(`META`)。"""
    return META_SORT_KEY


def country_sort_key(country: Country) -> str:
    """国別結果項目のソートキー(`COUNTRY#{country}`)。"""
    return f"{COUNTRY_KEY_PREFIX}{country.value}"


def is_country_sort_key(sort_key: str) -> bool:
    """そのソートキーが国別結果項目のものか。

    `META` と、将来追加されうる別種の項目を `list_countries` から除外するために
    使う。**未知の SK を例外にしない。** 項目種別を足しただけで既存の読み取りが
    落ちると、デプロイ順序に依存した障害になる。
    """
    return sort_key.startswith(COUNTRY_KEY_PREFIX)
