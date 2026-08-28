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
from gapatlas.adapters.llm.versions import CLASSIFIER_VERSION, PROMPT_VERSION
from gapatlas.adapters.serpapi.protocol import SerpApiClient
from gapatlas.application.country_scan import CountryScanner, CountryScanOutcome
from gapatlas.application.evidence import build_evidence_pack
from gapatlas.application.logging_context import log_context
from gapatlas.config.query_profile_loader import load_query_profile
from gapatlas.domain.models.common import Country, CountryStatus, ScanStatus, TopicId
from gapatlas.domain.models.result import (
    CountryResult,
    OpportunityBrief,
    RankingEntry,
    ScanProgress,
    ScanSummary,
    Versions,
)
from gapatlas.domain.scoring.constants import SCORE_VERSION

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

    @property
    def country_results(self) -> dict[Country, CountryResult]:
        return {country: outcome.result for country, outcome in self.outcomes.items()}


def _ranking_key(result: CountryResult) -> tuple[int, int, int, str]:
    """`need_gap_score` 降順。`None` は末尾へ回す(docs/api.md)。

    同点は `confidence` 降順 → 国コード昇順で決める。**順序を決定的にするため**
    であり、意味づけはしていない。
    """
    has_score = 0 if result.need_gap_score is None else 1
    score = result.need_gap_score or 0
    return (-has_score, -score, -result.confidence, result.country.value)


def _to_ranking_entry(result: CountryResult) -> RankingEntry:
    components = result.components

    def public(value: float | None) -> int | None:
        return None if value is None else round(value)

    return RankingEntry(
        country=result.country,
        status=result.status,
        need_gap_score=result.need_gap_score,
        confidence=result.confidence,
        demand=public(components.demand),
        pain=public(components.pain),
        solution_gap=public(components.solution_gap),
        news_urgency=public(components.news_urgency),
    )


def _scan_status(results: Sequence[CountryResult]) -> ScanStatus:
    if any(result.status is CountryStatus.FAILED for result in results):
        return ScanStatus.PARTIALLY_FAILED
    return ScanStatus.COMPLETED


def _summary_versions(profile_versions: Sequence[str]) -> Versions:
    """スキャン全体のバージョン識別子。

    `query_profile_version` は国ごとに異なるため、**スキャンに使った全国分を
    昇順で連結**する。国別の値は `CountryResult.versions` が持つ。
    """
    return Versions(
        query_profile_version=",".join(sorted(set(profile_versions))),
        score_version=SCORE_VERSION,
        classifier_version=CLASSIFIER_VERSION,
        prompt_version=PROMPT_VERSION,
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
    ) -> ScanOutput:
        """指定した国をスキャンし、ランキングと Brief まで組み立てる。"""
        if not countries:
            message = "countries must not be empty"
            raise ValueError(message)

        with log_context(scan_id=scan_id, topic=topic_id.value):
            outcomes = {
                country: self._scanner.scan(
                    load_query_profile(topic_id, country, self._profiles_dir),
                    scan_id=scan_id,
                    scan_time=scan_time,
                )
                for country in countries
            }

            ordered = sorted((outcome.result for outcome in outcomes.values()), key=_ranking_key)
            outcomes = self._attach_maps_to_top_countries(
                outcomes, ordered, topic_id, scan_time=scan_time
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
                versions=_summary_versions(
                    [result.versions.query_profile_version for result in results]
                ),
            )
            _LOGGER.info(
                "scan completed",
                extra={
                    "status": summary.status.value,
                    "ranked": [entry.country.value for entry in summary.ranking],
                    "has_brief": brief is not None,
                },
            )
            return ScanOutput(summary=summary, outcomes=outcomes)

    # --- 内部 -------------------------------------------------------------------------

    def _attach_maps_to_top_countries(
        self,
        outcomes: dict[Country, CountryScanOutcome],
        ordered: Sequence[CountryResult],
        topic_id: TopicId,
        *,
        scan_time: datetime,
    ) -> dict[Country, CountryScanOutcome]:
        """ランキング確定後、Top 2 についてのみ Maps を取得する。

        スコアには影響しない(Maps は Core Source ではない)。
        """
        updated = dict(outcomes)
        rankable = [result for result in ordered if result.status in RANKABLE_STATUSES]
        for result in rankable[:MAPS_COUNTRY_LIMIT]:
            profile = load_query_profile(topic_id, result.country, self._profiles_dir)
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
            pack = build_evidence_pack(
                top.country, topic_id, outcome.evaluation, outcome.result.evidence
            )
            brief = self._brief_writer.write_brief(pack)
            if brief is None:
                _LOGGER.warning("opportunity brief was not produced")
            return brief
