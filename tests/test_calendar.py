"""The `calendar` document generator — phase 3: model, dates, page enumeration.

The layouts and links are phase 4; here the generator validates its config,
computes the year's dates deterministically, resolves names with English
defaults, and enumerates the right pages in the right order with the right
destination keys. A calendar definition already validates and builds a
navigable-in-structure PDF.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError
from pypdf import PdfReader

from ctrlgrid.errors import DefinitionError
from ctrlgrid.generators import REGISTRY
from ctrlgrid.generators.calendar import (
    CalendarConfig,
    CalendarGenerator,
    day_count,
    days_of_year,
)
from ctrlgrid.generators.calendar_layout import pt
from ctrlgrid.loader import loads
from ctrlgrid.marks import Area, Polygon, Text
from ctrlgrid.pages import build
from ctrlgrid.writers.pdf import PdfWriter

AREA = Area(width=190_000, height=277_000)
Q = PdfWriter("unused.pdf")


def dests(cfg: CalendarConfig) -> list[str]:
    return [page.dest for page in CalendarGenerator().pages(cfg, area=AREA, q=Q)]


def cfg(**kw) -> CalendarConfig:
    return CalendarConfig.model_validate({"year": 2026, **kw})


class TestItIsRegistered:
    def test_calendar_is_a_known_generator(self) -> None:
        assert "calendar" in REGISTRY

    def test_it_is_a_document_generator(self) -> None:
        # The seam is detected by the `pages` method (§ 7).
        assert hasattr(REGISTRY["calendar"], "pages")


class TestTheDates:
    def test_an_ordinary_year_has_365_days(self) -> None:
        assert day_count(2026) == 365

    def test_a_leap_year_has_366(self) -> None:
        assert day_count(2028) == 366

    def test_the_days_run_from_january_to_december(self) -> None:
        days = list(days_of_year(2026))
        assert len(days) == 365
        assert days[0].isoformat() == "2026-01-01"
        assert days[-1].isoformat() == "2026-12-31"


class TestNames:
    def test_names_default_to_english(self) -> None:
        c = cfg()
        assert c.month_names()[0] == "January"
        assert c.weekday_names() == ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

    def test_names_can_be_overridden(self) -> None:
        c = cfg(months=[f"M{i}" for i in range(1, 13)], weekdays=list("MDMDFSS"))
        assert c.month_names()[0] == "M1"
        assert c.weekday_names()[0] == "M"


class TestValidation:
    def test_months_must_be_twelve(self) -> None:
        with pytest.raises(ValidationError):
            cfg(months=["Jan", "Feb"])

    def test_weekdays_must_be_seven(self) -> None:
        with pytest.raises(ValidationError):
            cfg(weekdays=["Mon", "Tue"])

    def test_a_holiday_outside_the_year_is_refused(self) -> None:
        with pytest.raises(ValidationError):
            cfg(holidays=[{"date": "2025-12-25", "label": "Christmas"}])

    def test_a_holiday_inside_the_year_is_fine(self) -> None:
        c = cfg(holidays=[{"date": "2026-12-25", "label": "Christmas"}])
        assert c.holidays[0].label == "Christmas"

    def test_a_schedule_block_needs_from_and_to(self) -> None:
        with pytest.raises(ValidationError):
            cfg(day={"blocks": [{"type": "schedule"}]})

    def test_a_schedule_from_after_to_is_refused(self) -> None:
        with pytest.raises(ValidationError):
            cfg(day={"blocks": [{"type": "schedule", "from": 20, "to": 8}]})

    def test_a_valid_day_with_from_and_to(self) -> None:
        c = cfg(day={"blocks": [{"type": "schedule", "from": 7, "to": 22, "height": "60%"}]})
        assert c.day.blocks[0].start_hour == 7 and c.day.blocks[0].end_hour == 22

    def test_a_bad_height_is_refused(self) -> None:
        with pytest.raises(ValidationError):
            cfg(day={"blocks": [{"type": "notes", "height": "tall"}]})


class TestPageEnumeration:
    def test_the_pages_and_their_order(self) -> None:
        d = dests(cfg(notes={"count": 20}))
        # contents, full-year overview, 2 half-years, 12 months, 365 days,
        # notes-index, 20 notes
        assert d[0] == "index"   # the contents page
        assert d[1] == "year"    # the full-year overview
        assert d[2] == "half-1" and d[3] == "half-2"
        assert d[4] == "month-01" and d[15] == "month-12"
        assert d[16] == "day-2026-01-01" and d[16 + 364] == "day-2026-12-31"
        assert "notes-index" in d
        assert d[-1] == "note-20" and "note-01" in d
        assert len(d) == 1 + 1 + 2 + 12 + 365 + 1 + 20

    def test_a_leap_year_has_one_more_day_page(self) -> None:
        assert len(dests(CalendarConfig.model_validate({"year": 2028}))) == 1 + 1 + 2 + 12 + 366

    def test_without_notes_there_is_no_notes_section(self) -> None:
        d = dests(cfg())
        assert not any(x.startswith("note") for x in d)
        assert len(d) == 1 + 1 + 2 + 12 + 365

    def test_a_title_page_leads_when_set(self) -> None:
        d = dests(cfg(title_page={"title": "2026"}))
        assert d[0] == "title" and d[1] == "index"


def _graph(c: CalendarConfig):
    pages = list(CalendarGenerator().pages(c, area=AREA, q=Q))
    dests = {page.dest for page in pages}
    edges = {(page.dest, link.target) for page in pages for link in page.links}
    return pages, dests, edges


class TestLinks:
    def test_no_link_dangles(self) -> None:
        # The whole point: every link resolves to a page that exists. With 40
        # notes the numbered index paginates, so its own page dests are exercised.
        _pages, dests, edges = _graph(cfg(notes={"count": 40}))
        dangling = sorted(target for _src, target in edges if target not in dests)
        assert dangling == []

    def test_the_contents_links_to_the_overviews_months_and_notes(self) -> None:
        pages, _dests, _edges = _graph(cfg(notes={"count": 5}))
        contents = next(p for p in pages if p.dest == "index")
        targets = {link.target for link in contents.links}
        assert {"year", "half-1", "half-2", "month-01", "month-12", "notes-index"} <= targets

    def test_a_month_links_every_date_to_its_day(self) -> None:
        pages, _dests, _edges = _graph(cfg())
        january = next(p for p in pages if p.dest == "month-01")
        targets = {link.target for link in january.links}
        assert "day-2026-01-01" in targets and "day-2026-01-31" in targets

    def test_the_notes_index_numbers_link_to_notes(self) -> None:
        pages, _dests, _edges = _graph(cfg(notes={"count": 5}))
        index = next(p for p in pages if p.dest == "notes-index")
        targets = {link.target for link in index.links}
        assert {"note-1", "note-5"} <= targets

    def test_the_notes_index_paginates_for_a_large_count(self) -> None:
        _pages, dests, _edges = _graph(cfg(notes={"count": 200}))
        assert "notes-index" in dests and "notes-index-2" in dests

    def test_every_page_carries_the_nav_strip(self) -> None:
        pages, _dests, _edges = _graph(cfg(notes={"count": 3}))
        for page in pages:
            targets = {link.target for link in page.links}
            assert "index" in targets and "year" in targets


class TestOverviewHalvesTitleAndWeek:
    ALL = {"title_page": {"title": "T"}, "week_view": {}, "notes": {"count": 40}}

    def test_weeks_are_off_by_default(self) -> None:
        _pages, dests, _edges = _graph(cfg())
        assert not any(d.startswith("week") for d in dests)

    def test_week_pages_cover_the_year(self) -> None:
        _pages, dests, _edges = _graph(cfg(week_view={}))
        weeks = sorted(d for d in dests if d.startswith("week-"))
        assert weeks[0] == "week-01" and len(weeks) == 53  # 2026, monday start

    def test_no_link_dangles_with_every_view(self) -> None:
        _pages, dests, edges = _graph(cfg(**self.ALL))
        assert sorted(t for _s, t in edges if t not in dests) == []

    def test_the_year_overview_links_days_and_months(self) -> None:
        pages, _dests, _edges = _graph(cfg())
        overview = next(p for p in pages if p.dest == "year")
        targets = {link.target for link in overview.links}
        assert {"day-2026-01-01", "month-01", "month-12"} <= targets

    def test_the_overview_links_weeks_only_when_weeks_are_on(self) -> None:
        off = next(p for p in _graph(cfg())[0] if p.dest == "year")
        on = next(p for p in _graph(cfg(week_view={}))[0] if p.dest == "year")
        assert not any(link.target.startswith("week-") for link in off.links)
        assert any(link.target == "week-01" for link in on.links)

    def test_a_half_year_links_its_months_and_days(self) -> None:
        h1 = next(p for p in _graph(cfg())[0] if p.dest == "half-1")
        targets = {link.target for link in h1.links}
        assert {"month-01", "month-06", "day-2026-01-01"} <= targets

    def test_a_week_links_only_its_in_year_days(self) -> None:
        week1 = next(p for p in _graph(cfg(week_view={}))[0] if p.dest == "week-01")
        targets = {link.target for link in week1.links}   # 29 Dec 2025 – 4 Jan 2026
        assert "day-2026-01-01" in targets        # in the year
        assert "day-2025-12-29" not in targets     # before the year — shown, not linked

    def test_the_nav_gains_week_when_enabled(self) -> None:
        day = next(p for p in _graph(cfg(week_view={}))[0] if p.dest == "day-2026-06-15")
        assert any(link.target.startswith("week-") for link in day.links)

    def test_the_title_page_is_a_plain_coloured_cover(self) -> None:
        title = next(
            p for p in _graph(cfg(title_page={"title": "2026", "subtitle": "sub"}))[0]
            if p.dest == "title"
        )
        assert not title.show_header and not title.show_footer
        assert title.background is not None and title.links == ()

    def test_a_cover_logo_renders_as_an_image(self, tmp_path: Path) -> None:
        from PIL import Image as PILImage

        from ctrlgrid.marks import Image
        logo = tmp_path / "logo.png"
        PILImage.new("RGBA", (200, 100), (0, 0, 0, 0)).save(logo)
        c = cfg(title_page={"title": "2026", "logo": str(logo)})
        title = next(p for p in CalendarGenerator().pages(c, area=AREA, q=Q) if p.dest == "title")
        assert any(isinstance(m, Image) for m in title.marks)

    def test_a_missing_cover_logo_is_refused(self) -> None:
        with pytest.raises((DefinitionError, ValidationError)):
            cfg(title_page={"title": "T", "logo": "/no/such/file.png"})


class TestPageCount:
    def test_it_matches_the_enumeration(self) -> None:
        # The report needs the real count without drawing every page; the formula
        # must agree with the pages actually produced, pagination included.
        gen = CalendarGenerator()
        variants = (
            {},
            {"notes": {"count": 200}},
            {"week_view": {}},
            {"title_page": {"title": "T"}, "week_view": {}, "notes": {"count": 40}},
        )
        for extra in variants:
            c = cfg(**extra)
            assert gen.page_count(c, area=AREA) == len(list(gen.pages(c, area=AREA, q=Q)))


class TestFitOrRefuse:
    def test_a_page_too_short_for_a_month_is_refused(self) -> None:
        tiny = Area(width=120_000, height=60_000)  # 60 mm tall — no room for 31 rows
        with pytest.raises(DefinitionError):
            CalendarGenerator().check(cfg(), area=tiny, q=Q)

    def test_day_blocks_over_one_page_are_refused(self) -> None:
        c = cfg(day={"blocks": [
            {"type": "notes", "height": "60%"},
            {"type": "notes", "height": "60%"},
        ]})
        with pytest.raises(DefinitionError):
            CalendarGenerator().check(c, area=AREA, q=Q)


class TestItValidatesAndBuilds:
    DEF = (
        "version: 1\n"
        "page: {format: a4, margin: 10mm}\n"
        "generator: calendar\n"
        "year: 2026\n"
        "notes: {count: 10}\n"
    )

    def test_a_calendar_definition_validates(self) -> None:
        document = loads(self.DEF, source="test")
        assert document.generator == "calendar"

    def test_it_builds_all_the_pages(self, tmp_path: Path) -> None:
        path = tmp_path / "cal.pdf"
        build(loads(self.DEF, source="test"), PdfWriter(path))
        # contents + overview + 2 half-years + 12 months + 365 days + notes-index + 10 notes
        assert len(PdfReader(str(path)).pages) == 1 + 1 + 2 + 12 + 365 + 1 + 10

    def test_two_runs_produce_identical_bytes(self, tmp_path: Path) -> None:
        # § 10.1: dates come from the year, never the wall-clock, so a calendar
        # is byte-identical between runs.
        build(loads(self.DEF, source="test"), PdfWriter(tmp_path / "a.pdf"))
        build(loads(self.DEF, source="test"), PdfWriter(tmp_path / "b.pdf"))
        assert (tmp_path / "a.pdf").read_bytes() == (tmp_path / "b.pdf").read_bytes()

    def test_a_constant_header_with_year_and_a_name(self, tmp_path: Path) -> None:
        # § 7: the optional header is constant furniture; `{year}` resolves from
        # the calendar, and a personalization is the user's own text.
        definition = (
            "version: 1\n"
            "page: {format: a4, margin: 12mm}\n"
            'header: {height: 8mm, gap: 3mm, center: "{year}", right: "Alexander"}\n'
            "generator: calendar\nyear: 2026\nnotes: {count: 3}\n"
        )
        path = tmp_path / "cal.pdf"
        build(loads(definition, source="test"), PdfWriter(path))
        text = PdfReader(str(path)).pages[0].extract_text()
        assert "Alexander" in text          # the header rendered
        assert "{year}" not in text          # the placeholder was resolved
        assert "2026" in text


class TestContentsLayout:
    """The contents page is one centred column, its groups set apart by
    whitespace, the whole block centred between nav strip and foot (§ 7)."""

    def _page(self, **kw):
        pages, _dests, _edges = _graph(cfg(**kw))
        return next(p for p in pages if p.dest == "index")

    def _entries(self, page) -> list[Text]:
        """The entry texts, top first. They are the only ones at their size —
        the nav strip is smaller and the title larger."""
        texts = [m for m in page.marks if isinstance(m, Text) and m.size == pt(12)]
        return sorted(texts, key=lambda mark: -mark.pos.y)

    def test_the_entries_share_one_left_edge(self) -> None:
        entries = self._entries(self._page(notes={"count": 5}))
        assert len({mark.pos.x for mark in entries}) == 1   # one column, one edge

    def test_the_column_is_centred_on_the_sheet(self) -> None:
        entries = self._entries(self._page(notes={"count": 5}))
        left = entries[0].pos.x
        widest = max(Q.text_width(m.content, family="sans", size=m.size) for m in entries)
        # Equal air to the left of the column and to the right of its widest entry.
        assert abs((left + widest + left) - AREA.width) <= 2

    def test_whitespace_separates_the_groups(self) -> None:
        entries = self._entries(self._page(notes={"count": 5}))
        ys = [mark.pos.y for mark in entries]
        steps = [ys[i] - ys[i + 1] for i in range(len(ys) - 1)]
        within = steps[3]           # January → February, inside the months
        assert steps[2] > within    # half-year 2 → January, across the groups
        assert steps[14] > within   # December → Notes, across the groups

    def test_the_block_sits_vertically_centred(self) -> None:
        page = self._page(notes={"count": 5})
        entries = self._entries(page)
        title = next(m for m in page.marks if isinstance(m, Text) and m.size == pt(20))
        above = AREA.height - (title.pos.y + title.size)   # area top → the title's cap
        below = entries[-1].pos.y                          # last baseline → area foot
        # Not exact: the nav strip sits inside the air above and nothing balances
        # it below. Close enough that neither end pools the whitespace.
        assert abs(above - below) < pt(30)

    def test_a_contents_too_long_for_the_page_is_refused(self) -> None:
        # One column holds fewer entries than the two it replaced, so a very long
        # notes index no longer fits — refused before page one, never half-drawn.
        with pytest.raises(DefinitionError, match="contents page needs"):
            CalendarGenerator().check(cfg(notes={"count": 3000}), area=AREA, q=Q)

    def test_an_ordinary_notes_count_is_not_refused(self) -> None:
        CalendarGenerator().check(cfg(notes={"count": 200}), area=AREA, q=Q)


class TestYearOverviewGrid:
    """The full-year overview's mini-months: one right edge per column, so a
    weekday letter sits over its own column and 9 stacks under 30 — and a week
    number down the left, linked when there are week pages (§ 7)."""

    def _year(self, **kw):
        pages, _dests, _edges = _graph(cfg(**kw))
        return next(p for p in pages if p.dest == "year")

    def _january(self, page) -> list[Text]:
        """January's texts — the top-left mini-month of the twelve."""
        texts = [m for m in page.marks if isinstance(m, Text)]
        top = max(t.pos.y for t in texts if t.content == "January")
        # `<= top` keeps the month name itself, which sits on that very baseline.
        return [t for t in texts if t.pos.x < 61_000 and top - 60_000 < t.pos.y <= top]

    def _right(self, mark: Text) -> int:
        """A mark's right edge, however it is anchored."""
        if mark.align == "right":
            return mark.pos.x
        return mark.pos.x + Q.text_width(mark.content, family="sans", size=mark.size)

    # The three kinds are told apart by how they are set, not by their content:
    # a "5" is both a day and a week number in January.
    def _letters(self, texts):
        return [t for t in texts if t.size == pt(6) and t.align == "right"]

    def _weeks(self, texts):
        return [t for t in texts if t.size == pt(6) and t.align != "right"]

    def _days(self, texts):
        return [t for t in texts if t.size == pt(6.5)]

    def test_the_weekday_letters_sit_over_their_columns(self) -> None:
        texts = self._january(self._year())
        letters = sorted(self._right(t) for t in self._letters(texts))
        rows: dict[int, list[Text]] = {}
        for day in self._days(texts):
            rows.setdefault(day.pos.y, []).append(day)
        full = next(r for r in rows.values() if len(r) == 7)   # a whole week
        assert letters == sorted(self._right(t) for t in full)

    def test_the_day_numbers_in_a_column_share_a_right_edge(self) -> None:
        texts = self._january(self._year())
        # Every Monday of January 2026 — one and two digits in the same column.
        mondays = [t for t in self._days(texts) if t.content in {"5", "12", "19", "26"}]
        assert len(mondays) == 4
        assert len({self._right(t) for t in mondays}) == 1

    def test_every_week_row_carries_its_number(self) -> None:
        texts = self._january(self._year())
        # January 2026 spans five weeks, and each row is named once.
        assert [t.content for t in sorted(self._weeks(texts), key=lambda m: -m.pos.y)] == [
            "1", "2", "3", "4", "5",
        ]

    def test_the_week_number_sits_on_its_own_row_baseline(self) -> None:
        texts = self._january(self._year())
        baselines = {t.pos.y for t in self._days(texts)}
        # Sizes differ, so a shared cap top would leave the number a hair high —
        # it is nudged onto the day baseline instead.
        assert all(week.pos.y in baselines for week in self._weeks(texts))

    def test_the_week_numbers_link_when_week_pages_exist(self) -> None:
        targets = {link.target for link in self._year(week_view={}).links}
        assert "week-01" in targets

    def test_without_week_pages_the_numbers_are_not_linked(self) -> None:
        assert not any(link.target.startswith("week-") for link in self._year().links)

    def test_no_link_dangles_with_week_pages(self) -> None:
        _pages, dests, edges = _graph(cfg(week_view={}, notes={"count": 5}))
        assert sorted(target for _src, target in edges if target not in dests) == []

    def test_the_month_name_stands_over_its_own_days(self) -> None:
        texts = self._january(self._year())
        title = next(t for t in texts if t.content == "January")
        # The first column's numbers are right-aligned, so a two-digit day is
        # where the column's text actually begins — and the name begins there.
        mondays = [t for t in self._days(texts) if t.content in {"12", "19", "26"}]
        assert len(mondays) == 3
        assert {t.pos.x for t in mondays} == {title.pos.x}

    def test_the_week_numbers_stand_clear_of_the_month_column(self) -> None:
        texts = self._january(self._year())
        title = next(t for t in texts if t.content == "January")
        # Crowded against the days, a week number is read as one of them.
        assert title.pos.x - max(self._right(t) for t in self._weeks(texts)) >= pt(8)

    def test_the_week_number_stands_further_off_than_a_day_does(self) -> None:
        texts = self._january(self._year())
        title = next(t for t in texts if t.content == "January")
        row = sorted(
            (t for t in self._days(texts) if t.content in {"12", "13", "14", "15"}),
            key=lambda t: t.pos.x,
        )
        between_days = row[1].pos.x - self._right(row[0])
        beside_week = title.pos.x - max(self._right(t) for t in self._weeks(texts))
        # Closer to its neighbours than the week number is to the block: that is
        # what makes the days read as a block and the week number as its label.
        assert beside_week > between_days

    def test_a_page_too_narrow_for_the_mini_months_is_refused(self) -> None:
        # The grid is sized from its content now, so a narrow sheet has to be
        # told rather than handed twelve months running into each other.
        narrow = Area(width=100_000, height=277_000)
        with pytest.raises(DefinitionError, match="full-year overview needs"):
            CalendarGenerator().check(cfg(), area=narrow, q=Q)


class TestHalfYearTable:
    """The half-year table: numbers that sit in their row, on one edge or both."""

    def _half(self, **kw):
        pages, _dests, _edges = _graph(cfg(**kw))
        return next(p for p in pages if p.dest == "half-1")

    def _reference(self, page) -> dict[str, Text]:
        """The 1..31 column on the left edge."""
        return {
            t.content: t
            for t in page.marks
            if isinstance(t, Text) and t.size == pt(6.5) and t.align != "right"
        }

    def test_the_day_number_sits_in_the_middle_of_its_row(self) -> None:
        page = self._half()
        numbers = self._reference(page)
        # The ruled cells of the first month column, top row first.
        cells = [m for m in page.marks if isinstance(m, Polygon) and m.weight > 0]
        left = min(min(p.x for p in cell.points) for cell in cells)
        january = sorted(
            (c for c in cells if min(p.x for p in c.points) == left),
            key=lambda c: -max(p.y for p in c.points),
        )
        for day, cell in enumerate(january, start=1):
            ys = [p.y for p in cell.points]
            mark = numbers[str(day)]
            middle = (min(ys) + max(ys)) / 2
            assert min(ys) < mark.pos.y < max(ys)          # inside its own row
            assert abs((mark.pos.y + mark.size / 2) - middle) < pt(2)   # and centred

    def test_the_numbers_can_be_shown_on_both_edges(self) -> None:
        page = self._half(year_view={"day_numbers": "both"})
        both = [t for t in page.marks
                if isinstance(t, Text) and t.content == "31" and t.size == pt(6.5)]
        assert len(both) == 2

    def test_by_default_the_numbers_are_on_the_left_only(self) -> None:
        page = self._half()
        only = [t for t in page.marks
                if isinstance(t, Text) and t.content == "31" and t.size == pt(6.5)]
        assert len(only) == 1


class TestMarkedDays:
    """A marked day — a holiday, a birthday, an anniversary — wears a colour,
    its own or the definition's default, and it beats the weekend shade (§ 7)."""

    MARKS = {
        "holidays": [
            {"date": "2026-01-01", "label": "New Year"},
            {"date": "2026-05-03", "label": "Birthday", "color": "#ffd9ec"},
        ]
    }

    def _page(self, dest: str):
        pages, _dests, _edges = _graph(cfg(**self.MARKS))
        return next(p for p in pages if p.dest == dest)

    def _fills(self, page) -> set[str]:
        return {m.fill_color for m in page.marks
                if isinstance(m, Polygon) and m.fill_color}

    def test_an_entry_may_carry_its_own_colour(self) -> None:
        c = cfg(**self.MARKS)
        assert c.holidays[1].color == "#ffd9ec"
        assert c.holidays[0].color is None      # this one takes the default
        assert c.holiday_color is not None

    def test_the_half_year_cell_takes_the_marked_colour(self) -> None:
        fills = self._fills(self._page("half-1"))
        c = cfg(**self.MARKS)
        assert c.holiday_color in fills                       # New Year's cell
        assert c.year_view.weekend_shade in fills             # weekends still shaded

    def test_the_month_row_takes_the_entrys_own_colour(self) -> None:
        assert "#ffd9ec" in self._fills(self._page("month-05"))

    def test_the_year_overview_colours_the_number_itself(self) -> None:
        # No cell boxes there by design, so the mark is a patch behind the number.
        assert cfg(**self.MARKS).holiday_color in self._fills(self._page("year"))

    def test_the_day_page_sets_the_label_on_its_colour(self) -> None:
        assert "#ffd9ec" in self._fills(self._page("day-2026-05-03"))

    def test_an_unmarked_weekday_stays_plain(self) -> None:
        assert self._fills(self._page("day-2026-05-04")) == set()


class TestContentsColourKey:
    """The contents page's optional colour key: a patch and what it stands for,
    written by the user because the calendar knows colours, not meanings (§ 7)."""

    KEY = [
        {"color": "#fce9e4", "label": "Public holidays"},
        {"color": "#ffd9ec", "label": "Birthdays"},
    ]

    def _contents(self, **kw):
        pages, _dests, _edges = _graph(cfg(**kw))
        return next(p for p in pages if p.dest == "index")

    def _patches(self, page) -> set[str]:
        return {m.fill_color for m in page.marks
                if isinstance(m, Polygon) and m.fill_color}

    def test_there_is_no_key_by_default(self) -> None:
        page = self._contents()
        assert self._patches(page) == set()
        assert not any(isinstance(m, Text) and m.content == "Birthdays" for m in page.marks)

    def test_the_key_shows_a_patch_and_its_label(self) -> None:
        page = self._contents(legend=self.KEY)
        assert self._patches(page) == {"#fce9e4", "#ffd9ec"}
        labels = {m.content for m in page.marks if isinstance(m, Text)}
        assert {"Public holidays", "Birthdays"} <= labels

    def test_a_key_line_without_a_colour_is_refused(self) -> None:
        with pytest.raises(ValidationError):
            cfg(legend=[{"label": "Birthdays"}])

    def test_the_key_counts_towards_the_page_fitting(self) -> None:
        # It is part of the block, so it can be what pushes the page over.
        many = [{"color": "#ffd9ec", "label": f"Kind {i}"} for i in range(40)]
        with pytest.raises(DefinitionError, match="contents page needs"):
            CalendarGenerator().check(cfg(legend=many), area=AREA, q=Q)


class TestMonthRowsAndNavPlacement:
    """The month row sets the weekday and the day number as two columns, and the
    nav strip hangs off the right so the page title keeps the left (§ 7)."""

    def _pages(self):
        pages, _dests, _edges = _graph(cfg())
        return pages

    def _right(self, mark: Text) -> int:
        return mark.pos.x + Q.text_width(mark.content, family="sans", size=mark.size)

    def _row_labels(self, page) -> tuple[list[Text], list[Text]]:
        rows = [m for m in page.marks if isinstance(m, Text) and m.size == pt(10)]
        return ([t for t in rows if not t.content.isdigit()],
                [t for t in rows if t.content.isdigit()])

    def test_the_weekday_names_share_a_left_edge(self) -> None:
        may = next(p for p in self._pages() if p.dest == "month-05")
        names, _numbers = self._row_labels(may)
        assert len(names) == 31
        assert len({t.pos.x for t in names}) == 1

    def test_the_day_numbers_share_a_right_edge(self) -> None:
        may = next(p for p in self._pages() if p.dest == "month-05")
        _names, numbers = self._row_labels(may)
        assert len(numbers) == 31           # 9 stands under 30 on its units digit
        assert len({self._right(t) for t in numbers}) == 1

    def test_the_whole_date_stays_one_tap_target(self) -> None:
        may = next(p for p in self._pages() if p.dest == "month-05")
        # Split into two columns, but still one link per day — not two.
        assert len([lk for lk in may.links if lk.target.startswith("day-2026-05")]) == 31

    def test_the_nav_strip_ends_at_the_right_edge(self) -> None:
        for page in self._pages()[:4]:
            nav_marks = [m for m in page.marks if isinstance(m, Text) and m.size == pt(9)]
            if nav_marks:                    # the title page carries no nav
                assert max(self._right(t) for t in nav_marks) == AREA.width


class TestWeekPageDateColumns:
    """The week page sets its dates in the same two columns as the month page,
    from the same arithmetic — and shows a marked day like every other view."""

    def _week(self, dest: str, **kw):
        pages, _dests, _edges = _graph(cfg(week_view={}, **kw))
        return next(p for p in pages if p.dest == dest)

    def _rows(self, page) -> tuple[list[Text], list[Text]]:
        rows = [m for m in page.marks if isinstance(m, Text) and m.size == pt(10)]
        return ([t for t in rows if not t.content.isdigit()],
                [t for t in rows if t.content.isdigit()])

    def _right(self, mark: Text) -> int:
        return mark.pos.x + Q.text_width(mark.content, family="sans", size=mark.size)

    def test_the_seven_dates_line_up(self) -> None:
        names, numbers = self._rows(self._week("week-18"))
        assert len(names) == 7 and len(numbers) == 7
        assert len({t.pos.x for t in names}) == 1          # weekdays flush left
        assert len({self._right(t) for t in numbers}) == 1  # numbers flush right

    def test_a_day_outside_the_year_keeps_the_columns_but_loses_the_link(self) -> None:
        # Week 1 of 2026 opens in December 2025 — those days have no page.
        page = self._week("week-01")
        names, numbers = self._rows(page)
        assert len({t.pos.x for t in names}) == 1
        assert len({self._right(t) for t in numbers}) == 1
        assert len([lk for lk in page.links if lk.target.startswith("day-")]) == 4

    def test_a_marked_day_colours_its_week_row(self) -> None:
        page = self._week(
            "week-18",
            holidays=[{"date": "2026-05-03", "label": "Birthday", "color": "#ffd9ec"}],
        )
        fills = {m.fill_color for m in page.marks if isinstance(m, Polygon) and m.fill_color}
        assert "#ffd9ec" in fills
