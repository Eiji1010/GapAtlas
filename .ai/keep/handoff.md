# 作業引き継ぎ: GapAtlas MVP 実装

この文書は**セッションとマシンをまたぐ引き継ぎ**のため Git 追跡ファイルとして置いています（`.ai/temp/` は worktree もマシンもまたげません）。作業が進んだら**上書き更新**してください。履歴は Git が持ちます。

- 最終更新: 2026-08-28
- 統合ブランチ: `develop`
- Remote: `git@github.com:Eiji1010/GapAtlas.git`

## 次のセッションで最初にやること

```bash
git fetch --all --prune
git switch develop && git pull --ff-only
make setup          # backend の依存関係(uv sync)
make verify         # 開始時点で緑であることを確認
```

読む順番:

1. `AGENTS.md`
2. `docs/index.md`
3. この引き継ぎ
4. `.ai/keep/workflows/autonomous-wave.md`（自律実行する場合）
5. 実装対象の仕様書

`.env` は Git 管理外です。必要なら `cp .env.example .env`。既定の `SERPAPI_MODE=fixture` / `LLM_MODE=stub` で外部APIキーなしに全て動きます。

## 作業目的

`gapatlas_claude_implementation_prompt.md`（ハッカソン向け実装依頼書）に基づく GapAtlas MVP の実装。

**依頼書の原本はリポジトリ外**（`~/Downloads/gapatlas_claude_implementation_prompt.md`）にあります。内容は `docs/requirements.md` へ転記済みで、**別マシンではそちらを正本として扱ってください。**

## 確定した方針（ユーザー確認済み）

| 論点 | 決定 | 記録 |
|---|---|---|
| LLM プロバイダ | **Anthropic API 直接**（Bedrock ではない）。`LLM_MODE=stub\|anthropic` | [ADR 0002](../../docs/decisions/0002-llm-provider.md) |
| AWS デプロイ | **Terraform コード作成と `validate`/`plan` まで。`apply` はしない** | `docs/requirements.md` の逸脱表 |
| SerpApi | **APIキー未取得。完全 fixture で進める**。live 実装は書くが未検証 | [ADR 0003](../../docs/decisions/0003-fixture-first.md) |
| 開発体制 | git worktree 上の複数エージェント並列 + 第三者視点レビュー | [自律Wave実行](workflows/autonomous-wave.md) |
| 権限 | `git push` / `gh pr create` / `gh pr merge` を無確認で許可。`main` へのマージと `terraform apply` は確認を残す | `.claude/settings.json` |

## Wave の進捗

| Wave | 内容 | 状態 |
|---|---|---|
| W0 | リポジトリ基盤 + 仕様ドキュメント一式 | **完了** |
| W1 | Phase 2 ドメインモデル（凍結契約） / SerpApi fixture 作成 | **完了** |
| W2 | Phase 3 SerpApiアダプタ / Phase 4+5 Scoring+Confidence / LLMアダプタ+分類 | **次はここ** |
| W3 | 統合 → CLI E2E（`make scan COUNTRY=JP`） | 未着手 |
| W4 | 第三者レビュー（仕様適合 / セキュリティ・信頼性 / 数値独立検証） | 未着手 |
| W5+ | Phase 6〜15 | 未着手 |

## 完了済みの成果物

### W0: 基盤

- `AGENTS.md` / `CLAUDE.md` — AI開発ルールの正本
- `.ai/keep/workflows/` — analyze / plan / implementation / review / **third-party-review** / **parallel-agents** / **autonomous-wave** / handoff
- `.ai/keep/templates/` — task-request / implementation-plan / completion-report / handoff / agent-handoff-request
- `docs/` — requirements / scoring / methodology / architecture / api / serpapi-schema / query-profiles / llm-prompts / index / development/commands
- `docs/decisions/` — ADR 0001〜0003
- `config/query_profiles/elder_care/{JP,US,GB,DE,IN}.yaml`
- `Makefile` / `backend/pyproject.toml`（ruff + mypy strict + pytest）/ `.env.example` / `.claude/settings.json`

### W1-1: ドメインモデル（Phase 2）— 凍結契約

`backend/src/gapatlas/domain/models/` と `backend/src/gapatlas/config/`。

検証: ruff / ruff format / **mypy strict** / **pytest 150件** すべて成功（統合ブランチで独立に再実行して確認済み）。

**後続トラックが知っておくべき点:**

- 全ドメインモデルは `ConfigDict(extra="forbid")`。**YAML やレスポンスに未知フィールドがあると弾かれる**
- `Settings` の API キーは **`SecretStr`**。利用側は `.get_secret_value()` を呼ぶ（`__repr__` へのキー漏洩を型で防止）
- `TrendsSeries.points` はバリデータで**古い順へ自動ソート**される（`scoring.md` の「末尾12点」前提をアダプタのバグで破れないようにするため）
- 日時は `UtcDatetime`（naive は `InvalidTemporalValueError`）
- `*Classification.confidence` は範囲外の値を **clip**（例外を投げない）
- 例外階層: `GapAtlasError` → `DomainError` / `ConfigError`。`DomainValidationError` は `ValueError` を継承（Pydantic が `ValidationError` へ変換するため）
- `__init__.py` はすべて**空**（再エクスポートしない＝並行作業の衝突源を消す方針）

### W1-2: SerpApi fixture

`backend/tests/fixtures/serpapi/` に 40 JSON + README。

- 正常系 25件: `elder_care/{JP,US,GB,DE,IN}/{trends_timeseries,trends_related_queries,search,news,maps}.json`
- 境界値・異常系 15件: `edge_cases/`
- **基準日 `2026-08-28T00:00:00Z`**。テストは `scan_time` にこれを明示的に渡すこと（渡さないと非決定的になる）
- 各国に異なるトレンド性質を付与: JP=明確な上昇 / DE=ノイズの多い上昇 / IN=低ボリューム(0が37.2%) / US=横ばい / GB=緩やかな下降。**ランキングに差が出るよう意図的に設計されている**
- Hard Rule 4（ゼロ率50%以上）は `edge_cases/trends_timeseries_half_zero.json`（61.5%）で検証する。IN は 37.2% で意図的に閾値未満
- 企業・媒体名はすべて架空、URL は予約ドメインのみ、APIキー混入なし（検証済み）

## W2 の計画

### 開始前に必ずやる契約変更（並列起動より先）

**QueryProfile に Maps 用のフィールドが無い。** fixture の `maps.json` は暫定的に `solution_query` と各国主要都市の座標を使っている。Maps は Phase 6 で Top2 の Local Evidence に必要になる。

W2 の並列起動より**前に**、統合担当が次を一括で行うこと（契約を実装 Wave 中に変えないため）。

1. `docs/query-profiles.md` に `maps_query`（1件）と `maps_location`（SerpApi の `ll` 形式）を追加
2. `config/query_profiles/elder_care/*.yaml` 5件へ追記
3. `domain/models/query_profile.py` の `QueryProfile` へフィールド追加（`extra="forbid"` のため**追記しないと YAML ロードが壊れる**）
4. `backend/tests/unit/config/` のテスト更新
5. `make verify` で緑を確認してからコミット

### 並列トラック（担当ディレクトリが重ならない3本）

| トラック | 担当ディレクトリ | 内容 |
|---|---|---|
| A: SerpApiアダプタ | `adapters/serpapi/`, `tests/unit/adapters/serpapi/` | Protocol 定義、fixture 実装、live(httpx) 実装、正規化。リトライ対象は 429/500/503 とネットワークエラーのみ |
| B: Scoring + Confidence | `domain/scoring/`, `tests/unit/scoring/` | `docs/scoring.md` を正本に純粋関数で実装。**時刻は引数で受け取る**。I/O 禁止 |
| C: LLMアダプタ + 分類 | `adapters/llm/`, `tests/unit/adapters/llm/` | `docs/llm-prompts.md` を正本に。stub は決定的な規則ベース（全部 NEUTRAL を返す無意味な stub にしない） |

**B は Scoring と Confidence を分割しないこと。** `INSUFFICIENT_EVIDENCE` と「Trends失敗→スコア非表示」の状態遷移が両方に跨るため。

### W3: 統合（統合担当が実施）

`application/` と `cli.py` を実装し、次を成立させる（依頼書 §31 の Phase 4 完了条件）。

```bash
make scan COUNTRY=JP
```

```json
{ "country": "JP", "topic": "elder_care", "demand": 0, "pain": 0,
  "solution_gap": 0, "need_gap_score": 0, "confidence": 0 }
```

値は fixture の内容に応じて変わってよい。

**注意**: `backend/pyproject.toml` は `[project.scripts] gapatlas = "gapatlas.cli:main"` を宣言済みだが `cli.py` はまだ無い。`make scan` は `cli.py` が入るまで失敗する。

## 重要な技術的判断（会話だけに残さないため記録）

### C1. ドメインモデルは並列化しない

全トラックの共通依存。W1 で確定済み。**W2 実行中にモデルを変更しない**（変更が必要なら上記「開始前の契約変更」で先に済ませる）。

### C2. Google Trends の 0〜100 は相対値

国間の絶対需要比較に使えない。Demand Momentum は**変化率のみ**から算出している。`docs/methodology.md` 参照。

### C3. Scoring と Confidence は同一エージェントが担当する

状態遷移が両方に跨るため。

### C4. LLM の非決定性をスコアへ漏らさない

分類結果は入力ハッシュでキャッシュ。単体テストは常に stub。

### C5. fixture の品質がテストの品質

`docs/serpapi-schema.md` で「確認済み」の構造のみに依存する。「未確認」項目に依存する実装を書かない。

### C6. 共有ファイルは統合担当だけが編集する

`AGENTS.md` / `CLAUDE.md` / `README.md` / `Makefile` / `backend/pyproject.toml` / `.env.example` / `docs/` 配下 / `.ai/keep/` 配下。並列エージェントは変更要望を完了報告に書く。

### C7. worktree エージェントのブランチ分岐元

`isolation: worktree` で起動したエージェントのブランチは、起動時の HEAD ではなく `main` から切られる場合がある（W1-2 で実際に発生）。マージ前に `git diff --name-only develop..<branch>` で担当範囲外の混入を確認すること。分岐元の差分がそのまま出るため、**ファイル名だけで混入と判断しない**。

## 持ち越した課題

| # | 内容 | 対応する Phase |
|---|---|---|
| 1 | QueryProfile に Maps 用フィールドが無い | **W2 開始前**（上記） |
| 2 | QueryProfile ローダーが `<repo>/config/query_profiles` を相対解決しており、**Lambda デプロイパッケージ内では解決できない**。`QUERY_PROFILES_DIR` 環境変数の追加か wheel 同梱が必要。`base_dir` 引数が注入点として用意済み | Phase 9 / 13 |
| 3 | `OpportunityBrief.cited_evidence_ids` の Evidence 実在チェックはモデル層では行えない（brief は `ScanSummary`、evidence は `CountryResult` にあり同居しない）。`docs/llm-prompts.md` 規定のコード側検証として application 層が担当する | Phase 11 |
| 4 | `load_all_query_profiles` は全 `Country` メンバーのファイル存在を要求する。将来 Topic ごとに対象国が異なる場合はディレクトリ走査へ変更が必要 | 将来 |
| 5 | `CountryResult` の整合性検証は片方向のみ（score が None ⇒ status は INSUFFICIENT_EVIDENCE/FAILED）。逆方向は未強制 | 必要になったら |

## 未確認事項（推測で実装しないこと）

SerpApi キー取得後に実データで再検証が必要。チェックリストは `docs/serpapi-schema.md` 末尾。

- TIMESERIES に複数キーワードを渡したときの `values` 配列の完全な構造（**fixture はこの推定に基づいており、違えば5か国の timeseries を作り直す必要がある**）
- `rising[].value` に `"Record"` が実際に出るか
- Google News の `stories` ネストの発生条件とキー構造
- Maps の `search_metadata` の Maps 固有キー
- News の `menu_links` / `related_topics` / `related_publications` の中身の構造

## SerpApi 調査で判明した、実装に直結する事実

いずれも公式ドキュメントで確認済み。詳細は `docs/serpapi-schema.md`。

1. **RELATED_QUERIES は1リクエスト1クエリのみ**（TIMESERIES と違いカンマ区切り不可）
2. **Google News に `snippet` が存在しない** → 関連性分類は `title` + `source.name` のみ
3. **Google News の `date` は絶対表記**、`iso_date`(ISO8601 UTC) が併記 → recency は `iso_date` を使う
4. **rising の `value` は `"+4,500%"` / `"Breakout"` / 未文書の `"Record"` を取りうる** → `extracted_value` を主とし防御的にパースする
5. Google Trends に `gl` / `google_domain` は無い。地域指定は `geo` のみ
6. 英国は `geo: GB` だが `gl: uk`

## 秘密情報について

- SerpApi / Anthropic の API キーはリポジトリに存在しない
- `.env` は `.gitignore` 済み。`.env.example` にはプレースホルダーのみ
- fixture に APIキーらしき文字列が無いことを検証済み

## 注意事項

- `main` へ直接コミットしない。統合ブランチは `develop`。`main` への反映は `develop` からの PR で行い、**人間の承認を得る**
- 強制push・履歴書き換えをしない
- `terraform apply` を実行しない
- テストを通すためにアサーションを弱めない
- 検証を通していないものを「完了」と報告しない
