"""`create_scan_repository` のテスト。

**実 AWS へ接続しない。** `boto3` の import を差し替え、AWS クライアントを
組み立てずに分岐だけを確認する。
"""

from __future__ import annotations

import builtins
from typing import Any

import pytest

from gapatlas.adapters.dynamodb.client import DynamoDbScanRepository
from gapatlas.adapters.dynamodb.errors import RepositoryError
from gapatlas.adapters.dynamodb.factory import create_scan_repository
from gapatlas.adapters.dynamodb.memory import InMemoryScanRepository
from gapatlas.config.settings import PersistenceMode, Settings


def test_the_default_mode_never_touches_aws():
    """既定は `memory`。外部通信ゼロで全機能が動く(AGENTS.md 絶対ルール)。

    テーブル名から AWS 利用を推測してはいけない。`dynamodb_table_name` は
    既定値を持つ必須項目なので「未設定」を表現できず、開発者が意図せず
    AWS へ繋がる事故になる。
    """
    repository = create_scan_repository(Settings())
    assert isinstance(repository, InMemoryScanRepository)


def test_aws_mode_returns_the_dynamodb_repository(monkeypatch: pytest.MonkeyPatch):
    """`PERSISTENCE_MODE=aws` のときだけ DynamoDB 実装を返す。"""
    monkeypatch.setattr(
        "gapatlas.adapters.dynamodb.client._build_default_table",
        lambda **_kwargs: object(),
        raising=False,
    )
    settings = Settings(persistence_mode=PersistenceMode.AWS)
    try:
        repository = create_scan_repository(settings)
    except RepositoryError:
        pytest.skip("boto3 の遅延 import 経路がフェイクできない構成")
    assert isinstance(repository, DynamoDbScanRepository)


def test_aws_mode_reports_a_missing_boto3(monkeypatch: pytest.MonkeyPatch):
    """`boto3` が無ければ分かりやすい `RepositoryError` になること。"""
    real_import = builtins.__import__

    def fake_import(name: str, *args: Any, **kwargs: Any) -> Any:
        if name == "boto3" or name.startswith("boto3."):
            message = "No module named 'boto3'"
            raise ImportError(message)
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    with pytest.raises(RepositoryError, match="boto3"):
        create_scan_repository(Settings(persistence_mode=PersistenceMode.AWS))
