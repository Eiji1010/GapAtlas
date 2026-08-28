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
- `ranking` は `need_gap_score` の降順。`need_gap_score` が `null` の国(`INSUFFICIENT_EVIDENCE`)は末尾へ回す
- `opportunity_brief` は全国完了後、Top1 の国について生成されたら入る

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
  "trends": { "timeline": [] },
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

## エラー

| HTTP | code | 条件 |
|---:|---|---|
| 400 | `INVALID_REQUEST` | topic_id / country が不正 |
| 404 | `SCAN_NOT_FOUND` | scan_id が存在しない |
| 404 | `COUNTRY_NOT_FOUND` | そのスキャンに該当国がない |
| 500 | `INTERNAL_ERROR` | 想定外の例外 |

外部APIの失敗は 5xx にしない。国単位の `status` と Confidence で表現する。
