"""The `mandala` blade (§ 7.11) — M8, and the second blade to build on the
polar geometry of § 7.6.

A mandala is a *template to draw on*, not a finished drawing: concentric guide
rings, N radial divisions, and a small set of parametric motif families whose
whole point is to lay down the N-fold (dihedral) symmetry. The motif is not a
user-drawn shape language (§ 2) — it is built-in elements the user
parameterises: a rosette of overlapping circles and inscribed regular / star
polygons, the two that need `Arc` and `Polygon` respectively (§ 7.11).

The scaffold reuses the polar geometry of § 7.6 — centre, outer radius, the
point at a radius and an angle — but *not* the cycle model (§ 15.1): sectors
and rings are plain counts, not a base value times dimensionless multiples.
"""

from __future__ import annotations

import math
from pathlib import Path

import pytest
from pydantic import ValidationError

from ctrlgrid.errors import DefinitionError
from ctrlgrid.generators.mandala import MandalaConfig, MandalaGenerator
from ctrlgrid.loader import loads
from ctrlgrid.marks import Arc, Area, Polygon, Segment
from ctrlgrid.pages import PageContext, build, preflight
from ctrlgrid.writers.pdf import PdfWriter

AREA = Area(width=100_000, height=80_000)  # centre (50, 40) mm, outer radius 40 mm
PAGE = PageContext(index=0, number=1, count=1, name=None, is_even=False, seed_material=b"")
Q = PdfWriter("unused.pdf")


def marks(definition: dict, area: Area = AREA) -> list:
    config = MandalaConfig.model_validate(definition)
    return list(MandalaGenerator().generate(config, area=area, page=PAGE, q=Q))


def arcs(definition: dict, area: Area = AREA) -> list[Arc]:
    return [m for m in marks(definition, area) if isinstance(m, Arc)]


def segments(definition: dict, area: Area = AREA) -> list[Segment]:
    return [m for m in marks(definition, area) if isinstance(m, Segment)]


def polygons(definition: dict, area: Area = AREA) -> list[Polygon]:
    return [m for m in marks(definition, area) if isinstance(m, Polygon)]


BARE = {"sectors": 4}


class TestTheScaffold:
    def test_the_centre_and_outer_radius_default_like_polar(self) -> None:
        # § 7.6: centre is the middle of the area, outer radius half the shorter
        # side. 80 mm tall → 40 mm.
        ring = arcs({**BARE, "rings": {"count": 1}})[0]
        assert (ring.center.x, ring.center.y) == (50_000, 40_000)
        assert ring.radius == 40_000

    def test_rings_are_evenly_spaced_out_to_the_rim(self) -> None:
        radii = sorted(r.radius for r in arcs({**BARE, "rings": {"count": 4}}))
        assert radii == [10_000, 20_000, 30_000, 40_000]

    def test_sectors_become_n_radial_spokes(self) -> None:
        spokes = segments({**BARE, "spokes": {}})
        assert len(spokes) == 4
        # A spoke points straight up: from the centre to the top of the disc.
        up = [s for s in spokes if s.start.x == 50_000 and s.end.x == 50_000]
        assert up and up[0].end.y == 80_000

    def test_spokes_can_leave_the_centre_clear(self) -> None:
        # An inner share keeps N spokes from meeting in one ink blot (§ 7.6).
        spoke = segments({**BARE, "spokes": {"inner": 0.5}})[0]
        near = min(
            math.dist((s.start.x, s.start.y), (50_000, 40_000))
            for s in segments({**BARE, "spokes": {"inner": 0.5}})
        )
        assert near == pytest.approx(20_000, abs=2)  # 0.5 * 40 mm
        assert spoke is not None


class TestTheRosette:
    def test_it_is_n_circles_one_per_sector(self) -> None:
        circles = arcs({**BARE, "rosette": {"at": 0.5, "radius": 0.25}})
        assert len(circles) == 4

    def test_each_circle_sits_on_its_spoke(self) -> None:
        # at = 0.5 of a 40 mm radius = 20 mm from the centre; the up circle is
        # centred 20 mm above the middle, radius 0.25 * 40 = 10 mm.
        circles = arcs({**BARE, "rosette": {"at": 0.5, "radius": 0.25}})
        up = [c for c in circles if c.center.x == 50_000 and c.center.y > 40_000]
        assert up and (up[0].center.y, up[0].radius) == (60_000, 10_000)

    def test_a_rosette_can_be_mirrored_onto_the_bisectors(self) -> None:
        # § 7.11: the motif is repeated *and* mirrored. Mirroring doubles the
        # ring of circles onto the sector bisectors — 2N in all.
        plain = arcs({**BARE, "rosette": {"at": 0.5, "radius": 0.25}})
        mirrored = arcs({**BARE, "rosette": {"at": 0.5, "radius": 0.25, "mirror": True}})
        assert len(mirrored) == 2 * len(plain)


class TestPolygons:
    def test_a_regular_polygon_has_its_sectors_vertices(self) -> None:
        poly = polygons({**BARE, "polygons": [{"radius": 0.9}]})[0]
        assert len(poly.points) == 4 and poly.closed

    def test_the_first_vertex_points_up(self) -> None:
        poly = polygons({**BARE, "polygons": [{"radius": 0.9}]})[0]
        top = max(poly.points, key=lambda p: p.y)
        assert (top.x, top.y) == (50_000, 76_000)  # 0.9 * 40 mm above the centre

    def test_a_star_polygon_visits_vertices_in_step_order(self) -> None:
        # {5/2} — a pentagram: five vertices, connected every second one.
        poly = polygons({"sectors": 5, "polygons": [{"radius": 0.8, "step": 2}]})[0]
        assert len(poly.points) == 5

    def test_a_polygon_can_override_its_side_count(self) -> None:
        poly = polygons({**BARE, "polygons": [{"radius": 0.9, "sides": 6}]})[0]
        assert len(poly.points) == 6


class TestValidation:
    def test_a_mandala_needs_at_least_two_sectors(self) -> None:
        with pytest.raises(ValidationError) as excinfo:
            MandalaConfig.model_validate({"sectors": 1, "rings": {"count": 3}})
        assert "sectors" in str(excinfo.value)

    def test_something_has_to_be_drawn(self) -> None:
        with pytest.raises(ValidationError) as excinfo:
            MandalaConfig.model_validate({"sectors": 6})
        message = str(excinfo.value)
        assert "rings" in message or "rosette" in message or "spokes" in message

    def test_a_compound_star_is_refused(self) -> None:
        # {6/2} is not a star but two overlaid triangles — gcd(6,2)=2. Refused
        # loudly rather than drawn as a broken single path (§ 12).
        with pytest.raises(ValidationError) as excinfo:
            MandalaConfig.model_validate(
                {"sectors": 6, "polygons": [{"radius": 0.8, "step": 2}]}
            )
        assert "step" in str(excinfo.value)

    def test_a_rosette_that_pokes_outside_the_area_is_refused(self) -> None:
        # § 8.2: nothing is drawn outside the pattern area. at + radius = 1.4 of
        # a 40 mm radius reaches 56 mm from the centre, past the 40 mm to the
        # top edge — refused before page one (§ 12 point 13).
        config = MandalaConfig.model_validate(
            {**BARE, "rosette": {"at": 0.9, "radius": 0.5}}
        )
        with pytest.raises(DefinitionError) as excinfo:
            MandalaGenerator().check(config, area=AREA, q=Q)
        assert "outside" in str(excinfo.value) or "area" in str(excinfo.value)


class TestTheSeam:
    def test_snapping_is_an_error(self) -> None:
        with pytest.raises(DefinitionError) as excinfo:
            preflight(
                loads(
                    "version: 1\npattern:\n  snap: cycle\ngenerator: mandala\n"
                    "sectors: 8\nrings:\n  count: 4\n",
                    source="test",
                ),
                Q,
            )
        message = str(excinfo.value)
        assert "mandala" in message and "snap" in message

    def test_the_pattern_is_the_same_on_every_page(self) -> None:
        config = MandalaConfig.model_validate({**BARE, "rings": {"count": 3}})
        assert MandalaGenerator().is_page_invariant(config) is True

    def test_there_is_no_period_to_snap_to(self) -> None:
        config = MandalaConfig.model_validate({**BARE, "rings": {"count": 3}})
        assert MandalaGenerator().periodic_axes(config) == {}

    def test_describe_reports_the_sectors_and_families(self) -> None:
        config = MandalaConfig.model_validate(
            {"sectors": 12, "rings": {"count": 6}, "rosette": {"at": 0.5, "radius": 0.2}}
        )
        described = "\n".join(MandalaGenerator().describe(config))
        assert "12" in described and "rosette" in described.lower()


class TestOnTheSheet:
    DEFINITION = (
        "version: 1\n"
        "page:\n  format: a5\n  margin: 10mm\n"
        "generator: mandala\n"
        "sectors: 12\n"
        "rings:\n  count: 6\n"
        "spokes:\n  {}\n"
        "rosette:\n  at: 0.5\n  radius: 0.2\n"
        "polygons:\n  - radius: 0.95\n"
    )

    def test_it_reaches_the_pdf(self, tmp_path: Path) -> None:
        import pdfread

        path = tmp_path / "target.pdf"
        build(loads(self.DEFINITION, source="test"), PdfWriter(path))
        assert pdfread.page_count(path) == 1

    def test_a_spoke_measures_the_full_radius(self, tmp_path: Path) -> None:
        # A5 is 148 mm wide, 10 mm margins: the shorter side of the pattern area
        # is 128 mm, so the outer radius is 64 mm. Arcs render as curves and are
        # not read back (§ 13.2); a horizontal spoke is a straight line of the
        # full radius, and measures 64 mm — to scale (§ 8.2).
        import pdfread

        path = tmp_path / "target.pdf"
        build(loads(self.DEFINITION, source="test"), PdfWriter(path))
        horizontal = [
            abs(line.x2 - line.x1) for line in pdfread.lines_um(path) if line.is_horizontal
        ]
        assert max(horizontal) == pytest.approx(64_000, abs=2)

    def test_two_runs_produce_identical_bytes(self, tmp_path: Path) -> None:
        first, second = tmp_path / "a.pdf", tmp_path / "b.pdf"
        for path in (first, second):
            build(loads(self.DEFINITION, source="test"), PdfWriter(path))
        assert first.read_bytes() == second.read_bytes()
