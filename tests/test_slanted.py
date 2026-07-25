"""Slanted line families (§ 7.1): `direction: 55deg`.

§ 7.1 fixed the semantics long before this was built — `base_spacing`, `offset`
and `extent` are measured **perpendicular** to the line direction, every line is
clipped to the pattern area, and snapping is not supported. What was open was
where line 0 sits, and it sits where it sits for a horizontal family: on the
pattern area's origin. An unlimited family then grows to both sides of it,
which changes nothing for horizontal and vertical, where the whole area lies on
the positive side.
"""

from __future__ import annotations

import math

import pytest
from pydantic import ValidationError

from ctrlgrid.generators.lines import Family, LinesConfig, LinesGenerator
from ctrlgrid.marks import Area, Segment
from ctrlgrid.writers.pdf import PdfWriter

Q = PdfWriter("unused.pdf")
BLADE = LinesGenerator()
A4 = Area(width=170_000, height=257_000)
SQUARE = Area(width=100_000, height=100_000)


def family(**kwargs) -> Family:
    return Family(**{"direction": "horizontal", "base_spacing": "10mm", **kwargs})


def draw(area: Area, **kwargs) -> list[Segment]:
    config = LinesConfig(families=[family(**kwargs)])
    page = next(iter(_contexts()))
    return list(BLADE.generate(config, area=area, page=page, q=Q))


def _contexts():
    from ctrlgrid.pages import page_contexts

    return page_contexts(count=1, snap=())


class TestTheAngle:
    def test_a_degree_direction_validates(self) -> None:
        assert family(direction="55deg").angle_deg == pytest.approx(55.0)

    def test_a_line_has_no_direction_so_the_angle_is_modulo_180(self) -> None:
        assert family(direction="235deg").angle_deg == pytest.approx(55.0)
        assert family(direction="-125deg").angle_deg == pytest.approx(55.0)

    def test_the_two_named_directions_still_work(self) -> None:
        assert family(direction="horizontal").axis == "y"
        assert family(direction="vertical").axis == "x"

    def test_a_slanted_family_has_no_axis_to_be_asked_for(self) -> None:
        # § 8.3 asks a blade for its periodic axes; a slanted family has none,
        # which is how § 7.1's "no snapping" falls out instead of a new rule.
        assert BLADE.periodic_axes(LinesConfig(families=[family(direction="55deg")])) == {}

    def test_a_cartesian_family_still_reports_its_axis(self) -> None:
        axes = BLADE.periodic_axes(LinesConfig(families=[family(direction="horizontal")]))
        assert set(axes) == {"y"}

    def test_governing_on_a_slant_is_refused(self) -> None:
        # Nothing to govern: snapping and leftover placement are per axis, and
        # a slanted family has no axis (§ 7.1, § 8.3).
        with pytest.raises(ValidationError) as excinfo:
            family(direction="55deg", governing=True)
        assert "governing" in str(excinfo.value)

    def test_a_logarithmic_slant_is_refused(self) -> None:
        with pytest.raises(ValidationError) as excinfo:
            family(direction="55deg", law="log10", decades=3)
        message = str(excinfo.value)
        assert "log10" in message and "55deg" in message

    def test_the_describe_line_names_the_angle(self) -> None:
        described = BLADE.describe(LinesConfig(families=[family(direction="55deg")]))
        assert described[0].startswith("55deg")


class TestTheGeneralCaseReproducesTheSpecialOne:
    """The sharpest test there is: 0° and 90° must come out exactly as
    `horizontal` and `vertical` do — same positions, weights, colours, order."""

    def test_zero_degrees_equals_horizontal(self) -> None:
        assert draw(A4, direction="0deg", spacing=[2, 1], weight=[2, 1, 1]) == draw(
            A4, direction="horizontal", spacing=[2, 1], weight=[2, 1, 1]
        )

    def test_ninety_degrees_equals_vertical(self) -> None:
        assert draw(A4, direction="90deg", spacing=[2, 1], weight=[2, 1, 1]) == draw(
            A4, direction="vertical", spacing=[2, 1], weight=[2, 1, 1]
        )


class TestTheGeometry:
    def test_neighbouring_lines_are_base_spacing_apart_perpendicular(self) -> None:
        # § 7.1: `base_spacing` is the *perpendicular* distance. Measured off
        # the drawn endpoints, within the micrometre that § 3.3's integer
        # positions cost — and it does not accumulate: the last line of the
        # sheet is as true as the first.
        segments = draw(A4, direction="55deg", base_spacing="8mm")
        distances = sorted(_perp(s, 55) for s in segments)
        steps = [b - a for a, b in zip(distances, distances[1:], strict=False)]
        assert len(steps) > 30
        assert all(abs(step - 8000) <= 1 for step in steps)
        assert max(abs(d - round(d / 8000) * 8000) for d in distances) <= 1

    def test_a_line_really_runs_at_the_declared_angle(self) -> None:
        # The longest line of the family, so that endpoint rounding — half a
        # micrometre over a quarter metre — cannot hide a wrong slope.
        longest = max(
            draw(A4, direction="55deg", base_spacing="8mm"),
            key=lambda s: (s.end.x - s.start.x) ** 2 + (s.end.y - s.start.y) ** 2,
        )
        angle = math.degrees(
            math.atan2(longest.end.y - longest.start.y, longest.end.x - longest.start.x)
        )
        assert angle == pytest.approx(55.0, abs=0.001)

    def test_both_ends_of_a_line_have_the_same_perpendicular(self) -> None:
        # What makes it a straight line at the right angle, checked per line.
        for segment in draw(A4, direction="35deg", base_spacing="12mm"):
            start = _project_point(segment.start, 35)
            end = _project_point(segment.end, 35)
            assert abs(start - end) <= 1

    def test_every_line_stays_inside_the_pattern_area(self) -> None:
        for segment in draw(A4, direction="35deg", base_spacing="12mm"):
            for point in (segment.start, segment.end):
                assert 0 <= point.x <= A4.width
                assert 0 <= point.y <= A4.height

    def test_line_zero_runs_through_the_origin(self) -> None:
        # On a square, the 45° line through the origin is the diagonal.
        segments = draw(SQUARE, direction="45deg", base_spacing="20mm")
        diagonal = [s for s in segments if abs(_perp(s, 45)) < 1]
        assert len(diagonal) == 1
        ends = {(diagonal[0].start.x, diagonal[0].start.y), (diagonal[0].end.x, diagonal[0].end.y)}
        assert ends == {(0, 0), (100_000, 100_000)}

    def test_it_fills_both_sides_of_line_zero(self) -> None:
        perpendiculars = [
            _perp(s, 45) for s in draw(SQUARE, direction="45deg", base_spacing="20mm")
        ]
        assert min(perpendiculars) < 0 < max(perpendiculars)

    def test_the_cycle_is_symmetric_about_line_zero(self) -> None:
        # [2, 1] going up steps 2 then 1; going down it steps 1 then 2, so the
        # positions mirror. Anything else would shift the pattern by a step.
        perpendiculars = sorted(
            round(_perp(s, 45))
            for s in draw(SQUARE, direction="45deg", base_spacing="10mm", spacing=[2, 1])
        )
        assert 0 in perpendiculars
        assert -10_000 in perpendiculars and 20_000 in perpendiculars

    def test_count_draws_that_many_lines_from_line_zero(self) -> None:
        segments = draw(SQUARE, direction="45deg", base_spacing="10mm", count=3)
        assert len(segments) == 3
        assert all(_perp(s, 45) >= -1 for s in segments)

    def test_an_extent_may_reach_below_line_zero(self) -> None:
        segments = draw(
            SQUARE, direction="45deg", base_spacing="10mm",
            extent={"start": "-30mm", "end": "0mm"},
        )
        assert segments
        assert all(-30_001 <= _perp(s, 45) <= 1 for s in segments)


def _project_point(point, angle_deg: float) -> float:
    """How far a point sits from line 0, along the family's perpendicular."""
    radians = math.radians(angle_deg)
    return -point.x * math.sin(radians) + point.y * math.cos(radians)


def _perp(segment: Segment, angle_deg: float) -> float:
    """The perpendicular coordinate of a drawn line — the quantity
    `base_spacing` is, taken from the drawn endpoints.

    The angle comes from the definition rather than from `atan2` of the
    endpoints: those are integer micrometres (§ 3.3), and an angle estimated
    from them is wrong by about one micrometre over the line's length, which
    turns into tens of micrometres once it is multiplied by the distance from
    the origin. Measuring the drawing with a ruler the drawing itself made is
    what that would be.
    """
    return _project_point(segment.start, angle_deg)
