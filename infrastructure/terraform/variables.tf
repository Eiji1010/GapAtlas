# 入力変数。**すべてに既定値を持たせる。**
# `terraform.tfvars` なしで `terraform validate` が通ることを要件とする。
#
# 既定値は `.env.example` / `backend/src/gapatlas/config/settings.py` の既定と
# 揃えている。片方だけ変えるとローカル実行と Lambda で挙動が食い違う。

variable "project_name" {
  description = "リソース名の接頭辞に使うプロジェクト名。"
  type        = string
  default     = "gapatlas"

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{1,20}$", var.project_name))
    error_message = "project_name は小文字英数字とハイフンで 2〜21 文字にすること。"
  }
}

variable "environment" {
  description = "環境名。リソース名とタグに使う。"
  type        = string
  default     = "dev"

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{1,10}$", var.environment))
    error_message = "environment は小文字英数字とハイフンで 2〜11 文字にすること。"
  }
}

variable "aws_region" {
  description = "デプロイ先リージョン。`.env.example` の AWS_REGION と揃える。"
  type        = string
  default     = "ap-northeast-1"
}

# ---- DynamoDB / S3 ----

variable "dynamodb_table_name" {
  description = "DynamoDB テーブル名。settings.py の DYNAMODB_TABLE_NAME 既定と揃える。"
  type        = string
  default     = "gapatlas"
}

variable "s3_bucket_name" {
  description = <<-EOT
    Data Lake のバケット名。settings.py の S3_BUCKET_NAME 既定と揃える。
    **S3 のバケット名はグローバルに一意**なので、実際にデプロイする際は
    必ず一意な名前へ変更すること(例: gapatlas-data-<アカウントID>)。
  EOT
  type        = string
  default     = "gapatlas-data"

  validation {
    # athena.py の _BUCKET_NAME_PATTERN と同じ形。DDL へ埋め込むため。
    condition     = can(regex("^[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]$", var.s3_bucket_name))
    error_message = "s3_bucket_name は S3 の命名規則(小文字英数字・ドット・ハイフンで 3〜63 文字)に従うこと。"
  }
}

variable "athena_results_bucket_name" {
  description = <<-EOT
    Athena のクエリ結果の出力先バケット名。Data Lake とは分ける。
    Athena は結果を CSV とメタデータで書き戻すため、同じバケットへ出すと
    将来プレフィックスを増やしたときにクエリ対象と混ざる危険がある。
    また結果は使い捨てなので、ライフサイクルで短期削除したい。
  EOT
  type        = string
  default     = "gapatlas-athena-results"

  validation {
    condition     = can(regex("^[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]$", var.athena_results_bucket_name))
    error_message = "athena_results_bucket_name は S3 の命名規則に従うこと。"
  }
}

variable "athena_results_retention_days" {
  description = "Athena のクエリ結果を保持する日数。使い捨てなので短くする。"
  type        = number
  default     = 7
}

# ---- Lambda ----

variable "lambda_runtime" {
  description = "Lambda のランタイム。backend/pyproject.toml の requires-python(>=3.12)と揃える。"
  type        = string
  default     = "python3.12"
}

variable "lambda_architecture" {
  description = "Lambda の CPU アーキテクチャ。arm64 のほうが単価が安い。"
  type        = string
  default     = "arm64"

  validation {
    condition     = contains(["arm64", "x86_64"], var.lambda_architecture)
    error_message = "lambda_architecture は arm64 か x86_64 にすること。"
  }
}

variable "lambda_package_source_dir" {
  description = <<-EOT
    Lambda デプロイパッケージの中身が入ったディレクトリ。
    空文字の場合は `placeholder/` を zip 化する(`terraform validate` を
    通すためのダミー)。実際のデプロイ手順は infrastructure/README.md を参照。
  EOT
  type        = string
  default     = ""
}

variable "api_lambda_memory_mb" {
  description = "Lambda API のメモリ。DynamoDB PutItem と SQS 送信だけなので小さくてよい。"
  type        = number
  default     = 512
}

variable "api_lambda_timeout_seconds" {
  description = <<-EOT
    Lambda API のタイムアウト。
    SLO は POST /scans が p95 < 800ms(docs/requirements.md「Performance SLO」)。
    API Gateway HTTP API 側の上限が 30 秒なので、それ以下に収める。
  EOT
  type        = number
  default     = 15
}

variable "worker_lambda_memory_mb" {
  description = <<-EOT
    Lambda Worker のメモリ。SerpApi 4 種を並列に呼び、レスポンスを正規化する。
    メモリは CPU 割り当てにも比例するため、API より大きくする。
  EOT
  type        = number
  default     = 1024
}

variable "worker_lambda_timeout_seconds" {
  description = <<-EOT
    Lambda Worker のタイムアウト。
    最悪ケースの見積り: SerpApi 8 秒 x (1 + 2 リトライ) を並列で約 30 秒
    + LLM 分類 30 秒 x (1 + 2 リトライ) で約 90 秒。余裕を見て 120 秒。
  EOT
  type        = number
  default     = 120
}

variable "worker_reserved_concurrency" {
  description = <<-EOT
    Lambda Worker の予約済み同時実行数。
    docs/architecture.md「Reserved concurrency は 2 程度から始める
    (SerpApi のレート制限を考慮)」。
  EOT
  type        = number
  default     = 2

  validation {
    # SQS イベントソースの scaling_config.maximum_concurrency の下限が 2。
    condition     = var.worker_reserved_concurrency >= 2
    error_message = "worker_reserved_concurrency は 2 以上にすること(SQS の maximum_concurrency の下限)。"
  }
}

# ---- SQS ----

variable "sqs_max_receive_count" {
  description = "DLQ へ送るまでの受信回数。docs/architecture.md「maxReceiveCount = 3」。"
  type        = number
  default     = 3
}

variable "sqs_message_retention_seconds" {
  description = "メインキューのメッセージ保持期間(既定 4 日)。"
  type        = number
  default     = 345600
}

variable "dlq_message_retention_seconds" {
  description = "DLQ の保持期間。障害調査のため最大の 14 日にする。"
  type        = number
  default     = 1209600
}

# ---- API Gateway ----

variable "cors_allowed_origins" {
  description = <<-EOT
    CORS を許可する Frontend origin。`.env.example` の CORS_ALLOWED_ORIGINS と
    同じ値を入れる。**ワイルドカード("*")を入れないこと**
    (docs/requirements.md「CORS を Frontend origin へ限定」)。
    Frontend は Cloudflare Pages なので、デプロイ後にその origin を追加する。
  EOT
  type        = list(string)
  default     = ["http://localhost:5173"]

  validation {
    condition     = length(var.cors_allowed_origins) > 0 && !contains(var.cors_allowed_origins, "*")
    error_message = "cors_allowed_origins は 1 件以上で、ワイルドカード(*)を含めないこと。"
  }
}

variable "api_throttling_rate_limit" {
  description = <<-EOT
    API Gateway のスロットリング(定常レート、req/sec)。
    SerpApi のクォータを守るための保険。デモ規模なので低く抑える。
  EOT
  type        = number
  default     = 20
}

variable "api_throttling_burst_limit" {
  description = "API Gateway のスロットリング(バースト)。"
  type        = number
  default     = 40
}

# ---- Glue / Athena ----

variable "glue_database_name" {
  description = "Glue のデータベース名。adapters/s3/athena.py の GLUE_DATABASE_NAME と一致させること。"
  type        = string
  default     = "gapatlas"
}

variable "gap_scores_table_name" {
  description = "Glue のテーブル名。athena.py の GAP_SCORES_TABLE_NAME と一致させること。"
  type        = string
  default     = "gap_scores"
}

variable "partition_countries" {
  description = <<-EOT
    パーティション射影(country)の値。
    backend/src/gapatlas/domain/models/common.py の Country Enum と
    一致させること。**ここに無い国は Athena から不可視になる**
    (エラーではなく 0 件が返る)。
  EOT
  type        = list(string)
  default     = ["JP", "US", "GB", "DE", "IN"]
}

variable "partition_topics" {
  description = "パーティション射影(topic)の値。TopicId Enum と一致させること。"
  type        = list(string)
  default     = ["elder_care"]
}

variable "partition_date_range_start" {
  description = <<-EOT
    パーティション射影(dt)の下限。
    athena.py の PROJECTION_DATE_RANGE_START と一致させること。
  EOT
  type        = string
  default     = "2026-01-01"
}

variable "athena_bytes_scanned_cutoff" {
  description = <<-EOT
    1 クエリあたりのスキャン量上限(バイト)。暴走クエリのコスト上限。
    デモのデータ量は数 MB 程度なので 1 GiB で十分。下限は 10 MB。
  EOT
  type        = number
  default     = 1073741824
}

# ---- ログ / アプリ設定 ----

variable "log_retention_days" {
  description = <<-EOT
    CloudWatch Logs の保持日数。
    デモ用途なので 14 日にする。ハッカソン期間中の障害調査には十分で、
    無期限保持(既定)にするとログ保管料が静かに積み上がる。
  EOT
  type        = number
  default     = 14
}

variable "log_level" {
  description = "アプリの LOG_LEVEL。settings.py の LogLevel と同じ値。"
  type        = string
  default     = "INFO"

  validation {
    condition     = contains(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"], var.log_level)
    error_message = "log_level は DEBUG / INFO / WARNING / ERROR / CRITICAL のいずれかにすること。"
  }
}

variable "serpapi_mode" {
  description = <<-EOT
    SERPAPI_MODE。既定は fixture(AGENTS.md「fixture mode を常に維持する」)。
    live にする場合は Secrets Manager へ API キーを入れたうえで、
    backend 側の読み出し実装が必要(infrastructure/README.md「秘密情報」)。
  EOT
  type        = string
  default     = "fixture"

  validation {
    condition     = contains(["fixture", "live"], var.serpapi_mode)
    error_message = "serpapi_mode は fixture か live にすること。"
  }

  validation {
    # backend は SERPAPI_API_KEY(環境変数)しか読まない。Secrets Manager から
    # 取得する実装が入るまで live にすると、Settings の資格情報チェックで
    # Lambda が起動時に落ち、全メッセージが maxReceiveCount を消費して DLQ へ行く。
    condition     = var.serpapi_mode == "fixture"
    error_message = "live は未対応。config/settings.py に Secrets Manager の読み出しを実装してから、この validation を外すこと。"
  }
}

variable "llm_mode" {
  description = "LLM_MODE。既定は stub。"
  type        = string
  default     = "stub"

  validation {
    condition     = contains(["stub", "anthropic"], var.llm_mode)
    error_message = "llm_mode は stub か anthropic にすること。"
  }

  validation {
    # serpapi_mode と同じ理由。ANTHROPIC_API_KEY を Secrets Manager から
    # 読む実装が無いため、anthropic にすると Lambda が起動できない。
    condition     = var.llm_mode == "stub"
    error_message = "anthropic は未対応。config/settings.py に Secrets Manager の読み出しを実装してから、この validation を外すこと。"
  }
}

variable "anthropic_model" {
  description = "ANTHROPIC_MODEL。settings.py の既定と揃える。"
  type        = string
  default     = "claude-sonnet-5"
}

variable "serpapi_timeout_seconds" {
  description = "SERPAPI_TIMEOUT_SECONDS。docs/architecture.md「Reliability」。"
  type        = number
  default     = 8
}

variable "serpapi_max_retries" {
  description = "SERPAPI_MAX_RETRIES。"
  type        = number
  default     = 2
}

variable "anthropic_timeout_seconds" {
  description = "ANTHROPIC_TIMEOUT_SECONDS。SDK 既定(read 600 秒)に委ねない。"
  type        = number
  default     = 30
}

variable "anthropic_max_retries" {
  description = "ANTHROPIC_MAX_RETRIES。"
  type        = number
  default     = 2
}
