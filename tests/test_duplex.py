"""Double-sided printing: inner and outer swap on even pages (§ 8.1).

The point of naming the margins `inner` and `outer` rather than `left` and
`right` is exactly this — the wider margin stays at the binding edge whichever
side of the sheet you are on. On front pages `inner` is the left one.

The pattern area keeps its size and only moves, which matters for § 3.3:
snapping is solved once for both page sorts, never per page. Solved per page it
could come out differently on the two sides, and that is precisely what you
would see when leafing through the stack.
"""

from __future__ import annotations

from pathlib import Path

import pdfread
import pytest

from ctrlgrid.loader import loads
from ctrlgrid.pages import Geometry, build, is_page_invariant, page_contexts
from ctrlgrid.writers.pdf import PdfWriter

# `remainder: end` so these tests measure the swap and nothing else: with the
# default `center` the 185 mm content width would also shift the grid by half
# its 5 mm surplus, which is tested in test_remainder.py and only obscures
# things here.
LOPSIDED = """
version: 1
page:
  format: a4
  duplex: true
  margin: {top: 5mm, bottom: 5mm, inner: 20mm, outer: 5mm}
pattern:
  remainder: end
pages:
  count: 4
generator: lines
families:
  - {direction: horizontal, base_spacing: 10mm}
  - {direction: vertical, base_spacing: 10mm}
"""


def document(text: str = LOPSIDED):
    return loads(text, source="test")


def geometries(text: str = LOPSIDED) -> tuple[Geometry, Geometry]:
    """The geometry of a front page and of a back page."""
    doc = document(text)
    front = Geometry.of(
        doc.sheet,
        header=doc.header,
        footer=doc.footer,
        pattern=doc.pattern,
        blade_axes=doc.axes,
    )
    return front, front.for_page(is_even=True, sheet=doc.sheet, duplex=doc.page.duplex)


class TestTheSwap:
    def test_a_front_page_puts_the_inner_margin_on_the_left(self) -> None:
        front, _ = geometries()
        assert front.origin.x == 20000

    def test_a_back_page_puts_the_outer_margin_on_the_left(self) -> None:
        _, back = geometries()
        assert back.origin.x == 5000

    def test_the_binding_edge_keeps_the_wider_margin_on_both_sides(self) -> None:
        # Front: 20 mm of white to the left of the pattern. Back: 20 mm to the
        # right of it. Stacked and bound, the wide margins meet at the spine.
        front, back = geometries()
        sheet_width = document().sheet.width
        assert front.origin.x == 20000
        assert sheet_width - (back.origin.x + back.area.width) == 20000

    def test_the_bands_move_with_the_pattern(self) -> None:
        text = LOPSIDED.replace(
            "pages:", "header:\n  height: 12mm\n  gap: 4mm\n  center: 'x'\npages:"
        )
        front, back = geometries(text)
        assert front.header is not None and back.header is not None
        assert front.header.left == 20000
        assert back.header.left == 5000


class TestWhatDoesNotChange:
    def test_the_pattern_area_keeps_its_size(self) -> None:
        # § 8.1: content_width = page - inner - outer, whichever way round.
        front, back = geometries()
        assert front.area == back.area

    def test_the_vertical_position_is_untouched(self) -> None:
        front, back = geometries()
        assert front.origin.y == back.origin.y

    def test_equal_margins_leave_nothing_to_swap(self) -> None:
        front, back = geometries(LOPSIDED.replace("inner: 20mm", "inner: 5mm"))
        assert front.origin == back.origin

    def test_without_duplex_both_sides_are_alike(self) -> None:
        # § 8.1: with duplex off, `inner` is simply always the left one.
        front, back = geometries(LOPSIDED.replace("duplex: true", "duplex: false"))
        assert front.origin == back.origin


class TestSnappingIsSolvedOnce:
    def test_both_page_sorts_snap_to_the_same_size(self) -> None:
        # § 3.3: solved once for both sorts, not per page — otherwise the two
        # sides could resolve differently, and that is what leafing through
        # would show.
        snapped = LOPSIDED.replace("  remainder: end", "  remainder: end\n  snap: cycle")
        front, back = geometries(snapped)
        assert front.area == back.area

    def test_the_surplus_is_placed_the_same_way_on_both(self) -> None:
        snapped = LOPSIDED.replace("  remainder: end", "  remainder: end\n  snap: cycle")
        front, back = geometries(snapped)
        assert front.origin.y == back.origin.y


class TestPageInvariance:
    def test_duplex_makes_the_pattern_page_dependent_whatever_the_blade_says(self) -> None:
        # § 3.3: the writer may store a page-invariant pattern once and
        # reference it per page (§ 10.1). Under duplex it must not, because the
        # pattern sits somewhere else on every other sheet.
        doc = document()
        from ctrlgrid import generators

        assert generators.get(doc.generator).is_page_invariant(doc.config) is True
        assert is_page_invariant(doc) is False

    def test_without_duplex_the_blade_decides(self) -> None:
        doc = document(LOPSIDED.replace("duplex: true", "duplex: false"))
        assert is_page_invariant(doc) is True


@pytest.fixture(scope="module")
def pdf(tmp_path_factory: pytest.TempPathFactory) -> Path:
    path = tmp_path_factory.mktemp("duplex") / "duplex.pdf"
    build(document(), PdfWriter(path))
    return path


class TestOnTheSheet:
    def test_the_grid_starts_at_the_inner_margin_on_page_one(self, pdf: Path) -> None:
        xs = sorted({round(line.x1) for line in pdfread.lines_um(pdf, 0) if line.is_vertical})
        assert xs[0] == pytest.approx(20000, abs=1)
        assert xs[-1] == pytest.approx(200000, abs=1)

    def test_and_at_the_outer_margin_on_page_two(self, pdf: Path) -> None:
        xs = sorted({round(line.x1) for line in pdfread.lines_um(pdf, 1) if line.is_vertical})
        assert xs[0] == pytest.approx(5000, abs=1)
        assert xs[-1] == pytest.approx(185000, abs=1)

    def test_page_three_looks_like_page_one_again(self, pdf: Path) -> None:
        first = sorted({round(line.x1) for line in pdfread.lines_um(pdf, 0) if line.is_vertical})
        third = sorted({round(line.x1) for line in pdfread.lines_um(pdf, 2) if line.is_vertical})
        assert first == third

    def test_the_rows_sit_at_the_same_height_on_both_sides(self, pdf: Path) -> None:
        front = sorted({round(line.y1) for line in pdfread.lines_um(pdf, 0) if line.is_horizontal})
        back = sorted({round(line.y1) for line in pdfread.lines_um(pdf, 1) if line.is_horizontal})
        assert front == back


class TestTheContext:
    def test_even_pages_are_the_ones_that_swap(self) -> None:
        # `is_even` is about the printed page number, so sheet 1 is a front.
        assert [c.is_even for c in page_contexts(count=4)] == [False, True, False, True]
