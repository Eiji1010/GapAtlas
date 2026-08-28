# ADR 0002: LLMプロバイダの選定

- Status: Accepted
- Date: 2026-08-28

## 背景

依頼書のアーキテクチャ図は Lambda Worker から「Bedrock / LLM」を呼ぶ構成になっている。一方、開発環境で Bedrock のモデルアクセス申請と IAM 設定を通す必要があり、fixture 中心の初期開発では検証の障害になる。

## 決定

**Anthropic API を直接呼び出す。** アダプタは `LLM_MODE` で切り替える。

| `LLM_MODE` | 実装 | 用途 |
|---|---|---|
| `stub` | 決定的なスタブ応答 | 単体テスト、fixture 開発 |
| `anthropic` | Anthropic Messages API | 実動作 |

LLM の呼び出しは `backend/src/gapatlas/adapters/llm` の Protocol の背後に隔離する。Bedrock へ切り替える場合、この Protocol の実装を1つ追加するだけで済む。

## 理由

- Bedrock のモデルアクセス有効化はアカウント側の手続きを伴い、開発初期のブロッカーになる
- 依頼書の「外部API呼び出し部分は必ず adapter として分離する」に従えば、プロバイダの差し替えは局所的な変更で済む
- `stub` モードにより、LLM を呼ばずに全ての単体テストが deterministic に通る

## 結果

- 依頼書のアーキテクチャ図から逸脱する。逸脱は[要件定義](../requirements.md)の「依頼書からの逸脱」節に記録する
- API キーは `ANTHROPIC_API_KEY` 環境変数(本番は Secrets Manager)から読む。Git に入れない
- Bedrock へ戻す場合の作業は「`LLMClient` Protocol の Bedrock 実装追加 + IAM ポリシー追加」に限定される
