"""`snap: pixel` — the one exception to dimensional accuracy (§ 8.3.1).

On a raster screen the nominal size is not exactly drawable: a 5 mm cell is
45.08 px at 229 dpi, so the device draws alternately 45 and 46 px and the grid
looks uneven though it is computed exactly. The user then has two evils and
both are legitimate — `none` keeps 5.000 mm and uneven cells, `pixel` keeps
even cells at 4.991 mm — so it is an option and never the default: the tool may
not make that trade for the user, but it must offer it and say what it costs.

Rules § 8.3.1 fixes: only with a device profile; every *step* rounded, not just
the base, so fractional cycle multiples still land on whole pixels; the actual
measure reported unprompted in both units; and it cancels the "positions not on
whole pixels" finding of § 12.1, which is its whole purpose.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ctrlgrid.errors import DefinitionError
from ctrlgrid.loader import loads
from ctrlgrid.marks import Segment
from ctrlgrid.pages import build, preflight
from ctrlgrid.writers.pdf import PdfWriter

Q = PdfWriter("unused.pdf")

# 1 px at 229 dpi = 25400/229 = 110.917 µm (kept exact, not rounded to a whole
# µm). 5 mm = 45.08 px → 45 px = 4991 µm.
PIXEL = 25400 / 229
DEVICE = "version: 1\npage:\n  device: remarkable-paper-pro\n"


def on_pixel(um: int) -> bool:
    """Whether a micrometre position is a whole number of device pixels.

    The tolerance is 0.01 px: a position is stored to the whole micrometre, and
    one µm is 1/110.9 = 0.009 px, so the rounding to µm is the only slack.
    """
    return abs(um / PIXEL - round(um / PIXEL)) < 0.01


def pixels(um: int) -> int:
    return round(um / PIXEL)


def rows(definition: str) -> list[int]:
    document = loads(definition, source="test")
    from ctrlgrid.pages import page_contexts

    geometry = preflight(document, Q)[0]
    page = next(page_contexts(count=1, snap=geometry.pixel_snap))
    from ctrlgrid import generators

    marks = generators.get(document.generator).generate(
        document.config, area=geometry.area, page=page, q=Q
    )
    return [m.start.y for m in marks if isinstance(m, Segment) and m.start.y == m.end.y]


class TestOnlyWithADevice:
    def test_pixel_on_paper_is_an_error(self) -> None:
        with pytest.raises(DefinitionError) as excinfo:
            preflight(
                loads(
                    "version: 1\npage:\n  format: a4\n"
                    "pattern:\n  snap: pixel\ngenerator: lines\nfamilies:\n"
                    "  - {direction: horizontal, base_spacing: 5mm, base_weight: 0.6pt}\n",
                    source="test",
                ),
                Q,
            )
        message = str(excinfo.value)
        assert "pixel" in message and "device" in message

    def test_pixel_no_longer_names_a_milestone(self) -> None:
        with pytest.raises(DefinitionError) as excinfo:
            preflight(
                loads(
                    "version: 1\npage:\n  format: a4\n"
                    "pattern:\n  snap: pixel\ngenerator: lines\nfamilies:\n"
                    "  - {direction: horizontal, base_spacing: 5mm, base_weight: 0.6pt}\n",
                    source="test",
                ),
                Q,
            )
        assert "M5" not in str(excinfo.value)


class TestRoundingEveryStep:
    def test_every_position_lands_on_a_whole_pixel(self) -> None:
        drawn = rows(
            DEVICE + "pattern:\n  snap: pixel\ngenerator: lines\nfamilies:\n"
            "  - {direction: horizontal, base_spacing: 5mm, base_weight: 0.6pt}\n"
        )
        assert drawn
        assert all(on_pixel(position) for position in drawn)

    def test_the_cells_are_uniform(self) -> None:
        # The point of § 8.3.1: 45 px each, not alternating 45/46.
        drawn = sorted(
            rows(
                DEVICE + "pattern:\n  snap: pixel\ngenerator: lines\nfamilies:\n"
                "  - {direction: horizontal, base_spacing: 5mm, base_weight: 0.6pt}\n"
            )
        )
        # Every cell is 45 pixels — uniform, not alternating 45/46.
        gaps = {pixels(drawn[i + 1] - drawn[i]) for i in range(len(drawn) - 1)}
        assert gaps == {45}

    def test_a_fractional_cycle_still_lands_on_whole_pixels(self) -> None:
        # § 8.3.1: every step rounded, not just the base — so [1, 1.5] works.
        drawn = rows(
            DEVICE + "pattern:\n  snap: pixel\ngenerator: lines\nfamilies:\n"
            "  - {direction: horizontal, base_spacing: 5mm, spacing: [1, 1.5], "
            "base_weight: 0.6pt}\n"
        )
        assert all(on_pixel(position) for position in drawn)

    def test_none_keeps_the_exact_nominal_size(self) -> None:
        # The other legitimate evil: exact 5.000 mm, uneven on the pixel grid.
        drawn = sorted(
            rows(
                DEVICE + "generator: lines\nfamilies:\n"
                "  - {direction: horizontal, base_spacing: 5mm, base_weight: 0.6pt}\n"
            )
        )
        assert drawn[1] - drawn[0] == 5_000

    def test_it_can_be_set_on_one_axis_only(self) -> None:
        document = loads(
            DEVICE + "pattern:\n  snap: {x: pixel, y: none}\ngenerator: dots\n"
            "grid:\n  x: {base_spacing: 5mm}\n  y: {base_spacing: 5mm}\n"
            "base_size: 0.3mm\n",
            source="test",
        )
        geometry = preflight(document, Q)[0]
        from ctrlgrid import generators
        from ctrlgrid.marks import Dot
        from ctrlgrid.pages import page_contexts

        page = next(page_contexts(count=1, snap=geometry.pixel_snap))
        dots = [
            m
            for m in generators.get("dots").generate(
                document.config, area=geometry.area, page=page, q=Q
            )
            if isinstance(m, Dot)
        ]
        assert all(on_pixel(dot.pos.x) for dot in dots)
        # y is not snapped, so 5 mm stays exactly 5000 µm, off the pixel grid.
        assert any(not on_pixel(dot.pos.y) for dot in dots)


class TestReporting:
    def test_the_actual_measure_is_reported_in_both_units(self) -> None:
        # § 8.3.1: unprompted, "5mm → 4.991mm (45px at 229dpi)".
        geometry = preflight(
            loads(
                DEVICE + "pattern:\n  snap: pixel\ngenerator: lines\nfamilies:\n"
                "  - {direction: horizontal, base_spacing: 5mm, base_weight: 0.6pt}\n",
                source="test",
            ),
            Q,
        )[0]
        text = "\n".join(geometry.notices)
        assert "4.991mm" in text and "45px" in text and "229dpi" in text

    def test_it_cancels_the_uneven_cells_finding(self) -> None:
        # § 8.3.1: snapping to pixels is exactly what removes that § 12.1 note.
        geometry = preflight(
            loads(
                DEVICE + "pattern:\n  snap: pixel\ngenerator: lines\nfamilies:\n"
                "  - {direction: horizontal, base_spacing: 5mm, base_weight: 0.6pt}\n",
                source="test",
            ),
            Q,
        )[0]
        assert not any("uneven" in note or "alternately" in note for note in geometry.notices)


class TestOnTheSheet:
    def test_it_reaches_the_pdf_and_repeats_identically(self, tmp_path: Path) -> None:
        first, second = tmp_path / "a.pdf", tmp_path / "b.pdf"
        definition = (
            DEVICE + "pattern:\n  snap: pixel\ngenerator: dots\n"
            "grid:\n  x: {base_spacing: 5mm}\n  y: {base_spacing: 5mm}\n"
            "base_size: 0.4mm\n"
        )
        for path in (first, second):
            build(loads(definition, source="test"), PdfWriter(path))
        assert first.read_bytes() == second.read_bytes()
