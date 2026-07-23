"""The `perspective` blade (§ 7.11) — M8, and the first blade to compute a
*converging* law instead of a cycle.

Every family so far — cartesian or polar — steps a base value by dimensionless
multiples (§ 5.3). A vanishing-point grid cannot: the ray spacing shrinks
towards the point, and that is its own geometry (§ 5.3 grants it, § 7.11 asks
for it). So this blade uses no `Cycle` at all. What it shares with `polar` is
the *shape* of the seam — own geometry, `supports_snap=False`,
`periodic_axes={}`, a `check` against the pattern area — not the machinery.

The law here is **equal base division** (the choice of § 7.11's two readings):
each vanishing point owns a base edge of the pattern area, that edge is cut
into equal steps, and a ray runs from every step to the point, clipped to the
area. Towards the point the angles crowd together — the receding-floor look.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from ctrlgrid.errors import DefinitionError
from ctrlgrid.generators.perspective import PerspectiveConfig, PerspectiveGenerator
from ctrlgrid.loader import loads
from ctrlgrid.marks import Area, Segment
from ctrlgrid.pages import PageContext, build, preflight
from ctrlgrid.writers.pdf import PdfWriter

AREA = Area(width=100_000, height=80_000)
PAGE = PageContext(index=0, number=1, count=1, name=None, is_even=False, seed_material=b"")
Q = PdfWriter("unused.pdf")


def segments(definition: dict, area: Area = AREA) -> list[Segment]:
    config = PerspectiveConfig.model_validate(definition)
    marks = PerspectiveGenerator().generate(config, area=area, page=PAGE, q=Q)
    return [mark for mark in marks if isinstance(mark, Segment)]


def horizontal(seg: Segment) -> bool:
    return seg.start.y == seg.end.y


def vertical(seg: Segment) -> bool:
    return seg.start.x == seg.end.x


class TestHorizon:
    def test_a_bare_fraction_draws_a_full_width_line(self) -> None:
        # § 7.11: the horizon is a share of the height; a bare number is the
        # shorthand for it. 0.5 of an 80 mm area is 40 mm up, full 100 mm wide.
        line = [seg for seg in segments({"horizon": 0.5}) if horizontal(seg)]
        assert len(line) == 1
        assert (line[0].start.x, line[0].start.y) == (0, 40_000)
        assert (line[0].end.x, line[0].end.y) == (100_000, 40_000)

    def test_it_can_carry_its_own_weight_and_colour(self) -> None:
        line = segments({"horizon": {"at": 0.5, "weight": "0.5pt", "color": "#334466"}})[0]
        assert line.color == "#334466"
        assert line.weight == pytest.approx(0.176, abs=0.01)


class TestTheFan:
    def test_the_base_edge_is_divided_evenly_endpoints_included(self) -> None:
        # A vanishing point above the centre takes the bottom edge (the one
        # farthest from it). Three rays land on y=0 at 0, 50, 100 mm — equal
        # steps, both corners included (§ 7.11).
        rays = segments({"vanishing_points": [{"at": [0.5, 1.5], "count": 3}]})
        feet = sorted(
            seg.start.x if seg.start.y == 0 else seg.end.x
            for seg in rays
            if seg.start.y == 0 or seg.end.y == 0
        )
        assert feet == [0, 50_000, 100_000]

    def test_the_rays_converge_towards_the_point(self) -> None:
        # Feet at x = 0, 50, 100 mm converge to the point at (50, 120). At the
        # top edge (y=80) the outer two have walked in to 100/3 and 200/3 mm,
        # while the middle ray runs straight up — that crowding towards the
        # point is the whole law (§ 7.11).
        rays = segments({"vanishing_points": [{"at": [0.5, 1.5], "count": 3}]})
        tops = sorted(
            seg.start.x if seg.start.y == 80_000 else seg.end.x
            for seg in rays
            if seg.start.y == 80_000 or seg.end.y == 80_000
        )
        assert tops == [33_333, 50_000, 66_667]

    def test_a_horizon_point_takes_the_opposite_side_edge(self) -> None:
        # A point off to the left on the horizon takes the right edge (§ 7.11).
        rays = segments({"vanishing_points": [{"at": [-0.5, 0.5], "count": 3}]})
        rim = sorted(
            seg.start.y if seg.start.x == 100_000 else seg.end.y
            for seg in rays
            if seg.start.x == 100_000 or seg.end.x == 100_000
        )
        assert rim == [0, 40_000, 80_000]

    def test_the_base_edge_can_be_named(self) -> None:
        # Override the default: the same left point, told to use the bottom.
        rays = segments(
            {"vanishing_points": [{"at": [-0.5, 0.5], "count": 3, "base": "bottom"}]}
        )
        # Not every ray survives — the corner ray to (0,0) runs along x<=0 and
        # never enters — but the middle one does, so the fan is not empty.
        assert rays

    def test_two_points_make_a_two_point_grid(self) -> None:
        rays = segments(
            {
                "vanishing_points": [
                    {"at": [-0.5, 0.5], "count": 4},
                    {"at": [1.5, 0.5], "count": 4},
                ]
            }
        )
        # Four rays each, minus any corner ray that grazes the edge.
        assert 6 <= len(rays) <= 8


class TestVerticals:
    def test_they_are_evenly_spaced_full_height_endpoints_included(self) -> None:
        verts = [seg for seg in segments({"verticals": {"count": 5}}) if vertical(seg)]
        xs = sorted(seg.start.x for seg in verts)
        assert xs == [0, 25_000, 50_000, 75_000, 100_000]
        assert all({seg.start.y, seg.end.y} == {0, 80_000} for seg in verts)


class TestValidation:
    def test_a_fan_needs_at_least_two_rays(self) -> None:
        with pytest.raises(ValidationError) as excinfo:
            PerspectiveConfig.model_validate(
                {"vanishing_points": [{"at": [0.5, 1.5], "count": 1}]}
            )
        assert "count" in str(excinfo.value)

    def test_something_has_to_be_drawn(self) -> None:
        with pytest.raises(ValidationError) as excinfo:
            PerspectiveConfig.model_validate({})
        message = str(excinfo.value)
        assert "vanishing_points" in message or "horizon" in message

    def test_a_point_whose_rays_miss_the_area_is_refused(self) -> None:
        # A left point told to divide the left edge: every ray runs along x<=0
        # and only touches the boundary. Nothing to draw — refused before page
        # one (§ 12 point 13), never silently empty.
        config = PerspectiveConfig.model_validate(
            {"vanishing_points": [{"at": [-0.5, 0.5], "count": 3, "base": "left"}]}
        )
        with pytest.raises(DefinitionError) as excinfo:
            PerspectiveGenerator().check(config, area=AREA, q=Q)
        assert "cross" in str(excinfo.value) or "outside" in str(excinfo.value)


class TestTheSeam:
    def test_snapping_is_an_error(self) -> None:
        # § 8.3: a vanishing-point grid has no axis to snap to. An error, not a
        # guess — refused before any geometry is computed.
        with pytest.raises(DefinitionError) as excinfo:
            preflight(
                loads(
                    "version: 1\npattern:\n  snap: cycle\ngenerator: perspective\n"
                    "horizon: 0.5\n",
                    source="test",
                ),
                Q,
            )
        message = str(excinfo.value)
        assert "perspective" in message and "snap" in message

    def test_the_pattern_is_the_same_on_every_page(self) -> None:
        config = PerspectiveConfig.model_validate({"horizon": 0.5})
        assert PerspectiveGenerator().is_page_invariant(config) is True

    def test_there_is_no_period_to_snap_to(self) -> None:
        config = PerspectiveConfig.model_validate({"horizon": 0.5})
        assert PerspectiveGenerator().periodic_axes(config) == {}

    def test_describe_reports_the_points_and_the_horizon(self) -> None:
        config = PerspectiveConfig.model_validate(
            {"horizon": 0.5, "vanishing_points": [{"at": [0.5, 1.5], "count": 12}]}
        )
        described = "\n".join(PerspectiveGenerator().describe(config))
        assert "12" in described and "horizon" in described.lower()


class TestOnTheSheet:
    DEFINITION = (
        "version: 1\n"
        "page:\n  format: a5\n  margin: 10mm\n"
        "generator: perspective\n"
        "horizon: 0.5\n"
        "vanishing_points:\n"
        "  - at: [-0.5, 0.5]\n    count: 8\n"
        "  - at: [1.5, 0.5]\n    count: 8\n"
        "verticals:\n  count: 10\n"
    )

    def test_it_reaches_the_pdf(self, tmp_path: Path) -> None:
        import pdfread

        path = tmp_path / "target.pdf"
        build(loads(self.DEFINITION, source="test"), PdfWriter(path))
        assert pdfread.page_count(path) == 1

    def test_the_horizon_measures_the_full_pattern_width(self, tmp_path: Path) -> None:
        # A5 is 148 mm wide, 10 mm margins each side: a 128 mm pattern area, so
        # the horizon runs the full 128 mm and nothing is scaled (§ 8.2).
        import pdfread

        path = tmp_path / "target.pdf"
        build(loads(self.DEFINITION, source="test"), PdfWriter(path))
        widths = [
            abs(line.x2 - line.x1) for line in pdfread.lines_um(path) if line.is_horizontal
        ]
        assert max(widths) == pytest.approx(128_000, abs=2)

    def test_two_runs_produce_identical_bytes(self, tmp_path: Path) -> None:
        first, second = tmp_path / "a.pdf", tmp_path / "b.pdf"
        for path in (first, second):
            build(loads(self.DEFINITION, source="test"), PdfWriter(path))
        assert first.read_bytes() == second.read_bytes()
