"""`ScanService` のテスト。ランキング整列・Top2 Maps・Top1 Brief。"""

from __future__ import annotations

import shutil
from datetime import UTC, datetime

import pytest
from conftest import (
    SCAN_ID,
    SCAN_TIME,
    TOPIC,
    ExplodingBriefWriter,
    ExplodingSerpApiClient,
    FailingSerpApiClient,
    NullBriefWriter,
    RecordingBriefWriter,
    RecordingSerpApiClient,
    TrendsKillClient,
)

from gapatlas.adapters.llm.errors import LlmRequestError
from gapatlas.adapters.llm.stub_client import StubLlmClient
from gapatlas.adapters.serpapi.fixture_client import FixtureSerpApiClient
from gapatlas.application.scan_service import (
    MAPS_COUNTRY_LIMIT,
    ScanService,
    _ranking_key,
    to_public_component,
)
from gapatlas.config.query_profile_loader import DEFAULT_QUERY_PROFILES_DIR
from gapatlas.domain.models.common import (
    Country,
    CountryStatus,
    ScanStatus,
    SourceName,
    SourceStatus,
)
from gapatlas.domain.models.result import CountryResult, Versions
from gapatlas.domain.models.scores import ConfidenceBreakdown, ScoreComponents

REPO_PROFILES_DIR = DEFAULT_QUERY_PROFILES_DIR


def _make_result(country, *, score, status, confidence) -> CountryResult:
    """ランキングキーの検証用に最小限の `CountryResult` を作る。"""
    return CountryResult(
        scan_id=SCAN_ID,
        topic_id=TOPIC,
        country=country,
        status=status,
        need_gap_score=score,
        confidence=confidence,
        components=ScoreComponents(),
        confidence_breakdown=ConfidenceBreakdown(
            data_completeness=0.0,
            sample_sufficiency=0.0,
            localization_quality=0.0,
            source_agreement=0.0,
            freshness=0.0,
        ),
        versions=Versions(
            query_profile_version="v",
            score_version="v",
            classifier_version="v",
            prompt_version="v",
        ),
        computed_at=datetime(2026, 8, 28, tzinfo=UTC),
    )


def _service(serpapi=None, classifier=None, brief_writer=None):
    return ScanService(
        serpapi or FixtureSerpApiClient(),
        classifier or StubLlmClient(),
        brief_writer or StubLlmClient(),
    )


def _run(service=None, countries=None):
    return (service or _service()).scan(
        TOPIC, countries or list(Country), scan_id=SCAN_ID, scan_time=SCAN_TIME
    )


def test_all_countries_are_scanned():
    output = _run()
    assert set(output.outcomes) == set(Country)
    assert output.summary.status is ScanStatus.COMPLETED
    assert output.summary.progress.total == len(Country)
    assert output.summary.progress.completed == len(Country)


def test_ranking_is_sorted_by_need_gap_score_descending():
    ranking = _run().summary.ranking
    scores = [entry.need_gap_score for entry in ranking if entry.need_gap_score is not None]
    assert scores == sorted(scores, reverse=True)


def test_countries_without_a_score_are_pushed_to_the_end():
    """`need_gap_score` が None の国は末尾へ回す(docs/api.md)。"""
    service = _service(serpapi=FailingSerpApiClient([SourceName.TRENDS]))
    # trends が全国で失敗するので全件 None。順序が国コード昇順で決定的になること
    ranking = _run(service).summary.ranking
    assert all(entry.need_gap_score is None for entry in ranking)
    assert [entry.country for entry in ranking] == sorted(Country, key=lambda c: c.value)


def test_ranking_mixes_scored_and_unscored_countries_correctly():
    output = _run(countries=[Country.JP, Country.US])
    scored = output.summary.ranking
    assert scored[0].need_gap_score is not None
    assert scored[0].need_gap_score >= (scored[1].need_gap_score or 0)


def test_maps_is_fetched_only_for_the_top_two_countries():
    output = _run()
    with_maps = [
        country
        for country, outcome in output.outcomes.items()
        if outcome.result.source_status[SourceName.MAPS] is SourceStatus.OK
    ]
    assert len(with_maps) == MAPS_COUNTRY_LIMIT
    top_two = [entry.country for entry in output.summary.ranking[:MAPS_COUNTRY_LIMIT]]
    assert sorted(with_maps, key=lambda c: c.value) == sorted(top_two, key=lambda c: c.value)


def test_other_countries_have_no_maps():
    output = _run()
    rest = [entry.country for entry in output.summary.ranking[MAPS_COUNTRY_LIMIT:]]
    for country in rest:
        assert output.outcomes[country].evidence.maps_places is None


def test_brief_is_generated_for_the_top_country_only():
    writer = RecordingBriefWriter()
    output = _run(_service(brief_writer=writer))
    assert len(writer.packs) == 1
    assert writer.packs[0].country is output.summary.ranking[0].country
    assert output.summary.opportunity_brief is not None


def test_the_evidence_pack_carries_no_urls():
    """LLM に URL を渡さない・生成させない(AGENTS.md 絶対ルール)。"""
    writer = RecordingBriefWriter()
    _run(_service(brief_writer=writer))
    pack = writer.packs[0]
    for item in pack.evidence:
        assert not hasattr(item, "url")
        assert "http" not in item.summary
    assert pack.limitations


def test_brief_citations_reference_existing_evidence_ids():
    output = _run()
    brief = output.summary.opportunity_brief
    assert brief is not None
    top_country = output.summary.ranking[0].country
    valid = {item.id for item in output.outcomes[top_country].result.evidence}
    assert set(brief.cited_evidence_ids) <= valid
    assert brief.cited_evidence_ids


def test_a_failed_country_marks_the_scan_partially_failed():
    output = _run(_service(serpapi=ExplodingSerpApiClient()))
    assert output.summary.status is ScanStatus.PARTIALLY_FAILED
    assert output.summary.completed_countries == []
    assert output.summary.opportunity_brief is None


def test_versions_join_every_scanned_query_profile():
    versions = _run().summary.versions
    assert versions.query_profile_version.count(",") == len(Country) - 1
    assert "elder-care-jp-v2" in versions.query_profile_version
    assert versions.score_version == "gapatlas-score-v1"


def test_scan_is_deterministic():
    first = _run().summary.model_dump()
    second = _run().summary.model_dump()
    assert first == second


def test_empty_country_list_is_rejected():
    with pytest.raises(ValueError, match="countries"):
        _service().scan(TOPIC, [], scan_id=SCAN_ID, scan_time=SCAN_TIME)


def test_single_country_scan_works():
    output = _run(countries=[Country.DE])
    assert set(output.outcomes) == {Country.DE}
    assert output.summary.ranking[0].country is Country.DE
    assert output.outcomes[Country.DE].result.status is CountryStatus.COMPLETED
    # 1か国でも Top2 の枠内なので Maps を取る
    assert output.outcomes[Country.DE].evidence.maps_places is not None


# --------------------------------------------------------------------------
# 第三者レビューで「定数を書き換えてもテストが通る」と実測された穴を塞ぐ
# --------------------------------------------------------------------------


def test_maps_is_fetched_for_exactly_two_countries():
    """docs/requirements.md「**Top 2 countries** についてのみ取得」。

    期待値に `MAPS_COUNTRY_LIMIT` を使うと自己参照になり、定数を 1 や 3 へ
    変えても通ってしまう。**リテラルで固定する。**
    """
    output = _run()
    with_maps = [
        country
        for country, outcome in output.outcomes.items()
        if outcome.result.source_status[SourceName.MAPS] is SourceStatus.OK
    ]
    assert len(with_maps) == 2
    assert set(with_maps) == {
        output.summary.ranking[0].country,
        output.summary.ranking[1].country,
    }
    assert MAPS_COUNTRY_LIMIT == 2


def test_unscored_countries_are_ranked_after_every_scored_country():
    """`need_gap_score` が None の国は、値を持つ国より必ず後(docs/api.md)。

    全国が None のケースだけでは「末尾へ回す」処理を消しても検出できない。
    **混在させる。**
    """
    service = _service(serpapi=TrendsKillClient([Country.JP, Country.GB]))
    ranking = _run(service).summary.ranking
    scores = [entry.need_gap_score for entry in ranking]
    assert scores[:3] == sorted((score for score in scores if score is not None), reverse=True)
    assert scores[3:] == [None, None]
    assert {entry.country for entry in ranking[3:]} == {Country.JP, Country.GB}


def test_a_zero_score_still_outranks_a_country_without_a_score():
    """`need_gap_score = 0` は有効なスコアであり `None` より上に来る。"""
    scored = _make_result(Country.US, score=0, status=CountryStatus.COMPLETED, confidence=50)
    unscored = _make_result(
        Country.JP, score=None, status=CountryStatus.INSUFFICIENT_EVIDENCE, confidence=69
    )
    assert sorted([unscored, scored], key=_ranking_key) == [scored, unscored]


def test_a_failed_country_ranks_below_an_insufficient_one():
    """`FAILED`(何も返せなかった)は `INSUFFICIENT_EVIDENCE` より後。

    confidence の大小に順序を委ねない(`_failed_outcome` が 0 を入れている、
    という別モジュールの実装詳細へ依存させない)。
    """
    failed = _make_result(Country.US, score=None, status=CountryStatus.FAILED, confidence=90)
    insufficient = _make_result(
        Country.JP, score=None, status=CountryStatus.INSUFFICIENT_EVIDENCE, confidence=10
    )
    assert sorted([failed, insufficient], key=_ranking_key) == [insufficient, failed]


def test_no_brief_or_maps_when_every_country_is_insufficient():
    """ランキング可能な国が無ければ Maps も Brief も作らない。

    `INSUFFICIENT_EVIDENCE` は**ランキングから除外**する(docs/scoring.md 7章)。
    `RANKABLE_STATUSES` にこれを足しても検出できない状態だった。
    """
    service = _service(serpapi=FailingSerpApiClient([SourceName.TRENDS]))
    output = _run(service)
    assert all(
        entry.status is CountryStatus.INSUFFICIENT_EVIDENCE for entry in output.summary.ranking
    )
    assert output.summary.opportunity_brief is None
    assert all(outcome.evidence.maps_places is None for outcome in output.outcomes.values())
    # INSUFFICIENT_EVIDENCE はエラーではないので status は completed のまま
    assert output.summary.status is ScanStatus.COMPLETED


def test_maps_and_brief_skip_insufficient_countries():
    """スコアを出せなかった国を飛ばして、次にランキング可能な国へ回す。"""
    writer = RecordingBriefWriter()
    service = _service(serpapi=TrendsKillClient([Country.JP, Country.DE]), brief_writer=writer)
    output = _run(service)

    rankable = [
        entry.country for entry in output.summary.ranking if entry.status is CountryStatus.COMPLETED
    ]
    assert writer.packs[0].country is rankable[0]
    for country in (Country.JP, Country.DE):
        assert output.outcomes[country].evidence.maps_places is None
    for country in rankable[:2]:
        assert output.outcomes[country].evidence.maps_places is not None


def test_maps_is_fetched_only_after_every_country_has_been_scanned():
    """docs/architecture.md「Maps は5か国のランキング確定後」。

    結果だけを見ると、順序が逆でも通ってしまう。**呼び出し順を固定する。**
    """
    client = RecordingSerpApiClient()
    _run(_service(serpapi=client))
    maps_calls = [index for index, (_, source) in enumerate(client.calls) if source == "maps"]
    core_calls = [index for index, (_, source) in enumerate(client.calls) if source != "maps"]
    assert maps_calls, "Maps が1度も取得されていない"
    assert min(maps_calls) > max(core_calls)


def test_public_components_use_round_half_up():
    """公開表現の丸めは四捨五入。組み込みの `round()`(偶数丸め)は使わない。"""
    assert to_public_component(0.5) == 1
    assert to_public_component(2.5) == 3
    assert to_public_component(64.5) == 65
    assert to_public_component(None) is None


def test_ranking_entry_components_match_the_country_result():
    """ランキングの成分が国別結果の公開表現と一致すること(1 ずれない)。"""
    output = _run()
    for entry in output.summary.ranking:
        evaluation = output.outcomes[entry.country].evaluation
        assert evaluation is not None
        assert entry.demand == evaluation.public_components.demand
        assert entry.pain == evaluation.public_components.pain
        assert entry.solution_gap == evaluation.public_components.solution_gap
        assert entry.news_urgency == evaluation.public_components.news_urgency


# --- Brief 生成の失敗 ---------------------------------------------------------------


@pytest.mark.parametrize(
    "error",
    [RuntimeError("boom"), LlmRequestError("api down"), ValueError("bad pack")],
    ids=["runtime", "llm", "value"],
)
def test_a_failing_brief_writer_does_not_lose_the_country_results(error):
    """Brief 生成の例外で5か国分の完成した結果を捨てない。

    Brief はランキング確定**後**に走るため、ここで例外を通すと 24回の
    SerpApi 呼び出しと全分類の成果が丸ごと失われる。
    """
    output = _run(_service(brief_writer=ExplodingBriefWriter(error)))
    assert output.summary.opportunity_brief is None
    assert len(output.summary.ranking) == len(Country)
    assert all(entry.need_gap_score is not None for entry in output.summary.ranking)


def test_a_brief_writer_returning_none_is_accepted():
    """検証に落ちた Brief は `None`。スキャンは成功のまま。"""
    output = _run(_service(brief_writer=NullBriefWriter()))
    assert output.summary.opportunity_brief is None
    assert output.summary.status is ScanStatus.COMPLETED


# --- QueryProfile の読み込み失敗 ------------------------------------------------------


def test_one_unreadable_profile_does_not_stop_the_other_countries(tmp_path):
    """1か国の YAML が欠けても、残りの国の結果は返す。"""
    profiles_dir = tmp_path / "query_profiles"
    shutil.copytree(REPO_PROFILES_DIR, profiles_dir)
    (profiles_dir / "elder_care" / "GB.yaml").unlink()

    service = ScanService(
        FixtureSerpApiClient(), StubLlmClient(), StubLlmClient(), profiles_dir=profiles_dir
    )
    output = service.scan(TOPIC, list(Country), scan_id=SCAN_ID, scan_time=SCAN_TIME)

    assert output.outcomes[Country.GB].result.status is CountryStatus.FAILED
    assert output.outcomes[Country.GB].result.versions.query_profile_version == "unknown"
    for country in (Country.JP, Country.US, Country.DE, Country.IN):
        assert output.outcomes[country].result.status is CountryStatus.COMPLETED
    assert output.summary.status is ScanStatus.PARTIALLY_FAILED
    assert Country.GB not in output.summary.completed_countries
    assert output.summary.opportunity_brief is not None


# --- enrich ----------------------------------------------------------------------


def test_enrich_false_skips_maps_and_brief():
    """表示しない Maps と Brief のために外部 API を呼ばない。"""
    client = RecordingSerpApiClient()
    writer = RecordingBriefWriter()
    service = ScanService(client, StubLlmClient(), writer)
    output = service.scan(TOPIC, [Country.JP], scan_id=SCAN_ID, scan_time=SCAN_TIME, enrich=False)
    assert output.summary.opportunity_brief is None
    assert writer.packs == []
    assert all(source != "maps" for _, source in client.calls)
    # スコアは通常どおり算出される
    assert output.summary.ranking[0].need_gap_score is not None


# --- 期待値の回帰 -------------------------------------------------------------------


def test_expected_scores_for_every_country():
    """fixture に対する期待値を固定する。

    スコアリング〜統合の回帰をここで捕まえる。値が変わったときは、
    fixture・スコア仕様・統合のどれが変わったのかを必ず確認すること。
    """
    output = _run()
    actual = {
        entry.country.value: (entry.need_gap_score, entry.confidence)
        for entry in output.summary.ranking
    }
    assert actual == {
        "JP": (75, 91),
        "DE": (67, 90),
        "IN": (66, 92),
        "GB": (58, 90),
        "US": (55, 90),
    }
