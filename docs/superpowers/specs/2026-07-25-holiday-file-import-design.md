# Calendar — holiday import from a file

**Date:** 2026-07-25
**Status:** approved (brainstorming), ready for implementation
**Touches:** `ctrlgrid/generators/calendar.py`, a new
`ctrlgrid/generators/holiday_import.py`, their tests, spec § 7.12, CLAUDE.md,
`docs/implementation-decisions.md`.

## Goal

Close the one calendar feature still open in § 7.12: **importing holidays from a
file** instead of only an inline list. An inline `holidays:` list already works
(`Holiday` model, `calendar.py:40`, validated against the year at
`calendar.py:178`). This adds a `holidays_file:` key that reads holidays from a
**YAML list** or an **iCalendar `.ics`** file, merges them with any inline list,
and names the source in the run report.

The tool's one promise is dimensional accuracy, not a calendar-data engine — so
the `.ics` support is deliberately narrow (concrete-dated events only) and every
other decision keeps the failure loud, never silent (§ 5.1, § 12).

## Decisions (from brainstorming)

| Question | Decision |
|---|---|
| File formats | **Both** YAML list and `.ics`. (CSV and full iCalendar rejected.) |
| Reference | New key **`holidays_file: path`** beside `holidays:`; both allowed, entries **merged**. |
| Merge collision | Same date in both → **inline wins** (hand-authored overrides the feed). |
| Multi-year file | **Filter to the calendar year**, report `kept N of M`; do not refuse. |
| `.ics` scope | **Concrete date-events only**: `VALUE=DATE` `DTSTART` + `SUMMARY`. |
| Unsupported `.ics` (`RRULE`, DATE-TIME) | **Skip and count** in the report — never silently dropped. |
| Source attribution | **Named in the run report** (`describe()`); nothing printed in the PDF. |
| Inline out-of-year | Still **refused** by the existing validator — only file entries are filtered. |

## Architecture — where loading happens

A **`model_validator(mode="before")`** on `CalendarConfig`. This is the seam-1
spot (definition → model, § 3.6): the before-validator receives the raw `data`
dict (`year`, `holidays`, `holidays_file`) **and** `info.context["base_dir"]`,
which the loader already threads into the calendar config's validation
(`loader.py:250` → `model_validate(data, context=context)`, `loader.py:802`).
This is exactly how `px`/relative measures resolve in the loader's validation
context and how `logo` anchors against `base_dir` (`calendar.py:113`). No blade,
no handle change.

*Alternative considered and rejected:* a `read_holidays()` in `loader.py`
mirroring `read_names()` (`loader.py:577`). Rejected because `read_names` is
**CLI-flag-driven** (`--names file`), while holidays are purely **def-driven**
like `logo`. The before-validator is the consistent home; the loader function is
not.

### before-validator flow

1. Pop any user-supplied `holidays_source` (it is computed, not input).
2. If no `holidays_file`, return unchanged (inline path untouched).
3. Resolve `holidays_file` against `base_dir` (def-relative, like `logo`).
4. Dispatch by extension: `.ics` → the `.ics` parser; `.yaml`/`.yml` → the YAML
   reader. Any other extension → loud `DefinitionError` naming the supported set.
5. **Filter** the file entries to `year`; remember `M` (total parsed) and how
   many fell outside the year, plus how many `.ics` events were skipped.
6. **Merge**: key by ISO date, file entries first, inline entries overwrite on
   collision. Sort the result by `(date, label)` for determinism (§ 12, same
   bytes).
7. Write the merged list to `data["holidays"]` (each entry a `{date, label}`
   dict, so the normal `Holiday` field validation still runs) and the computed
   provenance string to `data["holidays_source"]`.

The existing `_holidays_fall_in_the_year` after-validator (`calendar.py:178`)
stays: file entries are pre-filtered so they pass, and a hand-written inline
entry in the wrong year is still caught.

## The report line (source attribution)

A new **internal** field `holidays_source: str | None = None` on
`CalendarConfig`, set only by the before-validator (user input to it is popped).
`describe()` (`calendar.py:258`) replaces its current `"{n} holidays"` line with
the provenance string when a file was used, e.g.

```
12 holidays from holidays.ics (Google Calendar) — kept 12 of 40 in 2026, skipped 2 recurring/timed events
```

- **YAML origin:** the file name.
- **`.ics` origin:** `X-WR-CALNAME` if present, else `PRODID`, else the file name.
- Inline-only (no file) keeps today's `"{n} holidays"` line unchanged.

## The `.ics` parser (`holiday_import.py`)

Concrete-dated all-day events only. No new dependencies; hand-parsed and
deterministic.

1. **Read** bytes with the same UTF-8/CP1252 care as `read_names`
   (`loader.py:591`) — the "re-save as UTF-8" message reused, since `.ics`
   exports hit the same trap.
2. **Unfold** RFC 5545 folded lines: a CRLF (or LF) followed by a space or tab
   continues the previous logical line.
3. Walk `BEGIN:VEVENT … END:VEVENT` blocks; ignore `VTIMEZONE`, `VALARM`, etc.
4. Within a VEVENT:
   - `DTSTART;VALUE=DATE:YYYYMMDD` (or bare `DTSTART:YYYYMMDD`) → the date.
   - A `DTSTART` containing `T` (DATE-TIME) or a VEVENT with `RRULE` →
     **skipped and counted** (not represented).
   - `SUMMARY` → the label, unescaping `\,` `\;` `\n` `\\` per RFC 5545.
5. Return `(entries, skipped_count, origin)`.

## The YAML reader (`holiday_import.py`)

`ruamel` safe-load. The document must be a **list of maps**, each with `date`
and `label`. Shape errors are refused loudly (naming the index). The `date`
strings are left for the `Holiday` field to parse, so date validation and its
message stay in one place.

## Modules & files

- **New** `ctrlgrid/generators/holiday_import.py`: `read_holiday_file(path,
  year) -> (entries, notes)` plus the two parsers. Keeps `calendar.py` focused.
- `calendar.py`: the before-validator, the `holidays_source` field, the
  `describe()` change.
- Tests: `tests/test_calendar_holiday_import.py` (new) — TDD, failing first.

## Testing (TDD, failing first)

- YAML file merged with inline; inline wins on a shared date.
- `.ics` concrete events parsed; SUMMARY unescaped; folded line rejoined.
- Multi-year file filtered to the year; `kept N of M` in the report.
- `.ics` with an `RRULE` event and a DATE-TIME event → both skipped, count in
  the report, the concrete events still imported.
- Unknown extension refused, naming the supported set.
- Missing/unreadable file refused before page one (§ 12), path shown.
- def-relative resolution against `base_dir`.
- Non-UTF-8 `.ics` gives the CP1252 hint.
- Inline out-of-year entry still refused (file entries filtered).
- **A real rendered PDF** read back with `tests/pdfread.py` — the imported
  holiday label appears on its month/day page, exactly as an inline one does.

## Out of scope (named, per § 5)

- `RRULE` expansion, timezones, DATE-TIME events (skipped and counted).
- CSV and full iCalendar component support.
- Any holiday source printed *inside* the PDF (report only).
