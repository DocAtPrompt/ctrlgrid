# Calendar Holiday-File Import — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `holidays_file:` key to the calendar config that reads holidays from a YAML list or a concrete-dated `.ics` feed, merges them with any inline `holidays:` list (inline wins on date collision), filters to the calendar year, and names the source in the run report.

**Architecture:** A new self-contained module `ctrlgrid/generators/holiday_import.py` reads and parses the file (both formats, year filter, counts, origin). A `model_validator(mode="before")` on `CalendarConfig` resolves the path against `base_dir` (like `logo`), calls the reader, merges with the inline list, and stores a computed provenance string in a new internal `holidays_source` field. `describe()` surfaces that string in the report. No blade or handle change — this is pure seam-1 (definition → model) resolution.

**Tech Stack:** Python 3.11+, pydantic v2 (validators), ruamel.yaml (safe load, already a dependency), pytest, pypdf (read-back verification).

---

## File Structure

- **Create** `ctrlgrid/generators/holiday_import.py` — file reading + both parsers + year filter. One responsibility: turn a path into a `HolidayImport` (entries filtered to the year, plus counts and origin). Knows nothing about pydantic or the calendar model.
- **Create** `tests/test_calendar_holiday_import.py` — all tests for this feature.
- **Modify** `ctrlgrid/generators/calendar.py` — two new fields (`holidays_file`, `holidays_source`), the before-validator, the `describe()` line.
- **Modify** `docs/pflichtenheft-vorlagengenerator.md` (§ 7.12), `docs/CLAUDE.md`, `docs/implementation-decisions.md` — the truth, in the same breath.

Note on DRY vs. import cycles: `holiday_import.py` **replicates** the ~10-line
UTF-8/CP1252 decode from `read_names` (`loader.py:591`) rather than importing it.
`loader` imports the generator registry, so a generator module importing `loader`
would risk a cycle. The shared contract is the *message text* (§ 9.4), which the
plan copies verbatim.

---

## Task 1: The YAML reader

**Files:**
- Create: `ctrlgrid/generators/holiday_import.py`
- Test: `tests/test_calendar_holiday_import.py`

- [ ] **Step 1: Write the failing test**

```python
"""Holiday file import for the calendar — § 7.12.

The reader turns a path (.yaml/.yml or .ics) into holidays filtered to the
calendar's year, with the counts and origin the report needs. Parsing lives
here; the calendar model only resolves the path, merges and reports.
"""

from __future__ import annotations

import datetime

import pytest

from ctrlgrid.errors import DefinitionError
from ctrlgrid.generators.holiday_import import read_holiday_file


def test_yaml_list_is_read_and_filtered_to_the_year(tmp_path):
    f = tmp_path / "hol.yaml"
    f.write_text(
        "- date: 2026-01-01\n  label: New Year\n"
        "- date: 2026-12-25\n  label: Christmas\n"
        "- date: 2027-01-01\n  label: Next Year\n",
        encoding="utf-8",
    )
    result = read_holiday_file(f, 2026)
    assert [(e["date"], e["label"]) for e in result.entries] == [
        (datetime.date(2026, 1, 1), "New Year"),
        (datetime.date(2026, 12, 25), "Christmas"),
    ]
    assert result.total == 3          # all three concrete entries parsed
    assert result.skipped == 0        # YAML never skips
    assert result.origin == "hol.yaml"


def test_yaml_quoted_iso_date_is_coerced(tmp_path):
    f = tmp_path / "hol.yaml"
    f.write_text('- date: "2026-05-01"\n  label: May Day\n', encoding="utf-8")
    result = read_holiday_file(f, 2026)
    assert result.entries[0]["date"] == datetime.date(2026, 5, 1)


def test_yaml_that_is_not_a_list_is_refused(tmp_path):
    f = tmp_path / "hol.yaml"
    f.write_text("date: 2026-01-01\nlabel: New Year\n", encoding="utf-8")
    with pytest.raises(DefinitionError, match="list of holidays"):
        read_holiday_file(f, 2026)


def test_yaml_entry_missing_a_field_is_refused(tmp_path):
    f = tmp_path / "hol.yaml"
    f.write_text("- date: 2026-01-01\n", encoding="utf-8")
    with pytest.raises(DefinitionError, match="entry 0"):
        read_holiday_file(f, 2026)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_calendar_holiday_import.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'ctrlgrid.generators.holiday_import'`.

- [ ] **Step 3: Write the module with the YAML path (and the shared scaffolding)**

Create `ctrlgrid/generators/holiday_import.py`:

```python
"""Read holidays from a file for the `calendar` generator (§ 7.12).

Two formats: a YAML list of `{date, label}` maps, and a concrete-dated
iCalendar `.ics` feed. The reader filters to the calendar year and reports the
counts and origin the run report names. It knows nothing about pydantic or the
calendar model — the model resolves the path, merges with the inline list, and
builds the report line from what this returns.

The `.ics` support is deliberately narrow (§ 5.1): only events with a concrete
`VALUE=DATE` start are represented. Recurring (`RRULE`) or timed (DATE-TIME)
events are skipped and *counted*, never silently dropped.
"""

from __future__ import annotations

import codecs
import datetime
from dataclasses import dataclass
from pathlib import Path

from ctrlgrid.errors import DefinitionError


@dataclass(frozen=True)
class HolidayImport:
    """What a holiday file yields, ready for the model to merge and report.

    `entries` are `{date, label}` dicts already filtered to the calendar year.
    `total` is how many concrete-dated entries the file held (before the year
    filter); `skipped` is how many `.ics` events could not be represented
    (recurring or timed); `origin` names the source for the report.
    """

    entries: list[dict]
    total: int
    skipped: int
    origin: str


def _decode(data: bytes, path: Path) -> str:
    """Bytes → text with the same care as `read_names` (§ 9.4): holiday files,
    like name lists, come out of spreadsheets and export CP1252 far too often;
    "invalid start byte" is useless then."""
    data = data.removeprefix(codecs.BOM_UTF8)
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError as error:
        line = data.count(b"\n", 0, error.start) + 1
        column = error.start - (data.rfind(b"\n", 0, error.start) + 1) + 1
        raise DefinitionError(
            f"{path} is not valid UTF-8: line {line}, byte {error.start} "
            f"(character {column} of that line) is 0x{data[error.start]:02x}. "
            "Files exported from a spreadsheet are often CP1252 — "
            "re-save the file as UTF-8 (§ 9.4)"
        ) from None


def _coerce_date(value: object) -> datetime.date | None:
    """A YAML date is already a `date`; a quoted ISO string is coerced. Anything
    else is `None`, so the caller can refuse it in the user's terms."""
    if isinstance(value, datetime.date) and not isinstance(value, datetime.datetime):
        return value
    if isinstance(value, datetime.datetime):
        return value.date()
    if isinstance(value, str):
        try:
            return datetime.date.fromisoformat(value.strip())
        except ValueError:
            return None
    return None


def _parse_yaml(text: str, path: Path) -> tuple[list[dict], str]:
    from ruamel.yaml import YAML, YAMLError

    try:
        data = YAML(typ="safe").load(text)
    except YAMLError as error:
        raise DefinitionError(f"{path} is not valid YAML: {error}") from None
    if not isinstance(data, list):
        raise DefinitionError(
            f"{path}: expected a list of holidays (each a date and a label), "
            f"got {type(data).__name__}"
        )
    entries: list[dict] = []
    for index, item in enumerate(data):
        if not isinstance(item, dict) or "date" not in item or "label" not in item:
            raise DefinitionError(
                f"{path}: holiday entry {index} needs a `date` and a `label`"
            )
        date = _coerce_date(item["date"])
        if date is None:
            raise DefinitionError(
                f"{path}: holiday entry {index} has an unreadable date "
                f"{item['date']!r} — use YYYY-MM-DD"
            )
        entries.append({"date": date, "label": str(item["label"])})
    return entries, path.name


def read_holiday_file(path: Path, year: int) -> HolidayImport:
    """Read a holiday file, filter to `year`, and report the counts + origin."""
    try:
        raw = path.read_bytes()
    except OSError as error:
        raise DefinitionError(
            f"cannot read the holidays file {path}: {error.strerror}"
        ) from None
    text = _decode(raw, path)

    suffix = path.suffix.lower()
    if suffix in (".yaml", ".yml"):
        entries, origin = _parse_yaml(text, path)
        skipped = 0
    else:
        raise DefinitionError(
            f"{path}: holidays_file must be .ics, .yaml or .yml, "
            f"not {suffix or '<no extension>'}"
        )

    total = len(entries)
    kept = [entry for entry in entries if entry["date"].year == year]
    return HolidayImport(entries=kept, total=total, skipped=skipped, origin=origin)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_calendar_holiday_import.py -q`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add ctrlgrid/generators/holiday_import.py tests/test_calendar_holiday_import.py
git commit -m "calendar: holiday-file reader — YAML list + year filter (§ 7.12)"
```

---

## Task 2: The `.ics` parser

**Files:**
- Modify: `ctrlgrid/generators/holiday_import.py`
- Test: `tests/test_calendar_holiday_import.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_calendar_holiday_import.py`:

```python
_ICS = """BEGIN:VCALENDAR
PRODID:-//Example//Holidays//EN
X-WR-CALNAME:Austrian Holidays
BEGIN:VEVENT
DTSTART;VALUE=DATE:20260101
SUMMARY:New Year\\, and a comma
END:VEVENT
BEGIN:VEVENT
DTSTART;VALUE=DATE:20260406
SUMMARY:Easter
 Monday
END:VEVENT
BEGIN:VEVENT
DTSTART:20261225T000000Z
SUMMARY:Timed Christmas
END:VEVENT
BEGIN:VEVENT
DTSTART;VALUE=DATE:20260501
RRULE:FREQ=YEARLY
SUMMARY:Recurring May Day
END:VEVENT
BEGIN:VEVENT
DTSTART;VALUE=DATE:20270101
SUMMARY:Next Year
END:VEVENT
END:VCALENDAR
"""


def test_ics_reads_concrete_events_unfolds_and_unescapes(tmp_path):
    f = tmp_path / "hol.ics"
    f.write_text(_ICS.replace("\n", "\r\n"), encoding="utf-8")
    result = read_holiday_file(f, 2026)
    labels = {(e["date"], e["label"]) for e in result.entries}
    assert (datetime.date(2026, 1, 1), "New Year, and a comma") in labels
    assert (datetime.date(2026, 4, 6), "EasterMonday") in labels  # folded line rejoined


def test_ics_skips_timed_and_recurring_events_and_counts_them(tmp_path):
    f = tmp_path / "hol.ics"
    f.write_text(_ICS.replace("\n", "\r\n"), encoding="utf-8")
    result = read_holiday_file(f, 2026)
    # Kept in 2026: New Year + Easter Monday. Next Year (2027) filtered out.
    assert len(result.entries) == 2
    assert result.total == 3          # three concrete events (2026x2 + 2027x1)
    assert result.skipped == 2        # one timed + one recurring


def test_ics_origin_prefers_calname_then_prodid(tmp_path):
    f = tmp_path / "hol.ics"
    f.write_text(_ICS.replace("\n", "\r\n"), encoding="utf-8")
    assert read_holiday_file(f, 2026).origin == "Austrian Holidays"

    no_name = _ICS.replace("X-WR-CALNAME:Austrian Holidays\n", "")
    g = tmp_path / "hol2.ics"
    g.write_text(no_name.replace("\n", "\r\n"), encoding="utf-8")
    assert read_holiday_file(g, 2026).origin == "-//Example//Holidays//EN"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_calendar_holiday_import.py -q`
Expected: FAIL — `read_holiday_file` refuses `.ics` (`holidays_file must be .ics, .yaml or .yml`), because the `.ics` branch is not written yet.

- [ ] **Step 3: Add the `.ics` parser and wire the dispatch**

In `ctrlgrid/generators/holiday_import.py`, add these functions above `read_holiday_file`:

```python
def _unfold(text: str) -> list[str]:
    """RFC 5545 line unfolding: a line beginning with a space or tab continues
    the previous logical line."""
    lines: list[str] = []
    for raw in text.split("\n"):
        raw = raw.rstrip("\r")
        if raw[:1] in (" ", "\t") and lines:
            lines[-1] += raw[1:]
        else:
            lines.append(raw)
    return lines


def _unescape(value: str) -> str:
    """RFC 5545 TEXT unescaping: \\n / \\N → newline, \\, \\; \\\\ literal."""
    out: list[str] = []
    index = 0
    while index < len(value):
        char = value[index]
        if char == "\\" and index + 1 < len(value):
            nxt = value[index + 1]
            out.append({"n": "\n", "N": "\n", ",": ",", ";": ";", "\\": "\\"}.get(nxt, nxt))
            index += 2
        else:
            out.append(char)
            index += 1
    return "".join(out)


def _split_line(line: str) -> tuple[str, dict[str, str], str]:
    """`NAME;PARAM=VAL:value` → (NAME upper, {PARAM: VAL}, value)."""
    head, _, value = line.partition(":")
    parts = head.split(";")
    name = parts[0].strip().upper()
    params = {}
    for part in parts[1:]:
        key, _, val = part.partition("=")
        params[key.strip().upper()] = val.strip()
    return name, params, value


def _parse_ics(text: str) -> tuple[list[dict], int, str | None]:
    entries: list[dict] = []
    skipped = 0
    prodid: str | None = None
    calname: str | None = None

    in_event = False
    date: datetime.date | None = None
    summary = ""
    unusable = False  # timed DTSTART or an RRULE — not representable

    for line in _unfold(text):
        name, params, value = _split_line(line)
        if name == "BEGIN" and value.strip().upper() == "VEVENT":
            in_event, date, summary, unusable = True, None, "", False
        elif name == "END" and value.strip().upper() == "VEVENT":
            in_event = False
            if unusable:
                skipped += 1
            elif date is not None:
                entries.append({"date": date, "label": summary})
        elif name == "PRODID" and prodid is None:
            prodid = value.strip()
        elif name == "X-WR-CALNAME" and calname is None:
            calname = value.strip()
        elif in_event and name == "DTSTART":
            if "T" in value or params.get("VALUE") == "DATE-TIME":
                unusable = True
            else:
                digits = value.strip()[:8]
                date = datetime.date(int(digits[:4]), int(digits[4:6]), int(digits[6:8]))
        elif in_event and name == "RRULE":
            unusable = True
        elif in_event and name == "SUMMARY":
            summary = _unescape(value)

    return entries, skipped, calname or prodid
```

Then change the dispatch in `read_holiday_file` — replace the `else` branch that refuses everything with an `.ics` branch before it:

```python
    suffix = path.suffix.lower()
    if suffix == ".ics":
        entries, skipped, origin = _parse_ics(text)
        origin = origin or path.name
    elif suffix in (".yaml", ".yml"):
        entries, origin = _parse_yaml(text, path)
        skipped = 0
    else:
        raise DefinitionError(
            f"{path}: holidays_file must be .ics, .yaml or .yml, "
            f"not {suffix or '<no extension>'}"
        )
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_calendar_holiday_import.py -q`
Expected: PASS (7 passed).

- [ ] **Step 5: Commit**

```bash
git add ctrlgrid/generators/holiday_import.py tests/test_calendar_holiday_import.py
git commit -m "calendar: .ics holiday parser — concrete dates, skip+count the rest (§ 7.12)"
```

---

## Task 3: Reader edge cases — unknown extension, missing file, bad encoding

**Files:**
- Test: `tests/test_calendar_holiday_import.py`

The behavior already exists (Task 1's dispatch, `_decode`, the `read_bytes`
guard). This task locks it with tests so a later refactor cannot regress the
loud failures (§ 12).

- [ ] **Step 1: Write the failing test**

Append to `tests/test_calendar_holiday_import.py`:

```python
def test_unknown_extension_is_refused_naming_the_supported_set(tmp_path):
    f = tmp_path / "hol.csv"
    f.write_text("2026-01-01,New Year\n", encoding="utf-8")
    with pytest.raises(DefinitionError, match="must be .ics, .yaml or .yml"):
        read_holiday_file(f, 2026)


def test_missing_file_is_refused_with_the_path(tmp_path):
    with pytest.raises(DefinitionError, match="cannot read the holidays file"):
        read_holiday_file(tmp_path / "nope.yaml", 2026)


def test_non_utf8_file_gives_the_cp1252_hint(tmp_path):
    f = tmp_path / "hol.yaml"
    f.write_bytes(b"- date: 2026-01-01\n  label: Caf\xe9 Day\n")  # é as CP1252
    with pytest.raises(DefinitionError, match="CP1252"):
        read_holiday_file(f, 2026)
```

- [ ] **Step 2: Run the tests to verify they pass immediately**

Run: `uv run pytest tests/test_calendar_holiday_import.py -q`
Expected: PASS (10 passed). These assert existing behavior; if any fails, the
message wording drifted — fix the message, not the test intent.

- [ ] **Step 3: (No implementation needed — behavior already present.)**

- [ ] **Step 4: Commit**

```bash
git add tests/test_calendar_holiday_import.py
git commit -m "calendar: lock the loud holiday-file failures with tests (§ 12)"
```

---

## Task 4: Wire into `CalendarConfig` — fields, path resolution, merge

**Files:**
- Modify: `ctrlgrid/generators/calendar.py:147-186` (the `CalendarConfig` class)
- Test: `tests/test_calendar_holiday_import.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_calendar_holiday_import.py`:

```python
from ctrlgrid.generators.calendar import CalendarConfig


def _cfg(tmp_path, **kw):
    return CalendarConfig.model_validate(
        {"year": 2026, **kw}, context={"base_dir": tmp_path}
    )


def test_holidays_file_is_resolved_relative_to_base_dir_and_imported(tmp_path):
    (tmp_path / "hol.yaml").write_text(
        "- date: 2026-01-01\n  label: New Year\n", encoding="utf-8"
    )
    cfg = _cfg(tmp_path, holidays_file="hol.yaml")
    assert {(h.date, h.label) for h in cfg.holidays} == {
        (datetime.date(2026, 1, 1), "New Year")
    }


def test_inline_and_file_are_merged_inline_wins_on_collision(tmp_path):
    (tmp_path / "hol.yaml").write_text(
        "- date: 2026-01-01\n  label: File New Year\n"
        "- date: 2026-12-25\n  label: Christmas\n",
        encoding="utf-8",
    )
    cfg = _cfg(
        tmp_path,
        holidays_file="hol.yaml",
        holidays=[{"date": "2026-01-01", "label": "Inline New Year"}],
    )
    by_date = {h.date: h.label for h in cfg.holidays}
    assert by_date[datetime.date(2026, 1, 1)] == "Inline New Year"  # inline wins
    assert by_date[datetime.date(2026, 12, 25)] == "Christmas"
    assert len(cfg.holidays) == 2


def test_holidays_are_sorted_by_date(tmp_path):
    (tmp_path / "hol.yaml").write_text(
        "- date: 2026-12-25\n  label: Christmas\n"
        "- date: 2026-01-01\n  label: New Year\n",
        encoding="utf-8",
    )
    cfg = _cfg(tmp_path, holidays_file="hol.yaml")
    assert [h.date for h in cfg.holidays] == [
        datetime.date(2026, 1, 1),
        datetime.date(2026, 12, 25),
    ]


def test_inline_out_of_year_is_still_refused(tmp_path):
    with pytest.raises(ValidationError, match="not in 2026"):
        _cfg(tmp_path, holidays=[{"date": "2027-01-01", "label": "Wrong Year"}])


def test_holidays_source_cannot_be_set_by_the_user(tmp_path):
    # A user value is popped and ignored; no file → no source.
    cfg = _cfg(tmp_path, holidays_source="forged")
    assert cfg.holidays_source is None
```

Add `ValidationError` to the imports at the top of the test file if not present:

```python
from pydantic import ValidationError
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_calendar_holiday_import.py -q`
Expected: FAIL — `holidays_file` / `holidays_source` are extra keys
(`extra_forbidden`), and `CalendarConfig` has no import logic yet.

- [ ] **Step 3: Add the fields and the before-validator**

In `ctrlgrid/generators/calendar.py`, add the import near the top (after the
existing `from ctrlgrid...` imports, around line 29):

```python
from pathlib import Path

from ctrlgrid.generators.holiday_import import read_holiday_file
```

In `CalendarConfig` (around line 152-162), add the two fields beside `holidays`:

```python
    holidays: tuple[Holiday, ...] = ()
    holidays_file: str | None = None
    #: Computed provenance for the report (set by the before-validator, never by
    #: the user); `describe()` names it. § 7.12.
    holidays_source: str | None = None
```

Add this before-validator to `CalendarConfig` (place it above
`_holidays_fall_in_the_year` so field validators still run on the merged data;
before-validators always run first regardless, but keep the reading order):

```python
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
        try:
            year = int(data["year"])
        except (KeyError, TypeError, ValueError):
            return data  # let the `year` field report its own error first

        base = (info.context or {}).get("base_dir")
        path = Path(spec)
        if base is not None and not path.is_absolute():
            path = Path(base) / path
        imported = read_holiday_file(path, year)

        merged: dict[datetime.date, str] = {
            entry["date"]: entry["label"] for entry in imported.entries
        }
        stray = []  # inline entries pydantic should report (bad shape/date)
        for item in data.get("holidays") or ():
            date = _inline_date(item)
            if date is None:
                stray.append(item)
            else:
                merged[date] = item["label"]  # inline overrides the file
        data["holidays"] = [
            {"date": date, "label": merged[date]} for date in sorted(merged)
        ] + stray

        kept = len(imported.entries)
        line = f"{kept} holidays from {path.name} ({imported.origin})"
        if imported.total != kept:
            line += f" — kept {kept} of {imported.total} in {year}"
        if imported.skipped:
            line += f", skipped {imported.skipped} recurring/timed events"
        data["holidays_source"] = line
        return data
```

Add this module-level helper near the top of `calendar.py` (after the imports,
before the `Holiday` class):

```python
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
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_calendar_holiday_import.py -q`
Expected: PASS (15 passed).

- [ ] **Step 5: Run the full suite to catch regressions**

Run: `uv run pytest -q && uv run ruff check .`
Expected: all green, ruff clean.

- [ ] **Step 6: Commit**

```bash
git add ctrlgrid/generators/calendar.py tests/test_calendar_holiday_import.py
git commit -m "calendar: holidays_file — resolve, merge (inline wins), sort (§ 7.12)"
```

---

## Task 5: The report line in `describe()`

**Files:**
- Modify: `ctrlgrid/generators/calendar.py:258-267` (`describe`)
- Test: `tests/test_calendar_holiday_import.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_calendar_holiday_import.py`:

```python
from ctrlgrid.generators.calendar import CalendarGenerator


def test_describe_names_the_file_source(tmp_path):
    (tmp_path / "hol.ics").write_text(_ICS.replace("\n", "\r\n"), encoding="utf-8")
    cfg = _cfg(tmp_path, holidays_file="hol.ics")
    lines = CalendarGenerator().describe(cfg)
    assert any(
        "holidays from hol.ics (Austrian Holidays)" in line
        and "kept 2 of 3 in 2026" in line
        and "skipped 2 recurring/timed events" in line
        for line in lines
    )


def test_describe_keeps_the_plain_line_for_inline_only(tmp_path):
    cfg = _cfg(tmp_path, holidays=[{"date": "2026-01-01", "label": "New Year"}])
    assert "1 holidays" in CalendarGenerator().describe(cfg)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_calendar_holiday_import.py -k describe -q`
Expected: FAIL — `describe` still prints `"{n} holidays"`, not the source line.

- [ ] **Step 3: Update `describe`**

In `ctrlgrid/generators/calendar.py`, replace the holidays branch of `describe`
(currently lines 263-264):

```python
        if cfg.holidays:
            lines.append(f"{len(cfg.holidays)} holidays")
```

with:

```python
        if cfg.holidays_source:            # a file was imported — name the source (§ 7.12)
            lines.append(cfg.holidays_source)
        elif cfg.holidays:
            lines.append(f"{len(cfg.holidays)} holidays")
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_calendar_holiday_import.py -k describe -q`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add ctrlgrid/generators/calendar.py tests/test_calendar_holiday_import.py
git commit -m "calendar: describe() names the holiday-file source (§ 7.12)"
```

---

## Task 6: End-to-end — a real PDF, read back

**Files:**
- Test: `tests/test_calendar_holiday_import.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_calendar_holiday_import.py`:

```python
from ctrlgrid.loader import loads
from ctrlgrid.pages import build
from ctrlgrid.writers.pdf import PdfWriter
from pypdf import PdfReader


def test_imported_holiday_appears_on_the_month_page(tmp_path):
    (tmp_path / "hol.yaml").write_text(
        "- date: 2026-01-06\n  label: Epiphany\n", encoding="utf-8"
    )
    definition = (tmp_path / "cal.yaml")
    definition.write_text(
        "version: 1\n"
        "page:\n"
        "  format: a4\n"
        "  margin: 12mm\n"
        "generator: calendar\n"
        "year: 2026\n"
        "holidays_file: hol.yaml\n",
        encoding="utf-8",
    )
    doc = loads(definition.read_text(), source=str(definition))
    out = tmp_path / "cal.pdf"
    build(doc, PdfWriter(str(out)))

    reader = PdfReader(str(out))
    text = "".join(page.extract_text() for page in reader.pages)
    assert "Epiphany" in text
```

Note: mirror an existing calendar definition's exact `pattern:` shape if this
one is refused — check `examples/` for the `calendar` def and copy its top-level
keys. The point of the test is only that an imported label renders like an
inline one; keep the def minimal.

- [ ] **Step 2: Run the test to verify it fails, then passes**

Run: `uv run pytest tests/test_calendar_holiday_import.py -k month_page -q`
Expected: PASS if the wiring is correct. If it FAILS because the def is
rejected (wrong top-level shape), fix the definition string to match the
working `examples/` calendar def — this is a test-authoring fix, not a code
change. If "Epiphany" is missing, the import did not reach the page — debug with
`systematic-debugging` before proceeding.

- [ ] **Step 3: Commit**

```bash
git add tests/test_calendar_holiday_import.py
git commit -m "calendar: end-to-end — imported holiday renders on the page (§ 7.12)"
```

---

## Task 7: Update the spec and the handover docs

**Files:**
- Modify: `docs/pflichtenheft-vorlagengenerator.md:1163-1164` (§ 7.12 closing line)
- Modify: `docs/CLAUDE.md` (the calendar row + the intro's "only … is left")
- Modify: `docs/implementation-decisions.md` (append a numbered decision)

- [ ] **Step 1: Close the § 7.12 open line in the spec**

In `docs/pflichtenheft-vorlagengenerator.md`, replace:

```
Notizen. `{year}` als Kopf-Platzhalter. Offen bleibt nur der
Feiertags-**Datei**import (Inline-Liste funktioniert).
```

with:

```
Notizen. `{year}` als Kopf-Platzhalter. Feiertage kommen **inline oder aus
einer Datei** (`holidays_file`, YAML-Liste oder konkret-datiertes `.ics`),
gegen `base_dir` aufgelöst wie `logo`, aufs Jahr gefiltert und mit der
Inline-Liste vereint (Inline gewinnt bei Datumsgleichheit). Wiederkehrende
(`RRULE`) und terminierte (DATE-TIME) `.ics`-Events werden **gezählt
übersprungen**, nie still verschluckt; die Quelle nennt der Laufbericht
(`X-WR-CALNAME`/`PRODID`), nichts im PDF. Damit ist § 7.12 vollständig.
```

- [ ] **Step 2: Update `docs/CLAUDE.md`**

Two edits. First, the calendar row of the "Done" table — change its tail:

```
| ... `{year}` header placeholder. Only the holiday *file* import is left (inline works) |
```

to:

```
| ... `{year}` header placeholder. Holidays come inline **or from a file** (`holidays_file`: a YAML list or a concrete-dated `.ics`, resolved against `base_dir` like `logo`, filtered to the year, merged with inline — inline wins on a date clash; `.ics` recurring/timed events skipped and counted; source named in the run report). **§ 7.12 is complete.** |
```

Second, the intro paragraph — change:

```
... only importing holidays from a *file* is left (an inline list works). Only
M5's two device edges are otherwise left (see *Not done*).
```

to:

```
... and holidays now import from a file too (`holidays_file`, YAML or `.ics`,
§ 7.12) — the calendar is complete. Only M5's two device edges are otherwise
left (see *Not done*).
```

- [ ] **Step 3: Append an implementation decision**

Read the last few decisions in `docs/implementation-decisions.md` to get the
number and format (the handover says "forty-two so far"), then append:

```markdown
## Decision 43 — holiday file import loads in a before-validator (§ 7.12)

`holidays_file` resolves in a `CalendarConfig` `model_validator(mode="before")`,
not a loader function like `read_names`. Reason: `read_names` is CLI-flag-driven
(`--names`), holidays are def-driven like `logo`; the before-validator is where
`base_dir` is in the validation context and the raw fields are still dicts, so
the normal `Holiday` validation runs on the merged result. The `.ics` parser is
hand-written and deliberately narrow — concrete `VALUE=DATE` events only;
recurring/timed events are skipped and counted, never silently dropped (§ 5.1).
Merge rule: inline wins on a shared date (hand-authored beats a feed). The
UTF-8/CP1252 decode is replicated from `read_names` rather than imported, to
avoid a generator→loader import cycle; the shared contract is the message text.
```

- [ ] **Step 4: Verify the whole suite once more**

Run: `uv run pytest -q && uv run ruff check .`
Expected: all green, ruff clean.

- [ ] **Step 5: Commit**

```bash
git add docs/pflichtenheft-vorlagengenerator.md docs/CLAUDE.md docs/implementation-decisions.md
git commit -m "docs: close § 7.12 — holidays import from a file (YAML or .ics)"
```

---

## Self-Review Notes (author)

- **Spec coverage:** every decision in the design table maps to a task — formats
  (T1 YAML, T2 `.ics`), reference + merge (T4), year filter (T1/T2 reader), skip
  + count (T2), source in report (T5), inline-out-of-year still refused (T4),
  def-relative path (T4), end-to-end render (T6), docs (T7).
- **No placeholders:** every code step shows the actual code; T6's one
  conditional ("if the def is rejected, match `examples/`") is a test-authoring
  contingency, not a code placeholder.
- **Type consistency:** `HolidayImport(entries, total, skipped, origin)` is
  defined in T1 and used unchanged in T2/T4/T5; `read_holiday_file(path, year)`
  signature is stable throughout; `_inline_date` / `_coerce_date` are distinct by
  design (one for calendar inline dicts, one for YAML file items).
