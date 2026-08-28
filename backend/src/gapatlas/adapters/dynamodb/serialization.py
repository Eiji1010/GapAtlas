"""Pydantic モデル ↔ DynamoDB 項目の変換。

## 方式の選択: 属性へ展開する

モデルを JSON 文字列にして1属性へ押し込む方式ではなく、**トップレベルの
フィールドをそのまま DynamoDB の属性へ展開する**。理由は次のとおり。

- docs/architecture.md「DynamoDB」が COUNTRY item の例を
  `{"country": "JP", "status": "completed", "need_gap_score": 86, ...}` という
  属性の形で示しており、これが正本である
- 運用時にコンソールや `aws dynamodb get-item` で中身を読めるほうが、
  デモ中の障害調査が速い
- 将来 `status` などで `FilterExpression` を書きたくなったときに、項目の
  作り直しが要らない

代わりに **数値の往復に注意が要る**。DynamoDB は数値を `Decimal` で返し、
boto3 は `float` の書き込みを `TypeError` で拒否する。`_to_dynamodb_value` /
`_from_dynamodb_value` がこの境界を吸収する。

## 変換の規則

- `float` → `Decimal(str(value))`。`Decimal(float)` を使うと 84.6 が
  `84.59999999999999964...` になり、boto3 の `DYNAMODB_CONTEXT` が `Inexact`
  で落ちる
- `Decimal` → 整数値なら `int`、それ以外は `float`。公開スコアは `int`、
  内部スコアは `float` で、どちらも Pydantic 側が受け付ける
- `datetime` は `model_dump(mode="json")` により ISO 8601 文字列で保存する。
  復元時は `UtcDatetime` の `AfterValidator` が UTC へ正規化する
- `None` は DynamoDB の NULL として保存する。欠落と「明示的に None」を
  区別できるようにするため
- `PK` / `SK` / `ttl` は**モデルの属性ではない**。復元時に取り除く。
  domain モデルは `extra="forbid"` であり、渡すと弾かれる

復元できない項目は `RepositoryDataError` にする。**例外メッセージへ項目の値を
載せない**(docs/architecture.md「Security」)。Pydantic の `ValidationError` は
`input_value=...` に実データを埋め込むため、`loc` と `msg` だけを要約し、
原因例外は連鎖させない。
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from decimal import Decimal
from typing import Any, Final

from pydantic import BaseModel, ValidationError

from gapatlas.adapters.dynamodb.errors import RepositoryDataError
from gapatlas.adapters.dynamodb.table import (
    PARTITION_KEY_ATTRIBUTE,
    SORT_KEY_ATTRIBUTE,
    TTL_ATTRIBUTE,
)

RESERVED_ATTRIBUTES: Final[frozenset[str]] = frozenset(
    {PARTITION_KEY_ATTRIBUTE, SORT_KEY_ATTRIBUTE, TTL_ATTRIBUTE}
)
"""モデルには属さない、テーブル側の管理属性。復元時に取り除く。"""


def to_attributes(model: BaseModel) -> dict[str, Any]:
    """モデルを DynamoDB の項目属性へ変換する。キー属性と TTL は含まない。

    Raises:
        RepositoryDataError: 表現できない値(非有限の float など)を含む場合、
            またはモデルが管理属性と同名のフィールドを持つ場合。
    """
    payload = model.model_dump(mode="json")
    collisions = RESERVED_ATTRIBUTES.intersection(payload)
    if collisions:
        names = ", ".join(sorted(collisions))
        message = f"{type(model).__name__} defines reserved DynamoDB attributes: {names}"
        raise RepositoryDataError(message)
    converted = _to_dynamodb_value(payload)
    # `payload` は dict であり `_to_dynamodb_value` は dict を返す。
    return dict(_as_mapping(converted))


def from_attributes[ModelT: BaseModel](model_type: type[ModelT], item: Mapping[str, Any]) -> ModelT:
    """DynamoDB の項目をモデルへ復元する。

    Raises:
        RepositoryDataError: 属性の型が扱えない、または契約のモデルへ復元
            できない場合。
    """
    payload = {
        key: _from_dynamodb_value(value)
        for key, value in item.items()
        if key not in RESERVED_ATTRIBUTES
    }
    try:
        return model_type.model_validate(payload)
    except ValidationError as exc:
        message = f"stored item does not match {model_type.__name__}: {_summarize(exc)}"
        # `from exc` にしない。`ValidationError` の文字列表現は入力値そのものを
        # 含むため、トレースバック経由で項目の中身がログへ漏れる。
        raise RepositoryDataError(message) from None


def _to_dynamodb_value(value: object) -> object:
    """`model_dump(mode="json")` の出力を boto3 が受け付ける形へ変換する。"""
    if value is None or isinstance(value, bool | str | int):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            message = "non-finite float cannot be stored in DynamoDB"
            raise RepositoryDataError(message)
        return Decimal(str(value))
    if isinstance(value, Mapping):
        return {str(key): _to_dynamodb_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_to_dynamodb_value(item) for item in value]
    message = f"unsupported value type for DynamoDB: {type(value).__name__}"
    raise RepositoryDataError(message)


def _from_dynamodb_value(value: object) -> object:
    """DynamoDB が返した値を Pydantic が受け付ける形へ変換する。"""
    if value is None or isinstance(value, bool | str | int):
        return value
    if isinstance(value, Decimal):
        return _decimal_to_number(value)
    if isinstance(value, Mapping):
        return {str(key): _from_dynamodb_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_from_dynamodb_value(item) for item in value]
    message = f"unsupported attribute type from DynamoDB: {type(value).__name__}"
    raise RepositoryDataError(message)


def _decimal_to_number(value: Decimal) -> int | float:
    """`Decimal` を int / float へ戻す。整数値は int にする。

    DynamoDB は `need_gap_score`(int)も `demand`(float)も同じ `Decimal` で
    返すため、値そのものから判断するしかない。int を float フィールドへ渡すのは
    Pydantic が許容する。
    """
    if not value.is_finite():
        message = "non-finite number read from DynamoDB"
        raise RepositoryDataError(message)
    if value == value.to_integral_value():
        return int(value)
    return float(value)


def _as_mapping(value: object) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    message = f"expected a mapping, got {type(value).__name__}"
    raise RepositoryDataError(message)


def _summarize(exc: ValidationError) -> str:
    """検証エラーを `loc: msg` へ要約する。**入力値は含めない。**"""
    return "; ".join(
        f"{'.'.join(str(part) for part in error['loc'])}: {error['msg']}" for error in exc.errors()
    )
