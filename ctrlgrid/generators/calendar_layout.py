"""Drawing for the `calendar` generator (§ 7) — phase 4.

Kept apart from `calendar.py` (the config, dates and orchestration) because the
two do different jobs: this module knows only how to lay ink and link rectangles
into one page's area, and nothing about which pages exist or how they are
ordered. Every function here fills a `Page` — a small builder that accumulates
the six primitives and the link rectangles in area-local coordinates (origin
bottom-left, § 3.5); the handle translates them onto the sheet.

A link's visible part is an underlined `Text` (a `Segment` under an ordinary
`Text`), and the `Link` rectangle is the text's own box — minimal ink and bytes.
Everything is measured to fill the page: nothing scrolls, and where a set has no
page bound (`notes`) the generator paginates rather than shrink (§ 8.2, § 9).
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass

from ctrlgrid.document import DocumentPage, Link
from ctrlgrid.marks import Area, Mark, Point, Polygon, Segment, Text

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

    def __init__(self, area: Area, q: object) -> None:
        self.W = area.width
        self.H = area.height
        self.q = q
        self.marks: list[Mark] = []
        self.links: list[Link] = []

    def _y(self, top: float) -> int:
        return round(self.H - top)

    def text(self, x, top, s, size, color=INK, align="left"):
        # `top` is the top of the cap; the baseline sits one size below.
        self.marks.append(
            Text(pos=Point(round(x), self._y(top + size)), content=s, size=round(size),
                 family="sans", align=align, color=color)
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
        width = self.q.text_width(s, family="sans", size=round(size))
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


# ------------------------------------------------------------------ nav strip


@dataclass
class Nav:
    """The nav strip's context for one page: which views exist and where the
    contextual Quarter/Month/Week links jump to (§ 7)."""

    month: str
    quarter: str
    week: str
    has_quarter: bool = False
    has_week: bool = False
    has_notes: bool = False


def nav(page: Page, n: Nav) -> None:
    """The persistent strip of underlined links at the very top (§ 7).

    Index and Year are always there; Quarter, Week and Notes appear only when
    those views exist. Quarter/Month/Week are contextual — the current page's
    quarter, month and week.
    """
    size = pt(9)
    entries = [("Index", "index"), ("Year", "year")]
    if n.has_quarter:
        entries.append(("Quarter", n.quarter))
    entries.append(("Month", n.month))
    if n.has_week:
        entries.append(("Week", n.week))
    if n.has_notes:
        entries.append(("Notes", "notes-index"))
    x = 0
    for label, target in entries:
        page.link_text(x, pt(1), label, target, size)
        x += page.q.text_width(label, family="sans", size=size) + pt(14)


def crumb(page: Page, *, title, prev, nxt, up=None):
    """A page's own header: an optional up-link title, and ‹ › prev/next."""
    top = pt(15)
    size = pt(15)
    if up is not None:
        page.link_text(0, top, title, up, size)
    else:
        page.text(0, top, title, size, INK)
    if prev is not None:
        page.link_text(page.W - pt(36), top + pt(1), "‹", prev, pt(14))
    if nxt is not None:
        page.link_text(page.W - pt(12), top + pt(1), "›", nxt, pt(14))
    return top + pt(20)   # where the body may start


# -------------------------------------------------------------------- the pages


def index_page(page: Page, cfg, n: Nav, months) -> DocumentPage:
    nav(page, n)
    top = pt(20)
    page.text(0, top, str(cfg.year), pt(24), INK)
    top += pt(34)
    entries = [("Year", "year")]
    if n.has_quarter:
        entries += [(f"Q{q}", f"quarter-{q}") for q in range(1, 5)]
    entries += [(months[i], f"month-{i + 1:02d}") for i in range(12)]
    if n.has_week:
        entries.append(("Weeks", "week-01"))
    if n.has_notes:
        entries.append(("Notes", "notes-index"))
    col_w = page.W / 3
    for i, (label, target) in enumerate(entries):
        r, c = divmod(i, 3)
        page.link_text(round(c * col_w), top + r * pt(24), label, target, pt(13))
    return page.done("index", "index", "Index")


def year_page(page: Page, cfg, n: Nav, months) -> DocumentPage:
    nav(page, n)
    top = pt(18)
    page.text(0, top, str(cfg.year), pt(20), INK)
    top += pt(28)
    gap = pt(12)
    table_h = (page.H - top - gap) / 2
    _half_table(page, cfg, months, top, table_h, first_month=1)
    _half_table(page, cfg, months, top + table_h + gap, table_h, first_month=7)
    return page.done("year", "year", str(cfg.year))


def _half_table(page: Page, cfg, months, top, h, *, first_month: int) -> None:
    day_col = mm(7)
    col_w = (page.W - day_col) / 6
    row_h = h / 32  # one header row + 31 day rows
    shade = cfg.year_view.weekend_shade
    # weekend / non-existent shading, drawn under the grid
    for c in range(6):
        month = first_month + c
        cx = day_col + c * col_w
        for d in range(1, 32):
            rtop = top + row_h * d
            try:
                date = datetime.date(cfg.year, month, d)
            except ValueError:
                page.box(cx, rtop, col_w, row_h, 0.0, FAINT, FAINT)
                continue
            if date.weekday() >= 5 and shade:
                page.box(cx, rtop, col_w, row_h, 0.0, shade, shade)
            if cfg.year_view.cell_link == "day":
                page.links.append(
                    Link(Point(round(cx), page._y(rtop + row_h)),
                         Point(round(cx + col_w), page._y(rtop)), f"day-{date.isoformat()}")
                )
    # the grid
    for r in range(33):
        page.hline(0, page.W, top + r * row_h, 0.2, GUIDE)
    for c in range(8):
        page.vline(day_col + (c - 1) * col_w if c else 0, top, top + 32 * row_h, 0.2, GUIDE)
    # month headers (links) and day numbers
    for c in range(6):
        month = first_month + c
        page.link_text(round(day_col + c * col_w + pt(2)), round(top + pt(1)),
                       months[month - 1][:3], f"month-{month:02d}", pt(9))
    for d in range(1, 32):
        page.text(pt(1), round(top + row_h * d + pt(1)), str(d), pt(6.5), INK)


def month_page(page: Page, cfg, n: Nav, months, weekdays, month, holidays, prev, nxt):
    nav(page, n)
    ndays = _month_length(cfg.year, month)
    top = crumb(page, title=f"{months[month - 1]} {cfg.year}", prev=prev, nxt=nxt, up="year")
    avail = page.H - top - pt(2)
    row_h = avail / ndays
    for d in range(1, ndays + 1):
        date = datetime.date(cfg.year, month, d)
        rtop = top + (d - 1) * row_h
        if date.weekday() >= 5 and cfg.month_view.weekend_shade:
            page.box(0, rtop, page.W, row_h, 0.0,
                     cfg.month_view.weekend_shade, cfg.month_view.weekend_shade)
        page.hline(0, page.W, rtop, 0.2, GUIDE)
        page.link_text(pt(1), round(rtop + row_h / 2 - pt(5)),
                       f"{weekdays[date.weekday()]} {d}", f"day-{date.isoformat()}", pt(10))
        label = holidays.get(date)
        if label:
            page.text(mm(22), round(rtop + row_h / 2 - pt(4)), label, pt(8), LINK)
    page.hline(0, page.W, top + ndays * row_h, 0.2, GUIDE)
    return page.done(f"month-{month:02d}", "month", f"{months[month - 1]} {cfg.year}")


def day_page(page: Page, cfg, n: Nav, months, weekdays, date, blocks, holiday_label, prev, nxt):
    month = date.month
    nav(page, n)
    title = f"{weekdays[date.weekday()]} {date.day} {months[month - 1]}"
    top = crumb(page, title=title, prev=prev, nxt=nxt, up=f"month-{month:02d}")
    if holiday_label:
        page.text(0, top, holiday_label, pt(9), LINK)
        top += pt(12)
    _draw_blocks(page, blocks, top)
    return page.done(f"day-{date.isoformat()}", "day", title)


def notes_index_page(page: Page, cfg, n: Nav, *, page_no, page_count, numbers, prev, nxt):
    nav(page, n)
    title = "Notes" if page_count == 1 else f"Notes {page_no} / {page_count}"
    top = crumb(page, title=title, prev=prev, nxt=nxt)
    avail = page.H - top - pt(2)
    row_h = avail / len(numbers)
    width = len(str(cfg.notes.count))
    for i, num in enumerate(numbers):
        rtop = top + i * row_h
        page.hline(0, page.W, rtop, 0.2, GUIDE)
        page.link_text(pt(1), round(rtop + row_h / 2 - pt(5)), str(num),
                       f"note-{num:0{width}d}", pt(11))
    page.hline(0, page.W, top + len(numbers) * row_h, 0.2, GUIDE)
    dest = "notes-index" if page_no == 1 else f"notes-index-{page_no}"
    return page.done(dest, "notes_index", title)


def note_page(page: Page, cfg, n: Nav, *, num, prev, nxt) -> DocumentPage:
    width = len(str(cfg.notes.count))
    nav(page, n)
    top = crumb(page, title=f"Note {num}", prev=prev, nxt=nxt, up="notes-index")
    page.surface(0, top, page.W, page.H - top - pt(2), cfg.notes.surface)
    return page.done(f"note-{num:0{width}d}", "notes", f"Note {num}")


def quarter_page(page: Page, cfg, n: Nav, months, weekdays, quarter, prev, nxt) -> DocumentPage:
    nav(page, n)
    top = crumb(page, title=f"Q{quarter} · {cfg.year}", prev=prev, nxt=nxt, up="year")
    col_w = (page.W - mm(8)) / 3
    for i in range(3):
        month = (quarter - 1) * 3 + i + 1
        _mini_month(page, cfg, months, weekdays, month, i * (col_w + mm(4)), top, col_w)
    return page.done(f"quarter-{quarter}", "quarter", f"Q{quarter} · {cfg.year}")


def _start_weekday(week_start: str) -> int:
    return 0 if week_start == "monday" else 6


def _mini_month(page: Page, cfg, months, weekdays, month, x, top, w) -> None:
    start = _start_weekday(cfg.week_start)
    shade = cfg.quarter_view.weekend_shade
    page.link_text(round(x), round(top), months[month - 1], f"month-{month:02d}", pt(10))
    cw = w / 7
    hy = top + pt(14)
    for c in range(7):
        page.text(round(x + c * cw + cw / 2), round(hy), weekdays[(start + c) % 7][:2], pt(6),
                  GUIDE, "center")
    row_h = mm(6)
    grid_top = hy + pt(8)
    ndays = _month_length(cfg.year, month)
    for day in range(1, ndays + 1):
        date = datetime.date(cfg.year, month, day)
        col = (date.weekday() - start) % 7
        row = (day - 1 + (datetime.date(cfg.year, month, 1).weekday() - start) % 7) // 7
        cx = x + col * cw
        cy = grid_top + row * row_h
        if date.weekday() >= 5 and shade:
            page.box(cx, cy, cw, row_h, 0.0, shade, shade)
        page.box(cx, cy, cw, row_h, 0.3, GUIDE)
        page.text(round(cx + pt(1)), round(cy + pt(1)), str(day), pt(6), INK)
        if cfg.quarter_view.cell_link == "day":
            page.links.append(
                Link(Point(round(cx), page._y(cy + row_h)), Point(round(cx + cw), page._y(cy)),
                     f"day-{date.isoformat()}")
            )


def week_page(page: Page, cfg, n: Nav, months, weekdays, *, week_no, start_date, prev, nxt):
    import datetime as _dt

    nav(page, n)
    end = start_date + _dt.timedelta(days=6)
    label = f"Week {week_no} · {start_date.day} {months[start_date.month - 1][:3]}" \
            f" – {end.day} {months[end.month - 1][:3]}"
    top = crumb(page, title=label, prev=prev, nxt=nxt)
    has_tasks = cfg.week_view.tasks
    body = page.H - top - pt(2)
    row_h = body / 7
    right = page.W - (mm(48) if has_tasks else 0)
    for i in range(7):
        date = start_date + _dt.timedelta(days=i)
        rtop = top + i * row_h
        weekend = date.weekday() >= 5
        if weekend and cfg.week_view.weekend_shade:
            page.box(0, rtop, right, row_h, 0.0,
                     cfg.week_view.weekend_shade, cfg.week_view.weekend_shade)
        page.hline(0, right, rtop, 0.2, GUIDE)
        head = f"{weekdays[date.weekday()]} {date.day}"
        if date.year == cfg.year:
            page.link_text(pt(1), round(rtop + pt(2)), head, f"day-{date.isoformat()}", pt(10))
        else:
            page.text(pt(1), round(rtop + pt(2)), head, pt(9), GUIDE)  # outside the year, no link
        page.surface(mm(2), rtop + pt(14), right - mm(4), row_h - pt(16), cfg.week_view.surface)
    page.hline(0, right, top + 7 * row_h, 0.2, GUIDE)
    if has_tasks:
        page.vline(right, top, top + 7 * row_h, 0.3, GUIDE)
        page.text(right + pt(3), round(top + pt(2)), "tasks / notes", pt(8), LINK)
        page.surface(right, top + pt(12), page.W - right, 7 * row_h - pt(12), "lines")
    return page.done(f"week-{week_no:02d}", "week", label)


# ------------------------------------------------------------------- day blocks


def _draw_blocks(page: Page, blocks, top) -> None:
    avail = page.H - top - pt(2)
    fixed = sum(int(b.height[:-1]) for b in blocks if b.height != "rest")
    rests = [b for b in blocks if b.height == "rest"]
    rest_h = round(avail * max(0, 100 - fixed) / 100 / len(rests)) if rests else 0
    y = top
    for b in blocks:
        h = rest_h if b.height == "rest" else round(avail * int(b.height[:-1]) / 100)
        _draw_block(page, b, y, h)
        y += h


def _draw_block(page: Page, b, top, h) -> None:
    page.hline(0, page.W, top, 0.35, GUIDE)
    inner = top + pt(4)
    if b.type == "schedule":
        hours = b.end_hour - b.start_hour
        rh = (h - pt(4)) / max(1, hours)
        for i in range(hours):
            ry = inner + i * rh
            page.text(pt(1), round(ry), f"{b.start_hour + i:>2}", pt(7), INK)
            page.hline(mm(9), page.W, ry + rh - pt(1), 0.2, FAINT)
    elif b.type == "todo":
        rows = b.rows or max(1, int((h - pt(4)) // mm(8)))
        rh = (h - pt(4)) / rows
        for i in range(rows):
            ry = inner + i * rh
            page.box(pt(1), round(ry), mm(4), mm(4), 0.35, GUIDE)
            page.hline(mm(7), page.W, round(ry + mm(4)), 0.2, FAINT)
    else:  # notes
        page.surface(0, inner, page.W, h - pt(6), b.surface)


def _month_length(year: int, month: int) -> int:
    import calendar as _cal

    return _cal.monthrange(year, month)[1]


def notes_capacity(height: int) -> int:
    """How many numbered rows fit one index page at a comfortable height (§ 9).

    A fixed row height, so the index paginates over several one-page sheets
    rather than shrinking to hold a large count on one page (§ 8.2, § 9)."""
    return max(1, int((height - pt(44)) // mm(9)))
