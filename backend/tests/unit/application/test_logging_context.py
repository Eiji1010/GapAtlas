"""構造化ログのテスト。

docs/architecture.md「Observability」は全ログに `scan_id` / `country` /
`topic` / `source` を含めることを要求する。**API キーが出ないこと**も
併せて確認する(マスクは adapters 側の責務だが、両方のフィルタが同じ
レコードへ適用されることを固定する)。
"""

from __future__ import annotations

import io
import json
import logging
from concurrent.futures import ThreadPoolExecutor

import pytest
from conftest import SCAN_ID, SCAN_TIME

from gapatlas.adapters.llm.stub_client import StubLlmClient
from gapatlas.adapters.serpapi.fixture_client import FixtureSerpApiClient
from gapatlas.application.country_scan import CountryScanner
from gapatlas.application.logging_context import (
    CONTEXT_FIELDS,
    JsonFormatter,
    ScanContextFilter,
    configure_logging,
    current_context,
    log_context,
    submit_with_context,
)
from gapatlas.config.query_profile_loader import load_query_profile
from gapatlas.domain.models.common import Country, TopicId


def _record(message: str = "hello") -> logging.LogRecord:
    return logging.LogRecord("test", logging.INFO, __file__, 1, message, None, None)


def test_context_is_empty_by_default():
    assert current_context() == {}


def test_context_stacks_and_unwinds():
    with log_context(scan_id="s1", topic="elder_care"):
        assert current_context()["scan_id"] == "s1"
        with log_context(country="JP", source="trends"):
            inner = current_context()
            assert inner["scan_id"] == "s1"
            assert inner["country"] == "JP"
        assert "country" not in current_context()
    assert current_context() == {}


def test_none_values_are_ignored():
    with log_context(scan_id="s1", country=None):
        assert "country" not in current_context()


def test_filter_adds_every_context_field():
    record = _record()
    with log_context(scan_id="s1"):
        assert ScanContextFilter().filter(record) is True
    for field in CONTEXT_FIELDS:
        assert hasattr(record, field)
    assert record.scan_id == "s1"
    # 値が無くてもキーは落とさない(「取れていない」ことが分かるように)
    assert record.country is None


def test_json_formatter_emits_one_line_json():
    record = _record()
    with log_context(scan_id="s1", topic="elder_care", country="JP", source="trends"):
        ScanContextFilter().filter(record)
    line = JsonFormatter().format(record)
    assert "\n" not in line
    payload = json.loads(line)
    assert payload["message"] == "hello"
    assert payload["level"] == "INFO"
    assert payload["scan_id"] == "s1"
    assert payload["country"] == "JP"


def test_json_formatter_includes_extra_fields():
    record = _record()
    record.need_gap_score = 75
    line = JsonFormatter().format(record)
    assert json.loads(line)["need_gap_score"] == 75


def test_configure_logging_replaces_existing_handlers():
    stream = io.StringIO()
    root = logging.getLogger()
    previous = list(root.handlers)
    previous_level = root.level
    try:
        configure_logging("INFO", stream=stream)
        assert len(root.handlers) == 1
        logging.getLogger("gapatlas.test").info("configured")
        payload = json.loads(stream.getvalue().strip().splitlines()[-1])
        assert payload["message"] == "configured"
        assert set(CONTEXT_FIELDS) <= set(payload)
    finally:
        for handler in list(root.handlers):
            root.removeHandler(handler)
        for handler in previous:
            root.addHandler(handler)
        root.setLevel(previous_level)


def test_a_real_scan_logs_the_full_context():
    """実際のスキャンで4フィールドが埋まること。"""
    stream = io.StringIO()
    root = logging.getLogger()
    previous = list(root.handlers)
    previous_level = root.level
    try:
        configure_logging("INFO", stream=stream)
        scanner = CountryScanner(FixtureSerpApiClient(), StubLlmClient())
        scanner.scan(
            load_query_profile(TopicId.ELDER_CARE, Country.JP),
            scan_id=SCAN_ID,
            scan_time=SCAN_TIME,
        )
    finally:
        for handler in list(root.handlers):
            root.removeHandler(handler)
        for handler in previous:
            root.addHandler(handler)
        root.setLevel(previous_level)

    lines = [json.loads(line) for line in stream.getvalue().strip().splitlines() if line]
    assert lines, "スキャンが1行もログを出していない"
    completed = [line for line in lines if line["message"] == "country scan completed"]
    assert completed
    assert completed[0]["scan_id"] == SCAN_ID
    assert completed[0]["topic"] == "elder_care"
    assert completed[0]["country"] == "JP"


# --------------------------------------------------------------------------
# 第三者レビューの指摘(root ハンドラでのマスク / スレッド境界)
# --------------------------------------------------------------------------

FAKE_KEY = "root-handler-canary-key"
"""テスト用のダミー値。実キーではない。"""


def _capture(level: str = "INFO"):
    """`configure_logging` を適用し、後で必ず元へ戻すためのヘルパ。"""
    stream = io.StringIO()
    root = logging.getLogger()
    previous_handlers = list(root.handlers)
    previous_level = root.level
    configure_logging(level, stream=stream)

    def restore():
        for handler in list(root.handlers):
            root.removeHandler(handler)
        for handler in previous_handlers:
            root.addHandler(handler)
        root.setLevel(previous_level)

    return stream, restore


def test_the_root_handler_masks_api_keys_from_any_logger():
    """マスクは httpx 専用ではなく、**プロセスが出すログ全体**に効くこと。

    docs/architecture.md「自分が書くログだけでなく、プロセスが出すログ全体に
    対する要件である」。ロガー単位のフィルタだけだと、将来追加される
    ライブラリや自前のロガーが素通りする。
    """
    stream, restore = _capture()
    try:
        logging.getLogger("some.third.party").info(
            "sending https://serpapi.com/search.json?q=x&api_key=%s", FAKE_KEY
        )
    finally:
        restore()
    logged = stream.getvalue()
    assert FAKE_KEY not in logged
    assert "api_key=***" in logged


def test_the_root_handler_masks_api_keys_in_tracebacks():
    """`logger.exception` のトレースバック本文も覆うこと。"""
    stream, restore = _capture()
    try:
        try:
            message = f"failed to reach https://serpapi.com/search.json?api_key={FAKE_KEY}"
            raise RuntimeError(message)
        except RuntimeError:
            logging.getLogger("gapatlas.test").exception("boom")
    finally:
        restore()
    payload = json.loads(stream.getvalue().strip().splitlines()[-1])
    assert FAKE_KEY not in payload["exception"]
    assert "api_key=***" in payload["exception"]


def test_the_root_handler_masks_api_keys_in_extra_fields():
    """`extra=` で渡した文字列も覆うこと。"""
    stream, restore = _capture()
    try:
        logging.getLogger("gapatlas.test").info(
            "fetching", extra={"url": f"https://serpapi.com/search.json?api_key={FAKE_KEY}"}
        )
    finally:
        restore()
    payload = json.loads(stream.getvalue().strip().splitlines()[-1])
    assert FAKE_KEY not in payload["url"]
    assert "api_key=***" in payload["url"]


def test_submit_with_context_carries_the_context_into_a_thread():
    """`ThreadPoolExecutor` のワーカーは親の Context を継承しない。

    素の `executor.submit` を使うと、Phase 8 の並列化で全ログの4フィールドが
    `null` になる(docs/architecture.md「全ログに次を含める」)。
    """
    with ThreadPoolExecutor(max_workers=2) as executor, log_context(scan_id="s1", country="JP"):
        assert submit_with_context(executor, current_context).result() == {
            "scan_id": "s1",
            "country": "JP",
        }
        # 素の submit では伝わらないことも固定する(ヘルパを外したら落ちる)
        assert executor.submit(current_context).result() == {}


def test_submit_with_context_isolates_sibling_tasks():
    """ワーカー間で文脈が混ざらないこと。"""
    results = {}

    def record(name: str) -> None:
        results[name] = dict(current_context())

    with ThreadPoolExecutor(max_workers=2) as executor:
        with log_context(scan_id="s1", country="JP"):
            first = submit_with_context(executor, record, "jp")
        with log_context(scan_id="s1", country="US"):
            second = submit_with_context(executor, record, "us")
        first.result()
        second.result()

    assert results["jp"]["country"] == "JP"
    assert results["us"]["country"] == "US"


@pytest.mark.parametrize(
    "value",
    [
        {"x-api-key": "sk-ant-canary-abcdef"},
        ["sk-ant-canary-abcdef"],
        ("sk-ant-canary-abcdef",),
        {"nested": {"header": "Authorization: Bearer sk-ant-canary-abcdef"}},
    ],
    ids=["dict", "list", "tuple", "nested"],
)
def test_extra_fields_are_masked_even_when_not_strings(value):
    """`extra=` に dict を渡すと JSON へそのまま出るため、中身まで覆う。"""
    stream, restore = _capture()
    try:
        logging.getLogger("gapatlas.test").info("calling", extra={"payload": value})
    finally:
        restore()
    logged = stream.getvalue()
    assert "sk-ant-canary-abcdef" not in logged
    assert "***" in logged
