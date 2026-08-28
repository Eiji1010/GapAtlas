# SerpApi fixture

`SERPAPI_MODE=fixture` で外部通信ゼロの開発・テストを行うための、保存済み SerpApi レスポンスです。

SerpApi の API キーが未取得のため、これらは **live レスポンスの写しではなく、[SerpApi レスポンススキーマ](../../../docs/serpapi-schema.md) に厳密に従って人工的に作成したデータ**です。同文書で「未確認」とされている構造は推測で足していません（[未確認項目の扱い](#未確認項目の扱い)を参照）。

## 基準日

**すべての日付は `2026-08-28T00:00:00Z` を基準に逆算しています。**

テストは `scan_time = 2026-08-28T00:00:00Z` を明示的に引数で渡して実行してください。現在時刻を使うとテストが非決定的になります（`domain/scoring` は現在時刻を取得しない、という規約もこの前提に立っています）。

| 対象 | 基準日との関係 |
|---|---|
| Trends `timeline_data` | 週次 52 点。最新週は `Aug 23, 2026 – Aug 29, 2026`（基準日を含む週）。`date=today 12-m` 相当 |
| Trends `timestamp` | 各週の日曜 00:00:00 UTC の Unix 秒（**文字列**）。隣接点の差は常に 604800 |
| News `iso_date` | 基準日から **過去 0.4〜28.9 日**に分散（`news_future_date.json` を除く） |
| News `date` | 各国のローカルタイムゾーン表記。`iso_date` と同一時刻を指す |
| `search_metadata.created_at` / `processed_at` | `2026-08-28 00:00:01 UTC` / `2026-08-28 00:00:03 UTC` 固定 |

## ディレクトリ構成と命名規約

```
backend/tests/fixtures/serpapi/
├── elder_care/<COUNTRY>/          # 正常系。<COUNTRY> は ISO 3166-1 alpha-2（JP/US/GB/DE/IN）
│   ├── trends_timeseries.json         engine=google_trends, data_type=TIMESERIES
│   ├── trends_related_queries.json    engine=google_trends, data_type=RELATED_QUERIES
│   ├── search.json                    engine=google
│   ├── news.json                      engine=google_news
│   └── maps.json                      engine=google_maps
└── edge_cases/                    # 境界値・異常系。`<source>_<条件>.json`
```

- 正常系のファイル名は **ソース名のみ**。トピックと国はディレクトリで表します（将来のトピック追加時に `elder_care/` の兄弟を増やすだけで済む形）
- 異常系のファイル名は `<ソース>_<検証したい条件>.json`
- JSON はインデント2スペース、UTF-8、非 ASCII 文字は**エスケープせず**そのまま保存、末尾に改行

## 設計方針

1. **形状の正本は `docs/serpapi-schema.md`。** 同文書に記載のないキーは足していません。逆に、記載のある必須キー（`organic_results[].position` / `title` / `link` など）は正常系で必ず存在します
2. **`search_parameters` は QueryProfile と一致させる。** `config/query_profiles/elder_care/<COUNTRY>.yaml` の `geo` / `gl` / `hl` / `google_domain` およびクエリ文字列と厳密に一致します。Trends には `gl` / `google_domain` を**入れていません**（Trends に存在しないため）。Google News には `google_domain` を入れていません（パラメータ表に現れないため）
3. **秘密情報を含めない。** API キーらしき文字列は一切含みません。`search_metadata.json_endpoint` などは `https://serpapi.com/searches/FIXTURE/...` というダミー値で、`id` はすべて `FIXTURE_` 接頭辞です
4. **実在の企業・団体・個人を登場させない。** 事業者名・媒体名はすべて架空（`架空〜` / `Example 〜（fictional）` / `Beispiel 〜（fiktiv）`）で、URL は予約ドメイン（`example.com` / `example.org` / `example.co.jp` / `example.go.jp` / `example.lg.jp` / `example.co.uk` / `example.de` / `example.co.in`）のみを使用しています。個人情報は含みません
5. **国ごとに異なるストーリーを持たせる。** ランダムな数字ではなく、スコアに意味のある差が出るよう設計しています（次節）
6. **各国の検索語はその言語で書く。** 日本語・ドイツ語は機械翻訳調にならないよう、その言語圏で実際に使われる言い回しに寄せています（ただし人によるレビューは未実施。QueryProfile 側も `review_status: LLM_GENERATED` です）

## 正常系ファイル一覧

| ファイル | 内容 |
|---|---|
| `elder_care/<CC>/trends_timeseries.json` | 週次 52 点 × 3 キーワード。`values[]` は `query_index` 0/1/2 の3要素。`value` は文字列、`extracted_value` は数値。国内での最大値がちょうど 100（Trends のリクエスト内正規化を再現） |
| `elder_care/<CC>/trends_related_queries.json` | `related_queries.rising` 12 件（Pain 分類対象）と `related_queries.top` 8 件 |
| `elder_care/<CC>/search.json` | `organic_results` 10 件（`TOP_N` と一致）。うち 2 件は `position`/`title`/`link` のみの最小項目版 |
| `elder_care/<CC>/news.json` | `news_results` 8〜9 件。**`snippet` は存在しない**。`source` は `{name, icon, authors}` のネスト |
| `elder_care/<CC>/maps.json` | `local_results` 6 件。Core Score には使わず Local Evidence 表示のみ |

### 各国の Trends の性質

`values` は3キーワードすべてを含みますが、下表の `前8週` / `直近4週` は **第1キーワード**（`demand_queries[0]`）の平均です。`demand(median)` は [scoring.md](../../../docs/scoring.md) の Demand Momentum を3キーワードに適用した中央値（LLM 不要のため fixture から一意に決まります）。

| 国 | 性質 | 前8週平均 | 直近4週平均 | demand(median) | 値が 0 の割合 |
|---|---|---:|---:|---:|---:|
| JP | 明確な上昇トレンド | 71.9 | 94.8 | 84.6 | 0% |
| DE | ノイズの多い上昇（週次の振れ幅が大きい） | 66.6 | 83.0 | 78.1 | 0% |
| IN | 検索ボリュームが小さく 0 を多く含む（系列が粗い） | 62.5 | 78.2 | 68.1 | 37.2% |
| US | 横ばい | 90.4 | 91.0 | 54.5 | 0% |
| GB | 緩やかな下降 | 69.0 | 66.2 | 43.4 | 0% |

- IN は「低ボリュームゆえに 0 が多く、少数の検索で系列が跳ねる」状態を意図しています。**0 の割合は 37.2% で Hard Rule 4（50% 以上）には達しません。** Hard Rule 4 の検証は `edge_cases/trends_timeseries_half_zero.json` で行ってください
- **国同士で Trends の水準（0〜100 の値そのもの）を比較してはいけません。** Trends はリクエスト内の相対値であり、fixture もその性質を再現しています。比較してよいのは変化率から算出した Demand Momentum だけです

### 各国 `rising` の Pain カテゴリ分布（意図）

分類は LLM が行うため、下表は「そう分類されることを意図した内訳」です。テストでは LLM をスタブしてこの分布を再現してください。

| 国 | 件数 | ACCESS | SHORTAGE | WAIT_TIME | COST | QUALITY | WORKFORCE | NEUTRAL |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| JP | 12 | 2 | 2 | 2 | 2 | 1 | 2 | 1 |
| US | 12 | 2 | 2 | 2 | 2 | 1 | 2 | 1 |
| GB | 12 | 1 | 3 | 3 | 2 | 1 | 1 | 1 |
| DE | 12 | 2 | 3 | 1 | 2 | 1 | 2 | 1 |
| IN | 12 | 4 | 1 | 1 | 2 | 1 | 1 | 2 |

各国 1 件だけ `"Breakout"`（`extracted_value: 5000`）を含めています。残りは `"+30%"` 〜 `"+450%"` のパーセント文字列です。

### 各国 `organic_results` の Solution カテゴリ分布（意図）

| 国 | 件数 | DIRECT_PROVIDER | MARKETPLACE | GOVERNMENT | INFORMATION | NEWS | OTHER | 想定される solution_gap |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| JP | 10 | 2 | 1 | 3 | 3 | 1 | 0 | 高め（公的ポータルと情報サイトが上位） |
| US | 10 | 4 | 3 | 1 | 2 | 0 | 0 | 低い（事業者とマーケットプレイスが上位） |
| GB | 10 | 2 | 1 | 4 | 2 | 1 | 0 | 高め（自治体・規制側のページが上位） |
| DE | 10 | 3 | 2 | 2 | 3 | 0 | 0 | 中程度 |
| IN | 10 | 2 | 2 | 0 | 4 | 1 | 1 | 最も高い（情報サイトとフォーラムが上位） |

`OTHER` の検証用に IN のみフォーラム記事を含めています。**これは「実際のサービス供給不足」ではなく「検索上で見える Solution Coverage の不足」を表すデータです。**

### `news_results` の関連性分類（意図）

| 国 | 件数 | DIRECTLY_RELEVANT | RELATED | UNRELATED |
|---|---:|---:|---:|---:|
| JP | 9 | 7 | 2 | 0 |
| US | 8 | 6 | 2 | 0 |
| GB | 8 | 7 | 1 | 0 |
| DE | 8 | 7 | 1 | 0 |
| IN | 8 | 5 | 3 | 0 |

## 境界値・異常系ファイル一覧

異常系は形状だけを問題にするため、`search_parameters` は **US の QueryProfile（`geo=US` / `gl=us` / `hl=en` / `google_domain=google.com`）で統一**しています。

| ファイル | データの性質 | 何を検証するか |
|---|---|---|
| `trends_timeseries_11_points.json` | 週次 11 点（`values` は3要素） | `WINDOW_WEEKS=12` 未満 → `demand = None` → `status = INSUFFICIENT_EVIDENCE` |
| `trends_timeseries_all_zero.json` | 週次 52 点、`extracted_value` がすべて 0 | ゼロ除算しないこと。`ratio_score = 50` / `slope_score = 50` → `demand = 50`。かつ Hard Rule 4 で `confidence <= 59` |
| `trends_timeseries_half_zero.json` | 週次 52 点のうち 32 点（61.5%）が 0。非ゼロ点は 38〜68 | Hard Rule 4（0 の点が 50% 以上）→ `confidence <= 59`。`demand` 自体は計算可能 |
| `trends_timeseries_empty.json` | `interest_over_time.timeline_data` が空配列 | `trends` を `MISSING` と判定 → Hard Rule 1 → `need_gap_score = None` |
| `trends_related_queries_empty.json` | `rising` が空配列（`top` は 8 件） | `pain = None`。成分の重み再正規化が走ること。`Σ(g_i)==0` の分岐 |
| `trends_related_queries_no_rising.json` | `related_queries` に `top` はあるが **`rising` キーが無い** | キー欠落で `KeyError` を出さず `pain = None` にすること |
| `trends_related_queries_breakout.json` | `rising` 8 件に `"Breakout"` / `"Record"` / `"+4,500%"` / `extracted_value` キー欠落 / `extracted_value: null` / 未知文字列 `"Rekord"` を混在 | `extracted_value` 優先 → `value` のパース → 失敗時 `BREAKOUT_GROWTH_PERCENT (5000)`。**いずれの値でも例外を投げないこと** |
| `search_empty.json` | `organic_results` が空配列（`organic_results_state: "Fully empty"`） | `solution_gap = None`。`search` を `MISSING` と判定 |
| `search_minimal_fields.json` | 10 件すべてが `position` / `title` / `link` のみ | 任意キー（`snippet` / `displayed_link` など）が無くても正規化できること |
| `search_missing_position.json` | 6 件中 3 件（配列添字 2, 4, 5）に `position` キーが無い | `position` 欠落時に **配列内の 1 始まりの添字**で `rank_weight` を代替すること |
| `news_empty.json` | `news_results` が空配列 | `news_urgency = None`。`news` を `MISSING` と判定 |
| `news_no_iso_date.json` | 4 件すべてに `iso_date` が無く `date` のみ | `date` のパースを試み、失敗したら記事を**除外**すること（推測で日付を補わない）。全件除外なら `news_urgency = None` |
| `news_future_date.json` | 5 件中 2 件が未来日付（基準日 +1.5 日 / +0.25 日） | `age_days = max(0, ...)` で 0 に丸められること。`recency_weight = 1.0` |
| `error_429.json` | `{"error": "..."}` のみ | レート上限／クレジット枯渇。**リトライ対象** |
| `error_401.json` | `{"error": "..."}` のみ | APIキー不正。**リトライしない**（4xx、429 を除く） |

エラー fixture は `docs/serpapi-schema.md` で確認済みの `{"error": "..."}` 形式のみで、`search_metadata` を含めていません（エラー時の `search_metadata` の有無が未確認のため）。HTTP ステータスコードはレスポンスボディに現れないので、テスト側で 429 / 401 を指定してください。

## 未確認項目の扱い

`docs/serpapi-schema.md`「7. live 移行時に再検証すべき項目」に対する fixture 側の判断です。**live 移行時はここを最初に確認してください。**

| 未確認項目 | fixture での扱い |
|---|---|
| TIMESERIES に複数キーワードを渡したときの `values` 配列の構造 | 同文書の推定どおり、`values` が各クエリ分の要素を持ち `query_index` が 0/1/2 になる形で作成。**構造が違った場合、5か国の `trends_timeseries.json` すべてを作り直す必要があります** |
| `rising[].value` に `"Record"` が実際に出るか | 正常系には入れず、`edge_cases/trends_related_queries_breakout.json` にのみ含めています |
| Google News の `stories` ネスト | **一切使っていません。** 全ファイルがフラットな `news_results` です |
| Maps の `search_metadata` / `search_parameters` の Maps 固有キー | 確認済みの共通キーのみ使用。`ll` / `type` はリクエストパラメータ表で確認済みのため `search_parameters` に含めています |
| 各エンジンの `search_metadata` のエンジン固有 URL キー | `google_url` は Google Search の `search.json` にのみ設定。`google_trends_url` / `google_news_url` / `google_maps_url` は**未確認のため作成していません** |
| Google News の `menu_links` / `related_topics` / `related_publications` | 存在は確認済みですが**中身の構造が未確認のため省略**しています。正規化処理はこれらに依存してはいけません |

その他、この fixture 作成時に判断が必要だったが仕様が定まっていない点:

- **Maps 用のクエリが QueryProfile に無い。** `maps.json` の `q` は暫定的に `solution_query` を使い、`ll` は各国の主要都市の座標を置いています。Maps クエリと位置指定の決め方は QueryProfile 側の仕様として決める必要があります
- `related_queries[].link` は Google Trends の explore URL 形式（`https://trends.google.com/trends/explore?...`）にしています。SerpApi が返す値の構造を再現するためで、キーやトークンは含みません

## 更新するとき

- **数値を変える前に、その変更が [scoring.md](../../../docs/scoring.md) のどの分岐に影響するかを確認してください。** 特に上表の「国ごとのストーリー」はデモのランキングに直結します
- 実 API キー取得後に live レスポンスを取得したら、`docs/serpapi-schema.md` を更新したうえでこの fixture との差分を洗い出し、両方を同じ PR で直してください
- fixture を足す場合も、基準日 `2026-08-28T00:00:00Z` と命名規約を守ってください
