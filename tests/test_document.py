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


class TestAPageMayBeFilledByABlade:
    """§ 7.13: a `DocumentPage` may name a blade and its config instead of
    carrying marks, and the **handle** calls that blade — the notebook never
    touches one. One function answers "what is on this page", because the
    writer, the capability pre-flight and the media check all ask."""

    def _filled(self, marks=()):
        from ctrlgrid.document import Fill
        from ctrlgrid.generators.dots import DotsConfig

        config = DotsConfig.model_validate(
            {"grid": {"x": {"base_spacing": "10mm"}, "y": {"base_spacing": "10mm"}},
             "base_size": "0.5mm"}
        )
        return DocumentPage(
            dest="d", kind="section", marks=marks, fill=Fill("dots", config)
        )

    def test_its_own_marks_come_first_then_the_blades(self) -> None:
        from ctrlgrid.marks import Dot
        from ctrlgrid.pages import document_page_marks, page_contexts

        own = Text(pos=Point(0, 0), content="own", size=_SIZE)
        page = self._filled(marks=(own,))
        context = next(page_contexts(count=1, snap=()))
        marks = list(
            document_page_marks(
                page, area=Area(width=100_000, height=100_000), context=context,
                q=PdfWriter("unused.pdf"),
            )
        )
        assert marks[0] is own
        assert all(isinstance(mark, Dot) for mark in marks[1:])
        assert len(marks) > 50   # an 11 x 11 dot grid, at least

    def test_a_page_without_a_fill_is_just_its_marks(self) -> None:
        from ctrlgrid.pages import document_page_marks, page_contexts

        own = Text(pos=Point(0, 0), content="own", size=_SIZE)
        page = DocumentPage(dest="d", kind="plain", marks=(own,))
        context = next(page_contexts(count=1, snap=()))
        assert list(
            document_page_marks(
                page, area=Area(width=1000, height=1000), context=context,
                q=PdfWriter("unused.pdf"),
            )
        ) == [own]


class _Recording(PdfWriter):
    """A real writer that also keeps what it was asked to draw, per page.

    The document path's defects were all *absences* — a mark that should have
    been drawn and was not — so the test has to look at the marks themselves,
    not at whether a file appeared.
    """

    def __init__(self, path: Path) -> None:
        super().__init__(path)
        self.pages_drawn: list[list] = []

    def begin_page(self, width: int, height: int) -> None:
        self.pages_drawn.append([])
        super().begin_page(width, height)

    def draw(self, mark) -> None:
        self.pages_drawn[-1].append(mark)
        super().draw(mark)


NOTEBOOK = (
    "version: 1\n"
    "page: {format: a4, margin: 10mm}\n"
    "generator: notebook\n"
    "sections:\n"
    "  - label: Journal\n"
    "    pages: 2\n"
    "    generator: lines\n"
    "    families: [{direction: horizontal, base_spacing: 5mm, base_weight: 0.3pt}]\n"
)


def _drawn(text: str, tmp_path: Path) -> list[list]:
    writer = _Recording(tmp_path / "doc.pdf")
    build(loads(text, source="test"), writer)
    return writer.pages_drawn


class TestTheDocumentPathCarriesThePageModel:
    """§ 8.1: the frame belongs to the *page*, and a document has pages.

    `_build_document` grew as a second, thinner page path and never gained the
    furniture the blade path draws, while the loader went on accepting the keys
    — so a border, hole marks, a ruler, a stamp and a page background were
    validated, reported as a successful run, and drawn nowhere. § 5.1 calls a
    PDF that is *almost* right the worst failure class there is.
    """

    def test_duplex_moves_the_pattern_on_even_pages(self, tmp_path: Path) -> None:
        # § 8.1: under duplex the margins swap, so everything inside them moves.
        # A notebook is a bound book — this is the one artefact duplex exists for.
        text = NOTEBOOK.replace(
            "page: {format: a4, margin: 10mm}",
            "page:\n  format: a4\n  duplex: true\n"
            "  margin: {top: 10mm, bottom: 10mm, inner: 30mm, outer: 8mm}",
        )
        pages = _drawn(text, tmp_path)
        lefts = [
            min(mark.start.x for mark in page if hasattr(mark, "start"))
            for page in pages
            if any(hasattr(mark, "start") for mark in page)
        ]
        assert len(set(lefts)) > 1, f"every page starts at the same x: {lefts}"

    def test_a_border_reaches_a_document_page(self, tmp_path: Path) -> None:
        plain = _drawn(NOTEBOOK, tmp_path)
        bordered = _drawn(
            NOTEBOOK.replace("generator: notebook", "border: {weight: 0.6pt}\ngenerator: notebook"),
            tmp_path,
        )
        assert sum(len(p) for p in bordered) > sum(len(p) for p in plain)

    def test_hole_marks_reach_a_document_page(self, tmp_path: Path) -> None:
        plain = _drawn(NOTEBOOK, tmp_path)
        punched = _drawn(
            NOTEBOOK.replace("margin: 10mm}", "margin: 10mm, hole_marks: true}"), tmp_path
        )
        assert sum(len(p) for p in punched) > sum(len(p) for p in plain)

    def test_a_page_background_reaches_a_document_page(self, tmp_path: Path) -> None:
        plain = _drawn(NOTEBOOK, tmp_path)
        tinted = _drawn(
            NOTEBOOK.replace("margin: 10mm}", "margin: 10mm, background: '#eeeeee'}"), tmp_path
        )
        assert sum(len(p) for p in tinted) > sum(len(p) for p in plain)

    def test_a_stamp_reaches_a_document_page(self, tmp_path: Path) -> None:
        plain = _drawn(NOTEBOOK, tmp_path)
        stamped = _drawn(
            NOTEBOOK.replace("generator: notebook", "stamp: {text: DRAFT}\ngenerator: notebook"),
            tmp_path,
        )
        assert sum(len(p) for p in stamped) > sum(len(p) for p in plain)

    def test_a_ruler_reaches_a_document_page(self, tmp_path: Path) -> None:
        plain = _drawn(NOTEBOOK, tmp_path)
        ruled = _drawn(
            NOTEBOOK.replace(
                "generator: notebook", "ruler: {edges: [bottom], unit: cm}\ngenerator: notebook"
            ),
            tmp_path,
        )
        assert sum(len(p) for p in ruled) > sum(len(p) for p in plain)


class TestWhatADocumentDoesNotDo:
    """Decision 42 settled that a document takes its own write path — no cover,
    no imposition, no snap. What it did not settle is what happens when someone
    asks for one anyway, and the answer was: nothing, silently. `--nup` went
    further and printed an imposition summary for an imposition that had not
    happened, which § 12 counts as worse than no message at all.
    """

    def test_nup_on_a_document_is_refused_rather_than_reported(self, tmp_path: Path) -> None:
        document = loads(NOTEBOOK, source="test", overrides={"nup": "2x1", "nup_sheet": "a3"})
        with pytest.raises(DefinitionError) as excinfo:
            build(document, PdfWriter(tmp_path / "n.pdf"))
        assert "nup" in str(excinfo.value)

    def test_a_cover_on_a_document_is_refused(self, tmp_path: Path) -> None:
        document = loads(NOTEBOOK, source="test", overrides={"cover": True})
        with pytest.raises(DefinitionError) as excinfo:
            build(document, PdfWriter(tmp_path / "c.pdf"))
        assert "cover" in str(excinfo.value)

    def test_an_align_on_a_document_is_refused(self, tmp_path: Path) -> None:
        # § 8.5 anchors a *pattern* in its area; a document page is not one
        # pattern area, and § 7.13 already refuses `align` per section.
        text = NOTEBOOK.replace(
            "generator: notebook", "pattern: {align: top-left}\ngenerator: notebook"
        )
        with pytest.raises(DefinitionError) as excinfo:
            build(loads(text, source="test"), PdfWriter(tmp_path / "a.pdf"))
        assert "align" in str(excinfo.value)

    def test_a_section_whose_blade_needs_more_than_one_sheet_is_refused(
        self, tmp_path: Path
    ) -> None:
        # A `maze` with separate solution pages states a SheetPlan (decision 27)
        # that the handle carries out — on the blade path. The document path
        # never asks, so the solution landed on the page *before* its puzzle and
        # adding a title page silently redrew every maze. Refused until § 7.13
        # says what a per-section sheet plan should mean.
        text = (
            "version: 1\npage: {format: a4, margin: 10mm}\ngenerator: notebook\n"
            "sections:\n"
            "  - label: Mazes\n"
            "    pages: 4\n"
            "    generator: maze\n"
            "    cells: {x: 8, y: 8}\n"
            "    solution: separate_page\n"
        )
        with pytest.raises(DefinitionError) as excinfo:
            build(loads(text, source="test"), PdfWriter(tmp_path / "m.pdf"))
        assert "solution" in str(excinfo.value)


class TestTheBookmarkGuardIsReachable:
    """§ 10.2 requires `--skip-unsupported` to leave out links, **bookmarks**
    and the attachment.

    The wrapper had the guard — `if "outline" in self._missing: return` — and it
    could never fire, because `_ALL_CAPABILITIES` never contained `"outline"`
    and `_missing` is that set minus the writer's. The git history shows the set
    being extended for `attachment` and then for `link` as each guard was added;
    `outline` was the one that was not. Harmless only because `PngWriter.outline`
    happens to be a no-op today — a guard that cannot fire is not a guard.
    """

    def test_a_writer_without_the_capability_has_its_bookmarks_dropped(self) -> None:
        from ctrlgrid.pages import _ALL_CAPABILITIES, _LeavingOutWhatItCannotDraw

        assert "outline" in _ALL_CAPABILITIES

        class _NoBookmarks:
            def __init__(self) -> None:
                self.titles: list[str] = []

            def capabilities(self) -> set[str]:
                return _ALL_CAPABILITIES - {"outline"}

            def outline(self, title: str, *, index: int) -> None:
                self.titles.append(title)

        inner = _NoBookmarks()
        _LeavingOutWhatItCannotDraw(inner).outline("January", index=0)
        assert inner.titles == []

    def test_the_pdf_writer_still_declares_it_and_keeps_them(self) -> None:
        from ctrlgrid.pages import _LeavingOutWhatItCannotDraw
        from ctrlgrid.writers.pdf import PdfWriter

        writer = PdfWriter("unused.pdf")
        assert "outline" in writer.capabilities()
        recorded: list[str] = []
        writer.outline = lambda title, *, index: recorded.append(title)
        _LeavingOutWhatItCannotDraw(writer).outline("January", index=0)
        assert recorded == ["January"]
