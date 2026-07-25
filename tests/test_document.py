"""The document-generator seam (§ 7, the calendar) — the handle's document mode.

A document generator offers `pages()` instead of `generate()`: a sequence of
typed pages, each with its own marks, links and destination. The handle detects
it and writes each page — size, destination, marks (translated onto the sheet),
links — rather than looping identical pattern pages. Exercised here with a tiny
two-page fixture generator registered for the test; the real calendar is built on
this seam.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from pydantic import BaseModel, ConfigDict
from pypdf import PdfReader

from ctrlgrid import generators
from ctrlgrid.document import DocumentPage, Link
from ctrlgrid.errors import CtrlGridError, DefinitionError
from ctrlgrid.loader import loads
from ctrlgrid.marks import Area, Point, Text
from ctrlgrid.pages import build
from ctrlgrid.writers.pdf import PdfWriter
from ctrlgrid.writers.png import PngWriter
from tests.pdfread import text_on

_SIZE = round(13 * 25400 / 72)  # 13 pt in micrometres


class _DocConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class _TwoPageDoc:
    """A minimal document generator: two pages that link to each other."""

    name = "_testdoc"
    config_model = _DocConfig
    supports_snap = False

    def is_page_invariant(self, cfg: _DocConfig) -> bool:
        return True

    def periodic_axes(self, cfg: _DocConfig) -> dict[str, list]:
        return {}

    def describe(self, cfg: _DocConfig) -> list[str]:
        return ["two linked pages"]

    def check(self, cfg: _DocConfig, *, area: Area, q: object) -> None:
        return None

    def page_count(self, cfg: _DocConfig, *, area: Area) -> int:
        return 2

    def generate(self, cfg, *, area, page, q):  # never called for a document
        raise AssertionError("a document generator produces pages, not marks")

    def pages(self, cfg: _DocConfig, *, area: Area, q: object) -> Iterator[DocumentPage]:
        for dest, other, title, part in (
            ("one", "two", "One", "first"), ("two", "one", "Two", "second"),
        ):
            yield DocumentPage(
                dest=dest,
                kind="test",
                placeholders=(("part", part),),
                marks=(
                    Text(pos=Point(0, area.height - _SIZE), content=f"Page {dest}", size=_SIZE),
                ),
                links=(Link(Point(0, 0), Point(50_000, 10_000), other),),
                title=title,
            )


@pytest.fixture
def registered() -> Iterator[None]:
    generators.REGISTRY["_testdoc"] = _TwoPageDoc()  # type: ignore[assignment]
    try:
        yield
    finally:
        del generators.REGISTRY["_testdoc"]


DEF = "version: 1\npage: {format: a4, margin: 10mm}\ngenerator: _testdoc\n"
DEVICE_DEF = "version: 1\npage: {device: remarkable-paper-pro}\ngenerator: _testdoc\n"


def _annotations(page) -> list:
    annots = page.get("/Annots")
    return [a.get_object() for a in annots] if annots else []


def _dest_index(reader: PdfReader, annot) -> int | None:
    target = annot["/Dest"][0]
    for i, page in enumerate(reader.pages):
        if page.indirect_reference.idnum == target.idnum:
            return i
    return None


class TestDocumentMode:
    def test_it_writes_the_pages_the_generator_produces(self, registered, tmp_path: Path) -> None:
        build(loads(DEF, source="test"), PdfWriter(tmp_path / "d.pdf"))
        assert len(PdfReader(str(tmp_path / "d.pdf")).pages) == 2

    def test_the_links_resolve_across_pages(self, registered, tmp_path: Path) -> None:
        build(loads(DEF, source="test"), PdfWriter(tmp_path / "d.pdf"))
        reader = PdfReader(str(tmp_path / "d.pdf"))
        link0 = [a for a in _annotations(reader.pages[0]) if a.get("/Subtype") == "/Link"][0]
        link1 = [a for a in _annotations(reader.pages[1]) if a.get("/Subtype") == "/Link"][0]
        assert _dest_index(reader, link0) == 1   # page one → page two
        assert _dest_index(reader, link1) == 0   # page two → page one

    def test_each_page_becomes_a_bookmark(self, registered, tmp_path: Path) -> None:
        build(loads(DEF, source="test"), PdfWriter(tmp_path / "d.pdf"))
        outline = PdfReader(str(tmp_path / "d.pdf")).outline
        assert [o.title for o in outline] == ["One", "Two"]

    def test_two_runs_produce_identical_bytes(self, registered, tmp_path: Path) -> None:
        build(loads(DEF, source="test"), PdfWriter(tmp_path / "a.pdf"))
        build(loads(DEF, source="test"), PdfWriter(tmp_path / "b.pdf"))
        assert (tmp_path / "a.pdf").read_bytes() == (tmp_path / "b.pdf").read_bytes()


class TestPngIsRefused:
    def test_a_document_on_png_is_refused_for_want_of_links(
        self, registered, tmp_path: Path
    ) -> None:
        # § 10.2: PNG has neither links nor text, so a document is refused before
        # a page is written, naming the missing capability.
        doc = loads(DEVICE_DEF, source="test")
        with pytest.raises((DefinitionError, CtrlGridError)) as excinfo:
            build(doc, PngWriter(tmp_path / "out.png"))
        assert "link" in str(excinfo.value)


class TestBandsArePerPage:
    """§ 8.10: placeholders are filled per page — and the document path used to
    be the exception, laying its bands out once and stamping them everywhere.

    A calendar is navigated by tapping and wants no page numbers, which is why
    nobody noticed; a notebook is flipped through and does (§ 7.13).
    """

    HEADER = (
        "version: 1\npage: {format: a4, margin: 10mm}\n"
        "header:\n  height: 8mm\n  gap: 2mm\n  center: '{page} / {page_count}'\n"
        "generator: _testdoc\n"
    )

    def test_the_page_number_counts_up(self, registered, tmp_path: Path) -> None:
        path = tmp_path / "d.pdf"
        build(loads(self.HEADER, source="test"), PdfWriter(path))
        assert "1 / 2" in text_on(path, 0)
        assert "2 / 2" in text_on(path, 1)

    def test_a_page_may_supply_its_own_placeholder(self, registered, tmp_path: Path) -> None:
        # `{section}` is the notebook's case: only the generator knows which
        # section a page belongs to, only the handle knows its number.
        definition = (
            "version: 1\npage: {format: a4, margin: 10mm}\n"
            "header:\n  height: 8mm\n  gap: 2mm\n  left: '{part}'\n"
            "generator: _testdoc\n"
        )
        path = tmp_path / "d.pdf"
        build(loads(definition, source="test"), PdfWriter(path))
        assert "first" in text_on(path, 0)
        assert "second" in text_on(path, 1)

    def test_a_band_without_a_per_page_placeholder_is_the_same_on_every_page(
        self, registered, tmp_path: Path
    ) -> None:
        # The calendar's case, and the reason this change is invisible there:
        # constant text lays out to the same marks on every page.
        definition = (
            "version: 1\npage: {format: a4, margin: 10mm}\n"
            "header:\n  height: 8mm\n  gap: 2mm\n  center: 'constant'\n"
            "generator: _testdoc\n"
        )
        path = tmp_path / "d.pdf"
        build(loads(definition, source="test"), PdfWriter(path))
        assert text_on(path, 0).count("constant") == 1
        assert text_on(path, 1).count("constant") == 1
