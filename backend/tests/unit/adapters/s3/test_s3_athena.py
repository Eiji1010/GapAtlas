"""`athena.py` のテスト。

DDL とクエリは Glue(Phase 12)と Terraform(Phase 13)が使う。**`keys.py` の
配置と一致していることをリテラルで固定する。** 片方だけ変えると Athena は
エラーではなく0件を返すため、テストでしか検出できない。

Athena へは接続しない(文字列を組み立てるだけのモジュール)。
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from gapatlas.adapters.s3.athena import (
    COUNTRY_SCORE_HISTORY_SQL,
    GAP_SCORES_TABLE_NAME,
    GLUE_DATABASE_DDL,
    GLUE_DATABASE_NAME,
    PARTITION_COLUMNS,
    PROJECTION_DATE_RANGE_START,
    country_score_history_query,
    curated_table_location,
    gap_scores_table_ddl,
)
from gapatlas.adapters.s3.errors import ArchiveError
from gapatlas.adapters.s3.keys import curated_key
from gapatlas.domain.models.common import Country, TopicId

BUCKET = "gapatlas-data"
SCAN_TIME = datetime(2026, 8, 28, tzinfo=UTC)


def test_partition_columns_are_topic_country_dt():
    assert PARTITION_COLUMNS == ("topic", "country", "dt")


def test_curated_location_matches_the_key_layout():
    """`LOCATION` は `curated_key` のプレフィックスと一致すること。"""
    assert curated_table_location(BUCKET) == "s3://gapatlas-data/curated/gap_scores/"

    key = curated_key(
        topic_id=TopicId.ELDER_CARE,
        country=Country.JP,
        scan_time=SCAN_TIME,
        scan_id="s1",
    )
    assert f"s3://{BUCKET}/{key}".startswith(curated_table_location(BUCKET))


def test_ddl_declares_the_partition_columns_in_key_order():
    ddl = gap_scores_table_ddl(BUCKET)

    assert "PARTITIONED BY (\n  topic string,\n  country string,\n  dt string\n)" in ddl


def test_ddl_targets_the_curated_gap_scores_location():
    ddl = gap_scores_table_ddl(BUCKET)

    assert "CREATE EXTERNAL TABLE IF NOT EXISTS gapatlas.gap_scores (" in ddl
    assert "LOCATION 's3://gapatlas-data/curated/gap_scores/'" in ddl
    assert (
        "'storage.location.template' = "
        "'s3://gapatlas-data/curated/gap_scores/"
        "topic=${topic}/country=${country}/dt=${dt}'"
    ) in ddl


def test_ddl_uses_partition_projection_over_msck_repair():
    """射影を使う。`MSCK REPAIR TABLE` / Crawler を前提にしない。"""
    ddl = gap_scores_table_ddl(BUCKET)

    assert "'projection.enabled' = 'true'" in ddl
    assert "MSCK" not in ddl
    assert "'projection.topic.type' = 'enum'" in ddl
    assert "'projection.topic.values' = 'elder_care'" in ddl
    assert "'projection.country.type' = 'enum'" in ddl
    assert "'projection.country.values' = 'JP,US,GB,DE,IN'" in ddl
    assert "'projection.dt.type' = 'date'" in ddl
    assert "'projection.dt.format' = 'yyyy-MM-dd'" in ddl
    assert f"'projection.dt.range' = '{PROJECTION_DATE_RANGE_START},NOW'" in ddl
    assert "'projection.dt.interval.unit' = 'DAYS'" in ddl


def test_projection_values_cover_every_country_and_topic():
    """MVP の5か国と Elder Care がすべて射影に含まれること。"""
    ddl = gap_scores_table_ddl(BUCKET)

    for country in Country:
        assert country.value in ddl.split("'projection.country.values' = '")[1].split("'")[0]
    for topic in TopicId:
        assert topic.value in ddl.split("'projection.topic.values' = '")[1].split("'")[0]


def test_ddl_does_not_repeat_partition_columns_as_data_columns():
    """Hive はパーティション列と同名のデータ列を許さない。"""
    ddl = gap_scores_table_ddl(BUCKET)
    columns = ddl.split("(", 1)[1].split("PARTITIONED BY", 1)[0]

    assert "\n  country string," not in columns
    assert "\n  topic_id string," not in columns
    assert "\n  scan_id string," in columns
    assert "\n  need_gap_score int," in columns


def test_ddl_reads_json_lines():
    """保存形式は JSON Lines(`client.py`)。Parquet ではない。"""
    ddl = gap_scores_table_ddl(BUCKET)

    assert "ROW FORMAT SERDE 'org.openx.data.jsonserde.JsonSerDe'" in ddl
    assert "STORED AS TEXTFILE" in ddl
    assert "PARQUET" not in ddl.upper()


def test_database_ddl_matches_the_database_name():
    assert GLUE_DATABASE_DDL == "CREATE DATABASE IF NOT EXISTS gapatlas"
    assert GLUE_DATABASE_NAME == "gapatlas"
    assert GAP_SCORES_TABLE_NAME == "gap_scores"


@pytest.mark.parametrize(
    "bucket",
    [
        "",
        "ab",
        "Gapatlas-Data",
        "gapatlas data",
        "gapatlas'; DROP TABLE gap_scores; --",
        "gapatlas-data\n",
    ],
)
def test_invalid_bucket_names_are_rejected(bucket: str):
    """DDL へ埋め込む唯一の外部入力を許可形で検証する。"""
    with pytest.raises(ArchiveError):
        gap_scores_table_ddl(bucket)


# --- 履歴クエリ -------------------------------------------------------------------------


def test_history_query_targets_the_gap_scores_table():
    assert f"FROM {GLUE_DATABASE_NAME}.{GAP_SCORES_TABLE_NAME}" in COUNTRY_SCORE_HISTORY_SQL


def test_history_query_filters_by_the_partition_columns():
    assert "WHERE topic = ? AND country = ?" in COUNTRY_SCORE_HISTORY_SQL
    assert "ORDER BY dt, computed_at" in COUNTRY_SCORE_HISTORY_SQL


def test_history_query_selects_the_score_history():
    for column in ("dt", "scan_id", "need_gap_score", "confidence", "status"):
        assert column in COUNTRY_SCORE_HISTORY_SQL


@pytest.mark.parametrize("country", list(Country))
def test_history_query_passes_values_as_parameters(country: Country):
    """値を SQL へ連結しない(SQL インジェクション対策)。"""
    query = country_score_history_query(topic_id=TopicId.ELDER_CARE, country=country)

    assert query.sql == COUNTRY_SCORE_HISTORY_SQL
    assert query.parameters == ("elder_care", country.value)
    # 値がリテラルとして埋め込まれていないこと("ORDER" に "DE" が含まれるため、
    # 素の部分一致ではなく引用符付きで確認する)。
    assert f"'{country.value}'" not in query.sql
    assert f'"{country.value}"' not in query.sql
    assert query.sql.count("?") == len(query.parameters)


def test_history_query_parameter_order_matches_the_placeholders():
    query = country_score_history_query(topic_id=TopicId.ELDER_CARE, country=Country.DE)
    before_country = query.sql.index("topic = ?")

    assert before_country < query.sql.index("country = ?")
    assert query.parameters[0] == TopicId.ELDER_CARE.value
    assert query.parameters[1] == Country.DE.value
