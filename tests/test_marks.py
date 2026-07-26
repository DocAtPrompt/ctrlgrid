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
    rotate_180,
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


class TestRotate180:
    """A rigid half turn about the sheet's centre (§ 14).

    Not a mirror, and the difference is the whole reason it exists: `mirror_x`
    refuses to reflect text, because mirrored writing is what nobody wants. A
    half turn *must* carry the text with it — a page number left upright over an
    upside-down grid would be the sheet lying about which way is up.
    """

    W, H = 297_000, 210_000

    def turn(self, mark):
        return rotate_180(mark, width=self.W, height=self.H)

    def test_a_segment_maps_to_the_opposite_corner(self) -> None:
        turned = self.turn(Segment(start=Point(10_000, 20_000), end=Point(30_000, 20_000)))
        assert turned.start == Point(self.W - 10_000, self.H - 20_000)
        assert turned.end == Point(self.W - 30_000, self.H - 20_000)

    def test_turning_twice_is_the_identity(self) -> None:
        # The property that says it is a rotation and not something near one.
        original = Segment(start=Point(1_000, 2_000), end=Point(3_000, 44_000))
        assert self.turn(self.turn(original)) == original

    def test_text_turns_with_the_page(self) -> None:
        text = Text(pos=Point(10_000, 20_000), content="7", size=3_000)
        turned = self.turn(text)
        assert turned.pos == Point(self.W - 10_000, self.H - 20_000)
        assert turned.angle == 180.0
        # Alignment is *not* flipped: a half turn is rigid, so a left-aligned
        # label still starts at its anchor and now runs the other way, which is
        # exactly where the original box lands. Flipping it would move the box.
        assert turned.align == text.align

    def test_an_image_keeps_its_size_and_moves_by_its_far_corner(self) -> None:
        image = Image(pos=Point(10_000, 20_000), width=50_000, height=40_000, source="x.png")
        turned = self.turn(image)
        assert (turned.width, turned.height) == (50_000, 40_000)
        assert turned.pos == Point(self.W - 10_000 - 50_000, self.H - 20_000 - 40_000)

    def test_an_arc_keeps_its_sweep_and_turns_its_start(self) -> None:
        arc = Arc(center=Point(40_000, 50_000), radius=10_000, start_angle=30.0, sweep=90.0)
        turned = self.turn(arc)
        assert turned.center == Point(self.W - 40_000, self.H - 50_000)
        assert turned.sweep == 90.0
        assert turned.start_angle % 360 == 210.0
