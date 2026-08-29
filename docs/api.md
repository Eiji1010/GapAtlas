# API仕様

Base path: `/api/v1`

MVP のエンドポイントは4本のみ。認証は行わない(MVPではLogin/Accountを作らない)。

## 共通

- レスポンスは JSON
- CORS は Frontend origin へ限定する(`CORS_ALLOWED_ORIGINS`)
- エラーは HTTP ステータスと `{"error": {"code": "...", "message": "..."}}` で返す
- **1つの外部ソースが失敗してもシステム全体を 500 にしない。** 部分成功として返し Confidence へ反映する

## GET /api/v1/topics

利用可能な Topic と Country の一覧。

```json
{
  "topics": [
    {
      "topic_id": "elder_care",
      "label": "Elder Care",
      "countries": [
        { "country": "JP", "label": "Japan" },
        { "country": "US", "label": "United States" },
        { "country": "GB", "label": "United Kingdom" },
        { "country": "DE", "label": "Germany" },
        { "country": "IN", "label": "India" }
      ]
    }
  ]
}
```

## POST /api/v1/scans

スキャンを開始する。**即座に返す。重い SerpApi 処理を HTTP リクエスト内で実行しない。**

Request:

```json
{
  "topic_id": "elder_care",
  "countries": ["JP", "US", "GB", "DE", "IN"]
}
```

Response `202`:

```json
{
  "scan_id": "scan_abc123",
  "status": "processing"
}
```

処理: SCAN を作成 → 国ごとの Job を SQS へ投入 → Lambda Worker が処理。

SLO: p95 < 800ms。

## GET /api/v1/scans/{scan_id}

進捗とランキング。Frontend は**2秒間隔の Polling** でこれを呼ぶ(WebSocket / SSE は使わない)。

```json
{
  "scan_id": "scan_abc123",
  "topic_id": "elder_care",
  "status": "processing",
  "progress": {
    "total": 5,
    "completed": 2
  },
  "completed_countries": ["JP", "US"],
  "ranking": [
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
  ],
  "opportunity_brief": null,
  "versions": {
    "score_version": "gapatlas-score-v1",
    "classifier_version": "gapatlas-classifier-v1",
    "prompt_version": "gapatlas-prompt-v1"
  }
}
```

- `status`: `processing` / `completed` / `partially_failed`
  - **`INSUFFICIENT_EVIDENCE` はエラーではない**ため、全国がそうなっても `completed` を返す。`partially_failed` は `FAILED` の国がある場合のみ
  - 全国が `INSUFFICIENT_EVIDENCE` になるのは外形障害の可能性が高い。監視はログの `rankable_countries` / `insufficient_countries` を見る
- `ranking` は `need_gap_score` の降順。`need_gap_score` が `null` の国(`INSUFFICIENT_EVIDENCE`)は末尾へ回す。`need_gap_score = 0` は有効なスコアであり `null` より上に来る。末尾側は `INSUFFICIENT_EVIDENCE` → `FAILED` の順
- `opportunity_brief` は全国完了後、Top1 の国について生成されたら入る。**ランキング可能(`COMPLETED`)な国が1つも無ければ `null`**
- **処理中も部分的なランキングを返す。** Worker は1国終わるたびに概要を `status = processing` で上書きするため、2秒 Polling で `ranking` と `progress` が進む
- `progress` は**保存済みの国から算出**する。`completed` は「終了済みかつ `FAILED` でない国」の数で、`insufficient_evidence` は完了として数える(エラーではないため)。**`FAILED` の国は数えない**ので、1か国失敗したスキャンの進捗は 4/5 で止まる
- スキャン単位の `versions.query_profile_version` は、**スキャンに使った国別プロファイル版を昇順で連結した文字列**(例 `elder-care-de-v2,elder-care-jp-v2`)。国別の正確な値は `GET /scans/{scan_id}/countries/{country}` の `versions` を見ること
- `versions.classifier_version` / `prompt_version` は**実際に使った LLM アダプタ**の版。stub モードでは `-stub` が付く(結果が実 LLM と変わるため区別する)

## GET /api/v1/scans/{scan_id}/countries/{country}

国別の詳細と Evidence。

```json
{
  "scan_id": "scan_abc123",
  "topic_id": "elder_care",
  "country": "JP",
  "status": "completed",
  "need_gap_score": 86,
  "confidence": 92,
  "components": {
    "demand": 91,
    "pain": 84,
    "solution_gap": 78,
    "news_urgency": 83
  },
  "confidence_breakdown": {
    "data_completeness": 100,
    "sample_sufficiency": 95,
    "localization_quality": 100,
    "source_agreement": 88,
    "freshness": 92
  },
  "source_status": {
    "trends": "ok",
    "related_queries": "ok",
    "search": "ok",
    "news": "ok",
    "maps": "not_requested"
  },
  "evidence": [
    {
      "id": "E1",
      "source": "trends",
      "summary": "直近4週の平均が前8週比で上昇",
      "url": null
    }
  ],
  "trends": { "series": [] },
  "related_queries": [],
  "search_results": [],
  "news_results": [],
  "maps_results": null,
  "versions": {
    "query_profile_version": "elder-care-jp-v2",
    "score_version": "gapatlas-score-v1",
    "classifier_version": "gapatlas-classifier-v1",
    "prompt_version": "gapatlas-prompt-v1"
  }
}
```

- `maps_results` は Top 2 countries のみ非 `null`
- `evidence[].url` は **SerpApi のレスポンスに含まれていた URL のみ**。LLM に生成させない
- `status = insufficient_evidence` の場合、`need_gap_score` は `null` だが `confidence` と `confidence_breakdown` は返す

`trends` / `related_queries` / `search_results` / `news_results` は **分類結果を添えて**返します。UI が「この検索結果は `DIRECT_PROVIDER` と分類された」を示せるようにするためです。形は次のとおり。

```json
{
  "related_queries": [
    { "item": { "query": "...", "growth_percent": 4500.0, "is_breakout": false, "link": "..." },
      "classification": { "classification": "SHORTAGE", "confidence": 0.9 } }
  ]
}
```

- `maps_results` の `null` は「**取得していない**」(Top2 以外)、`[]` は「取得したが 0 件」。意味が違うので UI で区別すること
- `computed_at` は `CountryResult` に存在し、レスポンスにも含めます(上の例には記載がありませんが実装は返します)
- fixture 5か国での `CountryResult` の JSON は約 22KB(Maps 込み)。DynamoDB の項目上限 400KB に対して十分な余裕があり、テストで 200KB 未満を固定しています

## エラー

| HTTP | code | 条件 |
|---:|---|---|
| 400 | `INVALID_REQUEST` | topic_id / country / リクエスト本文が不正 |
| 404 | `SCAN_NOT_FOUND` | scan_id が存在しない。**形式が不正な scan_id もここへ倒す**(400 は topic_id / country 専用) |
| 404 | `COUNTRY_NOT_FOUND` | そのスキャンに該当国がない |
| 404 | `ROUTE_NOT_FOUND` | 定義されていないパス |
| 405 | `METHOD_NOT_ALLOWED` | パスは存在するがメソッドが違う |
| 500 | `INTERNAL_ERROR` | 想定外の例外。**本文にトレースバックを出さない** |

エラー本文に利用者の入力を反射させない(`scan_id` やパスを本文へ含めない)。値は構造化ログにのみ残す。

外部APIの失敗は 5xx にしない。国単位の `status` と Confidence で表現する。
