"""Dashed and dotted families (§ 5.3, § 7.1).

The dash cycle is the one cycle that does **not** run position-wise over the
marks. `weight: [1, 1, 2]` means "every third line heavier"; `dash: [2, 1]`
means "2 on, 1 off" *within every line of the family*. § 5.3 calls it a
`Strichel-/Punktmuster` — a pattern of one mark, not a sequence of marks — so
it also stays out of the effective period, which counts marks.
"""

from __future__ import annotations

from pathlib import Path

import pdfread
import pytest
from pydantic import ValidationError

from ctrlgrid.generators.lines import LinesConfig, LinesGenerator
from ctrlgrid.loader import loads
from ctrlgrid.marks import Area, Segment
from ctrlgrid.pages import PageContext, build
from ctrlgrid.writers.pdf import PdfWriter

AREA = Area(width=100_000, height=50_000)
PAGE = PageContext(index=0, number=1, count=1, name=None, is_even=False, seed_material=b"")


def marks(family: dict) -> list[Segment]:
    config = LinesConfig.model_validate({"families": [{**family}]})
    return list(LinesGenerator().generate(config, area=AREA, page=PAGE, q=None))


BASE = {"direction": "horizontal", "base_spacing": "10mm"}


class TestTheDashPattern:
    def test_solid_is_the_default_and_carries_no_pattern(self) -> None:
        assert marks(BASE)[0].dash == ()

    def test_the_cycle_multiplies_the_base_like_every_other_cycle(self) -> None:
        # § 5.3: entries are bare multiples of `base_dash`.
        mark = marks({**BASE, "style": "dashed", "base_dash": "1mm", "dash": [2, 1]})[0]
        assert mark.dash == (2.0, 1.0)

    def test_the_pattern_is_the_same_on_every_line_of_the_family(self) -> None:
        # The point of the whole file: not position-wise (§ 5.3).
        drawn = marks({**BASE, "style": "dashed", "base_dash": "1mm", "dash": [3, 1]})
        assert len({mark.dash for mark in drawn}) == 1

    def test_dashed_without_a_cycle_still_dashes(self) -> None:
        assert marks({**BASE, "style": "dashed"})[0].dash != ()

    def test_dotted_draws_round_dots(self) -> None:
        # A dot is a zero-length on-segment with a round cap — the same trick
        # § 10.1 uses for the `dots` blade, and the reason the cap field exists.
        mark = marks({**BASE, "style": "dotted"})[0]
        assert mark.cap == "round"
        assert mark.dash[0] == 0.0

    def test_dashed_keeps_square_ends(self) -> None:
        assert marks({**BASE, "style": "dashed"})[0].cap == "butt"


class TestValidation:
    def test_a_dash_cycle_on_a_solid_family_is_an_error(self) -> None:
        # § 5.1: silently ignoring it would leave a sheet that is almost right.
        with pytest.raises(ValidationError) as excinfo:
            LinesConfig.model_validate(
                {"families": [{**BASE, "style": "solid", "dash": [2, 1]}]}
            )
        message = str(excinfo.value)
        assert "dash" in message and "solid" in message

    def test_a_pattern_of_nothing_but_zeros_is_an_error(self) -> None:
        with pytest.raises(ValidationError) as excinfo:
            LinesConfig.model_validate(
                {"families": [{**BASE, "style": "dashed", "dash": [0, 0]}]}
            )
        assert "0" in str(excinfo.value)

    def test_a_dash_longer_than_the_line_is_not_an_error(self) -> None:
        # It simply draws solid. Nothing is wrong with it, and refusing would
        # mean knowing the pattern area here, which a blade does not (§ 3.3).
        assert marks({**BASE, "style": "dashed", "base_dash": "500mm"})


class TestTheEffectivePeriod:
    def test_the_dash_cycle_does_not_lengthen_the_period(self) -> None:
        # § 5.3: the period is counted in *marks*, and the dash pattern
        # describes one mark rather than a run of them.
        plain = LinesConfig.model_validate({"families": [{**BASE, "weight": [1, 2]}]})
        dashed = LinesConfig.model_validate(
            {"families": [{**BASE, "weight": [1, 2], "style": "dashed", "dash": [3, 1, 2]}]}
        )
        blade = LinesGenerator()
        assert blade.periodic_axes(plain)["y"][0].cycle_um == (
            blade.periodic_axes(dashed)["y"][0].cycle_um
        )

    def test_the_style_is_reported_on_the_cover(self) -> None:
        config = LinesConfig.model_validate(
            {"families": [{**BASE, "style": "dashed", "base_dash": "1mm", "dash": [2, 1]}]}
        )
        line = LinesGenerator().describe(config)[0]
        assert "dashed" in line and "1mm" in line and "[2, 1]" in line


class TestOnTheSheet:
    """Read back out of the file, in points — § 13.2 compares parsed geometry."""

    def sheet(self, tmp_path: Path, family: str) -> Path:
        path = tmp_path / "dash.pdf"
        build(
            loads(
                "version: 1\ngenerator: lines\nfamilies:\n"
                f"  - {{direction: horizontal, base_spacing: 10mm, {family}}}\n",
                source="test",
            ),
            PdfWriter(path),
        )
        return path

    def test_the_pattern_reaches_the_pdf_in_points(self, tmp_path: Path) -> None:
        # base 2 mm x [2, 1] is 4 mm on and 2 mm off — in points 11.34 and 5.67.
        path = self.sheet(tmp_path, "style: dashed, base_dash: 2mm, dash: [2, 1]")
        arrays = pdfread.dash_arrays(path)
        assert arrays, "no dash array in the content stream"
        assert arrays[0][0] == pytest.approx(4000 * 72 / 25400, abs=0.01)
        assert arrays[0][1] == pytest.approx(2000 * 72 / 25400, abs=0.01)

    def test_a_solid_family_sets_no_dash_at_all(self, tmp_path: Path) -> None:
        path = self.sheet(tmp_path, "style: solid")
        assert pdfread.dash_arrays(path) == []
        assert pdfread.lines_um(path)
