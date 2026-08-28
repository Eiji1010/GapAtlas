# S3 — Data Lake と Athena のクエリ結果(docs/architecture.md「S3 Data Lake」)。
#
#   raw/source={source}/topic={topic}/country={country}/dt={YYYY-MM-DD}/{scan_id}.json
#   normalized/topic={topic}/country={country}/dt={YYYY-MM-DD}/{scan_id}.json
#   curated/gap_scores/topic={topic}/country={country}/dt={YYYY-MM-DD}/{scan_id}.json
#
# キーの配置は backend/src/gapatlas/adapters/s3/keys.py が正本。
# Glue のパーティション射影(glue.tf)がこの形に依存する。
# **片方だけ変えると Athena がエラーではなく 0 件を返す。**

# ---------------------------------------------------------------------------
# Data Lake バケット
# ---------------------------------------------------------------------------

resource "aws_s3_bucket" "data" {
  bucket = var.s3_bucket_name
}

# Public Access Block(docs/requirements.md「S3 public access 禁止」)。
# **4 項目すべてを有効にする。**
resource "aws_s3_bucket_public_access_block" "data" {
  bucket = aws_s3_bucket.data.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# 既定の暗号化(SSE-S3)。
# KMS ではなく SSE-S3 を選ぶ理由: 保存するのは公開 Web 由来のデータで
# 個人情報を含まない(AGENTS.md)。KMS にすると Lambda と Athena の双方へ
# kms:Decrypt / kms:GenerateDataKey が必要になり、権限面が複雑になるうえ
# リクエストごとの KMS 料金が乗る。
resource "aws_s3_bucket_server_side_encryption_configuration" "data" {
  bucket = aws_s3_bucket.data.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
    bucket_key_enabled = true
  }
}

# バージョニングは**無効**にする。
# 理由:
#   1. オブジェクトキーに scan_id と dt が入る(keys.py)ため、同じキーへ
#      上書きが起きるのは同一 scan_id を再実行したときだけで、実質的に
#      イミュータブルな追記のみのデータである
#   2. データは再スキャンで再生成できる。誤削除からの復旧価値が低い
#   3. 非現行バージョンは Athena から見えないのに保管料だけ発生する
# 監査要件が出てきたら Enabled にし、非現行バージョンのライフサイクルも
# 同時に足すこと。
resource "aws_s3_bucket_versioning" "data" {
  bucket = aws_s3_bucket.data.id

  versioning_configuration {
    status = "Disabled"
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "data" {
  bucket = aws_s3_bucket.data.id

  # 中断したマルチパートアップロードは課金対象のまま残り続ける。
  # データ本体には有効期限を設けない(Athena の履歴分析が目的のため)。
  rule {
    id     = "abort-incomplete-multipart-upload"
    status = "Enabled"

    filter {}

    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }
  }

  depends_on = [aws_s3_bucket_versioning.data]
}

# ---------------------------------------------------------------------------
# Athena クエリ結果バケット
# ---------------------------------------------------------------------------

resource "aws_s3_bucket" "athena_results" {
  bucket = var.athena_results_bucket_name
}

resource "aws_s3_bucket_public_access_block" "athena_results" {
  bucket = aws_s3_bucket.athena_results.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "athena_results" {
  bucket = aws_s3_bucket.athena_results.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_versioning" "athena_results" {
  bucket = aws_s3_bucket.athena_results.id

  versioning_configuration {
    status = "Disabled"
  }
}

# クエリ結果は使い捨て。放置すると増え続けるので短期で消す。
resource "aws_s3_bucket_lifecycle_configuration" "athena_results" {
  bucket = aws_s3_bucket.athena_results.id

  rule {
    id     = "expire-query-results"
    status = "Enabled"

    filter {}

    expiration {
      days = var.athena_results_retention_days
    }

    abort_incomplete_multipart_upload {
      days_after_initiation = 1
    }
  }

  depends_on = [aws_s3_bucket_versioning.athena_results]
}
