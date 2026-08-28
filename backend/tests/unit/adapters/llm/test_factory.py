"""`factory.py` のテスト。

`LLM_MODE` による差し替えと、分類器がキャッシュで包まれていることを確認する。
"""

from __future__ import annotations

import pytest
from pydantic import SecretStr

from gapatlas.adapters.llm.cache import CachingLlmClassifier
from gapatlas.adapters.llm.errors import LlmError
from gapatlas.adapters.llm.factory import create_brief_writer, create_llm_classifier
from gapatlas.adapters.llm.stub_client import StubLlmClient
from gapatlas.config.settings import LlmMode, Settings, load_settings

FAKE_API_KEY = "test-anthropic-key-not-real"


def test_default_settings_produce_the_stub_classifier():
    classifier = create_llm_classifier(load_settings(env={}))
    assert isinstance(classifier, CachingLlmClassifier)


def test_the_stub_classifier_is_wrapped_in_the_cache(profile):
    classifier = create_llm_classifier(Settings(llm_mode=LlmMode.STUB))
    assert isinstance(classifier, CachingLlmClassifier)
    assert classifier.classify_rising_queries([], profile) == []


def test_default_settings_produce_the_stub_brief_writer():
    assert isinstance(create_brief_writer(load_settings(env={})), StubLlmClient)


def test_anthropic_mode_without_the_package_or_key_raises_llm_error():
    """API キーが無い状態で anthropic モードを組み立てると LlmError になる。"""
    settings = Settings(llm_mode=LlmMode.STUB, anthropic_api_key=None)
    settings = settings.model_copy(update={"llm_mode": LlmMode.ANTHROPIC})
    with pytest.raises(LlmError):
        create_llm_classifier(settings)
    with pytest.raises(LlmError):
        create_brief_writer(settings)


def test_anthropic_mode_requires_a_key_at_settings_level():
    """`Settings` 側でも資格情報の欠落を弾く(config 層の契約の確認)。"""
    with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
        Settings(llm_mode=LlmMode.ANTHROPIC, anthropic_api_key=None)
    assert (
        Settings(
            llm_mode=LlmMode.ANTHROPIC, anthropic_api_key=SecretStr(FAKE_API_KEY)
        ).anthropic_api_key
        is not None
    )
