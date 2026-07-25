"""Clipping a segment to the pattern area (§ 8.2), shared by `perspective` and
the slanted families of `lines` (§ 7.1).

The clipper was `perspective`'s and is now everybody's, which is the point:
two of them would drift, and a line that ends a hair outside the area is the
almost-right sheet § 5.1 warns about.
"""

from __future__ import annotations

from ctrlgrid.clip import clip_to_area
from ctrlgrid.marks import Area, Point

AREA = Area(width=100_000, height=100_000)


def test_a_segment_wholly_inside_comes_back_unchanged() -> None:
    a, b = Point(10_000, 10_000), Point(90_000, 20_000)
    assert clip_to_area(a, b, AREA) == (a, b)


def test_a_segment_crossing_two_edges_is_cut_at_both() -> None:
    # A 45° line through the middle, running well past both corners.
    clipped = clip_to_area(Point(-50_000, -50_000), Point(150_000, 150_000), AREA)
    assert clipped == (Point(0, 0), Point(100_000, 100_000))


def test_a_segment_that_misses_the_area_is_not_drawn() -> None:
    assert clip_to_area(Point(-10_000, 50_000), Point(-1000, 50_000), AREA) is None


def test_a_segment_that_only_touches_a_corner_is_not_drawn() -> None:
    # A ray of zero length is not a mark (§ 6).
    assert clip_to_area(Point(-50_000, 50_000), Point(50_000, -50_000), AREA) is None


def test_a_line_along_an_edge_survives() -> None:
    # The bottom edge itself is inside the area: a family's line 0 sits there,
    # and dropping it would silently lose the first line of every grid.
    clipped = clip_to_area(Point(-10_000, 0), Point(110_000, 0), AREA)
    assert clipped == (Point(0, 0), Point(100_000, 0))


def test_each_end_is_rounded_once_from_its_true_position() -> None:
    # § 8.2: exact rationals, so a long ray does not drift on the way in. The
    # slope here is 1/3, and the true entry point at x = 0 is y = 30 000 exactly.
    clipped = clip_to_area(Point(-30_000, 20_000), Point(270_000, 120_000), AREA)
    assert clipped is not None
    assert clipped[0] == Point(0, 30_000)
