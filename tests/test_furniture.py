"""Border, background, hole marks and stamp (§ 5.2, § 8.6, § 8.7).

All four belong to the handle, not to a blade (§ 3), and none of them changes
the pattern area: § 8.1 computes that from margins and bands alone, so adding a
border or hole marks never moves a single grid line.

Draw order is what the layers mean, and the writer does not sort (§ 3.6): the
background goes down first, the pattern on top of it, then the frame, then the
stamp over everything.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ctrlgrid.errors import DefinitionError
from ctrlgrid.frame import background_mark, border_mark, hole_marks, stamp_mark
from ctrlgrid.loader import loads
from ctrlgrid.marks import Arc, Layer, Polygon, Text
from ctrlgrid.pages import Geometry, build
from ctrlgrid.writers.pdf import PdfWriter

Q = PdfWriter("unused.pdf")


def document(page: str = "", blocks: str = "", overrides: dict | None = None):
    """A minimal A4 definition, with extra `page:` keys and top-level blocks."""
    text = (
        "version: 1\n"
        "page:\n"
        "  format: a4\n"
        f"{page}"
        f"{blocks}"
        "generator: lines\n"
        "families:\n"
        "  - {direction: horizontal, base_spacing: 10mm}\n"
    )
    return loads(text, overrides, source="test")


def geometry(doc) -> Geometry:
    return Geometry.of(
        doc.sheet,
        header=doc.header,
        footer=doc.footer,
        pattern=doc.pattern,
        blade_axes=doc.axes,
    )


class TestBorder:
    def test_it_sits_on_the_edge_of_the_pattern_area(self) -> None:
        # § 8.1: exactly on the pattern area's edge, not around the margins.
        doc = document(blocks="border:\n  weight: 0.6pt\n")
        area = geometry(doc)
        mark = border_mark(doc.border, area)
        assert isinstance(mark, Polygon)
        xs = sorted({point.x for point in mark.points})
        ys = sorted({point.y for point in mark.points})
        assert xs == [area.origin.x, area.origin.x + area.area.width]
        assert ys == [area.origin.y, area.origin.y + area.area.height]

    def test_a_gap_pushes_it_outwards_away_from_the_pattern(self) -> None:
        # § 5.2: `gap` is air between border and pattern, so the pattern keeps
        # its size and the border moves out.
        doc = document(blocks="border:\n  weight: 0.6pt\n  gap: 2mm\n")
        area = geometry(doc)
        mark = border_mark(doc.border, area)
        xs = sorted({point.x for point in mark.points})
        assert xs[0] == area.origin.x - 2000

    def test_a_border_does_not_shrink_the_pattern_area(self) -> None:
        plain = geometry(document())
        bordered = geometry(document(blocks="border:\n  weight: 0.6pt\n  gap: 2mm\n"))
        assert plain.area == bordered.area

    def test_it_is_a_closed_unfilled_quadrilateral(self) -> None:
        # § 6: Polygon replaces a rectangle primitive — a rectangle is a
        # quadrilateral, and the vocabulary grows by one instead of two.
        doc = document(blocks="border:\n  weight: 0.6pt\n")
        mark = border_mark(doc.border, geometry(doc))
        assert len(mark.points) == 4
        assert mark.closed is True
        assert mark.fill_color is None

    def test_it_belongs_to_the_frame(self) -> None:
        doc = document(blocks="border:\n  weight: 0.6pt\n")
        assert border_mark(doc.border, geometry(doc)).layer is Layer.FRAME

    def test_a_gap_that_runs_off_the_sheet_is_an_error(self) -> None:
        with pytest.raises(DefinitionError) as excinfo:
            doc = document(blocks="border:\n  weight: 0.6pt\n  gap: 20mm\n")
            border_mark(doc.border, geometry(doc))
        message = str(excinfo.value)
        assert "gap" in message and "20mm" in message


class TestBackground:
    def test_it_covers_the_whole_sheet(self) -> None:
        doc = document(page="  background: '#fffef8'\n")
        mark = background_mark(doc.page.background, doc.sheet)
        assert isinstance(mark, Polygon)
        assert sorted({p.x for p in mark.points}) == [0, doc.sheet.width]
        assert sorted({p.y for p in mark.points}) == [0, doc.sheet.height]

    def test_it_is_filled_in_the_colour_given(self) -> None:
        doc = document(page="  background: '#fffef8'\n")
        mark = background_mark(doc.page.background, doc.sheet)
        assert mark.fill_color == "#fffef8"

    def test_none_means_no_mark_at_all(self) -> None:
        assert background_mark(None, document().sheet) is None

    def test_the_default_is_none(self) -> None:
        assert document().page.background is None


class TestHoleMarks:
    """ISO 838 (§ 8.7): two holes, 80 mm apart, 12 mm in, about the centre."""

    def test_two_marks_eighty_millimetres_apart(self) -> None:
        doc = document(page="  hole_marks: true\n")
        marks = hole_marks(doc.page, doc.sheet, is_even=False)
        assert len(marks) == 2
        assert abs(marks[0].center.y - marks[1].center.y) == 80000

    def test_they_are_symmetric_about_the_middle_of_the_sheet(self) -> None:
        doc = document(page="  hole_marks: true\n")
        marks = hole_marks(doc.page, doc.sheet, is_even=False)
        middle = doc.sheet.height // 2
        assert sorted(m.center.y for m in marks) == [middle - 40000, middle + 40000]

    def test_they_sit_twelve_millimetres_from_the_binding_edge(self) -> None:
        doc = document(page="  hole_marks: true\n")
        marks = hole_marks(doc.page, doc.sheet, is_even=False)
        assert {m.center.x for m in marks} == {12000}

    def test_the_hole_is_six_millimetres_across(self) -> None:
        doc = document(page="  hole_marks: true\n")
        marks = hole_marks(doc.page, doc.sheet, is_even=False)
        assert all(isinstance(m, Arc) and m.radius == 3000 for m in marks)

    def test_in_landscape_they_move_to_the_top_edge(self) -> None:
        # § 8.7: that is where landscape sheets get filed.
        doc = document(page="  orientation: landscape\n  hole_marks: true\n")
        marks = hole_marks(doc.page, doc.sheet, is_even=False)
        assert {m.center.y for m in marks} == {doc.sheet.height - 12000}
        assert abs(marks[0].center.x - marks[1].center.x) == 80000

    def test_under_duplex_a_portrait_sheet_swaps_sides(self) -> None:
        doc = document(page="  duplex: true\n  hole_marks: true\n")
        front = hole_marks(doc.page, doc.sheet, is_even=False)
        back = hole_marks(doc.page, doc.sheet, is_even=True)
        assert {m.center.x for m in front} == {12000}
        assert {m.center.x for m in back} == {doc.sheet.width - 12000}

    def test_in_landscape_they_stay_put_under_duplex(self) -> None:
        # § 8.7: the top edge does not mirror when the sheet is turned.
        doc = document(
            page="  orientation: landscape\n  duplex: true\n  hole_marks: true\n"
        )
        front = hole_marks(doc.page, doc.sheet, is_even=False)
        back = hole_marks(doc.page, doc.sheet, is_even=True)
        assert [m.center for m in front] == [m.center for m in back]

    def test_they_are_drawn_over_the_pattern(self) -> None:
        # § 8.7: they lie in the pattern area, and that is the normal case —
        # so they go on the frame layer and are painted on top.
        doc = document(page="  hole_marks: true\n")
        assert all(m.layer is Layer.FRAME for m in hole_marks(doc.page, doc.sheet, is_even=False))

    def test_a_narrow_inner_margin_only_warns(self) -> None:
        # § 8.7: no error — that is simply what an ordinary sheet of paper
        # looks like, and no space is reserved for them.
        doc = document(page="  margin: 5mm\n  hole_marks: true\n")
        assert any("12" in notice for notice in doc.notices)

    def test_a_wide_enough_margin_says_nothing(self) -> None:
        doc = document(page="  margin: 15mm\n  hole_marks: true\n")
        assert doc.notices == ()

    def test_off_by_default(self) -> None:
        assert document().page.hole_marks is False


class TestStamp:
    def test_it_goes_on_the_topmost_layer(self) -> None:
        # § 8.6: over everything, because it is a transient state of the run
        # and not a property of the paper.
        doc = document(blocks='stamp:\n  text: "DRAFT"\n')
        mark = stamp_mark(doc.stamp, doc.sheet, q=Q)
        assert isinstance(mark, Text)
        assert mark.layer is Layer.OVERLAY

    def test_it_sits_in_the_middle_of_the_sheet(self) -> None:
        doc = document(blocks='stamp:\n  text: "DRAFT"\n')
        mark = stamp_mark(doc.stamp, doc.sheet, q=Q)
        assert mark.pos.x == doc.sheet.width // 2
        assert mark.pos.y == doc.sheet.height // 2
        assert mark.align == "center"

    def test_it_runs_diagonally_and_faintly_by_default(self) -> None:
        doc = document(blocks='stamp:\n  text: "DRAFT"\n')
        mark = stamp_mark(doc.stamp, doc.sheet, q=Q)
        assert mark.angle == pytest.approx(45.0)
        assert mark.opacity == pytest.approx(0.08)

    def test_auto_size_fills_most_of_the_sheet(self) -> None:
        doc = document(blocks='stamp:\n  text: "DRAFT"\n')
        mark = stamp_mark(doc.stamp, doc.sheet, q=Q)
        width = Q.text_width(mark.content, family=mark.family, size=mark.size)
        assert 0.5 * doc.sheet.width < width < 1.2 * doc.sheet.width

    def test_a_named_size_is_taken_as_given(self) -> None:
        doc = document(blocks='stamp:\n  text: "DRAFT"\n  size: 40pt\n')
        assert stamp_mark(doc.stamp, doc.sheet, q=Q).size == 14111

    def test_the_command_line_is_the_intended_route(self) -> None:
        # § 8.6: allowed in the definition, but a flag is the way it is meant
        # to be used — "draft" is a state of the run, not of the paper.
        doc = document(overrides={"stamp": "REVIEW"})
        assert doc.stamp is not None
        assert stamp_mark(doc.stamp, doc.sheet, q=Q).content == "REVIEW"

    def test_the_flag_beats_the_definition(self) -> None:
        doc = document(blocks='stamp:\n  text: "DRAFT"\n')
        overridden = document(
            blocks='stamp:\n  text: "DRAFT"\n', overrides={"stamp": "REVIEW"}
        )
        assert stamp_mark(doc.stamp, doc.sheet, q=Q).content == "DRAFT"
        assert stamp_mark(overridden.stamp, overridden.sheet, q=Q).content == "REVIEW"

    def test_no_stamp_by_default(self) -> None:
        assert document().stamp is None


class TestOnTheSheet:
    def test_everything_lands_in_the_finished_pdf(self, tmp_path: Path) -> None:
        import pdfread

        doc = document(
            page="  background: '#fffef8'\n  hole_marks: true\n",
            blocks='border:\n  weight: 0.6pt\nstamp:\n  text: "DRAFT"\n',
        )
        path = tmp_path / "furnished.pdf"
        build(doc, PdfWriter(path))
        assert "DRAFT" in pdfread.text_on(path)
        assert path.exists()

    def test_furniture_does_not_disturb_the_grid(self, tmp_path: Path) -> None:
        import pdfread

        plain = tmp_path / "plain.pdf"
        furnished = tmp_path / "furnished.pdf"
        build(document(), PdfWriter(plain))
        build(
            document(
                page="  background: '#fffef8'\n  hole_marks: true\n",
                blocks='border:\n  weight: 0.6pt\nstamp:\n  text: "DRAFT"\n',
            ),
            PdfWriter(furnished),
        )

        def rows(path: Path) -> list[int]:
            return sorted(
                {round(line.y1) for line in pdfread.lines_um(path) if line.is_horizontal}
            )

        assert rows(plain) == rows(furnished)
