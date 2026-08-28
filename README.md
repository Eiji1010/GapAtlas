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
make verify              # lint + 整形確認 + 型チェック + テスト
```

5か国のランキングと Opportunity Brief まで出す場合:

```bash
cd backend && uv run gapatlas scan --topic elder_care --all --mode fixture
```

結果は標準出力へ JSON、ログは標準エラーへ JSON1行で出ます。

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

MVP 実装中。現在の到達点は[要件定義](docs/requirements.md)の Definition of Done を参照してください。
