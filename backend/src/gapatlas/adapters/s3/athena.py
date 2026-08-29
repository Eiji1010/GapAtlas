"""Athena / Glue の定義。Phase 12 の土台。

**Athena を Web のリアルタイム表示に使わない。履歴分析専用**
(docs/architecture.md「Athena」)。UI が読むのは DynamoDB であり、ここで定義する
SQL はダッシュボードの裏側に置かない。

このモジュールは **SQL とスキーマ定義を文字列として提供するだけ**で、Athena へ
接続しない(AWS 認証情報が無い前提)。実行は Phase 12(Glue)と Phase 13
(Terraform)が行う。

対象は `curated/gap_scores/`(`keys.py` の `curated_key`)。配置とパーティション
(`topic` / `country` / `dt`)は `keys.py` と厳密に一致させること。**片方だけ
変更すると Athena が黙って0件を返す。**

保存形式は JSON Lines(`client.py`)。docs/architecture.md は Parquet を採らない方針と
しているが、Parquet ライブラリを依存に追加していないため JSON SerDe で読む。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final

from gapatlas.adapters.s3.errors import ArchiveError
from gapatlas.adapters.s3.keys import CURATED_DATASET, CURATED_PREFIX, DATE_FORMAT
from gapatlas.domain.models.common import Country, TopicId

GLUE_DATABASE_NAME: Final[str] = "gapatlas"
"""Glue のデータベース名。Terraform(Phase 13)と一致させること。"""

GAP_SCORES_TABLE_NAME: Final[str] = "gap_scores"
"""`curated/gap_scores/` を読むテーブル名。"""

PARTITION_COLUMNS: Final[tuple[str, ...]] = ("topic", "country", "dt")
"""パーティション列。`keys.py` のキー(`topic=` / `country=` / `dt=`)と同じ順序。"""

PROJECTION_DATE_RANGE_START: Final[str] = "2026-01-01"
"""`dt` のパーティション射影の下限。

これより前の日付は**検索対象にならない**。プロジェクト開始より前であり、
その期間のデータは存在しない。過去へ遡る必要が出たらここを下げる。
"""

_BUCKET_NAME_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]$")
"""S3 バケット名の許容形。

バケット名は `Settings`(環境変数)由来であり Web リクエスト由来ではないが、
DDL へ文字列として埋め込む唯一の外部入力なので、埋め込む前に**許可形の
完全一致**で検証する。引用符・空白・改行はこの形を通らないため、DDL を
壊す値や別の文を注入する値を弾ける。
"""

_DATE_FORMAT_EQUIVALENTS: Final[dict[str, str]] = {"%Y-%m-%d": "yyyy-MM-dd"}
"""`strftime` 表記(`keys.py`)と Athena のパーティション射影の表記の対応。

射影の `projection.dt.format` は Java の `DateTimeFormatter` 表記であり、
`keys.py` がキーを組み立てるときの `strftime` 表記とは別物。**片方だけ変えると
射影が既存のキーと一致せず、Athena がエラーではなく0件を返す。** 対応表に無い
形式は DDL を組み立てる時点で失敗させる。
"""


COUNTRY_SCORE_HISTORY_SQL: Final[str] = """\
SELECT
  dt,
  scan_id,
  need_gap_score,
  confidence,
  status,
  from_iso8601_timestamp(computed_at) AS computed_at
FROM gapatlas.gap_scores
WHERE topic = ? AND country = ?
ORDER BY dt, computed_at
"""
"""「国ごとの Need Gap Score 履歴」を取るクエリ(docs/architecture.md「Athena」)。

`?` は Athena の実行時パラメータ(`StartQueryExecution` の `ExecutionParameters`)。
**外部入力を文字列連結で埋め込まない。**

テーブル名は定数(`GLUE_DATABASE_NAME` / `GAP_SCORES_TABLE_NAME`)ではなく
リテラルで書いている。SELECT 文を文字列補間で組み立てる形にしないため。
定数との一致は単体テストで固定する。

`need_gap_score` が NULL の行(Insufficient Evidence / Failed)も残す。
「スコアが出なかった」ことも履歴の一部であり、行ごと落とすと欠測と
「スコア0」の区別が付かなくなるため、`status` を併せて返す。

1日に複数回スキャンした場合は同じ `dt` に複数行が並ぶ。`computed_at` は
ISO 8601 の文字列として保存されており、辞書順が時刻順と一致しない
(小数秒の有無で崩れる)ため、タイムスタンプへ変換してから並べ替える。
"""

GLUE_DATABASE_DDL: Final[str] = "CREATE DATABASE IF NOT EXISTS gapatlas"
"""テーブルを作る前に必要なデータベース。Phase 12 / 13 が実行する。"""


@dataclass(frozen=True)
class AthenaQuery:
    """実行するクエリと、そのプレースホルダへ渡す値。"""

    sql: str
    parameters: tuple[str, ...]
    """`sql` 中の `?` へ順に対応する値。SQL 文字列へ連結しないこと。"""


def curated_table_location(bucket: str) -> str:
    """`curated/gap_scores/` の S3 URI。

    プレフィックスは `keys.py` の定数から組み立てる。キーの配置を変えたときに
    テーブルの `LOCATION` が置き去りにならないようにするため。

    Raises:
        ArchiveError: バケット名が S3 の命名規則を満たさない場合。
    """
    return f"s3://{_validated_bucket(bucket)}/{CURATED_PREFIX}/{CURATED_DATASET}/"


def gap_scores_table_ddl(bucket: str) -> str:
    """`curated/gap_scores/` を読む Glue テーブルの DDL。

    **パーティション射影(partition projection)を使う。** `MSCK REPAIR TABLE` や
    Glue Crawler を前提にしない理由:

    1. スキャンの直後に Athena から読めること。`MSCK REPAIR` 方式では新しい
       `dt` を追加するたびに実行が必要で、忘れると**エラーではなく0件**が返る。
    2. `MSCK REPAIR` はプレフィックス全体を走査するため、`dt` が増えるほど
       遅くなる。日次で partition が増える構造とは相性が悪い。
    3. パーティション値が列挙可能である。`topic` は `TopicId`、`country` は
       `Country` という**閉じた Enum** であり、`dt` は日付。射影の前提
       (取りうる値を事前に宣言できること)を満たす。
    4. 定期実行の Glue ジョブや Crawler を足さずに済む(コストと構成要素を
       増やさない)。

    代償として、射影の範囲外(`PROJECTION_DATE_RANGE_START` より前、または
    Enum に無い国)は検索されない。国とトピックを増やすときは、この DDL も
    同時に更新すること。

    データ列に `country` を置かないのは Hive の制約による。パーティション列と
    同名のデータ列は宣言できない。`topic_id` も対称性のため置かない。どちらも
    パーティション列(`country` / `topic`)から取得でき、`keys.py` が
    `country.value` / `topic_id.value` をそのままパーティション値にしているため
    値も一致する。

    Raises:
        ArchiveError: バケット名が S3 の命名規則を満たさない場合。
    """
    location = curated_table_location(bucket)
    date_format = _athena_date_format()
    countries = ",".join(country.value for country in Country)
    topics = ",".join(topic.value for topic in TopicId)
    return f"""\
CREATE EXTERNAL TABLE IF NOT EXISTS {GLUE_DATABASE_NAME}.{GAP_SCORES_TABLE_NAME} (
  scan_id string,
  status string,
  need_gap_score int,
  confidence int,
  components struct<
    demand: double,
    pain: double,
    solution_gap: double,
    news_urgency: double
  >,
  confidence_breakdown struct<
    data_completeness: double,
    sample_sufficiency: double,
    localization_quality: double,
    source_agreement: double,
    freshness: double
  >,
  source_status map<string, string>,
  evidence array<struct<
    id: string,
    source: string,
    summary: string,
    url: string
  >>,
  versions struct<
    query_profile_version: string,
    score_version: string,
    classifier_version: string,
    prompt_version: string
  >,
  computed_at string
)
PARTITIONED BY (
  topic string,
  country string,
  dt string
)
ROW FORMAT SERDE 'org.openx.data.jsonserde.JsonSerDe'
WITH SERDEPROPERTIES (
  'ignore.malformed.json' = 'true'
)
STORED AS TEXTFILE
LOCATION '{location}'
TBLPROPERTIES (
  'projection.enabled' = 'true',
  'projection.topic.type' = 'enum',
  'projection.topic.values' = '{topics}',
  'projection.country.type' = 'enum',
  'projection.country.values' = '{countries}',
  'projection.dt.type' = 'date',
  'projection.dt.format' = '{date_format}',
  'projection.dt.range' = '{PROJECTION_DATE_RANGE_START},NOW',
  'projection.dt.interval' = '1',
  'projection.dt.interval.unit' = 'DAYS',
  'storage.location.template' = '{location}topic=${{topic}}/country=${{country}}/dt=${{dt}}'
)
"""


def country_score_history_query(*, topic_id: TopicId, country: Country) -> AthenaQuery:
    """「国ごとの Need Gap Score 履歴」のクエリを組み立てる。

    SQL は定数のまま返し、値は `parameters` として分けて渡す。
    `TopicId` / `Country` は閉じた `StrEnum` なので値そのものは安全だが、
    **安全性を呼び出し元の入力源に依存させない**ためにプレースホルダを使う。
    将来この関数の引数が API のクエリ文字列から来るようになっても、SQL の
    組み立て方を変えずに済む。
    """
    return AthenaQuery(sql=COUNTRY_SCORE_HISTORY_SQL, parameters=(topic_id.value, country.value))


def _validated_bucket(bucket: str) -> str:
    """DDL へ埋め込んでよいバケット名か検証する。

    Raises:
        ArchiveError: S3 の命名規則を満たさない場合。値そのものは載せない。
    """
    if _BUCKET_NAME_PATTERN.fullmatch(bucket) is None:
        raise ArchiveError(
            "S3 bucket name is not valid for an Athena table location "
            "(expected 3-63 chars of lowercase letters, digits, '.' or '-')"
        )
    return bucket


def _athena_date_format() -> str:
    """`keys.py` の `dt` 形式に対応する Athena の日付形式。

    Raises:
        ArchiveError: 対応表に無い形式へ `keys.py` が変わっていた場合。
    """
    athena_format = _DATE_FORMAT_EQUIVALENTS.get(DATE_FORMAT)
    if athena_format is None:
        raise ArchiveError(
            f"no Athena partition projection format is defined for keys.DATE_FORMAT "
            f"({DATE_FORMAT!r})"
        )
    return athena_format
