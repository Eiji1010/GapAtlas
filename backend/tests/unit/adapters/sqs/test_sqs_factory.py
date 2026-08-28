"""`create_job_queue` のテスト。

**実 AWS へ接続しない。** `boto3` の import を差し替え、AWS クライアントを
組み立てずに分岐だけを確認する。
"""

from __future__ import annotations

import builtins
from typing import Any

import pytest

from gapatlas.adapters.sqs.client import SqsJobQueue
from gapatlas.adapters.sqs.errors import JobQueueError
from gapatlas.adapters.sqs.factory import create_job_queue
from gapatlas.adapters.sqs.memory import InMemoryJobQueue
from gapatlas.config.settings import PersistenceMode, Settings

QUEUE_URL = "https://sqs.ap-northeast-1.amazonaws.com/000000000000/gapatlas-jobs"


def test_the_default_mode_never_touches_aws():
    """既定は `memory`。外部通信ゼロで全機能が動く(AGENTS.md 絶対ルール)。"""
    assert isinstance(create_job_queue(Settings()), InMemoryJobQueue)


def test_a_queue_url_alone_does_not_enable_aws():
    """`SQS_QUEUE_URL` の有無から AWS 利用を推測しない。"""
    queue = create_job_queue(Settings(sqs_queue_url=QUEUE_URL))
    assert isinstance(queue, InMemoryJobQueue)


def test_aws_mode_returns_the_sqs_queue(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        "gapatlas.adapters.sqs.client._build_default_client",
        lambda **_kwargs: object(),
        raising=False,
    )
    settings = Settings(persistence_mode=PersistenceMode.AWS, sqs_queue_url=QUEUE_URL)
    assert isinstance(create_job_queue(settings), SqsJobQueue)


def test_aws_mode_without_a_queue_url_is_reported_clearly():
    settings = Settings(persistence_mode=PersistenceMode.AWS)
    with pytest.raises(JobQueueError, match="SQS_QUEUE_URL"):
        create_job_queue(settings)


def test_aws_mode_reports_a_missing_boto3(monkeypatch: pytest.MonkeyPatch):
    real_import = builtins.__import__

    def fake_import(name: str, *args: Any, **kwargs: Any) -> Any:
        if name == "boto3" or name.startswith("boto3."):
            message = "No module named 'boto3'"
            raise ImportError(message)
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    settings = Settings(persistence_mode=PersistenceMode.AWS, sqs_queue_url=QUEUE_URL)
    with pytest.raises(JobQueueError, match="boto3"):
        create_job_queue(settings)
