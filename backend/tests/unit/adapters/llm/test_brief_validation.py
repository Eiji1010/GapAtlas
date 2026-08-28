"""`brief_validation.py` のテスト。

docs/llm-prompts.md「コード側の検証(必須)」の5項目をそれぞれ検証する。
"""

from __future__ import annotations

from gapatlas.adapters.llm.brief_validation import validate_brief
from gapatlas.domain.models.result import OpportunityBrief

DISCLAIMER = (
    "This is a search-visible signal only and does not measure the severity of the problem."
)


def make_brief(**overrides) -> OpportunityBrief:
    values = {
        "why_now": "Demand accelerated [E1].",
        "what_people_are_struggling_with": "Shortage-related queries increased [E2].",
        "visible_solutions": "Few direct providers appeared [E1].",
        "what_this_does_not_prove": DISCLAIMER,
        "next_validation": "Check official statistics, then interview local providers.",
        "cited_evidence_ids": ["E1", "E2"],
    }
    values.update(overrides)
    return OpportunityBrief(**values)


def test_a_valid_brief_is_accepted(pack):
    validated = validate_brief(make_brief(), pack)
    assert validated is not None
    assert validated.why_now == "Demand accelerated [E1]."


# --- 1. 存在しない Evidence ID の引用を除去する ------------------------------------------


def test_unknown_evidence_citation_is_removed(pack):
    brief = make_brief(why_now="Demand accelerated [E1] and something else [E9].")
    validated = validate_brief(brief, pack)
    assert validated is not None
    assert "[E9]" not in validated.why_now
    assert "[E1]" in validated.why_now


def test_a_section_whose_only_citation_is_unknown_is_rejected(pack):
    assert validate_brief(make_brief(why_now="Demand accelerated [E7]."), pack) is None


def test_unknown_citations_do_not_reach_cited_evidence_ids(pack):
    brief = make_brief(next_validation="Look at [E9] again.", cited_evidence_ids=["E1", "E2", "E9"])
    validated = validate_brief(brief, pack)
    assert validated is not None
    assert "E9" not in validated.cited_evidence_ids


# --- 2. 各節に最低1つの Evidence 引用 ---------------------------------------------------


def test_a_section_without_any_citation_is_rejected(pack):
    for field in ("why_now", "what_people_are_struggling_with", "visible_solutions"):
        assert validate_brief(make_brief(**{field: "No citation here."}), pack) is None


def test_next_validation_does_not_need_a_citation(pack):
    brief = make_brief(next_validation="Interview local providers.")
    assert validate_brief(brief, pack) is not None


# --- 3. URL を除去する -----------------------------------------------------------------


def test_urls_are_removed_from_every_section(pack):
    brief = make_brief(
        why_now="Demand accelerated [E1] see https://example.com/a",
        next_validation="Read http://example.org/b for context.",
    )
    validated = validate_brief(brief, pack)
    assert validated is not None
    for section in validated.model_dump().values():
        assert "http://" not in str(section)
        assert "https://" not in str(section)
    assert "[E1]" in validated.why_now


def test_a_section_that_is_only_a_url_is_rejected(pack):
    assert validate_brief(make_brief(why_now="https://example.com/a"), pack) is None


# --- 4. what_this_does_not_prove -------------------------------------------------------


def test_an_empty_disclaimer_is_rejected(pack):
    assert validate_brief(make_brief(what_this_does_not_prove="   "), pack) is None


def test_a_disclaimer_without_a_known_limitation_is_rejected(pack):
    assert validate_brief(make_brief(what_this_does_not_prove="Nothing to add."), pack) is None


def test_a_japanese_disclaimer_is_accepted(pack):
    brief = make_brief(
        what_this_does_not_prove="これは検索上の可視性であり、実際の供給量ではありません。"
    )
    assert validate_brief(brief, pack) is not None


def test_a_disclaimer_that_is_only_a_url_is_rejected(pack):
    assert validate_brief(make_brief(what_this_does_not_prove="https://example.com/"), pack) is None


# --- 5. cited_evidence_ids を再抽出する -------------------------------------------------


def test_cited_evidence_ids_are_re_extracted_from_the_body(pack):
    brief = make_brief(cited_evidence_ids=["E2"])
    validated = validate_brief(brief, pack)
    assert validated is not None
    assert validated.cited_evidence_ids == ["E1", "E2"]


def test_self_reported_ids_that_are_not_in_the_body_are_dropped(pack):
    brief = make_brief(
        what_people_are_struggling_with="Shortage queries increased [E1].",
        cited_evidence_ids=["E1", "E2"],
    )
    validated = validate_brief(brief, pack)
    assert validated is not None
    assert validated.cited_evidence_ids == ["E1"]


def test_cited_evidence_ids_follow_the_evidence_pack_order(make_evidence_pack):
    large = make_evidence_pack(evidence_count=4)
    brief = make_brief(
        why_now="[E4] and [E1].",
        what_people_are_struggling_with="[E3].",
        visible_solutions="[E2].",
        cited_evidence_ids=[],
    )
    validated = validate_brief(brief, large)
    assert validated is not None
    assert validated.cited_evidence_ids == ["E1", "E2", "E3", "E4"]


def test_the_original_brief_is_not_mutated(pack):
    brief = make_brief(why_now="Demand accelerated [E1] [E9].")
    validate_brief(brief, pack)
    assert "[E9]" in brief.why_now
