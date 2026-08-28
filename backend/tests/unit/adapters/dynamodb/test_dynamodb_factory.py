"""`create_scan_repository` のテスト。

**実 AWS へ接続しない。** `boto3` の import を差し替え、AWS クライアントを
組み立てずに分岐だけを確認する。
"""

from __future__ import annotations

import builtins
from typing import Any

import pytest

from gapatlas.adapters.dynamodb.errors import RepositoryError
from gapatlas.adapters.dynamodb.factory import create_scan_repository


def test_factory_returns_the_dynamodb_repository_without_boto3(
    monkeypatch: pytest.MonkeyPatch, settings
):
    """`boto3` が無ければ分かりやすい `RepositoryError` になること。

    現状ファクトリは DynamoDB 実装だけを返す。「AWS へ繋がない既定」を選ぶ
    設定(`PERSISTENCE_MODE`)は `Settings` にまだ無く、統合担当が追加する。
    """
    real_import = builtins.__import__

    def fake_import(name: str, *args: Any, **kwargs: Any) -> Any:
        if name == "boto3" or name.startswith("boto3."):
            message = "No module named 'boto3'"
            raise ImportError(message)
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    with pytest.raises(RepositoryError, match="boto3"):
        create_scan_repository(settings)
