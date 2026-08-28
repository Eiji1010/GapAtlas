"""domain 層で使用する例外。

呼び出し元が種類を判別できるよう、標準の `ValueError` をそのまま投げずに
この階層を使う。

`DomainValidationError` は `ValueError` を継承している。Pydantic のバリデータが
送出した `ValueError`(およびその派生)は Pydantic により `ValidationError` へ
変換されるため、モデル境界では `ValidationError`、それ以外の呼び出し経路では
`GapAtlasError` として一貫して扱える。
"""

from __future__ import annotations


class GapAtlasError(Exception):
    """GapAtlas のすべての例外の基底。"""


class DomainError(GapAtlasError):
    """domain 層で発生する例外の基底。"""


class DomainValidationError(DomainError, ValueError):
    """domain モデルの制約違反。"""


class InvalidTemporalValueError(DomainValidationError):
    """timezone-aware でない日時など、時間表現が不正な場合。"""


class ModelConsistencyError(DomainValidationError):
    """単一フィールドでは表現できないモデル横断の整合性違反。"""
