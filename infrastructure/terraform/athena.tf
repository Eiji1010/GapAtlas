# Athena — 履歴分析専用のワークグループ。
#
# **Web のリアルタイム表示には使わない**(docs/architecture.md「Athena」)。
# UI が読むのは DynamoDB。ここは「国ごとの Need Gap Score 履歴」
# (athena.py の COUNTRY_SCORE_HISTORY_SQL)を実行するための場所。

resource "aws_athena_workgroup" "main" {
  name        = local.name_prefix
  description = "GapAtlas の履歴分析用ワークグループ。"

  configuration {
    # クライアント側で出力先を上書きさせない。上書きできると
    # 結果が別のバケットへ書かれ、ライフサイクル(s3.tf)が効かなくなる。
    enforce_workgroup_configuration = true

    # 暴走クエリのコスト上限。デモのデータ量なら数 MB で足りる。
    bytes_scanned_cutoff_per_query = var.athena_bytes_scanned_cutoff

    publish_cloudwatch_metrics_enabled = true

    result_configuration {
      output_location = "s3://${aws_s3_bucket.athena_results.id}/query-results/"

      encryption_configuration {
        # 結果バケットの既定暗号化(s3.tf)と揃える。
        encryption_option = "SSE_S3"
      }
    }
  }

  # デモ環境では作り直しを繰り返す。ワークグループに実行履歴が残っていても
  # 破棄できるようにする(履歴は S3 側のライフサイクルで消える)。
  force_destroy = true
}

# クエリの実体は backend 側の定数(athena.py の COUNTRY_SCORE_HISTORY_SQL)が
# 正本。ここには「保存済みクエリ」としてコンソールから開ける形で置く。
# **SQL を二重管理にしないため、実行時に使うのは backend の定数のほう。**
resource "aws_athena_named_query" "country_score_history" {
  name        = "${local.name_prefix}-country-score-history"
  description = "国ごとの Need Gap Score 履歴。正本は adapters/s3/athena.py の COUNTRY_SCORE_HISTORY_SQL。"

  workgroup = aws_athena_workgroup.main.id
  database  = aws_glue_catalog_database.main.name

  # コンソールから手で流せるように、パラメータ(?)ではなくリテラルの
  # 例を入れている。アプリからの実行は必ず ExecutionParameters を使うこと
  # (athena.py: 外部入力を文字列連結で埋め込まない)。
  query = <<-SQL
    SELECT
      dt,
      scan_id,
      need_gap_score,
      confidence,
      status,
      from_iso8601_timestamp(computed_at) AS computed_at
    FROM ${var.glue_database_name}.${var.gap_scores_table_name}
    WHERE topic = 'elder_care' AND country = 'JP'
    ORDER BY dt, computed_at
  SQL

  depends_on = [aws_glue_catalog_table.gap_scores]
}
