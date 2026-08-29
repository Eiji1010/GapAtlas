# アーキテクチャ

## 全体構成

Frontend のみ Cloudflare、Backend / Data Platform は AWS。

```text
Cloudflare Pages (React + TypeScript)
        |  HTTPS / 2秒 Polling
        v
API Gateway HTTP API
        |
        v
Lambda API (Python)
        |
        v
      SQS  ──(maxReceiveCount=3)──> DLQ
        |
        v
Lambda Worker (Python, reserved concurrency = 2)
        |
        +------ SerpApi
        +------ Anthropic API (分類 / Opportunity Brief)
        +------ DynamoDB   … 最新結果・UI表示用
        +------ S3         … raw / normalized / curated
                  |
                  v
           Glue Data Catalog
                  |
                  v
               Athena       … 履歴分析専用
```

- Lambda は **VPC に入れない**。**NAT Gateway を作らない**
- WebSocket / SSE / Step Functions / ECS / EKS / EC2 / RDS / Redis は使わない
- Monitoring は CloudWatch
- IaC は Terraform(`apply` は行わない)

## バックエンドの層

Clean Architecture を過剰適用しない。層は5つ。

```text
backend/src/gapatlas/
├── api/           # Lambda ハンドラ。HTTP ↔ ユースケースの変換のみ
├── application/   # ユースケース。スキャンのオーケストレーション
├── domain/
│   ├── models/    # Pydantic モデル。全層が共有する凍結契約
│   └── scoring/   # スコア計算。純粋関数のみ。I/O 禁止
├── adapters/
│   ├── serpapi/   # SerpApi クライアント + fixture 実装 + キャッシュ
│   ├── llm/       # LLM クライアント + stub 実装
│   ├── dynamodb/  # 最新結果の読み書き
│   ├── s3/        # raw / normalized / curated と Athena 定義
│   └── sqs/       # ジョブ投入とメッセージ復元
└── config/        # 設定、QueryProfile ローダー
```

### 依存の向き

```text
api → application → domain
              ↓
          adapters (Protocol 経由で注入)
```

- `domain` は他のどの層にも依存しない
- `domain/scoring` はネットワーク・ファイルI/O・現在時刻取得・乱数を持たない。**時刻は引数で受け取る**
- `application` はアダプタを **Protocol(構造的部分型)** として受け取る。具体実装に依存しない
- 外部APIの生レスポンスは adapters 内で正規化モデルへ変換する。**生の dict を domain へ流さない**
- **正規化関数(`adapters/serpapi/normalize.py`)は純粋関数であり、application から直接呼んでよい。** `SerpApiClient` Protocol が生の dict を返すのは、raw JSON を無加工で S3 へ保存する要件があるため。application は「取得(Protocol) → 正規化(純粋関数) → domain」の順に組み立てる。**domain へ渡すのは正規化済みモデルだけ**という制約は維持する

## データフロー

```text
QueryProfile (YAML)
      ↓
SerpApi Adapter (fixture | live)  ──> raw JSON を S3 raw/ へ保存
      ↓
Normalizer  … 生レスポンス → 正規化モデル
      ↓
LLM Classifier (stub | anthropic)  … 分類のみ。スコアは決めない
      ↓
Scoring Engine (純粋関数)  … Need Gap Signal Score
      ↓
Confidence Engine (純粋関数)  … Evidence Confidence
      ↓
CountryResult
      ↓
   ┌──┴──┐
DynamoDB   S3 normalized/ curated/
(最新)      (履歴 → Glue → Athena)
```

## 非同期処理

```text
POST /scans
   ↓
SCAN META を DynamoDB へ作成 (status=processing)
   ↓
国ごとに Job を SQS へ投入 (JP / US / GB / DE / IN)
   ↓
Lambda Worker が1メッセージ1国を処理
   ↓
完了ごとに DynamoDB の COUNTRY item を更新
   ↓
全国完了後、Top1 について Opportunity Brief を生成
```

- Reserved concurrency は 2 程度から始める(SerpApi のレート制限を考慮)
- 各 Worker 内では 4つの SerpApi 呼び出しを Concurrency Limit 付きで並列化してよい
- `maxReceiveCount = 3` を超えたメッセージは DLQ へ
- Maps は 5か国のランキング確定後、Top 2 についてのみ取得する

## DynamoDB

Operational DB。最新状態と UI 表示用データのみ。アクセスパターンを優先し、過剰な Single Table Design にしない。

| PK | SK | 内容 |
|---|---|---|
| `SCAN#{scan_id}` | `META` | スキャン全体の状態、進捗、ランキング、Opportunity Brief |
| `SCAN#{scan_id}` | `COUNTRY#{country}` | 国別の結果と Evidence |

COUNTRY item の例:

```json
{
  "PK": "SCAN#scan_abc123",
  "SK": "COUNTRY#JP",
  "country": "JP",
  "status": "completed",
  "need_gap_score": 86,
  "confidence": 92,
  "components": { "demand": 91, "pain": 84, "solution_gap": 78, "news_urgency": 83 },
  "ttl": 1790000000
}
```

`CountryResult` のフィールドを属性へ展開して保存する(JSON 1属性に固めない)。障害調査でコンソールから読めること、将来 `status` で `FilterExpression` を使えることを優先する。下位スコアは `components` 配下にネストする(`CountryResult` の形が正本)。

`ttl` は**保存時刻**から算出する(既定 30 日)。`ScanSummary` には時刻フィールドが無く `computed_at` を基準にできないため、また TTL の目的が「デモ後に自動削除する」ことであるため。Terraform の `ttl { attribute_name = "ttl" }` と属性名を一致させること。

**永続化のモードは `PERSISTENCE_MODE`**(`memory` / `aws`、既定 `memory`)。`SERPAPI_MODE=fixture` と同じ思想で、既定では AWS へ接続しない。テーブル名やバケット名の有無から AWS 利用を推測してはいけない(どちらも既定値を持つ必須項目なので「未設定」を表現できない)。

アクセスパターン:

1. `GET /scans/{scan_id}` → PK 単一、SK `META` の GetItem
2. 進捗とランキング → PK 単一の Query(`SCAN#{id}` 配下すべて)
3. `GET /scans/{scan_id}/countries/{country}` → PK+SK の GetItem

TTL 属性を持たせ、デモ後に自動削除できるようにする。

## S3 Data Lake

Bucket: `gapatlas-data`(public access は完全にブロック)

```text
raw/
  source=trends/topic=elder_care/country=JP/dt=2026-08-28/{scan_id}.json
  source=related_queries/...
  source=search/...
  source=news/...
  source=maps/...

normalized/
  topic=elder_care/country=JP/dt=2026-08-28/...

curated/
  gap_scores/topic=elder_care/country=JP/dt=2026-08-28/...
```

Partition key は `topic` / `country` / `dt`。

- `raw/` は SerpApi のレスポンスを **JSON のまま**保存する
- **非同期経路(Lambda Worker)では `normalized/` に Maps が含まれない。** Maps はランキング確定後に Top2 だけへ足すが、そのとき Worker は他ソースの正規化済みデータを持っていない(SQS メッセージにも DynamoDB にも入っていない)。部分的な内容で同じキーを上書きすると事実と違う内容が残るため、`normalized/` は書き直さない。Maps の取得結果は `raw/source=maps/...` と `curated/` に残る。**同期実行(CLI)では Maps を含む**ので、両者の `normalized/` は一致しない
- `normalized/` `curated/` は **JSON Lines**(1オブジェクト1レコード)。Parquet は `pyarrow` の追加が必要で、Lambda のパッケージサイズが 40〜60MB 増えるため MVP では採用しない。切り替える場合は Glue の `ROW FORMAT SERDE` / `STORED AS` も同時に変更する
- Glue は**パーティション射影**を使う。`MSCK REPAIR TABLE` 方式は新しい `dt` ごとに実行が必要で、忘れると**エラーではなく 0 件**が返る(デモで最も危険な失敗モード)。代償として、射影範囲外の `dt` と `Country` Enum に無い国は不可視になる。**国やトピックを増やすときはテーブル定義の更新が必須**

## Athena

**Web のリアルタイム表示には使わない。履歴分析専用。**

```text
DynamoDB = 最新結果
Athena   = 過去分析
```

MVP では最低限「国ごとの Need Gap Score 履歴」を Athena から取得できるようにする。

## Cache

| Source | TTL |
|---|---:|
| Trends | 6h |
| Related Queries | 6h |
| Search | 6h |
| News | 1h |
| Maps | 24h |
| LLM Classification | input hash が変わるまで |
| AI Insight | evidence hash が変わるまで |

キャッシュキーには `query_profile_version` を含める。Cache Hit の場合 SerpApi を再度呼ばない。

実装は `adapters/serpapi/cache.py`(`CachingSerpApiClient`)。**live モードだけを包む。** fixture を包むと2回目以降の `cache_age_seconds` が 0 でなくなり、Freshness が実行のたびに変わってテストとデモの決定性が壊れる。

- **失敗はキャッシュしない。** 1回の失敗を TTL のあいだ引きずらない
- **キャッシュ経過時間を `SourceFetch.cache_age_seconds` へ載せる。** `docs/scoring.md` の Freshness は `related_queries` と `search` の古さをこれで測る。0 を返し続けると6時間前の結果でも「今取得した」ものとして扱われる
- 保存先はプロセス内メモリ。**Lambda の実行環境をまたぐ共有キャッシュ(DynamoDB など)は MVP の範囲外**。キャッシュが効かなくても結果は正しく、外部呼び出しが増えるだけという設計にしてある
- LLM の分類キャッシュは別（`adapters/llm/cache.py`、入力ハッシュで引く）

## Reliability

- SerpApi timeout 8秒、リトライ最大2回、Exponential backoff
- **リトライ対象は 429 / 500 / 503 とネットワークエラーのみ。** その他の 4xx はリトライしない
- **LLM(Anthropic API)も timeout を明示する。** `ANTHROPIC_TIMEOUT_SECONDS`(既定 30秒)と `ANTHROPIC_MAX_RETRIES`(既定 2)で制御し、SDK の既定値(read 600秒)に委ねない。委ねると1呼び出しが最悪30分近くブロックし、Lambda Worker のタイムアウト経由で SQS の `maxReceiveCount` を消費して DLQ へ落ちる
- **分類が全滅した場合(1件も分類できなかった場合)は、そのソースを `MISSING` として扱う。** 既定値で全件を埋めた結果をスコアへ流すと `solution_gap = 100`(最大値)が観測値として入り、Confidence にも反映されない
- 1つのソースが失敗しても他のソースの結果でスコアを算出し、Confidence へ反映する
- `trends` の失敗のみ Need Gap Score を出さない扱いとする
- **レスポンス本文にサイズ上限を設ける。** 上限が無いと、障害時の巨大な本文でメモリを使い切り「1ソースの失敗」ではなくプロセス強制終了になる

## Observability

CloudWatch Structured Logging(JSON1行)。全ログに次を含める。

`scan_id` / `country` / `topic` / `source`

**API key をログへ書かない。** ログ出力前にマスクする。

これは**自分が書くログだけでなく、プロセスが出すログ全体**に対する要件である。SerpApi は認証をクエリパラメータ(`api_key=...`)でしか受け付けないため URL そのものが秘密情報であり、httpx はリクエストごとに完全な URL を INFO で出力する。外部ライブラリのロガーへマスク用のフィルタを装着すること(`adapters/serpapi/logging_guard.py`)。

**ログのコンテキスト伝播は `contextvars` を使う**(`application/logging_context.py`)。アダプタ層は `scan_id` を知りえないため、関数シグネチャを変えずに伝播させる。`log_context(...)` で文脈を積み、`ScanContextFilter` がレコードへ載せる。

**スレッドへは自動では伝わらない。** `ThreadPoolExecutor` のワーカーは親の `Context` を継承しないため、Phase 8 で並列化する際は `submit_with_context` を使うこと。使わないと全ログの4フィールドが `null` になる。`asyncio` のタスクは自動で引き継ぐ。

**API キーのマスクは root ハンドラへ装着する。** ロガー単位のフィルタ(`httpx` / `httpcore`)だけでは、自前のロガーや将来追加されるライブラリが素通りする。`configure_logging` が `ApiKeyMaskingFilter` を root ハンドラへ付け、`extra=` の値と例外トレースバックもマスクする。

Metrics(**候補。MVP では未実装**): `scan_duration_ms` / `serpapi_latency_ms` / `serpapi_calls` / `serpapi_errors` / `cache_hits` / `cache_misses` / `llm_latency` / `country_completed` / `scan_completed`

現状は構造化ログのみで、`put_metric` も EMF もメトリクスフィルタも実装していない。したがって Performance SLO は**測定できていない**。

## Security

- SerpApi API key を Git に入れない。Secrets Manager または環境変数
- S3 public access 禁止(Block Public Access 全4項目を有効)
- CORS を Frontend origin へ限定
- IAM は Least Privilege(Lambda ごとに必要最小の権限)
- 個人情報を収集しない
