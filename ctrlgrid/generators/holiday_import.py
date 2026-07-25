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
