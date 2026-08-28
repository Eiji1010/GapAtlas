"""SQS メッセージ1件(=1国)を処理するユースケース。

`ScanService` の同期版と同じ成果物を、**1メッセージ1国**の非同期実行で作る
(docs/architecture.md「非同期処理」)。1国の失敗が他国を巻き込まないように
するための分割であり、ランキング・Top2 Maps・Top1 Brief・概要の確定は
**最後に完了した国のワーカー**が行う。

```text
SQS メッセージ(1国)
   ↓ QueryProfile を読む(読めなければその国は FAILED)
   ↓ CountryScanner.scan
   ↓ DynamoDB COUNTRY item / S3 raw・normalized・curated へ保存
   ↓ list_countries が job.countries を網羅していたら
       ランキング確定 → Top2 の Maps → Top1 の Brief → SCAN META を保存
```

## 「最後の1国」判定は競合する

判定は `repository.list_countries()` の読み取りに基づくため、**2つのワーカーが
ほぼ同時に自分の国を保存すると、両方が「自分が最後」と判断しうる**。その場合
概要の確定処理が2回走る。

MVP ではこれを許容する。実害は次の3点に限られると整理した。

- `save_scan` は同じ `(PK, SK)` への上書き(`ScanRepository` の契約)であり、
  入力が同じなら結果も同じ。**書き込みが衝突しても壊れない**
- ランキングは同じ `CountryResult` 群から `_ranking_key` で決まるので同一になる
- Maps の再取得は `source_status[maps]` が `NOT_REQUESTED` の国だけに限って
  いるので、二重には走らない

したがって余分に発生するのは **Opportunity Brief の LLM 呼び出し 1回**だけで
ある。デモ規模(5か国 / Reserved concurrency 2)では許容できるコストと判断した。
DynamoDB の条件付き書き込みで解消する案は完了報告に記載する。

## 例外を投げる / 投げない

SQS は「ハンドラが例外を投げた = 処理失敗」と解釈してメッセージを再配信し、
`maxReceiveCount = 3` を超えると DLQ へ送る(docs/requirements.md
「Reliability」)。**再配信は同じジョブの再実行**であり、1国あたり
SerpApi 4回 + LLM 3回を再度支払う。したがって「リトライで直る見込みがあるか」
だけで方針を決める。

**成功扱いにする(メッセージを削除させる)失敗:**

- SerpApi / LLM の一時障害 — `CountryScanner` が内部でソース単位に捕捉して
  `MISSING` として吸収し、部分的な結果と Confidence を返す。再実行しても
  同じ fixture / 同じ障害状況なら結果は変わらない
- QueryProfile を読めない — YAML はリトライでは現れない。その国を `FAILED`
  として記録するほうが、DLQ で沈黙するより可視性が高い
- DynamoDB / S3 への保存の失敗 — 算出済みの結果を捨てないことを優先する
  (`ScanService._persist_country` と同じ方針、docs/requirements.md
  「Reliability」)。リトライすると外部 API 呼び出しを払い直したうえで、
  永続化が落ちている間はどうせ失敗する
- ランキング確定・Maps・Brief・概要保存の失敗 — 同上。ここまで来た時点で
  各国の `CountryResult` は保存済みであり、UI は進捗を表示できる

**リトライさせる(例外を投げる)失敗:**

- 上記以外の想定外の例外。ワーカー自身の実装バグ、権限設定の誤り、
  Lambda のタイムアウトやメモリ不足などが該当する。**握りつぶすと DLQ に
  何も残らず、障害が可視化されない。** 3回で DLQ へ落とし、そこで気付く

`JobDecodeError` はこの層へ届かない。本文を復元できないメッセージは
Lambda ハンドラが捨てる(`adapters/sqs/decode.py`)。

**この方針の代償**は、DynamoDB が落ちている間のスキャンが `processing` の
まま残ることである(誰も概要を書けない)。リトライで救える見込みが薄い一方、
再実行の代金は確実に発生するため、MVP ではこちらを選んだ。
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path
from typing import Final

from gapatlas.adapters.dynamodb.protocol import ScanRepository
from gapatlas.adapters.llm.protocol import BriefWriter
from gapatlas.adapters.s3.protocol import ScanArchive
from gapatlas.application.country_scan import (
    CountryScanner,
    CountryScanOutcome,
    RawSources,
    build_failed_outcome,
)
from gapatlas.application.evidence import build_evidence_pack
from gapatlas.application.jobs import ScanJob
from gapatlas.application.logging_context import log_context
from gapatlas.application.persistence import (
    archive_curated,
    archive_normalized,
    archive_raw,
    save_country,
    save_summary,
)
from gapatlas.application.scan_service import (
    MAPS_COUNTRY_LIMIT,
    RANKABLE_STATUSES,
    _ranking_key,
    build_scan_summary,
    to_public_component,
)
from gapatlas.config.errors import ConfigError
from gapatlas.config.query_profile_loader import load_query_profile
from gapatlas.domain.models.classification import ClassifiedEvidence
from gapatlas.domain.models.common import (
    Country,
    CountryStatus,
    ScanStatus,
    SourceName,
    SourceStatus,
    TopicId,
)
from gapatlas.domain.models.normalized import NormalizedEvidence
from gapatlas.domain.models.query_profile import QueryProfile
from gapatlas.domain.models.result import (
    CountryResult,
    Evidence,
    OpportunityBrief,
    ScanSummary,
)
from gapatlas.domain.models.scores import ConfidenceResult, NeedGapResult
from gapatlas.domain.scoring.engine import CountryEvaluation, PublicComponents

_LOGGER: Final[logging.Logger] = logging.getLogger(__name__)


def public_evaluation_from_result(result: CountryResult) -> CountryEvaluation:
    """保存済みの `CountryResult` から `CountryEvaluation` の**公開表現だけ**を復元する。

    非同期版では、最後の国のワーカーが手元に持つのは自分の国の
    `CountryScanOutcome` だけである。他国については DynamoDB に保存された
    `CountryResult` しか読めないが、`CountryScanner.attach_maps` と
    `build_evidence_pack` はどちらも `CountryEvaluation` を要求するため、
    ここで詰め直す。

    **内部 float 表現は復元できない。** `CountryResult` は公開表現(丸め済みの
    int)しか保存していないため、`need_gap.score` と `confidence.score` には
    丸め済みの値を、`components_used` と `applied_caps` には空リストを入れる。
    **この戻り値をスコア計算へ流してはいけない。** 使ってよいのは
    `public_*` と `components` / `breakdown` だけである。
    """
    return CountryEvaluation(
        status=result.status,
        need_gap=NeedGapResult(
            score=None if result.need_gap_score is None else float(result.need_gap_score),
            components=result.components,
            components_used=[],
        ),
        confidence=ConfidenceResult(
            score=float(result.confidence),
            breakdown=result.confidence_breakdown,
            applied_caps=[],
        ),
        public_need_gap_score=result.need_gap_score,
        public_confidence=result.confidence,
        public_components=PublicComponents(
            demand=to_public_component(result.components.demand),
            pain=to_public_component(result.components.pain),
            solution_gap=to_public_component(result.components.solution_gap),
            news_urgency=to_public_component(result.components.news_urgency),
        ),
    )


class ScanWorker:
    """SQS メッセージ1件を処理する。

    アダプタは Protocol として受け取る(docs/architecture.md「依存の向き」)。
    現在時刻はこの層でも取得しない。基準時刻は `ScanJob.scan_time` を使う
    (スキャン全国で同じ基準時刻を使うため、`application/jobs.py`)。
    """

    def __init__(
        self,
        scanner: CountryScanner,
        repository: ScanRepository,
        archive: ScanArchive | None = None,
        brief_writer: BriefWriter | None = None,
        *,
        profiles_dir: Path | None = None,
    ) -> None:
        """
        Args:
            scanner: 1国分のスキャン。
            repository: 最新結果の保存先。**省略できない。**「自分が最後の1国か」
                の判定に `list_countries` が要るため。
            archive: 履歴の保存先(S3 / インメモリ)。省略すると保存しない。
            brief_writer: Opportunity Brief の生成器。省略すると Brief を作らない。
            profiles_dir: QueryProfile の格納ディレクトリ。省略時は既定値。
        """
        self._scanner = scanner
        self._repository = repository
        self._archive = archive
        self._brief_writer = brief_writer
        self._profiles_dir = profiles_dir

    def handle(self, job: ScanJob) -> CountryScanOutcome:
        """1国分を処理する。

        戻り値は**その国のスキャン結果**であり、Maps を足す前の状態である。
        自国が Top2 に入った場合、保存済みの `CountryResult` には Maps が
        足されているため、**正本はリポジトリ側**になる。呼び出し元(Lambda
        ハンドラ)はログとメトリクス用にだけ使うこと。
        """
        with log_context(scan_id=job.scan_id, topic=job.topic_id.value, country=job.country.value):
            outcome = self._scan_country(job)
            self._persist_country(outcome, scan_time=job.scan_time)
            self._finalize_if_last(job)
            return outcome

    # --- 1国分の処理 ------------------------------------------------------------------

    def _scan_country(self, job: ScanJob) -> CountryScanOutcome:
        profile = self._load_profile(job.topic_id, job.country)
        if profile is None:
            return build_failed_outcome(
                job.topic_id, job.country, scan_id=job.scan_id, scan_time=job.scan_time
            )
        return self._scanner.scan(profile, scan_id=job.scan_id, scan_time=job.scan_time)

    def _load_profile(self, topic_id: TopicId, country: Country) -> QueryProfile | None:
        """QueryProfile を読む。読めなければ `None`。

        1か国の YAML が欠けているだけで健全な4か国の結果まで失うのは
        docs/requirements.md「Reliability」に反する(`ScanService._load_profiles`
        と同じ方針)。
        """
        with log_context(country=country.value):
            try:
                return load_query_profile(topic_id, country, self._profiles_dir)
            except ConfigError as exc:
                _LOGGER.warning(
                    "query profile could not be loaded; the country is marked failed",
                    extra={"error": type(exc).__name__},
                )
                return None

    # --- 完了判定と確定処理 -----------------------------------------------------------

    def _save_interim_summary(self, job: ScanJob, results: Sequence[CountryResult]) -> None:
        """処理中の概要を保存する。

        Worker が最後の1国でしか概要を書かないと、`GET /scans/{id}` の
        `ranking` が完了まで空のままになり、**2秒 Polling で進捗が動かない**
        (docs/api.md の例は `status: processing` で部分的なランキングを示す)。
        国が1つ終わるたびに、そこまでの結果で概要を上書きする。

        Opportunity Brief は付けない(全国完了後に Top1 へ生成するため)。

        保存に失敗して結果を1件も読めない場合は何も書かない。空の概要で
        API が作った初期 META を上書きすると、対象国の情報まで失われる。
        """
        if not results:
            return
        summary = build_scan_summary(
            scan_id=job.scan_id,
            topic_id=job.topic_id,
            total=len(job.countries),
            results=results,
            status=ScanStatus.PROCESSING,
        )
        self._persist_summary(summary)

    def _finalize_if_last(self, job: ScanJob) -> None:
        """自分が最後の1国なら、スキャン全体を確定する。

        判定は `list_countries` が `job.countries` を**すべて**含むかどうかで
        行う。競合しうることはモジュール docstring に記載のとおり。
        """
        stored = self._list_countries(job.scan_id)
        if stored is None:
            return
        expected = set(job.countries)
        results = [result for result in stored if result.country in expected]
        if expected - {result.country for result in results}:
            # まだ揃っていない。2秒 Polling で進捗が見えるよう途中経過を保存する
            self._save_interim_summary(job, results)
            return
        self._finalize(job, results)

    def _list_countries(self, scan_id: str) -> list[CountryResult] | None:
        """保存済みの国別結果を読む。読めなければ `None`(=確定処理を行わない)。"""
        try:
            return self._repository.list_countries(scan_id)
        except Exception:
            _LOGGER.exception("persistence failed", extra={"operation": "list country results"})
            return None

    def _finalize(self, job: ScanJob, results: Sequence[CountryResult]) -> None:
        """ランキング確定 -> Top2 Maps -> Top1 Brief -> 概要の保存。"""
        ordered = sorted(results, key=_ranking_key)
        enriched = self._attach_maps_to_top_countries(job, ordered)
        final = [enriched.get(result.country, result) for result in ordered]

        brief = self._write_brief(job.topic_id, final)
        summary = build_scan_summary(
            scan_id=job.scan_id,
            topic_id=job.topic_id,
            total=len(job.countries),
            results=final,
            brief=brief,
        )
        _LOGGER.info(
            "scan completed",
            extra={
                "status": summary.status.value,
                "ranked": [entry.country.value for entry in summary.ranking],
                "has_brief": brief is not None,
                # `INSUFFICIENT_EVIDENCE` はエラーではないので status は
                # `completed` のままだが、全国がそうなるのは外形障害である。
                "rankable_countries": sum(
                    1 for result in final if result.status in RANKABLE_STATUSES
                ),
                "insufficient_countries": sum(
                    1 for result in final if result.status is CountryStatus.INSUFFICIENT_EVIDENCE
                ),
                "failed_countries": sum(
                    1 for result in final if result.status is CountryStatus.FAILED
                ),
            },
        )
        self._persist_summary(summary)

    # --- Top2 の Maps -----------------------------------------------------------------

    def _attach_maps_to_top_countries(
        self, job: ScanJob, ordered: Sequence[CountryResult]
    ) -> dict[Country, CountryResult]:
        """ランキング確定後、Top2 についてのみ Maps を取得する。

        スコアには影響しない(Maps は Core Source ではない、docs/scoring.md 6章)。
        変わるのは `source_status` と Evidence の一覧だけである。

        **Maps を取得済みの国は飛ばす。** 同じジョブが再配信されて確定処理が
        2回走っても Evidence が二重に増えないようにするため(冪等性)。
        """
        rankable = [result for result in ordered if result.status in RANKABLE_STATUSES]
        enriched: dict[Country, CountryResult] = {}
        for result in rankable[:MAPS_COUNTRY_LIMIT]:
            if result.source_status.get(SourceName.MAPS) is not SourceStatus.NOT_REQUESTED:
                continue
            profile = self._load_profile(job.topic_id, result.country)
            if profile is None:
                continue
            outcome = self._fetch_maps(result, profile, scan_time=job.scan_time)
            enriched[result.country] = outcome.result
            self._persist_maps(outcome, scan_time=job.scan_time)
        return enriched

    def _fetch_maps(
        self, result: CountryResult, profile: QueryProfile, *, scan_time: datetime
    ) -> CountryScanOutcome:
        """保存済みの `CountryResult` へ Maps を足す。

        `CountryScanner.attach_maps` を**取得と正規化のためだけ**に使い、
        Evidence の差し替えは自前で行う。`attach_maps` は
        `build_evidence(evidence, classified)` で Evidence 一覧を作り直すが、
        非同期版のワーカーは他国の `NormalizedEvidence` / `ClassifiedEvidence`
        を持っていない(SQS メッセージにも DynamoDB にも入っていない)。
        空の証拠を渡して作り直させると「急上昇クエリ 0 件のうち…」のような
        **事実と異なる要約**で上書きしてしまう。

        そこで空の証拠を種にして `attach_maps` を呼び、返ってきた Maps 分の
        Evidence(必ず `E1` 1件、または Maps が MISSING なら 0件)だけを取り出し、
        保存済み Evidence の末尾へ採番し直して足す。`build_evidence` は Maps を
        最後に並べるため、同期版(`ScanService`)と同じ並びと同じ要約になる。
        """
        seed = CountryScanOutcome(
            result=result,
            evidence=NormalizedEvidence(),
            classified=ClassifiedEvidence(),
            evaluation=public_evaluation_from_result(result),
            raw=RawSources(payloads={}),
        )
        fetched = self._scanner.attach_maps(seed, profile, scan_time=scan_time)
        maps_status = fetched.evidence.source_status(SourceName.MAPS)
        merged_evidence = [
            *result.evidence,
            *_renumbered(fetched.result.evidence, start=len(result.evidence) + 1),
        ]
        merged = CountryResult.model_validate(
            result.model_dump()
            | {
                "source_status": {**result.source_status, SourceName.MAPS: maps_status},
                "evidence": [item.model_dump() for item in merged_evidence],
                # Screen 2 の Maps 表示。`None` は「取得していない」なので、
                # 取得を試みた国では必ず配列(0件でも空配列)にする。
                "maps_results": [
                    place.model_dump() for place in (fetched.evidence.maps_places or [])
                ],
            }
        )
        return CountryScanOutcome(
            result=merged,
            evidence=fetched.evidence,
            classified=fetched.classified,
            evaluation=fetched.evaluation,
            raw=fetched.raw,
        )

    # --- Opportunity Brief ------------------------------------------------------------

    def _write_brief(
        self, topic_id: TopicId, ordered: Sequence[CountryResult]
    ) -> OpportunityBrief | None:
        """Top1 について Opportunity Brief を生成する。

        ランキング可能な国が1つも無ければ生成しない。`brief_writer` を注入して
        いない場合も生成しない。
        """
        if self._brief_writer is None:
            return None
        writer = self._brief_writer
        top = next((result for result in ordered if result.status in RANKABLE_STATUSES), None)
        if top is None:
            _LOGGER.info("opportunity brief skipped: no rankable country")
            return None
        with log_context(country=top.country.value):
            try:
                pack = build_evidence_pack(
                    top.country, topic_id, public_evaluation_from_result(top), top.evidence
                )
                brief = writer.write_brief(pack)
            except Exception:
                # Brief はランキング確定**後**に走る。ここで例外を通すと、
                # 完了済みの全国分の結果を丸ごと捨てることになる
                # (docs/requirements.md「1 Source が失敗してもシステム全体を
                # 500 エラーにしない」)。Brief は出さないほうが安全。
                _LOGGER.exception("opportunity brief generation failed")
                return None
            if brief is None:
                _LOGGER.warning("opportunity brief was not produced")
            return brief

    # --- 永続化 -----------------------------------------------------------------------
    #
    # 規則は `application/persistence.py` が持つ(`ScanService` と共有)。
    # **保存の失敗でジョブを失敗させない。** 例外を通すと算出済みの結果を
    # 捨てたうえで SerpApi と LLM の呼び出しを再度支払うことになる
    # (モジュール docstring「例外を投げる / 投げない」)。

    def _persist_country(self, outcome: CountryScanOutcome, *, scan_time: datetime) -> None:
        """1国分を保存する。"""
        result = outcome.result
        with log_context(country=result.country.value):
            archive_raw(
                self._archive,
                outcome.raw.payloads,
                topic_id=result.topic_id,
                country=result.country,
                scan_time=scan_time,
                scan_id=result.scan_id,
            )
            archive_normalized(
                self._archive,
                outcome.evidence,
                topic_id=result.topic_id,
                country=result.country,
                scan_time=scan_time,
                scan_id=result.scan_id,
            )
            archive_curated(self._archive, result, scan_time=scan_time)
            save_country(self._repository, result)

    def _persist_maps(self, outcome: CountryScanOutcome, *, scan_time: datetime) -> None:
        """Maps を足した国を保存し直す。

        **`normalized/` は書き直さない。** ここで持っている
        `NormalizedEvidence` は Maps だけの部分的なものであり、同じキーへ
        書くと `_fetch_maps` が避けた「事実と異なる要約での上書き」を
        S3 側でやってしまう。`raw/` は Maps 専用のキーなので追記になり、
        `curated/` は完全な `CountryResult` を書く。
        """
        result = outcome.result
        with log_context(country=result.country.value):
            archive_raw(
                self._archive,
                outcome.raw.payloads,
                topic_id=result.topic_id,
                country=result.country,
                scan_time=scan_time,
                scan_id=result.scan_id,
            )
            archive_curated(self._archive, result, scan_time=scan_time)
            save_country(self._repository, result)

    def _persist_summary(self, summary: ScanSummary) -> None:
        """スキャン概要を保存する。"""
        save_summary(self._repository, summary)


def _renumbered(items: Sequence[Evidence], *, start: int) -> list[Evidence]:
    """Evidence の id を `E{start}` から振り直す。要約と URL は変えない。"""
    return [
        item.model_copy(update={"id": f"E{start + offset}"}) for offset, item in enumerate(items)
    ]
