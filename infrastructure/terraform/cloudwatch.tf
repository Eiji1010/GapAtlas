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
