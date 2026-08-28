# SerpApi レスポンススキーマ

SerpApi 公式ドキュメントを調査した結果です。**fixture と正規化処理はこの文書に従って実装します。**

APIキーが未取得のため live での実検証は行っていません。**確認済み** は公式ドキュメントで直接確認したもの、**未確認** はドキュメントで確認できなかったものです。未確認の項目に依存する実装を書いてはいけません。

出典:
- https://serpapi.com/google-trends-api
- https://serpapi.com/google-trends-related-queries
- https://serpapi.com/search-api
- https://serpapi.com/organic-results
- https://serpapi.com/google-news-api
- https://serpapi.com/google-maps-api
- https://serpapi.com/api-status-and-error-codes

## 実装に直結する重要事項

1. **RELATED_QUERIES は1リクエストにつき1クエリのみ**。TIMESERIES と異なりカンマ区切りの複数指定ができない(確認済み)
2. **Google News に `snippet` は存在しない**(確認済み)。関連性分類は `title` と `source.name` のみで行う
3. **Google News の `date` は絶対表記**(`"01/02/2026, 10:30 PM, +0700 +07"`)。相対表記(`"1 hour ago"`)ではない。recency 計算には併記される **`iso_date`(ISO8601 UTC)** を使う
4. **RELATED_QUERIES の `rising[].value` は `"+4,500%"` / `"Breakout"` を取りうる**。加えて公式未記載の `"Record"` が観測されたという報告がある(非公式)。**数値化は `extracted_value` を主とし、`value` のパースに失敗しても落ちない防御的実装にする**
5. Google Trends には `gl` / `google_domain` が存在しない。地域指定は **`geo` のみ**(確認済み)
6. Google Search / News / Maps は `gl` / `hl` の2文字コードで国・言語を指定する(確認済み)

## 1. Google Trends TIMESERIES

`engine=google_trends`, `data_type=TIMESERIES`

### リクエスト

| パラメータ | 内容 | 確認 |
|---|---|---|
| `engine` | `google_trends` | 確認済み |
| `q` | 検索語。**カンマ区切りで最大5語まで比較可能** | 確認済み |
| `geo` | 地域。既定は Worldwide。国コードを指定 | 確認済み |
| `hl` | 2文字言語コード | 確認済み |
| `date` | 期間 | 確認済み |
| `api_key` | APIキー | 確認済み |

`date` に指定可能な値(確認済み): `now 1-H` / `now 4-H` / `now 1-d` / `now 7-d` / `today 1-m` / `today 3-m` / `today 12-m` / `today 5-y` / `all`、カスタム範囲 `yyyy-mm-dd yyyy-mm-dd`、時間単位範囲 `yyyy-mm-ddThh yyyy-mm-ddThh`(1週間以内)。

`data_type` に指定可能な値(確認済み): `TIMESERIES`(既定) / `GEO_MAP` / `GEO_MAP_0` / `RELATED_TOPICS` / `RELATED_QUERIES`

**GapAtlas では `date=today 12-m` を使い、週次データ点を取得する。**

### レスポンス(確認済み)

```json
{
  "interest_over_time": {
    "timeline_data": [
      {
        "date": "Dec 29, 2024 – Jan 4, 2025",
        "timestamp": "1735430400",
        "values": [
          { "query": "quantum computing", "query_index": 0, "value": "8", "extracted_value": 8 }
        ]
      }
    ]
  }
}
```

- `date`: 文字列(人間可読の期間表記)
- `timestamp`: **文字列**の Unix タイムスタンプ
- `value`: **文字列**
- `extracted_value`: **数値**。正規化ではこちらを使う
- `query_index`: 数値。複数キーワード比較時にどのクエリかを示す

**未確認**: 複数キーワード時の完全なサンプル JSON は公式ページに掲載がない。`values` 配列が各クエリ分の要素を持つと推定されるが、live で再検証が必要。

## 2. Google Trends RELATED_QUERIES

`engine=google_trends`, `data_type=RELATED_QUERIES`

**制約(確認済み)**: 「Related queries chart accepts only single query per search」。複数キーワード不可。

### レスポンス(確認済み)

```json
{
  "related_queries": {
    "rising": [
      { "query": "...", "value": "+4,500%", "extracted_value": 4500, "link": "...", "serpapi_link": "..." }
    ],
    "top": [
      { "query": "...", "value": "100", "extracted_value": 100, "link": "...", "serpapi_link": "..." }
    ]
  }
}
```

`rising[].value` の取りうる値(確認済み):

- パーセント文字列 `"+4,500%"`(千位区切りのカンマあり)
- **`"Breakout"`**(急上昇率が極端に高い場合)
- 非公式報告として `"Record"` の観測例あり(参考: serpapi/public-roadmap#3025)

`extracted_value` にはいずれの場合も数値が入る(確認済み)。

**実装方針**: `extracted_value` が数値ならそれを採用。無い/数値でない場合は `value` から `+` `,` `%` を除去して数値化を試み、失敗したら **`Breakout` 相当の上限値**として扱う(上限値は[スコアリング仕様](scoring.md)に定義)。未知文字列でも例外を投げない。

## 3. Google Search

`engine=google`

### リクエスト(確認済み)

必須: `q`, `api_key`。国 `gl`(2文字), 言語 `hl`(2文字), ドメイン `google_domain`(既定 `google.com`)。`location` も存在するが値形式は**未確認**のため使用しない。

### `organic_results[]` のキー(確認済み)

| キー | 有無 |
|---|---|
| `position` (Integer) | 常に存在 |
| `title` (String) | 常に存在 |
| `link` (String) | 常に存在 |
| `redirect_link`, `displayed_link`, `snippet`, `snippet_highlighted_words`, `date`, `source` | 任意 |
| `sitelinks`, `rich_snippet`, `about_this_result`, `cached_page_link`, `related_pages_link`, `thumbnail`, `favicon` | 任意 |

**fixture では「フル項目版」と「最小項目版(`position`/`title`/`link` のみ)」を混在させ、任意キー欠落時の耐性を検証する。**

## 4. Google News

`engine=google_news`

### リクエスト(確認済み)

必須: `engine`, `api_key`。クエリ `q`、地域 `gl` / `hl`(2文字コード)。`google_domain` はパラメータ表に現れない(**未確認/おそらく非対応**)。

### `news_results[]` のキー(確認済み)

`position`, `title`, `source`(ネスト: `name`, `icon`, `authors`), `link`, `thumbnail`, `thumbnail_small`, `date`, `iso_date`

- **`snippet` は存在しない**(確認済み)
- `date`: `"01/02/2026, 10:30 PM, +0700 +07"` 形式
- `iso_date`: `"2026-01-02T15:30:13Z"` 形式。**recency 計算にはこちらを使う**

トップレベルには `news_results` の他に `menu_links` / `related_topics` / `related_publications` が存在(確認済み)。

**未確認**: `stories` によるグループ化ネストが `engine=google_news` で発生するかは一次資料で確認できなかった。正規化処理は `stories` が存在しない形を基本とし、存在した場合も落ちない実装にする。

## 5. Google Maps

`engine=google_maps`

### リクエスト(確認済み)

必須: `engine`, `type`(`search` または `place`), `api_key`。位置は `ll`(`@緯度,経度,ズーム` 例 `@40.7455096,-74.0083012,14z`) / `location`(文字列) / `lat`+`lon`。`gl` / `hl` / `google_domain` は Search API と同一形式。

### `local_results[]` のキー(確認済み)

`position`, `title`, `place_id`, `data_id`, `data_cid`, `reviews_link`, `photos_link`, `gps_coordinates`(`latitude`/`longitude`), `provider_id`, `rating`(数値), `reviews`(数値), `price`, `extracted_price`(数値), `type`, `types`(配列), `type_id`, `type_ids`(配列), `address`, `country`, `open_state`, `hours`, `operating_hours`, `phone`, `extensions`, `service_options`, `order_online`, `thumbnail`, `serpapi_thumbnail`

**Maps は Core Score に使用しない。Top 2 countries の Local Evidence 表示のみ。**

## 6. 共通メタとエラー

### `search_metadata`(確認済み、Google Search 由来)

`id`, `status`(`Processing` → `Success`/`Error`), `json_endpoint`, `created_at`, `processed_at`, `google_url`, `raw_html_file`, `total_time_taken`

### `search_parameters`(確認済み)

`engine`, `q`, `location_requested`, `location_used`, `google_domain`, `hl`, `gl`, `device`

### `search_information`(確認済み)

`organic_results_state`, `query_displayed`, `total_results`, `time_taken_displayed`, `results_for`。Maps では `local_results_state`, `query_displayed`。

### エラー(確認済み)

```json
{ "error": "String - A human-readable message about the error." }
```

| HTTP | 意味 |
|---:|---|
| 200 | 正常 |
| 400 | パラメータ不備 |
| 401 | APIキー不正 |
| 403 | 権限不足 |
| 404 | リソースなし |
| 410 | アーカイブ期限切れ |
| 429 | レート上限超過 または 検索クレジット枯渇 |
| 500 / 503 | SerpApi 側障害 |

**リトライ対象は 429 / 500 / 503 とネットワークエラーのみ。4xx(429を除く)はリトライしない。**

## 7. live 移行時に再検証すべき項目

APIキー取得後、次を実データで確認し本文書を更新する。

- [ ] TIMESERIES に複数キーワードを渡したときの `values` 配列の構造
- [ ] RELATED_QUERIES の `rising[].value` に `"Record"` が実際に出るか
- [ ] Google News の `stories` ネストの発生条件とキー構造
- [ ] Maps の `search_metadata` / `search_parameters` に Maps 固有キーがあるか
- [ ] 各エンジンの実レスポンスと fixture の差分
