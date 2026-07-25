"""The edge ruler's ladder (§ 8.12) — where the ticks are and what they say.

Kept apart from `frame.py` because two callers need exactly this arithmetic and
must never disagree about it: the drawing and the pre-flight's fit check. Two
copies drift, and a scale that is checked against one arithmetic and drawn with
another is the almost-right sheet of § 5.1.

No marks here and no page: positions along an edge, the strings beside them,
and the width of the strip a ruler needs. Micrometres throughout (§ 3.3), and
the positions are exact multiples of the step rather than a running sum.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

from ctrlgrid.marks import Um
from ctrlgrid.model import RulerSpec

#: Tick lengths, measured outward from the pattern edge. Fixed measures the way
#: the cover sheet's figures are fixed (§ 8.8): a yardstick nobody can bend is
#: the point of a yardstick.
SHORT_TICK: Um = 1200
MID_TICK: Um = 2000
LONG_TICK: Um = 3000

#: Between the long tick and its number.
LABEL_GAP: Um = 1000

#: Cap height as a share of the font size. Digits have no descender, so this is
#: what a number is tall. A proportion and not a measurement: it only reserves
#: space, while the *width* that decides whether two numbers collide is measured
#: by the writer (§ 10.2).
CAP_HEIGHT = (7, 10)

#: Micrometres per unit of the printed numbers — the one place `unit` acts.
_PER_UNIT: dict[str, int] = {"mm": 1000, "cm": 10_000, "in": 25_400}

TickKind = Literal["short", "mid", "label"]


@dataclass(frozen=True, slots=True)
class Tick:
    """One tick: how far along the edge it sits, and how long it is drawn."""

    at: Um
    """Distance from the pattern area's origin, along the edge."""

    kind: TickKind


def ticks(ruler: RulerSpec, *, extent: Um) -> list[Tick]:
    """Every tick from zero to `extent`, the longest kind winning where two
    ladders meet. A tick past the end is not drawn: the scale measures the area
    it borders and does not run into the corner (§ 8.12)."""
    step = ruler.step.um
    result: list[Tick] = []
    for index in range(extent // step + 1):
        at = index * step  # an exact multiple, never accumulated (§ 3.3)
        if at % ruler.label_every.um == 0:
            kind: TickKind = "label"
        elif ruler.mid_every is not None and at % ruler.mid_every.um == 0:
            kind = "mid"
        else:
            kind = "short"
        result.append(Tick(at=at, kind=kind))
    return result


def tick_length(kind: TickKind) -> Um:
    return {"short": SHORT_TICK, "mid": MID_TICK, "label": LONG_TICK}[kind]


def label_text(ruler: RulerSpec, *, at: Um) -> str:
    """What the number at `at` reads — exactly, with the fewest digits that say
    it, and never rounded. `label_every: 25mm` under `unit: cm` prints 2.5, and
    a scale that printed 3 there would be worse than no scale (§ 8.12)."""
    value = Decimal(at) / Decimal(_PER_UNIT[ruler.unit])
    return format(value.normalize(), "f")


def strip_width(ruler: RulerSpec) -> Um:
    """The room a ruler needs between the pattern edge and whatever stands next
    to it — the long tick, the gap, and the height of a digit."""
    numerator, denominator = CAP_HEIGHT
    return LONG_TICK + LABEL_GAP + ruler.font.size.um * numerator // denominator
