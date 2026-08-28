# QueryProfile 仕様

`config/query_profiles/<topic_id>/<COUNTRY>.yaml`

国ごとの検索クエリ定義です。再現可能性のため、内容を変更したら `version` を上げます。

## スキーマ

| フィールド | 型 | 必須 | 制約 |
|---|---|---|---|
| `topic_id` | string | ○ | MVP は `elder_care` のみ |
| `country` | string | ○ | ISO 3166-1 alpha-2。ファイル名と一致すること |
| `language` | string | ○ | ISO 639-1 |
| `version` | string | ○ | `query_profile_version` として結果に記録される |
| `review_status` | enum | ○ | `LLM_GENERATED` または `MANUAL_REVIEWED` |
| `serpapi.geo` | string | ○ | Google Trends の地域指定 |
| `serpapi.gl` | string | ○ | Google Search / News の国指定 |
| `serpapi.hl` | string | ○ | 言語指定 |
| `serpapi.google_domain` | string | ○ | Google Search / Maps 用 |
| `demand_queries` | list[string] | ○ | **1〜5件**。Trends TIMESERIES は最大5語の比較に対応 |
| `related_query_seed` | list[string] | ○ | **ちょうど1件**。RELATED_QUERIES は1リクエスト1クエリのみ |
| `solution_query` | list[string] | ○ | **ちょうど1件** |
| `news_query` | list[string] | ○ | **ちょうど1件** |
| `maps_query` | list[string] | ○ | **ちょうど1件** |
| `maps_location` | string | ○ | SerpApi Maps の `ll` 形式(`@緯度,経度,ズームz`) |

件数制約はローダーで検証し、違反する場合は起動時に失敗させます。曖昧な集約規則を持ち込まないための制約です。

`geo` と `gl` が異なる国があります(例: 英国は `geo: GB` / `gl: uk`)。詳細は[SerpApi レスポンススキーマ](serpapi-schema.md)を参照。

## Maps 用フィールド

Google Maps は **Core Score に使いません**([要件定義](requirements.md))。5か国のランキング確定後、**Top 2 countries** についてのみ取得し Local Evidence として表示するためのものです。**Maps の件数を実際の供給量として扱ってはいけません。**

| フィールド | 内容 |
|---|---|
| `maps_query` | Maps 検索に渡すクエリ。「その地域で実際に申し込めるサービス」を探す語にする |
| `maps_location` | 検索の中心座標。SerpApi の `ll` パラメータ形式 `@<緯度>,<経度>,<ズーム>z` |

`maps_location` はモデル側で形式(`@緯度,経度,ズームz`)と座標の範囲(緯度 ±90 / 経度 ±180)を検証します。形式違反は起動時に失敗させます。

**現在の5か国は、各国の代表都市1点(東京 / New York / London / Berlin / Delhi)を `12z` で指定しています。** 全国を代表する値ではなく、あくまで「その国で最も検索結果が得られる1地点」です。国全体の供給量を測るものではないことを UI にも明記します。

## `review_status` の意味

[スコアリング仕様](scoring.md)の Localization quality に直結します。

| 値 | Localization quality |
|---|---:|
| `MANUAL_REVIEWED` | 100 |
| `LLM_GENERATED` | 70 |

**現在の5か国はすべて `LLM_GENERATED` です。** その言語圏の利用者が実際に使う検索語かどうかを人が確認していないためです。人によるレビューを行った国は `MANUAL_REVIEWED` へ変更してください。

## クエリ設計の指針

| フィールド | 何を狙うか |
|---|---|
| `demand_queries` | その国で最も一般的な「課題そのもの」の検索語。事業者名やブランド名を含めない |
| `related_query_seed` | rising queries を広く拾えるよう、最も一般的な1語 |
| `solution_query` | 「解決策を探している人」の検索語。この検索結果の上位に何が出るかで Solution Coverage を測る |
| `news_query` | その国で報道されている課題の言い回し |

翻訳ではなく、その言語圏で実際に使われる言い回しを使います。直訳は Localization quality を下げる原因になります。
