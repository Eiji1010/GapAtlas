# 開発コマンド

`Makefile` に定義されたコマンドのみを検証に使用します。ここに定義がない検証は「未実施」として扱います。

## セットアップ

```bash
make setup            # backend の依存関係をインストール(uv sync)
make setup-frontend   # frontend の依存関係をインストール(npm install)
```

## 検証

```bash
make verify           # lint + 整形確認 + 型チェック + テスト をまとめて実行
make test             # pytest
make lint             # ruff check
make format           # ruff format(整形を適用)
make format-check     # ruff format --check(整形済みか確認)
make typecheck        # mypy(strict)
```

## 実行

```bash
make scan COUNTRY=JP  # fixture モードで単一国のスキャンを実行し JSON を出力
```

CLI を直接呼ぶと、5か国のランキングと Opportunity Brief まで出せます。

```bash
cd backend
uv run gapatlas scan --topic elder_care --all --mode fixture
uv run gapatlas scan --topic elder_care --country JP --full     # 完全な結果 JSON
uv run gapatlas scan --topic elder_care --country JP --scan-time 2026-08-28T00:00:00Z
```

- **結果は標準出力へ JSON、ログは標準エラーへ JSON1行**で出ます。`... 2>/dev/null | jq` で結果だけを取り出せます
- `--scan-time` を省略すると現在時刻を使います。**fixture の基準日は `2026-08-28T00:00:00Z`** なので、再現性のある出力が要る場合は明示してください

## Terraform

```bash
make tf-validate      # terraform init -backend=false && terraform validate
make tf-plan          # terraform plan
```

`terraform apply` は実行しません。

## 前提

- Python 3.12 以上、`uv`
- Node.js 20 以上、`npm`
- Terraform 1.5 以上

## 環境変数

`.env.example` をコピーして `.env` を作成します。`.env` はGit管理対象外です。

```bash
cp .env.example .env
```

既定は `SERPAPI_MODE=fixture` / `LLM_MODE=stub` / `PERSISTENCE_MODE=memory` です。この状態で外部通信なしに全てのテストとスキャンが動作します。

`PERSISTENCE_MODE=aws` にすると DynamoDB と S3 へ書き込みます。AWS 認証情報と `aws` extra(`make setup` で入ります)が必要です。**保存に失敗してもスキャン自体は完了します**(算出済みの結果を捨てないため)。

`LLM_MODE=anthropic` を使う場合は `anthropic` パッケージが必要です。`make setup` は `uv sync --all-extras` を実行するため通常は入っていますが、未インストールの環境では起動時に `LlmError` になります。
