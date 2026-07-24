"""Embedding the definition as a PDF file attachment (§ 8.8, § 15 point 5).

`pages.embed_def` / `--embed-def` makes the PDF carry its own source: the exact
bytes the user wrote, the same text the cover's checksum is taken over (§ 8.8).
So a sheet that came out right reproduces itself years later without anyone
finding the definition again.

The mechanism is a real PDF EmbeddedFile in the catalog's `/Names
/EmbeddedFiles` name tree, plus `/AF` — reportlab has no filespec support, so
the writer builds the objects itself. Two invariants ride on that:
identical input still gives identical bytes (§ 10.1), and the PNG writer, which
cannot carry an attachment, refuses the run by name rather than dropping it
(§ 10.2).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pypdf import PdfReader

from ctrlgrid.errors import CtrlGridError, DefinitionError
from ctrlgrid.loader import loads
from ctrlgrid.pages import build
from ctrlgrid.writers import Attachment, DocumentMeta
from ctrlgrid.writers.pdf import PdfWriter

A4 = (210000, 297000)

DEF = (
    "version: 1\n"
    "page:\n  format: a4\n"
    "generator: lines\n"
    "families:\n"
    "  - {direction: horizontal, base_spacing: 10mm}\n"
)


def write(path: Path, attachment: Attachment | None) -> Path:
    writer = PdfWriter(path)
    writer.begin_document(DocumentMeta(title="test", attachment=attachment))
    writer.begin_page(*A4)
    writer.end_page()
    writer.end_document()
    return path


def attachments(path: Path) -> dict[str, bytes]:
    reader = PdfReader(str(path))
    return {name: data[0] for name, data in reader.attachments.items()}


# --------------------------------------------------------------- seam 3 writer


class TestTheWriterEmbeds:
    def test_it_declares_the_capability(self) -> None:
        # § 10.2: a writer says what it can do; the pre-flight refuses the rest.
        assert "attachment" in PdfWriter("unused.pdf").capabilities()

    def test_an_attachment_becomes_an_embedded_file(self, tmp_path: Path) -> None:
        data = b"pattern:\n  count: {x: 5}\n"
        path = write(tmp_path / "a.pdf", Attachment(filename="d.yaml", data=data))
        assert attachments(path) == {"d.yaml": data}

    def test_it_keeps_the_exact_bytes(self, tmp_path: Path) -> None:
        # Not re-encoded, not re-indented: byte-for-byte what the user wrote.
        data = "pattern:\n  # a comment with ü and ß\n  count: {x: 5}\n".encode()
        path = write(tmp_path / "b.pdf", Attachment(filename="d.yaml", data=data))
        assert attachments(path)["d.yaml"] == data

    def test_without_one_nothing_is_embedded(self, tmp_path: Path) -> None:
        path = write(tmp_path / "none.pdf", None)
        assert attachments(path) == {}
        assert b"/EmbeddedFiles" not in path.read_bytes()

    def test_embedding_stays_reproducible(self, tmp_path: Path) -> None:
        # § 10.1: acceptance criterion 3. The manual PDF objects must carry no
        # timestamp and no random id, or every golden comparison in CI breaks.
        att = Attachment(filename="d.yaml", data=b"a: 1\n")
        first = write(tmp_path / "one.pdf", att).read_bytes()
        second = write(tmp_path / "two.pdf", att).read_bytes()
        assert first == second

    def test_it_does_not_clobber_the_outline(self, tmp_path: Path) -> None:
        # The attachment lives in the catalog's `/Names`; the outline (§ 10.1)
        # must survive it. A regression guard: were the outline ever moved to a
        # `/Names /Dests` tree, the wholesale assignment here would wipe it.
        from pypdf import PdfReader

        writer = PdfWriter(tmp_path / "both.pdf")
        writer.begin_document(
            DocumentMeta(title="t", attachment=Attachment("d.yaml", b"a: 1\n"))
        )
        for index in range(3):
            writer.begin_page(*A4)
            writer.outline(f"Page {index}", index=index)
            writer.end_page()
        writer.end_document()

        reader = PdfReader(str(tmp_path / "both.pdf"))
        assert list(reader.attachments) == ["d.yaml"]
        assert [entry.title for entry in reader.outline] == ["Page 0", "Page 1", "Page 2"]


# ----------------------------------------------------------- model & overrides


class TestTheSwitch:
    def test_it_is_off_by_default(self) -> None:
        assert loads(DEF, source="test").pages.embed_def is False

    def test_the_definition_can_ask_for_it(self) -> None:
        text = DEF + "pages:\n  embed_def: true\n"
        assert loads(text, source="test").pages.embed_def is True

    def test_the_flag_switches_it_on(self) -> None:
        # § 11: like --cover, the flag only ever turns it on.
        doc = loads(DEF, {"embed_def": True}, source="test")
        assert doc.pages.embed_def is True

    def test_the_document_carries_its_own_source_text(self) -> None:
        # The embedded bytes are the source, so the model has to keep it.
        assert loads(DEF, source="test").source_text == DEF


# ------------------------------------------------------------- through `build`


class TestABuiltPdf:
    def test_it_carries_its_own_definition(self, tmp_path: Path) -> None:
        text = DEF + "pages:\n  embed_def: true\n"
        doc = loads(text, source="my-grid.yaml")
        path = tmp_path / "out.pdf"
        build(doc, PdfWriter(path))
        assert attachments(path)["my-grid.yaml"] == text.encode("utf-8")

    def test_the_attachment_is_named_after_the_source(self, tmp_path: Path) -> None:
        # A preset name has no extension; the attachment gets `.yaml`.
        text = DEF + "pages:\n  embed_def: true\n"
        doc = loads(text, source="millimeter-a4")
        path = tmp_path / "out.pdf"
        build(doc, PdfWriter(path))
        assert "millimeter-a4.yaml" in attachments(path)

    def test_without_the_switch_there_is_no_attachment(self, tmp_path: Path) -> None:
        doc = loads(DEF, source="test.yaml")
        path = tmp_path / "plain.pdf"
        build(doc, PdfWriter(path))
        assert attachments(path) == {}


# ----------------------------------------------------------- the PNG refusal


class TestPngCannotEmbed:
    def test_it_is_refused_and_named(self, tmp_path: Path) -> None:
        # § 10.2: PNG has no way to carry a file, so the run is refused before
        # a page is written, and the message names the way out (PDF).
        from ctrlgrid.writers.png import PngWriter

        text = (
            "version: 1\n"
            "page:\n  device: remarkable-paper-pro\n"
            "generator: dots\n"
            "grid:\n  x: {base_spacing: 5mm}\n  y: {base_spacing: 5mm}\n"
            "base_size: 0.5mm\n"
            "color: '#000000'\n"
            "pages:\n  embed_def: true\n"
        )
        doc = loads(text, source="test")
        with pytest.raises((DefinitionError, CtrlGridError)) as excinfo:
            build(doc, PngWriter(tmp_path / "out.png"))
        assert "attachment" in str(excinfo.value)
