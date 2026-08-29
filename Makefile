.DEFAULT_GOAL := help
BACKEND := backend
FRONTEND := frontend

.PHONY: help setup setup-backend setup-frontend test test-backend test-frontend \
        lint lint-backend lint-frontend format format-check format-check-frontend \
        typecheck typecheck-backend typecheck-frontend build verify verify-frontend \
        serve scan tf-validate tf-plan clean

help: ## コマンド一覧を表示する
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

setup: setup-backend ## 依存関係をインストールする

setup-backend: ## backend の依存関係をインストールする
	cd $(BACKEND) && uv sync --all-extras

setup-frontend: ## frontend の依存関係をインストールする
	cd $(FRONTEND) && npm install

test: test-backend ## テストを実行する

test-backend: ## backend のテストを実行する
	cd $(BACKEND) && uv run pytest

test-frontend: ## frontend のテストを実行する
	cd $(FRONTEND) && npm run test

lint: lint-backend ## lint を実行する

lint-backend: ## backend の lint を実行する
	cd $(BACKEND) && uv run ruff check .

lint-frontend: ## frontend の lint を実行する
	cd $(FRONTEND) && npm run lint

format: ## コードを整形する
	cd $(BACKEND) && uv run ruff format .

format-check: ## 整形済みか確認する
	cd $(BACKEND) && uv run ruff format --check .

format-check-frontend: ## frontend が整形済みか確認する
	cd $(FRONTEND) && npm run format:check

typecheck: typecheck-backend ## 型チェックを実行する

typecheck-backend: ## backend の型チェックを実行する
	cd $(BACKEND) && uv run mypy

typecheck-frontend: ## frontend の型チェックを実行する
	cd $(FRONTEND) && npm run typecheck

build: ## frontend をビルドする
	cd $(FRONTEND) && npm run build

verify: lint format-check typecheck test ## backend の lint・整形確認・型チェック・テストをまとめて実行する

verify-frontend: lint-frontend format-check-frontend typecheck-frontend test-frontend build ## frontend の検証をまとめて実行する

serve: ## ローカル開発用の API サーバーを起動する(本番は Lambda)
	cd $(BACKEND) && uv run gapatlas serve --port $(or $(PORT),8000)

scan: ## fixture モードで単一国のスキャンを実行する 例: make scan COUNTRY=JP
	cd $(BACKEND) && uv run gapatlas scan --topic elder_care --country $(or $(COUNTRY),JP) --mode fixture

tf-validate: ## Terraform の構文を検証する
	cd infrastructure/terraform && terraform init -backend=false && terraform validate

tf-plan: ## Terraform の変更計画を表示する(apply はしない)
	cd infrastructure/terraform && terraform plan

clean: ## 生成物を削除する
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	rm -rf $(BACKEND)/.pytest_cache $(BACKEND)/.mypy_cache $(BACKEND)/.ruff_cache
