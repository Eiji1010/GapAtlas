# 作業引き継ぎ: GapAtlas MVP 実装

この文書は**セッションとマシンをまたぐ引き継ぎ**のため Git 追跡ファイルとして置いています（`.ai/temp/` は worktree もマシンもまたげません）。作業が進んだら**上書き更新**してください。履歴は Git が持ちます。

- 最終更新: 2026-08-29
- 統合ブランチ: `develop`
- Remote: `git@github.com:Eiji1010/GapAtlas.git`

## 次のセッションで最初にやること

```bash
git fetch --all --prune
git switch develop && git pull --ff-only
make setup          # backend の依存関係(uv sync --all-extras)
make verify         # 開始時点で緑であることを確認(799 passed)
```

読む順番:

1. `AGENTS.md`
2. `docs/index.md`
3. この引き継ぎ
4. `.ai/keep/workflows/autonomous-wave.md`（自律実行する場合）
5. 実装対象の仕様書

`.env` は Git 管理外です。必要なら `cp .env.example .env`。既定の `SERPAPI_MODE=fixture` / `LLM_MODE=stub` で外部APIキーなしに全て動きます。

### 環境の前提（2026-08-29 時点で確認）

- `uv` が必要です。未導入なら `brew install uv`
- **`gh` は未認証です。** PR の作成・マージには `gh auth login` が必要（人間が対話で実行する）。認証できるまで、Wave の成果は `develop` へ直接 push しています

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
| W2 | Phase 3 SerpApiアダプタ / Phase 4+5 Scoring+Confidence / LLMアダプタ+分類 | **完了**（第三者レビュー3観点と指摘対応まで） |
| W3 | 統合 → CLI E2E（`make scan COUNTRY=JP`） | **次はここ** |
| W4 | 第三者レビュー（W3 の統合部分） | 未着手 |
| W5+ | Phase 7〜15（永続化 / API / Frontend / Terraform / Athena / demo） | 未着手 |

`make verify` は **799 passed**（ruff / ruff format / mypy strict / pytest すべて緑）。

## 完了済みの成果物

### W0: 基盤

- `AGENTS.md` / `CLAUDE.md` — AI開発ルールの正本
- `.ai/keep/workflows/` — analyze / plan / implementation / review / third-party-review / parallel-agents / autonomous-wave / handoff
- `.ai/keep/templates/` — task-request / implementation-plan / completion-report / handoff / agent-handoff-request
- `docs/` — requirements / scoring / methodology / architecture / api / serpapi-schema / query-profiles / llm-prompts / index / development/commands
- `docs/decisions/` — ADR 0001〜0003
- `config/query_profiles/elder_care/{JP,US,GB,DE,IN}.yaml`
- `Makefile` / `backend/pyproject.toml`（ruff + mypy strict + pytest）/ `.env.example` / `.claude/settings.json`

### W1: ドメインモデルと fixture

`backend/src/gapatlas/domain/models/` と `backend/src/gapatlas/config/`、`backend/tests/fixtures/serpapi/`（40 JSON + README）。

**後続が知っておくべき点:**

- 全ドメインモデルは `ConfigDict(extra="forbid")`。**YAML やレスポンスに未知フィールドがあると弾かれる**
- `Settings` の API キーは **`SecretStr`**。利用側は `.get_secret_value()` を呼ぶ
- `TrendsSeries.points` はバリデータで**古い順へ自動ソート**される
- 日時は `UtcDatetime`（naive は `InvalidTemporalValueError`）
- `*Classification.confidence` は範囲外の値を **clip**（例外を投げない）。`5.0 → 1.0` / `-2.0 → 0.0`
- 例外階層: `GapAtlasError` → `DomainError` / `ConfigError` / `SerpApiError` / `LlmError`
- `__init__.py` はすべて**空**（再エクスポートしない）
- fixture の**基準日は `2026-08-28T00:00:00Z`**。テストは `scan_time` にこれを明示的に渡すこと

### W2: アダプタとスコアリング（本 Wave）

契約変更 → 並列実装3トラック → 統合 → 独立検証 → 第三者レビュー3観点 → 指摘対応。

#### 契約変更

`QueryProfile` へ `maps_query` / `maps_location`（SerpApi `ll` 形式）を追加。5か国の `version` を **v2** へ更新。`maps_location` は形式と座標範囲をモデルで検証する。

#### 公開シグネチャ（後続が配線に使う）

```python
# adapters/serpapi
def build_params(source: SourceName, profile: QueryProfile) -> dict[str, str]
class SerpApiClient(Protocol):
    def fetch(self, source: SourceName, profile: QueryProfile) -> dict[str, Any]
class FixtureSerpApiClient:  # __init__(base_dir: Path | None = None)
class LiveSerpApiClient:     # __init__(settings, *, client=None, sleep=time.sleep)
def create_serpapi_client(settings: Settings) -> SerpApiClient
def normalize_trends_timeseries(raw, queries: Sequence[str]) -> TrendsTimeseries
def normalize_related_queries(raw) -> list[RisingQuery]
def normalize_search_results(raw) -> list[SearchResultItem]
def normalize_news_results(raw) -> list[NewsArticle]
def normalize_maps_results(raw) -> list[MapsPlace]
def mask_api_key(text: str) -> str
def install_api_key_log_guard(logger_names=GUARDED_LOGGER_NAMES) -> None

# domain/scoring
def round_half_up(value: float) -> int
def clip(value: float, lower: float, upper: float) -> float
def compute_ratio_score(window: Sequence[float]) -> float
def compute_slope_score(window: Sequence[float]) -> float
def compute_query_demand_score(points: Sequence[float]) -> float | None
def compute_demand(trends: TrendsTimeseries | None) -> float | None
def compute_pain(classified: Sequence[ClassifiedRisingQuery]) -> float | None
def compute_solution_gap(classified: Sequence[ClassifiedSearchResult]) -> float | None
def compute_news_urgency(classified, scan_time: datetime) -> float | None
def compute_components(evidence, classified, scan_time) -> ScoreComponents
def compute_need_gap(components: ScoreComponents) -> NeedGapResult
def compute_confidence(evidence, profile, components, scan_time) -> ConfidenceResult
def compute_sample_sufficiency(evidence, profile) -> float   # profile が必要
def evaluate_country(evidence, classified, profile, scan_time) -> CountryEvaluation

# adapters/llm
class LlmClassifier(Protocol):   # classify_rising_queries / _search_results / _news_articles
class BriefWriter(Protocol):     # write_brief(pack: EvidencePack) -> OpportunityBrief | None
class StubLlmClient              # 引数なしで構築。両 Protocol を満たす
class AnthropicLlmClient         # __init__(settings, *, client=None)
class CachingLlmClassifier       # __init__(inner: LlmClassifier)
class EvidencePack / EvidenceSummary / BriefComponents
def validate_brief(brief, pack) -> OpportunityBrief | None
def create_llm_classifier(settings) -> LlmClassifier
def create_brief_writer(settings) -> BriefWriter
CLASSIFIER_VERSION / PROMPT_VERSION / SCORE_VERSION
```

`__init__.py` は空なので、**サブモジュールから直接 import** してください。

#### W3 が必ず守るべき契約

1. **`evaluate_country` は `CountryStatus.FAILED` を返しません。** 想定外の例外は application 層が捕捉して `FAILED` にする
2. **分類が全滅すると `LlmError` が飛びます。** application 層はこれを捕捉して**該当ソースを `MISSING`** にすること。既定値で埋めた結果をスコアへ流してはいけない
3. **`SourceFetch` の組み立ては application 層の責務。** 「取得できたが中身が空」を `MISSING` と判定するのも application 層（`domain/scoring` は `NormalizedEvidence.fetches` を信じる）
4. `normalize_trends_timeseries` の第2引数には `profile.demand_queries` をそのまま渡す
5. `compute_sample_sufficiency` は `profile` を要求する（各 demand query 基準で数えるため）

## W3 の計画（次にやること）

`application/` と `cli.py` を実装し、次を成立させる（依頼書 §31 の Phase 4 完了条件）。

```bash
make scan COUNTRY=JP
```

```json
{ "country": "JP", "topic": "elder_care", "demand": 0, "pain": 0,
  "solution_gap": 0, "need_gap_score": 0, "confidence": 0 }
```

**着手前に決めること（後から変えると全ログ呼び出しの書き換えになる）:**

- **構造化ログのコンテキスト伝播方式。** `docs/architecture.md`「Observability」は全ログに `scan_id` / `country` / `topic` / `source` を要求するが、アダプタ層は `scan_id` を知りえない。`contextvars` か `LoggerAdapter` かを先に決める

**実装の骨子:**

- `application/country_scan.py` — 1国分の取得 → 正規化 → 分類 → 評価。**1ソースの失敗で全体を止めない**（`SerpApiError` / `LlmError` を捕捉して `SourceFetch(status=MISSING)`）
- `application/evidence.py` — `Evidence`（`E1` 始まりの連番）と `EvidencePack` の組み立て。**URL は SerpApi レスポンス由来のものだけ**
- `application/scan_service.py` — 5か国の実行、ランキング整列（`need_gap_score` 降順、`None` は末尾）、Top1 の Brief、Top2 の Maps
- `cli.py` — `gapatlas scan --topic elder_care --country JP --mode fixture`

**参考**: `backend/tests/unit/integration/test_fixture_to_score_pipeline.py` に、fixture → 正規化 → stub 分類 → `evaluate_country` を通す配線がすでにあります。application 層はこれを製品コードへ移す形になります。

## 重要な技術的判断（会話だけに残さないため記録）

### C1. ドメインモデルは並列化しない

全トラックの共通依存。W1 で確定済み。変更が必要なら Wave 開始前に単独で行う（W2 の Maps フィールド追加がその例）。

### C2. Google Trends の 0〜100 は相対値

国間の絶対需要比較に使えない。Demand Momentum は**変化率のみ**から算出。`docs/methodology.md` 参照。

### C3. Scoring と Confidence は同一エージェントが担当する

`INSUFFICIENT_EVIDENCE` の状態遷移が両方に跨るため。

### C4. LLM の非決定性をスコアへ漏らさない

分類結果は入力ハッシュでキャッシュ。単体テストは常に stub。

### C5. fixture の品質がテストの品質

`docs/serpapi-schema.md` で「確認済み」の構造のみに依存する。

### C6. 共有ファイルは統合担当だけが編集する

`AGENTS.md` / `CLAUDE.md` / `README.md` / `Makefile` / `backend/pyproject.toml` / `.env.example` / `docs/` 配下 / `.ai/keep/` 配下。並列エージェントは変更要望を完了報告に書く。

### C7. worktree エージェントのブランチ分岐元

`isolation: worktree` のブランチは `main` から切られる場合がある。**エージェントへの指示に `git merge --no-edit develop` を必ず入れること。** W2 では3トラクとも `Already up to date.` となり問題は起きなかった。マージ前の混入確認は `git diff --stat $(git merge-base develop <branch>)..<branch>` を使う（`develop..<branch>` だと先にマージした他トラックの差分が混ざる）。

### C8. Demand は厳密な水準非依存ではない（W2 で判明）

`SMOOTHING = 5.0` を分母へ加えるため、低ボリュームの系列は同じ変化率でも 50 寄りに減衰する。**意図した設計**であり、`docs/scoring.md` へ明記済み。「系列を10倍しても同じ値」というテストは成立しないので書かないこと。

### C9. ログのマスクはプロセス全体に対する要件（W2 で判明）

SerpApi はクエリパラメータ認証のみで URL 自体が秘密情報。httpx は全リクエストの URL を INFO で出力するため、自前のログをマスクするだけでは不十分。`adapters/serpapi/logging_guard.py` が `httpx` / `httpcore` のロガーへフィルタを装着する。**新しい HTTP ライブラリを足す場合は `GUARDED_LOGGER_NAMES` へ追加すること。**

### C10. 「分類の全滅」は欠損として扱う（W2 で判明）

既定値で全件を埋めた結果をスコアへ流すと `solution_gap = 100`（最大値）が観測値として入り、Confidence にも反映されない。アダプタは全滅時に `LlmError` を送出する。

### C11. 仕様の数値はテストにリテラルで書く（W2 で判明）

実装の定数を期待値に使うと自己参照になり、値を書き換えても検出できない。W2 のレビューではミューテーション試験42件のうち4件がこれで見逃されていた。

## 持ち越した課題

| # | 内容 | 対応する Phase |
|---|---|---|
| 1 | QueryProfile ローダーと fixture クライアントが `<repo>/...` を相対解決しており、**Lambda デプロイパッケージ内では解決できない**。両者とも `base_dir` 引数が注入点として用意済み | Phase 9 / 13 |
| 2 | `OpportunityBrief.cited_evidence_ids` の Evidence 実在チェックはモデル層では行えない。`validate_brief` がコード側検証を担うが、`EvidencePack` の組み立ては application 層 | Phase 6 / 11 |
| 3 | `load_all_query_profiles` は全 `Country` メンバーのファイル存在を要求する。Topic ごとに対象国が異なる場合はディレクトリ走査へ変更が必要 | 将来 |
| 4 | `CountryResult` の整合性検証は片方向のみ（score が None ⇒ status は INSUFFICIENT_EVIDENCE/FAILED） | 必要になったら |
| 5 | **全ログに `scan_id` が無い。** アダプタ層は知りえないため、コンテキスト伝播方式を決める必要がある | **Phase 6 の着手前** |
| 6 | `mypy` が `tests/` を型チェックしていない（`packages = ["gapatlas"]`）。有効化には test ディレクトリへの `__init__.py` 追加が必要で、`from conftest import ...` が壊れる | 別途 |
| 7 | live クライアントがリトライごとに `httpx.Client` を再生成する（TLS ハンドシェイクの無駄） | Phase 14 |
| 8 | `edge_cases/search_missing_position.json` は `position` の代替値が本来の順位と一致するため、「添字代替」と「全件添字上書き」を区別できない | fixture を触る機会に |
| 9 | `MapsPlace.link` は `docs/serpapi-schema.md` の確認済みキー一覧に無い。防御的読み取りとして残している | live 検証時 |

## 未確認事項（推測で実装しないこと）

SerpApi キー取得後に実データで再検証が必要。チェックリストは `docs/serpapi-schema.md` 7章。

- **TIMESERIES に複数キーワードを渡したときの `values` 配列の構造。** 実装と fixture の両方がこの推定に依存しており、**違っていた場合は例外が出ず系列が空になり、全国が `INSUFFICIENT_EVIDENCE` になる（無言の全滅）**
- `rising[].value` に `"Record"` が実際に出るか
- Google News の `stories` ネストの発生条件とキー構造（検出したら警告ログを出す実装になっている）
- Maps の `search_metadata` の Maps 固有キー、`local_results[].link` の有無
- Anthropic API で `tool_choice` 強制が現行モデルで期待どおり動くか（フェイククライアントでしか検証していない）

## 秘密情報について

- SerpApi / Anthropic の API キーはリポジトリに存在しない
- `.env` は `.gitignore` 済み。`.env.example` にはプレースホルダーのみ
- fixture に APIキーらしき文字列が無いことを検証済み
- **live モードのログ流出は W2 で塞いだ**（`logging_guard.py` + 回帰テスト）。新しい HTTP ライブラリを足すときは同じ経路を確認すること

## 注意事項

- `main` へ直接コミットしない。統合ブランチは `develop`。`main` への反映は `develop` からの PR で行い、**人間の承認を得る**
- 強制push・履歴書き換えをしない
- `terraform apply` を実行しない
- テストを通すためにアサーションを弱めない
- 検証を通していないものを「完了」と報告しない
