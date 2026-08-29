"""`ScanRepository` の契約テスト。**全実装へ同じアサーションを適用する。**

`repository` fixture(conftest.py)がインメモリ実装と DynamoDB 実装の両方を
パラメータとして流す。片方だけが満たす振る舞いを契約に紛れ込ませないため、
ここには実装固有の検証を書かない(DynamoDB 固有は
`test_dynamodb_repository.py`)。

`test_memory_repository.py` は凍結されているため、こちらへ契約を集約する。
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from gapatlas.adapters.dynamodb.protocol import ScanRepository
from gapatlas.adapters.llm.stub_client import StubLlmClient
from gapatlas.adapters.serpapi.fixture_client import FixtureSerpApiClient
from gapatlas.application.country_scan import CountryScanner
from gapatlas.config.query_profile_loader import load_query_profile
from gapatlas.domain.models.common import Country, ScanStatus, TopicId

SCAN_TIME = datetime(2026, 8, 28, tzinfo=UTC)


def test_missing_scan_returns_none(repository: ScanRepository):
    """「存在しない」は例外ではなく None(404 は API 層が組み立てる)。"""
    assert repository.get_scan("nope") is None


def test_missing_country_returns_none(repository: ScanRepository):
    assert repository.get_country("nope", Country.JP) is None


def test_list_countries_for_an_unknown_scan_is_empty(repository: ScanRepository):
    assert repository.list_countries("nope") == []


def test_save_and_get_scan_round_trips(repository: ScanRepository, make_summary):
    summary = make_summary()
    repository.save_scan(summary)
    loaded = repository.get_scan("s1")
    assert loaded is not None
    assert loaded.model_dump() == summary.model_dump()


def test_save_and_get_scan_round_trips_with_brief(repository: ScanRepository, make_summary):
    """`opportunity_brief` を含む場合(ネストしたモデル + 文字列リスト)。"""
    summary = make_summary(with_brief=True)
    repository.save_scan(summary)
    loaded = repository.get_scan("s1")
    assert loaded is not None
    assert loaded.model_dump() == summary.model_dump()


def test_save_and_get_country_round_trips(repository: ScanRepository, make_result):
    result = make_result(Country.JP)
    repository.save_country(result)
    loaded = repository.get_country("s1", Country.JP)
    assert loaded is not None
    assert loaded.model_dump() == result.model_dump()


def test_scoreless_country_round_trips(repository: ScanRepository, make_result):
    """`need_gap_score=None` の国も復元できること。"""
    result = make_result(Country.US, score=None)
    repository.save_country(result)
    loaded = repository.get_country("s1", Country.US)
    assert loaded is not None
    assert loaded.need_gap_score is None
    assert loaded.model_dump() == result.model_dump()


def test_saving_the_same_scan_overwrites(repository: ScanRepository, make_summary):
    repository.save_scan(make_summary())
    repository.save_scan(make_summary(with_brief=True))
    loaded = repository.get_scan("s1")
    assert loaded is not None
    assert loaded.opportunity_brief is not None


def test_saving_the_same_key_overwrites(repository: ScanRepository, make_result):
    repository.save_country(make_result(Country.JP, score=75))
    repository.save_country(make_result(Country.JP, score=60))
    loaded = repository.get_country("s1", Country.JP)
    assert loaded is not None
    assert loaded.need_gap_score == 60


def test_list_countries_is_sorted_by_country_code(repository: ScanRepository, make_result):
    for country in (Country.US, Country.JP, Country.DE):
        repository.save_country(make_result(country))
    assert [result.country for result in repository.list_countries("s1")] == [
        Country.DE,
        Country.JP,
        Country.US,
    ]


def test_list_countries_isolates_scans(repository: ScanRepository, make_result):
    repository.save_country(make_result(Country.JP, scan_id="s1"))
    repository.save_country(make_result(Country.US, scan_id="s2"))
    assert [result.country for result in repository.list_countries("s1")] == [Country.JP]
    assert [result.country for result in repository.list_countries("s2")] == [Country.US]


def test_list_countries_excludes_the_scan_summary(
    repository: ScanRepository, make_summary, make_result
):
    """同じ `scan_id` に概要を保存しても、国一覧には現れないこと。"""
    repository.save_scan(make_summary())
    repository.save_country(make_result(Country.JP))
    assert [result.country for result in repository.list_countries("s1")] == [Country.JP]


def test_list_countries_round_trips_full_results(repository: ScanRepository, make_result):
    """一覧で返る項目も単体取得と同じ内容であること。"""
    result = make_result(Country.DE)
    repository.save_country(result)
    listed = repository.list_countries("s1")
    assert [item.model_dump() for item in listed] == [result.model_dump()]


def test_get_scan_does_not_return_country_items(repository: ScanRepository, make_result):
    """国別結果しか無いスキャンで `get_scan` が None を返すこと。"""
    repository.save_country(make_result(Country.JP))
    assert repository.get_scan("s1") is None


def test_get_country_does_not_return_the_summary(repository: ScanRepository, make_summary):
    repository.save_scan(make_summary())
    assert repository.get_country("s1", Country.JP) is None


# --------------------------------------------------------------------------
# 条件付き保存(完了済みスキャンの巻き戻り防止)
# --------------------------------------------------------------------------


def test_an_interim_summary_overwrites_a_processing_scan(repository, make_summary):
    """処理中なら上書きできること(条件が厳しすぎて進捗が止まらないこと)。"""
    repository.save_scan(make_summary(status=ScanStatus.PROCESSING))
    assert repository.save_scan_if_unfinished(make_summary(status=ScanStatus.PROCESSING)) is True
    stored = repository.get_scan("s1")
    assert stored is not None
    assert stored.status is ScanStatus.PROCESSING


def test_an_interim_summary_writes_when_nothing_is_stored(repository, make_summary):
    assert repository.save_scan_if_unfinished(make_summary(status=ScanStatus.PROCESSING)) is True
    assert repository.get_scan("s1") is not None


@pytest.mark.parametrize("finished", [ScanStatus.COMPLETED, ScanStatus.PARTIALLY_FAILED])
def test_an_interim_summary_never_rolls_back_a_finished_scan(repository, make_summary, finished):
    """確定済みを `processing` へ巻き戻さない。

    無条件上書きだと、遅れて着地した途中経過が完了済みのスキャンを
    `processing` へ戻し、ランキングと Brief が失われる。
    """
    repository.save_scan(make_summary(status=finished))
    assert repository.save_scan_if_unfinished(make_summary(status=ScanStatus.PROCESSING)) is False
    stored = repository.get_scan("s1")
    assert stored is not None
    assert stored.status is finished


def test_the_final_summary_always_overwrites(repository, make_summary):
    """確定した概要は無条件で書ける。"""
    repository.save_scan(make_summary(status=ScanStatus.PROCESSING))
    repository.save_scan(make_summary(status=ScanStatus.COMPLETED))
    stored = repository.get_scan("s1")
    assert stored is not None
    assert stored.status is ScanStatus.COMPLETED


def test_a_real_scan_result_round_trips(repository, make_summary):
    """**fixture から作った実結果**が往復すること。

    合成データだけで往復を確かめると、Screen 2 用のフィールドが既定値の
    ままになり、シリアライズがそれらを落としても気づけない。
    """
    scanner = CountryScanner(FixtureSerpApiClient(), StubLlmClient())
    profile = load_query_profile(TopicId.ELDER_CARE, Country.JP)
    scanned = scanner.attach_maps(
        scanner.scan(profile, scan_id="s1", scan_time=SCAN_TIME),
        profile,
        scan_time=SCAN_TIME,
    ).result

    # 中身が空でないことの担保(空だと往復が自明に通ってしまう)
    assert scanned.trends is not None
    assert len(scanned.trends.series) == 3
    assert len(scanned.related_queries) == 12
    assert len(scanned.search_results) == 10
    assert len(scanned.news_results) == 9
    assert scanned.maps_results is not None
    assert len(scanned.maps_results) == 6

    repository.save_country(scanned)
    loaded = repository.get_country("s1", Country.JP)
    assert loaded is not None
    assert loaded.model_dump() == scanned.model_dump()
