# インフラ (Terraform)

GapAtlas の Backend / Data Platform を Terraform で定義します。構成の正本は
[アーキテクチャ](../docs/architecture.md)「全体構成」です。

```text
Cloudflare Pages (別トラック)
        |  HTTPS / 2秒 Polling
        v
API Gateway HTTP API
        v
Lambda API (Python)
        v
      SQS  ──(maxReceiveCount=3)──> DLQ
        v
Lambda Worker (Python, reserved concurrency = 2)
        ├─ DynamoDB … 最新結果・UI表示用
        └─ S3       … raw / normalized / curated
                  └─ Glue Data Catalog → Athena … 履歴分析専用
```

- Lambda は **VPC に入れません**。**NAT Gateway も作りません**
- ECS / EKS / EC2 / RDS / Redis / Step Functions / Kafka / Elasticsearch /
  OpenSearch は作りません（[AGENTS.md](../AGENTS.md)「作らないもの」）
- リモート state（backend）は設定していません（`apply` しないため）

## ディレクトリ

```text
infrastructure/
├── README.md
└── terraform/
    ├── main.tf                    # provider / required_providers / locals
    ├── variables.tf               # 入力変数（すべて既定値あり）
    ├── outputs.tf                 # 出力値（秘密情報は出さない）
    ├── dynamodb.tf                # DynamoDB テーブル
    ├── s3.tf                      # Data Lake / Athena 結果バケット
    ├── sqs.tf                     # ジョブキュー + DLQ
    ├── lambda.tf                  # Lambda API / Worker / イベントソース
    ├── apigateway.tf              # HTTP API / ルート / ステージ
    ├── glue.tf                    # Glue データベース / gap_scores テーブル
    ├── athena.tf                  # ワークグループ / 保存済みクエリ
    ├── iam.tf                     # Lambda ごとの最小権限ロール
    ├── cloudwatch.tf              # ロググループと保持期間
    ├── secrets.tf                 # Secrets Manager（箱のみ）
    ├── terraform.tfvars.example   # 記入例（実値は書かない）
    └── placeholder/               # Lambda パッケージのダミー
```

## 作成するリソース

| 種別 | リソース | 要点 |
|---|---|---|
| DynamoDB | `aws_dynamodb_table.main` | `PK` / `SK` / `ttl`、PAY_PER_REQUEST |
| S3 | `aws_s3_bucket.data` ほか 4 リソース | Block Public Access 全 4 項目、SSE-S3、バージョニング無効、MPU 中断の掃除 |
| S3 | `aws_s3_bucket.athena_results` ほか 4 リソース | Athena 結果用。7 日で失効 |
| SQS | `aws_sqs_queue.scan_jobs` / `.dlq` / `aws_sqs_queue_redrive_allow_policy.dlq` | `maxReceiveCount = 3`、可視化タイムアウト 720 秒 |
| Lambda | `aws_lambda_function.api` / `.worker` | ハンドラは backend のコードと一致。Worker は予約済み同時実行 2 |
| Lambda | `aws_lambda_event_source_mapping.worker` | `batch_size = 1`、`maximum_concurrency = 2` |
| API Gateway | `aws_apigatewayv2_api` / `_integration` / `_route` × 4 / `_stage` | HTTP API、CORS は origin 限定、`$default` ステージ |
| Lambda 権限 | `aws_lambda_permission.api_gateway` | この API からの呼び出しのみ許可 |
| Glue | `aws_glue_catalog_database.main` / `aws_glue_catalog_table.gap_scores` | パーティション射影（`topic` / `country` / `dt`） |
| Athena | `aws_athena_workgroup.main` / `aws_athena_named_query.country_score_history` | 結果出力先を強制、スキャン量上限あり |
| IAM | ロール 2 + インラインポリシー 2 | Lambda ごとに最小権限 |
| CloudWatch Logs | ロググループ 3 | 保持 14 日 |
| Secrets Manager | シークレット 2（**値は入れない**） | SerpApi / Anthropic の API キー |

## `terraform apply` は行いません

[要件定義](../docs/requirements.md)「依頼書からの逸脱」のとおり、本プロジェクトでは
**コード作成と `validate` までにとどめ、`apply` は行いません**。AWS アカウントへの
課金と汚染を避けるためです。[AGENTS.md](../AGENTS.md)「禁止事項」にも
`terraform apply` を実行しないと明記されています。

### 検証（これだけ実行する）

```bash
cd infrastructure/terraform
terraform fmt -recursive -check
terraform init -backend=false
terraform validate
```

リポジトリのルートからなら `make tf-validate` でも同じことができます。

`terraform plan` は AWS 認証情報を必要とするため、このリポジトリの作業では
実行しません（`make tf-plan` は残してありますが、認証情報がある環境専用です）。

### 実際にデプロイする場合の手順

**この手順は未検証です**（`apply` していないため）。実行する場合は、課金と
リソース作成が発生することを理解したうえで行ってください。

1. **state の置き場を決める。** 現状はローカル state です。複数人で扱うなら
   S3 + DynamoDB ロックの backend を `main.tf` に追加してから初期化する
2. **バケット名を一意にする。** `terraform.tfvars.example` を
   `terraform.tfvars` にコピーし、`s3_bucket_name` と
   `athena_results_bucket_name` を一意な名前に変える（S3 のバケット名は
   グローバルに一意）
3. **Lambda パッケージを作る**（次節）。展開先を
   `lambda_package_source_dir` に指定する
4. 認証情報を用意して初期化・確認・適用する

   ```bash
   cd infrastructure/terraform
   terraform init
   terraform plan -out=tfplan
   terraform apply tfplan
   ```

5. **Secrets Manager へ API キーを入れる**（値は Terraform 管理外。次節）
6. `terraform output api_base_url` を Frontend の API 接続先に設定する
7. `terraform output` の `cors_allowed_origins` 相当（Cloudflare Pages の
   origin）を `terraform.tfvars` に追記して再適用する

後片付けは `terraform destroy` です。S3 バケットにオブジェクトが残っていると
削除に失敗するので、先に空にしてください（`force_destroy` は**あえて付けて
いません**。取り違えでデータを消さないため）。

## Lambda デプロイパッケージの作り方

**このリポジトリにはまだデプロイパッケージがありません。**

### 現在の扱い（判断）

`aws_lambda_function.filename` に存在しないパスを直書きすると、`plan` の時点で
ファイルが読めずに失敗し、Terraform コードそのものの検証ができなくなります。
そこで `data "archive_file"` で `placeholder/` を zip 化したダミーを既定にして、
パッケージが無い状態でも `validate` と `plan` が通るようにしています。

```hcl
# lambda.tf
locals {
  lambda_package_source_dir = (
    var.lambda_package_source_dir != ""
    ? var.lambda_package_source_dir
    : "${path.module}/placeholder"
  )
}
```

`placeholder/` の zip をそのままデプロイしてもハンドラは見つかりません。
実際にデプロイするときは `lambda_package_source_dir` に本物の展開先を渡します。
API と Worker は**同じパッケージ**を使い、ハンドラ名だけが違います。

### ビルド手順（概略・未検証）

Lambda のランタイムは `python3.12`、アーキテクチャは `arm64` です。
ネイティブ拡張を含む依存（`pydantic-core` など）があるため、**ターゲットに
合わせたホイールを取得する**必要があります。

```bash
# 1. 作業ディレクトリ
BUILD=$(mktemp -d)

# 2. 依存を lock から解決してエクスポート
cd backend
uv export --frozen --no-dev --extra aws --extra llm --no-emit-project > "$BUILD/requirements.txt"

# 3. Lambda のターゲット向けにインストール
#    --python-platform / --target で arm64 + cp312 のホイールを取る
uv pip install \
  --requirements "$BUILD/requirements.txt" \
  --python-platform aarch64-manylinux2014 \
  --python-version 3.12 \
  --only-binary :all: \
  --target "$BUILD/package"

# 4. アプリのコードを重ねる（src レイアウトなので src/ 直下を配置する）
cp -R backend/src/gapatlas "$BUILD/package/gapatlas"

# 5. QueryProfile の YAML も同梱する（config ローダーが読む）
cp -R config "$BUILD/package/config"

# 6. Terraform へ渡す
cd infrastructure/terraform
terraform apply -var="lambda_package_source_dir=$BUILD/package"
```

`boto3` / `botocore` は Lambda のランタイムに同梱されているので、
サイズが 50MB（zip）を超えるようなら依存から外すことを検討してください。
ただしランタイム同梱版はバージョンが古いことがあるため、外す場合は
実際に動くことを確認してください。

パッケージだけを差し替えたいときは Terraform を経由せずに次でも更新できます
（state と実体がずれるので、恒久的な運用にはしないこと）。

```bash
aws lambda update-function-code \
  --function-name "$(terraform output -raw api_lambda_function_name)" \
  --zip-file fileb://gapatlas-lambda.zip
```

## backend のコードと一致させる必要がある定数

**片方だけ変えると壊れます。** 変更するときは必ず両方を同時に直してください。

| 種別 | 値 | backend 側の正本 | Terraform 側 |
|---|---|---|---|
| DynamoDB ハッシュキー | `PK` | `adapters/dynamodb/table.py` `PARTITION_KEY_ATTRIBUTE` | `dynamodb.tf` `hash_key` |
| DynamoDB レンジキー | `SK` | `adapters/dynamodb/table.py` `SORT_KEY_ATTRIBUTE` | `dynamodb.tf` `range_key` |
| DynamoDB TTL 属性 | `ttl` | `adapters/dynamodb/table.py` `TTL_ATTRIBUTE` | `dynamodb.tf` `ttl.attribute_name` |
| S3 curated プレフィックス | `curated/gap_scores/` | `adapters/s3/keys.py` `CURATED_PREFIX` / `CURATED_DATASET` | `main.tf` `local.curated_location`、`glue.tf` `location` |
| パーティション列と順序 | `topic` → `country` → `dt` | `adapters/s3/keys.py` `curated_key()`、`athena.py` `PARTITION_COLUMNS` | `glue.tf` `partition_keys` と `storage.location.template` |
| `dt` の形式 | `%Y-%m-%d` ↔ `yyyy-MM-dd` | `adapters/s3/keys.py` `DATE_FORMAT`、`athena.py` `_DATE_FORMAT_EQUIVALENTS` | `glue.tf` `projection.dt.format` |
| 射影の開始日 | `2026-01-01` | `adapters/s3/athena.py` `PROJECTION_DATE_RANGE_START` | `variables.tf` `partition_date_range_start` |
| Glue データベース名 | `gapatlas` | `adapters/s3/athena.py` `GLUE_DATABASE_NAME` | `variables.tf` `glue_database_name` |
| Glue テーブル名 | `gap_scores` | `adapters/s3/athena.py` `GAP_SCORES_TABLE_NAME` | `variables.tf` `gap_scores_table_name` |
| テーブルの列と型 | `scan_id` ほか 10 列 | `adapters/s3/athena.py` `gap_scores_table_ddl()` | `glue.tf` `columns` |
| SerDe | `org.openx.data.jsonserde.JsonSerDe` | `adapters/s3/athena.py` | `glue.tf` `ser_de_info` |
| 国 / トピックの射影値 | `JP,US,GB,DE,IN` / `elder_care` | `domain/models/common.py` `Country` / `TopicId` | `variables.tf` `partition_countries` / `partition_topics` |
| API ハンドラ名 | `gapatlas.api.lambda_handlers.api_handler` | `api/lambda_handlers.py` | `lambda.tf` `handler` |
| Worker ハンドラ名 | `gapatlas.api.worker_handler.worker_handler` | `api/worker_handler.py` | `lambda.tf` `handler` |
| SQS のバッチサイズ | `1` | `adapters/sqs/decode.py` / `api/worker_handler.py` | `lambda.tf` `batch_size` |
| API ベースパス | `/api/v1` | `api/lambda_handlers.py` `API_PREFIX` | `apigateway.tf` `route_key` |
| 環境変数名 | 下表 | `config/settings.py` `load_settings()` | `lambda.tf` `environment.variables` |

### 危険な失敗モード

**Glue のパーティション射影がずれると、Athena はエラーではなく 0 件を返します。**
`dt` の形式、`storage.location.template` の並び、`Country` / `TopicId` の値の
いずれかが S3 のキーと食い違っても、クエリは成功したように見えます。
`keys.py` を変更したら必ず `glue.tf` も直してください。

### Lambda へ渡す環境変数

`config/settings.py` の `load_settings()` が読む名前と一致させています。

| 変数 | API | Worker | 備考 |
|---|:--:|:--:|---|
| `PERSISTENCE_MODE` | ✓ | ✓ | `aws` 固定。既定（`memory`）のままだと AWS へ書かない |
| `DYNAMODB_TABLE_NAME` | ✓ | ✓ | |
| `S3_BUCKET_NAME` | ✓ | ✓ | |
| `LOG_LEVEL` | ✓ | ✓ | |
| `SQS_QUEUE_URL` | ✓ | — | API がジョブを投入する先 |
| `CORS_ALLOWED_ORIGINS` | ✓ | — | カンマ区切り |
| `SERPAPI_MODE` / `SERPAPI_TIMEOUT_SECONDS` / `SERPAPI_MAX_RETRIES` | — | ✓ | |
| `LLM_MODE` / `ANTHROPIC_MODEL` / `ANTHROPIC_TIMEOUT_SECONDS` / `ANTHROPIC_MAX_RETRIES` | — | ✓ | |
| `SERPAPI_API_KEY_SECRET_ARN` / `ANTHROPIC_API_KEY_SECRET_ARN` | — | ✓ | **backend 側は未対応**（次節） |

**`AWS_REGION` は渡していません。** Lambda の予約済み環境変数であり、設定しよう
とすると関数の更新自体が失敗します。`settings.py` は `os.environ` から読みますが、
実行時に Lambda が自動で入れるため問題ありません。

## 秘密情報の渡し方

### 判断: Secrets Manager を使う（値は Terraform 管理外）

[要件定義](../docs/requirements.md)「Security」は「Secret は Secrets Manager
または環境変数」としています。ここでは **Secrets Manager** を選びました。

理由:

1. **環境変数へ直接入れると Terraform の state に平文で残る。** `.tfvars` は
   `.gitignore` 済みですが、state 経由で漏れます。`sensitive = true` を付けても
   state の中身は平文です。「API key を Git に入れない」という要件を、
   運用の注意ではなく仕組みで守れるほうがよい
2. Terraform は「箱」だけを作り、値を一切知らないので、
   `terraform plan` の出力やログにも現れない
3. 読み出しは IAM で Worker のロール、かつ**この 2 つの ARN** だけに絞れる
   （`iam.tf` の `ReadApiKeySecrets`）。CloudTrail にも残る
4. ローテーションしても Terraform の再適用が要らない

そのため `secrets.tf` は `aws_secretsmanager_secret` だけを定義し、
`aws_secretsmanager_secret_version` を**あえて定義していません**。

### 現状の制約（重要・未解決）

`config/settings.py` は API キーを**環境変数**（`SERPAPI_API_KEY` /
`ANTHROPIC_API_KEY`）から読みます。**Secrets Manager から読む実装はまだ
ありません。** そのため:

- Terraform の既定は `SERPAPI_MODE=fixture` / `LLM_MODE=stub` にしてあります
  （[AGENTS.md](../AGENTS.md)「fixture mode を常に維持する」とも整合します）。
  この状態なら API キーは不要で、外部通信ゼロで動きます
- `live` / `anthropic` へ切り替えるには、**backend 側に Secrets Manager からの
  読み出しを追加する必要があります**（`infrastructure/` の担当範囲外）。
  Worker は ARN を `SERPAPI_API_KEY_SECRET_ARN` /
  `ANTHROPIC_API_KEY_SECRET_ARN` で受け取れる状態にしてあります

値の投入（Terraform の外で行う）:

```bash
aws secretsmanager put-secret-value \
  --secret-id gapatlas-dev/serpapi-api-key \
  --secret-string 'ここに実値'
```

**`.tf` にも `.tfvars.example` にも実値を書かないでください。**
`*.tfvars` はリポジトリの `.gitignore` で除外済みです（`*.tfvars.example` のみ追跡）。

## コスト概算（デモ規模・未検証）

前提: `ap-northeast-1`、ハッカソンのデモ期間中に**スキャン数十回・
リクエスト数千件**程度。多くの項目が無料枠に収まります。

| サービス | 課金要素 | 月額の目安 |
|---|---|---:|
| Secrets Manager | シークレット 2 個 × $0.40 | **約 $0.80** |
| CloudWatch Logs | 取り込み $0.76/GB + 保管。デモなら数百 MB 未満 | 約 $0.1〜0.5 |
| Lambda | リクエストと GB 秒。無料枠（月 100 万リクエスト / 40 万 GB 秒）内 | 約 $0 |
| API Gateway HTTP API | 100 万リクエストあたり約 $1.2。数千件なら | 約 $0 |
| DynamoDB | オンデマンド。書き込み 100 万 WRU あたり約 $1.4 | 約 $0 |
| S3 | $0.025/GB・月。データは数 MB〜数十 MB | 約 $0 |
| SQS | 月 100 万リクエストまで無料 | $0 |
| Glue Data Catalog | 100 万オブジェクトまで無料 | $0 |
| Athena | スキャン 1TB あたり $5。1 クエリ最低 10MB 課金 | 約 $0 |
| **合計** | | **月 $1〜3 程度** |

- 固定費の主役は **Secrets Manager**（シークレット 1 個あたり $0.40/月）です。
  使わない期間は削除してください
- **NAT Gateway を作らない**方針により、月 $40 前後の固定費を避けています。
  これが構成上いちばん効いているコスト判断です
- SerpApi と Anthropic API の利用料は AWS の外です。ここには含めていません
- **実際に `apply` していないため、上記はすべて見積りです。**

## 未解決 / 注意事項

- **`apply` していないため、すべて未検証です。** 通っているのは
  `terraform validate`（構文と型の検証）までで、AWS が実際に受け付けるか
  （バケット名の一意性、IAM の実効権限、Glue の射影が意図どおり動くか）は
  確認できていません
- `live` / `anthropic` モードは backend 側の Secrets Manager 対応待ちです
- Frontend（Cloudflare Pages）の origin が確定したら
  `cors_allowed_origins` に追加する必要があります
- CloudWatch アラーム（DLQ にメッセージが溜まったときの通知など）は
  作っていません。MVP の要件に無く、過剰設計を避けたためです
