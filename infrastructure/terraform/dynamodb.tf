# DynamoDB — 最新結果と UI 表示用データ(docs/architecture.md「DynamoDB」)。
#
# | PK              | SK                  | 内容                       |
# |-----------------|---------------------|----------------------------|
# | SCAN#{scan_id}  | META                | スキャン全体の状態・ランキング |
# | SCAN#{scan_id}  | COUNTRY#{country}   | 国別の結果と Evidence        |
#
# 属性名は backend/src/gapatlas/adapters/dynamodb/table.py の
# PARTITION_KEY_ATTRIBUTE / SORT_KEY_ATTRIBUTE / TTL_ATTRIBUTE と一致させること。
# **片方だけ変えるとアプリが ValidationException で落ちる。**

resource "aws_dynamodb_table" "main" {
  name = var.dynamodb_table_name

  # スキャンは人が押したときだけ走る、極端にスパイクの多いワークロード。
  # プロビジョンド容量は張り付き待機のコストが無駄になるため使わない。
  billing_mode = "PAY_PER_REQUEST"

  hash_key  = "PK" # table.py: PARTITION_KEY_ATTRIBUTE
  range_key = "SK" # table.py: SORT_KEY_ATTRIBUTE

  # DynamoDB はキー属性だけを宣言する(それ以外はスキーマレス)。
  attribute {
    name = "PK"
    type = "S"
  }

  attribute {
    name = "SK"
    type = "S"
  }

  # デモ後に自動削除するための TTL(docs/architecture.md)。
  # 属性名は table.py の TTL_ATTRIBUTE と一致させること。
  ttl {
    attribute_name = "ttl" # table.py: TTL_ATTRIBUTE
    enabled        = true
  }

  # デモ用途。データは再スキャンで再生成できるため PITR は使わない
  # (有効にするとストレージ量に応じた継続課金が発生する)。
  point_in_time_recovery {
    enabled = false
  }

  # 保存時の暗号化は AWS 所有キーによる既定の暗号化に任せる。
  # 顧客管理 KMS キーは月額と KMS リクエスト料が乗るため、
  # 個人情報を持たない(AGENTS.md)デモでは見合わない。
}
