"""Panels in, cut and fold out — the whole geometry of a net (§ 7.14).

A box style produces **panels**, closed polygons in area-local micrometres, and
nothing else. One rule turns them into marks:

    an edge two panels share is a **fold**;
    an edge only one panel has is a **cut**.

That is the entire cut/fold distinction, and it falls out of the geometry
instead of being maintained by hand — so a new style is a list of panels, never
a traced outline, and no style can trace one wrongly.

The matching is **exact**: positions are integer micrometres (§ 3.3), so two
panels either share an edge or they do not and there is no tolerance to tune.
What that costs is a rule for the styles: every flap spans its attachment edge
completely and tapers only on its free side. A carton is cut that way anyway.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from ctrlgrid.marks import Point

Edge = tuple[Point, Point]


@dataclass(frozen=True, slots=True)
class Panel:
    """One face or flap of a net: a closed polygon, and a name for messages."""

    points: tuple[Point, ...]
    name: str

    def edges(self) -> list[Edge]:
        return [
            (point, self.points[(index + 1) % len(self.points)])
            for index, point in enumerate(self.points)
        ]


def _key(edge: Edge) -> tuple[int, int, int, int]:
    """An edge, direction removed: one panel may walk it either way round."""
    (a, b) = edge
    return min((a.x, a.y), (b.x, b.y)) + max((a.x, a.y), (b.x, b.y))


def edges(panels: Sequence[Panel]) -> tuple[list[Edge], list[Edge]]:
    """`(cuts, folds)` for a whole net.

    The order is the order the panels were given, and within a panel the order
    of its points — so the same net produces the same marks in the same
    sequence, which is what § 10.1 asks of every generator.
    """
    seen: dict[tuple[int, int, int, int], list[tuple[int, Edge, str]]] = {}
    for index, panel in enumerate(panels):
        for edge in panel.edges():
            seen.setdefault(_key(edge), []).append((index, edge, panel.name))

    cuts: list[Edge] = []
    folds: list[Edge] = []
    for entries in seen.values():
        if len(entries) == 1:
            cuts.append(entries[0][1])
        elif len(entries) == 2:
            folds.append(entries[0][1])
        else:
            # Not user input: a style produced it, and a sheet cannot fold three
            # ways along one line. Loud, at the seam, rather than a net that
            # looks plausible and does not close.
            names = ", ".join(sorted(name for _index, _edge, name in entries))
            raise AssertionError(
                f"{len(entries)} panels share one edge ({names}) — a net folds two ways "
                "along a line, not more (§ 7.14)"
            )
    return cuts, folds
