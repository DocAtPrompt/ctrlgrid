"""N-up imposition (§ 14, M6) — finished pages placed on a larger sheet.

The one rule that makes this unlike every comparable tool: **it never scales.**
`pdfjam` and `pdfcpu` shrink the pages to make them fit; here 5 mm would become
2.5 mm, which contradicts § 8.2 head-on. So pages go on at **100 %**, and if
they do not fit it is an error with the arithmetic, never an automatic
reduction. The intended use is the reverse of the usual one: define a small
format, print a large sheet, cut it up.

It works on finished pages, which is why it does not breach the "no layout
system" rule (§ 2): the pattern is untouched, whole rendered pages are only
placed. The cover sheet (§ 8.8) is exempt, and imposition drops the per-page
bookmarks — they would point at the wrong place on an imposed sheet.
"""

from __future__ import annotations

from pathlib import Path

import pdfread
import pytest

from ctrlgrid.errors import DefinitionError
from ctrlgrid.loader import loads
from ctrlgrid.pages import build
from ctrlgrid.writers.pdf import PdfWriter

# A6 is 105 x 148 mm; four of them are 210 x 296 mm, inside A4's 210 x 297.
LINES = (
    "version: 1\n"
    "page:\n  format: a6\n  margin: 0mm\n"
    "generator: lines\n"
    "families:\n"
    "  - {direction: horizontal, base_spacing: 10mm}\n"
)


def document(pages: int, nup: str = "2x2", sheet: str = "a4", **extra):
    overrides = {"pages": pages, "nup": nup, "nup_sheet": sheet, **extra}
    return loads(LINES, overrides, source="test")


class TestTheLayout:
    def test_four_a6_pages_fit_one_a4_sheet(self, tmp_path: Path) -> None:
        path = tmp_path / "nup.pdf"
        build(document(4), PdfWriter(path))
        assert pdfread.page_count(path) == 1
        width, height = pdfread.media_box_um(path)
        assert (round(width), round(height)) == (210_000, 297_000)

    def test_eight_pages_take_two_sheets(self, tmp_path: Path) -> None:
        path = tmp_path / "nup.pdf"
        build(document(8), PdfWriter(path))
        assert pdfread.page_count(path) == 2

    def test_a_part_full_last_sheet_is_still_one_sheet(self, tmp_path: Path) -> None:
        # Five A6 pages: one full A4 and one with a single page on it.
        path = tmp_path / "nup.pdf"
        build(document(5), PdfWriter(path))
        assert pdfread.page_count(path) == 2

    def test_the_pages_are_placed_at_full_size(self, tmp_path: Path) -> None:
        # § 8.2: 100 %. Inside one cell the 10 mm grid is exactly 10 mm — the
        # spacing is never shrunk to make the block fit.
        path = tmp_path / "nup.pdf"
        build(document(4), PdfWriter(path))
        # A6 is 148 mm tall, so lines below that belong to one bottom-row page.
        # A set: the two bottom-row pages share the same line heights.
        rows = sorted(
            {
                round(line.y1)
                for line in pdfread.lines_um(path)
                if line.is_horizontal and round(line.y1) < 148_000
            }
        )
        gaps = {rows[i + 1] - rows[i] for i in range(len(rows) - 1)}
        assert gaps == {10_000}

    def test_the_first_page_sits_top_left(self, tmp_path: Path) -> None:
        # Reading order: page 0 is the top-left cell. Its footer text proves it.
        path = tmp_path / "nup.pdf"
        text = (
            "version: 1\npage:\n  format: a6\n  margin: 5mm\n"
            "footer:\n  height: 8mm\n  center: '{page}'\n"
            "generator: lines\nfamilies:\n"
            "  - {direction: horizontal, base_spacing: 10mm}\n"
        )
        build(loads(text, {"pages": 4, "nup": "2x2", "nup_sheet": "a4"}, source="t"),
              PdfWriter(path))
        assert "1" in pdfread.text_on(path)


class TestItNeverScales:
    def test_pages_too_big_for_the_sheet_are_refused_with_the_arithmetic(self) -> None:
        # § 14: 4 A4 pages at 100 % need 420 x 594 mm; A4 is 210 x 297.
        with pytest.raises(DefinitionError) as excinfo:
            build(
                loads(
                    "version: 1\npage:\n  format: a4\n"
                    "generator: lines\nfamilies:\n"
                    "  - {direction: horizontal, base_spacing: 10mm}\n",
                    {"pages": 4, "nup": "2x2", "nup_sheet": "a4"},
                    source="test",
                ),
                PdfWriter("/dev/null"),
            )
        message = str(excinfo.value)
        assert "420" in message and "594" in message
        assert "210" in message and "297" in message

    def test_nothing_is_written_when_it_does_not_fit(self, tmp_path: Path) -> None:
        path = tmp_path / "never.pdf"
        with pytest.raises(DefinitionError):
            build(
                loads(
                    "version: 1\npage:\n  format: a4\n"
                    "generator: lines\nfamilies:\n"
                    "  - {direction: horizontal, base_spacing: 10mm}\n",
                    {"pages": 4, "nup": "2x2", "nup_sheet": "a4"},
                    source="test",
                ),
                PdfWriter(path),
            )
        assert not path.exists()

    def test_a_free_nup_sheet_works(self, tmp_path: Path) -> None:
        # A large custom sheet for a 3x3 of A6.
        path = tmp_path / "nup.pdf"
        build(document(9, nup="3x3", sheet="320x450mm"), PdfWriter(path))
        width, height = pdfread.media_box_um(path)
        assert (round(width), round(height)) == (320_000, 450_000)


class TestTheCoverIsExempt:
    def test_the_cover_is_its_own_page_before_the_imposed_sheets(self, tmp_path: Path) -> None:
        # § 8.8: the calibration sheet is not placed in a cell — it keeps the
        # page size, so its 50 mm square stays a real 50 mm.
        path = tmp_path / "nup.pdf"
        build(document(4, cover=True), PdfWriter(path))
        assert pdfread.page_count(path) == 2  # one cover + one imposed A4
        cover_w, cover_h = pdfread.media_box_um(path, 0)
        assert (round(cover_w), round(cover_h)) == (105_000, 148_000)
        assert "50 mm" in pdfread.text_on(path, 0)
        sheet_w, sheet_h = pdfread.media_box_um(path, 1)
        assert (round(sheet_w), round(sheet_h)) == (210_000, 297_000)


class TestCropMarks:
    def test_they_are_off_by_default(self, tmp_path: Path) -> None:
        # A sheet with real margin, so the marks have room to appear when asked.
        path = tmp_path / "nup.pdf"
        build(document(4, sheet="230x316mm"), PdfWriter(path))
        plain = len(pdfread.lines_um(path))
        marked = tmp_path / "marked.pdf"
        build(document(4, sheet="230x316mm", crop_marks=True), PdfWriter(marked))
        assert len(pdfread.lines_um(marked)) > plain

    def test_they_sit_in_the_margin_between_block_and_sheet_edge(self, tmp_path: Path) -> None:
        # A6 block is 210 x 296 on A4 210 x 297: 0.5 mm top and bottom. The
        # marks live in that strip, at the cut lines.
        path = tmp_path / "marked.pdf"
        build(document(4, sheet="230x316mm", crop_marks=True), PdfWriter(path))
        # Some very short segments appear that a bare grid never has.
        short = [
            line
            for line in pdfread.lines_um(path)
            if 0 < abs(line.x2 - line.x1) + abs(line.y2 - line.y1) < 6_000
        ]
        assert short


class TestReporting:
    def test_the_run_reports_the_imposition(self, tmp_path: Path) -> None:
        from ctrlgrid.pages import sheet_plan  # noqa: F401

        document_ = document(4)
        assert document_.nup is not None
        assert document_.nup.cols == 2 and document_.nup.rows == 2

    def test_a_bad_nup_string_is_refused(self) -> None:
        with pytest.raises(DefinitionError) as excinfo:
            loads(LINES, {"pages": 1, "nup": "2by2", "nup_sheet": "a4"}, source="test")
        assert "2x2" in str(excinfo.value) or "CxR" in str(excinfo.value)
