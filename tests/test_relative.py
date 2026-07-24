"""The general relative measure (§ 8.11) — `%w`/`%h`/`%s`, end to end.

A fixed millimetre fills A4 (1:√2) and a 3:4 e-ink slate differently. A relative
measure is a fraction of the pattern area, so a definition fills whatever medium
it lands on. It resolves in seam 1 against the *raw* pattern area — sheet minus
margins and bands — the same way `px` resolves against a device density, so
nothing downstream ever sees a relative unit (§ 3.6, § 8.11).

Allowed only in a generator's spatial measures. In a margin, a band, a weight or
a size it is refused: those either have no pattern area or define it.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ctrlgrid.errors import DefinitionError
from ctrlgrid.loader import loads
from ctrlgrid.pages import build
from ctrlgrid.writers.pdf import PdfWriter


def spacing_um(definition: str) -> int:
    return loads(definition, source="test").config.families[0].base_spacing.um


A4_VERTICAL = (
    "version: 1\n"
    "page:\n  format: {fmt}\n  margin: 10mm\n"
    "generator: lines\n"
    "families:\n  - direction: vertical\n    base_spacing: {measure}\n"
)


class TestResolution:
    def test_percent_of_width_is_a_fraction_of_the_pattern_width(self) -> None:
        # A4 is 210 mm wide, 10 mm margins each side: a 190 mm pattern width, so
        # 10%w is 19 mm — exactly, in seam 1.
        assert spacing_um(A4_VERTICAL.format(fmt="a4", measure="10%w")) == 19_000

    def test_percent_of_height(self) -> None:
        # A4 is 297 mm tall, 10 mm top and bottom: 277 mm, so 10%h is 27.7 mm.
        assert spacing_um(A4_VERTICAL.format(fmt="a4", measure="10%h")) == 27_700

    def test_percent_of_the_shorter_side(self) -> None:
        # The shorter side of the A4 pattern area is its 190 mm width, so 10%s
        # matches 10%w here.
        assert spacing_um(A4_VERTICAL.format(fmt="a4", measure="10%s")) == 19_000

    def test_it_fills_the_medium_the_same_definition_scales(self) -> None:
        # The whole point: one definition, two formats, proportional spacing.
        a4 = spacing_um(A4_VERTICAL.format(fmt="a4", measure="10%w"))  # 190 mm -> 19
        a5 = spacing_um(A4_VERTICAL.format(fmt="a5", measure="10%w"))  # 128 mm -> 12.8
        assert a4 == 19_000 and a5 == 12_800

    def test_bands_come_off_before_the_fraction_is_taken(self) -> None:
        # The reference is the pattern area, not the page: a header eats into the
        # height, so 10%h shrinks with it.
        definition = (
            "version: 1\n"
            "page:\n  format: a4\n  margin: 10mm\n"
            "header:\n  height: 17mm\n  gap: 10mm\n"  # 27 mm off the height
            "generator: lines\n"
            "families:\n  - direction: horizontal\n    base_spacing: 10%h\n"
        )
        # 297 - 20 (margins) - 27 (header) = 250 mm, so 10%h is 25 mm.
        assert spacing_um(definition) == 25_000


class TestRefusal:
    def test_a_relative_margin_is_refused(self) -> None:
        # A margin *defines* the pattern area — it cannot be a fraction of it.
        definition = (
            "version: 1\n"
            "page:\n  format: a4\n  margin: 5%w\n"
            "generator: lines\n"
            "families:\n  - direction: vertical\n    base_spacing: 5mm\n"
        )
        with pytest.raises(DefinitionError) as excinfo:
            loads(definition, source="test")
        assert "%w" in str(excinfo.value)

    def test_a_relative_weight_is_refused(self) -> None:
        # A stroke weight is not spatial; it must not scale with the page.
        definition = (
            "version: 1\n"
            "page:\n  format: a4\n  margin: 10mm\n"
            "generator: lines\n"
            "families:\n"
            "  - direction: vertical\n    base_spacing: 5mm\n    base_weight: 1%w\n"
        )
        with pytest.raises(DefinitionError) as excinfo:
            loads(definition, source="test")
        assert "%w" in str(excinfo.value)


class TestOnTheSheet:
    def test_the_spacing_measures_the_fraction(self, tmp_path: Path) -> None:
        # Read the real PDF back: vertical lines every 10%w = 19 mm on A4.
        import pdfread

        path = tmp_path / "relative.pdf"
        build(loads(A4_VERTICAL.format(fmt="a4", measure="10%w"), source="test"), PdfWriter(path))
        xs = sorted({round(line.x1) for line in pdfread.lines_um(path) if line.is_vertical})
        gaps = {b - a for a, b in zip(xs, xs[1:], strict=False)}
        assert gaps == {19_000}
