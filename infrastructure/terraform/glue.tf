# Glue Data Catalog — curated/gap_scores を Athena から読むためのカタログ。
#
# **正本は backend/src/gapatlas/adapters/s3/athena.py の DDL**
# (GLUE_DATABASE_DDL / gap_scores_table_ddl)。この Terraform 定義は
# その DDL を宣言的に置き換えたもので、列・パーティション・SerDe・
# TBLPROPERTIES を一致させている。
#
# **片方だけ変えると Athena がエラーではなく 0 件を返す**(最も危険な失敗
# モード)。athena.py 側にはテーブル定義との一致を固定する単体テストがある。

resource "aws_glue_catalog_database" "main" {
  # athena.py: GLUE_DATABASE_NAME = "gapatlas"
  name        = var.glue_database_name
  description = "GapAtlas の履歴分析用データベース(Athena 専用。Web のリアルタイム表示には使わない)。"
}

resource "aws_glue_catalog_table" "gap_scores" {
  # athena.py: GAP_SCORES_TABLE_NAME = "gap_scores"
  name          = var.gap_scores_table_name
  database_name = aws_glue_catalog_database.main.name
  table_type    = "EXTERNAL_TABLE"

  parameters = {
    EXTERNAL       = "TRUE"
    classification = "json"

    # ---- パーティション射影 ----
    # MSCK REPAIR TABLE / Glue Crawler を使わない理由は athena.py の
    # gap_scores_table_ddl() の docstring に書いてある。要点は
    # 「新しい dt を追加するたびの実行を忘れると 0 件が返る」こと。
    "projection.enabled" = "true"

    # topic / country は閉じた Enum(TopicId / Country)。
    # **ここに無い値は検索対象にならない。** 国やトピックを増やすときは
    # variables.tf の partition_topics / partition_countries も更新すること。
    "projection.topic.type"     = "enum"
    "projection.topic.values"   = join(",", var.partition_topics)
    "projection.country.type"   = "enum"
    "projection.country.values" = join(",", var.partition_countries)

    # dt は日付。format は Java の DateTimeFormatter 表記であり、
    # keys.py の strftime 表記("%Y-%m-%d")とは別物。
    # athena.py の _DATE_FORMAT_EQUIVALENTS が対応を持っている。
    "projection.dt.type"          = "date"
    "projection.dt.format"        = "yyyy-MM-dd"
    "projection.dt.range"         = "${var.partition_date_range_start},NOW"
    "projection.dt.interval"      = "1"
    "projection.dt.interval.unit" = "DAYS"

    # $${...} は Terraform のエスケープ。Athena へは ${topic} の形で渡る。
    # keys.py の curated_key() が組み立てるキーと同じ並び。
    "storage.location.template" = "${local.curated_location}topic=$${topic}/country=$${country}/dt=$${dt}"
  }

  # keys.py: curated/gap_scores/topic=.../country=.../dt=.../{scan_id}.json
  partition_keys {
    name = "topic"
    type = "string"
  }

  partition_keys {
    name = "country"
    type = "string"
  }

  partition_keys {
    name = "dt"
    type = "string"
  }

  storage_descriptor {
    location = local.curated_location

    # 保存形式は JSON Lines(adapters/s3/client.py)。Parquet は pyarrow が
    # 必要で Lambda のパッケージが 40〜60MB 増えるため MVP では採用しない
    # (docs/architecture.md「S3 Data Lake」)。切り替えるときは
    # ここの input/output format と ser_de_info も同時に変更すること。
    input_format  = "org.apache.hadoop.mapred.TextInputFormat"
    output_format = "org.apache.hadoop.hive.ql.io.HiveIgnoreKeyTextOutputFormat"

    ser_de_info {
      serialization_library = "org.openx.data.jsonserde.JsonSerDe"

      parameters = {
        # 壊れた 1 行でクエリ全体を失敗させない。
        "ignore.malformed.json" = "true"
      }
    }

    # ---- 列定義 ----
    # athena.py の gap_scores_table_ddl() と同じ順序・同じ型。
    # **country / topic をデータ列に置かない。** Hive はパーティション列と
    # 同名のデータ列を宣言できないため(athena.py の docstring)。

    columns {
      name = "scan_id"
      type = "string"
    }

    columns {
      name = "status"
      type = "string"
    }

    columns {
      name    = "need_gap_score"
      type    = "int"
      comment = "Insufficient Evidence / Failed のときは NULL。欠測とスコア 0 を区別する。"
    }

    columns {
      name = "confidence"
      type = "int"
    }

    columns {
      name = "components"
      type = "struct<demand:double,pain:double,solution_gap:double,news_urgency:double>"
    }

    columns {
      name = "confidence_breakdown"
      type = "struct<data_completeness:double,sample_sufficiency:double,localization_quality:double,source_agreement:double,freshness:double>"
    }

    columns {
      name = "source_status"
      type = "map<string,string>"
    }

    columns {
      name = "evidence"
      type = "array<struct<id:string,source:string,summary:string,url:string>>"
    }

    columns {
      name    = "versions"
      type    = "struct<query_profile_version:string,score_version:string,classifier_version:string,prompt_version:string>"
      comment = "再現可能性のためのバージョン識別子(AGENTS.md)。"
    }

    columns {
      name    = "computed_at"
      type    = "string"
      comment = "ISO 8601 文字列。並べ替えは from_iso8601_timestamp() で変換してから行う。"
    }
  }
}
