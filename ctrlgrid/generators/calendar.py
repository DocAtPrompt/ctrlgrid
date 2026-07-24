"""`calendar` — a linked, write-on planner PDF (§ 7, the document generator).

The first generator that is not a blade: it owns pages and their links (see
`ctrlgrid.document`). This module is phase 3 — the model and the dates: the YAML
config, the deterministic date arithmetic, the name defaults and the page
*enumeration* (the right pages, in order, with the right destination keys). The
drawn layouts and the links between pages are phase 4; here every page carries
only its title, so the document is navigable in structure and testable in shape.

Dates come from `year` and `week_start` through the standard library's proleptic
Gregorian calendar — deterministic, no wall-clock (§ 10.1). Names are taken from
the definition with English defaults, strictly language-neutral (§ 7.8).
"""

from __future__ import annotations

import calendar as _calendar
import datetime
from collections.abc import Iterator
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ctrlgrid.document import DocumentPage
from ctrlgrid.marks import Area, Mark, Point, Text
from ctrlgrid.model import ColorField, Section
from ctrlgrid.writers import WriterQuery

Surface = Literal["blank", "lines", "dots", "grid"]

_DEFAULT_MONTHS = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]
_DEFAULT_WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

_TITLE_PT = 16


class Holiday(Section):
    """One holiday: a date and the label to show on it (§ 7)."""

    date: datetime.date
    label: str


class DayBlock(Section):
    """One block on the day page — the day is an ordered list of these (§ 7).

    `type` picks the block; `height` is a percentage (`"55%"`) of the day's area
    or `"rest"`; `surface` is the writing surface. `from`/`to` bound a
    `schedule`'s hours; `rows` sets a `todo`'s tick-box count.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)

    type: Literal["schedule", "todo", "notes"]
    height: str = "rest"
    surface: Surface = "lines"
    start_hour: int | None = Field(default=None, alias="from", ge=0, le=24)
    end_hour: int | None = Field(default=None, alias="to", ge=0, le=24)
    rows: int | None = Field(default=None, ge=1)

    @field_validator("height")
    @classmethod
    def _height_is_percent_or_rest(cls, value: str) -> str:
        if value != "rest" and not (value.endswith("%") and value[:-1].isdigit()):
            raise ValueError(f"height must be a percentage like '40%' or 'rest', not {value!r}")
        return value

    @model_validator(mode="after")
    def _schedule_has_a_span(self) -> DayBlock:
        if self.type == "schedule":
            if self.start_hour is None or self.end_hour is None:
                raise ValueError("a schedule block needs `from` and `to` hours (§ 7)")
            if self.start_hour >= self.end_hour:
                raise ValueError(
                    f"schedule `from` ({self.start_hour}) must be before `to` ({self.end_hour})"
                )
        return self


class DaySpec(Section):
    """The day page: an ordered list of blocks (§ 7)."""

    blocks: tuple[DayBlock, ...] = Field(min_length=1)


class YearView(Section):
    """The two half-year tables (§ 7)."""

    weekend_shade: ColorField = "#f0f2f5"
    cell_link: Literal["day", "month", "none"] = "day"


class MonthView(Section):
    """The vertical day list (§ 7)."""

    weekend_shade: ColorField = "#f0f2f5"
    surface: Surface = "lines"


class NotesSpec(Section):
    """The note pages and their numbered index (§ 7)."""

    count: int = Field(ge=1)
    surface: Surface = "lines"


class CalendarConfig(BaseModel):
    """The definition section for the calendar (§ 3.6, seam 2)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    year: int = Field(ge=1, le=9999)
    week_start: Literal["monday", "sunday"] = "monday"
    months: tuple[str, ...] | None = None
    weekdays: tuple[str, ...] | None = None
    holidays: tuple[Holiday, ...] = ()
    year_view: YearView = YearView()
    month_view: MonthView = MonthView()
    day: DaySpec | None = None
    notes: NotesSpec | None = None

    @field_validator("months")
    @classmethod
    def _twelve_months(cls, value: tuple[str, ...] | None) -> tuple[str, ...] | None:
        if value is not None and len(value) != 12:
            raise ValueError(f"months needs exactly 12 names, got {len(value)}")
        return value

    @field_validator("weekdays")
    @classmethod
    def _seven_weekdays(cls, value: tuple[str, ...] | None) -> tuple[str, ...] | None:
        if value is not None and len(value) != 7:
            raise ValueError(f"weekdays needs exactly 7 names, got {len(value)}")
        return value

    @model_validator(mode="after")
    def _holidays_fall_in_the_year(self) -> CalendarConfig:
        for holiday in self.holidays:
            if holiday.date.year != self.year:
                raise ValueError(
                    f"holiday {holiday.date.isoformat()} ({holiday.label!r}) is not in "
                    f"{self.year} — a calendar only marks its own year (§ 7)"
                )
        return self

    # ------------------------------------------------------------ resolved names

    def month_names(self) -> list[str]:
        return list(self.months) if self.months else _DEFAULT_MONTHS

    def weekday_names(self) -> list[str]:
        return list(self.weekdays) if self.weekdays else _DEFAULT_WEEKDAYS


# ------------------------------------------------------------------ date helpers


def days_of_year(year: int) -> Iterator[datetime.date]:
    """Every date in the year, in order — deterministic, no wall-clock (§ 10.1)."""
    for month in range(1, 13):
        for day in range(1, _calendar.monthrange(year, month)[1] + 1):
            yield datetime.date(year, month, day)


def day_count(year: int) -> int:
    return 366 if _calendar.isleap(year) else 365


# ---------------------------------------------------------------- the generator


class CalendarGenerator:
    name = "calendar"
    config_model = CalendarConfig

    #: § 8.3: a document has no pattern axis to snap to.
    supports_snap = False

    def is_page_invariant(self, cfg: CalendarConfig) -> bool:
        """False: every page differs — this is not one repeated pattern (§ 10.1)."""
        return False

    def periodic_axes(self, cfg: CalendarConfig) -> dict[str, list]:
        """None: a calendar has no periodic axis (§ 8.3)."""
        return {}

    def describe(self, cfg: CalendarConfig) -> list[str]:
        lines = [
            f"year {cfg.year}, week starts {cfg.week_start}",
            f"{day_count(cfg.year)} day pages",
        ]
        if cfg.holidays:
            lines.append(f"{len(cfg.holidays)} holidays")
        if cfg.notes is not None:
            lines.append(f"{cfg.notes.count} note pages, {cfg.notes.surface}")
        return lines

    def check(self, cfg: CalendarConfig, *, area: Area, q: WriterQuery) -> None:
        """Fit-or-refuse lives here (§ 12 point 13). The layout-dependent checks
        (a day's blocks, a month's day rows) arrive with the drawing in phase 4;
        the structural ones are already in the config validators above."""
        return None

    def generate(self, cfg, *, area, page, q):  # never called — a document
        raise AssertionError("calendar is a document generator; it produces pages")

    # ------------------------------------------------------------------- pages

    def pages(self, cfg: CalendarConfig, *, area: Area, q: WriterQuery) -> Iterator[DocumentPage]:
        """The page skeleton (phase 3): the right pages, in order, with the right
        destination keys and a title. Layouts and links are phase 4."""
        months = cfg.month_names()
        yield self._page(area, "index", "index", "Index")
        yield self._page(area, "year", "year", str(cfg.year))
        for month in range(1, 13):
            yield self._page(area, f"month-{month:02d}", "month", f"{months[month - 1]} {cfg.year}")
        for date in days_of_year(cfg.year):
            yield self._page(area, f"day-{date.isoformat()}", "day", date.isoformat())
        if cfg.notes is not None:
            width = len(str(cfg.notes.count))
            yield self._page(area, "notes-index", "notes_index", "Notes")
            for i in range(1, cfg.notes.count + 1):
                yield self._page(area, f"note-{i:0{width}d}", "notes", f"Note {i}")

    def _page(self, area: Area, dest: str, kind: str, title: str) -> DocumentPage:
        size = round(_TITLE_PT * 25400 / 72)
        marks: tuple[Mark, ...] = (
            Text(pos=Point(0, area.height - size), content=title, size=size),
        )
        return DocumentPage(dest=dest, kind=kind, marks=marks, links=(), title=title)
