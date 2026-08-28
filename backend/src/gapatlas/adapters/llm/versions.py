"""分類器とプロンプトのバージョン識別子。

正本は docs/llm-prompts.md「バージョン管理」。

| 変更内容 | 上げるバージョン |
|---|---|
| カテゴリの追加・削除・定義変更 | `CLASSIFIER_VERSION` |
| 分類の後処理・フォールバック規則の変更 | `CLASSIFIER_VERSION` |
| プロンプト文面の変更 | `PROMPT_VERSION` |
| モデル ID の変更 | `PROMPT_VERSION` |

両方を結果(`Versions`)へ記録し、再現可能性を保つ。
"""

from __future__ import annotations

from typing import Final

CLASSIFIER_VERSION: Final[str] = "gapatlas-classifier-v1"
PROMPT_VERSION: Final[str] = "gapatlas-prompt-v1"
