# 作業引き継ぎ: GapAtlas MVP 実装

この文書は**セッションとマシンをまたぐ引き継ぎ**のため Git 追跡ファイルとして置いています（`.ai/temp/` は worktree もマシンもまたげません）。作業が進んだら**上書き更新**してください。履歴は Git が持ちます。

- 最終更新: 2026-08-29 (W8 完了 + ローカル開発サーバー追加時点)
- 統合ブランチ: `develop`
- Remote: `git@github.com:Eiji1010/GapAtlas.git`

## 次のセッションで最初にやること

```bash
git fetch --all --prune
git switch develop && git pull --ff-only
make setup          # backend の依存関係(uv sync --all-extras)
make verify         # backend。開始時点で緑であることを確認(1400 件超)
make setup-frontend # frontend の依存(npm install)
make lint-frontend && make typecheck-frontend && make test-frontend && make build
make tf-validate    # terraform(apply はしない)
```

読む順番:

1. `AGENTS.md`
2. `docs/index.md`
3. この引き継ぎ
4. `.ai/keep/workflows/autonomous-wave.md`（自律実行する場合）
5. 実装対象の仕様書

`.env` は Git 管理外です。必要なら `cp .env.example .env`。既定の `SERPAPI_MODE=fixture` / `LLM_MODE=stub` で外部APIキーなしに全て動きます。

### 環境の前提（2026-08-29 時点で確認）

- `uv` / `node` / `npm` / `terraform` が必要です。未導入なら `brew install uv`、`brew install hashicorp/tap/terraform`
- **`gh` は未認証です。** PR の作成・マージには `gh auth login` が必要（人間が対話で実行する）。認証できるまで、Wave の成果は `develop` へ直接 push しています
- **セッションのレート上限に注意。** 2026-08-29 の作業中に上限（Asia/Tokyo 7:30 リセット）へ当たり、実行中のサブエージェント5体が同時に落ちました。worktree の成果は残るので、統合担当が引き継いで完成させられます

### 画面をバックエンドへ繋いで動かす

```bash
# ターミナル1: API + Worker を1プロセスで起動(既定 http://localhost:8000/api/v1)
make serve

# ターミナル2: 画面を live モードで開く
cd frontend && VITE_API_MODE=live npm run dev
```

`backend/src/gapatlas/api/dev_server.py` は**開発専用**です。本番の入口は API Gateway + Lambda で、このサーバーは同じハンドラ（`api/lambda_handlers.py`）を標準ライブラリの `http.server` で包んだだけです（依存の追加なし）。SQS の代わりにインメモリキューを使い、バックグラウンドスレッドが**1国ずつ**処理します（本番の `batch_size = 1` と同じ単位）。状態はプロセス内メモリなので、再起動すると過去のスキャンは消えます。

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
| W3 | Phase 6 統合 → CLI E2E（`make scan COUNTRY=JP`） | **完了** |
| W4 | W3 の第三者レビュー3観点と指摘対応 | **完了** |
| W5 | Phase 7 永続化（DynamoDB / S3 / Athena 定義） | **完了** |
| W6 | Phase 8 SQS + Worker / Phase 9 API | **完了** |
| W7 | Phase 10 Frontend / Phase 13 Terraform / Cache / Phase 12 Athena クライアント / Phase 14 E2E / Phase 15 demo | **完了** |
| W8 | W5〜W7 の第三者レビュー3観点と指摘対応 | **完了** |
| W9 | main への PR（人間の承認が必要） | **次はここ** |
| 追加 | ローカル開発用 API サーバー（`make serve`） | **完了** |

`make verify` は **1450 passed**（ruff / ruff format / mypy strict / pytest すべて緑）。frontend は 12 件、`terraform validate` も成功。

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

### W3+W4: application 層と CLI（Phase 6）

`SerpApi Fixture → Normalize → Scoring → Confidence → JSON Output` が通るようになりました。

```bash
make scan COUNTRY=JP
cd backend && uv run gapatlas scan --topic elder_care --all --mode fixture
```

fixture に対する現在の期待値（テストで固定済み）:

| 国 | need_gap_score | confidence |
|---|---:|---:|
| JP | 75 | 91 |
| DE | 67 | 90 |
| IN | 66 | 92 |
| GB | 58 | 90 |
| US | 55 | 90 |

#### 公開シグネチャ（W5 が配線に使う）

```python
# application/logging_context.py
def configure_logging(level: str = "INFO", *, stream: Any | None = None) -> None
def log_context(**fields: str | None) -> Iterator[None]        # contextmanager
def current_context() -> Mapping[str, str]
def submit_with_context(executor, function, /, *args, **kwargs) -> Future  # スレッド用
class ScanContextFilter / JsonFormatter
CONTEXT_FIELDS = ("scan_id", "topic", "country", "source")

# application/evidence.py
def build_evidence(evidence, classified) -> list[Evidence]
def build_evidence_pack(country, topic_id, evaluation, items) -> EvidencePack
METHODOLOGY_LIMITATIONS: tuple[str, ...]

# application/country_scan.py
class RawSources:        payloads: dict[SourceName, dict[str, Any]]
class CountryScanOutcome: result / evidence / classified / evaluation / raw
class CountryScanner:
    def __init__(self, serpapi: SerpApiClient, classifier: LlmClassifier)
    def scan(self, profile, *, scan_id, scan_time) -> CountryScanOutcome
    def attach_maps(self, outcome, profile, *, scan_time) -> CountryScanOutcome
def build_failed_outcome(topic_id, country, *, scan_id, scan_time, ...) -> CountryScanOutcome
def build_versions(query_profile_version, *, classifier_version, prompt_version) -> Versions

# application/scan_service.py
class ScanOutput:  summary: ScanSummary / outcomes: dict[Country, CountryScanOutcome]
class ScanService:
    def __init__(self, serpapi, classifier, brief_writer, *, profiles_dir=None)
    def scan(self, topic_id, countries, *, scan_id, scan_time, enrich=True) -> ScanOutput
MAPS_COUNTRY_LIMIT = 2 / RANKABLE_STATUSES = {COMPLETED} / STATUS_RANK
def to_public_component(value: float | None) -> int | None

# cli.py
def main(argv: Sequence[str] | None = None) -> int
```

#### W5 以降が知っておくべき点

1. **`RawSources.payloads` が S3 raw/ 保存用の生レスポンス**。`CountryScanOutcome.raw` に入っている
2. **`ScanOutput.outcomes` は全国分を保持する。** live では最悪 25 payload × 8MB（`MAX_RESPONSE_BYTES`）を同時に抱える。Phase 7 で S3 へ払い出す際は、**国のスキャン完了直後に解放する**設計にすること（持ち越し課題 #10）
3. **並列化するときは `submit_with_context` を使う。** 素の `executor.submit` ではログの4フィールドが `null` になる
4. `ScanService.scan(enrich=False)` で Top2 Maps と Top1 Brief をスキップできる（表示しない呼び出し元が無駄な外部 API 呼び出しを避けるため）

## 旧 W3 の計画（完了済み・参考）

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

### W5〜W7: 永続化・非同期・API・Frontend・Terraform

Phase 1〜15 が一巡しました。`docs/requirements.md` の Definition of Done 18項目は、
**実 AWS / 実 SerpApi / 実 Anthropic が要るもの以外はすべて実装済み**です。

#### 追加された公開シグネチャ

```python
# adapters/dynamodb    ScanRepository / InMemoryScanRepository / DynamoDbScanRepository
#                      create_scan_repository(settings)
# adapters/s3          ScanArchive / InMemoryScanArchive / S3ScanArchive
#                      create_scan_archive(settings) / keys.py / athena.py
#                      AthenaScoreHistory.country_score_history(topic_id, country)
# adapters/sqs         JobQueue / InMemoryJobQueue / SqsJobQueue
#                      create_job_queue(settings) / decode_job / decode_records
# adapters/serpapi     CachingSerpApiClient / CacheStore / cache_age_seconds(...)
# application/jobs     ScanJob
# application/worker   ScanWorker.handle(job)
# application/persistence  save_country / save_summary / archive_raw / _normalized / _curated
# application/scan_service build_scan_summary(...) / maps_targets(...)
# api                  ApiService / api_handler / worker_handler
```

#### 動作モード（既定はすべて外部通信ゼロ）

| 環境変数 | 既定 | 備考 |
|---|---|---|
| `SERPAPI_MODE` | `fixture` | `live` はキャッシュで包まれる |
| `LLM_MODE` | `stub` | 版に `-stub` が付く |
| `PERSISTENCE_MODE` | `memory` | `aws` で DynamoDB / S3 / SQS |
| `VITE_API_MODE` | `mock` | frontend。バックエンド不要 |

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

### C12. 「国の内側」だけでなく「国の外側」も保護する（W4 で判明）

`CountryScanner.scan` は `except Exception` で完全に保護されているが、
**その外側**（QueryProfile の読み込み、ランキング確定後の Maps 取得、
Opportunity Brief の生成）は保護されていなかった。いずれも
「5か国分の完成した成果を1回の失敗で捨てる」構造になっていた。
**新しい処理をスキャンの前後へ足すときは、必ず同じ観点で確認すること。**

### C13. Core Source の `OK` は「取得できたか」ではなく「計算に使えるか」（W4 で判明）

`docs/scoring.md` 6章の `OK` は「下位スコアの計算に使える内容があった」。
Trends は 12 点未満だと Demand を計算できないので `MISSING` にする。
「1点でもあれば OK」にすると、スコアを出せないのに `data_completeness` が
満点になり、**Confidence が正常系より高くなる**。

### C14. 版識別子は実装ごとに変える（W4 で判明）

stub の規則ベース分類と実 LLM の分類は結果が変わる。同じ
`classifier_version` を名乗ると結果を後から再現できない。
`LlmClassifier` / `BriefWriter` は `classifier_version` / `prompt_version`
プロパティを持ち、stub は `-stub` 接尾辞、Anthropic は `prompt_version` に
モデル ID を含める。

### C15. レビュア間の判断の割れは正本で決める（W4 の実例）

「全国が `INSUFFICIENT_EVIDENCE` のときのスキャン status」について、
R2 は「外形障害を検知できないので `PARTIALLY_FAILED`」、R3 は
「`INSUFFICIENT_EVIDENCE` はエラーではないので `COMPLETED`」と割れた。
`docs/scoring.md` 7章の明文（「エラーではない」）を根拠に `COMPLETED` を
採用し、監視の要求はログの指標（`rankable_countries` /
`insufficient_countries` / `failed_countries`）で満たした。
**多数決にしない。**

### C16. 「Cache 動作」は fixture を包まない（W7 で判明）

`CachingSerpApiClient` は **live モードだけ**を包む。fixture を包むと2回目
以降の `cache_age_seconds` が 0 でなくなり、Freshness が実行のたびに変わって
テストとデモの決定性が壊れる。

キャッシュ経過時間は `SourceFetch.cache_age_seconds` へ載せる。ここを 0 の
ままにすると、`docs/scoring.md` の Freshness が「6時間前の結果でも今取得した」
と扱う。**キャッシュを入れるときは Freshness への配線まで含めて1組**である。

### C17. 検証の終了コードをパイプで潰さない（W7 の失敗）

`make verify 2>&1 | tail -4 && git commit` と書くと、パイプの終了コードは
`tail` のものになり、**lint が落ちていてもコミットが進む**。実際に1度
壊れたまま push した。`make verify >/dev/null 2>&1 && ...` のように、
**検証コマンドの終了コードを直接見ること。**

### C18. Terraform と backend の定数は両方直す（W7）

`infrastructure/README.md` に一覧がある。片方だけ変えると壊れる。

- DynamoDB: `PK` / `SK` / `ttl`（`adapters/dynamodb/table.py`）
- S3 のキー配置（`adapters/s3/keys.py`）と Glue のパーティション列
- Lambda のハンドラ名（`api.lambda_handlers.api_handler` / `api.worker_handler.worker_handler`）
- 環境変数名（`config/settings.py`）、`batch_size = 1`、`maxReceiveCount = 3`

### C19. 「無言の失敗」を疑う（W8 の最大の学び）

第三者レビューが見つけた Critical 3件は、いずれも**例外も赤いテストも
出ない**失敗だった。

1. Lambda で QueryProfile が読めず、全国 `FAILED` のスキャンが `completed`
   として保存される（`ConfigError` を握っていたため WARNING 1行だけ）
2. 完了済みスキャンが途中経過で `processing` へ巻き戻り、フロントが永久に
   Polling する（`save_scan` が無条件上書きだったため）
3. DynamoDB のシリアライズが Screen 2 用の5フィールドを落としても、
   1370 件のテストが1つも落ちない（テストのビルダが既定値のままだった）

**共通点**: 「捕捉して既定値へ倒す」設計と、「既定値で作ったテストデータ」の
組み合わせ。**例外を握る箇所を書いたら、その分岐が観測できるかを必ず確認する。**

### C20. テストデータに既定値を使わない

`CountryResult` の新フィールドは既定値（`None` / `[]`）を持つ。テストの
ビルダがそれを埋めないと、**保存時に丸ごと落としても往復テストが通る**。
モデルへフィールドを足したら、テストのビルダにも非既定値を入れること。

### C21. Terraform と backend の定数一致は機械的に検証する

コメントで紐付けても、**Terraform 側だけを変えたときに何も落ちない**。
`backend/tests/unit/integration/test_terraform_constants.py` が `.tf` を
正規表現で読んで突き合わせる。定数を増やしたらここへも足すこと。

### C22. 依存の差し替えはモジュール属性ではなく引数で行う

ローカル開発サーバーは当初 `lambda_handlers.build_service` をモジュールごと
差し替えていた。復元手段が無いため、**同一プロセスの後続処理へ漏れる**。実際に
`test_build_service_uses_the_in_memory_defaults` が「dev サーバー起動後に実行
されると本物の `build_service` を一度も呼ばない」状態になり、緑のまま検証が
無意味になっていた。`api_handler(event, context, *, service=None)` という
キーワード引数の注入点へ変更した。**pytest の収集順に依存して意味が変わる
テストは、赤くならないので気づけない。**

### C23. 開発サーバーの応答は本番ハンドラと同じ経路を通す

`do_PUT` などを定義しないと `http.server` の既定へ落ち、**501 + HTML**（CORS
ヘッダ無し）を返す。本番（API Gateway → `_require_method`）は **405 + JSON**
なので、ローカルで再現できない差異になる。全メソッドを `api_handler` へ流す。

また、上限超過の本文は**切り詰めない**。マルチバイト境界で切ると `decode` が
例外を投げ、応答を返さないまま接続が切れる。読み捨ててから 400 を返す。

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
| 10 | **`ScanOutput.outcomes` が全国分の生レスポンスを保持し続ける。** live では最悪 25 payload × 8MB。S3 へ払い出したら解放する設計にすること | **Phase 7 の着手時** |
| 11 | ソース取得も国の処理も完全に逐次。live では 5国 × 4ソース = 20回の逐次呼び出しになり「5 Country Ranking p50 < 15 sec」を満たせない | Phase 8 |
| 12 | `MISSING` と判定したソースの正規化済みデータを捨てている。`GET /scans/{id}/countries/{c}` は `news_results` を返す契約なので、「日付は無いが実在する記事」を出せない | Phase 9 |
| 13 | `ScanSummary.versions.query_profile_version` は国別の版を連結した文字列。`docs/api.md` に明記済みだが、本来は `ScanSummary` 専用の版モデルを持つほうが素直 | 必要になったら |
| 14 | **キャッシュはプロセス内メモリのみ。** Lambda の実行環境をまたいで共有されない。共有キャッシュ（DynamoDB など）は MVP の範囲外 | 必要になったら |
| 15 | **「最後の1国」判定が競合しうる。** 概要の保存は冪等で、余分に発生するのは Brief の LLM 呼び出し1回。厳密に解くには `ScanRepository` へ条件付き書き込みの追加が必要 | 必要になったら |
| 16 | `CountryScanner` に `fetch_maps` の公開メソッドが無いため、Worker が空の証拠を種に `attach_maps` を呼ぶ迂回をしている（`worker.py` の `_fetch_maps`） | リファクタの機会に |
| 17 | Worker 内の4つの SerpApi 呼び出しが逐次。並列化するときは `submit_with_context` を使うこと（使わないと全ログの4フィールドが `null` になる） | Phase 8 の性能改善 |
| 18 | **Athena / DynamoDB / S3 / SQS / Lambda はいずれも実 AWS では未検証。** `terraform apply` を行わない方針のため | AWS 利用の判断後 |
| 19 | **`SERPAPI_MODE=live` / `LLM_MODE=anthropic` は Secrets Manager からの読み出しが未実装**。Terraform の `validation` で弾いている。実装したら validation を外すこと | live 検証時 |
| 20 | 「最後の1国」判定の競合で、Top2 の Maps 呼び出しが 2回ずつ（計4回）になりうる。概要の巻き戻りと Brief の二重生成は解決済み。厳密に解くには確定処理のリーダー選出が必要 | 必要になったら |
| 21 | 非同期経路では `normalized/` に Maps が含まれない（同期実行とは内容が違う）。`raw/` と `curated/` には残る | Phase 12 の分析時 |
| 22 | Metrics（`scan_duration_ms` など）は未実装。**Performance SLO を測定する手段が無い** | Phase 14 の性能作業 |
| 23 | frontend の mock データ（約5,800行）が本番ビルドにも同梱される（304KB）。動的 import で分離できる | 必要になったら |

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
