# CloudWatch Logs — 構造化ログの出力先(docs/architecture.md「Observability」)。
#
# ロググループを **Terraform 側で先に作る**。Lambda に自動生成させると
#   - 保持期間が「失効しない」になり、ログ保管料が静かに積み上がる
#   - 実行ロールに logs:CreateLogGroup が必要になり、
#     Resource が "*" 相当に広がって Least Privilege から外れる
# ため。作成済みなら Lambda は CreateLogStream / PutLogEvents だけでよい。

resource "aws_cloudwatch_log_group" "api_lambda" {
  # Lambda が書き込む先の名前は固定(/aws/lambda/<関数名>)。
  name              = "/aws/lambda/${local.name_prefix}-api"
  retention_in_days = var.log_retention_days
}

resource "aws_cloudwatch_log_group" "worker_lambda" {
  name              = "/aws/lambda/${local.name_prefix}-worker"
  retention_in_days = var.log_retention_days
}

resource "aws_cloudwatch_log_group" "api_gateway_access" {
  name              = "/aws/apigateway/${local.name_prefix}-http-api"
  retention_in_days = var.log_retention_days
}


# ---------------------------------------------------------------------------
# アラーム
# ---------------------------------------------------------------------------
#
# DLQ は 14 日保持するので調査はできるが、**落ちたことに気付く仕掛けが無い**と
# 意味がない。通知先(SNS)は運用の判断なので作らず、アラーム自体だけを置く。
# 通知が要る場合は `alarm_actions` に SNS トピックの ARN を足すこと。

resource "aws_cloudwatch_metric_alarm" "dlq_not_empty" {
  alarm_name        = "${local.name_prefix}-dlq-not-empty"
  alarm_description = "DLQ にメッセージが溜まっている。Worker が3回失敗したことを意味する。"

  namespace   = "AWS/SQS"
  metric_name = "ApproximateNumberOfMessagesVisible"
  dimensions = {
    QueueName = aws_sqs_queue.dlq.name
  }

  statistic           = "Maximum"
  period              = 300
  evaluation_periods  = 1
  threshold           = 0
  comparison_operator = "GreaterThanThreshold"
  # データが無い = メッセージが無い。欠測でアラームを鳴らさない。
  treat_missing_data = "notBreaching"
}

resource "aws_cloudwatch_metric_alarm" "worker_errors" {
  alarm_name        = "${local.name_prefix}-worker-errors"
  alarm_description = "Worker Lambda が例外で終了している。実装バグか権限設定の誤り。"

  namespace   = "AWS/Lambda"
  metric_name = "Errors"
  dimensions = {
    FunctionName = aws_lambda_function.worker.function_name
  }

  statistic           = "Sum"
  period              = 300
  evaluation_periods  = 1
  threshold           = 0
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"
}
