"""The test the whole project exists for (§ 13.2).

Generate a PDF, read it back with pypdf, and check MediaBox and mark
coordinates against expected values — to 1 µm. Golden comparisons check parsed
geometry, never bytes, so a reportlab update cannot break the suite.

M1 acceptance criterion 2 (§ 14) is exactly this test passing for
`millimeter-a4`: MediaBox 210 x 297 mm, line spacing 1.000 mm, every fifth line
emphasised. Criterion 3 — byte-identical repeat runs — sits alongside it,
because it is the other one that cannot be retrofitted without rebuilding.

Written before the code it checks, on purpose. Retrofitted, this test finds
nothing: by then the expected values would be derived from the actual output.
"""

from __future__ import annotations

from pathlib import Path

import pdfread
import pytest

from ctrlgrid.loader import load_preset
from ctrlgrid.pages import build
from ctrlgrid.writers.pdf import PdfWriter

MM = 1000


@pytest.fixture(scope="module")
def millimeter_a4(tmp_path_factory: pytest.TempPathFactory) -> Path:
    path = tmp_path_factory.mktemp("dimensional") / "millimeter-a4.pdf"
    document = load_preset("millimeter-a4", {"pages": 3})
    build(document, PdfWriter(path))
    return path


class TestTheSheet:
    def test_the_media_box_is_a4_to_the_micrometre(self, millimeter_a4: Path) -> None:
        width, height = pdfread.media_box_um(millimeter_a4)
        assert width == pytest.approx(210 * MM, abs=1)
        assert height == pytest.approx(297 * MM, abs=1)

    def test_three_pages_were_asked_for_and_three_arrived(self, millimeter_a4: Path) -> None:
        assert pdfread.page_count(millimeter_a4) == 3


class TestTheGrid:
    def test_the_lines_sit_exactly_one_millimetre_apart(self, millimeter_a4: Path) -> None:
        # The one promise (§ 1): what says 1 mm measures 1 mm.
        ys = sorted({line.y1 for line in pdfread.lines_um(millimeter_a4) if line.is_horizontal})
        gaps = [second - first for first, second in zip(ys, ys[1:], strict=False)]
        assert all(gap == pytest.approx(1 * MM, abs=1) for gap in gaps)

    def test_the_grid_starts_at_the_margin(self, millimeter_a4: Path) -> None:
        # § 8.1: the pattern area begins at the non-printable border, and the
        # first mark of a family sits on its origin.
        ys = sorted({line.y1 for line in pdfread.lines_um(millimeter_a4) if line.is_horizontal})
        assert ys[0] == pytest.approx(5 * MM, abs=1)

    def test_the_grid_fills_the_pattern_area_and_stops(self, millimeter_a4: Path) -> None:
        ys = sorted({line.y1 for line in pdfread.lines_um(millimeter_a4) if line.is_horizontal})
        assert ys[-1] == pytest.approx(292 * MM, abs=1)
        assert len(ys) == 288  # 5 mm .. 292 mm inclusive, one per millimetre

    def test_horizontal_lines_span_the_content_width(self, millimeter_a4: Path) -> None:
        line = next(line for line in pdfread.lines_um(millimeter_a4) if line.is_horizontal)
        assert line.x1 == pytest.approx(5 * MM, abs=1)
        assert line.x2 == pytest.approx(205 * MM, abs=1)

    def test_the_vertical_family_is_there_too(self, millimeter_a4: Path) -> None:
        xs = sorted({line.x1 for line in pdfread.lines_um(millimeter_a4) if line.is_vertical})
        assert len(xs) == 201  # 5 mm .. 205 mm inclusive
        assert xs[1] - xs[0] == pytest.approx(1 * MM, abs=1)

    def test_every_fifth_line_is_emphasised(self, millimeter_a4: Path) -> None:
        # § 1.1: the single most implemented feature of every comparable tool,
        # here as the ordinary case of the cycle mechanism.
        horizontals = [line for line in pdfread.lines_um(millimeter_a4) if line.is_horizontal]
        thin = 0.15 * 25.4 / 72
        for position, line in enumerate(horizontals[:11]):
            expected = thin * 2.7 if position % 5 == 4 else thin
            assert line.width_mm == pytest.approx(expected, abs=1e-4)


class TestReproducibility:
    def test_the_same_command_twice_gives_the_same_bytes(self, tmp_path: Path) -> None:
        # Acceptance criterion 3 (§ 14), and the reason the writer fixes the
        # creation date and the document ID (§ 10.1).
        outputs = []
        for run in ("first", "second"):
            path = tmp_path / f"{run}.pdf"
            build(load_preset("millimeter-a4", {"pages": 2}), PdfWriter(path))
            outputs.append(path.read_bytes())
        assert outputs[0] == outputs[1]

    def test_the_pdf_carries_no_wall_clock_time(self, tmp_path: Path) -> None:
        from pypdf import PdfReader

        path = tmp_path / "meta.pdf"
        build(load_preset("millimeter-a4"), PdfWriter(path))
        info = PdfReader(str(path)).metadata
        assert info is not None
        assert str(info.get("/CreationDate", "")).startswith("D:2000")


class TestOtherFormats:
    def test_the_same_definition_on_letter_keeps_its_millimetres(self, tmp_path: Path) -> None:
        # § 8.1: the format is the base, everything else is relative to it —
        # so it can be exchanged without touching the definition.
        path = tmp_path / "letter.pdf"
        build(load_preset("millimeter-a4", {"format": "letter"}), PdfWriter(path))
        width, height = pdfread.media_box_um(path)
        assert (width, height) == (pytest.approx(215900, abs=1), pytest.approx(279400, abs=1))

        ys = sorted({line.y1 for line in pdfread.lines_um(path) if line.is_horizontal})
        assert ys[1] - ys[0] == pytest.approx(1 * MM, abs=1)

    def test_landscape_swaps_the_sheet_but_not_the_spacing(self, tmp_path: Path) -> None:
        path = tmp_path / "landscape.pdf"
        build(load_preset("millimeter-a4", {"orientation": "landscape"}), PdfWriter(path))
        width, height = pdfread.media_box_um(path)
        assert width == pytest.approx(297 * MM, abs=1)
        assert height == pytest.approx(210 * MM, abs=1)
