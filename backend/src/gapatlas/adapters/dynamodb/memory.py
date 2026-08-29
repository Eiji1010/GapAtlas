"""インメモリの `ScanRepository`。

AWS へ接続せずに API と CLI を動かすための実装。`SERPAPI_MODE=fixture` /
`LLM_MODE=stub` と同じ思想で、**外部通信ゼロで全機能が動く**状態を保つ
(AGENTS.md 絶対ルール)。

プロセス内にしか残らない。永続化が要る場面では DynamoDB 実装を使う。
"""

from __future__ import annotations

from gapatlas.domain.models.common import Country, ScanStatus
from gapatlas.domain.models.result import CountryResult, ScanSummary

FINISHED_STATUSES = frozenset({ScanStatus.COMPLETED, ScanStatus.PARTIALLY_FAILED})
"""これ以上「途中経過」で上書きしてはいけない状態。"""


class InMemoryScanRepository:
    """辞書に保持するだけの `ScanRepository`。"""

    def __init__(self) -> None:
        self._scans: dict[str, ScanSummary] = {}
        self._countries: dict[tuple[str, Country], CountryResult] = {}

    def save_scan(self, summary: ScanSummary) -> None:
        self._scans[summary.scan_id] = summary

    def save_scan_if_unfinished(self, summary: ScanSummary) -> bool:
        stored = self._scans.get(summary.scan_id)
        if stored is not None and stored.status in FINISHED_STATUSES:
            return False
        self._scans[summary.scan_id] = summary
        return True

    def save_country(self, result: CountryResult) -> None:
        self._countries[(result.scan_id, result.country)] = result

    def get_scan(self, scan_id: str) -> ScanSummary | None:
        return self._scans.get(scan_id)

    def get_country(self, scan_id: str, country: Country) -> CountryResult | None:
        return self._countries.get((scan_id, country))

    def list_countries(self, scan_id: str) -> list[CountryResult]:
        return [
            result
            for (stored_scan_id, _country), result in sorted(
                self._countries.items(), key=lambda item: item[0][1].value
            )
            if stored_scan_id == scan_id
        ]
