"""One page's ink and links — the builder both document generators draw on.

Extracted from `calendar_layout` when `notebook` needed exactly the same thing
(§ 7.13): a small builder that accumulates the six primitives and the link
rectangles in area-local coordinates (origin bottom-left, § 3.5), with `top`
counted downward because a page is read that way. The handle translates the
result onto the sheet.

Shared rather than copied, the way `polar_geometry` is shared by `polar` and
`mandala`: two builders would drift, and a link box that is a hair off its own
glyphs is the kind of almost-right § 5.1 refuses.
"""

from __future__ import annotations

from ctrlgrid.document import DocumentPage, Link
from ctrlgrid.marks import (
    Area,  # noqa: F401  (re-exported for the layout modules)
    Mark,
    Point,
    Polygon,
    Segment,
    Text,
)

PT = 25400 / 72

INK = "#1e2a36"
LINK = "#2f5686"
GUIDE = "#c8ced6"
FAINT = "#e6e9ee"


def pt(value: float) -> int:
    return round(value * PT)


def mm(value: float) -> int:
    return round(value * 1000)


_SURFACE_STEP = 6000  # 6 mm default spacing for writing surfaces


class Page:
    """One page's marks and links, in area-local micrometres (§ 3.5).

    Coordinates are given *from the top* for readability — a calendar reads
    downward — and flipped to the y-up area here. `q` measures text so a link's
    box is exactly its glyphs.
    """

    def __init__(self, area: Area, q: object, family: str = "sans") -> None:
        self.W = area.width
        self.H = area.height
        self.q = q
        #: The token every text on this page is set in (§ 10.3, decision 15).
        #: A document names one font for the whole document — there is nothing
        #: on these pages that would want two — and it is what makes § 10.3's
        #: stage 2 reachable from a calendar at all.
        self.family = family
        self.marks: list[Mark] = []
        self.links: list[Link] = []

    def _y(self, top: float) -> int:
        return round(self.H - top)

    def text(self, x, top, s, size, color=INK, align="left"):
        # `top` is the top of the cap; the baseline sits one size below.
        self.marks.append(
            Text(pos=Point(round(x), self._y(top + size)), content=s, size=round(size),
                 family=self.family, align=align, color=color)
        )

    def hline(self, x1, x2, top, weight=0.2, color=GUIDE):
        self.marks.append(
            Segment(start=Point(round(x1), self._y(top)), end=Point(round(x2), self._y(top)),
                    weight=weight, color=color)
        )

    def vline(self, x, top1, top2, weight=0.2, color=GUIDE):
        self.marks.append(
            Segment(start=Point(round(x), self._y(top1)), end=Point(round(x), self._y(top2)),
                    weight=weight, color=color)
        )

    def box(self, x, top, w, h, weight=0.0, color=GUIDE, fill=None):
        y1 = self._y(top + h)
        y2 = self._y(top)
        pts = (Point(round(x), y1), Point(round(x + w), y1),
               Point(round(x + w), y2), Point(round(x), y2))
        self.marks.append(
            Polygon(points=pts, closed=True, weight=weight, color=color, fill_color=fill)
        )

    def link_text(self, x, top, s, target, size, color=LINK, align="left"):
        """Underlined text that jumps to `target`. Left-aligned only (calendars
        do not need a right-aligned link, and it keeps the box arithmetic simple)."""
        width = self.q.text_width(s, family=self.family, size=round(size))
        self.text(x, top, s, size, color, align)
        under = top + size + pt(0.8)
        self.hline(x, x + width, under, 0.35, color)
        # the tap box is the text's own bounds, a hair of padding around it
        self.links.append(
            Link(Point(round(x - pt(1)), self._y(top + size + pt(2))),
                 Point(round(x + width + pt(1)), self._y(top - pt(1))), target)
        )

    def surface(self, x, top, w, h, kind, step=_SURFACE_STEP):
        """A writing surface: blank, ruled lines, a dot grid, or squares."""
        if kind == "blank" or h <= 0 or w <= 0:
            return
        if kind in ("lines", "grid"):
            y = top + step
            while y < top + h - 1:
                self.hline(x, x + w, y, 0.2, FAINT)
                y += step
        if kind == "grid":
            gx = x + step
            while gx < x + w - 1:
                self.vline(gx, top, top + h, 0.2, FAINT)
                gx += step
        if kind == "dots":
            gy = top + step
            while gy < top + h - 1:
                gx = x + step
                while gx < x + w - 1:
                    self.marks.append(
                        Segment(start=Point(round(gx), self._y(gy)),
                                end=Point(round(gx), self._y(gy)),
                                weight=0.5, color=GUIDE, cap="round")
                    )
                    gx += step
                gy += step

    def done(self, dest, kind, title) -> DocumentPage:
        return DocumentPage(dest=dest, kind=kind, marks=tuple(self.marks),
                            links=tuple(self.links), title=title)


