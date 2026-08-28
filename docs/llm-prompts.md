# LLM プロンプト仕様

`classifier_version = gapatlas-classifier-v1`
`prompt_version = gapatlas-prompt-v1`

LLM の役割は **分類** と **説明** の2つだけです。この文書はその契約の正本です。

## 絶対条件

- **LLM にスコアを計算させない。** 分類結果は数値計算の入力にすぎない
- **LLM に URL を生成させない。** 生成文中の URL は SerpApi のレスポンス由来のものだけを、コード側で差し込む
- **LLM に Evidence に存在しない事実を断定させない**
- 出力は必ず **Structured JSON**。自由文の中に JSON を埋める形式にしない
- 分類は `LLM_MODE=stub` で **決定的なスタブ**に差し替えられること。単体テストは常に stub で動く
- 分類結果は入力ハッシュでキャッシュする（同じ入力に同じ結果を返す）

## 共通のレスポンス規約

すべての分類 API は次の形を返します。

```json
{
  "results": [
    { "index": 0, "classification": "SHORTAGE", "confidence": 0.94 },
    { "index": 1, "classification": "NEUTRAL",  "confidence": 0.61 }
  ]
}
```

- `index` は入力配列の 0 始まりの添字。**入力と同数・同順で返させるが、コード側で照合すること**
- 欠落した `index` があれば、その項目は `NEUTRAL` / `OTHER` / `UNRELATED` に `confidence = 0.0` で補完する（例外にしない）
- 未知の `classification` 値が返ってきた場合も同様に既定値へフォールバックし、警告ログを出す
- `confidence` が数値でない、または範囲外の場合は `0.0〜1.0` に clip する
- **LLM の失敗でスキャン全体を止めない。** 分類が全滅した場合、その成分は `None`（欠損）として扱い、Confidence へ反映する
- **「全滅」はアダプタが `LlmError` を送出して知らせる。** application 層はこれを捕捉して該当ソースを `MISSING` にする。既定値で全件を埋めた結果を返してはいけない（`solution_gap = 100` が最大値として観測値のように扱われ、Confidence にも反映されない）。**部分的な欠落は例外にしない**（既定値の `confidence = 0.0` はスコアへ寄与せず、件数は Sample sufficiency が評価する）

## 1. Related Queries の分類（Pain Signal 用）

### 入力

Google Trends RELATED_QUERIES の `rising` 配列の検索語。1件ずつではなくバッチで渡す。

各項目に渡す情報は **検索語の文字列のみ**。成長率を渡してはいけません（成長率を見せると LLM が「重要度」を判断しようとし、分類がスコアに汚染されます）。

### カテゴリ

| 値 | 定義 |
|---|---|
| `ACCESS` | サービスや制度に到達できない、たどり着けないことを示す |
| `SHORTAGE` | 供給が足りない、空きがない、見つからないことを示す |
| `WAIT_TIME` | 待機期間、順番待ち、いつになるかを示す |
| `COST` | 費用、負担、補助の有無など経済的障壁を示す |
| `QUALITY` | 質の低さ、事故、不信、苦情を示す |
| `WORKFORCE` | 担い手・人材の不足、労働環境を示す |
| `NEUTRAL` | 上記のいずれの困りごとも示さない（一般的な情報探索、固有名詞、無関係語） |

### プロンプトの要件

- システムプロンプトで「あなたは検索クエリを分類する分類器である。スコアや順位を決めてはいけない」と明示する
- 対象国と言語を伝える（例: 日本語の検索語である、という文脈）
- **迷った場合は `NEUTRAL` を選び、`confidence` を下げるよう指示する。** 無理に困りごとへ寄せさせない
- 出力例を1つだけ示す（Few-shot を増やしすぎると特定カテゴリへ引っ張られる）
- カテゴリの定義は上表をそのまま渡す

## 2. Search Results の分類（Solution Coverage Gap 用）

### 入力

Google Search の `organic_results` 上位10件。各項目について **`title` / `link` / `snippet`（あれば）/ `displayed_link`（あれば）** を渡す。

`position` を渡してはいけません（順位重みはコード側で計算します）。

### カテゴリ

| 値 | 定義 |
|---|---|
| `DIRECT_PROVIDER` | サービスを直接提供している事業者・施設のサイト |
| `MARKETPLACE` | 複数の提供者を比較・検索・仲介するプラットフォーム |
| `GOVERNMENT` | 政府・自治体・公的機関のサイト |
| `INFORMATION` | 解説記事、まとめ、ブログ、辞書、Q&A |
| `NEWS` | 報道記事 |
| `OTHER` | 上記のいずれでもない |

### プロンプトの要件

- 「その URL の先で実際にサービスを申し込めるか」を判断基準として明示する
- 迷った場合は `OTHER` を選び `confidence` を下げるよう指示する
- ドメインの見た目だけで判断せず、`title` と `snippet` を併せて判断させる

## 3. News Results の分類（News Urgency 用）

### 入力

Google News の `news_results`。各項目について **`title` と `source.name` のみ**。

**Google News に `snippet` は存在しません**（[SerpApi スキーマ](serpapi-schema.md)参照）。存在しないフィールドを前提にしたプロンプトを書かないでください。

日付を渡してはいけません（recency はコード側で `iso_date` から計算します）。

### カテゴリ

| 値 | 定義 |
|---|---|
| `DIRECTLY_RELEVANT` | その国のその課題（Elder Care）そのものを扱った記事 |
| `RELATED` | 隣接する話題（高齢化全般、医療、社会保障など）を扱った記事 |
| `UNRELATED` | 無関係 |

### プロンプトの要件

- 対象 Topic と国を伝える
- 見出しだけで判断できない場合は `RELATED` を選び `confidence` を下げるよう指示する

## 4. Opportunity Brief の生成

ランキング Top1 の国について生成します。

### 入力

コード側が組み立てた **Evidence パック**のみを渡します。LLM に生データを渡しません。

```json
{
  "country": "JP",
  "topic": "elder_care",
  "need_gap_score": 86,
  "confidence": 92,
  "components": { "demand": 91, "pain": 84, "solution_gap": 78, "news_urgency": 83 },
  "evidence": [
    { "id": "E1", "source": "trends", "summary": "直近4週の検索需要が前8週比で上昇" },
    { "id": "E2", "source": "related_queries", "summary": "SHORTAGE に分類された急上昇クエリが3件" },
    { "id": "E3", "source": "search", "summary": "上位10件のうち直接提供事業者は2件" },
    { "id": "E4", "source": "news", "summary": "過去14日に人手不足を扱った記事が5件" }
  ],
  "limitations": ["Solution Coverage は検索上の可視性であり実際の供給量ではない", "..."]
}
```

Evidence の `summary` は **コード側が生成した事実**です。LLM はこれを言い換え・統合するだけで、新しい事実を足しません。

### 出力

```json
{
  "why_now": "...",
  "what_people_are_struggling_with": "...",
  "visible_solutions": "...",
  "what_this_does_not_prove": "...",
  "next_validation": "...",
  "cited_evidence_ids": ["E1", "E2", "E3", "E4"]
}
```

### 引用の規約

本文中で Evidence を `[E1]` の形式で引用させます。

```text
Demand accelerated [E1], while shortage-related queries increased [E2].
```

### コード側の検証（必須）

生成結果を**そのまま採用してはいけません。** 次を検証します。

1. 本文中の `[E<n>]` がすべて入力の Evidence ID に存在すること。存在しない ID を含む場合は**その節を再生成するか、引用を除去する**
2. `why_now` / `what_people_are_struggling_with` / `visible_solutions` の各節に **最低1つの Evidence 引用があること**
3. 本文に URL(`http://` / `https://`) が含まれていないこと。含まれていたら除去する
4. `what_this_does_not_prove` に、[方法論と限界](methodology.md)由来の限界が最低1つ含まれること
5. `cited_evidence_ids` を本文から再抽出して上書きする（LLM の自己申告を信用しない）

検証に失敗し再生成しても直らない場合、**Opportunity Brief を出さない**（`null` を返す）。誤った断定を出すより出さないほうが安全です。

### プロンプトの要件

- 「入力の Evidence に無い事実を書いてはいけない。数値を新たに作ってはいけない。URL を書いてはいけない」を明示する
- 「断定を避け、観測された内容として書く」ことを明示する
- `what_this_does_not_prove` は必ず埋めさせる。空にさせない
- `next_validation` は「次に何を調べるか」の具体的な行動にする（一次調査、統計、規制、現地ヒアリング）

## stub モードの要件

`LLM_MODE=stub` のとき、次を満たしてください。

- ネットワークに一切アクセスしない
- 同じ入力に対して常に同じ出力を返す（乱数・時刻に依存しない）
- 分類は、入力文字列に対する**決定的な規則**（例: キーワード一致表）で決める。すべて `NEUTRAL` を返すような無意味な stub にしない。スコアリングのテストが意味を持たなくなるため
- stub の分類規則は `docs/` ではなくコードとテストで管理する（プロンプト仕様の一部ではない）
- Opportunity Brief の stub は、入力 Evidence ID をすべて引用した固定文面を返す。**引用は「コード側の検証」2 を満たすよう、`why_now` / `what_people_are_struggling_with` / `visible_solutions` の3節それぞれに置く**（1節にまとめると検証で落ちる）

## バージョン管理

| 変更内容 | 上げるバージョン |
|---|---|
| カテゴリの追加・削除・定義変更 | `classifier_version` |
| 分類の後処理・フォールバック規則の変更 | `classifier_version` |
| プロンプト文面の変更 | `prompt_version` |
| モデル ID の変更 | `prompt_version` |

両方を結果に記録し、再現可能性を保ちます。

**版は実装ごとに異なる値を返します。** `LlmClassifier` / `BriefWriter` は `classifier_version` / `prompt_version` プロパティを持ち、結果にはそれが記録されます。

| 実装 | `classifier_version` | `prompt_version` |
|---|---|---|
| `StubLlmClient` | `gapatlas-classifier-v1-stub` | `gapatlas-prompt-v1-stub` |
| `AnthropicLlmClient` | `gapatlas-classifier-v1` | `gapatlas-prompt-v1+<モデルID>` |

stub の規則ベース分類と実 LLM の分類は結果が変わるため、同じ識別子を名乗ってはいけません。モデル ID を `prompt_version` に含めるのは、モデルを差し替えたときに版が自動で変わるようにするためです。
