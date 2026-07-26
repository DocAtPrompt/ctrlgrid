"""Stage 2 of § 10.3 — a named font file, embedded and subset.

The stage exists for one reason: stage 1's standard fonts stop at Latin-1, and
a class list stops with them at the first Polish name. So the test that matters
most here is the one where `ł` goes from an error to a printed letter.

Two rules shape the rest. **A path, never a name** (§ 10.3): name lookup is
different on every platform and is exactly the unreliability the tool avoids.
And **embedding rights are checked, not assumed**: a font whose `fsType`
forbids embedding aborts the run and is named, rather than being quietly
swapped for something else.

The test font is Bitstream Vera Sans, which ships with reportlab and is free to
embed — no font file joins this repository (§ 13).
"""

from __future__ import annotations

from pathlib import Path

import pytest
import reportlab

from ctrlgrid.errors import DefinitionError
from ctrlgrid.fonts import load_font, token_for
from ctrlgrid.loader import loads
from ctrlgrid.model import FontSpec
from ctrlgrid.pages import build
from ctrlgrid.writers.pdf import PdfWriter

VERA = Path(reportlab.__file__).parent / "fonts" / "Vera.ttf"


def restricted(tmp_path: Path, fs_type: int = 0x0002) -> Path:
    """A copy of the test font whose OS/2 table forbids embedding."""
    from fontTools.ttLib import TTFont

    font = TTFont(str(VERA))
    font["OS/2"].fsType = fs_type
    path = tmp_path / "Restricted.ttf"
    font.save(str(path))
    return path


def document(font: str, text: str = "Zoë", tmp: Path | None = None):
    return loads(
        "version: 1\n"
        "header:\n"
        "  height: 12mm\n"
        f"  left: '{text}'\n"
        "  font:\n"
        f"{font}"
        "generator: lines\n"
        "families:\n"
        "  - {direction: horizontal, base_spacing: 10mm}\n",
        source="test",
    )


FILE_FONT = f"    file: '{VERA}'\n    size: 11pt\n"


class TestLoading:
    def test_it_reads_the_name_and_the_version(self) -> None:
        # § 10.3: the cover sheet names file and font version, so both have to
        # come out of the file rather than out of the path.
        font = load_font(str(VERA))
        assert "Vera" in font.name
        assert font.version

    def test_a_missing_file_names_the_path(self) -> None:
        with pytest.raises(DefinitionError) as excinfo:
            load_font("/nowhere/Imaginary.ttf")
        # The message names the file; the separator is the platform's own
        # (backslashes on Windows), so the assertion checks the name, not the
        # POSIX spelling (§ 10.3).
        assert "Imaginary.ttf" in str(excinfo.value)

    def test_something_that_is_not_a_font_says_so(self, tmp_path: Path) -> None:
        impostor = tmp_path / "notafont.ttf"
        impostor.write_text("this is not a font", encoding="utf-8")
        with pytest.raises(DefinitionError) as excinfo:
            load_font(str(impostor))
        assert "notafont.ttf" in str(excinfo.value)

    def test_a_tilde_is_expanded(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # § 10.3 writes the example with `~`, so it has to work. Home is
        # redirected to a temp dir with a font in it, so the test never depends
        # on where the runner's home is — on Windows CI it sits on a different
        # drive from reportlab's Vera, and a cross-drive relative path is an
        # error there (§ 13). Set both names expanduser reads: HOME on POSIX,
        # USERPROFILE on Windows.
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setenv("USERPROFILE", str(tmp_path))
        font_file = tmp_path / "vera.ttf"
        font_file.write_bytes(VERA.read_bytes())
        font = load_font("~/vera.ttf")
        assert font.path == font_file.resolve()

    def test_the_same_file_is_parsed_once(self) -> None:
        assert load_font(str(VERA)) is load_font(str(VERA))


class TestEmbeddingRights:
    """§ 10.3: checked, not assumed — and refused loudly, never substituted."""

    def test_a_restricted_font_is_refused_by_name(self, tmp_path: Path) -> None:
        with pytest.raises(DefinitionError) as excinfo:
            load_font(str(restricted(tmp_path)))
        message = str(excinfo.value)
        assert "Vera" in message or "Restricted.ttf" in message
        assert "fsType" in message and "embed" in message

    def test_a_font_that_forbids_subsetting_is_refused(self, tmp_path: Path) -> None:
        # We always subset (§ 10.3), so "no subsetting" is not a licence we
        # can honour by doing less.
        with pytest.raises(DefinitionError) as excinfo:
            load_font(str(restricted(tmp_path, 0x0104)))
        assert "subset" in str(excinfo.value)

    def test_print_and_preview_embedding_is_allowed(self) -> None:
        # The test font itself: fsType 4, which is what most free fonts carry.
        assert load_font(str(VERA)).fs_type == 4


class TestTheModel:
    def test_a_file_and_a_family_together_are_an_error(self) -> None:
        # § 10.3: two ways of saying which font, pointing at different fonts.
        with pytest.raises(ValueError) as excinfo:
            FontSpec.model_validate({"family": "serif", "file": str(VERA)})
        assert "family" in str(excinfo.value) and "file" in str(excinfo.value)

    def test_a_file_alone_is_fine(self) -> None:
        assert FontSpec.model_validate({"file": str(VERA)}).file == str(VERA)

    def test_the_token_carries_the_resolved_path(self) -> None:
        # The mark vocabulary does not grow for this (§ 6): `family` on a Text
        # mark is a font token, and a file font is one.
        spec = FontSpec.model_validate({"file": str(VERA)})
        assert spec.token == token_for(str(VERA))
        assert FontSpec().token == "sans"


class TestTheWriter:
    def test_it_measures_the_named_font_and_not_helvetica(self) -> None:
        writer = PdfWriter("unused.pdf")
        own = writer.text_width("Hamburgefonstiv", family=token_for(str(VERA)), size=10_000)
        standard = writer.text_width("Hamburgefonstiv", family="sans", size=10_000)
        assert own > 0 and own != standard

    def test_glyph_coverage_comes_from_the_file(self) -> None:
        # The whole point of stage 2: `ł` is missing from the standard fonts
        # and present in this one.
        writer = PdfWriter("unused.pdf")
        assert writer.missing_glyphs("Michał", family="sans") == ["ł"]
        assert writer.missing_glyphs("Michał", family=token_for(str(VERA))) == []

    def test_a_glyph_the_file_lacks_is_still_reported(self) -> None:
        writer = PdfWriter("unused.pdf")
        assert writer.missing_glyphs("Győző", family=token_for(str(VERA))) == ["ő"]


class TestOnTheSheet:
    def test_a_polish_name_reaches_the_paper(self, tmp_path: Path) -> None:
        import pdfread

        path = tmp_path / "polish.pdf"
        build(document(FILE_FONT, text="Michał"), PdfWriter(path))
        assert "Michał" in pdfread.text_on(path)

    def test_the_font_is_embedded(self, tmp_path: Path) -> None:
        # § 10.3: the *PDF* is the same everywhere, even though making it needs
        # a local file. That is only true if the font travels with it.
        from pypdf import PdfReader

        path = tmp_path / "embedded.pdf"
        build(document(FILE_FONT, text="Michał"), PdfWriter(path))
        fonts = PdfReader(str(path)).pages[0]["/Resources"]["/Font"]
        descriptors = [
            font.get_object()["/FontDescriptor"].get_object()
            for font in fonts.values()
            if "/FontDescriptor" in font.get_object()
        ]
        assert any("/FontFile2" in descriptor for descriptor in descriptors)

    def test_without_the_file_the_same_name_is_refused(self, tmp_path: Path) -> None:
        # § 10.2: the message has to point at the way out, not just at the glyph.
        path = tmp_path / "never.pdf"
        with pytest.raises(DefinitionError) as excinfo:
            build(document("    family: sans\n", text="Michał"), PdfWriter(path))
        message = str(excinfo.value)
        assert "ł" in message and "file" in message
        assert not path.exists()

    def test_a_restricted_font_never_reaches_a_page(self, tmp_path: Path) -> None:
        path = tmp_path / "never.pdf"
        blocked = restricted(tmp_path)
        with pytest.raises(DefinitionError):
            build(document(f"    file: '{blocked}'\n"), PdfWriter(path))
        assert not path.exists()

    def test_the_definition_names_the_field_and_the_line(self) -> None:
        with pytest.raises(DefinitionError) as excinfo:
            document("    file: '/nowhere/Imaginary.ttf'\n")
        error = excinfo.value
        assert error.field == "header.font.file"
        assert error.line is not None

    def test_two_runs_produce_identical_bytes(self, tmp_path: Path) -> None:
        # § 10.1 — subsetting must not depend on anything but the input.
        first, second = tmp_path / "a.pdf", tmp_path / "b.pdf"
        for path in (first, second):
            build(document(FILE_FONT, text="Michał"), PdfWriter(path))
        assert first.read_bytes() == second.read_bytes()

    def test_the_cover_names_the_font_file_and_its_version(self) -> None:
        # § 10.3 requires it: the cover sheet has to make the sheet
        # reproducible, and a different font is a different sheet.
        from ctrlgrid.cover import summary

        text = "\n".join(summary(document(FILE_FONT)))
        assert "Vera.ttf" in text
        assert load_font(str(VERA)).version in text

    def test_the_font_line_does_not_run_into_its_label(self) -> None:
        # `header font` is longer than every label the summary had before it,
        # and a fixed label column ran the two together: `header fontVera.ttf`.
        from ctrlgrid.cover import summary

        labels = {
            "generator", "format", "margins", "pattern", "pages", "family",
            "header font", "footer font", "definition", "tool",
        }
        for line in summary(document(FILE_FONT)):
            assert line.split("  ")[0] in labels, line


class TestGlyphsAreCheckedInGeneratorTextToo:
    """§ 12 point 13 asks the pre-flight to measure "Kopf-, Fuß- **und
    Beschriftungstext**" and then: "sind alle Glyphen in der Schrift vorhanden?"

    Only the bands were ever asked. A grid label, a segment label, a form title
    or a calendar's month name went unchecked — so `months: [styczeń, …]` passed
    `check`, reported a successful run, and put `stycze` and a box on the paper.
    The standard PDF fonts reach Latin-1 and no further (§ 10.3), which is
    exactly why `missing_glyphs` exists.
    """

    POLISH_GRID = (
        "version: 1\n"
        "page: {format: a4, margin: 15mm}\n"
        "generator: grid\n"
        "cells: {x: 3, y: 3}\n"
        'labels: {columns: ["Łódź", "Kraków", "Gdańsk"], rows: "n"}\n'
    )

    def test_a_label_the_standard_fonts_cannot_draw_is_refused(self) -> None:
        from ctrlgrid.errors import DefinitionError
        from ctrlgrid.loader import loads
        from ctrlgrid.pages import preflight
        from ctrlgrid.writers.pdf import PdfWriter

        with pytest.raises(DefinitionError) as excinfo:
            preflight(loads(self.POLISH_GRID, source="t"), PdfWriter("unused.pdf"))
        message = str(excinfo.value)
        assert "Ł" in message or "ń" in message
        assert "font" in message  # the way out is naming a font file (§ 10.3)

    def test_latin_1_labels_are_fine(self) -> None:
        from ctrlgrid.loader import loads
        from ctrlgrid.pages import preflight
        from ctrlgrid.writers.pdf import PdfWriter

        text = self.POLISH_GRID.replace(
            '["Łódź", "Kraków", "Gdańsk"]', '["Köln", "Nîmes", "Ávila"]'
        )
        preflight(loads(text, source="t"), PdfWriter("unused.pdf"))

    def test_a_calendar_month_name_is_checked_as_well(self) -> None:
        # The case that started this: a document generator's own text.
        from ctrlgrid.errors import DefinitionError
        from ctrlgrid.loader import loads
        from ctrlgrid.pages import preflight
        from ctrlgrid.writers.pdf import PdfWriter

        text = (
            "version: 1\n"
            "page: {format: a4, margin: 12mm}\n"
            "generator: calendar\n"
            "year: 2027\n"
            "months: [styczeń, luty, marzec, kwiecień, maj, czerwiec, lipiec,\n"
            "         sierpień, wrzesień, październik, listopad, grudzień]\n"
        )
        with pytest.raises(DefinitionError) as excinfo:
            preflight(loads(text, source="t"), PdfWriter("unused.pdf"))
        assert "ń" in str(excinfo.value)

    def test_a_named_font_file_that_covers_them_is_accepted(self) -> None:
        # § 10.3's stage 2 is the documented way out, so it has to actually work.
        #
        # Turkish rather than Polish, and that is the point of the fixture: Vera
        # ships with reportlab and has 256 glyphs — it covers `ğ` and `ş`, which
        # the standard fonts lack, and it does *not* cover `ń`. My first version
        # of this test asked Vera for Polish, failed, and looked like a bug in
        # the check. It was a bug in the probe.
        from pathlib import Path

        import reportlab

        from ctrlgrid.errors import DefinitionError
        from ctrlgrid.loader import loads
        from ctrlgrid.pages import preflight
        from ctrlgrid.writers.pdf import PdfWriter

        turkish = self.POLISH_GRID.replace(
            '["Łódź", "Kraków", "Gdańsk"]', '["Ağrı", "Muş", "Sivas"]'
        )
        with pytest.raises(DefinitionError):
            preflight(loads(turkish, source="t"), PdfWriter("unused.pdf"))

        vera = Path(reportlab.__file__).parent / "fonts" / "Vera.ttf"
        with_font = turkish.replace(
            "cells: {x: 3, y: 3}\n",
            f"cells: {{x: 3, y: 3}}\nfont: {{file: '{vera}', size: 8pt}}\n",
        )
        preflight(loads(with_font, source="t"), PdfWriter("unused.pdf"))
