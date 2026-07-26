"""N-up imposition (§ 14, M6) — finished pages placed on a larger sheet.

**It never scales**, and that is the whole point. Every comparable tool shrinks
the pages to make them fit; here 5 mm would become 2.5 mm, which contradicts
§ 8.2 head-on. So pages go on at 100 %, and if the block does not fit the sheet
it is an error with the arithmetic, never an automatic reduction. The intended
use is the reverse of the usual one: define a small format, print a large
sheet, cut it up.

It works on *finished* pages, which is why it does not breach the "no layout
system" rule (§ 2): the pattern is untouched — whole rendered pages are only
translated onto a bigger sheet. The block of pages is centred, so the leftover
becomes an even margin on every side, and optional crop marks sit in it at the
cut lines.

This module is pure geometry: it says where each page goes and where the cut
marks are. The page loop in `pages.py` does the placing, and the writer never
learns that imposition happened — it draws translated marks like any other.
"""

from __future__ import annotations

from dataclasses import dataclass

from ctrlgrid.errors import DefinitionError
from ctrlgrid.marks import Layer, Point, Segment, Um

#: How far a crop mark reaches into the margin, and how far it is held off the
#: page edge so the cut line itself stays clean. The *length* is clamped to the
#: margin actually available, so a tight sheet gets shorter marks; the gap is
#: fixed, and a margin narrower than it gets no marks on that pair of edges at
#: all rather than a mark drawn over a page (see `_tick`).
MARK_LENGTH = 4_000
MARK_GAP = 1_000
MARK_WEIGHT = 0.2


@dataclass(frozen=True, slots=True)
class Imposition:
    """An `--nup CxR` request with its sheet (§ 14, M6)."""

    cols: int
    rows: int
    sheet_width: Um
    sheet_height: Um
    sheet_name: str
    crop_marks: bool = False
    #: § 14: saddle-stitch order rather than reading order. A booklet *is* a
    #: 2x1 imposition, so no geometry changes — `cell`, `check_fits` and
    #: `crop_mark_segments` never read this. Only `slots` does, which is why it
    #: sits on the request beside `crop_marks` and not in the geometry.
    booklet: bool = False

    @property
    def per_sheet(self) -> int:
        return self.cols * self.rows

    def check_fits(self, page_width: Um, page_height: Um) -> None:
        """§ 14: refuse with the arithmetic rather than shrink to fit.

        The message is the one the specification writes out verbatim — the
        block size the pages need at 100 %, and the sheet that cannot hold it.
        """
        block_w = self.cols * page_width
        block_h = self.rows * page_height
        if block_w <= self.sheet_width and block_h <= self.sheet_height:
            return
        raise DefinitionError(
            f"{self.cols}x{self.rows} pages at 100 % need {_mm(block_w)} x {_mm(block_h)}, "
            f"sheet {self.sheet_name} is {_mm(self.sheet_width)} x {_mm(self.sheet_height)} "
            "— imposition never scales (§ 8.2, § 14). Use a larger --nup-sheet, a smaller "
            "page format, or a smaller --nup",
            field="nup",
        )

    def cell(self, position: int, page_width: Um, page_height: Um) -> Point:
        """Where the bottom-left of page `position` in a sheet sits (§ 14).

        Reading order: position 0 is the top-left cell. In PDF coordinates the
        origin is bottom-left, so the top row has the greatest y.
        """
        block_w = self.cols * page_width
        block_h = self.rows * page_height
        margin_x = (self.sheet_width - block_w) // 2
        margin_y = (self.sheet_height - block_h) // 2
        col = position % self.cols
        row_from_top = position // self.cols
        return Point(
            margin_x + col * page_width,
            margin_y + (self.rows - 1 - row_from_top) * page_height,
        )

    def crop_mark_segments(self, page_width: Um, page_height: Um) -> list[Segment]:
        """Cut guides in the margin, at every page-block grid line (§ 14).

        Drawn only where there is margin to hold them, so a block that fills the
        sheet in one direction simply has no marks on that pair of edges. They
        are cut *guides*, not a frame: short ticks reaching in from the sheet
        edge towards each cut line, never crossing the pages themselves.
        """
        if not self.crop_marks:
            return []

        block_w = self.cols * page_width
        block_h = self.rows * page_height
        left = (self.sheet_width - block_w) // 2
        bottom = (self.sheet_height - block_h) // 2
        right = left + block_w
        top = bottom + block_h

        segments: list[Segment] = []
        # Vertical cut lines (between columns and at the two ends): a tick down
        # from the bottom edge and up from the top edge, in the margin strips.
        for col in range(self.cols + 1):
            x = left + col * page_width
            segments += _tick(x, bottom, -1, vertical=True, room=bottom)
            segments += _tick(x, top, +1, vertical=True, room=self.sheet_height - top)
        # Horizontal cut lines: a tick in from the left and right edges.
        for row in range(self.rows + 1):
            y = bottom + row * page_height
            segments += _tick(left, y, -1, vertical=False, room=left)
            segments += _tick(right, y, +1, vertical=False, room=self.sheet_width - right)
        return segments


def slots(page_count: int, imposition: Imposition) -> list[list[int | None]]:
    """For every sheet side, which rendered page goes in which cell (§ 14).

    `None` means the cell stays empty — a part-full last sheet in plain n-up,
    or a blank leaf in a booklet. Both kinds of imposition are described here
    and nowhere else: a second description of "what is on this sheet" would
    drift from this one the first time either changed, which this codebase has
    now learnt four times over (`layout_band`, the writer wrapper,
    `document_page_marks`, `page_furniture`).

    Indices are into the rendered pages, 0-based. Position within a sheet is
    the one `Imposition.cell` numbers: 0 is top-left, reading order.
    """
    if imposition.booklet:
        return _folded(page_count)
    per = imposition.per_sheet
    return [
        [index if index < page_count else None for index in range(start, start + per)]
        for start in range(0, max(page_count, 1), per)
    ]


def _folded(page_count: int) -> list[list[int | None]]:
    """Saddle stitch: every sheet nested inside the next (§ 14).

    With *P* the page count rounded up to a multiple of four — a folded sheet
    carries four pages, so the count cannot be anything else — sheet *i*
    carries pages `P - 2i` and `2i + 1` on its front and `2i + 2` and
    `P - 2i - 1` on its back. Returned in printing order, front and back
    interleaved, which is what duplex printing consumes.

    Padding is not a second mechanism: a page number above the real count has
    no index, so it comes back as `None` and nothing is drawn for it.
    """
    padded = -(-page_count // 4) * 4
    sides: list[list[int | None]] = []
    for sheet in range(padded // 4):
        front = (padded - 1 - 2 * sheet, 2 * sheet)
        back = (2 * sheet + 1, padded - 2 - 2 * sheet)
        for side in (front, back):
            sides.append([index if index < page_count else None for index in side])
    return sides


def _tick(x: Um, y: Um, direction: int, *, vertical: bool, room: Um) -> list[Segment]:
    """One crop tick, or nothing if the margin cannot hold even a gap."""
    if room <= MARK_GAP:
        return []
    length = min(MARK_LENGTH, room - MARK_GAP)
    near = MARK_GAP * direction
    far = (MARK_GAP + length) * direction
    if vertical:
        start, end = Point(x, y + near), Point(x, y + far)
    else:
        start, end = Point(x + near, y), Point(x + far, y)
    return [Segment(start=start, end=end, weight=MARK_WEIGHT, layer=Layer.FRAME)]


def parse_nup(nup: str, sheet_name: str, resolve) -> Imposition:
    """`2x2` and a sheet name into an `Imposition` (§ 14).

    `resolve` turns a format name or a free size into (width, height) — the
    same resolver the page format uses, so `--nup-sheet 320x450mm` works too.
    """
    text = str(nup).strip().lower().replace("×", "x")
    parts = text.split("x")
    if len(parts) != 2 or not all(part.strip().isdigit() for part in parts):
        raise DefinitionError(
            f"--nup is written as CxR, columns by rows — got {nup!r}. For example `2x2` "
            "puts four pages on a sheet (§ 14)",
            field="nup",
        )
    cols, rows = (int(part) for part in parts)
    if cols < 1 or rows < 1:
        raise DefinitionError(
            f"--nup {nup!r} needs at least one column and one row (§ 14)", field="nup"
        )
    width, height = resolve(sheet_name)
    return Imposition(
        cols=cols, rows=rows, sheet_width=width, sheet_height=height, sheet_name=sheet_name
    )


def _mm(um: Um) -> str:
    return f"{um / 1000:.0f}mm"
