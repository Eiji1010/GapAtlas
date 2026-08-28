# 要件定義

出典は `gapatlas_claude_implementation_prompt.md`(ハッカソン向け実装依頼)。この文書が実装の正本です。

## プロダクト

**GapAtlas** — Discover where needs are rising faster than solutions.

「検索需要や困りごとが増加している一方で、検索上で見える解決策が追いついていない地域」をライブWebデータから発見する。

### 主張の範囲

- 発見するのは **Search-visible unmet-need signal** である
- 社会問題の客観的な深刻度を判定するものではない
- 出力は「次に詳しく調査すべき地域」の優先順位である

詳細は[方法論と限界](methodology.md)を参照。

## ターゲット

- Primary User: 企業の新規事業担当 / 事業開発担当 / Innovation担当
- Jobs To Be Done: 「どの国・地域・課題を次に詳しく調査するべきか判断したい」

## スコープ

| 項目 | MVP |
|---|---|
| Topic | Elder Care のみ |
| Countries | JP / US / GB / DE / IN |
| Childcare / Skills 等 | 実装しない(将来追加可能な構造だけ維持) |

## 使用する SerpApi

Core Scan で使用する4種類。

1. Google Trends TIMESERIES
2. Google Trends RELATED_QUERIES
3. Google Search
4. Google News

Google Maps は **Core Score に使用しない**。5か国ランキング完成後、**Top 2 countries** についてのみ取得し Local Evidence として表示する。Maps件数を実際の供給量として扱ってはいけない。

## Query Profile

国ごとに `config/query_profiles/<topic>/<COUNTRY>.yaml` を持つ。

```yaml
topic_id: elder_care
country: JP
language: ja
version: elder-care-jp-v1

demand_queries:
  - 介護
  - 介護施設
  - 在宅介護

related_query_seed:
  - 介護

solution_query:
  - 介護 サービス

news_query:
  - 介護 人手不足
```

再現可能性のため、結果に次の4バージョンを必ず含める。

- `query_profile_version`
- `score_version`
- `classifier_version`
- `prompt_version`

## スコア

定義は[スコアリング仕様](scoring.md)を正本とする。

- **Need Gap Signal Score** (0〜100): Demand 40% / Pain 25% / Solution Coverage Gap 25% / News Urgency 10%
- **Evidence Confidence** (0〜100): Need Gap Score とは完全に別のスコアとして扱う

LLM にスコアを計算させてはいけない。数値計算はすべて Python で deterministic に行う。

## AIの役割

AIは次の2つだけに使用する。

### A. Classification

- Related Queries の分類(ACCESS / SHORTAGE / WAIT_TIME / COST / QUALITY / WORKFORCE / NEUTRAL)
- Search Results の分類(DIRECT_PROVIDER / MARKETPLACE / GOVERNMENT / INFORMATION / NEWS / OTHER)
- News Results の関連性分類

いずれも Structured JSON で返す。

### B. Opportunity Brief

最終結果を基に次の5節を生成する。

- WHY NOW
- WHAT PEOPLE ARE STRUGGLING WITH
- VISIBLE SOLUTIONS
- WHAT THIS DOES NOT PROVE
- NEXT VALIDATION

制約:

- Evidence に存在しない事実を断定しない
- Evidence には ID(`E1` `E2` ...)を付与し、AIは `Demand accelerated [E1]` のように引用する
- **URLをLLMに生成させない**

## Frontend

React + TypeScript。Hosting は Cloudflare Pages。画面は3つだけ。

### Screen 1: Discover

Elder Care / Countries(JP・US・GB・DE・IN) / Analyze Live Signals ボタン / 進捗表示 / 国別ランキング(Need Gap・Confidence)

### Screen 2: Country Evidence

Country / Need Gap Signal Score / Evidence Confidence / Demand / Pain / Solution Gap / News Urgency / Trends / Related Queries / Search / News / Maps(Top2のみ)

### Screen 3: Opportunity Brief

WHY NOW / WHAT PEOPLE ARE STRUGGLING WITH / VISIBLE SOLUTIONS / WHAT THIS DOES NOT PROVE / NEXT VALIDATION

## 更新方式

WebSocket / SSE は使わない。**2秒程度の Polling**。

## API

[API仕様](api.md)を正本とする。MVPは4本。

```http
GET  /api/v1/topics
POST /api/v1/scans
GET  /api/v1/scans/{scan_id}
GET  /api/v1/scans/{scan_id}/countries/{country}
```

`POST /scans` は即座に `scan_id` を返す。重い SerpApi 処理を HTTP Request 内で実行してはいけない。

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

Cache Hit の場合は SerpApi を再度呼ばない。

## Fixture Mode

最優先機能。`SERPAPI_MODE=fixture` / `SERPAPI_MODE=live` で切り替える。fixture モードでは `backend/tests/fixtures/` の保存済みレスポンスを使用する。開発・Unit Test では原則 fixture。

## Reliability

- SerpApi timeout: 8秒程度
- Retry: 最大2回程度、Exponential backoff
- SQS `maxReceiveCount = 3`、失敗後は DLQ
- 1 Source が失敗してもシステム全体を 500 エラーにしない
- 部分成功を許容し、Confidence へ反映する

## Performance SLO

| 操作 | 目標 |
|---|---:|
| Initial Page | < 1.5 sec |
| POST /scans | p95 < 800ms |
| Cache Hit | p95 < 1.5 sec |
| First Country Result | < 5 sec |
| 5 Country Ranking | p50 < 15 sec / p95 < 30 sec |
| AI Insight | Ranking 完了後 +5 sec 以内 |

外部API依存のため時間を保証せず、progressive UI を優先する。

## Observability

CloudWatch Structured Logging。ログに最低限含める: `scan_id` / `country` / `topic` / `source`。

Metrics候補: `scan_duration_ms` / `serpapi_latency_ms` / `serpapi_calls` / `serpapi_errors` / `cache_hits` / `cache_misses` / `llm_latency` / `country_completed` / `scan_completed`

## Security

- SerpApi API key を Git に入れない
- Secret は Secrets Manager または環境変数
- S3 public access 禁止
- CORS を Frontend origin へ限定
- ログへ API key を書かない
- IAM は Least Privilege
- 個人情報を収集しない

## 作らないもの

Login / User Account / Payment / Multi Tenant / ECS / EKS / EC2 / RDS / Redis / WebSocket / Step Functions / Kafka / Elasticsearch / OpenSearch / 200 countries / Multiple Topics / AI Forecast / TAM Calculation

## Definition of Done

- [ ] Elder Care を分析可能
- [ ] 5か国分析可能
- [ ] Core SerpApi API 4種類を使用
- [ ] Raw JSON を S3 へ保存
- [ ] Need Gap Signal Score を計算
- [ ] Evidence Confidence を計算
- [ ] 5か国ランキング表示
- [ ] Country Detail 表示
- [ ] Evidence 表示
- [ ] Top2 に Maps Evidence
- [ ] Top1 に AI Opportunity Brief
- [ ] AI が Evidence ID を引用
- [ ] Insufficient Evidence 対応
- [ ] Cache 動作
- [ ] fixture / live 切替
- [ ] Athena で過去 Score 取得
- [ ] 部分的API障害でシステム全体が落ちない
- [ ] Score Unit Test
- [ ] E2E demo が動く

これ以上の機能を MVP 完成前に追加しない。

## 実装フェーズ

| Phase | 内容 |
|---:|---|
| 1 | Project bootstrap |
| 2 | Domain Models / Pydantic Models |
| 3 | SerpApi Adapter + fixture mode |
| 4 | Need Gap Scoring Engine |
| 5 | Confidence Engine |
| 6 | Country Scan Service |
| 7 | DynamoDB / S3 adapters |
| 8 | SQS async flow |
| 9 | API Gateway / Lambda API |
| 10 | React MVP |
| 11 | AI Classification / Opportunity Brief |
| 12 | Glue / Athena |
| 13 | Terraform |
| 14 | E2E / performance / reliability |
| 15 | README / demo preparation |

Frontend や Terraform を先に作らない。最優先は次の End-to-End を成立させること。

```text
SerpApi Fixture → Normalize → Scoring → Confidence → JSON Output
```

## 依頼書からの逸脱

| 項目 | 依頼書 | 本実装 | 理由 |
|---|---|---|---|
| LLMプロバイダ | Bedrock / LLM | Anthropic API 直接 | [ADR 0002](decisions/0002-llm-provider.md) |
| Terraform | IaC は Terraform | コード作成と `validate`/`plan` まで。`apply` はしない | AWSアカウントへの課金と汚染を避けるため |
| SerpApi live | fixture/live 切替 | live は実装するが未検証(APIキー未取得) | [ADR 0003](decisions/0003-fixture-first.md) |
