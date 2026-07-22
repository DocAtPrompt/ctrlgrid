"""The `polar` blade (§ 7.6) — M3, and the hard test of § 14.

Every other generator is cartesian. If the handle copes with a polar one —
pattern area, frame, capability check, label measurement — the architecture
holds; if it falls apart, better after blade two than after blade seven.

**The cycle model carries over unchanged** (§ 7.6): base times dimensionless
multiples, cyclically, only in polar coordinates. Rings run in micrometres and
spokes in micro-degrees, and both go through the same `Cycle` the `lines`
families use — which is what "unchanged" has to mean if it means anything.
"""

from __future__ import annotations

import math
from pathlib import Path

import pytest
from pydantic import ValidationError

from ctrlgrid.errors import DefinitionError
from ctrlgrid.generators.polar import PolarConfig, PolarGenerator
from ctrlgrid.loader import loads
from ctrlgrid.marks import Arc, Area, Segment, Text
from ctrlgrid.pages import PageContext, build, preflight
from ctrlgrid.writers.pdf import PdfWriter

AREA = Area(width=100_000, height=80_000)
PAGE = PageContext(index=0, number=1, count=1, name=None, is_even=False, seed_material=b"")
Q = PdfWriter("unused.pdf")

RINGS = {"rings": {"base_radius": "10mm"}}
SPOKES = {"spokes": {"base_angle": "30deg"}}


def marks(definition: dict, area: Area = AREA) -> list:
    config = PolarConfig.model_validate(definition)
    return list(PolarGenerator().generate(config, area=area, page=PAGE, q=Q))


def arcs(definition: dict, area: Area = AREA) -> list[Arc]:
    return [mark for mark in marks(definition, area) if isinstance(mark, Arc)]


def spokes(definition: dict, area: Area = AREA) -> list[Segment]:
    return [mark for mark in marks(definition, area) if isinstance(mark, Segment)]


class TestTheCentreAndTheRadius:
    def test_the_centre_is_the_middle_of_the_pattern_area(self) -> None:
        ring = arcs(RINGS)[0]
        assert (ring.center.x, ring.center.y) == (50_000, 40_000)

    def test_the_outer_radius_is_half_the_shorter_side(self) -> None:
        # § 7.6: 80 mm tall area, so 40 mm — the largest circle that fits.
        rings = arcs({"rings": {"base_radius": "1mm"}})
        assert max(ring.radius for ring in rings) == 40_000

    def test_both_can_be_overridden(self) -> None:
        rings = arcs(
            {
                "center": {"x": "30mm", "y": "20mm"},
                "outer_radius": "15mm",
                "rings": {"base_radius": "5mm"},
            }
        )
        assert (rings[0].center.x, rings[0].center.y) == (30_000, 20_000)
        assert max(ring.radius for ring in rings) == 15_000


class TestRings:
    def test_they_sit_on_multiples_of_the_base_radius(self) -> None:
        radii = [ring.radius for ring in arcs({"rings": {"base_radius": "10mm"}})]
        assert radii == [10_000, 20_000, 30_000, 40_000]

    def test_the_cycle_applies_exactly_as_it_does_to_a_family(self) -> None:
        # § 7.6: the model carries over unchanged — [1, 1, 2] on a 10 mm base
        # gives 10, 20, 40 …, the same arithmetic § 5.3 defines for spacings.
        radii = [
            ring.radius
            for ring in arcs({"rings": {"base_radius": "10mm", "radius": [1, 1, 2]}})
        ]
        assert radii == [10_000, 20_000, 40_000]

    def test_there_is_no_ring_of_radius_zero(self) -> None:
        # Mark 0 of a family sits on the origin, and in polar coordinates that
        # is the centre point — a circle of radius 0 is not a mark.
        assert all(ring.radius > 0 for ring in arcs(RINGS))

    def test_weight_and_colour_stay_in_step_with_the_radius(self) -> None:
        rings = arcs(
            {
                "rings": {
                    "base_radius": "10mm",
                    "base_weight": "0.2pt",
                    "weight": [1, 1, 1, 2],
                    "color": ["#111111", "#222222"],
                }
            }
        )
        assert rings[3].weight == pytest.approx(2 * rings[0].weight)
        assert [ring.color for ring in rings[:2]] == ["#111111", "#222222"]

    def test_a_full_circle_is_one_arc(self) -> None:
        # § 6: `Arc` covers full circles, rings and segment arcs, and M3 is the
        # first blade that actually uses it.
        ring = arcs(RINGS)[0]
        assert (ring.start_angle, ring.sweep) == (0.0, 360.0)


class TestSpokes:
    def test_thirty_degrees_gives_twelve_spokes(self) -> None:
        assert len(spokes(SPOKES)) == 12

    def test_the_spoke_at_three_hundred_and_sixty_is_not_drawn_twice(self) -> None:
        # It is the one at 0°, and two strokes on one line print heavier.
        angles = {
            round(math.degrees(math.atan2(s.end.y - s.start.y, s.end.x - s.start.x)) % 360)
            for s in spokes(SPOKES)
        }
        assert len(angles) == 12

    def test_the_angle_cycle_works_like_any_other(self) -> None:
        drawn = spokes({"spokes": {"base_angle": "30deg", "angle": [1, 1, 2]}})
        angles = sorted(
            round(math.degrees(math.atan2(s.end.y - s.start.y, s.end.x - s.start.x)) % 360)
            for s in drawn
        )
        assert angles[:4] == [0, 30, 60, 120]

    def test_a_spoke_reaches_the_outer_radius(self) -> None:
        spoke = spokes(SPOKES)[0]
        length = math.dist((spoke.start.x, spoke.start.y), (spoke.end.x, spoke.end.y))
        assert length == pytest.approx(40_000, abs=2)

    def test_radial_extent_shortens_it_from_the_inside(self) -> None:
        # § 7.6: `radial_extent`, not `extent` — here the bound runs *along*
        # the spoke, and one key name for two reference axes would be a trap.
        spoke = spokes(
            {"spokes": {"base_angle": "90deg", "radial_extent": {"start": "10mm"}}}
        )[0]
        assert math.dist((spoke.start.x, spoke.start.y), (50_000, 40_000)) == pytest.approx(
            10_000, abs=2
        )

    def test_radial_extent_can_stop_short_of_the_rim(self) -> None:
        spoke = spokes(
            {"spokes": {"base_angle": "90deg", "radial_extent": {"end": "20mm"}}}
        )[0]
        assert math.dist((spoke.end.x, spoke.end.y), (50_000, 40_000)) == pytest.approx(
            20_000, abs=2
        )


class TestLabels:
    def texts(self, definition: dict) -> list[Text]:
        return [mark for mark in marks(definition) if isinstance(mark, Text)]

    def middle_of(self, text: Text) -> tuple[float, float]:
        """Where the label *looks* like it sits.

        A `Text` mark is anchored on its baseline, so the drawn glyphs sit
        above `pos`. What is placed in the segment is the visual middle, and
        the offset comes from the same query the layout used (§ 10.2) rather
        than from a number copied out of the implementation.
        """
        ascent, _ = Q.text_metrics(family=text.family, size=text.size)
        return text.pos.x, text.pos.y + ascent / 2

    def test_a_counting_pattern_labels_the_segments(self) -> None:
        # § 7.10: the count comes from the generator, the pattern says how to
        # count — twelve 30° segments, so 1 … 12.
        contents = [text.content for text in self.texts({**SPOKES, "labels": {"spokes": "n"}})]
        assert contents == [str(number) for number in range(1, 13)]

    def test_the_label_sits_between_two_spokes(self) -> None:
        # Segment 1 of a 90° family runs from 0° to 90°, so its label sits at
        # 45° — in the middle of the wedge, not on a line.
        text = self.texts(
            {"spokes": {"base_angle": "90deg"}, "labels": {"spokes": "n"}}
        )[0]
        x, y = self.middle_of(text)
        angle = math.degrees(math.atan2(y - 40_000, x - 50_000)) % 360
        assert angle == pytest.approx(45, abs=0.5)

    def test_the_label_radius_is_a_share_of_the_outer_radius(self) -> None:
        text = self.texts(
            {"spokes": {"base_angle": "90deg"},
             "labels": {"spokes": "n", "spoke_radius": 0.5}}
        )[0]
        assert math.dist(self.middle_of(text), (50_000, 40_000)) == pytest.approx(
            20_000, abs=2
        )

    def test_ring_labels_are_an_explicit_list_from_outside_in(self) -> None:
        # § 7.6 writes them as a score: [10, 8, 6, 4].
        contents = [
            text.content
            for text in self.texts({**RINGS, "labels": {"rings": [10, 8, 6, 4]}})
        ]
        assert contents == ["10", "8", "6", "4"]

    def test_a_ring_list_of_the_wrong_length_names_both_numbers(self) -> None:
        with pytest.raises(DefinitionError) as excinfo:
            marks({**RINGS, "labels": {"rings": [10, 8]}})
        message = str(excinfo.value)
        assert "2" in message and "4" in message

    def test_ring_labels_do_not_sit_on_a_spoke(self) -> None:
        # Seen on a real sheet: straight up is where a spoke runs on any family
        # that divides 90°, and a number printed over a line is unreadable.
        # They go on the bisector of the segment that contains straight up.
        texts = self.texts(
            {**RINGS, "spokes": {"base_angle": "90deg"}, "labels": {"rings": [4, 3, 2, 1]}}
        )
        for text in texts:
            x, y = self.middle_of(text)
            angle = math.degrees(math.atan2(y - 40_000, x - 50_000)) % 360
            assert abs(angle - 135) < 0.5

    def test_without_spokes_ring_labels_stand_straight_up(self) -> None:
        texts = self.texts({**RINGS, "labels": {"rings": [4, 3, 2, 1]}})
        assert all(text.pos.x == 50_000 for text in texts)

    def test_labels_none_leaves_them_out(self) -> None:
        assert self.texts({**SPOKES, "labels": {"spokes": "none"}}) == []


class TestMeasuringLabelsBeforeRendering:
    """§ 7.6: "12" in a 15° segment at the inner radius does not fit, and that
    has to come out before the first page, not on it (§ 10.2, § 12 point 13)."""

    def test_a_label_too_wide_for_its_segment_is_refused(self) -> None:
        config = PolarConfig.model_validate(
            {
                "spokes": {"base_angle": "3deg"},
                "labels": {"spokes": "n", "spoke_radius": 0.05, "font": {"size": "12pt"}},
            }
        )
        with pytest.raises(DefinitionError) as excinfo:
            PolarGenerator().check(config, area=AREA, q=Q)
        message = str(excinfo.value)
        assert "segment" in message.lower()

    def test_a_ring_list_of_the_wrong_length_is_caught_before_writing(self) -> None:
        # Found on a real sheet, not by a test: the count mismatch was raised
        # from `generate`, which is half way through writing the file. Every
        # refusal belongs in the pre-flight (§ 12 point 13).
        config = PolarConfig.model_validate({**RINGS, "labels": {"rings": [10, 8]}})
        with pytest.raises(DefinitionError):
            PolarGenerator().check(config, area=AREA, q=Q)

    def test_a_label_that_fits_passes(self) -> None:
        config = PolarConfig.model_validate({**SPOKES, "labels": {"spokes": "n"}})
        PolarGenerator().check(config, area=AREA, q=Q)

    def test_a_circle_larger_than_the_pattern_area_is_refused(self) -> None:
        # Nothing is clipped and nothing is scaled (§ 8.2): the blade gets the
        # pattern area and everything it draws belongs inside it.
        config = PolarConfig.model_validate({"outer_radius": "60mm", **RINGS})
        with pytest.raises(DefinitionError) as excinfo:
            PolarGenerator().check(config, area=AREA, q=Q)
        assert "60mm" in str(excinfo.value)


class TestTheSeam:
    def test_snapping_is_an_error_for_polar(self) -> None:
        # § 8.3 and § 7.6: an error, never a guess.
        with pytest.raises(DefinitionError) as excinfo:
            preflight(
                loads(
                    "version: 1\npattern:\n  snap: cycle\ngenerator: polar\n"
                    "rings:\n  base_radius: 10mm\n",
                    source="test",
                ),
                Q,
            )
        message = str(excinfo.value)
        assert "polar" in message and "snap" in message

    def test_the_pattern_is_the_same_on_every_page(self) -> None:
        config = PolarConfig.model_validate(RINGS)
        assert PolarGenerator().is_page_invariant(config) is True

    def test_describe_reports_both_families(self) -> None:
        config = PolarConfig.model_validate({**RINGS, **SPOKES})
        described = "\n".join(PolarGenerator().describe(config))
        assert "10mm" in described and "30deg" in described

    def test_at_least_one_family_is_required(self) -> None:
        with pytest.raises(ValidationError) as excinfo:
            PolarConfig.model_validate({})
        assert "rings" in str(excinfo.value) and "spokes" in str(excinfo.value)


class TestOnTheSheet:
    DEFINITION = (
        "version: 1\n"
        "page:\n  format: a5\n  margin: 10mm\n"
        "generator: polar\n"
        "rings:\n  base_radius: 10mm\n  weight: [1, 1, 1, 2]\n"
        "spokes:\n  base_angle: 30deg\n"
        "labels:\n  spokes: 'n'\n"
    )

    def test_it_reaches_the_pdf(self, tmp_path: Path) -> None:
        import pdfread

        path = tmp_path / "target.pdf"
        build(loads(self.DEFINITION, source="test"), PdfWriter(path))
        assert pdfread.page_count(path) == 1
        assert "12" in pdfread.text_on(path)

    def test_the_rim_measures_what_it_should(self, tmp_path: Path) -> None:
        # A5 is 148 mm wide, 10 mm margins: the shorter side of the pattern
        # area is 128 mm, so the outer radius is 64 mm and a spoke is 64 mm.
        import pdfread

        path = tmp_path / "target.pdf"
        build(loads(self.DEFINITION, source="test"), PdfWriter(path))
        horizontal = [
            line for line in pdfread.lines_um(path) if line.is_horizontal
        ]
        widths = [abs(line.x2 - line.x1) for line in horizontal]
        assert max(widths) == pytest.approx(64_000, abs=2)

    def test_two_runs_produce_identical_bytes(self, tmp_path: Path) -> None:
        first, second = tmp_path / "a.pdf", tmp_path / "b.pdf"
        for path in (first, second):
            build(loads(self.DEFINITION, source="test"), PdfWriter(path))
        assert first.read_bytes() == second.read_bytes()

    def test_nothing_is_written_when_the_ring_labels_do_not_match(
        self, tmp_path: Path
    ) -> None:
        path = tmp_path / "never.pdf"
        definition = (
            "version: 1\ngenerator: polar\n"
            "rings:\n  base_radius: 10mm\n"
            "labels:\n  rings: [10, 8]\n"
        )
        with pytest.raises(DefinitionError):
            build(loads(definition, source="test"), PdfWriter(path))
        assert not path.exists()

    def test_nothing_is_written_when_a_label_does_not_fit(self, tmp_path: Path) -> None:
        path = tmp_path / "never.pdf"
        definition = (
            "version: 1\ngenerator: polar\n"
            "spokes:\n  base_angle: 2deg\n"
            "labels:\n  spokes: 'n'\n  spoke_radius: 0.05\n"
        )
        with pytest.raises(DefinitionError):
            build(loads(definition, source="test"), PdfWriter(path))
        assert not path.exists()
