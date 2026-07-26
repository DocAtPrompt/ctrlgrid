"""The edge ruler's ladder (§ 8.12) — where the ticks are and what they say.

Kept apart from `frame.py` because two callers need exactly this arithmetic and
must never disagree about it: the drawing and the pre-flight's fit check. Two
copies drift, and a scale that is checked against one arithmetic and drawn with
another is the almost-right sheet of § 5.1.

No marks here and no page: positions along an edge, the strings beside them,
and the width of the strip a ruler needs. Micrometres throughout (§ 3.3), and
each tick is computed from its index rather than from the tick before it — a
*value* is an exact multiple of the step, and a *position* is that value
plus wherever zero sits on the edge (§ 8.12).
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

from ctrlgrid.marks import Um
from ctrlgrid.model import RulerSpec
from ctrlgrid.writers import WriterQuery

#: Tick lengths, measured outward from the pattern edge. Fixed measures the way
#: the cover sheet's figures are fixed (§ 8.8): a yardstick nobody can bend is
#: the point of a yardstick.
SHORT_TICK: Um = 1200
MID_TICK: Um = 2000
LONG_TICK: Um = 3000

#: Between the long tick and its number.
LABEL_GAP: Um = 1000

#: Micrometres per unit of the printed numbers — the one place `unit` acts.
_PER_UNIT: dict[str, int] = {"mm": 1000, "cm": 10_000, "in": 25_400}

TickKind = Literal["short", "mid", "label"]


@dataclass(frozen=True, slots=True)
class Tick:
    """One tick: how far along the edge it sits, and how long it is drawn."""

    at: Um
    """Where the tick is drawn: a distance along the edge from its start."""

    kind: TickKind

    value: Um = 0
    """What the tick *measures*: its signed distance from the scale's zero.
    The two differ as soon as zero is not the edge's start (§ 8.12)."""


def ticks(ruler: RulerSpec, *, extent: Um, zero: Um = 0) -> list[Tick]:
    """Every tick of one edge, the longest kind winning where two ladders meet.

    `zero` is where the scale's nought sits along the edge, and the ladder hangs
    on **it** rather than on the edge's start: with a centred origin the
    labelled ticks have to be symmetric about the middle, or the 0 would fall
    between two of them (§ 8.12). So the walk runs outward from zero in both
    directions and stops at the ends — a tick past the end is not drawn, because
    the scale measures the area it borders and does not run into the corner.
    """
    step = ruler.step.um
    result: list[Tick] = []
    # The lowest multiple of the step that is still *on* the edge. Floor, not
    # ceiling: `-ceil(zero / step)` overshoots by one whenever zero is not a
    # whole number of steps from the edge's start, and puts the first tick a
    # fraction of a step into the corner. With `origin: center` that is the
    # ordinary case rather than a corner one — a 175.5 mm extent put it at
    # −0.25 mm — which is why the docstring above and the drawing disagreed.
    first = -(zero // step)
    last = (extent - zero) // step
    for index in range(first, last + 1):
        offset = index * step                     # exact multiples, never a sum (§ 3.3)
        at = zero + offset
        if offset % ruler.label_every.um == 0:
            kind: TickKind = "label"
        elif ruler.mid_every is not None and offset % ruler.mid_every.um == 0:
            kind = "mid"
        else:
            kind = "short"
        result.append(Tick(at=at, kind=kind, value=offset))
    return result


def tick_length(kind: TickKind) -> Um:
    return {"short": SHORT_TICK, "mid": MID_TICK, "label": LONG_TICK}[kind]


def label_text(ruler: RulerSpec, *, at: Um) -> str:
    """What a number reads — exactly, with the fewest digits that say it, and
    never rounded. `label_every: 25mm` under `unit: cm` prints 2.5, and a scale
    that printed 3 there would be worse than no scale (§ 8.12).

    `at` is the tick's **value**, not its position: past a centred zero it is
    negative, and the minus sign belongs on the sheet.
    """
    value = Decimal(at) / Decimal(_PER_UNIT[ruler.unit])
    return format(value.normalize(), "f")


def number_height(ruler: RulerSpec, *, q: WriterQuery) -> Um:
    """How tall a number is, asked of the writer rather than guessed at.

    The font's ascent, which is at least the height of a digit — measuring is
    what § 10.2 has a query for, and a guessed proportion is precisely the kind
    of almost-right number this project keeps finding in its own bugs.
    """
    ascent, _descent = q.text_metrics(family=ruler.font.token, size=ruler.font.size.um)
    return ascent


def strip_width(ruler: RulerSpec, *, q: WriterQuery) -> Um:
    """The room a ruler needs between the pattern edge and whatever stands next
    to it — the long tick, the gap, and the height of a number."""
    return LONG_TICK + LABEL_GAP + number_height(ruler, q=q)
