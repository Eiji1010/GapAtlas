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
│   ├── serpapi/   # SerpApi クライアント + fixture 実装
│   ├── llm/       # LLM クライアント + stub 実装
│   ├── dynamodb/
│   └── s3/
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
  "country": "JP",
  "status": "completed",
  "need_gap_score": 86,
  "confidence": 92,
  "demand": 91,
  "pain": 84,
  "solution_gap": 78,
  "news_urgency": 83
}
```

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
- `normalized/` `curated/` は可能なら Parquet を使う

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

## Reliability

- SerpApi timeout 8秒、リトライ最大2回、Exponential backoff
- **リトライ対象は 429 / 500 / 503 とネットワークエラーのみ。** その他の 4xx はリトライしない
- 1つのソースが失敗しても他のソースの結果でスコアを算出し、Confidence へ反映する
- `trends` の失敗のみ Need Gap Score を出さない扱いとする

## Observability

CloudWatch Structured Logging(JSON1行)。全ログに次を含める。

`scan_id` / `country` / `topic` / `source`

**API key をログへ書かない。** ログ出力前にマスクする。

Metrics: `scan_duration_ms` / `serpapi_latency_ms` / `serpapi_calls` / `serpapi_errors` / `cache_hits` / `cache_misses` / `llm_latency` / `country_completed` / `scan_completed`

## Security

- SerpApi API key を Git に入れない。Secrets Manager または環境変数
- S3 public access 禁止(Block Public Access 全4項目を有効)
- CORS を Frontend origin へ限定
- IAM は Least Privilege(Lambda ごとに必要最小の権限)
- 個人情報を収集しない
