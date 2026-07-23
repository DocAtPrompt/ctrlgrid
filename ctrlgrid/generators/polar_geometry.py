"""The polar geometry two blades share (§ 7.6, § 7.11).

§ 7.11 says `mandala` "builds on the same polar geometry as § 7.6". For that to
mean anything, the centre, the outer radius, and the point at a radius and an
angle have to be *one* piece of code, not two that drift. So they live here,
and both `polar` and `mandala` import them.

What is **not** here is the cycle model: § 15.1 is explicit that `mandala` does
not use it. A ring family stepping a base radius by dimensionless multiples is
`polar`'s alone (§ 5.3, § 7.6); `mandala` counts plain sectors and rings. The
shared part is the coordinate arithmetic, nothing above it.

Angles run in micro-degrees for the reason lengths run in micrometres (§ 3.3):
a full turn is the exact integer 360_000_000, so twelve 30° spokes close the
circle instead of ending at 359.999999°.
"""

from __future__ import annotations

import math

from ctrlgrid.marks import Area, Point, Um

FULL_TURN = 360_000_000
PER_DEGREE = 1_000_000


def default_center(area: Area) -> Point:
    """The middle of the pattern area (§ 7.6)."""
    return Point(area.width // 2, area.height // 2)


def default_outer(area: Area) -> Um:
    """Half the shorter side — the largest disc that fits (§ 7.6)."""
    return min(area.width, area.height) // 2


def udeg(degrees: float) -> int:
    return round(degrees * PER_DEGREE)


def polar_point(center: Point, radius: Um, degrees: float) -> Point:
    """A point at `radius` and `degrees`, mathematically positive from the right.

    Computed from the exact angle every time rather than by stepping around the
    circle: § 8.2 forbids accumulated drift, so each point stands on its own
    (§ 3.3, § 3.5).
    """
    radians = math.radians(degrees)
    return Point(
        center.x + round(radius * math.cos(radians)),
        center.y + round(radius * math.sin(radians)),
    )
