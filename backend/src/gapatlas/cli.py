"""GapAtlas の CLI。

```bash
gapatlas scan --topic elder_care --country JP --mode fixture
gapatlas scan --topic elder_care --all
```

`SerpApi Fixture -> Normalize -> Scoring -> Confidence -> JSON Output` を
コマンド1本で通すための入口(docs/requirements.md「最優先は次の End-to-End を
成立させること」)。

**結果は標準出力へ JSON、ログは標準エラーへ JSON1行**で出す。パイプで結果だけを
取り出せるようにするため。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any, Final

from gapatlas.adapters.dynamodb.factory import create_scan_repository
from gapatlas.adapters.llm.factory import create_brief_writer, create_llm_classifier
from gapatlas.adapters.s3.factory import create_scan_archive
from gapatlas.adapters.serpapi.factory import create_serpapi_client
from gapatlas.application.logging_context import configure_logging
from gapatlas.application.scan_service import ScanOutput, ScanService
from gapatlas.config.errors import ConfigError
from gapatlas.config.settings import LlmMode, SerpApiMode, Settings, load_settings
from gapatlas.domain.models.common import Country, TopicId
from gapatlas.domain.models.errors import GapAtlasError
from gapatlas.domain.models.result import CountryResult

EXIT_OK = 0
EXIT_ERROR = 1

SCAN_ID_PATTERN: Final[re.Pattern[str]] = re.compile(r"[A-Za-z0-9_-]{1,64}")
"""`--scan-id` に許す形。ストレージキーになるためパス区切りを含めない。"""


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="gapatlas", description="GapAtlas CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    scan = subparsers.add_parser("scan", help="トピックと国のスキャンを実行する")
    scan.add_argument(
        "--topic",
        default=TopicId.ELDER_CARE.value,
        choices=[member.value for member in TopicId],
        help="対象トピック",
    )
    target = scan.add_mutually_exclusive_group()
    target.add_argument(
        "--country",
        choices=[member.value for member in Country],
        help="対象国。省略時は JP",
    )
    target.add_argument("--all", action="store_true", help="対象国すべてをスキャンする")
    scan.add_argument(
        "--mode",
        choices=[member.value for member in SerpApiMode],
        help="SerpApi の動作モード。省略時は環境変数 SERPAPI_MODE",
    )
    scan.add_argument(
        "--llm-mode",
        choices=[member.value for member in LlmMode],
        help="LLM の動作モード。省略時は環境変数 LLM_MODE",
    )
    scan.add_argument(
        "--scan-time",
        help="スキャン基準時刻(ISO8601)。省略時は現在時刻。テストは必ず指定する",
    )
    scan.add_argument("--scan-id", help="スキャンID。省略時は自動生成")
    scan.add_argument("--full", action="store_true", help="要約ではなく完全な結果 JSON を出力する")
    return parser.parse_args(argv)


def _resolve_settings(args: argparse.Namespace) -> Settings:
    """環境変数を読み、CLI 引数で上書きする。"""
    settings = load_settings()
    overrides: dict[str, Any] = {}
    if args.mode is not None:
        overrides["serpapi_mode"] = SerpApiMode(args.mode)
    if args.llm_mode is not None:
        overrides["llm_mode"] = LlmMode(args.llm_mode)
    return settings.model_copy(update=overrides) if overrides else settings


def _resolve_scan_time(raw: str | None) -> datetime:
    """`--scan-time` を UTC aware な datetime にする。

    省略時のみ現在時刻を使う。`domain/scoring` は現在時刻を取得しないため、
    **時刻の決定はここが唯一の場所**である。

    Raises:
        ConfigError: ISO 8601 として解釈できない場合。生のトレースバックを
            出さず `{"error": ...}` の契約を守るため、型を変換する。
    """
    if raw is None:
        return datetime.now(tz=UTC)
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError as exc:
        message = f"--scan-time must be an ISO 8601 datetime, got {raw!r}"
        raise ConfigError(message) from exc
    return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)


def _resolve_scan_id(raw: str | None) -> str:
    """`--scan-id` を検証する。省略時は生成する。

    scan_id は Phase 7 で S3 キーと DynamoDB のパーティションキーになる予定
    なので、任意文字列を通さない。

    Raises:
        ConfigError: 形式が不正な場合。
    """
    if raw is None:
        return f"scan_{uuid.uuid4().hex[:12]}"
    if not SCAN_ID_PATTERN.fullmatch(raw):
        message = (
            "--scan-id must match "
            f"{SCAN_ID_PATTERN.pattern} (letters, digits, '_' and '-'), got {raw!r}"
        )
        raise ConfigError(message)
    return raw


def _country_summary(result: CountryResult) -> dict[str, Any]:
    """依頼書 §31 が求める最小の出力形。"""
    components = result.components

    def public(value: float | None) -> int | None:
        return None if value is None else round(value)

    return {
        "country": result.country.value,
        "topic": result.topic_id.value,
        "status": result.status.value,
        "demand": public(components.demand),
        "pain": public(components.pain),
        "solution_gap": public(components.solution_gap),
        "news_urgency": public(components.news_urgency),
        "need_gap_score": result.need_gap_score,
        "confidence": result.confidence,
    }


def _render(output: ScanOutput, countries: Sequence[Country], *, full: bool) -> dict[str, Any]:
    if full:
        return {
            "summary": output.summary.model_dump(mode="json"),
            "countries": {
                country.value: output.outcomes[country].result.model_dump(mode="json")
                for country in countries
            },
        }
    if len(countries) == 1:
        return _country_summary(output.outcomes[countries[0]].result)
    return {
        "scan_id": output.summary.scan_id,
        "topic": output.summary.topic_id.value,
        "status": output.summary.status.value,
        "ranking": [
            _country_summary(output.outcomes[entry.country].result)
            for entry in output.summary.ranking
        ],
        "opportunity_brief": (
            output.summary.opportunity_brief.model_dump(mode="json")
            if output.summary.opportunity_brief is not None
            else None
        ),
    }


def main(argv: Sequence[str] | None = None) -> int:
    """CLI の入口。終了コードを返す。"""
    args = _parse_args(argv)

    try:
        settings = _resolve_settings(args)
        scan_time = _resolve_scan_time(args.scan_time)
        scan_id = _resolve_scan_id(args.scan_id)
    except ConfigError as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return EXIT_ERROR

    configure_logging(settings.log_level.value, stream=sys.stderr)

    countries = (
        list(Country) if args.all else [Country(args.country) if args.country else Country.JP]
    )

    try:
        service = ScanService(
            create_serpapi_client(settings),
            create_llm_classifier(settings),
            create_brief_writer(settings),
            repository=create_scan_repository(settings),
            archive=create_scan_archive(settings),
        )
        output = service.scan(
            TopicId(args.topic),
            countries,
            scan_id=scan_id,
            scan_time=scan_time,
            # 要約だけを出す単一国モードでは Maps と Brief を表示しないので、
            # 使わない外部 API 呼び出しを行わない。
            enrich=args.full or len(countries) > 1,
        )
    except GapAtlasError as exc:
        print(
            json.dumps({"error": f"{type(exc).__name__}: {exc}"}, ensure_ascii=False),
            file=sys.stderr,
        )
        return EXIT_ERROR

    print(json.dumps(_render(output, countries, full=args.full), ensure_ascii=False, indent=2))
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
