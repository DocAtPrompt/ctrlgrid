"""Holiday file import for the calendar — § 7.12.

The reader turns a path (.yaml/.yml or .ics) into holidays filtered to the
calendar's year, with the counts and origin the report needs. Parsing lives
here; the calendar model only resolves the path, merges and reports.
"""

from __future__ import annotations

import datetime

import pytest
from pydantic import ValidationError
from pypdf import PdfReader

from ctrlgrid.errors import DefinitionError
from ctrlgrid.generators.calendar import CalendarConfig, CalendarGenerator
from ctrlgrid.generators.holiday_import import read_holiday_file
from ctrlgrid.loader import loads
from ctrlgrid.pages import build
from ctrlgrid.writers.pdf import PdfWriter


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


def test_ics_invalid_dtstart_is_refused_loudly(tmp_path):
    ics = (
        "BEGIN:VCALENDAR\n"
        "BEGIN:VEVENT\n"
        "DTSTART;VALUE=DATE:20260231\n"  # 31 February — calendrically invalid
        "SUMMARY:Impossible\n"
        "END:VEVENT\n"
        "END:VCALENDAR\n"
    )
    f = tmp_path / "hol.ics"
    f.write_text(ics.replace("\n", "\r\n"), encoding="utf-8")
    with pytest.raises(DefinitionError, match="DTSTART"):
        read_holiday_file(f, 2026)


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


def test_non_string_holidays_file_reports_the_field_type_error(tmp_path):
    # The before-validator runs before field coercion; a non-string spec must not
    # reach Path() and raise a bare TypeError — pydantic reports the str-field
    # type error cleanly (non-negotiable #6 / § 12).
    with pytest.raises(ValidationError, match="holidays_file"):
        _cfg(tmp_path, holidays_file=123)


def test_yaml_report_line_does_not_double_the_filename(tmp_path):
    (tmp_path / "hol.yaml").write_text(
        "- date: 2026-01-01\n  label: New Year\n", encoding="utf-8"
    )
    cfg = _cfg(tmp_path, holidays_file="hol.yaml")
    lines = CalendarGenerator().describe(cfg)
    assert "1 holidays from hol.yaml" in lines
    assert not any("(hol.yaml)" in line for line in lines)


def test_imported_holiday_appears_on_the_month_page(tmp_path):
    (tmp_path / "hol.yaml").write_text(
        "- date: 2026-01-06\n  label: Epiphany\n", encoding="utf-8"
    )
    definition = tmp_path / "cal.yaml"
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
