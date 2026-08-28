"""`parsing.py` のテスト。

docs/llm-prompts.md「共通のレスポンス規約」の各分岐を確認する。**どのケースでも
入力と同数の結果を返すか、明記した例外になること**が最重要。
"""

from __future__ import annotations

import pytest

from gapatlas.adapters.llm.errors import LlmResponseError
from gapatlas.adapters.llm.parsing import (
    parse_classification_results,
    parse_news_classifications,
    parse_pain_classifications,
    parse_solution_classifications,
)
from gapatlas.domain.models.classification import (
    NewsRelevance,
    PainCategory,
    SolutionCategory,
)


def parse_pain_raw(payload, expected_count=3):
    """`ParsedClassifications` をそのまま返す。"""
    return parse_classification_results(
        payload,
        expected_count=expected_count,
        category=PainCategory,
        default=PainCategory.NEUTRAL,
    )


def parse_pain(payload, expected_count=3):
    """`(category, confidence)` のリストだけを返す。"""
    return parse_pain_raw(payload, expected_count).items


def test_parses_a_well_formed_response():
    payload = {
        "results": [
            {"index": 0, "classification": "SHORTAGE", "confidence": 0.94},
            {"index": 1, "classification": "NEUTRAL", "confidence": 0.61},
            {"index": 2, "classification": "COST", "confidence": 0.5},
        ]
    }
    assert parse_pain(payload) == [
        (PainCategory.SHORTAGE, 0.94),
        (PainCategory.NEUTRAL, 0.61),
        (PainCategory.COST, 0.5),
    ]


def test_accepts_a_json_string_payload():
    payload = '{"results": [{"index": 1, "classification": "COST", "confidence": 0.8}]}'
    assert parse_pain(payload) == [
        (PainCategory.NEUTRAL, 0.0),
        (PainCategory.COST, 0.8),
        (PainCategory.NEUTRAL, 0.0),
    ]


def test_matches_by_index_not_by_order():
    """LLM が順序を入れ替えて返しても `index` で照合する。"""
    payload = {
        "results": [
            {"index": 2, "classification": "COST", "confidence": 0.7},
            {"index": 0, "classification": "ACCESS", "confidence": 0.6},
            {"index": 1, "classification": "QUALITY", "confidence": 0.5},
        ]
    }
    assert parse_pain(payload) == [
        (PainCategory.ACCESS, 0.6),
        (PainCategory.QUALITY, 0.5),
        (PainCategory.COST, 0.7),
    ]


def test_missing_index_is_filled_with_the_default_and_zero_confidence():
    payload = {"results": [{"index": 0, "classification": "SHORTAGE", "confidence": 0.9}]}
    parsed = parse_pain(payload)
    assert len(parsed) == 3
    assert parsed[1] == (PainCategory.NEUTRAL, 0.0)
    assert parsed[2] == (PainCategory.NEUTRAL, 0.0)


def test_duplicate_index_keeps_the_first_entry():
    payload = {
        "results": [
            {"index": 0, "classification": "SHORTAGE", "confidence": 0.9},
            {"index": 0, "classification": "COST", "confidence": 0.1},
        ]
    }
    parsed = parse_pain(payload)
    assert len(parsed) == 3
    assert parsed[0] == (PainCategory.SHORTAGE, 0.9)


@pytest.mark.parametrize("index", [-1, 3, 99])
def test_out_of_range_index_is_ignored(index):
    payload = {"results": [{"index": index, "classification": "COST", "confidence": 0.9}]}
    parsed = parse_pain(payload)
    assert len(parsed) == 3
    assert all(item == (PainCategory.NEUTRAL, 0.0) for item in parsed)


def test_non_integer_index_is_ignored():
    payload = {
        "results": [
            {"index": "0", "classification": "COST", "confidence": 0.9},
            {"index": True, "classification": "COST", "confidence": 0.9},
            {"classification": "COST", "confidence": 0.9},
        ]
    }
    parsed = parse_pain(payload)
    assert len(parsed) == 3
    assert all(item == (PainCategory.NEUTRAL, 0.0) for item in parsed)


def test_unknown_category_falls_back_to_the_default_with_zero_confidence(caplog):
    payload = {"results": [{"index": 0, "classification": "PANIC", "confidence": 0.99}]}
    with caplog.at_level("WARNING"):
        parsed = parse_pain(payload)
    assert parsed[0] == (PainCategory.NEUTRAL, 0.0)
    assert any("unknown" in record.message.lower() for record in caplog.records)


def test_category_value_is_normalized():
    payload = {"results": [{"index": 0, "classification": "  shortage ", "confidence": 0.4}]}
    assert parse_pain(payload)[0] == (PainCategory.SHORTAGE, 0.4)


def test_non_string_category_falls_back_to_the_default():
    payload = {"results": [{"index": 0, "classification": 7, "confidence": 0.4}]}
    assert parse_pain(payload)[0] == (PainCategory.NEUTRAL, 0.0)


@pytest.mark.parametrize(
    ("raw_confidence", "expected"),
    [
        ("high", 0.0),
        (None, 0.0),
        (True, 0.0),
        (-0.5, 0.0),
        (1.5, 1.0),
        (2, 1.0),
        (float("nan"), 0.0),
        (0.25, 0.25),
    ],
)
def test_confidence_is_clipped(raw_confidence, expected):
    payload = {"results": [{"index": 0, "classification": "COST", "confidence": raw_confidence}]}
    assert parse_pain(payload)[0] == (PainCategory.COST, expected)


def test_missing_confidence_key_becomes_zero():
    payload = {"results": [{"index": 0, "classification": "COST"}]}
    assert parse_pain(payload)[0] == (PainCategory.COST, 0.0)


@pytest.mark.parametrize("results", ["not-a-list", 42, {"index": 0}, None])
def test_results_that_is_not_an_array_falls_back_to_defaults(results):
    parsed = parse_pain({"results": results})
    assert len(parsed) == 3
    assert all(item == (PainCategory.NEUTRAL, 0.0) for item in parsed)


def test_missing_results_key_falls_back_to_defaults():
    parsed = parse_pain({"data": []})
    assert len(parsed) == 3
    assert all(item == (PainCategory.NEUTRAL, 0.0) for item in parsed)


def test_entry_that_is_not_an_object_is_ignored():
    payload = {"results": ["SHORTAGE", 3, None]}
    parsed = parse_pain(payload)
    assert len(parsed) == 3
    assert all(item == (PainCategory.NEUTRAL, 0.0) for item in parsed)


def test_top_level_json_array_falls_back_to_defaults():
    """壊れた JSON ではないので例外にしない(既定値で埋める)。"""
    parsed = parse_pain('[{"index": 0, "classification": "COST"}]')
    assert len(parsed) == 3
    assert all(item == (PainCategory.NEUTRAL, 0.0) for item in parsed)


@pytest.mark.parametrize("payload", ["", "{", "not json at all", '{"results": [},'])
def test_broken_json_raises_llm_response_error(payload):
    with pytest.raises(LlmResponseError):
        parse_pain(payload)


def test_zero_and_negative_expected_count_return_empty():
    assert parse_pain({"results": []}, expected_count=0) == []
    assert parse_pain({"results": []}, expected_count=-3) == []


def test_typed_helpers_use_the_documented_defaults():
    """一部だけ欠落した場合は既定値で補完する(例外にしない)。"""
    partial = {"results": [{"index": 0, "classification": "SHORTAGE", "confidence": 0.9}]}
    pain = parse_pain_classifications(partial, 2)
    assert pain[1].classification is PainCategory.NEUTRAL
    assert pain[1].confidence == 0.0

    solution = parse_solution_classifications(
        {"results": [{"index": 0, "classification": "NEWS", "confidence": 0.7}]}, 2
    )
    assert solution[1].classification is SolutionCategory.OTHER

    news = parse_news_classifications(
        {"results": [{"index": 0, "classification": "RELATED", "confidence": 0.7}]}, 2
    )
    assert news[1].classification is NewsRelevance.UNRELATED


def test_typed_helpers_return_the_expected_count():
    payload = {"results": [{"index": 0, "classification": "NEWS", "confidence": 0.7}]}
    parsed = parse_solution_classifications(payload, 4)
    assert len(parsed) == 4
    assert parsed[0].classification is SolutionCategory.NEWS


def test_parsing_does_not_log_the_classified_content(caplog):
    """個人情報混入を避けるため、分類対象の文字列をログへ出さない。"""
    payload = {"results": [{"index": 0, "classification": "MADE_UP", "confidence": 0.4}]}
    with caplog.at_level("WARNING"):
        parse_pain(payload)
    joined = " ".join(record.getMessage() for record in caplog.records)
    assert "MADE_UP" not in joined


# --- 分類の全滅(docs/llm-prompts.md「分類が全滅した場合」) ------------------------------


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"results": []},
        {"results": "not-a-list"},
        {"results": [{"index": 0, "classification": "MADE_UP", "confidence": 0.9}]},
        {"results": [{"index": 99, "classification": "SHORTAGE", "confidence": 0.9}]},
        '{"results": []}',
    ],
    ids=[
        "empty-object",
        "empty-results",
        "results-not-list",
        "unknown-category",
        "out-of-range-index",
        "json-string",
    ],
)
def test_typed_helpers_reject_a_total_fallback(payload):
    """1件も解決できなかった場合は LlmError にする。

    既定値で全件を埋めた結果を返すと `solution_gap = 100`(最大値)が実際の
    観測値としてスコアへ入り、Confidence にも反映されない。
    """
    with pytest.raises(LlmResponseError, match="all"):
        parse_pain_classifications(payload, 3)
    with pytest.raises(LlmResponseError, match="all"):
        parse_solution_classifications(payload, 3)
    with pytest.raises(LlmResponseError, match="all"):
        parse_news_classifications(payload, 3)


def test_partial_fallback_is_not_rejected():
    """一部でも解決できていれば例外にしない(件数は Sample sufficiency で評価する)。"""
    payload = {"results": [{"index": 1, "classification": "COST", "confidence": 0.8}]}
    parsed = parse_pain_classifications(payload, 3)
    assert len(parsed) == 3
    assert parsed[1].classification is PainCategory.COST


def test_empty_input_is_not_a_total_fallback():
    """入力が0件なら「全滅」ではない。"""
    assert parse_pain_classifications({"results": []}, 0) == []


def test_resolved_count_counts_only_llm_resolved_entries():
    payload = {
        "results": [
            {"index": 0, "classification": "SHORTAGE", "confidence": 0.9},
            {"index": 1, "classification": "MADE_UP", "confidence": 0.9},
        ]
    }
    parsed = parse_pain_raw(payload, 3)
    assert parsed.resolved_count == 1
    assert parsed.is_total_fallback is False
