"""スキャン結果の永続化 Protocol。

DynamoDB は **Operational DB**であり、最新状態と UI 表示用データだけを持つ
(docs/architecture.md「DynamoDB」)。履歴分析は S3 + Athena が担当する。

| PK | SK | 内容 |
|---|---|---|
| `SCAN#{scan_id}` | `META` | スキャン全体の状態・進捗・ランキング・Brief |
| `SCAN#{scan_id}` | `COUNTRY#{country}` | 国別の結果と Evidence |

application 層はこの Protocol だけを見る。具体実装(DynamoDB / インメモリ)へ
依存しない(docs/architecture.md「依存の向き」)。

`runtime_checkable` は付けない。メソッド名の有無しか見ないため契約の保証に
ならない。
"""

from __future__ import annotations

from typing import Protocol

from gapatlas.domain.models.common import Country, CountryStatus
from gapatlas.domain.models.result import CountryResult, ScanSummary


class ScanRepository(Protocol):
    """スキャンの読み書き。**例外で呼び出し元を落とさないこと。**

    実装は失敗を `RepositoryError` 系へ変換する。読み取りは「無ければ None」
    を返し、例外にしない(docs/api.md の 404 は API 層が組み立てる)。
    """

    def save_scan(self, summary: ScanSummary) -> None:
        """スキャン概要を保存する。同じ `scan_id` は無条件で上書きする。

        **確定した概要を書くときだけ使うこと。** 途中経過には
        `save_scan_if_unfinished` を使う。
        """
        ...

    def save_scan_if_unfinished(self, summary: ScanSummary) -> bool:
        """保存済みの概要が**まだ終端でない場合のみ**上書きする。

        Worker は1国終わるたびに途中経過を書く。並行実行では「まだ揃って
        いない」と読んだ Worker の書き込みが、別 Worker の確定書き込みより
        **後に着地する**ことがある。無条件上書きだと完了済みのスキャンが
        `processing` へ巻き戻り、ランキングと Opportunity Brief が失われ、
        フロントエンドは終端状態に到達できず 2秒 Polling を続ける。

        Returns:
            上書きしたら `True`。既に終端だったため書かなかったら `False`。
        """
        ...

    def save_country(self, result: CountryResult) -> None:
        """国別結果を保存する。同じ `(scan_id, country)` は上書きする。"""
        ...

    def get_scan(self, scan_id: str) -> ScanSummary | None:
        """スキャン概要を取得する。存在しなければ `None`。"""
        ...

    def get_country(self, scan_id: str, country: Country) -> CountryResult | None:
        """国別結果を取得する。存在しなければ `None`。"""
        ...

    def list_countries(self, scan_id: str) -> list[CountryResult]:
        """そのスキャンの国別結果をすべて取得する。順序は国コード昇順。"""
        ...

    def list_country_statuses(self, scan_id: str) -> list[tuple[Country, CountryStatus]]:
        """国と status だけを取得する。順序は国コード昇順。

        `GET /scans/{scan_id}` は2秒間隔で叩かれ、進捗を数えるためだけに
        呼ばれる。`CountryResult` は Screen 2 用の詳細を含むため1件 20KB を
        超える。全属性を読むと、2.4KB の応答を返すために 100KB 超を毎回
        読むことになる。**進捗の算出にはこちらを使う。**
        """
        ...
