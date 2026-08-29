"""永続化のガード付きヘルパ。

`ScanService`(同期実行)と `ScanWorker`(SQS 経由の非同期実行)の両方から
同じ規則で保存するために、自由関数として切り出す。**同じロジックを2箇所で
書かない**(W6 の第三者指摘)。

## 方針

**保存の失敗でスキャンを止めない。** 保存はスコア算出の後段であり、ここで
例外を通すと算出済みの結果を捨てることになる(docs/requirements.md
「Reliability」/「1 Source が失敗してもシステム全体を 500 エラーにしない」)。

例外の型を絞らない。アダプタは独自の例外階層(`RepositoryError` /
`ArchiveError`)を持つが、boto3 由来の想定外の例外も同じく「保存に失敗した
だけ」として扱いたい。**失敗はログへ残す**ので沈黙はしない。
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from datetime import datetime
from typing import Any, Final

from gapatlas.adapters.dynamodb.protocol import ScanRepository
from gapatlas.adapters.s3.protocol import ScanArchive
from gapatlas.domain.models.common import Country, SourceName, TopicId
from gapatlas.domain.models.normalized import NormalizedEvidence
from gapatlas.domain.models.result import CountryResult, ScanSummary

_LOGGER: Final[logging.Logger] = logging.getLogger(__name__)


def _log_failure(operation: str, **extra: str) -> None:
    _LOGGER.exception("persistence failed", extra={"operation": operation, **extra})


def save_country(repository: ScanRepository | None, result: CountryResult) -> None:
    """国別結果を保存する。失敗はログへ残して握る。"""
    if repository is None:
        return
    try:
        repository.save_country(result)
    except Exception:
        _log_failure("country repository")


def save_summary(repository: ScanRepository | None, summary: ScanSummary) -> None:
    """確定した概要を保存する(無条件で上書きする)。失敗はログへ残して握る。"""
    if repository is None:
        return
    try:
        repository.save_scan(summary)
    except Exception:
        _log_failure("scan repository")


def save_interim_summary(repository: ScanRepository | None, summary: ScanSummary) -> None:
    """途中経過の概要を保存する。**確定済みなら上書きしない。**

    並行実行では「まだ揃っていない」と読んだ Worker の書き込みが、別 Worker
    の確定書き込みより後に着地することがある。無条件上書きだと完了済みの
    スキャンが `processing` へ巻き戻り、ランキングと Opportunity Brief が
    失われる(フロントエンドは終端状態に到達できず Polling を続ける)。
    """
    if repository is None:
        return
    try:
        if not repository.save_scan_if_unfinished(summary):
            _LOGGER.info("skipped an interim summary; the scan is already finalized")
    except Exception:
        _log_failure("scan repository")


def archive_raw(
    archive: ScanArchive | None,
    payloads: Mapping[SourceName, Mapping[str, Any]],
    *,
    topic_id: TopicId,
    country: Country,
    scan_time: datetime,
    scan_id: str,
) -> None:
    """SerpApi の生レスポンスを無加工で保存する(docs/architecture.md)。"""
    if archive is None:
        return
    for source, payload in payloads.items():
        try:
            archive.put_raw(
                source=source,
                topic_id=topic_id,
                country=country,
                scan_time=scan_time,
                scan_id=scan_id,
                payload=payload,
            )
        except Exception:
            _log_failure("raw archive", source=source.value)


def archive_normalized(
    archive: ScanArchive | None,
    evidence: NormalizedEvidence,
    *,
    topic_id: TopicId,
    country: Country,
    scan_time: datetime,
    scan_id: str,
) -> None:
    """正規化済み証拠データを保存する。

    **部分的な証拠で呼ばないこと。** 同じキーへ書くため、Maps だけを持つ
    証拠で上書きすると、事実と異なる内容が残る。
    """
    if archive is None:
        return
    try:
        archive.put_normalized(
            topic_id=topic_id,
            country=country,
            scan_time=scan_time,
            scan_id=scan_id,
            evidence=evidence,
        )
    except Exception:
        _log_failure("normalized archive")


def archive_curated(
    archive: ScanArchive | None,
    result: CountryResult,
    *,
    scan_time: datetime,
) -> None:
    """スコアを保存する。Athena の分析対象。"""
    if archive is None:
        return
    try:
        archive.put_curated(
            topic_id=result.topic_id,
            country=result.country,
            scan_time=scan_time,
            scan_id=result.scan_id,
            result=result,
        )
    except Exception:
        _log_failure("curated archive")
