# API Gateway HTTP API — docs/api.md の 4 エンドポイント。
#
#   GET  /api/v1/topics
#   POST /api/v1/scans
#   GET  /api/v1/scans/{scan_id}
#   GET  /api/v1/scans/{scan_id}/countries/{country}
#
# REST API(v1)ではなく HTTP API(v2)。MVP は認証なし・単純なプロキシ統合だけで、
# HTTP API のほうが安く、レイテンシも小さい。

resource "aws_apigatewayv2_api" "main" {
  name          = "${local.name_prefix}-http-api"
  protocol_type = "HTTP"
  description   = "GapAtlas MVP API (docs/api.md)"

  # CORS は Frontend origin へ限定する
  # (docs/requirements.md「CORS を Frontend origin へ限定」)。
  # **ワイルドカードにしない。** variables.tf の validation でも禁じている。
  #
  # HTTP API に CORS を設定すると、API Gateway は**統合(Lambda)が返した
  # CORS ヘッダを無視して**自分の設定を使う。ヘッダが二重にならないので、
  # ハンドラ側(api/http.py)の cors_headers と併存させて問題ない。
  cors_configuration {
    allow_origins = var.cors_allowed_origins
    allow_methods = ["GET", "POST", "OPTIONS"]
    allow_headers = ["content-type"]
    max_age       = 300

    # Cookie / 認証情報は使わない(MVP は Login を作らない)。
    allow_credentials = false
  }
}

resource "aws_apigatewayv2_integration" "api_lambda" {
  api_id = aws_apigatewayv2_api.main.id

  integration_type = "AWS_PROXY"
  integration_uri  = aws_lambda_function.api.invoke_arn

  # api/http.py の parse_request は payload format version 2.0 を前提にしている。
  payload_format_version = "2.0"

  # 統合のタイムアウトは Lambda 側のタイムアウトより少しだけ長くする。
  # 逆にすると、Lambda がまだ動いているのに API が 504 を返す。
  timeout_milliseconds = (var.api_lambda_timeout_seconds + 1) * 1000
}

locals {
  # docs/api.md の 4 ルート。ここに無いパスは 404(ハンドラ側の
  # RouteNotFoundError ではなく API Gateway が返す)。
  api_routes = [
    "GET /api/v1/topics",
    "POST /api/v1/scans",
    "GET /api/v1/scans/{scan_id}",
    "GET /api/v1/scans/{scan_id}/countries/{country}",
  ]
}

resource "aws_apigatewayv2_route" "routes" {
  for_each = toset(local.api_routes)

  api_id    = aws_apigatewayv2_api.main.id
  route_key = each.value
  target    = "integrations/${aws_apigatewayv2_integration.api_lambda.id}"
}

resource "aws_apigatewayv2_stage" "default" {
  api_id = aws_apigatewayv2_api.main.id

  # $default ステージにすると URL にステージ名が入らず、
  # lambda_handlers.py の MAX_PREFIX_OFFSET(ステージ名 1 段まで許容)にも
  # 依存しない素直な /api/v1/... になる。
  name        = "$default"
  auto_deploy = true

  access_log_settings {
    destination_arn = aws_cloudwatch_log_group.api_gateway_access.arn

    # 構造化ログ(JSON 1 行)。docs/architecture.md「Observability」。
    # requestId は Lambda 側のログの request_id と突き合わせるために入れる。
    format = jsonencode({
      requestId          = "$context.requestId"
      requestTime        = "$context.requestTime"
      httpMethod         = "$context.httpMethod"
      routeKey           = "$context.routeKey"
      path               = "$context.path"
      status             = "$context.status"
      responseLatency    = "$context.responseLatency"
      integrationLatency = "$context.integration.latency"
      integrationStatus  = "$context.integration.status"
      errorMessage       = "$context.error.message"
    })
  }

  default_route_settings {
    # SerpApi のクォータを守るための保険。ここで絞っておかないと、
    # ポーリング(2 秒間隔)や連打がそのまま SQS へ流れる。
    throttling_rate_limit  = var.api_throttling_rate_limit
    throttling_burst_limit = var.api_throttling_burst_limit

    # 詳細メトリクスは追加課金になる。デモでは要らない。
    detailed_metrics_enabled = false
  }
}

# API Gateway からの Lambda 呼び出しを許可する。
# source_arn をこの API のものに限定しており、他の API からは呼べない。
resource "aws_lambda_permission" "api_gateway" {
  statement_id  = "AllowInvokeFromHttpApi"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.api.function_name
  principal     = "apigateway.amazonaws.com"

  # "<execution_arn>/*/*" = この API の全ステージ・全ルート。
  # ルートごとに 4 本へ分けることもできるが、同じ関数を指す 4 本の
  # 許可になるだけで実効的な権限は変わらないため、1 本にまとめている。
  source_arn = "${aws_apigatewayv2_api.main.execution_arn}/*/*"
}
