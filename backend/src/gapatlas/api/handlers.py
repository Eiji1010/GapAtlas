"""4エンドポイントのユースケース。

HTTP から切り離してテストできるよう、`ApiService` は素の `dict` を返す。
`Request` / `statusCode` を知っているのは `lambda_handlers.py` だけ。

**スコア計算とスキャンの実行をここへ書かない。** `POST /scans` は SCAN META を
作って SQS へジョブを投げるだけで即座に返す(docs/requirements.md「重い SerpApi
処理を HTTP Request 内で実行してはいけない」)。
"""

from __future__ import annotations

import logging
import re
from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any, Final

from gapatlas.adapters.dynamodb.protocol import ScanRepository
from gapatlas.adapters.sqs.protocol import JobQueue
from gapatlas.api.errors import CountryNotFoundError, InvalidRequestError, ScanNotFoundError
from gapatlas.application.jobs import ScanJob
from gapatlas.application.logging_context import log_context
from gapatlas.application.scan_service import to_public_component
from gapatlas.config.settings import Settings
from gapatlas.domain.models.common import Country, CountryStatus, ScanStatus, TopicId
from gapatlas.domain.models.result import CountryResult, ScanProgress, ScanSummary, Versions
from gapatlas.domain.scoring.constants import SCORE_VERSION

_LOGGER: Final[logging.Logger] = logging.getLogger(__name__)

SCAN_ID_PATTERN: Final[re.Pattern[str]] = re.compile(r"[A-Za-z0-9_-]{1,64}")
"""`scan_id` に許す形。`cli.py` の `--scan-id` と同じ制約。

DynamoDB のパーティションキーと S3 のキーになるため、パス区切りを含む任意
文字列を通さない。形が違う値はストレージへ問い合わせずに 404 とする
(`../` のようなパスを下層へ渡さない)。
"""

CREATE_SCAN_FIELDS: Final[frozenset[str]] = frozenset({"topic_id", "countries"})
"""`POST /scans` の本文が持てるキー(docs/api.md)。

未知のキーは弾く。`country` と `countries` の綴り違いを黙って受け取ると、
1か国のつもりが5か国スキャンされる。domain モデルの `extra="forbid"` と
同じ方針。
"""

UNRESOLVED_VERSION: Final[str] = "pending"
"""スキャン作成時点で確定していないバージョン識別子。

`query_profile_version` は国別 YAML を読むまで、`classifier_version` /
`prompt_version` は実際に使う LLM アダプタを組み立てるまで決まらない。
`POST /scans` でそれらを解決すると「重い処理を HTTP 内で実行しない」に反する
ため、Worker が最終概要を保存する時点で実値へ置き換わる前提で置く。
"""

TERMINAL_COUNTRY_STATUSES: Final[frozenset[CountryStatus]] = frozenset(
    {CountryStatus.COMPLETED, CountryStatus.INSUFFICIENT_EVIDENCE, CountryStatus.FAILED}
)
"""処理が終わった国の status。進捗の分子を数えるのに使う。"""


def _topic_label(topic_id: TopicId) -> str:
    """`elder_care` -> `Elder Care`。ラベルをハードコードしない。"""
    return topic_id.value.replace("_", " ").title()


def _parse_topic_id(value: Any) -> TopicId:
    """`topic_id` を `TopicId` へ変換する。

    Raises:
        InvalidRequestError: 未知のトピック、または文字列でない場合(400)。
    """
    if not isinstance(value, str):
        message = "topic_id is required and must be a string"
        raise InvalidRequestError(message)
    try:
        return TopicId(value)
    except ValueError as exc:
        allowed = ", ".join(member.value for member in TopicId)
        message = f"unknown topic_id: {value!r}; allowed: {allowed}"
        raise InvalidRequestError(message) from exc


def parse_country(value: str) -> Country:
    """パス変数や本文の国コードを `Country` へ変換する。大文字小文字は問わない。

    Raises:
        InvalidRequestError: 対象外の国の場合(400)。
    """
    try:
        return Country(value.strip().upper())
    except ValueError as exc:
        allowed = ", ".join(member.value for member in Country)
        message = f"unknown country: {value!r}; allowed: {allowed}"
        raise InvalidRequestError(message) from exc


def _parse_countries(value: Any) -> list[Country]:
    """`countries` を `Country` のリストへ変換する。

    省略(キーが無い、または `null`)なら MVP 対象の全5か国。重複は最初の
    出現位置を残して落とす。

    Raises:
        InvalidRequestError: リストでない、空、または未知の国を含む場合(400)。
    """
    if value is None:
        return list(Country)
    if not isinstance(value, list):
        message = "countries must be an array of country codes"
        raise InvalidRequestError(message)
    if not value:
        message = "countries must not be empty"
        raise InvalidRequestError(message)

    parsed: list[Country] = []
    for item in value:
        if not isinstance(item, str):
            message = "countries must be an array of country codes"
            raise InvalidRequestError(message)
        country = parse_country(item)
        if country not in parsed:
            parsed.append(country)
    return parsed


def _initial_versions() -> Versions:
    """作成直後の SCAN META が持つバージョン識別子。

    `score_version` はデプロイ済みコードの定数なので確定値を入れる。残りは
    確定していないため `UNRESOLVED_VERSION` を置く。
    """
    return Versions(
        query_profile_version=UNRESOLVED_VERSION,
        score_version=SCORE_VERSION,
        classifier_version=UNRESOLVED_VERSION,
        prompt_version=UNRESOLVED_VERSION,
    )


def _public_scores(values: Mapping[str, float | None]) -> dict[str, int | None]:
    """内部 float を公開表現の int へ丸める。

    `ranking` と同じ `to_public_component` を通す。別々に丸めると同じ画面で
    1ずれた値が出る(docs/scoring.md「四捨五入」)。
    """
    return {key: to_public_component(value) for key, value in values.items()}


def country_payload(result: CountryResult) -> dict[str, Any]:
    """`GET /scans/{scan_id}/countries/{country}` の本文。

    Screen 2 が表示する詳細(`trends` / `related_queries` / `search_results` /
    `news_results` / `maps_results`)も返す。値はすべて `CountryResult` に
    保存されているものであり、**ここで推測して埋めない**
    (AGENTS.md「Evidence に存在しない事実を断定しない」)。

    `maps_results` は **Top 2 countries のみ非 `null`**。`null` は「取得して
    いない」を意味し、空配列(「取得したが0件」)とは区別する。
    """
    components = result.components
    breakdown = result.confidence_breakdown
    return {
        "scan_id": result.scan_id,
        "topic_id": result.topic_id.value,
        "country": result.country.value,
        "status": result.status.value,
        "need_gap_score": result.need_gap_score,
        "confidence": result.confidence,
        "components": _public_scores(
            {
                "demand": components.demand,
                "pain": components.pain,
                "solution_gap": components.solution_gap,
                "news_urgency": components.news_urgency,
            }
        ),
        "confidence_breakdown": _public_scores(
            {
                "data_completeness": breakdown.data_completeness,
                "sample_sufficiency": breakdown.sample_sufficiency,
                "localization_quality": breakdown.localization_quality,
                "source_agreement": breakdown.source_agreement,
                "freshness": breakdown.freshness,
            }
        ),
        "source_status": {
            source.value: status.value for source, status in result.source_status.items()
        },
        "evidence": [item.model_dump(mode="json") for item in result.evidence],
        "trends": result.trends.model_dump(mode="json") if result.trends is not None else None,
        "related_queries": [item.model_dump(mode="json") for item in result.related_queries],
        "search_results": [item.model_dump(mode="json") for item in result.search_results],
        "news_results": [item.model_dump(mode="json") for item in result.news_results],
        "maps_results": (
            [place.model_dump(mode="json") for place in result.maps_results]
            if result.maps_results is not None
            else None
        ),
        "versions": result.versions.model_dump(mode="json"),
        "computed_at": result.computed_at.isoformat(),
    }


def _derive_progress(
    summary: ScanSummary, results: Sequence[CountryResult]
) -> tuple[ScanProgress, list[Country]]:
    """保存済みの COUNTRY item から進捗を数える。

    `completed` は **`FAILED` 以外の終了国数**。`ScanService` が最終概要で
    使う定義と同じにする。定義を変えると、完了した瞬間に進捗の数字が飛ぶ。
    """
    finished = [result for result in results if result.status in TERMINAL_COUNTRY_STATUSES]
    completed = [result.country for result in finished if result.status is not CountryStatus.FAILED]
    # 保存済みの国数が概要の `total` を超えることは通常無いが、超えたときに
    # `ScanProgress` の検証(completed <= total)で 500 にしない。
    total = max(summary.progress.total, len(finished))
    return ScanProgress(total=total, completed=len(completed)), completed


class ApiService:
    """4エンドポイントのユースケース。HTTP を知らない。"""

    def __init__(self, repository: ScanRepository, queue: JobQueue, settings: Settings) -> None:
        """
        Args:
            repository: 最新結果の読み書き(DynamoDB / インメモリ)。
            queue: 国別ジョブの投入先(SQS / インメモリ)。
            settings: 実行時設定。CORS のように HTTP 層が使う値も含むため、
                入口が組み立てた同じインスタンスを保持する。
        """
        self._repository = repository
        self._queue = queue
        self._settings = settings

    @property
    def settings(self) -> Settings:
        """入口(`lambda_handlers`)が CORS 判定に使う。"""
        return self._settings

    def list_topics(self) -> dict[str, Any]:
        """`GET /api/v1/topics`。

        利用可能な Topic と Country は `TopicId` / `Country` から組み立てる。
        国の並びは Enum の宣言順(docs/api.md の例と同じ JP・US・GB・DE・IN)。
        """
        countries = [{"country": country.value, "label": country.label} for country in Country]
        return {
            "topics": [
                {
                    "topic_id": topic.value,
                    "label": _topic_label(topic),
                    "countries": countries,
                }
                for topic in TopicId
            ]
        }

    def create_scan(
        self, body: Mapping[str, Any], *, scan_id: str, scan_time: datetime
    ) -> dict[str, Any]:
        """`POST /api/v1/scans`。**即座に返す。**

        SCAN META を `status=processing` で作り、国ごとの `ScanJob` を投入する
        だけ。SerpApi も LLM もここでは呼ばない(SLO: p95 < 800ms)。

        `scan_id` と `scan_time` は引数で受け取る。生成をここで行うと同じ入力で
        結果が変わり、テストが非決定的になるため
        (`domain/scoring` が時刻を引数で受け取るのと同じ方針)。

        Args:
            body: リクエスト本文(JSON オブジェクト)。
            scan_id: 入口が生成した ID。
            scan_time: スキャン全体で共有する基準時刻。全ジョブへ同じ値を配る。

        Raises:
            InvalidRequestError: topic_id / countries が不正な場合(400)。
        """
        unknown = sorted(set(body) - CREATE_SCAN_FIELDS)
        if unknown:
            message = f"unknown fields in request body: {', '.join(unknown)}"
            raise InvalidRequestError(message)

        topic_id = _parse_topic_id(body.get("topic_id"))
        countries = _parse_countries(body.get("countries"))

        with log_context(scan_id=scan_id, topic=topic_id.value):
            summary = ScanSummary(
                scan_id=scan_id,
                topic_id=topic_id,
                status=ScanStatus.PROCESSING,
                progress=ScanProgress(total=len(countries), completed=0),
                completed_countries=[],
                ranking=[],
                opportunity_brief=None,
                versions=_initial_versions(),
            )
            # META を先に保存する。Worker が先に走っても対象のスキャンを
            # 必ず読めるようにするため。
            self._repository.save_scan(summary)
            self._queue.enqueue(
                [
                    ScanJob(
                        scan_id=scan_id,
                        topic_id=topic_id,
                        country=country,
                        scan_time=scan_time,
                        countries=countries,
                    )
                    for country in countries
                ]
            )
            _LOGGER.info(
                "scan accepted",
                extra={"countries": [country.value for country in countries]},
            )
            return {"scan_id": scan_id, "status": summary.status.value}

    def get_scan(self, scan_id: str) -> dict[str, Any]:
        """`GET /api/v1/scans/{scan_id}`。Frontend が2秒間隔で叩く。

        **`progress` と `completed_countries` は保存済みの COUNTRY item から
        算出する**(保存された概要をそのまま返さない)。Worker は最後の1国が
        終わった時点でしか概要を保存しないため、概要の `progress` は処理中ずっと
        `0 / N` のままになる。それを返すと Polling しても進捗が動かない。

        `status` / `ranking` / `opportunity_brief` / `versions` は保存された
        概要をそのまま返す。ランキングの並べ替えと Brief の生成は application
        層の責務であり、api 層で作り直さない。したがって処理中は `ranking` が
        空になる(完了報告の申し送り事項)。

        Raises:
            ScanNotFoundError: `scan_id` が存在しない場合(404)。
        """
        summary = self._load_summary(scan_id)
        progress, completed = _derive_progress(summary, self._repository.list_countries(scan_id))
        payload = summary.model_dump(mode="json")
        payload["progress"] = progress.model_dump(mode="json")
        payload["completed_countries"] = [country.value for country in completed]
        return payload

    def get_country(self, scan_id: str, country: str) -> dict[str, Any]:
        """`GET /api/v1/scans/{scan_id}/countries/{country}`。

        Raises:
            InvalidRequestError: 対象外の国コードの場合(400)。
            ScanNotFoundError: スキャン自体が無い場合(404)。
            CountryNotFoundError: スキャンはあるが該当国が無い場合(404)。
        """
        parsed = parse_country(country)
        self._require_valid_scan_id(scan_id)

        result = self._repository.get_country(scan_id, parsed)
        if result is not None:
            return country_payload(result)

        # 見つかったときは読み取り1回で済ませる。区別が要るときだけ META を読む。
        if self._repository.get_scan(scan_id) is None:
            raise ScanNotFoundError()
        raise CountryNotFoundError(parsed.value)

    # --- 内部 -------------------------------------------------------------------------

    def _require_valid_scan_id(self, scan_id: str) -> None:
        """`scan_id` の形を確認する。

        形が違う値は「存在しない」として 404 にする。400 にしないのは、
        docs/api.md のエラー表で 400 が topic_id / country 専用のため。
        """
        if not SCAN_ID_PATTERN.fullmatch(scan_id):
            raise ScanNotFoundError()

    def _load_summary(self, scan_id: str) -> ScanSummary:
        self._require_valid_scan_id(scan_id)
        summary = self._repository.get_scan(scan_id)
        if summary is None:
            raise ScanNotFoundError()
        return summary
