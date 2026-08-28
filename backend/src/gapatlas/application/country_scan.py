"""1国分のスキャン。取得 → 正規化 → 分類 → 評価 → `CountryResult`。

**1つのソースが失敗してもシステム全体を止めない**(docs/requirements.md
「Reliability」)。ソース単位で例外を捕捉し、そのソースを `MISSING` として
記録して残りで評価する。欠けている事実は Evidence Confidence が反映する。

`domain/scoring` は `NormalizedEvidence.fetches` を信じるだけなので、
**「取得できたが中身が空」を `MISSING` と判定するのはこの層の責務**である。
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Final

from gapatlas.adapters.llm.errors import LlmError
from gapatlas.adapters.llm.protocol import LlmClassifier
from gapatlas.adapters.llm.versions import CLASSIFIER_VERSION, PROMPT_VERSION
from gapatlas.adapters.serpapi.errors import SerpApiError
from gapatlas.adapters.serpapi.normalize import (
    normalize_maps_results,
    normalize_news_results,
    normalize_related_queries,
    normalize_search_results,
    normalize_trends_timeseries,
)
from gapatlas.adapters.serpapi.protocol import SerpApiClient
from gapatlas.application.evidence import build_evidence
from gapatlas.application.logging_context import log_context
from gapatlas.domain.models.classification import (
    ClassifiedEvidence,
    ClassifiedNewsArticle,
    ClassifiedRisingQuery,
    ClassifiedSearchResult,
)
from gapatlas.domain.models.common import (
    CORE_SOURCES,
    Country,
    CountryStatus,
    SourceName,
    SourceStatus,
    TopicId,
)
from gapatlas.domain.models.normalized import (
    MapsPlace,
    NewsArticle,
    NormalizedEvidence,
    RisingQuery,
    SearchResultItem,
    SourceFetch,
    TrendsTimeseries,
)
from gapatlas.domain.models.query_profile import QueryProfile
from gapatlas.domain.models.result import CountryResult, Versions
from gapatlas.domain.models.scores import ConfidenceBreakdown, ScoreComponents
from gapatlas.domain.scoring.constants import SCORE_VERSION, WINDOW_WEEKS
from gapatlas.domain.scoring.engine import CountryEvaluation, evaluate_country

_LOGGER: Final[logging.Logger] = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class RawSources:
    """S3 raw/ へ無加工で保存するための生レスポンス(Phase 7 で使う)。"""

    payloads: dict[SourceName, dict[str, Any]]


@dataclass(frozen=True, slots=True)
class CountryScanOutcome:
    """1国分のスキャン結果。後続の永続化・API・Brief 生成が使う。"""

    result: CountryResult
    evidence: NormalizedEvidence
    classified: ClassifiedEvidence
    evaluation: CountryEvaluation | None
    """想定外の例外で評価まで到達できなかった場合は None(`status = FAILED`)。"""

    raw: RawSources


UNKNOWN_QUERY_PROFILE_VERSION: Final[str] = "unknown"
"""QueryProfile を読めなかったときに記録する版。実在の版と区別できる値にする。"""


def build_versions(
    query_profile_version: str,
    *,
    classifier_version: str = CLASSIFIER_VERSION,
    prompt_version: str = PROMPT_VERSION,
) -> Versions:
    """結果へ記録する4つの版識別子。

    分類器の版は**実際に注入されたアダプタ**のものを使う。stub と実 LLM は
    分類ロジックもプロンプトも違うのに同じ識別子を名乗ると、結果を後から
    再現できない(docs/scoring.md 8章)。
    """
    return Versions(
        query_profile_version=query_profile_version,
        score_version=SCORE_VERSION,
        classifier_version=classifier_version,
        prompt_version=prompt_version,
    )


def build_failed_outcome(
    topic_id: TopicId,
    country: Country,
    *,
    scan_id: str,
    scan_time: datetime,
    query_profile_version: str = UNKNOWN_QUERY_PROFILE_VERSION,
    classifier_version: str = CLASSIFIER_VERSION,
    prompt_version: str = PROMPT_VERSION,
) -> CountryScanOutcome:
    """`FAILED` の結果を組み立てる。`confidence = 0`。

    QueryProfile を読めなかった場合など、スキャンを開始すらできなかった国にも
    使えるよう `profile` を要求しない(docs/scoring.md 7章の `FAILED` は
    **国単位**のステータスであり、1国の失敗で他国の結果を捨てないため)。
    """
    empty_breakdown = ConfidenceBreakdown(
        data_completeness=0.0,
        sample_sufficiency=0.0,
        localization_quality=0.0,
        source_agreement=0.0,
        freshness=0.0,
    )
    result = CountryResult(
        scan_id=scan_id,
        topic_id=topic_id,
        country=country,
        status=CountryStatus.FAILED,
        need_gap_score=None,
        confidence=0,
        components=ScoreComponents(),
        confidence_breakdown=empty_breakdown,
        source_status={
            **dict.fromkeys(CORE_SOURCES, SourceStatus.MISSING),
            # 取得を試みていないので MISSING ではなく NOT_REQUESTED。
            # 正常系と同じ5キーを必ず返す(docs/api.md の source_status)。
            SourceName.MAPS: SourceStatus.NOT_REQUESTED,
        },
        evidence=[],
        versions=build_versions(
            query_profile_version,
            classifier_version=classifier_version,
            prompt_version=prompt_version,
        ),
        computed_at=scan_time,
    )
    return CountryScanOutcome(
        result=result,
        evidence=NormalizedEvidence(),
        classified=ClassifiedEvidence(),
        evaluation=None,
        raw=RawSources(payloads={}),
    )


class CountryScanner:
    """1国分のスキャンを実行する。

    アダプタは Protocol として受け取る(docs/architecture.md「依存の向き」)。
    現在時刻は引数で受け取り、この層でも取得しない。
    """

    def __init__(self, serpapi: SerpApiClient, classifier: LlmClassifier) -> None:
        self._serpapi = serpapi
        self._classifier = classifier

    # --- 公開 API ---------------------------------------------------------------------

    def scan(
        self,
        profile: QueryProfile,
        *,
        scan_id: str,
        scan_time: datetime,
    ) -> CountryScanOutcome:
        """1国分を評価する。**例外を上へ投げない。**

        想定外の例外は `status = FAILED` として返す(docs/scoring.md 7章)。
        API の呼び出し元を 5xx にしないため(docs/api.md)。
        """
        with log_context(
            scan_id=scan_id, topic=profile.topic_id.value, country=profile.country.value
        ):
            try:
                return self._scan(profile, scan_id=scan_id, scan_time=scan_time)
            except Exception:
                _LOGGER.exception("country scan failed with an unexpected error")
                return self._failed_outcome(profile, scan_id=scan_id, scan_time=scan_time)

    # --- 内部 -------------------------------------------------------------------------

    def _scan(
        self,
        profile: QueryProfile,
        *,
        scan_id: str,
        scan_time: datetime,
    ) -> CountryScanOutcome:
        raw: dict[SourceName, dict[str, Any]] = {}
        fetches: dict[SourceName, SourceFetch] = {}

        trends = self._fetch(
            SourceName.TRENDS,
            profile,
            raw=raw,
            fetches=fetches,
            scan_time=scan_time,
            normalize=lambda payload: normalize_trends_timeseries(payload, profile.demand_queries),
            # Demand Momentum は各クエリに WINDOW_WEEKS 点を要求する
            # (docs/scoring.md 2章)。1点でもあれば OK とすると、Demand を
            # 1つも計算できないのに data_completeness が満点になり、
            # 「スコアは出ないが Confidence は最高」という出力になる。
            has_content=lambda value: any(
                len(series.points) >= WINDOW_WEEKS for series in value.series
            ),
            empty=TrendsTimeseries(),
        )
        rising = self._fetch(
            SourceName.RELATED_QUERIES,
            profile,
            raw=raw,
            fetches=fetches,
            scan_time=scan_time,
            normalize=normalize_related_queries,
            has_content=bool,
            empty=list[RisingQuery](),
        )
        search = self._fetch(
            SourceName.SEARCH,
            profile,
            raw=raw,
            fetches=fetches,
            scan_time=scan_time,
            normalize=normalize_search_results,
            has_content=bool,
            empty=list[SearchResultItem](),
        )
        news = self._fetch(
            SourceName.NEWS,
            profile,
            raw=raw,
            fetches=fetches,
            scan_time=scan_time,
            normalize=normalize_news_results,
            # 日付をパースできた記事が1件も無ければ News Urgency を出せないため
            # 「計算に使える内容が無かった」= MISSING とする(docs/scoring.md 6章)。
            has_content=lambda articles: any(
                article.published_at is not None for article in articles
            ),
            empty=list[NewsArticle](),
        )
        classified = self._classify(profile, rising, search, news, fetches)

        evidence = NormalizedEvidence(
            trends=trends,
            rising_queries=rising,
            search_results=search,
            news_articles=news,
            maps_places=None,
            fetches=fetches,
        )
        evaluation = evaluate_country(evidence, classified, profile, scan_time)

        result = CountryResult(
            scan_id=scan_id,
            topic_id=profile.topic_id,
            country=profile.country,
            status=evaluation.status,
            need_gap_score=evaluation.public_need_gap_score,
            confidence=evaluation.public_confidence,
            components=evaluation.need_gap.components,
            confidence_breakdown=evaluation.confidence.breakdown,
            source_status={
                source: evidence.source_status(source)
                for source in (*CORE_SOURCES, SourceName.MAPS)
            },
            evidence=build_evidence(evidence, classified),
            versions=build_versions(
                profile.version,
                classifier_version=self._classifier.classifier_version,
                prompt_version=self._classifier.prompt_version,
            ),
            computed_at=scan_time,
        )
        _LOGGER.info(
            "country scan completed",
            extra={
                "status": evaluation.status.value,
                "need_gap_score": evaluation.public_need_gap_score,
                "confidence": evaluation.public_confidence,
                "missing_sources": [source.value for source in evidence.missing_core_sources()],
                # Phase 7 で S3 へ払い出すまで保持し続けるため、実測を積む。
                "raw_bytes": sum(len(str(payload)) for payload in raw.values()),
            },
        )
        return CountryScanOutcome(
            result=result,
            evidence=evidence,
            classified=classified,
            evaluation=evaluation,
            raw=RawSources(payloads=raw),
        )

    def attach_maps(
        self, outcome: CountryScanOutcome, profile: QueryProfile, *, scan_time: datetime
    ) -> CountryScanOutcome:
        """Maps を追加取得して結果へ反映する。**スコアは変わらない。**

        Maps は Core Source ではない(docs/scoring.md 6章)ため、Need Gap Score も
        Evidence Confidence も再計算しない。変わるのは `source_status` と
        Evidence の一覧だけである。ランキング確定後に Top2 だけへ適用するため、
        国全体を再スキャンせずここで差分だけを足す。
        """
        if outcome.evaluation is None:
            return outcome

        with log_context(
            scan_id=outcome.result.scan_id,
            topic=profile.topic_id.value,
            country=profile.country.value,
        ):
            raw = dict(outcome.raw.payloads)
            fetches = dict(outcome.evidence.fetches)
            places = self._fetch(
                SourceName.MAPS,
                profile,
                raw=raw,
                fetches=fetches,
                scan_time=scan_time,
                normalize=normalize_maps_results,
                has_content=bool,
                empty=list[MapsPlace](),
            )
            evidence = outcome.evidence.model_copy(
                update={"maps_places": places, "fetches": fetches}
            )
            # `model_copy(update=...)` は検証を再実行しないため、
            # `CountryResult` のモデル横断バリデータを通す形で作り直す。
            result = CountryResult.model_validate(
                outcome.result.model_dump()
                | {
                    "source_status": {
                        source: evidence.source_status(source)
                        for source in (*CORE_SOURCES, SourceName.MAPS)
                    },
                    "evidence": [
                        item.model_dump() for item in build_evidence(evidence, outcome.classified)
                    ],
                }
            )
            return CountryScanOutcome(
                result=result,
                evidence=evidence,
                classified=outcome.classified,
                evaluation=outcome.evaluation,
                raw=RawSources(payloads=raw),
            )

    def _fetch[T](
        self,
        source: SourceName,
        profile: QueryProfile,
        *,
        raw: dict[SourceName, dict[str, Any]],
        fetches: dict[SourceName, SourceFetch],
        scan_time: datetime,
        normalize: Callable[[Mapping[str, Any]], T],
        has_content: Callable[[T], bool],
        empty: T,
    ) -> T:
        """1ソースを取得して正規化する。失敗しても例外を上へ投げない。

        `has_content` が False なら「取得できたが計算に使える内容が無かった」
        として `MISSING` にする(docs/scoring.md 6章の Core Source の定義)。
        """
        with log_context(source=source.value):
            try:
                payload = self._serpapi.fetch(source, profile)
            except SerpApiError as exc:
                _LOGGER.warning("source fetch failed", extra={"error": type(exc).__name__})
                fetches[source] = SourceFetch(
                    source=source,
                    status=SourceStatus.MISSING,
                    error=type(exc).__name__,
                    fetched_at=scan_time,
                )
                return empty

            raw[source] = payload
            try:
                normalized = normalize(payload)
            except SerpApiError as exc:
                _LOGGER.warning("source normalization failed", extra={"error": type(exc).__name__})
                fetches[source] = SourceFetch(
                    source=source,
                    status=SourceStatus.MISSING,
                    error=type(exc).__name__,
                    fetched_at=scan_time,
                )
                return empty

            status = SourceStatus.OK if has_content(normalized) else SourceStatus.MISSING
            if status is SourceStatus.MISSING:
                _LOGGER.info("source returned no usable content")
            fetches[source] = SourceFetch(source=source, status=status, fetched_at=scan_time)
            return normalized if status is SourceStatus.OK else empty

    def _classify(
        self,
        profile: QueryProfile,
        rising: Sequence[RisingQuery],
        search: Sequence[SearchResultItem],
        news: Sequence[NewsArticle],
        fetches: dict[SourceName, SourceFetch],
    ) -> ClassifiedEvidence:
        """3種類の分類を行う。**分類が全滅したソースは MISSING へ落とす。**

        アダプタは全滅時に `LlmError` を投げる(docs/llm-prompts.md)。既定値で
        埋めた結果をスコアへ流すと `solution_gap = 100`(最大値)が観測値として
        入り、Confidence にも反映されない。
        """
        pain = self._classify_source(
            SourceName.RELATED_QUERIES,
            rising,
            fetches,
            lambda items: [
                ClassifiedRisingQuery(item=item, classification=classification)
                for item, classification in zip(
                    items, self._classifier.classify_rising_queries(items, profile), strict=True
                )
            ],
        )
        solution = self._classify_source(
            SourceName.SEARCH,
            search,
            fetches,
            lambda items: [
                ClassifiedSearchResult(item=item, classification=classification)
                for item, classification in zip(
                    items, self._classifier.classify_search_results(items, profile), strict=True
                )
            ],
        )
        relevance = self._classify_source(
            SourceName.NEWS,
            news,
            fetches,
            lambda items: [
                ClassifiedNewsArticle(item=item, classification=classification)
                for item, classification in zip(
                    items, self._classifier.classify_news_articles(items, profile), strict=True
                )
            ],
        )
        return ClassifiedEvidence(
            rising_queries=pain, search_results=solution, news_articles=relevance
        )

    def _classify_source[ItemT, ClassifiedT](
        self,
        source: SourceName,
        items: Sequence[ItemT],
        fetches: dict[SourceName, SourceFetch],
        classify: Callable[[Sequence[ItemT]], list[ClassifiedT]],
    ) -> list[ClassifiedT]:
        if not items:
            return []
        with log_context(source=source.value):
            try:
                return classify(items)
            except (LlmError, ValueError) as exc:
                # ValueError は `zip(..., strict=True)` が投げる契約違反
                # (返却件数が入力と違う)。1ソースの分類器のバグで国全体を
                # FAILED にせず、そのソースだけ MISSING へ落とす。
                _LOGGER.warning(
                    "classification failed; treating the source as missing",
                    extra={"error": type(exc).__name__},
                )
                fetches[source] = SourceFetch(
                    source=source,
                    status=SourceStatus.MISSING,
                    error=type(exc).__name__,
                    fetched_at=fetches[source].fetched_at,
                )
                return []

    def _failed_outcome(
        self, profile: QueryProfile, *, scan_id: str, scan_time: datetime
    ) -> CountryScanOutcome:
        """想定外の例外時の結果。"""
        return build_failed_outcome(
            profile.topic_id,
            profile.country,
            scan_id=scan_id,
            scan_time=scan_time,
            query_profile_version=profile.version,
            classifier_version=self._classifier.classifier_version,
            prompt_version=self._classifier.prompt_version,
        )
