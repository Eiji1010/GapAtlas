"""5か国のスキャンを束ねるユースケース。

順序は docs/architecture.md「非同期処理」に従う。

1. 国ごとにスキャン(Maps は取らない)
2. ランキングを確定する
3. **Top 2 countries** についてのみ Maps を取得する
4. **Top 1** について Opportunity Brief を生成する

MVP の CLI では同期的に順次実行する。SQS 経由の非同期化は Phase 8。
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Final

from gapatlas.adapters.llm.protocol import BriefWriter, LlmClassifier
from gapatlas.adapters.serpapi.protocol import SerpApiClient
from gapatlas.application.country_scan import (
    CountryScanner,
    CountryScanOutcome,
    build_failed_outcome,
)
from gapatlas.application.evidence import build_evidence_pack
from gapatlas.application.logging_context import log_context
from gapatlas.config.errors import ConfigError
from gapatlas.config.query_profile_loader import load_query_profile
from gapatlas.domain.models.common import Country, CountryStatus, ScanStatus, TopicId
from gapatlas.domain.models.query_profile import QueryProfile
from gapatlas.domain.models.result import (
    CountryResult,
    OpportunityBrief,
    RankingEntry,
    ScanProgress,
    ScanSummary,
    Versions,
)
from gapatlas.domain.scoring.constants import SCORE_VERSION
from gapatlas.domain.scoring.rounding import round_half_up

_LOGGER: Final[logging.Logger] = logging.getLogger(__name__)

MAPS_COUNTRY_LIMIT: Final[int] = 2
"""Maps を取得する国数。docs/requirements.md「Top 2 countries についてのみ取得」。"""

RANKABLE_STATUSES: Final[frozenset[CountryStatus]] = frozenset({CountryStatus.COMPLETED})
"""ランキングの上位に載せてよい status。

`INSUFFICIENT_EVIDENCE` は**エラーではないが除外**する(docs/scoring.md 7章)。
表示自体は行うため `ranking` には残し、末尾へ回す。
"""


@dataclass(frozen=True, slots=True)
class ScanOutput:
    """スキャン1回分の全成果物。永続化と API がここから取り出す。"""

    summary: ScanSummary
    outcomes: dict[Country, CountryScanOutcome]


STATUS_RANK: Final[dict[CountryStatus, int]] = {
    CountryStatus.COMPLETED: 0,
    CountryStatus.INSUFFICIENT_EVIDENCE: 1,
    CountryStatus.FAILED: 2,
    CountryStatus.PROCESSING: 3,
    CountryStatus.PENDING: 4,
}
"""ランキング末尾側の順序。**`FAILED` は必ず最後**にする。

`INSUFFICIENT_EVIDENCE` は「部分的な結果と Confidence を返せた」状態、
`FAILED` は「何も返せなかった」状態なので、前者を上に置く。confidence の
大小に依存させない(`_failed_outcome` が 0 を入れているという別モジュールの
実装詳細へ順序を委ねないため)。
"""


def _ranking_key(result: CountryResult) -> tuple[int, int, int, str]:
    """`need_gap_score` 降順。`None` は末尾へ回す(docs/api.md)。

    `None` は 0(取りうる最小スコア)として並べる。`need_gap_score` が `None` の
    国は必ず `INSUFFICIENT_EVIDENCE` か `FAILED` であり(`CountryResult` の
    モデル検証)、`COMPLETED` かつ 0 点の国と同点になったときは status 項が
    決着させる。したがって**スコアを持つ国が必ず先に来る**。

    同点は status 優先度 → `confidence` 降順 → 国コード昇順で決める。
    **順序を決定的にするため**であり、意味づけはしていない。
    """
    score = result.need_gap_score if result.need_gap_score is not None else 0
    return (
        -score,
        STATUS_RANK[result.status],
        -result.confidence,
        result.country.value,
    )


def to_public_component(value: float | None) -> int | None:
    """内部 float を公開表現の int へ丸める。

    **組み込みの `round()` を使わないこと。** 偶数丸めになり
    docs/scoring.md「四捨五入(round half up)」に反する。`engine.py` の
    公開表現と 1 ずれ、同じ画面で違う値が出る。
    """
    return None if value is None else round_half_up(value)


def _to_ranking_entry(result: CountryResult) -> RankingEntry:
    components = result.components
    return RankingEntry(
        country=result.country,
        status=result.status,
        need_gap_score=result.need_gap_score,
        confidence=result.confidence,
        demand=to_public_component(components.demand),
        pain=to_public_component(components.pain),
        solution_gap=to_public_component(components.solution_gap),
        news_urgency=to_public_component(components.news_urgency),
    )


def _scan_status(results: Sequence[CountryResult]) -> ScanStatus:
    if any(result.status is CountryStatus.FAILED for result in results):
        return ScanStatus.PARTIALLY_FAILED
    return ScanStatus.COMPLETED


def _summary_versions(results: Sequence[CountryResult]) -> Versions:
    """スキャン全体のバージョン識別子。

    `query_profile_version` は国ごとに異なるため、**スキャンに使った全国分を
    昇順で連結**する(単一国なら1件なのでその国の版そのものになる)。
    国別の正確な値は `CountryResult.versions` が持つ。docs/api.md 参照。

    分類器の版は国をまたいで同一のはずだが、念のため連結する。
    """

    def joined(values: Sequence[str]) -> str:
        return ",".join(sorted(set(values)))

    return Versions(
        query_profile_version=joined([result.versions.query_profile_version for result in results]),
        score_version=SCORE_VERSION,
        classifier_version=joined([result.versions.classifier_version for result in results]),
        prompt_version=joined([result.versions.prompt_version for result in results]),
    )


class ScanService:
    """1トピック・複数国のスキャンを実行する。"""

    def __init__(
        self,
        serpapi: SerpApiClient,
        classifier: LlmClassifier,
        brief_writer: BriefWriter,
        *,
        profiles_dir: Path | None = None,
    ) -> None:
        self._scanner = CountryScanner(serpapi, classifier)
        self._brief_writer = brief_writer
        self._profiles_dir = profiles_dir

    def scan(
        self,
        topic_id: TopicId,
        countries: Sequence[Country],
        *,
        scan_id: str,
        scan_time: datetime,
        enrich: bool = True,
    ) -> ScanOutput:
        """指定した国をスキャンし、ランキングと Brief まで組み立てる。

        Args:
            enrich: Top2 の Maps 取得と Top1 の Opportunity Brief 生成を行うか。
                結果を表示しない呼び出し元(要約だけを出す CLI など)が、
                使わない外部 API 呼び出しを避けられるようにする。
        """
        if not countries:
            message = "countries must not be empty"
            raise ValueError(message)

        with log_context(scan_id=scan_id, topic=topic_id.value):
            profiles = self._load_profiles(topic_id, countries)
            outcomes = {
                country: (
                    self._scanner.scan(profile, scan_id=scan_id, scan_time=scan_time)
                    if profile is not None
                    else build_failed_outcome(
                        topic_id, country, scan_id=scan_id, scan_time=scan_time
                    )
                )
                for country, profile in profiles.items()
            }

            ordered = sorted((outcome.result for outcome in outcomes.values()), key=_ranking_key)
            brief: OpportunityBrief | None = None
            if enrich:
                outcomes = self._attach_maps_to_top_countries(
                    outcomes, ordered, profiles, scan_time=scan_time
                )
                brief = self._write_brief(outcomes, ordered, topic_id)

            results = [outcomes[result.country].result for result in ordered]
            completed = [
                result.country for result in results if result.status is not CountryStatus.FAILED
            ]
            summary = ScanSummary(
                scan_id=scan_id,
                topic_id=topic_id,
                status=_scan_status(results),
                progress=ScanProgress(total=len(countries), completed=len(completed)),
                completed_countries=completed,
                ranking=[_to_ranking_entry(result) for result in results],
                opportunity_brief=brief,
                versions=_summary_versions(results),
            )
            rankable = [result for result in results if result.status in RANKABLE_STATUSES]
            _LOGGER.info(
                "scan completed",
                extra={
                    "status": summary.status.value,
                    "ranked": [entry.country.value for entry in summary.ranking],
                    "has_brief": brief is not None,
                    # `INSUFFICIENT_EVIDENCE` はエラーではないので status は
                    # `completed` のままだが、全国がそうなるのは外形障害である。
                    # 監視が検知できるよう件数を出す(docs/scoring.md 7章)。
                    "rankable_countries": len(rankable),
                    "insufficient_countries": sum(
                        1
                        for result in results
                        if result.status is CountryStatus.INSUFFICIENT_EVIDENCE
                    ),
                    "failed_countries": sum(
                        1 for result in results if result.status is CountryStatus.FAILED
                    ),
                },
            )
            return ScanOutput(summary=summary, outcomes=outcomes)

    # --- 内部 -------------------------------------------------------------------------

    def _load_profiles(
        self, topic_id: TopicId, countries: Sequence[Country]
    ) -> dict[Country, QueryProfile | None]:
        """国ごとに QueryProfile を読む。**1件の失敗で全体を止めない。**

        読めなかった国は `None` とし、呼び出し側が `FAILED` として扱う。
        1か国の YAML が欠けているだけで健全な4か国の結果まで失うのは
        docs/requirements.md「Reliability」に反する。
        """
        profiles: dict[Country, QueryProfile | None] = {}
        for country in countries:
            with log_context(country=country.value):
                try:
                    profiles[country] = load_query_profile(topic_id, country, self._profiles_dir)
                except ConfigError as exc:
                    _LOGGER.warning(
                        "query profile could not be loaded; the country is marked failed",
                        extra={"error": type(exc).__name__},
                    )
                    profiles[country] = None
        return profiles

    def _attach_maps_to_top_countries(
        self,
        outcomes: dict[Country, CountryScanOutcome],
        ordered: Sequence[CountryResult],
        profiles: dict[Country, QueryProfile | None],
        *,
        scan_time: datetime,
    ) -> dict[Country, CountryScanOutcome]:
        """ランキング確定後、Top 2 についてのみ Maps を取得する。

        スコアには影響しない(Maps は Core Source ではない)。読み込み済みの
        プロファイルを再利用し、YAML を二重に読まない。
        """
        updated = dict(outcomes)
        rankable = [result for result in ordered if result.status in RANKABLE_STATUSES]
        for result in rankable[:MAPS_COUNTRY_LIMIT]:
            profile = profiles.get(result.country)
            if profile is None:
                continue
            updated[result.country] = self._scanner.attach_maps(
                updated[result.country], profile, scan_time=scan_time
            )
        return updated

    def _write_brief(
        self,
        outcomes: dict[Country, CountryScanOutcome],
        ordered: Sequence[CountryResult],
        topic_id: TopicId,
    ) -> OpportunityBrief | None:
        """Top 1 について Opportunity Brief を生成する。

        ランキング可能な国が1つも無ければ生成しない。生成結果はアダプタ側で
        `validate_brief` を通っており、検証に落ちれば `None` が返る。
        """
        top = next((result for result in ordered if result.status in RANKABLE_STATUSES), None)
        if top is None:
            _LOGGER.info("opportunity brief skipped: no rankable country")
            return None
        outcome = outcomes[top.country]
        if outcome.evaluation is None:
            return None
        with log_context(country=top.country.value):
            try:
                pack = build_evidence_pack(
                    top.country, topic_id, outcome.evaluation, outcome.result.evidence
                )
                brief = self._brief_writer.write_brief(pack)
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
