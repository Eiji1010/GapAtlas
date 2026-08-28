"""数値の丸めと clip。純粋関数のみ。

docs/scoring.md「公開スコアは 0〜100 の整数。内部では float を保持し、
最終出力時に四捨五入(round half up)する」に対応する。
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal


def round_half_up(value: float) -> int:
    """四捨五入(round half up)して整数にする。

    Python 標準の `round()` は偶数丸め(banker's rounding)で
    `round(0.5) == 0` / `round(2.5) == 2` になるため使わない。この関数は
    `round_half_up(0.5) == 1` / `round_half_up(2.5) == 3` を保証する。

    負値は本仕様(0〜100 のスコア)では発生しないが、定義は
    `decimal.ROUND_HALF_UP` に従い **0 から遠い側へ** 丸める。
    すなわち `round_half_up(-0.5) == -1`、`round_half_up(-2.5) == -3`。

    `float` を `str` 経由で `Decimal` へ変換するのは、2進浮動小数の
    表現誤差ではなく「見えている10進数」を基準に丸めるためである。
    """
    return int(Decimal(str(value)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def clip(value: float, lower: float, upper: float) -> float:
    """`clip(x, lo, hi) = max(lo, min(hi, x))`(docs/scoring.md 記法)。"""
    return max(lower, min(upper, value))
