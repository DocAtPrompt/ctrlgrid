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
from ctrlgrid.loader import loads
from ctrlgrid.marks import Area
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
        # index, year, 12 months, 365 days, notes-index, 20 notes
        assert d[0] == "index"
        assert d[1] == "year"
        assert d[2] == "month-01" and d[13] == "month-12"
        assert d[14] == "day-2026-01-01" and d[14 + 364] == "day-2026-12-31"
        assert "notes-index" in d
        assert d[-1] == "note-20" and "note-01" in d
        assert len(d) == 1 + 1 + 12 + 365 + 1 + 20

    def test_a_leap_year_has_one_more_day_page(self) -> None:
        assert len(dests(CalendarConfig.model_validate({"year": 2028}))) == 1 + 1 + 12 + 366

    def test_without_notes_there_is_no_notes_section(self) -> None:
        d = dests(cfg())
        assert not any(x.startswith("note") for x in d)
        assert len(d) == 1 + 1 + 12 + 365


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

    def test_the_index_links_to_year_months_and_notes(self) -> None:
        pages, _dests, _edges = _graph(cfg(notes={"count": 5}))
        index = next(p for p in pages if p.dest == "index")
        targets = {link.target for link in index.links}
        assert {"year", "month-01", "month-12", "notes-index"} <= targets

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


class TestPageCount:
    def test_it_matches_the_enumeration(self) -> None:
        # The report needs the real count without drawing every page; the formula
        # must agree with the pages actually produced, pagination included.
        gen = CalendarGenerator()
        for notes in (None, {"count": 10}, {"count": 200}):
            c = cfg(notes=notes)
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
        # 1 index + 1 year + 12 months + 365 days + 1 notes-index + 10 notes
        assert len(PdfReader(str(path)).pages) == 1 + 1 + 12 + 365 + 1 + 10

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
