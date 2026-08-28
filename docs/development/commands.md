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

> **`make scan` はまだ動きません。** `backend/src/gapatlas/cli.py` が未実装のため `ModuleNotFoundError` になります。Phase 6(Country Scan Service)で有効になります。

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

既定は `SERPAPI_MODE=fixture` と `LLM_MODE=stub` です。この状態で外部通信なしに全てのテストが動作します(`make scan` は Phase 6 の CLI 実装後)。

`LLM_MODE=anthropic` を使う場合は `anthropic` パッケージが必要です。`make setup` は `uv sync --all-extras` を実行するため通常は入っていますが、未インストールの環境では起動時に `LlmError` になります。
