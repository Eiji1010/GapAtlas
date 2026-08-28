"""LLM アダプタのテストで共有する fixture。

テストは決定的にする。現在時刻・乱数・ネットワークに依存しない。
"""

from __future__ import annotations

import pytest

from gapatlas.adapters.llm.models import BriefComponents, EvidencePack, EvidenceSummary
from gapatlas.domain.models.common import Country, SourceName, TopicId
from gapatlas.domain.models.query_profile import QueryProfile, ReviewStatus, SerpApiParams


def make_profile(
    country: Country = Country.GB, language: str = "en", version: str = "test-profile-v1"
) -> QueryProfile:
    """テスト用の QueryProfile。`config/query_profiles` の実ファイルには依存しない。"""
    return QueryProfile(
        topic_id=TopicId.ELDER_CARE,
        country=country,
        language=language,
        version=version,
        review_status=ReviewStatus.LLM_GENERATED,
        serpapi=SerpApiParams(geo="GB", gl="uk", hl="en", google_domain="google.co.uk"),
        demand_queries=["elderly care"],
        related_query_seed=["elderly care"],
        solution_query=["elderly care services"],
        news_query=["elderly care staff shortage"],
        maps_query=["elderly care"],
        maps_location="@51.5072,-0.1276,12z",
    )


def make_pack(evidence_count: int = 2) -> EvidencePack:
    """テスト用の EvidencePack。"""
    return EvidencePack(
        country=Country.GB,
        topic_id=TopicId.ELDER_CARE,
        need_gap_score=71,
        confidence=64,
        components=BriefComponents(demand=80, pain=70, solution_gap=60, news_urgency=None),
        evidence=[
            EvidenceSummary(
                id=f"E{number}",
                source=SourceName.TRENDS,
                summary=f"observed fact number {number}",
            )
            for number in range(1, evidence_count + 1)
        ],
        limitations=["Solution Coverage は検索上の可視性であり実際の供給量ではない"],
    )


@pytest.fixture
def profile() -> QueryProfile:
    return make_profile()


@pytest.fixture
def make_query_profile():
    """`QueryProfile` を作る関数。国・言語・version を変えたい場合に使う。"""
    return make_profile


@pytest.fixture
def pack() -> EvidencePack:
    return make_pack()


@pytest.fixture
def make_evidence_pack():
    """`EvidencePack` を作る関数。Evidence 件数を変えたい場合に使う。"""
    return make_pack
