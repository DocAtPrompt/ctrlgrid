"""`calendar` — a linked, write-on planner PDF (§ 7, the document generator).

The first generator that is not a blade: it owns pages and their links (see
`ctrlgrid.document`). This module holds the config, the deterministic date
arithmetic and the page *orchestration* — which pages exist, in what order, with
which destination keys and links; the drawing of each page lives in
`calendar_layout.py`.

The core views (Index, Year, Month, Day, Notes) are always produced; Quarter and
Week are opt-in, each enabled by its own `*_view` section. Dates come from `year`
and `week_start` through the standard library's proleptic Gregorian calendar —
deterministic, no wall-clock (§ 10.1). Names are taken from the definition with
English defaults, strictly language-neutral (§ 7.8).
"""

from __future__ import annotations

import calendar as _calendar
import datetime
from collections.abc import Iterator
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ctrlgrid.document import DocumentPage
from ctrlgrid.errors import DefinitionError
from ctrlgrid.generators.holiday_import import read_holiday_file
from ctrlgrid.marks import Area
from ctrlgrid.model import ColorField, Section
from ctrlgrid.writers import WriterQuery

Surface = Literal["blank", "lines", "dots", "grid"]

_DEFAULT_MONTHS = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]
_DEFAULT_WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def _inline_date(item) -> datetime.date | None:
    """The date of an inline holiday entry, or None when the entry is malformed
    — then pydantic reports it in the user's own terms (§ 12)."""
    if not isinstance(item, dict) or "date" not in item or "label" not in item:
        return None
    value = item["date"]
    if isinstance(value, datetime.date) and not isinstance(value, datetime.datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.date.fromisoformat(value.strip())
        except ValueError:
            return None
    return None


def _resolve_def_image(value: str | None, info, field: str) -> str | None:
    """Anchor an image path to the definition (§ 5.2) and check it loads — here,
    in validation, so a missing or unreadable PNG is refused before page one
    (§ 12). Shared by the title page's `logo` and `background_image`."""
    if value is None:
        return None
    from pathlib import Path

    from ctrlgrid.images import load_image

    base = (info.context or {}).get("base_dir")
    path = Path(value)
    if base is not None and not path.is_absolute():
        path = Path(base) / path
    load_image(str(path), field=field)
    return str(path)


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


class TitlePage(Section):
    """A cover page: a full-sheet colour with a centred title and subtitle, and
    an optional logo above them (§ 7, opt-in)."""

    title: str
    subtitle: str | None = None
    background: ColorField = "#2f3a48"
    text_color: ColorField = "#ffffff"
    logo: str | None = None
    background_image: str | None = None
    background_fit: Literal["cover", "contain"] = "cover"
    header: bool = False
    footer: bool = False

    @field_validator("logo")
    @classmethod
    def _resolve_logo(cls, value: str | None, info) -> str | None:
        return _resolve_def_image(value, info, "title_page.logo")

    @field_validator("background_image")
    @classmethod
    def _resolve_background_image(cls, value: str | None, info) -> str | None:
        return _resolve_def_image(value, info, "title_page.background_image")


class WeekView(Section):
    """The week pages: seven day sections in week-start order (§ 7, opt-in)."""

    weekend_shade: ColorField = "#f0f2f5"
    surface: Surface = "lines"
    tasks: bool = True


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
    holidays_file: str | None = None
    #: Computed provenance for the report (set by the before-validator, never by
    #: the user); `describe()` names it. § 7.12.
    holidays_source: str | None = None
    title_page: TitlePage | None = None
    year_view: YearView = YearView()
    month_view: MonthView = MonthView()
    week_view: WeekView | None = None
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

    @model_validator(mode="before")
    @classmethod
    def _import_holidays_file(cls, data, info):
        """Seam 1 (§ 3.6): read `holidays_file` here, where `base_dir` is in the
        validation context (like `logo`) and the raw fields are still dicts, so
        the normal `Holiday` validation runs on the merged result.

        File entries are filtered to the year and merged with the inline list;
        an inline entry wins on a shared date (hand-authored beats a feed). A
        computed provenance string goes to `holidays_source` for the report;
        any user value there is dropped — it is not an input (§ 7.12)."""
        if not isinstance(data, dict):
            return data
        data = dict(data)
        data.pop("holidays_source", None)  # computed, never user input
        spec = data.get("holidays_file")
        if not spec:
            return data
        if not isinstance(spec, str):
            return data  # let the `holidays_file` field report its own type error
        try:
            year = int(data["year"])
        except (KeyError, TypeError, ValueError):
            return data  # let the `year` field report its own error first

        base = (info.context or {}).get("base_dir")
        path = Path(spec)
        if base is not None and not path.is_absolute():
            path = Path(base) / path
        imported = read_holiday_file(path, year)

        # File entries become clean {date, label} dicts; inline entries are kept
        # verbatim so `Holiday`'s extra="forbid" still refuses a typo'd key —
        # stripping them here would make validation depend on whether a file is
        # present (§ 12, fail loudly).
        merged: dict[datetime.date, dict] = {
            entry["date"]: {"date": entry["date"], "label": entry["label"]}
            for entry in imported.entries
        }
        stray = []  # inline entries pydantic should report (bad shape/date)
        for item in data.get("holidays") or ():
            date = _inline_date(item)
            if date is None:
                stray.append(item)
            else:
                merged[date] = item  # inline overrides the file, extras and all
        data["holidays"] = [merged[date] for date in sorted(merged)] + stray

        kept = len(imported.entries)
        # The `.ics` origin (X-WR-CALNAME/PRODID) is worth naming; the YAML origin
        # is just the filename again, so don't double it (§ 7.12).
        line = f"{kept} holidays from {path.name}"
        if imported.origin != path.name:
            line += f" ({imported.origin})"
        if imported.total != kept:
            line += f" — kept {kept} of {imported.total} in {year}"
        if imported.skipped:
            line += f", skipped {imported.skipped} recurring/timed events"
        data["holidays_source"] = line
        return data

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


def _start_weekday(week_start: str) -> int:
    """0 for Monday, 6 for Sunday — the `datetime.weekday()` index (§ 7)."""
    return 0 if week_start == "monday" else 6


def weeks_of_year(year: int, week_start: str) -> list[tuple[int, datetime.date]]:
    """(week number, start date) for every week covering the year (§ 7).

    Weeks are aligned to `week_start`, not ISO — ISO assumes Monday and would
    mislabel a Sunday-start calendar. The first week starts on the `week_start`
    on or before Jan 1, so the year's first and last weeks may reach a few days
    outside it; those out-of-year days are shown without a link.
    """
    jan1 = datetime.date(year, 1, 1)
    dec31 = datetime.date(year, 12, 31)
    offset = (jan1.weekday() - _start_weekday(week_start)) % 7
    first = jan1 - datetime.timedelta(days=offset)
    count = (dec31 - first).days // 7 + 1
    return [(i + 1, first + datetime.timedelta(days=7 * i)) for i in range(count)]


def week_of(date: datetime.date, year: int, week_start: str) -> int:
    """Which week number a date falls in (§ 7), aligned to `week_start`."""
    jan1 = datetime.date(year, 1, 1)
    offset = (jan1.weekday() - _start_weekday(week_start)) % 7
    first = jan1 - datetime.timedelta(days=offset)
    return (date - first).days // 7 + 1


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
        if cfg.holidays_source:            # a file was imported — name the source (§ 7.12)
            lines.append(cfg.holidays_source)
        elif cfg.holidays:
            lines.append(f"{len(cfg.holidays)} holidays")
        if cfg.notes is not None:
            lines.append(f"{cfg.notes.count} note pages, {cfg.notes.surface}")
        return lines

    def check(self, cfg: CalendarConfig, *, area: Area, q: WriterQuery) -> None:
        """Fit-or-refuse: what can only be judged against the area (§ 9, § 12).

        The structural refusals are already in the config validators; here are
        the two that depend on the page size — a day whose fixed block heights
        exceed the page, and a month whose 31 day rows cannot fit at a readable
        size. Nothing is ever scaled or scrolled (§ 8.2); the reader zooms.
        """
        if cfg.day is not None:
            fixed = sum(int(b.height[:-1]) for b in cfg.day.blocks if b.height != "rest")
            if fixed > 100:
                raise DefinitionError(
                    f"the day's block heights add up to {fixed}% — over the 100% of one "
                    "page. Lower a height or use `rest` (§ 9)",
                    field="day",
                )
        # A month lists all 31 possible day rows on one page; below a readable
        # minimum the run is refused rather than shrunk (§ 8.2).
        min_row = 4000  # 4 mm
        header = round(40 * 25400 / 72)  # nav + crumb, roughly
        if area.height - header < 31 * min_row:
            raise DefinitionError(
                "the pattern area is too short for a month's 31 day rows at a readable "
                f"size (needs about {round((31 * min_row + header) / 1000)} mm of height) — "
                "use a taller page or smaller margins (§ 9)",
                field="page",
            )

    def placeholders(self, cfg: CalendarConfig) -> dict[str, str]:
        """Document-supplied header/footer placeholders (§ 8.10): `{year}`."""
        return {"year": str(cfg.year)}

    def generate(self, cfg, *, area, page, q):  # never called — a document
        raise AssertionError("calendar is a document generator; it produces pages")

    def page_count(self, cfg: CalendarConfig, *, area: Area) -> int:
        """The total number of pages, without drawing any (§ 11.3 reports it).

        Contents + full-year overview + two half-years + 12 months + every day;
        an optional title page; the week pages when weeks are on; and the notes'
        paginated index plus one page per note.
        """
        from ctrlgrid.generators import calendar_layout as layout

        total = 1 + 1 + 2 + 12 + day_count(cfg.year)
        if cfg.title_page is not None:
            total += 1
        if cfg.week_view is not None:
            total += len(weeks_of_year(cfg.year, cfg.week_start))
        if cfg.notes is not None:
            capacity = layout.notes_capacity(area.height)
            index_pages = -(-cfg.notes.count // capacity)  # ceil
            total += index_pages + cfg.notes.count
        return total

    def _notes_index_toc(self, cfg, layout, area) -> list[tuple[str, str]]:
        """The contents page's links to the (paginated) notes index."""
        if cfg.notes is None:
            return []
        total = -(-cfg.notes.count // layout.notes_capacity(area.height))
        if total == 1:
            return [("Notes", "notes-index")]
        return [
            (f"Notes {k}", "notes-index" if k == 1 else f"notes-index-{k}")
            for k in range(1, total + 1)
        ]

    # ------------------------------------------------------------------- pages

    def pages(self, cfg: CalendarConfig, *, area: Area, q: WriterQuery) -> Iterator[DocumentPage]:
        """Every page of the calendar, in order, drawn and linked (§ 7)."""
        from ctrlgrid.generators import calendar_layout as layout

        months = cfg.month_names()
        weekdays = cfg.weekday_names()
        has_notes = cfg.notes is not None
        has_week = cfg.week_view is not None
        holidays = {h.date: h.label for h in cfg.holidays}
        all_days = list(days_of_year(cfg.year))
        weeks = weeks_of_year(cfg.year, cfg.week_start) if has_week else []
        day_blocks = cfg.day.blocks if cfg.day is not None else (
            DayBlock(type="notes", height="rest", surface="lines"),
        )

        def make() -> layout.Page:
            return layout.Page(area, q)

        def nav(month: int = 1, week_no: int = 1) -> layout.Nav:
            return layout.Nav(
                month=f"month-{month:02d}", week=f"week-{week_no:02d}",
                has_week=has_week, has_notes=has_notes,
            )

        def wk(date: datetime.date) -> int:
            return week_of(date, cfg.year, cfg.week_start)

        if cfg.title_page is not None:
            yield layout.title_page(make(), cfg)
        toc = self._notes_index_toc(cfg, layout, area)
        yield layout.contents_page(make(), cfg, nav(), months, toc)
        yield layout.year_overview_page(make(), cfg, nav(), months, weekdays)
        yield layout.half_year_page(make(), cfg, nav(1), months, 1)
        yield layout.half_year_page(make(), cfg, nav(7), months, 2)

        for month in range(1, 13):
            prev = f"month-{month - 1:02d}" if month > 1 else None
            nxt = f"month-{month + 1:02d}" if month < 12 else None
            n = nav(month, wk(datetime.date(cfg.year, month, 1)))
            yield layout.month_page(make(), cfg, n, months, weekdays, month, holidays, prev, nxt)

        if has_week:
            for idx, (week_no, start) in enumerate(weeks):
                prev = f"week-{weeks[idx - 1][0]:02d}" if idx > 0 else None
                nxt = f"week-{weeks[idx + 1][0]:02d}" if idx < len(weeks) - 1 else None
                month = start.month if start.year == cfg.year else 1
                yield layout.week_page(
                    make(), cfg, nav(month, week_no), months, weekdays,
                    week_no=week_no, start_date=start, prev=prev, nxt=nxt,
                )

        last = len(all_days) - 1
        for i, date in enumerate(all_days):
            prev = f"day-{all_days[i - 1].isoformat()}" if i > 0 else None
            nxt = f"day-{all_days[i + 1].isoformat()}" if i < last else None
            yield layout.day_page(
                make(), cfg, nav(date.month, wk(date)), months, weekdays,
                date, day_blocks, holidays.get(date), prev, nxt,
            )

        if has_notes:
            yield from self._notes_pages(cfg, layout, make, nav())

    def _notes_pages(self, cfg, layout, page, nav) -> Iterator[DocumentPage]:
        count = cfg.notes.count
        cap = layout.notes_capacity(page().H)
        chunks = [list(range(i + 1, min(i + cap, count) + 1)) for i in range(0, count, cap)]
        total = len(chunks)

        def index_dest(page_no: int) -> str:
            return "notes-index" if page_no == 1 else f"notes-index-{page_no}"

        for page_no, numbers in enumerate(chunks, start=1):
            prev = index_dest(page_no - 1) if page_no > 1 else None
            nxt = index_dest(page_no + 1) if page_no < total else None
            yield layout.notes_index_page(
                page(), cfg, nav, page_no=page_no, page_count=total,
                numbers=numbers, prev=prev, nxt=nxt,
            )

        width = len(str(count))
        for i in range(1, count + 1):
            prev = f"note-{i - 1:0{width}d}" if i > 1 else None
            nxt = f"note-{i + 1:0{width}d}" if i < count else None
            yield layout.note_page(page(), cfg, nav, num=i, prev=prev, nxt=nxt)
