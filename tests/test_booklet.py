"""The sheet order: which page lands in which cell (§ 14).

`impose.slots` is the whole of booklet imposition that is not already there —
an order, and a front/back pairing. It knows no millimetres, so most of this
file needs no PDF at all: a fold order is arithmetic a binder can check.
"""

from __future__ import annotations

from ctrlgrid.impose import Imposition, slots


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
