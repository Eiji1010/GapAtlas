# ドキュメント索引

GapAtlas の仕様・設計・運用ドキュメントの入口です。AI開発ルールの正本は[AGENTS.md](../AGENTS.md)です。

## 仕様

| 文書 | 内容 |
|---|---|
| [要件定義](requirements.md) | MVPスコープ、機能要件、Definition of Done |
| [スコアリング仕様](scoring.md) | Need Gap Signal Score と Evidence Confidence の計算定義 |
| [方法論と限界](methodology.md) | この指標が何を示し、何を示さないか |
| [アーキテクチャ](architecture.md) | システム構成、データフロー、データモデル |
| [API仕様](api.md) | MVP の4エンドポイント |
| [SerpApi レスポンススキーマ](serpapi-schema.md) | 調査済みのレスポンス構造と未確認事項 |
| [QueryProfile 仕様](query-profiles.md) | 国別クエリ定義のスキーマと制約 |
| [LLM プロンプト仕様](llm-prompts.md) | 分類と Opportunity Brief の契約 |

## 開発

| 文書 | 内容 |
|---|---|
| [開発コマンド](development/commands.md) | 検証・実行コマンドの一覧 |
| [開発ルール](../.ai/keep/rules/development.md) | 変更前調査、テスト、ログ、秘密情報の扱い |

## ワークフロー

| 文書 | 内容 |
|---|---|
| [調査](../.ai/keep/workflows/analyze.md) | 変更前の調査手順 |
| [実装計画](../.ai/keep/workflows/plan.md) | 計画の作り方 |
| [実装](../.ai/keep/workflows/implementation.md) | 実装と検証 |
| [セルフレビュー](../.ai/keep/workflows/review.md) | 依頼と差分の突き合わせ |
| [第三者レビュー](../.ai/keep/workflows/third-party-review.md) | 独立視点でのレビュー |
| [並行作業](../.ai/keep/workflows/parallel-agents.md) | 複数エージェントでのworktree運用 |
| [引き継ぎ](../.ai/keep/workflows/handoff.md) | セッションをまたぐ引き継ぎ |

## 現在の引き継ぎ

[作業引き継ぎ](../.ai/keep/handoff.md) — セッション・マシンをまたぐ現在の状態。作業が進んだら上書き更新する。

## 意思決定記録

| 文書 | 内容 |
|---|---|
| [ADR 0001](decisions/0001-initial-architecture.md) | 初期アーキテクチャ |
| [ADR 0002](decisions/0002-llm-provider.md) | LLMプロバイダの選定 |
| [ADR 0003](decisions/0003-fixture-first.md) | fixture 優先の開発方針 |
