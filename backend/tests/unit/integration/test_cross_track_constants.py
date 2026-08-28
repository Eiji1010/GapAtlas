"""トラックをまたいで二重定義されている定数の一致を検証する。

W2 では SerpApi アダプタと domain/scoring を別々のエージェントが並行実装した。
両者は依存関係を持たない設計(adapters が domain/models だけに依存する)のため、
`docs/scoring.md` の同じ定数をそれぞれが自分の層に持っている。
値がずれると Pain Signal が静かに誤るので、ここで一致を固定する。
"""

from __future__ import annotations

from gapatlas.adapters.serpapi.normalize import BREAKOUT_GROWTH_PERCENT
from gapatlas.domain.scoring.constants import (
    BREAKOUT_GROWTH_PERCENT as SCORING_BREAKOUT_GROWTH_PERCENT,
)
from gapatlas.domain.scoring.constants import GROWTH_CAP_PERCENT


def test_breakout_growth_percent_matches_between_adapter_and_scoring():
    """docs/scoring.md の BREAKOUT_GROWTH_PERCENT は 1 つの値である。"""
    assert BREAKOUT_GROWTH_PERCENT == SCORING_BREAKOUT_GROWTH_PERCENT == 5000.0


def test_growth_cap_is_not_below_breakout_value():
    """Breakout 相当値が上限で切られて別の値にならないこと。

    アダプタは "Breakout" を BREAKOUT_GROWTH_PERCENT へ正規化し、scoring は
    GROWTH_CAP_PERCENT で clip する。cap のほうが小さいと Breakout が
    静かに別の値へ潰れる。
    """
    assert GROWTH_CAP_PERCENT >= BREAKOUT_GROWTH_PERCENT
