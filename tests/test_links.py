"""Internal PDF links — the navigation capability behind the calendar (§ 10.2).

A link is a PDF annotation (a GoTo over a rectangle), not a drawing primitive —
so it lives outside the six primitives (§ 6), exactly like the bookmark
`outline()` already does. The writer gains two methods: `define_dest(key)` marks
a page as a named destination, `link(a, b, target)` lays a link rectangle over
`a`→`b` pointing at that destination. It is a capability (`"link"`) the PDF
writer has and the PNG writer does not, so a run that needs links is refused on
PNG by name — the same mechanism as text (§ 10.4).
"""

from __future__ import annotations

from pathlib import Path

from pypdf import PdfReader

from ctrlgrid.marks import Point
from ctrlgrid.writers import DocumentMeta
from ctrlgrid.writers.pdf import PdfWriter
from ctrlgrid.writers.png import PngWriter

A4 = (210_000, 297_000)


def write_linked(path: Path) -> Path:
    """Two pages that link to each other."""
    writer = PdfWriter(path)
    writer.begin_document(DocumentMeta(title="links"))

    writer.begin_page(*A4)
    writer.define_dest("one")
    writer.link(Point(10_000, 200_000), Point(60_000, 210_000), "two")
    writer.end_page()

    writer.begin_page(*A4)
    writer.define_dest("two")
    writer.link(Point(10_000, 280_000), Point(50_000, 290_000), "one")
    writer.end_page()

    writer.end_document()
    return path


def _annotations(page) -> list:
    annots = page.get("/Annots")
    return [a.get_object() for a in annots] if annots else []


def _dest_page_index(reader: PdfReader, annot) -> int | None:
    target = annot["/Dest"][0]  # an indirect reference to the destination page
    for i, page in enumerate(reader.pages):
        if page.indirect_reference.idnum == target.idnum:
            return i
    return None


class TestTheCapability:
    def test_the_pdf_writer_can_link(self) -> None:
        assert "link" in PdfWriter("unused.pdf").capabilities()

    def test_the_png_writer_cannot_link(self) -> None:
        # PNG has no annotations; a calendar to PNG is refused for want of it.
        assert "link" not in PngWriter("unused.png").capabilities()


class TestLinksResolve:
    def test_each_page_carries_one_link(self, tmp_path: Path) -> None:
        reader = PdfReader(str(write_linked(tmp_path / "l.pdf")))
        for page in reader.pages:
            links = [a for a in _annotations(page) if a.get("/Subtype") == "/Link"]
            assert len(links) == 1

    def test_a_link_lands_on_its_destination(self, tmp_path: Path) -> None:
        # Page 0 links to dest "two", defined on page 1; page 1 links back.
        reader = PdfReader(str(write_linked(tmp_path / "l.pdf")))
        link0 = _annotations(reader.pages[0])[0]
        link1 = _annotations(reader.pages[1])[0]
        assert _dest_page_index(reader, link0) == 1
        assert _dest_page_index(reader, link1) == 0

    def test_the_link_rectangle_is_where_it_was_put(self, tmp_path: Path) -> None:
        # 10 mm .. 60 mm in x, 200 mm .. 210 mm in y, in points (1 mm = 72/25.4 pt).
        reader = PdfReader(str(write_linked(tmp_path / "l.pdf")))
        rect = [float(v) for v in _annotations(reader.pages[0])[0]["/Rect"]]
        mm = 72 / 25.4
        assert rect[0] == round(10 * mm, 1) or abs(rect[0] - 10 * mm) < 0.5
        assert abs(rect[2] - 60 * mm) < 0.5
        assert abs(rect[3] - 210 * mm) < 0.5


class TestReproducibility:
    def test_two_runs_produce_identical_bytes(self, tmp_path: Path) -> None:
        # § 10.1: links must not break byte-identical output.
        first = write_linked(tmp_path / "a.pdf").read_bytes()
        second = write_linked(tmp_path / "b.pdf").read_bytes()
        assert first == second
