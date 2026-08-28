# 出力値。Frontend の設定(VITE_API_BASE_URL 相当)と運用手順で使う。
# **秘密情報は出力しない。** Secrets Manager は ARN のみ。

output "api_base_url" {
  description = "API のベース URL。Frontend の API 接続先に設定する(末尾に /api/v1 が付く)。"
  value       = "${aws_apigatewayv2_api.main.api_endpoint}/api/v1"
}

output "api_gateway_endpoint" {
  description = "API Gateway HTTP API のエンドポイント($default ステージ)。"
  value       = aws_apigatewayv2_api.main.api_endpoint
}

output "api_lambda_function_name" {
  description = "Lambda API の関数名。パッケージ更新(update-function-code)で使う。"
  value       = aws_lambda_function.api.function_name
}

output "worker_lambda_function_name" {
  description = "Lambda Worker の関数名。"
  value       = aws_lambda_function.worker.function_name
}

output "dynamodb_table_name" {
  description = "DynamoDB テーブル名(DYNAMODB_TABLE_NAME)。"
  value       = aws_dynamodb_table.main.name
}

output "s3_bucket_name" {
  description = "Data Lake のバケット名(S3_BUCKET_NAME)。"
  value       = aws_s3_bucket.data.id
}

output "sqs_queue_url" {
  description = "ジョブキューの URL(SQS_QUEUE_URL)。"
  value       = aws_sqs_queue.scan_jobs.url
}

output "sqs_dlq_url" {
  description = "DLQ の URL。失敗メッセージの調査に使う。"
  value       = aws_sqs_queue.dlq.url
}

output "glue_database_name" {
  description = "Glue のデータベース名。"
  value       = aws_glue_catalog_database.main.name
}

output "athena_workgroup_name" {
  description = "Athena のワークグループ名。"
  value       = aws_athena_workgroup.main.name
}

output "athena_results_bucket_name" {
  description = "Athena のクエリ結果バケット名。"
  value       = aws_s3_bucket.athena_results.id
}

output "secret_arns" {
  description = "API キーを入れる Secrets Manager の ARN。**値は Terraform 管理外**(secrets.tf)。"
  value = {
    serpapi   = aws_secretsmanager_secret.serpapi_api_key.arn
    anthropic = aws_secretsmanager_secret.anthropic_api_key.arn
  }
}

output "log_group_names" {
  description = "CloudWatch Logs のロググループ名。"
  value = {
    api_lambda    = aws_cloudwatch_log_group.api_lambda.name
    worker_lambda = aws_cloudwatch_log_group.worker_lambda.name
    api_gateway   = aws_cloudwatch_log_group.api_gateway_access.name
  }
}
