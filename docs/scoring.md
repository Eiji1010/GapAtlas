# スコアリング仕様

`score_version = gapatlas-score-v1`

この文書はスコア計算の**正本**です。実装はこの定義から一意に決まります。第三者レビュアはこの文書だけを見て独立に再実装し、実装の出力と突き合わせられなければなりません。

## 絶対条件

- **LLM にスコアを計算させない。** すべての数値計算は Python で deterministic に行う
- LLM は**分類だけ**を行い、`{"classification": ..., "confidence": ...}` を返す。分類結果は入力として扱う
- `domain/scoring` は純粋関数のみ。ネットワーク、ファイルI/O、現在時刻の取得、乱数を持ち込まない。**現在時刻は引数で受け取る**

## 記法

- `clip(x, lo, hi)` = `max(lo, min(hi, x))`
- `mean(xs)` = 算術平均
- `median(xs)` = 中央値。要素数が偶数の場合は中央2つの算術平均
- `pstdev(xs)` = 母標準偏差(N で割る)
- `log1p(x)` = `ln(1 + x)`
- 公開スコアは **0〜100 の整数**。内部では float を保持し、最終出力時に **四捨五入(round half up)** する
- 計算不能な下位スコアは `None` とし、0 で代替しない

## 1. Need Gap Signal Score

```text
NeedGapScore =
    0.40 * demand
  + 0.25 * pain
  + 0.25 * solution_gap
  + 0.10 * news_urgency
```

各成分は 0〜100。

### 欠損時の扱い

- **`demand` が計算不能な場合、NeedGapScore を出さない**(`need_gap_score = None`, `status = INSUFFICIENT_EVIDENCE`)。Trends は必須ソースである
- `demand` 以外の成分が欠損した場合、**欠損成分を除いた重みで再正規化する**

```text
NeedGapScore = Σ(w_i * s_i) / Σ(w_i)   ※ i は s_i が None でない成分のみ
```

再正規化を行った場合、`score_components_used` に使用した成分名を記録する。欠損を 0 として扱ってはいけない(欠損と「値が0」は別である)。

- Core Source が2つ以上欠損した場合、成分の再正規化にかかわらず `status = INSUFFICIENT_EVIDENCE` とし `need_gap_score = None` とする

## 2. Demand Momentum (weight 40%)

入力: Google Trends TIMESERIES の週次系列。`timeline_data[].values[].extracted_value` を使用する。

### 定数

| 定数 | 値 |
|---|---:|
| `WINDOW_WEEKS` | 12 |
| `RECENT_WEEKS` | 4 |
| `PREVIOUS_WEEKS` | 8 |
| `SMOOTHING` | 5.0 |

### 単一クエリのスコア

系列を古い順に並べ、末尾 12 点を `y[0..11]` とする(`y[11]` が最新)。

**12点未満の場合、そのクエリのスコアは計算不能とする。**

#### ratio_score

```text
previous_mean = mean(y[0..7])     # 前8週
recent_mean   = mean(y[8..11])    # 直近4週
r = (recent_mean + SMOOTHING) / (previous_mean + SMOOTHING)
ratio_score = clip(50 + 100 * (r - 1), 0, 100)
```

`SMOOTHING` により分母は常に 5 以上となるためゼロ除算は発生しない。

#### slope_score

`y[0..11]` に対して最小二乗法で直線を当てはめる。`x[i] = i`(0〜11)。

```text
n = 12
x_mean = mean(x)      # = 5.5
y_mean = mean(y)
slope = Σ((x[i] - x_mean) * (y[i] - y_mean)) / Σ((x[i] - x_mean)^2)
```

分母は `x` が定数列でない限り常に正(`n=12` のとき 143.0)。

系列の水準に依存しないよう、窓全体での相対変化に変換する。

```text
relative_change = slope * (n - 1) / (y_mean + SMOOTHING)
slope_score = clip(50 + 100 * relative_change, 0, 100)
```

`ratio_score` と同じ感度になる(窓全体で +50% の変化 → 100、-50% → 0)。

#### 合成

```text
query_demand_score = 0.70 * ratio_score + 0.30 * slope_score
```

### 複数クエリの合成

```text
demand = median([query_demand_score for q in demand_queries if 計算可能])
```

計算可能なクエリが1つも無い場合、`demand = None`。

### 禁止事項

Google Trends の 0〜100 値は**その検索期間・地域内での相対値**である。国同士の絶対需要比較に使ってはいけない。Demand Momentum は**変化率のみ**から算出しており、水準を比較していない。

## 3. Pain Signal (weight 25%)

入力: Google Trends RELATED_QUERIES の `rising` 配列と、各クエリに対する LLM 分類結果。

### 成長率の取得と圧縮

各 rising query `i` について成長率(%)を求める。

1. `extracted_value` が数値ならそれを使う
2. 数値でない場合、`value` から `+` `,` `%` を除去して数値化を試みる
3. 数値化できない場合(`"Breakout"` / `"Record"` / 未知文字列)は `BREAKOUT_GROWTH_PERCENT` を使う

| 定数 | 値 |
|---|---:|
| `BREAKOUT_GROWTH_PERCENT` | 5000.0 |
| `GROWTH_CAP_PERCENT` | 5000.0 |

```text
growth_i = clip(raw_growth_i, 0, GROWTH_CAP_PERCENT)
g_i = log1p(growth_i)
```

負の成長率は 0 に切り上げる(rising リストに負値は本来現れない)。

### カテゴリ重み

| 分類 | 重み | 理由 |
|---|---:|---|
| `SHORTAGE` | 1.00 | 供給不足の直接的な訴え |
| `WAIT_TIME` | 1.00 | 供給不足が待機として顕在化 |
| `ACCESS` | 0.90 | 到達できないという困りごと |
| `WORKFORCE` | 0.80 | 担い手不足。供給側の制約 |
| `COST` | 0.70 | 経済的障壁。需給以外の要因も含む |
| `QUALITY` | 0.60 | 供給はあるが満たされていない |
| `NEUTRAL` | 0.00 | 困りごとを示さない |

この重み表は本プロジェクトの決定であり、`score_version` に紐づく。変更する場合は `score_version` を上げる。

### 計算

```text
w_i = category_weight(classification_i)
c_i = confidence_i          # LLM が返す 0.0〜1.0
pain = 100 * Σ(w_i * c_i * g_i) / Σ(g_i)
```

- `Σ(g_i) == 0` または rising が空の場合、`pain = None`
- `confidence` が範囲外の場合は `clip(c_i, 0.0, 1.0)` する
- 結果は定義上 0〜100 に収まるが、浮動小数誤差に備え `clip(pain, 0, 100)` する

### 設計意図

Pain は rising query の**構成**(困りごと系の成長がどれだけの割合を占めるか)を測る。rising query の**件数の少なさ**は Pain を下げるのではなく、[Evidence Confidence](#6-evidence-confidence) の Sample sufficiency で扱う。スコアと確信度を混ぜないための分離である。

## 4. Solution Coverage Gap (weight 25%)

入力: Google Search の `organic_results` 上位 `TOP_N` 件と、各結果に対する LLM 分類結果。

| 定数 | 値 |
|---|---:|
| `TOP_N` | 10 |

### カバレッジ重み

| 分類 | 重み |
|---|---:|
| `DIRECT_PROVIDER` | 1.0 |
| `MARKETPLACE` | 0.7 |
| `GOVERNMENT` | 0.4 |
| `INFORMATION` | 0.0 |
| `NEWS` | 0.0 |
| `OTHER` | 0.0 |

`DIRECT_PROVIDER` / `MARKETPLACE` / `GOVERNMENT` の値は依頼書に明記されている。残り3つは「解決策そのものではない」ため 0。

### 順位重み

上位ほど検索上の可視性が高い。

```text
rank_weight_i = 1 / log2(position_i + 1)
```

`position` は SerpApi の 1 始まりの順位。`position=1` → 1.0、`position=10` → 約 0.289。`position` が欠落している要素は配列内の 1 始まりの添字で代替する。

### 計算

```text
solution_visibility = 100 * Σ(coverage_weight_i * confidence_i * rank_weight_i) / Σ(rank_weight_i)
solution_gap = 100 - solution_visibility
```

- `organic_results` が空の場合、`solution_gap = None`
- 分母は上位 `TOP_N` 件**すべて**の順位重みの合計(分類にかかわらず)。分類済みの件だけで割ってはいけない
- `clip(solution_gap, 0, 100)` する

### 表示上の必須注記

これは「実際のサービス供給不足」ではなく **「検索上で見える Solution Coverage の不足」** である。UI に必ず明示する。

## 5. News Urgency (weight 10%)

入力: Google News の `news_results` と、各記事に対する LLM 関連性分類結果。

### 関連性重み

| 分類 | 重み |
|---|---:|
| `DIRECTLY_RELEVANT` | 1.0 |
| `RELATED` | 0.5 |
| `UNRELATED` | 0.0 |

分類は `title` と `source.name` のみを入力とする(Google News に `snippet` は存在しない)。

### 新しさ

記事の `iso_date`(ISO8601 UTC)を使う。`iso_date` が無い記事は `date` のパースを試み、失敗した場合はその記事を**除外**する(推測で日付を補わない)。

```text
age_days_i = max(0, (scan_time - published_at_i) / 86400秒)
recency_weight_i = exp(-age_days_i / 30)
```

`scan_time` は引数で受け取る。関数内で現在時刻を取得しない。

### 計算

| 定数 | 値 |
|---|---:|
| `NEWS_SATURATION` | 5.0 |

```text
news_mass = Σ(relevance_weight_i * confidence_i * recency_weight_i)
news_urgency = 100 * (1 - exp(-news_mass / NEWS_SATURATION))
```

飽和曲線を使うため上限を超えない。目安として「完全に関連する当日の記事」5本で約 63、15本で約 95。

- `news_results` が空、または日付をパースできる記事が1件も無い場合、`news_urgency = None`

### 禁止事項

**ニュースが少ないことを「問題が存在しない」と判断してはいけない。** News は全体の 10% に留めており、少ない場合は Confidence 側で扱う。

## 6. Evidence Confidence

**Need Gap Score とは完全に別のスコアである。** 0〜100。

### Core Source

Core Source は次の4つ。Maps は含まない。

1. `trends`(TIMESERIES)
2. `related_queries`
3. `search`
4. `news`

各ソースは次のいずれかの状態を持つ。

- `OK`: 取得に成功し、下位スコアの計算に使える内容があった
- `MISSING`: 取得に失敗した、または内容が空で計算に使えなかった

### 重み

| 要素 | 重み |
|---|---:|
| Data completeness | 30% |
| Sample sufficiency | 25% |
| Localization quality | 20% |
| Source agreement | 15% |
| Freshness | 10% |

```text
confidence_raw =
    0.30 * data_completeness
  + 0.25 * sample_sufficiency
  + 0.20 * localization_quality
  + 0.15 * source_agreement
  + 0.10 * freshness
```

### Data completeness

```text
data_completeness = 100 * (OK の Core Source 数) / 4
```

### Sample sufficiency

| ソース | 数える対象 | 目標件数 |
|---|---|---:|
| `trends` | 週次データ点 | 12 |
| `related_queries` | rising query | 10 |
| `search` | organic result | 10 |
| `news` | 日付をパースできた記事 | 5 |

```text
ratio_s = clip(count_s / target_s, 0, 1)      # MISSING のソースは ratio_s = 0
sample_sufficiency = 100 * mean([ratio_s for s in 4つの Core Source])
```

### Localization quality

QueryProfile の `review_status` から決まる。

| `review_status` | 値 |
|---|---:|
| `MANUAL_REVIEWED` | 100 |
| `LLM_GENERATED` | 70 |

依頼書の「LLM生成のみのQueryProfile → Localization 最大70」「手動レビュー済QueryProfile → Localization 100」に対応する。

さらに、QueryProfile の `language` がその国の主要言語でない場合は `localization_quality` を 20 減じる(下限 0)。判定は QueryProfile の `language` と国コードの対応表による。

### Source agreement

4つの下位スコアが互いに整合しているか。値が散らばっているほど確信度を下げる。

```text
s = [x / 100 for x in [demand, pain, solution_gap, news_urgency] if x is not None]
```

- `len(s) < 2` の場合、`source_agreement = 0`
- それ以外:

```text
source_agreement = clip(100 * (1 - 2 * pstdev(s)), 0, 100)
```

`s` の各要素は [0, 1] に収まるため `pstdev(s)` の最大は 0.5。したがって値域は [0, 100]。

### Freshness

`OK` の Core Source ごとに、根拠データの古さを求める。

| ソース | `age_days` |
|---|---|
| `trends` | `scan_time` − 最新の timeline データ点の timestamp |
| `news` | `scan_time` − 最も新しい記事の `iso_date` |
| `related_queries` | キャッシュ経過時間(新規取得なら 0) |
| `search` | キャッシュ経過時間(新規取得なら 0) |

```text
freshness_s = 100 * exp(-max(0, age_days_s) / 30)
freshness = mean([freshness_s for s in OK の Core Source])
```

`OK` の Core Source が0件の場合は `freshness = 0`。

### Hard Rules

`confidence_raw` を求めた後、次を**この順に**適用する。

1. `trends` が `MISSING` → `need_gap_score = None`, `status = INSUFFICIENT_EVIDENCE`
2. Core Source の `MISSING` が **2つ以上** → `status = INSUFFICIENT_EVIDENCE`, `need_gap_score = None`
3. Core Source の `MISSING` が **ちょうど1つ** → `confidence = min(confidence, 69)`
4. Trends の週次データ点のうち **値が 0 のものが 50% 以上** → `confidence = min(confidence, 59)`
5. `localization_quality` の上限は Localization quality 節の表に従う(算出時点で適用済み)

`status = INSUFFICIENT_EVIDENCE` の場合も **Evidence Confidence は算出して返す**。何がどれだけ欠けているかを利用者へ示すためである。

### 丸め

```text
confidence = round_half_up(clip(confidence_after_hard_rules, 0, 100))
```

## 7. ステータス

| status | 条件 |
|---|---|
| `COMPLETED` | `need_gap_score` を算出できた |
| `INSUFFICIENT_EVIDENCE` | Hard Rules 1 または 2 に該当 |
| `FAILED` | 想定外の例外により処理を完了できなかった |

`INSUFFICIENT_EVIDENCE` はエラーではない。**部分的な結果と Confidence を返し、ランキングからは除外する。**

## 8. バージョン

結果には必ず次を含める。

| フィールド | 例 | 変更条件 |
|---|---|---|
| `query_profile_version` | `elder-care-jp-v1` | QueryProfile の内容を変えたとき |
| `score_version` | `gapatlas-score-v1` | この文書の計算定義・定数・重みを変えたとき |
| `classifier_version` | `gapatlas-classifier-v1` | 分類カテゴリ定義または分類ロジックを変えたとき |
| `prompt_version` | `gapatlas-prompt-v1` | LLM プロンプトを変えたとき |

## 9. テストで必ず押さえる境界

- 週次データ点が 11 点 → `demand = None`
- 週次データ点が全て 0 → `r = 1` → `ratio_score = 50`、`slope = 0` → `slope_score = 50`、`demand = 50`。かつ Hard Rule 4 により `confidence <= 59`
- `previous_mean = 0`, `recent_mean = 0` でゼロ除算しない
- `r` が非常に大きい / 小さいとき `clip` が効く
- rising が空 → `pain = None`
- rising が全て `NEUTRAL` → `pain = 0`(`None` ではない)
- `"Breakout"` / `"Record"` / 未知文字列で例外を投げない
- `organic_results` が空 → `solution_gap = None`
- `organic_results` が全て `DIRECT_PROVIDER` かつ confidence 1.0 → `solution_gap = 0`
- `news_results` が空 → `news_urgency = None`
- `iso_date` が無い記事のみ → `news_urgency = None`
- 未来日付の記事 → `age_days = 0` に丸められる
- Core Source 1つ欠損 → `confidence <= 69`
- Core Source 2つ欠損 → `status = INSUFFICIENT_EVIDENCE`
- `trends` 欠損 → `need_gap_score = None`
- 下位スコアが1つしか無い → `source_agreement = 0`
