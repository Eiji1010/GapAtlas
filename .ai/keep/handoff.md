# 作業引き継ぎ: GapAtlas MVP 実装

この文書は**マシンをまたぐ引き継ぎ**のため Git 追跡ファイルとして置いています（`.ai/temp/` は worktree もマシンもまたげません）。作業が進んだら**上書き更新**してください。履歴は Git が持ちます。

- 最終更新: 2026-08-28
- 対象ブランチ: `develop`
- Remote: `git@github.com:Eiji1010/GapAtlas.git`

## 作業目的

`gapatlas_claude_implementation_prompt.md`（ハッカソン向け実装依頼書）に基づく GapAtlas MVP の実装。要件の正本は[要件定義](../../docs/requirements.md)へ転記済みです。**依頼書の原本はリポジトリ外**（`~/Downloads/gapatlas_claude_implementation_prompt.md`）にあるため、別マシンで作業する場合は `docs/requirements.md` を正本として扱ってください。

## 次のセッションで最初に確認すること

1. `AGENTS.md`
2. `docs/index.md`
3. この引き継ぎ
4. `git log --oneline` と `git status`
5. 関連コードとテスト

## 確定した方針（ユーザー確認済み）

| 論点 | 決定 | 記録 |
|---|---|---|
| LLM プロバイダ | **Anthropic API 直接**（Bedrock ではない）。`LLM_MODE=stub\|anthropic` | [ADR 0002](../../docs/decisions/0002-llm-provider.md) |
| AWS デプロイ | **Terraform コード作成と `validate`/`plan` まで。`apply` はしない** | [要件定義](../../docs/requirements.md)の逸脱表 |
| SerpApi | **APIキー未取得。完全 fixture で進める**。live 実装は書くが未検証 | [ADR 0003](../../docs/decisions/0003-fixture-first.md) |
| 開発体制 | git worktree 上の複数エージェント並列 + 第三者視点レビュー | [並行作業](workflows/parallel-agents.md) / [第三者レビュー](workflows/third-party-review.md) |

## 開発の進め方（Wave 方式）

依存関係のある作業を同時に走らせると下流が壊れるため、Wave に分けています。

| Wave | 内容 | 状態 |
|---|---|---|
| W0 | リポジトリ基盤 + 仕様ドキュメント一式 | 完了 |
| W1 | Phase 2 ドメインモデル（凍結契約） / SerpApi fixture 作成 | （更新すること） |
| W2 | Phase 3 SerpApiアダプタ / Phase 4+5 Scoring+Confidence / LLMアダプタ+分類 | 未着手 |
| W3 | 統合 → CLI E2E（`make scan COUNTRY=JP`） | 未着手 |
| W4 | 第三者レビュー（仕様適合 / セキュリティ・信頼性 / 数値独立検証） | 未着手 |
| W5+ | Phase 6〜15 | 未着手 |

**Phase 4 到達時点の完了条件**（依頼書 §31）:

```bash
make scan COUNTRY=JP
```

で次の形の JSON が出ること。値は fixture の内容に応じて変わってよい。

```json
{ "country": "JP", "topic": "elder_care", "demand": 0, "pain": 0,
  "solution_gap": 0, "news_urgency": 0, "need_gap_score": 0, "confidence": 0 }
```

## 重要な技術的判断（会話だけに残さないため記録）

### C1. ドメインモデルは並列化しない

全トラックの共通依存であるため、W1 で単独確定させてから W2 を並列起動します。W2 実行中にモデルを変更しないでください。

### C2. Google Trends の 0〜100 は相対値

国間の絶対需要比較に使えません。Demand Momentum は**変化率のみ**から算出しています。詳細は[方法論](../../docs/methodology.md)。

### C3. Scoring と Confidence は同一エージェントが担当する

`INSUFFICIENT_EVIDENCE` と「Trends失敗→スコア非表示」の状態遷移が両方に跨るため、分割すると境界がズレます。

### C4. LLM の非決定性をスコアへ漏らさない

分類結果は入力ハッシュでキャッシュし、単体テストでは常に stub を使います。

### C5. fixture の品質がテストの品質

[SerpApi スキーマ](../../docs/serpapi-schema.md)で「確認済み」とされた構造のみに依存します。「未確認」項目に依存する実装を書かないでください。

### C6. 共有ファイルは統合担当だけが編集する

`AGENTS.md` / `CLAUDE.md` / `README.md` / `Makefile` / `backend/pyproject.toml` / `.env.example` / `docs/` 配下 / `.ai/keep/` 配下。並列エージェントは変更要望を完了報告に書きます。

## SerpApi 調査で判明した、実装に直結する事実

いずれも公式ドキュメントで確認済み。詳細は[SerpApi スキーマ](../../docs/serpapi-schema.md)。

1. **RELATED_QUERIES は1リクエスト1クエリのみ**（TIMESERIES と違いカンマ区切り不可）→ `related_query_seed` はちょうど1件に制約
2. **Google News に `snippet` が存在しない** → 関連性分類は `title` + `source.name` のみ
3. **Google News の `date` は絶対表記**、`iso_date`(ISO8601 UTC) が併記される → recency は `iso_date` を使う
4. **rising の `value` は `"+4,500%"` / `"Breakout"` / 未文書の `"Record"` を取りうる** → `extracted_value` を主とし防御的にパースする
5. Google Trends に `gl` / `google_domain` は無い。地域指定は `geo` のみ
6. 英国は `geo: GB` だが `gl: uk`

## 未確認事項（推測で実装しないこと）

- TIMESERIES に複数キーワードを渡したときの `values` 配列の完全な構造
- `rising[].value` に `"Record"` が実際に出るか
- Google News の `stories` ネストの発生条件とキー構造
- Maps の `search_metadata` の Maps 固有キー
- **上記はすべて SerpApi キー取得後に実データで再検証が必要**（[SerpApi スキーマ](../../docs/serpapi-schema.md)末尾のチェックリスト）

## 秘密情報について

- SerpApi / Anthropic の API キーはリポジトリに存在しません
- `.env` は `.gitignore` 済み。`.env.example` にはプレースホルダーのみ
- 別マシンで作業する場合は `cp .env.example .env` から始めてください

## 注意事項

- `main` へ直接コミットしない。統合ブランチは `develop`
- 強制push・履歴書き換えをしない
- `terraform apply` を実行しない
- テストを通すためにアサーションを弱めない
