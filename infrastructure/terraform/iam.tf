# IAM — Lambda ごとに最小権限(docs/requirements.md「IAM は Least Privilege」)。
#
# **AWSLambdaBasicExecutionRole などの AWS 管理ポリシーを使わない。**
# 管理ポリシーは logs の Resource が広く、logs:CreateLogGroup も含むため、
# ロググループを Terraform で作る構成(cloudwatch.tf)では過剰になる。
#
# 許可した API はアプリが実際に呼ぶものだけ。
#   - DynamoDB: PutItem / GetItem / Query (adapters/dynamodb/client.py)
#   - S3      : PutObject               (adapters/s3/client.py)
#   - SQS(送信): SendMessage / SendMessageBatch (adapters/sqs/client.py)
#   - SQS(受信): ReceiveMessage / DeleteMessage / GetQueueAttributes
#                (Lambda のイベントソースマッピングが使う)

data "aws_iam_policy_document" "lambda_assume_role" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

# ---------------------------------------------------------------------------
# Lambda API
# ---------------------------------------------------------------------------

resource "aws_iam_role" "api_lambda" {
  name               = "${local.name_prefix}-api-lambda"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume_role.json
}

data "aws_iam_policy_document" "api_lambda" {
  # 自分のロググループにだけ書ける。CreateLogGroup は与えない。
  statement {
    sid       = "WriteOwnLogs"
    effect    = "Allow"
    actions   = ["logs:CreateLogStream", "logs:PutLogEvents"]
    resources = ["${aws_cloudwatch_log_group.api_lambda.arn}:*"]
  }

  # API は SCAN META の作成(PutItem)と、進捗・国別結果の読み取り
  # (GetItem / Query)だけを行う。DeleteItem / Scan は与えない。
  statement {
    sid       = "ReadWriteScanItems"
    effect    = "Allow"
    actions   = ["dynamodb:PutItem", "dynamodb:GetItem", "dynamodb:Query"]
    resources = [aws_dynamodb_table.main.arn]
  }

  # 国ごとのジョブ投入。受信系(ReceiveMessage / DeleteMessage)は与えない。
  statement {
    sid       = "SendScanJobs"
    effect    = "Allow"
    actions   = ["sqs:SendMessage", "sqs:SendMessageBatch"]
    resources = [aws_sqs_queue.scan_jobs.arn]
  }
}

resource "aws_iam_role_policy" "api_lambda" {
  name   = "${local.name_prefix}-api-lambda"
  role   = aws_iam_role.api_lambda.id
  policy = data.aws_iam_policy_document.api_lambda.json
}

# ---------------------------------------------------------------------------
# Lambda Worker
# ---------------------------------------------------------------------------

resource "aws_iam_role" "worker_lambda" {
  name               = "${local.name_prefix}-worker-lambda"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume_role.json
}

data "aws_iam_policy_document" "worker_lambda" {
  statement {
    sid       = "WriteOwnLogs"
    effect    = "Allow"
    actions   = ["logs:CreateLogStream", "logs:PutLogEvents"]
    resources = ["${aws_cloudwatch_log_group.worker_lambda.arn}:*"]
  }

  # 国別結果の書き込みと、進捗判定のための読み取り。
  statement {
    sid       = "ReadWriteScanItems"
    effect    = "Allow"
    actions   = ["dynamodb:PutItem", "dynamodb:GetItem", "dynamodb:Query"]
    resources = [aws_dynamodb_table.main.arn]
  }

  # raw / normalized / curated への書き込みのみ。
  # 読み取り(GetObject)も一覧(ListBucket)も現在のコードは使わない。
  # Resource をバケット直下の "/*" に限定しており、"*" は使っていない。
  statement {
    sid       = "WriteDataLakeObjects"
    effect    = "Allow"
    actions   = ["s3:PutObject"]
    resources = ["${aws_s3_bucket.data.arn}/*"]
  }

  # Lambda のイベントソースマッピングがキューを読むために必要。
  statement {
    sid    = "ConsumeScanJobs"
    effect = "Allow"
    actions = [
      "sqs:ReceiveMessage",
      "sqs:DeleteMessage",
      "sqs:GetQueueAttributes",
    ]
    resources = [aws_sqs_queue.scan_jobs.arn]
  }

  # 外部 API キーの読み出し。**この 2 つの Secret に限定する。**
  # 値は Terraform 管理外(secrets.tf)。
  statement {
    sid     = "ReadApiKeySecrets"
    effect  = "Allow"
    actions = ["secretsmanager:GetSecretValue"]
    resources = [
      aws_secretsmanager_secret.serpapi_api_key.arn,
      aws_secretsmanager_secret.anthropic_api_key.arn,
    ]
  }
}

resource "aws_iam_role_policy" "worker_lambda" {
  name   = "${local.name_prefix}-worker-lambda"
  role   = aws_iam_role.worker_lambda.id
  policy = data.aws_iam_policy_document.worker_lambda.json
}


# ---------------------------------------------------------------------------
# Athena(履歴分析)
# ---------------------------------------------------------------------------

# Glue の ARN はアカウント ID を含むため、実行アカウントを解決する。
data "aws_caller_identity" "current" {}
#
# `gapatlas history` を実行するための最小権限。**Lambda には付けない。**
# Athena は Web のリアルタイム表示に使わず履歴分析専用であり
# (docs/architecture.md「Athena」)、実行するのは運用者の手元か、将来の
# 分析ジョブである。API / Worker のロールに付けると Least Privilege を崩す。

data "aws_iam_policy_document" "athena_reader" {
  statement {
    sid = "RunHistoryQueries"
    actions = [
      "athena:StartQueryExecution",
      "athena:GetQueryExecution",
      "athena:GetQueryResults",
      "athena:StopQueryExecution",
    ]
    resources = [aws_athena_workgroup.main.arn]
  }

  statement {
    sid = "ReadGlueCatalog"
    actions = [
      "glue:GetDatabase",
      "glue:GetTable",
      "glue:GetPartitions",
    ]
    resources = [
      "arn:aws:glue:${var.aws_region}:${data.aws_caller_identity.current.account_id}:catalog",
      aws_glue_catalog_database.main.arn,
      "arn:aws:glue:${var.aws_region}:${data.aws_caller_identity.current.account_id}:table/${aws_glue_catalog_database.main.name}/*",
    ]
  }

  statement {
    sid       = "ReadCuratedScores"
    actions   = ["s3:GetObject", "s3:ListBucket"]
    resources = [aws_s3_bucket.data.arn, "${aws_s3_bucket.data.arn}/curated/*"]
  }

  statement {
    sid       = "WriteQueryResults"
    actions   = ["s3:GetObject", "s3:PutObject", "s3:ListBucket"]
    resources = [aws_s3_bucket.athena_results.arn, "${aws_s3_bucket.athena_results.arn}/*"]
  }
}

resource "aws_iam_policy" "athena_reader" {
  name        = "${local.name_prefix}-athena-reader"
  description = "gapatlas history を実行するための最小権限。ロールへは紐付けない。"
  policy      = data.aws_iam_policy_document.athena_reader.json
}
