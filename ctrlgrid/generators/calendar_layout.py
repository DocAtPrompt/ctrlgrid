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
from ctrlgrid.marks import Area, Image, Mark, Point, Polygon, Segment, Text

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


def marked_days(cfg) -> dict[datetime.date, str]:
    """date → the colour that marks it (§ 7).

    A marked day is any entry of `holidays` — a public holiday, a birthday, an
    anniversary; the calendar does not care which. Its own `color` wins, else the
    definition's `holiday_color`.
    """
    return {h.date: (h.color or cfg.holiday_color) for h in cfg.holidays}


def _badge(page: Page, x, top, text, size, color) -> None:
    """A filled patch behind a piece of text — how a marked day shows itself
    where there is no cell to fill (§ 7). Drawn before the text, so the text
    reads over it; the patch is the glyphs' own width, measured."""
    pad = pt(1.5)
    width = page.q.text_width(text, family="sans", size=round(size))
    page.box(x - pad, top - pad, width + 2 * pad, size + 2 * pad, 0.0, color, color)


def date_columns(page: Page, weekdays, size, x=None) -> tuple[int, int]:
    """The two columns a date label is set in (§ 7): the weekday keeps the left
    edge `x`, and the day numbers are right-aligned in a column of their own, so
    9 stands under 30 on its units digit.

    Measured, never assumed: a definition may name its days `Montag` or `月`.
    Returns the weekday's x and the numbers' shared right edge.
    """
    x = pt(1) if x is None else x
    name_w = max(page.q.text_width(name, family="sans", size=round(size)) for name in weekdays)
    widest = page.q.text_width("30", family="sans", size=round(size))
    return x, round(x + name_w + pt(7) + widest)


def date_label(page: Page, top, name, number, size, columns, *, target=None,
               color=LINK) -> None:
    """One date set in those columns. Each piece is underlined on its own — no
    rule across the gap — but the link is a single rectangle over both, so the
    whole date stays one tap target on a pen device. Without a `target` it is
    plain text: a day outside the year has no page to jump to.
    """
    name_x, num_right = columns
    num_w = page.q.text_width(number, family="sans", size=round(size))
    page.text(name_x, top, name, size, color)
    page.text(num_right - num_w, top, number, size, color)
    if target is None:
        return
    under = top + size + pt(0.8)
    page.hline(name_x, name_x + page.q.text_width(name, family="sans", size=round(size)),
               under, 0.35, color)
    page.hline(num_right - num_w, num_right, under, 0.35, color)
    page.links.append(Link(
        Point(0, page._y(top + size + pt(2))),
        Point(round(num_right + pt(1)), page._y(top - pt(1))),
        target,
    ))


# ------------------------------------------------------------------ nav strip


@dataclass
class Nav:
    """The nav strip's context for one page: which views exist and where the
    contextual Month/Week links jump to (§ 7)."""

    month: str
    week: str
    has_week: bool = False
    has_notes: bool = False


def nav(page: Page, n: Nav) -> None:
    """The persistent strip of underlined links at the very top (§ 7).

    Index (the contents) and Year (the full-year overview) are always there;
    Week and Notes appear only when those views exist. Month/Week are contextual
    — the current page's month and week. It hangs off the *right* edge: the page
    title owns the left, and the two no longer compete for the same corner.
    """
    size = pt(9)
    entries = [("Index", "index"), ("Year", "year"), ("Month", n.month)]
    if n.has_week:
        entries.append(("Week", n.week))
    if n.has_notes:
        entries.append(("Notes", "notes-index"))
    gap = pt(14)
    widths = [page.q.text_width(label, family="sans", size=size) for label, _ in entries]
    # Ranged against the right edge: on the left it shared the corner with the
    # page title, and the two fought over it. Measured, so a translated label
    # still ends flush.
    x = page.W - (sum(widths) + gap * (len(entries) - 1))
    for (label, target), width in zip(entries, widths, strict=True):
        page.link_text(round(x), pt(1), label, target, size)
        x += width + gap


def crumb(page: Page, *, title, prev, nxt, up=None):
    """A page's own header: an optional up-link title, and ‹ › prev/next."""
    top = pt(13)
    size = pt(14)
    if up is not None:
        page.link_text(0, top, title, up, size)
    else:
        page.text(0, top, title, size, INK)
    if prev is not None:
        page.link_text(page.W - pt(34), top + pt(1), "‹", prev, pt(13))
    if nxt is not None:
        page.link_text(page.W - pt(11), top + pt(1), "›", nxt, pt(13))
    return top + pt(16)   # where the body may start — kept tight (whitespace)


# -------------------------------------------------------------------- the pages


def title_page(page: Page, cfg) -> DocumentPage:
    """The cover: a full-sheet colour (painted by the handle) with an optional
    logo, a centred title and subtitle. No nav; header/footer only if
    `title_page` opts in (§ 7.12)."""
    tp = cfg.title_page
    if tp.logo:
        from ctrlgrid.images import load_image
        logo = load_image(tp.logo)
        lh = mm(28)
        lw = round(lh * logo.aspect)
        lower = page.H / 2 - pt(64)  # the logo sits above the title
        page.marks.append(Image(
            pos=Point(round((page.W - lw) / 2), page._y(lower)),
            width=lw, height=lh, source=str(logo.path),
        ))
    page.text(page.W / 2, page.H / 2 - pt(26), tp.title, pt(40), tp.text_color, "center")
    if tp.subtitle:
        page.text(page.W / 2, page.H / 2 + pt(22), tp.subtitle, pt(16), tp.text_color, "center")
    return DocumentPage(
        dest="title", kind="title", marks=tuple(page.marks), links=(),
        title=tp.title, background=tp.background,
        background_image=tp.background_image, background_fit=tp.background_fit,
        show_header=tp.header, show_footer=tp.footer,
    )


#: The contents page's vertical rhythm. Named, because `contents_page` draws
#: with them and `check` refuses on them — one arithmetic, never two that drift.
CONTENTS_NAV = pt(14)         # the nav strip's own height, above everything
_CONTENTS_TITLE_GAP = pt(34)  # title top → first entry top
_CONTENTS_LINE = pt(22)       # one entry to the next
_CONTENTS_GROUP_GAP = pt(14)  # the whitespace between two groups
#: The colour key's patch and the air between it and its label.
_KEY_PATCH = pt(9)
_KEY_GAP = pt(6)


def contents_height(entries: int, groups: int) -> int:
    """How tall the contents block is, title included (§ 7).

    Shared by the drawing and the pre-flight refusal: a contents page is one
    page or it is refused (§ 8.2), and the two may not disagree about how tall
    it is.
    """
    return (
        _CONTENTS_TITLE_GAP
        + entries * _CONTENTS_LINE
        + max(0, groups - 1) * _CONTENTS_GROUP_GAP
    )


def contents_page(page: Page, cfg, n: Nav, months, notes_index) -> DocumentPage:
    """The table of contents: links to the overviews, months and note indices.

    One centred column, not two: a contents page is *read*, and a single column
    with a common left edge gives the eye one edge to follow — and a bigger tap
    target on a pen device. The three groups (overviews, months, notes) are set
    apart by whitespace rather than by rules, because they are already distinct
    in kind and a line would be ink that says nothing (§ 7).

    An optional fourth group is the colour key: a patch and what it stands for.
    It is the one place the marked-day colours are explained, and it is written
    by the user — the calendar knows the colours, never their meanings.
    """
    nav(page, n)
    groups = [
        [
            ("Full-year overview", "year"),
            (f"Half-year 1 · {months[0][:3]}–{months[5][:3]}", "half-1"),
            (f"Half-year 2 · {months[6][:3]}–{months[11][:3]}", "half-2"),
        ],
        [(months[i], f"month-{i + 1:02d}") for i in range(12)],
        list(notes_index),
    ]
    groups = [group for group in groups if group]

    size = pt(12)
    legend = list(cfg.legend)
    # The column is as wide as its widest line and sits in the middle of the
    # sheet — measured, never guessed, so a translated month name still centres.
    # A key line is its patch, the gap, and its label.
    widths = [
        page.q.text_width(label, family="sans", size=round(size))
        for group in groups
        for label, _ in group
    ]
    widths += [
        _KEY_PATCH + _KEY_GAP + page.q.text_width(e.label, family="sans", size=round(size))
        for e in legend
    ]
    left = round((page.W - max(widths)) / 2)

    # Centred vertically between the nav strip and the foot of the area, so the
    # air falls evenly above and below instead of pooling at the bottom. The
    # pre-flight has already refused a block too tall to sit here (§ 8.2).
    entries = sum(len(group) for group in groups) + len(legend)
    block = contents_height(entries, len(groups) + (1 if legend else 0))
    top = CONTENTS_NAV + max(0, round((page.H - CONTENTS_NAV - block) / 2))

    page.text(round(page.W / 2), top, "Contents", pt(20), INK, "center")
    top += _CONTENTS_TITLE_GAP
    for index, group in enumerate(groups):
        if index:
            top += _CONTENTS_GROUP_GAP   # the whitespace between the groups
        for label, target in group:
            page.link_text(left, top, label, target, size)
            top += _CONTENTS_LINE
    if legend:
        top += _CONTENTS_GROUP_GAP
        for entry in legend:
            # The patch is centred on the cap, so it reads as part of the line.
            # It is outlined: a pale fill on white is otherwise hard to find, and
            # the palest colours are exactly the ones a calendar wants.
            page.box(left, top + (size - _KEY_PATCH) / 2, _KEY_PATCH, _KEY_PATCH,
                     0.2, GUIDE, entry.color)
            page.text(left + _KEY_PATCH + _KEY_GAP, top, entry.label, size, INK)
            top += _CONTENTS_LINE
    return page.done("index", "index", "Contents")


def year_overview_page(page: Page, cfg, n: Nav, months, weekdays) -> DocumentPage:
    """A single-page whole year: twelve mini-months, three across (§ 7). Only
    numbers as links — the month name → its month, a day number → its day. No
    cell boxes; it fits one page and the reader zooms (§ 8.2)."""
    nav(page, n)
    top = pt(16)
    page.text(0, top, f"{cfg.year} · full year", pt(15), INK)
    top += pt(22)
    cols, rows = 3, 4
    gutter = _YEAR_GUTTER
    cell_w = mini_month_cell_width(page.W)
    cell_h = (page.H - top - pt(2) - (rows - 1) * gutter) / rows
    marked = marked_days(cfg)
    for m in range(12):
        r, c = divmod(m, cols)
        _mini_month(page, cfg, months, weekdays, m + 1,
                    c * (cell_w + gutter), top + r * (cell_h + gutter), cell_w, cell_h,
                    n.has_week, marked)
    return page.done("year", "year", f"{cfg.year} full year")


#: The air between two day columns. The mini-month is built from its content
#: outwards — a column is one two-digit day plus this — rather than by dividing
#: the cell, so tightening the days is what widens the gap beside them.
_DAY_GAP = pt(11)
#: Between a week number and the day grid it belongs to. Wide enough that a
#: two-digit week never crowds a two-digit Monday — the crowding is what made
#: the week numbers read as days.
_WEEK_GAP = pt(24)
#: Between the twelve mini-months, three across.
_YEAR_GUTTER = mm(4)


def mini_month_width(q) -> int:
    """How wide one mini-month needs to be: the week number, the gap beside it,
    and seven day columns (§ 7).

    Content-sized, so it is measured here once and refused in the pre-flight
    against the cell it has to sit in — a narrow sheet must be told, not handed
    twelve months running into each other (§ 8.2).
    """
    day_w = q.text_width("30", family="sans", size=round(pt(6.5)))
    week_w = q.text_width("53", family="sans", size=round(pt(6)))
    return round(week_w + _WEEK_GAP + day_w + 6 * (day_w + _DAY_GAP))


def mini_month_cell_width(area_width: int) -> float:
    """The width each of the twelve mini-months gets — three across (§ 7)."""
    return (area_width - 2 * _YEAR_GUTTER) / 3


def _mini_month(page: Page, cfg, months, weekdays, month, x, top, w, h,
                has_week: bool = False, marked: dict | None = None) -> None:
    """One mini-month of the full-year overview (§ 7).

    Everything hangs off one right edge per column: the weekday letter and every
    day number in that column are right-aligned to it, so the letter really does
    sit over its column and 9 and 30 stack on their units digit.

    The grid is built from its content outwards rather than by dividing the cell:
    a column is one two-digit day plus `_DAY_GAP`. So the days sit as close as
    they need to, the week number keeps a wide gap beside them, and what is left
    over falls between the months instead of stretching them.
    """
    # Imported here, not at the top: `calendar` imports this module back, and the
    # week arithmetic must live once, not twice.
    from ctrlgrid.generators.calendar import week_of

    start = _start_weekday(cfg.week_start)

    day_size = pt(6.5)
    week_size = pt(6)
    # Measured, not divided: the widest day and the widest week the year can show.
    day_w = page.q.text_width("30", family="sans", size=round(day_size))
    week_w = page.q.text_width("53", family="sans", size=round(week_size))
    col_w = day_w + _DAY_GAP

    # Where a two-digit day in the first column begins. The month name starts
    # here too, so the name stands over its own days and *not* over the week
    # numbers: a number directly under a month name is read as a day, which is
    # exactly the misreading the week column must not invite (§ 7).
    body_left = round(x + week_w + _WEEK_GAP)

    def right_edge(column: int) -> float:
        """The shared right edge of a day column — letters and numbers use it."""
        return body_left + day_w + column * col_w

    page.link_text(body_left, round(top), months[month - 1], f"month-{month:02d}", pt(9))

    header = top + pt(13)
    for c in range(7):
        page.text(round(right_edge(c)), round(header),
                  weekdays[(start + c) % 7][:1], week_size, GUIDE, "right")

    grid_top = header + pt(6)
    row_h = (h - (grid_top - top)) / 6
    ndays = _month_length(cfg.year, month)
    lead = (datetime.date(cfg.year, month, 1).weekday() - start) % 7

    # The week number of each row that actually holds days, right-aligned against
    # the day grid. It links to its week page when there are week pages to link to.
    for row in range(6):
        first = max(1, row * 7 - lead + 1)
        if first > ndays:
            break
        number = week_of(datetime.date(cfg.year, month, first), cfg.year, cfg.week_start)
        label = str(number)
        # Right-aligned just left of the day grid: close enough to read as this
        # row's, far enough not to join the column the month name heads.
        wx = round(
            body_left - _WEEK_GAP
            - page.q.text_width(label, family="sans", size=round(week_size))
        )
        # Nudged down by the size difference so the week number sits on the same
        # baseline as its own days: `top` is the cap, and the two sizes differ.
        cy = round(grid_top + row * row_h + day_size - week_size)
        if has_week:
            page.link_text(wx, cy, label, f"week-{number:02d}", week_size)
        else:
            page.text(wx, cy, label, week_size, GUIDE)

    for d in range(1, ndays + 1):
        idx = lead + d - 1
        label = str(d)
        # Right-aligned by measuring: `link_text` anchors left, so the underline
        # and the tap box follow the glyphs rather than a guessed box.
        cx = right_edge(idx % 7) - page.q.text_width(label, family="sans", size=round(day_size))
        cy = grid_top + (idx // 7) * row_h
        # No cell boxes here by design (§ 7), so a marked day colours the number.
        colour = (marked or {}).get(datetime.date(cfg.year, month, d))
        if colour:
            _badge(page, round(cx), round(cy), label, day_size, colour)
        page.link_text(round(cx), round(cy), label,
                       f"day-{cfg.year:04d}-{month:02d}-{d:02d}", day_size)


def half_year_page(page: Page, cfg, n: Nav, months, half: int) -> DocumentPage:
    """One half-year as a month-column × day-row table (the old year page, now a
    full page each). Keeps the table style — the year *overview* is the minimal
    one (§ 7)."""
    nav(page, n)
    first_month = 1 if half == 1 else 7
    span = f"{months[first_month - 1][:3]}–{months[first_month + 4][:3]}"
    prev = "half-1" if half == 2 else None
    nxt = "half-2" if half == 1 else None
    top = crumb(page, title=f"Half-year {half} · {span}", prev=prev, nxt=nxt, up="year")
    _half_table(page, cfg, months, top, page.H - top - pt(2), first_month=first_month)
    return page.done(f"half-{half}", "half", f"Half-year {half}")


def _half_table(page: Page, cfg, months, top, h, *, first_month: int) -> None:
    """A month-column × day-row table. Cells are drawn per existing day, so a
    short month's column simply ends — no empty boxes for the missing days
    (§ 7). Weekends shaded, the month header and day cells link."""
    day_col = mm(7)
    both = cfg.year_view.day_numbers == "both"
    # Six month columns share what the reference column(s) leave.
    col_w = (page.W - day_col - (day_col if both else 0)) / 6
    row_h = h / 32  # one header row + 31 day rows
    shade = cfg.year_view.weekend_shade
    marked = marked_days(cfg)
    size = pt(6.5)

    def in_row(row: int, text_size: float) -> int:
        """The cap top that puts text in the middle of its row, whatever its
        size. A fixed inset put the number at the top of an 8 mm row instead."""
        return round(top + row_h * row + (row_h - text_size) / 2)

    # The reference column of day numbers 1..31, on the left and — when the table
    # is wide enough to lose the row on the way across — on the right as well.
    for d in range(1, 32):
        page.text(pt(1), in_row(d, size), str(d), size, INK)
        if both:
            page.text(page.W - pt(1), in_row(d, size), str(d), size, INK, "right")
    for c in range(6):
        month = first_month + c
        cx = day_col + c * col_w
        page.link_text(round(cx + pt(2)), in_row(0, pt(9)),
                       months[month - 1][:3], f"month-{month:02d}", pt(9))
        ndays = _month_length(cfg.year, month)
        for d in range(1, ndays + 1):
            rtop = top + row_h * d
            date = datetime.date(cfg.year, month, d)
            # The marked day's own colour first: it is the more particular fact.
            fill = marked.get(date) or (shade if date.weekday() >= 5 else None)
            if fill:
                page.box(cx, rtop, col_w, row_h, 0.0, fill, fill)
            page.box(cx, rtop, col_w, row_h, 0.2, GUIDE)  # only existing days get a cell
            if cfg.year_view.cell_link == "day":
                page.links.append(
                    Link(Point(round(cx), page._y(rtop + row_h)),
                         Point(round(cx + col_w), page._y(rtop)), f"day-{date.isoformat()}")
                )


def month_page(page: Page, cfg, n: Nav, months, weekdays, month, holidays, prev, nxt):
    nav(page, n)
    ndays = _month_length(cfg.year, month)
    top = crumb(page, title=f"{months[month - 1]} {cfg.year}", prev=prev, nxt=nxt, up="year")
    avail = page.H - top - pt(2)
    row_h = avail / ndays
    marked = marked_days(cfg)
    size = pt(10)
    columns = date_columns(page, weekdays, size)
    num_right = columns[1]
    for d in range(1, ndays + 1):
        date = datetime.date(cfg.year, month, d)
        rtop = top + (d - 1) * row_h
        fill = marked.get(date) or (
            cfg.month_view.weekend_shade if date.weekday() >= 5 else None
        )
        if fill:
            page.box(0, rtop, page.W, row_h, 0.0, fill, fill)
        page.hline(0, page.W, rtop, 0.2, GUIDE)
        date_label(page, round(rtop + row_h / 2 - pt(5)), weekdays[date.weekday()],
                   str(d), size, columns, target=f"day-{date.isoformat()}")
        holiday = holidays.get(date)
        if holiday is not None:
            page.text(round(num_right + pt(14)), round(rtop + row_h / 2 - pt(4)),
                      holiday.label, pt(8), INK)
    page.hline(0, page.W, top + ndays * row_h, 0.2, GUIDE)
    return page.done(f"month-{month:02d}", "month", f"{months[month - 1]} {cfg.year}")


def day_page(page: Page, cfg, n: Nav, months, weekdays, date, blocks, holiday, prev, nxt):
    month = date.month
    nav(page, n)
    title = f"{weekdays[date.weekday()]} {date.day} {months[month - 1]}"
    top = crumb(page, title=title, prev=prev, nxt=nxt, up=f"month-{month:02d}")
    if holiday is not None:
        # The day has no cell to fill, so the label wears the colour itself. It
        # starts a little lower than the body would: the patch reaches above the
        # cap, and the title above it has descenders.
        top += pt(4)
        _badge(page, 0, top, holiday.label, pt(9), holiday.color or cfg.holiday_color)
        page.text(0, top, holiday.label, pt(9), INK)
        top += pt(16)
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


def _start_weekday(week_start: str) -> int:
    return 0 if week_start == "monday" else 6


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
    size = pt(10)
    # The same two columns as the month page, from the same arithmetic.
    columns = date_columns(page, weekdays, size)
    marked = marked_days(cfg)
    for i in range(7):
        date = start_date + _dt.timedelta(days=i)
        rtop = top + i * row_h
        fill = marked.get(date) or (
            cfg.week_view.weekend_shade if date.weekday() >= 5 else None
        )
        if fill:
            page.box(0, rtop, right, row_h, 0.0, fill, fill)
        page.hline(0, right, rtop, 0.2, GUIDE)
        # A day outside the year has no page of its own, so it is set plainly —
        # in the same columns, so the seven still line up.
        inside = date.year == cfg.year
        date_label(page, round(rtop + pt(2)), weekdays[date.weekday()], str(date.day),
                   size, columns,
                   target=f"day-{date.isoformat()}" if inside else None,
                   color=LINK if inside else GUIDE)
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
    inner = top + pt(2)
    if b.type == "schedule":
        hours = b.end_hour - b.start_hour
        rh = (h - pt(2)) / max(1, hours)
        for i in range(hours):
            ry = inner + i * rh
            page.text(pt(1), round(ry), f"{b.start_hour + i:>2}", pt(7), INK)
            page.hline(mm(9), page.W, ry + rh - pt(1), 0.2, FAINT)
    elif b.type == "todo":
        rows = b.rows or max(1, int((h - pt(2)) // mm(8)))
        rh = (h - pt(2)) / rows
        for i in range(rows):
            ry = inner + i * rh
            page.box(pt(1), round(ry), mm(4), mm(4), 0.35, GUIDE)
            page.hline(mm(7), page.W, round(ry + mm(4)), 0.2, FAINT)
    else:  # notes
        page.surface(0, inner, page.W, h - pt(4), b.surface)


def _month_length(year: int, month: int) -> int:
    import calendar as _cal

    return _cal.monthrange(year, month)[1]


def notes_capacity(height: int) -> int:
    """How many numbered rows fit one index page at a comfortable height (§ 9).

    A fixed row height, so the index paginates over several one-page sheets
    rather than shrinking to hold a large count on one page (§ 8.2, § 9)."""
    return max(1, int((height - pt(44)) // mm(9)))
