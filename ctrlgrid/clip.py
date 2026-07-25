"""Clipping a segment to the pattern area — one implementation, shared (§ 8.2).

Liang–Barsky, in exact rationals. It was written for `perspective`'s rays and
lives here because slanted `lines` families need exactly the same cut (§ 7.1):
two clippers would drift, and a grid whose lines end a hair outside the area is
the almost-right sheet § 5.1 warns about.
"""

from __future__ import annotations

from fractions import Fraction

from ctrlgrid.marks import Area, Point


def clip_to_area(a: Point, b: Point, area: Area) -> tuple[Point, Point] | None:
    """The part of segment `a`–`b` inside the area, or None if it never enters.

    Liang–Barsky, in exact rationals so the two clipped ends are each rounded
    once from their true position (§ 8.2 forbids accumulated drift). A segment
    that only touches the boundary at a single point returns None: a ray of zero
    length is not a mark.
    """
    dx, dy = b.x - a.x, b.y - a.y
    limits = (
        (-dx, a.x - 0),  # left:   x >= 0
        (dx, area.width - a.x),  # right:  x <= width
        (-dy, a.y - 0),  # bottom: y >= 0
        (dy, area.height - a.y),  # top:    y <= height
    )
    t0, t1 = Fraction(0), Fraction(1)
    for p, q in limits:
        if p == 0:
            if q < 0:  # parallel to this edge and wholly outside it
                return None
            continue
        r = Fraction(q, p)
        if p < 0:
            if r > t0:
                t0 = r
        else:
            if r < t1:
                t1 = r
    if t0 >= t1:
        return None
    return (
        Point(a.x + round(t0 * dx), a.y + round(t0 * dy)),
        Point(a.x + round(t1 * dx), a.y + round(t1 * dy)),
    )
