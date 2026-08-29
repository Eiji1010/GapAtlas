# Lambda — API と Worker(docs/architecture.md「全体構成」)。
#
# **VPC には入れない。NAT Gateway も作らない**(AGENTS.md / architecture.md)。
# SerpApi と Anthropic API へ出るだけなので、VPC に入れると NAT Gateway の
# 固定費と経路設定が増えるだけで得るものが無い。
#
# ハンドラ名は backend のコードと一致させること。
#   API    : gapatlas.api.lambda_handlers.api_handler
#   Worker : gapatlas.api.worker_handler.worker_handler
#
# 環境変数名は backend/src/gapatlas/config/settings.py の load_settings() が
# 読む名前と一致させること。**AWS_REGION は設定しない**(下記の注記を参照)。

# ---------------------------------------------------------------------------
# デプロイパッケージ
# ---------------------------------------------------------------------------
#
# **Lambda のデプロイパッケージはこのリポジトリにまだ無い。**
# ここでは `placeholder/` を zip 化したダミーを既定にして、
# パッケージが無くても `terraform validate` / `plan` が通るようにする。
# `filename` に存在しないパスを直書きすると plan の時点で失敗し、
# コードの検証ができなくなるため、この形を選んだ。
#
# 実際にデプロイするときは、uv で依存を固めて展開したディレクトリを
# `lambda_package_source_dir` に渡す(手順は infrastructure/README.md)。
# API と Worker はどちらも同じ backend パッケージで、ハンドラだけが違う。

locals {
  lambda_package_source_dir = (
    var.lambda_package_source_dir != ""
    ? var.lambda_package_source_dir
    : "${path.module}/placeholder"
  )
}

data "archive_file" "lambda_package" {
  type        = "zip"
  source_dir  = local.lambda_package_source_dir
  output_path = "${path.module}/build/gapatlas-lambda.zip"
}

# ---------------------------------------------------------------------------
# 共通の環境変数
# ---------------------------------------------------------------------------
#
# AWS_REGION / AWS_DEFAULT_ACCESS_KEY などは Lambda の**予約済み環境変数**で、
# 設定しようとすると関数の更新自体が失敗する。settings.py は os.environ から
# AWS_REGION を読むが、Lambda が実行時に自動で入れるためここでは渡さない。

locals {
  common_environment = {
    # AWS へ接続するモード。既定(memory)のままだと DynamoDB / S3 / SQS を
    # 一切使わずプロセス内メモリで動いてしまう(settings.py)。
    PERSISTENCE_MODE = "aws"

    DYNAMODB_TABLE_NAME = aws_dynamodb_table.main.name
    S3_BUCKET_NAME      = aws_s3_bucket.data.id
    LOG_LEVEL           = var.log_level

    # **必須。** 省略すると query_profile_loader がリポジトリ配置を前提に
    # 相対解決し、パッケージ内で国別 YAML を見つけられない。ScanWorker は
    # ConfigError を握るため、例外ではなく「全国 FAILED のスキャンが
    # completed として保存される」という無言の失敗になる。
    # infrastructure/README.md のパッケージ構成に合わせた絶対パス。
    QUERY_PROFILES_DIR = "/var/task/config/query_profiles"

    # Athena のワークグループ名。backend の既定値と Terraform の名前が
    # 食い違うと、クエリが WorkGroup not found で必ず失敗する。
    ATHENA_WORKGROUP = aws_athena_workgroup.main.name
  }
}

# ---------------------------------------------------------------------------
# Lambda API
# ---------------------------------------------------------------------------

resource "aws_lambda_function" "api" {
  function_name = "${local.name_prefix}-api"
  role          = aws_iam_role.api_lambda.arn

  # backend/src/gapatlas/api/lambda_handlers.py の api_handler。
  handler = "gapatlas.api.lambda_handlers.api_handler"

  runtime       = var.lambda_runtime
  architectures = [var.lambda_architecture]

  filename         = data.archive_file.lambda_package.output_path
  source_code_hash = data.archive_file.lambda_package.output_base64sha256

  memory_size = var.api_lambda_memory_mb
  timeout     = var.api_lambda_timeout_seconds

  environment {
    variables = merge(local.common_environment, {
      # ジョブ投入先。settings.py の SQS_QUEUE_URL。
      SQS_QUEUE_URL = aws_sqs_queue.scan_jobs.url

      # API Gateway の CORS 設定(apigateway.tf)が優先されるが、
      # ハンドラ側も同じ値を持たせて挙動を一致させる。
      CORS_ALLOWED_ORIGINS = join(",", var.cors_allowed_origins)
    })
  }

  # ロググループを先に作ってから関数を作る(cloudwatch.tf の注記)。
  depends_on = [
    aws_cloudwatch_log_group.api_lambda,
    aws_iam_role_policy.api_lambda,
  ]
}

# ---------------------------------------------------------------------------
# Lambda Worker
# ---------------------------------------------------------------------------

resource "aws_lambda_function" "worker" {
  function_name = "${local.name_prefix}-worker"
  role          = aws_iam_role.worker_lambda.arn

  # backend/src/gapatlas/api/worker_handler.py の worker_handler。
  handler = "gapatlas.api.worker_handler.worker_handler"

  runtime       = var.lambda_runtime
  architectures = [var.lambda_architecture]

  filename         = data.archive_file.lambda_package.output_path
  source_code_hash = data.archive_file.lambda_package.output_base64sha256

  memory_size = var.worker_lambda_memory_mb
  timeout     = var.worker_lambda_timeout_seconds

  # docs/architecture.md「Reserved concurrency は 2 程度から始める
  # (SerpApi のレート制限を考慮)」。
  reserved_concurrent_executions = var.worker_reserved_concurrency

  environment {
    variables = merge(local.common_environment, {
      SERPAPI_MODE            = var.serpapi_mode
      SERPAPI_TIMEOUT_SECONDS = tostring(var.serpapi_timeout_seconds)
      SERPAPI_MAX_RETRIES     = tostring(var.serpapi_max_retries)

      LLM_MODE                  = var.llm_mode
      ANTHROPIC_MODEL           = var.anthropic_model
      ANTHROPIC_TIMEOUT_SECONDS = tostring(var.anthropic_timeout_seconds)
      ANTHROPIC_MAX_RETRIES     = tostring(var.anthropic_max_retries)

      # SERPAPI_API_KEY / ANTHROPIC_API_KEY は**ここへ書かない**。
      # 平文が Terraform の state に残るため。値は Secrets Manager
      # (secrets.tf)に置き、ARN だけを渡す。
      SERPAPI_API_KEY_SECRET_ARN   = aws_secretsmanager_secret.serpapi_api_key.arn
      ANTHROPIC_API_KEY_SECRET_ARN = aws_secretsmanager_secret.anthropic_api_key.arn
    })
  }

  depends_on = [
    aws_cloudwatch_log_group.worker_lambda,
    aws_iam_role_policy.worker_lambda,
  ]
}

# SQS -> Lambda Worker。
resource "aws_lambda_event_source_mapping" "worker" {
  event_source_arn = aws_sqs_queue.scan_jobs.arn
  function_name    = aws_lambda_function.worker.arn

  # **1 メッセージ 1 国**。adapters/sqs/decode.py と worker_handler.py が
  # これを前提にしている。増やすなら ReportBatchItemFailures と
  # record ごとの失敗収集が必要(worker_handler.py の docstring)。
  batch_size = 1

  # まとめ待ちをしない。「First Country Result < 5 sec」の SLO を守るため
  # (docs/requirements.md「Performance SLO」)。
  maximum_batching_window_in_seconds = 0

  # function_response_types は指定しない。batch_size = 1 では
  # 「例外を投げる = そのメッセージの失敗」で意図どおりに動き、
  # ハンドラも常に空の batchItemFailures を返すため。

  # ポーラーの同時実行を予約済み同時実行と揃える。揃えないとポーラーが
  # 予約数を超えて起動しようとし、スロットリングによる無駄な再配信で
  # maxReceiveCount を消費する。
  scaling_config {
    maximum_concurrency = var.worker_reserved_concurrency
  }
}
