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
