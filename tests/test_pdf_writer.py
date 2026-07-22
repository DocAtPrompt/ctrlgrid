"""The PDF writer — seam 3, and the only module that may see reportlab (§ 3.3).

Two of its duties cannot be retrofitted (§ 14): identical input must give
identical bytes (§ 10.1), and the query API must really answer, because § 12
measures every page before the first one is written.
"""

from __future__ import annotations

from pathlib import Path

import pdfread
import pytest

from ctrlgrid.marks import Dot, Layer, Point, Segment, Text
from ctrlgrid.writers import DocumentMeta
from ctrlgrid.writers.pdf import PdfWriter

A4 = (210000, 297000)


def write(path: Path, marks: list = (), pages: int = 1) -> Path:
    writer = PdfWriter(path)
    writer.begin_document(DocumentMeta(title="test"))
    for _ in range(pages):
        writer.begin_page(*A4)
        for mark in marks:
            writer.draw(mark)
        writer.end_page()
    writer.end_document()
    return path


class TestTheSheetIsExact:
    def test_the_media_box_is_the_page_size_to_the_micrometre(self, tmp_path: Path) -> None:
        # § 8.2: exact MediaBox in absolute units, never "scale to fit".
        width, height = pdfread.media_box_um(write(tmp_path / "a4.pdf"))
        assert width == pytest.approx(210000, abs=1)
        assert height == pytest.approx(297000, abs=1)

    def test_every_page_asked_for_is_written(self, tmp_path: Path) -> None:
        assert pdfread.page_count(write(tmp_path / "three.pdf", pages=3)) == 3


class TestReproducibility:
    def test_two_runs_produce_identical_bytes(self, tmp_path: Path) -> None:
        # Acceptance criterion 3 (§ 14). reportlab writes the creation time and
        # a random document ID by default, which would break this and every
        # golden comparison in CI (§ 10.1).
        marks = [Segment(start=Point(0, 0), end=Point(210000, 0), weight=0.1)]
        first = write(tmp_path / "one.pdf", marks).read_bytes()
        second = write(tmp_path / "two.pdf", marks).read_bytes()
        assert first == second

    def test_the_producer_line_does_not_carry_a_timestamp(self, tmp_path: Path) -> None:
        from pypdf import PdfReader

        info = PdfReader(str(write(tmp_path / "meta.pdf"))).metadata
        assert info is not None
        assert "ctrlgrid" in str(info.get("/Producer", ""))


class TestDrawing:
    def test_a_segment_arrives_where_it_was_put(self, tmp_path: Path) -> None:
        segment = Segment(start=Point(5000, 10000), end=Point(205000, 10000), weight=0.05)
        (line,) = pdfread.lines_um(write(tmp_path / "seg.pdf", [segment]))
        assert (line.x1, line.y1, line.x2, line.y2) == pytest.approx(
            (5000, 10000, 205000, 10000), abs=1
        )

    def test_a_stroke_keeps_its_width(self, tmp_path: Path) -> None:
        segment = Segment(start=Point(0, 0), end=Point(1000, 0), weight=0.0529166)
        (line,) = pdfread.lines_um(write(tmp_path / "w.pdf", [segment]))
        assert line.width_mm == pytest.approx(0.0529166, abs=1e-5)

    def test_a_dot_is_a_zero_length_round_capped_stroke(self, tmp_path: Path) -> None:
        # § 10.1: a filled circle costs four Bézier curves each; 2500 dots per
        # page over 30 pages is the difference between a small file and a
        # double-digit megabyte one.
        path = write(tmp_path / "dot.pdf", [Dot(pos=Point(1000, 2000), diameter=0.3)])
        stream = _content(path)
        assert b"1 J" in stream, "round line cap not set"
        assert b"c\n" not in stream, "dot drawn as Bézier curves"

    def test_text_is_written(self, tmp_path: Path) -> None:
        path = write(
            tmp_path / "text.pdf",
            [Text(pos=Point(10000, 10000), content="Class 3B", size=3175, layer=Layer.FRAME)],
        )
        assert "Class 3B" in pdfread.text_on(path)


class TestTheQueryApi:
    """§ 10.2 — the pre-flight questions, and § 14 point 5: really used."""

    def test_a_wider_string_measures_wider(self, tmp_path: Path) -> None:
        writer = PdfWriter(tmp_path / "q.pdf")
        assert writer.text_width("mmmm", family="sans", size=3175) > writer.text_width(
            "i", family="sans", size=3175
        )

    def test_the_empty_string_has_no_width(self, tmp_path: Path) -> None:
        assert PdfWriter(tmp_path / "q.pdf").text_width("", family="sans", size=3175) == 0

    def test_width_scales_with_size(self, tmp_path: Path) -> None:
        writer = PdfWriter(tmp_path / "q.pdf")
        single = writer.text_width("Anna", family="sans", size=3175)
        double = writer.text_width("Anna", family="sans", size=6350)
        # Widths come back as whole micrometres, so doubling may land one off.
        assert double == pytest.approx(single * 2, abs=1)

    def test_metrics_give_an_ascent_and_a_descent(self, tmp_path: Path) -> None:
        # § 8.4 checks a band's height against both.
        ascent, descent = PdfWriter(tmp_path / "q.pdf").text_metrics(family="sans", size=3175)
        assert ascent > 0 and descent > 0
        assert ascent + descent < 3175 * 1.6

    def test_latin_1_is_covered(self, tmp_path: Path) -> None:
        writer = PdfWriter(tmp_path / "q.pdf")
        assert writer.missing_glyphs("Müller-Lüdenscheidt éàñç…", family="sans") == []

    def test_glyphs_outside_latin_1_are_reported(self, tmp_path: Path) -> None:
        # § 10.3: the likeliest first stumbling block of the whole tool.
        writer = PdfWriter(tmp_path / "q.pdf")
        assert writer.missing_glyphs("Michał Erdős", family="sans") == ["ł", "ő"]

    def test_the_writer_says_what_it_can_do(self, tmp_path: Path) -> None:
        capabilities = PdfWriter(tmp_path / "q.pdf").capabilities()
        assert {"vector", "text", "color"} <= capabilities


def _content(path: Path) -> bytes:
    from pypdf import PdfReader

    return PdfReader(str(path)).pages[0].get_contents().get_data()
