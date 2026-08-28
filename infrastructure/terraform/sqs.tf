# SQS — Lambda API と Lambda Worker の間の非同期境界
# (docs/architecture.md「非同期処理」)。
#
#   POST /scans -> 国ごとに 1 メッセージ(JP / US / GB / DE / IN)
#                   -> Lambda Worker が 1 メッセージ 1 国を処理
#
# maxReceiveCount = 3 を超えたメッセージは DLQ へ。

resource "aws_sqs_queue" "dlq" {
  name = "${local.name_prefix}-scan-jobs-dlq"

  # 障害調査のため最大(14 日)まで残す。DLQ へ落ちた時点で
  # 「何が起きたか」を後から読めることが価値なので、短くしない。
  message_retention_seconds = var.dlq_message_retention_seconds

  sqs_managed_sse_enabled = true
}

# この DLQ を redrive 先にできるのはメインキューだけに限定する。
resource "aws_sqs_queue_redrive_allow_policy" "dlq" {
  queue_url = aws_sqs_queue.dlq.id

  redrive_allow_policy = jsonencode({
    redrivePermission = "byQueue"
    sourceQueueArns   = [aws_sqs_queue.scan_jobs.arn]
  })
}

resource "aws_sqs_queue" "scan_jobs" {
  name = "${local.name_prefix}-scan-jobs"

  # 可視化タイムアウトは **Lambda Worker のタイムアウトより長くする**。
  # 短いと、まだ処理中のメッセージが他の Worker へ再配信され、
  # 同じ国を二重にスキャンして SerpApi のクォータを無駄に消費する。
  # AWS の推奨に従い関数タイムアウトの 6 倍にする(イベントソースが
  # 再試行する余地を残すため)。
  #   120 秒 x 6 = 720 秒
  # 代償として、恒久的に失敗するメッセージが DLQ へ届くまで最悪
  # 720 秒 x 3 回 = 36 分かかる。デモ規模では許容し、急ぎで DLQ を
  # 見たい場合は worker_lambda_timeout_seconds を下げること。
  visibility_timeout_seconds = var.worker_lambda_timeout_seconds * 6

  message_retention_seconds = var.sqs_message_retention_seconds

  # ロングポーリング。空受信のリクエスト課金を減らす。
  receive_wait_time_seconds = 20

  sqs_managed_sse_enabled = true

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.dlq.arn
    maxReceiveCount     = var.sqs_max_receive_count # docs/architecture.md: 3
  })
}
