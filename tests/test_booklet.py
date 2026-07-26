"""The sheet order: which page lands in which cell (§ 14).

`impose.slots` is the whole of booklet imposition that is not already there —
an order, and a front/back pairing. It knows no millimetres, so most of this
file needs no PDF at all: a fold order is arithmetic a binder can check.
"""

from __future__ import annotations

from pathlib import Path

import pdfread
import pytest

from ctrlgrid.errors import CtrlGridError, DefinitionError
from ctrlgrid.impose import Imposition, slots
from ctrlgrid.loader import loads
from ctrlgrid.pages import build
from ctrlgrid.writers.pdf import PdfWriter


def imposition(cols: int, rows: int, *, booklet: bool = False) -> Imposition:
    return Imposition(
        cols=cols,
        rows=rows,
        sheet_width=210_000,
        sheet_height=297_000,
        sheet_name="a4",
        booklet=booklet,
    )


class TestPlainNup:
    """Reading order, in blocks — what `_write_imposed` did by hand."""

    def test_four_pages_on_one_two_by_two_sheet(self) -> None:
        assert slots(4, imposition(2, 2)) == [[0, 1, 2, 3]]

    def test_a_part_full_last_sheet_leaves_empty_cells(self) -> None:
        # Five pages on 2x2: the sixth, seventh and eighth cells hold nothing.
        assert slots(5, imposition(2, 2)) == [[0, 1, 2, 3], [4, None, None, None]]


class TestTheFoldOrder:
    """§ 14: sheet *i* carries (P-2i, 2i+1) on its front and (2i+2, P-2i-1) on
    its back, with P the count rounded up to a multiple of four. The numbers
    below are 1-based page numbers turned into 0-based indices by hand, so the
    test states the binder's rule and not the code's arithmetic."""

    def test_eight_pages_are_the_classic_order(self) -> None:
        # Pages 8-1, 2-7, 6-3, 4-5 — front and back of two sheets, interleaved.
        assert slots(8, imposition(2, 1, booklet=True)) == [
            [7, 0],
            [1, 6],
            [5, 2],
            [3, 4],
        ]

    def test_six_pages_are_padded_to_eight_and_the_blanks_are_the_outer_leaf(
        self,
    ) -> None:
        # Six pages still need two sheets; pages 7 and 8 do not exist, so the
        # cells that would hold them stay empty — and they are the two halves
        # of the outermost leaf, which is where a binder expects the blanks.
        assert slots(6, imposition(2, 1, booklet=True)) == [
            [None, 0],
            [1, None],
            [5, 2],
            [3, 4],
        ]

    @pytest.mark.parametrize("pages", [4, 8, 12, 16, 20, 40])
    def test_every_page_appears_exactly_once(self, pages: int) -> None:
        placed = [
            index
            for sheet in slots(pages, imposition(2, 1, booklet=True))
            for index in sheet
            if index is not None
        ]
        assert sorted(placed) == list(range(pages))

    @pytest.mark.parametrize("pages", [5, 6, 7, 9, 30])
    def test_the_two_numbers_on_a_sheet_side_always_sum_to_p_plus_one(
        self, pages: int
    ) -> None:
        # The rule a binder recognises a fold order by: on any side of any
        # sheet, the two page numbers add up to one more than the total. It is
        # an independent second opinion on the formula, the way math.log10 is
        # for the logarithmic axis.
        padded = -(-pages // 4) * 4
        for side in slots(pages, imposition(2, 1, booklet=True)):
            # 0-based indices back to 1-based page numbers; a blank stands for
            # a padded page, whose number the sum would still need.
            known = [index + 1 for index in side if index is not None]
            if len(known) == 2:
                assert sum(known) == padded + 1, side

    def test_the_sheet_count_is_the_padded_page_count_over_two(self) -> None:
        # Two sides per physical sheet, four pages per sheet: 30 pages padded
        # to 32 is 8 sheets, so 16 sides in the PDF.
        assert len(slots(30, imposition(2, 1, booklet=True))) == 16


# A5 is 148 x 210 mm; two side by side are 296 x 210, which needs a landscape
# sheet. `--nup-sheet` takes a free size, so the sheet is written out.
A5_LINES = (
    "version: 1\n"
    "page:\n  format: a5\n  margin: 0mm\n"
    "generator: lines\n"
    "families:\n"
    "  - {direction: horizontal, base_spacing: 10mm}\n"
)


def booklet(pages: int, **extra):
    overrides = {
        "pages": pages,
        "booklet": True,
        "nup_sheet": "297x210mm",
        **extra,
    }
    return loads(A5_LINES, overrides, source="test")


class TestTheRun:
    def test_eight_pages_come_out_as_four_sheet_sides(self, tmp_path: Path) -> None:
        path = tmp_path / "b.pdf"
        build(booklet(8), PdfWriter(path))
        assert pdfread.page_count(path) == 4
        width, height = pdfread.media_box_um(path)
        assert (round(width), round(height)) == (297_000, 210_000)

    def test_six_pages_still_take_two_sheets(self, tmp_path: Path) -> None:
        path = tmp_path / "b.pdf"
        build(booklet(6), PdfWriter(path))
        assert pdfread.page_count(path) == 4

    def test_booklet_and_nup_together_are_refused(self) -> None:
        from ctrlgrid.cli import _overrides

        with pytest.raises(CtrlGridError) as excinfo:
            _overrides(None, None, None, None, nup="2x2", booklet=True)
        assert "--booklet" in str(excinfo.value) and "--nup" in str(excinfo.value)

    def test_a_document_generator_refuses_the_booklet_by_name(
        self, tmp_path: Path
    ) -> None:
        text = (
            "version: 1\n"
            "page: {format: a5, margin: 10mm}\n"
            "generator: notebook\n"
            "sections:\n"
            "  - {label: 'Dots', pages: 2, generator: dots,\n"
            "     grid: {x: {base_spacing: 5mm}, y: {base_spacing: 5mm}}}\n"
        )
        with pytest.raises(DefinitionError) as excinfo:
            build(
                loads(text, {"booklet": True, "nup_sheet": "297x210mm"}, source="t"),
                PdfWriter(tmp_path / "never-written.pdf"),
            )
        assert "--booklet" in str(excinfo.value)

    def test_a_portrait_sheet_is_refused_with_the_landscape_hint(
        self, tmp_path: Path
    ) -> None:
        # Two A5 pages need 296 mm of width; A4 portrait has 210. The message
        # has to name the sheet that would work, or the user is left doing the
        # arithmetic the tool just did (§ 12). The named size is the block
        # itself — 296 x 210 — which is a legal free size and fits exactly;
        # A4 landscape (297 x 210) is the same sheet with a millimetre spare.
        with pytest.raises(DefinitionError) as excinfo:
            build(
                loads(A5_LINES, {"pages": 4, "booklet": True}, source="t"),
                PdfWriter(tmp_path / "never-written.pdf"),
            )
        assert "296x210mm" in str(excinfo.value)


class TestTheReport:
    def test_it_names_the_padding_the_sheets_and_the_turning_edge(
        self, tmp_path: Path
    ) -> None:
        # § 8.2's discipline: name the setting, do not say "mind the flip".
        from typer.testing import CliRunner

        from ctrlgrid.cli import app

        definition = tmp_path / "d.yaml"
        definition.write_text(A5_LINES, encoding="utf-8")
        result = CliRunner().invoke(
            app,
            ["-d", str(definition), "--pages", "6", "--booklet",
             "--nup-sheet", "297x210mm", "-o", str(tmp_path / "b.pdf")],
        )
        assert result.exit_code == 0, result.output
        assert "padded to 8" in result.output
        assert "2 sheet(s)" in result.output
        assert "SHORT edge" in result.output
        assert "page 2" in result.output

    def report_for(self, tmp_path: Path, definition: str) -> str:
        from typer.testing import CliRunner

        from ctrlgrid.cli import app

        path = tmp_path / "d.yaml"
        path.write_text(definition, encoding="utf-8")
        result = CliRunner().invoke(
            app,
            ["-d", str(path), "--pages", "8", "--booklet",
             "--nup-sheet", "297x210mm", "-o", str(tmp_path / "b.pdf")],
        )
        assert result.exit_code == 0, result.output
        return result.output

    def test_pages_without_numbers_are_told_how_to_check_the_flip(
        self, tmp_path: Path
    ) -> None:
        # § 12: an instruction the user cannot act on is a bug. "Page 2 must be
        # behind page 1" is exactly that on blank grid paper, which is the
        # commonest thing this tool makes — no number is printed anywhere.
        output = self.report_for(tmp_path, A5_LINES)
        assert "{page}" in output

    def test_pages_that_carry_their_number_are_not_told_twice(
        self, tmp_path: Path
    ) -> None:
        # The sheet already answers it, so the advice would be noise. The tool
        # can tell: a band field holding `{page}` is the only way a blade's page
        # gets a number on it.
        output = self.report_for(tmp_path, NUMBERED)
        assert "SHORT edge" in output
        assert "{page}" not in output


NUMBERED = (
    "version: 1\n"
    "page:\n  format: a5\n  margin: 10mm\n"
    "footer:\n  height: 8mm\n  gap: 2mm\n  center: '{page}'\n"
    "generator: lines\n"
    "families:\n"
    "  - {direction: horizontal, base_spacing: 10mm}\n"
)


class TestTheSheetsThemselves:
    """The order, read off the artefact rather than out of the function."""

    def sides(self, path: Path) -> list[list[str]]:
        """Each sheet side as [left page number, right page number]."""
        found = []
        for index in range(pdfread.page_count(path)):
            numbers = [
                text for text in pdfread.texts_um(path, index)
                if text.content.isdigit()
            ]
            found.append([t.content for t in sorted(numbers, key=lambda t: t.x)])
        return found

    def sheet(self, tmp_path: Path, pages: int, name: str = "b.pdf") -> Path:
        path = tmp_path / name
        build(
            loads(NUMBERED, {"pages": pages, "booklet": True,
                             "nup_sheet": "297x210mm"}, source="t"),
            PdfWriter(path),
        )
        return path

    def test_eight_pages_fold_into_eight_one_two_seven_six_three_four_five(
        self, tmp_path: Path
    ) -> None:
        assert self.sides(self.sheet(tmp_path, 8)) == [
            ["8", "1"], ["2", "7"], ["6", "3"], ["4", "5"],
        ]

    def test_a_padded_cell_draws_nothing_at_all(self, tmp_path: Path) -> None:
        # Not an empty page — the absence of one. A footer reading "7" on a
        # leaf nobody filled would claim content that does not exist.
        assert self.sides(self.sheet(tmp_path, 6)) == [
            ["1"], ["2"], ["6", "3"], ["4", "5"],
        ]

    def test_two_runs_are_byte_identical(self, tmp_path: Path) -> None:
        # § 10.1, and it is checked whenever anything is added to the writer.
        first = self.sheet(tmp_path, 6, "1.pdf")
        second = self.sheet(tmp_path, 6, "2.pdf")
        assert first.read_bytes() == second.read_bytes()
