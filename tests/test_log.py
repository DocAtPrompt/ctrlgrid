"""Logarithmic axes (§ 7.9) — a property of a line family, not a generator.

Log paper is **periodic per decade**: the lines sit at log₁₀(1…10) and that
pattern repeats identically in every decade. The difference from the linear
case is not the periodicity but that the cycle entries are *positions within
the period* rather than *increments* — which is why the tool computes the
positions and nobody types `0.4771`.

A log family has a fixed total length of `decades × base_spacing` and does not
repeat. `decades` acts like `count` does on a linear family, and where the
block sits in the pattern area is decided by `remainder` (§ 8.5).
"""

from __future__ import annotations

import math
from pathlib import Path

import pytest
from pydantic import ValidationError

from ctrlgrid.errors import DefinitionError
from ctrlgrid.generators.lines import LinesConfig, LinesGenerator
from ctrlgrid.loader import loads
from ctrlgrid.marks import Area, Segment
from ctrlgrid.pages import PageContext, build, preflight
from ctrlgrid.writers.pdf import PdfWriter

AREA = Area(width=100_000, height=80_000)
PAGE = PageContext(index=0, number=1, count=1, name=None, is_even=False, seed_material=b"")
Q = PdfWriter("unused.pdf")

DECADE = {
    "direction": "horizontal",
    "law": "log10",
    "base_spacing": "25mm",
    "decades": 3,
}


def marks(family: dict, area: Area = AREA) -> list[Segment]:
    config = LinesConfig.model_validate({"families": [family]})
    return list(LinesGenerator().generate(config, area=area, page=PAGE, q=Q))


class TestThePositions:
    def test_a_decade_holds_nine_lines_plus_the_closing_one(self) -> None:
        # 1 … 9 in each decade, and the 10 that closes the last one.
        assert len(marks(DECADE)) == 3 * 9 + 1

    def test_they_sit_where_the_logarithm_says(self) -> None:
        positions = [mark.start.y for mark in marks(DECADE)]
        assert positions[0] == 0
        assert positions[1] == pytest.approx(25_000 * math.log10(2), abs=1)
        assert positions[9] == 25_000
        assert positions[-1] == 75_000

    def test_the_block_has_a_fixed_length_and_does_not_repeat(self) -> None:
        # § 7.9: `decades` acts like `count` — a longer area does not add a
        # fourth decade.
        assert max(mark.start.y for mark in marks(DECADE)) == 75_000

    def test_the_weight_cycle_runs_over_the_lines_of_a_decade(self) -> None:
        # Nine entries against nine lines: the decade start comes out heavy.
        drawn = marks({**DECADE, "base_weight": "0.15pt",
                       "weight": [2, 1, 1, 1, 1, 1, 1, 1, 1]})
        assert drawn[0].weight == pytest.approx(2 * drawn[1].weight)
        assert drawn[9].weight == pytest.approx(drawn[0].weight)

    def test_an_offset_moves_the_whole_block(self) -> None:
        drawn = marks({**DECADE, "decades": 2, "offset": "5mm"})
        assert drawn[0].start.y == 5_000

    def test_a_vertical_log_family_works_the_same(self) -> None:
        drawn = marks({**DECADE, "direction": "vertical", "decades": 2})
        assert drawn[0].start.x == 0
        assert max(mark.start.x for mark in drawn) == 50_000


class TestValidation:
    def test_log10_without_decades_is_an_error(self) -> None:
        with pytest.raises(ValidationError) as excinfo:
            LinesConfig.model_validate(
                {"families": [{"direction": "horizontal", "law": "log10",
                               "base_spacing": "25mm"}]}
            )
        assert "decades" in str(excinfo.value)

    def test_decades_without_log10_is_an_error(self) -> None:
        # § 5.1: a key that cannot take effect where it stands is an error.
        with pytest.raises(ValidationError) as excinfo:
            LinesConfig.model_validate(
                {"families": [{"direction": "horizontal", "base_spacing": "5mm",
                               "decades": 3}]}
            )
        assert "log10" in str(excinfo.value)

    def test_a_spacing_cycle_on_a_log_family_is_an_error(self) -> None:
        # The positions come from the logarithm; a spacing cycle would be a
        # second, contradictory answer to where the lines go (§ 7.9).
        with pytest.raises(ValidationError) as excinfo:
            LinesConfig.model_validate(
                {"families": [{**DECADE, "spacing": [1, 2]}]}
            )
        assert "spacing" in str(excinfo.value)

    def test_the_base_spacing_is_the_decade_length(self) -> None:
        described = LinesGenerator().describe(
            LinesConfig.model_validate({"families": [DECADE]})
        )[0]
        # § 7.9: "repeats every N lines" is meaningless for a family that does
        # not repeat, so the decade length is reported instead.
        assert "decade" in described and "25mm" in described
        assert "repeats" not in described


class TestFittingTheArea:
    def test_a_block_longer_than_the_area_is_refused_with_the_arithmetic(self) -> None:
        config = LinesConfig.model_validate(
            {"families": [{**DECADE, "base_spacing": "40mm", "decades": 3}]}
        )
        with pytest.raises(DefinitionError) as excinfo:
            LinesGenerator().check(config, area=AREA, q=Q)
        message = str(excinfo.value)
        assert "120.0mm" in message and "80.0mm" in message

    def test_nothing_is_written_when_it_does_not_fit(self, tmp_path: Path) -> None:
        path = tmp_path / "never.pdf"
        definition = (
            "version: 1\npage: {format: a6}\ngenerator: lines\nfamilies:\n"
            "  - {direction: horizontal, law: log10, base_spacing: 60mm, decades: 3}\n"
        )
        with pytest.raises(DefinitionError):
            build(loads(definition, source="test"), PdfWriter(path))
        assert not path.exists()


class TestSnapping:
    def test_snapping_a_log_axis_is_refused(self) -> None:
        # § 7.9: decade lengths do not divide sensibly into grid steps.
        definition = (
            "version: 1\npattern: {snap: cycle}\ngenerator: lines\nfamilies:\n"
            "  - {direction: horizontal, law: log10, base_spacing: 25mm, decades: 2}\n"
        )
        with pytest.raises(DefinitionError) as excinfo:
            preflight(loads(definition, source="test"), Q)
        message = str(excinfo.value)
        assert "log10" in message and "snap" in message

    def test_remainder_still_places_the_block(self) -> None:
        # § 7.9 sends the placement question to § 8.5: `center` puts the fixed
        # block in the middle of the pattern area.
        definition = (
            "version: 1\npage: {format: a5, margin: 10mm}\n"
            "pattern: {remainder: center}\ngenerator: lines\nfamilies:\n"
            "  - {direction: horizontal, law: log10, base_spacing: 25mm, decades: 2}\n"
        )
        geometry, _, _, _ = preflight(loads(definition, source="test"), Q)
        assert geometry.area.height == 50_000
        assert geometry.origin.y > 10_000


class TestOnTheSheet:
    def test_semi_log_paper_reaches_the_pdf(self, tmp_path: Path) -> None:
        import pdfread

        path = tmp_path / "semilog.pdf"
        build(
            loads(
                "version: 1\npage: {format: a5, margin: 10mm}\n"
                "generator: lines\nfamilies:\n"
                "  - {direction: horizontal, law: log10, base_spacing: 25mm, decades: 4,\n"
                "     weight: [2, 1, 1, 1, 1, 1, 1, 1, 1]}\n"
                "  - {direction: vertical, base_spacing: 5mm}\n",
                source="test",
            ),
            PdfWriter(path),
        )
        rows = sorted({round(line.y1) for line in pdfread.lines_um(path)
                       if line.is_horizontal})
        assert len(rows) == 4 * 9 + 1
        # The gaps shrink inside a decade and jump back at its start.
        gaps = [rows[i + 1] - rows[i] for i in range(9)]
        assert gaps == sorted(gaps, reverse=True)
