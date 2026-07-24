"""The mark vocabulary and the one place coordinates are shifted (§ 6).

A generator computes in local coordinates with the origin at the bottom left of
the pattern area and knows nothing about margins (§ 3.3). A finished mark
carries sheet coordinates. The move between the two is an addition, and it
happens in exactly one place — so that is the behaviour worth testing.
"""

from __future__ import annotations

import dataclasses

import pytest

from ctrlgrid.marks import (
    Arc,
    Area,
    Dot,
    Image,
    Layer,
    Point,
    Polygon,
    Segment,
    Text,
    mirror_y,
    translate,
)


class TestMirrorY:
    # § 8.5: the vertical counterpart of mirror_x, so a pattern can anchor at the
    # top. Reflects positions about a horizontal line; text is never turned over.
    def test_a_segment_flips_both_ends_in_y(self) -> None:
        seg = Segment(start=Point(1000, 2000), end=Point(4000, 9000))
        flipped = mirror_y(seg, about=10_000)
        assert (flipped.start, flipped.end) == (Point(1000, 8000), Point(4000, 1000))

    def test_text_keeps_its_alignment_and_is_not_turned_over(self) -> None:
        # Upside-down writing is never wanted; only the anchor moves, and a
        # vertical reflection leaves the horizontal alignment alone.
        text = Text(pos=Point(3000, 2000), content="C", size=1000, align="right")
        flipped = mirror_y(text, about=10_000)
        assert flipped.pos == Point(3000, 8000) and flipped.align == "right"

    def test_an_arc_reflects_its_centre_and_angles(self) -> None:
        arc = Arc(center=Point(5000, 3000), radius=1000, start_angle=30.0, sweep=60.0)
        flipped = mirror_y(arc, about=10_000)
        assert flipped.center == Point(5000, 7000)
        assert flipped.start_angle == -90.0 and flipped.sweep == 60.0


class TestLayers:
    def test_the_writer_paints_pattern_then_frame_then_overlay(self) -> None:
        # § 6: marks arrive in layer order and the writer does not sort.
        assert Layer.PATTERN < Layer.FRAME < Layer.OVERLAY


class TestMarksAreImmutable:
    def test_a_segment_cannot_be_changed_after_the_fact(self) -> None:
        segment = Segment(start=Point(0, 0), end=Point(1000, 0))
        with pytest.raises(dataclasses.FrozenInstanceError):
            segment.weight = 2.0  # type: ignore[misc]

    def test_a_mark_is_on_the_pattern_layer_unless_it_says_otherwise(self) -> None:
        # Everything a generator yields is pattern (§ 3.6); the handle supplies
        # frame and overlay explicitly.
        assert Segment(start=Point(0, 0), end=Point(0, 0)).layer is Layer.PATTERN


class TestTranslate:
    """Local pattern coordinates to sheet coordinates — an addition, once."""

    def test_a_segment_moves_at_both_ends(self) -> None:
        moved = translate(Segment(start=Point(0, 0), end=Point(1000, 500)), dx=5000, dy=20000)
        assert (moved.start, moved.end) == (Point(5000, 20000), Point(6000, 20500))

    def test_a_dot_moves(self) -> None:
        moved = translate(Dot(pos=Point(100, 200), diameter=0.3), dx=5000, dy=20000)
        assert moved.pos == Point(5100, 20200)

    def test_an_arc_moves_its_centre_only(self) -> None:
        arc = Arc(center=Point(0, 0), radius=10000, start_angle=0.0, sweep=360.0)
        moved = translate(arc, dx=5000, dy=20000)
        assert moved.center == Point(5000, 20000)
        assert moved.radius == 10000

    def test_a_polygon_moves_every_point(self) -> None:
        polygon = Polygon(points=(Point(0, 0), Point(1000, 0), Point(0, 1000)))
        moved = translate(polygon, dx=10, dy=20)
        assert moved.points == (Point(10, 20), Point(1010, 20), Point(10, 1020))

    def test_text_moves(self) -> None:
        moved = translate(Text(pos=Point(0, 0), content="A1", size=3175), dx=7, dy=8)
        assert moved.pos == Point(7, 8)

    def test_an_image_moves(self) -> None:
        image = Image(pos=Point(0, 0), width=1000, height=1000, source="logo.png")
        assert translate(image, dx=7, dy=8).pos == Point(7, 8)

    def test_everything_else_survives_unchanged(self) -> None:
        segment = Segment(
            start=Point(0, 0), end=Point(1, 0), weight=0.35, color="#4466aa", opacity=0.5
        )
        moved = translate(segment, dx=1, dy=1)
        assert (moved.weight, moved.color, moved.opacity) == (0.35, "#4466aa", 0.5)

    def test_shifting_by_nothing_returns_an_equal_mark(self) -> None:
        segment = Segment(start=Point(3, 4), end=Point(5, 6))
        assert translate(segment, dx=0, dy=0) == segment

    def test_the_shift_stays_integral(self) -> None:
        # Positions are integer micrometres and must not turn into floats on
        # the way out of the generator (§ 3.3, § 8.2).
        moved = translate(Dot(pos=Point(1, 1), diameter=0.3), dx=2, dy=3)
        assert isinstance(moved.pos.x, int) and isinstance(moved.pos.y, int)


class TestArea:
    def test_an_area_is_the_size_of_the_pattern_area_with_the_origin_at_zero(self) -> None:
        area = Area(width=200000, height=250000)
        assert (area.width, area.height) == (200000, 250000)
