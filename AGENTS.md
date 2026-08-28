# AI開発ガイド

## プロジェクト概要

**GapAtlas** — Discover where needs are rising faster than solutions.

「検索需要や困りごとが増加している一方で、検索上で見える解決策が追いついていない地域」をライブWebデータから発見するサービスです。DevNetwork [API + Cloud + AI] Hackathon 2026「SerpApi – Best AI Use Case」向けのMVPを開発します。

要件の正本は[要件定義](docs/requirements.md)です。設計は[アーキテクチャ](docs/architecture.md)、スコア定義は[スコアリング仕様](docs/scoring.md)、方法論の限界は[方法論](docs/methodology.md)を正本とします。

### このプロダクトが主張しないこと

GapAtlasは**社会問題の客観的な深刻度を判定しない**。あくまで **Search-visible unmet-need signal** を発見し、「次に詳しく調査すべき地域」の優先順位を作るツールです。この境界はコード・UI・ドキュメントのすべてで守ります。

## 絶対ルール

依頼書由来の禁止事項です。違反する実装は差し戻します。

- **LLMにスコアを決定させない。** 数値計算はすべてPythonでdeterministicに行う
- **AIは分類と説明にのみ使用する**
- **AIはEvidenceに存在しない事実を断定しない。** URLをLLMに生成させない
- **外部API呼び出しは必ずadapterとして分離する**
- **fixture modeを常に維持する。** `SERPAPI_MODE=fixture` で外部通信ゼロで全機能が動くこと
- **Google Trendsの0〜100値を国同士の絶対需要比較に使わない**（相対指標であるため）
- **Maps件数を実際の供給量として扱わない**
- **ニュースが少ないことを「問題が存在しない」と判断しない**
- 要件を勝手に拡張・変更しない。過剰設計をしない
- 実装途中でも常に起動・テスト可能な状態を維持する
- 不明な重大仕様は推測で実装せず質問する。軽微な実装判断は合理的に進めてよい

## 作らないもの

以下は実装禁止です。

Login / User Account / Payment / Multi Tenant / ECS / EKS / EC2 / RDS / Redis / WebSocket / SSE / Step Functions / Kafka / Elasticsearch / OpenSearch / 200 countries / Multiple Topics / AI Forecast / TAM Calculation

## MVPスコープ

- Topic: **Elder Care のみ**
- Countries: **JP / US / GB / DE / IN の5か国のみ**
- 将来のTopic追加が可能な構造だけ維持し、実装はしない

## アーキテクチャ方針

- Frontend は Cloudflare Pages、Backend/Data Platform は AWS
- API Gateway HTTP API → Lambda API (Python) → SQS → Lambda Worker (Python)
- Lambda は VPC に入れない。NAT Gateway を作らない
- DynamoDB = 最新結果（UI表示用）、S3 + Glue + Athena = 履歴分析
- Athena をWebのリアルタイム表示に使わない
- IaC は Terraform。`terraform apply` は行わない（コード作成と `validate` / `plan` まで）
- Clean Architecture を過剰適用しない。層は `api` / `application` / `domain` / `adapters` / `config` の5つに留める

## ディレクトリごとの役割

| ディレクトリ | 役割 |
|---|---|
| `backend/src/gapatlas/api` | Lambda ハンドラ、HTTPリクエスト/レスポンス変換 |
| `backend/src/gapatlas/application` | ユースケース。スキャンのオーケストレーション |
| `backend/src/gapatlas/domain/models` | Pydanticモデル。全層が共有する凍結契約 |
| `backend/src/gapatlas/domain/scoring` | Need Gap Score / Evidence Confidence の計算。**純粋関数のみ。I/O禁止** |
| `backend/src/gapatlas/adapters/serpapi` | SerpApiクライアントと fixture 実装 |
| `backend/src/gapatlas/adapters/llm` | LLMクライアントと stub 実装 |
| `backend/src/gapatlas/adapters/dynamodb` | DynamoDB読み書き |
| `backend/src/gapatlas/adapters/s3` | S3 raw/normalized/curated 書き込み |
| `backend/src/gapatlas/config` | 設定読み込み、QueryProfileローダー |
| `backend/tests/fixtures` | SerpApiレスポンスのfixture |
| `frontend/src` | React + TypeScript + Vite |
| `infrastructure/terraform` | Terraform |
| `config/query_profiles` | 国別クエリプロファイル(YAML) |
| `docs/` | 仕様書・アーキテクチャ・開発ルール |

## 最初に行うこと

1. `AGENTS.md`（この文書）を読む
2. `docs/index.md` を読む
3. 作業対象に関連する仕様書を読む
4. 関連コードとテストを調査する
5. コード変更前に実装計画を作成する

## 標準ワークフロー

- 機能変更前に[調査ワークフロー](.ai/keep/workflows/analyze.md)を実施する
- 実装前に[実装計画ワークフロー](.ai/keep/workflows/plan.md)に従って計画を作る
- 計画を提示した後、[実装ワークフロー](.ai/keep/workflows/implementation.md)に従って実装と検証を行う
- 実装後に[セルフレビューワークフロー](.ai/keep/workflows/review.md)で依頼と差分を直接比較する
- 統合前に[第三者レビューワークフロー](.ai/keep/workflows/third-party-review.md)を実施する
- 検証結果は[完了報告テンプレート](.ai/keep/templates/completion-report.md)に従い、未実施項目も含めて報告する
- セッションをまたぐ場合は[引き継ぎワークフロー](.ai/keep/workflows/handoff.md)に従って引き継ぎを作る

## ブランチ運用

- ブランチは `main` → `develop` → 作業ブランチの3階層とする
- `main` はリリース済みの状態を保ち、直接コミットしない
- `develop` が統合ブランチであり、作業ブランチのPRは `develop` へ向ける
- 作業ブランチ名は `feature/<内容>`、ドキュメントのみの場合は `docs/<内容>` とする
- 強制pushと履歴の書き換えは行わない

## 複数エージェントでの並行作業

[並行作業ワークフロー](.ai/keep/workflows/parallel-agents.md)を正本とします。要点は次のとおりです。

### 分岐元を揃える

- 作業ブランチは必ず `develop` から切る。分岐前に `git fetch` で最新化する
- 分岐後に `develop` が進んだ場合、統合前に `develop` をマージして解消する

### 担当範囲を分割する

衝突を避けるため、担当範囲をディレクトリ単位で分割する。担当範囲外のファイルを変更しない。

| 担当 | 主なディレクトリ |
|---|---|
| ドメインモデル | `backend/src/gapatlas/domain/models` |
| スコアリング | `backend/src/gapatlas/domain/scoring`, `backend/tests/unit/scoring` |
| SerpApiアダプタ | `backend/src/gapatlas/adapters/serpapi`, `backend/tests/fixtures` |
| LLMアダプタ | `backend/src/gapatlas/adapters/llm` |
| 永続化アダプタ | `backend/src/gapatlas/adapters/{dynamodb,s3}` |
| アプリケーション/API | `backend/src/gapatlas/{application,api}` |
| フロントエンド | `frontend/` |
| インフラ | `infrastructure/` |
| クエリプロファイル | `config/query_profiles` |

### 共有ファイルを直接編集しない

次のファイルは複数のエージェントが変更したくなるため、衝突源になりやすい。作業ブランチでは編集せず、変更が必要な点を完了報告に記載する。統合担当がまとめて反映する。

- `AGENTS.md`
- `CLAUDE.md`
- `README.md`
- `Makefile`
- `backend/pyproject.toml`
- `.env.example`
- `docs/index.md`
- `.ai/keep/` 配下

担当範囲の変更によってこれらの記述が実態と矛盾する場合は、矛盾の内容と修正案を報告する。

### エージェント間で共有される情報

- 他のエージェントが参照できるのは、**Gitで追跡されているファイルのみ**である
- `.ai/temp/` は `.gitignore` の対象であり、git worktree を使用する場合は他のエージェントから参照できない
- 恒久的に共有すべき仕様・ルール・判断は、`docs/` 配下または `.ai/keep/` 配下の追跡ファイルへ記載する

### 他のエージェントへの引き継ぎ

[エージェント引き継ぎ依頼テンプレート](.ai/keep/templates/agent-handoff-request.md)を使用し、引き継ぎ先はこのリポジトリの文脈を持たない前提で記載する。

## コーディング規約

- Python は Ruff(lint/format) と mypy(strict) に従う。設定は `backend/pyproject.toml` を参照する
- TypeScript は ESLint と Prettier に従う。設定は `frontend/` を参照する
- `domain/scoring` は純粋関数のみ。ネットワーク、ファイルI/O、時刻取得、乱数を持ち込まない（時刻は引数で受け取る）
- 外部APIのレスポンスは必ず正規化モデルへ変換してから domain へ渡す。生のdictをdomainへ流さない
- 秘密情報は `.env` にのみ保持し、コードや設定例に実値を書かない
- バージョン識別子（`query_profile_version` / `score_version` / `classifier_version` / `prompt_version`）を結果に必ず含める。再現可能性を最優先する

## テスト方針

- スコアリングは Unit Test 必須。境界値（ゼロ除算、全ゼロ系列、欠損ソース、clip境界）を必ず含める
- LLM分類結果はテストでスタブし、テストを非決定的にしない
- 開発・Unit Test では原則 fixture モードを使用する
- テストを通す目的で既存のアサーションを弱めない

## コマンド一覧

`Makefile` と[開発コマンド](docs/development/commands.md)を参照する。

## 禁止事項

- 秘密情報や認証情報を表示・保存・コミットしない
- SerpApi API key をGitに入れない。ログへAPI keyを書かない
- `terraform apply` を実行しない
- 承認なしで依存ライブラリを追加しない
- 強制pushや履歴を書き換えるGit操作を行わない
- テストを通すためにテスト自体を不正に弱めない
- 型エラーやlintエラーを無視しない
- 個人情報を収集しない

## 基本ルール

- 回答とドキュメントは原則として日本語で記述する。コード内の識別子とコミットメッセージは英語でよい
- 実装前に既存コードを調査する
- 既存の設計・命名・責務分割を尊重する
- 指示されていない仕様追加・リファクタリングを行わない
- 変更範囲を必要最小限にする
- 製品コードを変更した場合はテストを追加または更新する
- 現在未確認のプロジェクト情報は、根拠を確認できるまで「未確認」として扱う
