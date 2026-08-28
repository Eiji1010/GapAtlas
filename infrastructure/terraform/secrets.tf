# Secrets Manager — 外部 API キーの置き場
# (docs/requirements.md「Secret は Secrets Manager または環境変数」)。
#
# ## なぜ Secrets Manager にしたか
#
# 「環境変数へ直接入れる」を選ぶと、値を Terraform へ渡す必要があり、
# **Terraform の state ファイルへ平文で残る**。`.tfvars` を .gitignore しても
# state 経由で漏れるため、Git に入れないという要件を満たしきれない。
# Secrets Manager なら次が成り立つ。
#
#   1. Terraform は「箱」だけを作り、値を一切知らない
#      (aws_secretsmanager_secret_version を**あえて定義しない**)
#   2. 値の投入・更新・ローテーションは Terraform の外(コンソール / CLI)
#   3. 読み出しは CloudTrail に残り、IAM で Worker のロールだけに絞れる
#
# ## 現状の制約(重要)
#
# backend/src/gapatlas/config/settings.py は API キーを**環境変数**
# (SERPAPI_API_KEY / ANTHROPIC_API_KEY)から読む。Secrets Manager を読む
# 実装はまだ無い。したがって:
#
#   - Terraform の既定は SERPAPI_MODE=fixture / LLM_MODE=stub のままにする
#     (AGENTS.md「fixture mode を常に維持する」とも整合する)
#   - live / anthropic へ切り替えるには backend 側に Secrets Manager からの
#     読み出しを足す必要がある。詳細は infrastructure/README.md「秘密情報の
#     渡し方」を参照
#
# ここで作るのは箱と、Worker から読むための ARN(iam.tf / lambda.tf)だけ。

resource "aws_secretsmanager_secret" "serpapi_api_key" {
  name        = "${local.name_prefix}/serpapi-api-key"
  description = "SerpApi の API キー。値は Terraform 管理外(コンソール / CLI で投入する)。"

  # デモ環境では作り直しを繰り返すため、削除後の復旧待機を最短にする。
  # 本番運用へ移すときは既定(30 日)へ戻すこと。
  recovery_window_in_days = 7
}

resource "aws_secretsmanager_secret" "anthropic_api_key" {
  name        = "${local.name_prefix}/anthropic-api-key"
  description = "Anthropic API の API キー。値は Terraform 管理外。"

  recovery_window_in_days = 7
}
