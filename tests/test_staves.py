"""The `staves` blade (§ 7.3) — grouped line families.

Two things carry the whole section. **Two ways of saying the same size**,
`stave_space` (the distance between neighbouring lines) or `stave_height` (top
line to bottom line), which exclude each other and convert by `lines − 1`, not
by 4 — tablature has six lines. And **`system_gap` is the gap, not the pitch**:
measured from the bottom line of one system to the top line of the next, so it
survives a switch from notation to tablature unchanged.

The unit `sp` is generator-local (§ 5.1): it means stave spaces, it is resolved
once `stave_space` is known, and it exists so a sheet stays proportioned when
the stave size changes.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from ctrlgrid import fonts
from ctrlgrid.errors import DefinitionError
from ctrlgrid.generators.staves import CLEF_FONT, CLEFS, StavesConfig, StavesGenerator
from ctrlgrid.loader import loads
from ctrlgrid.marks import Area, Segment, Text
from ctrlgrid.pages import PageContext, build
from ctrlgrid.writers.pdf import PdfWriter

AREA = Area(width=100_000, height=100_000)
PAGE = PageContext(index=0, number=1, count=1, name=None, is_even=False, seed_material=b"")
Q = PdfWriter("unused.pdf")


def marks(definition: dict, area: Area = AREA) -> list[Segment]:
    config = StavesConfig.model_validate(definition)
    return list(StavesGenerator().generate(config, area=area, page=PAGE, q=Q))


def rows(definition: dict, area: Area = AREA) -> list[int]:
    return sorted({mark.start.y for mark in marks(definition, area)}, reverse=True)


class TestTheSize:
    def test_stave_space_is_the_distance_between_neighbours(self) -> None:
        lines = rows({"count": 1, "stave_space": "1.75mm"})
        assert len(lines) == 5
        assert lines[0] - lines[1] == 1750

    def test_stave_height_converts_by_the_number_of_lines_minus_one(self) -> None:
        # § 7.3: 7 mm over five lines is 1.75 mm — and the divisor follows
        # `lines`, so tablature divides by five, not four.
        assert rows({"count": 1, "stave_height": "7mm"})[0] - rows(
            {"count": 1, "stave_height": "7mm"}
        )[1] == 1750

    def test_tablature_divides_by_five(self) -> None:
        lines = rows({"count": 1, "stave_height": "7mm", "lines": 6})
        assert len(lines) == 6
        assert lines[0] - lines[1] == 1400

    def test_the_two_ways_exclude_each_other(self) -> None:
        with pytest.raises(ValidationError) as excinfo:
            StavesConfig.model_validate(
                {"count": 1, "stave_space": "1.75mm", "stave_height": "7mm"}
            )
        message = str(excinfo.value)
        assert "stave_space" in message and "stave_height" in message

    def test_one_of_them_is_required(self) -> None:
        with pytest.raises(ValidationError):
            StavesConfig.model_validate({"count": 1})


class TestTheSystemGap:
    def test_it_is_measured_between_the_nearest_lines(self) -> None:
        # § 7.3: bottom line of one system to top line of the next, which is
        # what makes it independent of `lines`.
        lines = rows({"count": 2, "stave_space": "2mm", "system_gap": "10mm"})
        bottom_of_first, top_of_second = lines[4], lines[5]
        assert bottom_of_first - top_of_second == 10_000

    def test_the_gap_does_not_change_when_the_line_count_does(self) -> None:
        five = rows({"count": 2, "stave_space": "2mm", "system_gap": "10mm"})
        six = rows({"count": 2, "stave_space": "2mm", "system_gap": "10mm", "lines": 6})
        assert five[4] - five[5] == six[5] - six[6] == 10_000

    def test_it_can_be_given_in_stave_spaces(self) -> None:
        # § 7.3: `sp` is why a sheet stays proportioned at any stave size.
        lines = rows({"count": 2, "stave_space": "2mm", "system_gap": "4sp"})
        assert lines[4] - lines[5] == 8_000

    def test_sp_outside_this_blade_is_still_refused(self) -> None:
        # § 5.1: a generator-local unit has no meaning elsewhere.
        with pytest.raises(DefinitionError) as excinfo:
            loads(
                "version: 1\npage: {margin: 4sp}\ngenerator: lines\n"
                "families: [{direction: horizontal, base_spacing: 5mm}]\n",
                source="test",
            )
        assert "sp" in str(excinfo.value)


class TestTheSystems:
    def test_the_first_system_starts_at_the_top(self) -> None:
        # Music is read from the top down, so that is where the sheet fills.
        assert rows({"count": 2, "stave_space": "2mm", "system_gap": "10mm"})[0] == 100_000

    def test_every_system_has_the_same_shape(self) -> None:
        lines = rows({"count": 3, "stave_space": "2mm", "system_gap": "8mm"})
        first = [lines[0] - value for value in lines[0:5]]
        second = [lines[5] - value for value in lines[5:10]]
        assert first == second

    def test_a_line_spans_the_pattern_area(self) -> None:
        mark = marks({"count": 1, "stave_space": "2mm"})[0]
        assert (mark.start.x, mark.end.x) == (0, AREA.width)

    def test_too_many_systems_are_refused_with_the_arithmetic(self) -> None:
        config = StavesConfig.model_validate(
            {"count": 12, "stave_space": "2mm", "system_gap": "10mm"}
        )
        with pytest.raises(DefinitionError) as excinfo:
            StavesGenerator().check(config, area=AREA, q=Q)
        message = str(excinfo.value)
        assert "100.0mm" in message and "12" in message


def clefs(definition: dict, area: Area = AREA) -> list[Text]:
    config = StavesConfig.model_validate(definition)
    return [
        m
        for m in StavesGenerator().generate(config, area=area, page=PAGE, q=Q)
        if isinstance(m, Text)
    ]


class TestClefs:
    # M9 (§ 7.3, § 15.3): a clef is a Text mark in the embedded music font. The
    # SMuFL convention makes it exact — 1 em = 4 stave spaces, and the glyph
    # origin sits on the clef's reference line, so size = 4 x space and the text
    # baseline goes on that line.
    def test_none_is_the_default_and_draws_nothing(self) -> None:
        assert StavesConfig.model_validate({"count": 1, "stave_space": "2mm"}).clef == "none"
        assert clefs({"count": 2, "stave_space": "2mm"}) == []

    def test_a_treble_clef_is_text_in_the_embedded_music_font(self) -> None:
        clef = clefs({"count": 1, "stave_space": "1.75mm", "clef": "treble"})[0]
        assert clef.content == chr(0xE050)  # SMuFL gClef
        assert clef.family == fonts.token_for(str(CLEF_FONT))
        assert clef.align == "left"

    def test_the_clef_is_four_stave_spaces_tall(self) -> None:
        # § 7.3 / SMuFL: 1 em = 4 stave spaces, so the font size is 4 x space.
        clef = clefs({"count": 1, "stave_space": "1.75mm", "clef": "treble"})[0]
        assert clef.size == 4 * 1750

    def test_each_clef_sits_on_its_reference_line(self) -> None:
        # Top line of the first system is at area.height (music fills from the
        # top). The reference line is N spaces down: treble 3 (the G line),
        # bass 1 (the F line), alto 2 (the middle), tenor 1.
        space = 1750
        for name, (_cp, ref) in CLEFS.items():
            clef = clefs({"count": 1, "stave_space": "1.75mm", "clef": name})[0]
            assert clef.pos.y == AREA.height - ref * space, name

    def test_the_four_clefs_map_to_the_right_glyphs(self) -> None:
        got = {
            name: clefs({"count": 1, "stave_space": "2mm", "clef": name})[0].content
            for name in CLEFS
        }
        assert got == {
            "treble": chr(0xE050),
            "bass": chr(0xE062),
            "alto": chr(0xE05C),
            "tenor": chr(0xE05C),
        }

    def test_one_clef_per_system(self) -> None:
        assert len(clefs({"count": 3, "stave_space": "1.75mm", "clef": "bass"})) == 3

    def test_the_clef_sits_at_the_indent(self) -> None:
        clef = clefs(
            {"count": 1, "stave_space": "1.75mm", "clef": "treble", "clef_indent": "5mm"}
        )[0]
        assert clef.pos.x == 5000

    def test_a_clef_needs_a_five_line_staff(self) -> None:
        # The reference lines are defined for a 5-line staff; on tablature a
        # music clef has no line to sit on. Refused loudly (§ 12), not guessed.
        with pytest.raises(ValidationError) as excinfo:
            StavesConfig.model_validate(
                {"count": 1, "stave_space": "2mm", "lines": 6, "clef": "treble"}
            )
        assert "5" in str(excinfo.value) and "clef" in str(excinfo.value).lower()


class TestTheSeam:
    def test_snapping_is_refused(self) -> None:
        # § 8.3 lists `staves` among the blades where snapping is an error.
        assert StavesGenerator().supports_snap is False

    def test_describe_reports_the_size_both_ways(self) -> None:
        described = "\n".join(
            StavesGenerator().describe(
                StavesConfig.model_validate({"count": 4, "stave_space": "1.75mm"})
            )
        )
        assert "1.75mm" in described and "4" in described


class TestOnTheSheet:
    DEFINITION = (
        "version: 1\n"
        "page:\n  format: a4\n  margin: 15mm\n"
        "generator: staves\n"
        "count: 10\n"
        "stave_space: 1.75mm\n"
        "system_gap: 6sp\n"
        "weight: 0.2pt\n"
    )

    def test_it_reaches_the_pdf(self, tmp_path: Path) -> None:
        import pdfread

        path = tmp_path / "staves.pdf"
        build(loads(self.DEFINITION, source="test"), PdfWriter(path))
        assert pdfread.page_count(path) == 1
        assert len(pdfread.lines_um(path)) == 10 * 5

    def test_the_lines_measure_what_they_should(self, tmp_path: Path) -> None:
        import pdfread

        path = tmp_path / "staves.pdf"
        build(loads(self.DEFINITION, source="test"), PdfWriter(path))
        rows_um = sorted({round(line.y1) for line in pdfread.lines_um(path)}, reverse=True)
        assert rows_um[0] - rows_um[1] == pytest.approx(1750, abs=2)

    def test_two_runs_produce_identical_bytes(self, tmp_path: Path) -> None:
        first, second = tmp_path / "a.pdf", tmp_path / "b.pdf"
        for path in (first, second):
            build(loads(self.DEFINITION, source="test"), PdfWriter(path))
        assert first.read_bytes() == second.read_bytes()


class TestClefsOnTheSheet:
    DEFINITION = (
        "version: 1\n"
        "page:\n  format: a4\n  margin: 15mm\n"
        "generator: staves\n"
        "count: 6\n"
        "stave_space: 2mm\n"
        "system_gap: 8sp\n"
        "clef: treble\n"
    )

    def test_the_music_font_is_embedded(self, tmp_path: Path) -> None:
        # § 15.3: self-contained through embedding. The clef font travels inside
        # the PDF — subset to the clef glyphs — under its renamed identity.
        from pypdf import PdfReader

        path = tmp_path / "clef.pdf"
        build(loads(self.DEFINITION, source="test"), PdfWriter(path))
        resource = PdfReader(str(path)).pages[0]["/Resources"]["/Font"]
        basefonts = [str(resource[key]["/BaseFont"]) for key in resource]
        assert any("CtrlgridClefs" in name for name in basefonts)

    def test_two_runs_produce_identical_bytes(self, tmp_path: Path) -> None:
        first, second = tmp_path / "a.pdf", tmp_path / "b.pdf"
        for path in (first, second):
            build(loads(self.DEFINITION, source="test"), PdfWriter(path))
        assert first.read_bytes() == second.read_bytes()
