"""Name lists (§ 9.4) — the thing no comparable tool does at all (§ 1.1).

A list belongs outside the definition: the structure is the form, the list is a
throwaway file. Mechanically it is the same page(i) model as the maze seed.

Two modes, and which one applies is decided by whether a page count was named:
with a list and no count, the data leads and there is one sheet per entry.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ctrlgrid.errors import DefinitionError
from ctrlgrid.loader import loads, read_names

MINIMAL = """
version: 1
header:
  height: 10mm
  gap: 4mm
  center: "{name}"
generator: lines
families:
  - {direction: horizontal, base_spacing: 10mm}
"""


def write(tmp_path: Path, text: str, name: str = "class.txt") -> Path:
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


class TestReadingTheFile:
    def test_one_entry_per_line(self, tmp_path: Path) -> None:
        path = write(tmp_path, "Anna Berger\nBert Cole\nCarla Dietz\n")
        assert read_names(path) == ["Anna Berger", "Bert Cole", "Carla Dietz"]

    def test_a_trailing_newline_is_not_an_empty_name(self, tmp_path: Path) -> None:
        assert len(read_names(write(tmp_path, "Anna\nBert\n"))) == 2

    def test_blank_lines_are_skipped(self, tmp_path: Path) -> None:
        assert read_names(write(tmp_path, "Anna\n\n\nBert\n")) == ["Anna", "Bert"]

    def test_windows_line_endings_work(self, tmp_path: Path) -> None:
        path = tmp_path / "crlf.txt"
        path.write_bytes(b"Anna\r\nBert\r\n")
        assert read_names(path) == ["Anna", "Bert"]

    def test_a_byte_order_mark_is_tolerated(self, tmp_path: Path) -> None:
        # § 9.4: expected UTF-8, BOM tolerated. Windows editors add one.
        path = tmp_path / "bom.txt"
        path.write_bytes(b"\xef\xbb\xbfAnna\nBert\n")
        assert read_names(path) == ["Anna", "Bert"]

    def test_surrounding_whitespace_goes(self, tmp_path: Path) -> None:
        assert read_names(write(tmp_path, "  Anna  \n\tBert\n")) == ["Anna", "Bert"]

    def test_a_missing_file_says_so(self, tmp_path: Path) -> None:
        with pytest.raises(DefinitionError) as excinfo:
            read_names(tmp_path / "nope.txt")
        assert "nope.txt" in str(excinfo.value)

    def test_an_empty_list_is_an_error(self, tmp_path: Path) -> None:
        with pytest.raises(DefinitionError):
            read_names(write(tmp_path, "\n\n"))


class TestEncoding:
    def test_a_decoding_error_names_the_line_and_the_byte(self, tmp_path: Path) -> None:
        # § 9.4: not "invalid start byte". Lists exported from spreadsheets are
        # regularly CP1252, and that is the commonest stumble at this point.
        path = tmp_path / "cp1252.txt"
        path.write_bytes("Anna\nBert\nJürgen Groß\n".encode("cp1252"))
        with pytest.raises(DefinitionError) as excinfo:
            read_names(path)
        message = str(excinfo.value)
        assert "line 3" in message
        assert "byte" in message.lower()
        assert "1252" in message or "spreadsheet" in message.lower()


class TestTheTwoModes:
    def test_a_list_alone_gives_one_sheet_per_entry(self, tmp_path: Path) -> None:
        # § 9.4: data-driven is the default as soon as a list is given.
        names = ["Anna", "Bert", "Carla", "Dora"]
        document = loads(MINIMAL, {"names": names}, source="test")
        assert document.pages.count == 4
        assert document.names == names

    def test_a_page_count_takes_over_and_truncates(self, tmp_path: Path) -> None:
        names = [f"Name {n}" for n in range(27)]
        document = loads(MINIMAL, {"names": names, "pages": 10}, source="test")
        assert document.pages.count == 10
        assert document.names == names[:10]

    def test_truncating_is_said_out_loud(self, tmp_path: Path) -> None:
        # § 9.4: the legitimate "let me look at three sheets first" case — and
        # not silent mutilation, as long as the number is named.
        names = [f"Name {n}" for n in range(27)]
        document = loads(MINIMAL, {"names": names, "pages": 10}, source="test")
        assert any("10 of 27" in notice for notice in document.notices)

    def test_a_short_list_repeats_cyclically(self, tmp_path: Path) -> None:
        document = loads(MINIMAL, {"names": ["Anna", "Bert"], "pages": 5}, source="test")
        assert document.names == ["Anna", "Bert", "Anna", "Bert", "Anna"]

    def test_a_count_in_the_definition_also_fixes_the_number(self) -> None:
        text = MINIMAL.replace("version: 1", "version: 1\npages:\n  count: 2")
        document = loads(text, {"names": ["Anna", "Bert", "Carla"]}, source="test")
        assert document.pages.count == 2

    def test_an_exact_match_says_nothing(self) -> None:
        document = loads(MINIMAL, {"names": ["Anna", "Bert"], "pages": 2}, source="test")
        assert document.notices == ()


class TestInlineLists:
    def test_a_list_may_sit_in_the_definition_for_the_one_off_case(self) -> None:
        # § 9.4: allowed, but not the intended way — the list is a throwaway
        # file and the definition is the form.
        text = MINIMAL.replace("version: 1", "version: 1\npages:\n  names: [Anna, Bert]")
        document = loads(text, source="test")
        assert document.names == ["Anna", "Bert"]
        assert document.pages.count == 2

    def test_the_command_line_beats_the_definition(self) -> None:
        # § 11, without exception.
        text = MINIMAL.replace("version: 1", "version: 1\npages:\n  names: [Anna, Bert]")
        document = loads(text, {"names": ["Xaver"]}, source="test")
        assert document.names == ["Xaver"]


class TestOnTheSheet:
    def test_each_page_carries_its_own_name(self, tmp_path: Path) -> None:
        import pdfread

        from ctrlgrid.pages import build
        from ctrlgrid.writers.pdf import PdfWriter

        path = tmp_path / "class.pdf"
        document = loads(MINIMAL, {"names": ["Anna Berger", "Bert Cole"]}, source="test")
        build(document, PdfWriter(path))

        assert "Anna Berger" in pdfread.text_on(path, 0)
        assert "Bert Cole" in pdfread.text_on(path, 1)

    def test_the_entries_become_a_table_of_contents(self, tmp_path: Path) -> None:
        # § 10.1: so a 30-page document can be navigated.
        from pypdf import PdfReader

        from ctrlgrid.pages import build
        from ctrlgrid.writers.pdf import PdfWriter

        path = tmp_path / "class.pdf"
        document = loads(MINIMAL, {"names": ["Anna Berger", "Bert Cole"]}, source="test")
        build(document, PdfWriter(path))

        titles = [str(item.title) for item in PdfReader(str(path)).outline]
        assert titles == ["Anna Berger", "Bert Cole"]

    def test_a_run_without_names_has_no_table_of_contents(self, tmp_path: Path) -> None:
        from pypdf import PdfReader

        from ctrlgrid.pages import build
        from ctrlgrid.writers.pdf import PdfWriter

        path = tmp_path / "plain.pdf"
        plain = MINIMAL.replace('  center: "{name}"', '  center: "Class 3B"')
        build(loads(plain, {"pages": 2}, source="test"), PdfWriter(path))
        assert list(PdfReader(str(path)).outline) == []

    def test_naming_names_stays_reproducible(self, tmp_path: Path) -> None:
        # § 10.1 holds for data-driven runs too — the outline must not carry a
        # timestamp or a random key either.
        from ctrlgrid.pages import build
        from ctrlgrid.writers.pdf import PdfWriter

        outputs = []
        for run in ("one", "two"):
            path = tmp_path / f"{run}.pdf"
            document = loads(MINIMAL, {"names": ["Anna", "Bert"]}, source="test")
            build(document, PdfWriter(path))
            outputs.append(path.read_bytes())
        assert outputs[0] == outputs[1]


class TestWithoutAList:
    def test_the_placeholder_still_refuses(self) -> None:
        # § 8.10: not an empty string — that would quietly produce a sheet with
        # a blank header where one was expected.
        from ctrlgrid.pages import preflight
        from ctrlgrid.writers.pdf import PdfWriter

        document = loads(MINIMAL, source="test")
        with pytest.raises(DefinitionError) as excinfo:
            preflight(document, PdfWriter("unused.pdf"))
        assert "--names" in str(excinfo.value)
