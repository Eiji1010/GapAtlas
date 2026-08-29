# GapAtlas

> Discover where needs are rising faster than solutions.

検索需要や困りごとが増加している一方で、**検索上で見える解決策**が追いついていない地域を、ライブWebデータから発見するサービスです。

DevNetwork [API + Cloud + AI] Hackathon 2026 「SerpApi – Best AI Use Case」向けの MVP。

## これは何をするものか

企業の新規事業・事業開発担当が、**「どの国・地域・課題を次に詳しく調査するべきか」** を判断するためのツールです。

5か国(JP / US / GB / DE / IN)の Elder Care について、SerpApi 経由で取得したライブ検索データから2つのスコアを算出します。

| スコア | 意味 |
|---|---|
| **Need Gap Signal Score** (0〜100) | 需要と困りごとの増加に対して、検索上の解決策がどれだけ追いついていないか |
| **Evidence Confidence** (0〜100) | そのシグナルをどれだけ信用してよいか |

この2つを**分離**しているため、「シグナルが弱い」のか「まだ判断材料が足りない」のかを区別できます。

## これは何をしないものか

- 社会問題の客観的な深刻度を判定しない
- 実際のサービス供給量を測定しない
- 市場規模や将来予測を算出しない
- 国同士の絶対的な検索需要を比較しない

詳細は[方法論と限界](docs/methodology.md)を参照してください。

## 設計上の中核

- **LLM にスコアを計算させない。** 数値計算はすべて Python で deterministic に行う。AI は分類と説明にのみ使う
- **AI は Evidence に存在しない事実を断定しない。** 生成文には Evidence ID(`E1` `E2` ...)の引用を必須とし、URL を AI に生成させない
- **fixture mode が既定。** 外部通信ゼロで全機能とテストが動く

## 構成

```text
Cloudflare Pages (React + TypeScript)
        ↓  2秒 Polling
API Gateway HTTP API → Lambda API → SQS → Lambda Worker
                                              ├─ SerpApi
                                              ├─ Anthropic API
                                              ├─ DynamoDB (最新結果)
                                              └─ S3 → Glue → Athena (履歴)
```

詳細は[アーキテクチャ](docs/architecture.md)。

## セットアップ

```bash
cp .env.example .env
make setup
```

既定は `SERPAPI_MODE=fixture` / `LLM_MODE=stub` です。この状態で外部APIキーなしに動作します。

## 実行

```bash
make scan COUNTRY=JP     # fixture モードで単一国を分析し JSON を出力
make serve               # ローカル API サーバーを起動(http://localhost:8000/api/v1)
make verify              # lint + 整形確認 + 型チェック + テスト
```

5か国のランキングと Opportunity Brief まで出す場合:

```bash
cd backend && uv run gapatlas scan --topic elder_care --all --mode fixture
```

結果は標準出力へ JSON、ログは標準エラーへ JSON1行で出ます。

### デモ手順

**外部APIキー無し・AWS 無しで最初から最後まで動きます。**

```bash
# 1. 依存を入れる
make setup && make setup-frontend

# 2. バックエンドの検証(lint / 整形 / 型 / テスト)
make verify

# 3. 5か国のスキャンを CLI で通す
cd backend && uv run gapatlas scan --topic elder_care --all --mode fixture 2>/dev/null

# 4. 画面を開く(既定はモックモードなのでバックエンド不要)
cd frontend && npm run dev
```

画面をバックエンドに繋ぐ場合は、**ターミナルを2つ**使います。

```bash
# ターミナル1: API + Worker を1プロセスで起動する
make serve

# ターミナル2: 画面を live モードで開く
cd frontend && VITE_API_MODE=live npm run dev
```

`make serve` は本番の Lambda ハンドラをそのまま `http.server` で包んだ**開発用**の
サーバーです(`backend/src/gapatlas/api/dev_server.py`)。SQS の代わりにインメモリの
キューを使い、バックグラウンドスレッドが**1国ずつ**処理するため、画面の2秒 Polling で
進捗が進む様子もそのまま再現できます。認証・レート制限・並列処理はありません。

CLI の出力（fixture に対する値。テストで固定しています）:

| 国 | Need Gap | Confidence |
|---|---:|---:|
| JP | 75 | 91 |
| DE | 67 | 90 |
| IN | 66 | 92 |
| GB | 58 | 90 |
| US | 55 | 90 |

Top 2（JP・DE）に Maps の Local Evidence、Top 1（JP）に Opportunity Brief が付きます。

### 動作モード

| 環境変数 | 既定 | 意味 |
|---|---|---|
| `SERPAPI_MODE` | `fixture` | `fixture` は保存済みレスポンス、`live` は SerpApi を実際に呼ぶ |
| `LLM_MODE` | `stub` | `stub` は決定的な規則ベース分類、`anthropic` は Anthropic API |
| `PERSISTENCE_MODE` | `memory` | `memory` はプロセス内、`aws` は DynamoDB と S3 |
| `VITE_API_MODE`（frontend） | `mock` | `mock` はバックエンド不要、`live` は API を呼ぶ |

**既定はすべて外部通信ゼロ**です。`live` / `anthropic` / `aws` は実装済みですが、
API キーと AWS 認証情報が無いため**未検証**です（[ADR 0003](docs/decisions/0003-fixture-first.md)）。

## ドキュメント

[docs/index.md](docs/index.md) が入口です。

| 文書 | 内容 |
|---|---|
| [要件定義](docs/requirements.md) | MVPスコープと Definition of Done |
| [スコアリング仕様](docs/scoring.md) | スコア計算の正本 |
| [方法論と限界](docs/methodology.md) | 何を示し、何を示さないか |
| [アーキテクチャ](docs/architecture.md) | システム構成とデータフロー |
| [API仕様](docs/api.md) | 4エンドポイント |
| [SerpApi スキーマ](docs/serpapi-schema.md) | 調査済みのレスポンス構造 |
| [QueryProfile 仕様](docs/query-profiles.md) | 国別クエリ定義 |
| [LLM プロンプト仕様](docs/llm-prompts.md) | 分類と Opportunity Brief の契約 |

AI エージェントで開発する場合は [AGENTS.md](AGENTS.md) を先に読んでください。

## 状態

MVP の実装は Phase 1〜15 まで一巡しています。

| 層 | 状態 |
|---|---|
| ドメインモデル / スコアリング / Confidence | 実装済み・テスト済み |
| SerpApi アダプタ（fixture / live）とキャッシュ | fixture 検証済み、**live は未検証** |
| LLM アダプタ（stub / Anthropic） | stub 検証済み、**Anthropic は未検証** |
| application 層 + CLI | 実装済み・E2E テスト済み |
| 永続化（DynamoDB / S3）と Athena | 実装済み、**実 AWS では未検証** |
| 非同期（SQS + Worker）と API 4本 | 実装済み・E2E テスト済み |
| Frontend（3画面） | 実装済み・テスト済み |
| Terraform | `validate` まで。**`apply` はしない** |

**未検証の範囲**は [ADR 0002](docs/decisions/0002-llm-provider.md) /
[ADR 0003](docs/decisions/0003-fixture-first.md) と
[要件定義の逸脱表](docs/requirements.md#依頼書からの逸脱)に記録しています。
現在の到達点と持ち越し課題は[作業引き継ぎ](.ai/keep/handoff.md)が正本です。
