"""`Settings.llm_mode` に応じた LLM アダプタの組み立て。

`stub` / `anthropic` の切り替えはここだけで行う(ADR 0002)。分類器は必ず
`CachingLlmClassifier` で包む。同じ入力に同じ結果を返し、同一スキャン内で
同じソースを二度分類しないため。
"""

from __future__ import annotations

from gapatlas.adapters.llm.anthropic_client import AnthropicLlmClient
from gapatlas.adapters.llm.cache import CachingBriefWriter, CachingLlmClassifier
from gapatlas.adapters.llm.protocol import BriefWriter, LlmClassifier
from gapatlas.adapters.llm.stub_client import StubLlmClient
from gapatlas.config.settings import LlmMode, Settings


def create_llm_classifier(settings: Settings) -> LlmClassifier:
    """分類器を作る。キャッシュで包んだものを返す。

    Raises:
        LlmError: `LLM_MODE=anthropic` で API キーが無い、または `anthropic`
            パッケージが未インストールの場合。
    """
    inner: LlmClassifier
    if settings.llm_mode is LlmMode.ANTHROPIC:
        inner = AnthropicLlmClient(settings)
    else:
        inner = StubLlmClient()
    return CachingLlmClassifier(inner)


def create_brief_writer(settings: Settings) -> BriefWriter:
    """Opportunity Brief 生成器を作る。Evidence ハッシュのキャッシュで包む。

    docs/requirements.md「Cache」の `| AI Insight | evidence hash が
    変わるまで |`。Worker の「最後の1国」判定が競合すると確定処理が2回
    走りうるため、同じ根拠なら同じ Brief を返す(実 LLM は決定的でないので、
    キャッシュが無いと2回目が別の文面で上書きする)。

    Raises:
        LlmError: `LLM_MODE=anthropic` で API キーが無い、または `anthropic`
            パッケージが未インストールの場合。
    """
    inner: BriefWriter
    if settings.llm_mode is LlmMode.ANTHROPIC:
        inner = AnthropicLlmClient(settings)
    else:
        inner = StubLlmClient()
    return CachingBriefWriter(inner)
