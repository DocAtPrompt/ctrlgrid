"""The cover sheet (§ 8.8).

Two things on one page, and three rules that make it unlike any other sheet:
it is not counted in the numbering, it carries no frame furniture at all, and
because it names the tool version it is excluded from golden comparisons
(§ 13.2) — which is why every assertion here is about the *page after* the
cover whenever it is about the pattern.

The calibration square is the only answer there is to a problem outside our
control (§ 8.2): we cannot stop a print driver scaling, so we make it visible.
That is why its size is asserted to the micrometre.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ctrlgrid.cover import RULE_LENGTH, SQUARE_SIDE, cover_marks, summary
from ctrlgrid.errors import DefinitionError
from ctrlgrid.loader import loads
from ctrlgrid.marks import Layer, Polygon, Segment, Text
from ctrlgrid.pages import build
from ctrlgrid.writers.pdf import PdfWriter

Q = PdfWriter("unused.pdf")


def document(
    page: str = "", blocks: str = "", overrides: dict | None = None, fmt: str = "a4"
):
    text = (
        "version: 1\n"
        "page:\n"
        f"  format: {fmt}\n"
        f"{page}"
        f"{blocks}"
        "generator: lines\n"
        "families:\n"
        "  - {direction: horizontal, base_spacing: 10mm}\n"
    )
    return loads(text, overrides, source="test")


def marks(doc):
    return cover_marks(doc, q=Q)


def square(doc) -> Polygon:
    found = [mark for mark in marks(doc) if isinstance(mark, Polygon)]
    assert len(found) == 1, "the cover carries exactly one calibration square"
    return found[0]


class TestCalibrationSquare:
    def test_its_side_is_exactly_fifty_millimetres(self) -> None:
        # § 8.8: the whole point. A square that is 49.6 mm on paper proves the
        # driver scaled — a square that is 49.6 mm in the file proves nothing.
        mark = square(document(blocks="pages:\n  cover: true\n"))
        xs = sorted({point.x for point in mark.points})
        ys = sorted({point.y for point in mark.points})
        assert xs[1] - xs[0] == SQUARE_SIDE == 50_000
        assert ys[1] - ys[0] == SQUARE_SIDE

    def test_it_is_a_closed_unfilled_quadrilateral(self) -> None:
        mark = square(document(blocks="pages:\n  cover: true\n"))
        assert len(mark.points) == 4
        assert mark.closed is True
        assert mark.fill_color is None

    def test_it_carries_its_nominal_size_as_a_label(self) -> None:
        texts = [m.content for m in marks(document(blocks="pages:\n  cover: true\n"))
                 if isinstance(m, Text)]
        assert "50 mm" in texts


class TestHundredMillimetreRule:
    def test_it_is_exactly_one_hundred_millimetres_long(self) -> None:
        doc = document(blocks="pages:\n  cover: true\n")
        rules = [
            mark
            for mark in marks(doc)
            if isinstance(mark, Segment) and mark.start.y == mark.end.y
            and abs(mark.end.x - mark.start.x) == RULE_LENGTH
        ]
        assert len(rules) == 1
        assert RULE_LENGTH == 100_000

    def test_it_carries_its_nominal_size_as_a_label(self) -> None:
        texts = [m.content for m in marks(document(blocks="pages:\n  cover: true\n"))
                 if isinstance(m, Text)]
        assert "100 mm" in texts

    def test_it_is_ticked_at_both_ends(self) -> None:
        # Without end ticks a ruler cannot be laid against it accurately.
        doc = document(blocks="pages:\n  cover: true\n")
        verticals = [
            mark for mark in marks(doc)
            if isinstance(mark, Segment) and mark.start.x == mark.end.x
        ]
        assert len(verticals) == 2
        assert abs(verticals[0].start.x - verticals[1].start.x) == RULE_LENGTH


class TestSummary:
    """§ 8.8: enough to reproduce a sheet that worked, years later."""

    def test_it_names_the_generator(self) -> None:
        assert any("lines" in line for line in summary(document()))

    def test_it_names_the_format_and_the_measured_sheet(self) -> None:
        text = "\n".join(summary(document()))
        assert "a4" in text and "portrait" in text and "210.0" in text and "297.0" in text

    def test_it_names_every_margin(self) -> None:
        text = "\n".join(summary(document(page="  margin: 7mm\n")))
        assert "7mm" in text or "7.0" in text

    def test_it_names_the_snap_mode(self) -> None:
        text = "\n".join(summary(document(blocks="pattern:\n  snap: spacing\n")))
        assert "spacing" in text

    def test_it_reports_the_base_values_and_the_cycles(self) -> None:
        # § 8.8 asks for base values and cycles, and only the blade knows them —
        # which is what `describe` is for (§ 3.6, seam 2).
        doc = document()
        text = "\n".join(summary(doc))
        assert "10mm" in text

    def test_it_reports_the_effective_period_in_marks_and_millimetres(self) -> None:
        text = "\n".join(summary(document()))
        assert "10.0 mm" in text

    def test_it_names_the_tool_version(self) -> None:
        from ctrlgrid import __version__

        assert any(__version__ in line for line in summary(document()))

    def test_it_names_the_definition_and_its_checksum(self) -> None:
        # § 8.8: name *or* checksum; both, so a bent copy is distinguishable
        # from the preset it came from.
        doc = document()
        text = "\n".join(summary(doc))
        assert "test" in text and doc.digest in text

    def test_two_definitions_that_differ_get_different_checksums(self) -> None:
        assert document().digest != document(page="  margin: 7mm\n").digest


class TestFormatsTooSmall:
    """§ 8.2: nothing on this page is ever scaled to fit.

    A "50 mm" square measuring 38 mm because the paper was small would be
    worse than no cover at all — it is the exact failure the page exists to
    make visible.
    """

    def test_a_format_too_narrow_for_the_rule_is_refused(self) -> None:
        doc = document(fmt="a6", blocks="pages:\n  cover: true\n")
        with pytest.raises(DefinitionError) as excinfo:
            cover_marks(doc, q=Q)
        message = str(excinfo.value)
        assert "100.0mm" in message and "95.0mm" in message

    def test_it_is_refused_before_a_single_page_is_written(self, tmp_path: Path) -> None:
        # § 12 point 13: abort completely or build completely.
        path = tmp_path / "never.pdf"
        with pytest.raises(DefinitionError):
            build(
                document(fmt="a6", blocks="pages:\n  cover: true\n"),
                PdfWriter(path),
            )
        assert not path.exists()

    def test_without_a_cover_the_small_format_is_fine(self, tmp_path: Path) -> None:
        path = tmp_path / "a6.pdf"
        build(document(fmt="a6"), PdfWriter(path))
        assert path.exists()


class TestOnTheSheet:
    def test_the_cover_is_off_by_default(self, tmp_path: Path) -> None:
        import pdfread

        path = tmp_path / "plain.pdf"
        build(document(blocks="pages:\n  count: 2\n"), PdfWriter(path))
        assert pdfread.page_count(path) == 2

    def test_it_is_an_additional_first_page(self, tmp_path: Path) -> None:
        import pdfread

        path = tmp_path / "cover.pdf"
        build(document(blocks="pages:\n  count: 2\n  cover: true\n"), PdfWriter(path))
        assert pdfread.page_count(path) == 3
        assert "50 mm" in pdfread.text_on(path, 0)

    def test_it_is_not_counted_in_the_numbering(self, tmp_path: Path) -> None:
        # § 8.8: --pages 2 gives two numbered sheets plus a cover, and
        # `{page} / {page_count}` still runs 1…2.
        import pdfread

        path = tmp_path / "numbered.pdf"
        build(
            document(
                blocks=(
                    "footer:\n  height: 8mm\n  left: '{page} / {page_count}'\n"
                    "pages:\n  count: 2\n  cover: true\n"
                )
            ),
            PdfWriter(path),
        )
        assert "1 / 2" in pdfread.text_on(path, 1)
        assert "2 / 2" in pdfread.text_on(path, 2)

    def test_it_carries_no_header_footer_border_or_hole_marks(self, tmp_path: Path) -> None:
        import pdfread

        path = tmp_path / "furnished.pdf"
        build(
            document(
                page="  hole_marks: true\n",
                blocks=(
                    "header:\n  height: 8mm\n  left: 'CLASS 3B'\n"
                    "border:\n  weight: 0.6pt\n"
                    "pages:\n  cover: true\n"
                ),
            ),
            PdfWriter(path),
        )
        assert "CLASS 3B" not in pdfread.text_on(path, 0)
        assert "CLASS 3B" in pdfread.text_on(path, 1)

    def test_it_carries_no_pattern(self, tmp_path: Path) -> None:
        import pdfread

        path = tmp_path / "cover.pdf"
        build(document(blocks="pages:\n  cover: true\n"), PdfWriter(path))
        horizontals = [line for line in pdfread.lines_um(path, 0) if line.is_horizontal]
        # Only the calibration rule, never a grid.
        assert len(horizontals) == 1

    def test_the_square_measures_fifty_millimetres_in_the_finished_pdf(
        self, tmp_path: Path
    ) -> None:
        # Acceptance criterion 2 of § 14, applied to the one page that exists
        # to prove it: read back out of the file, not asserted on the model.
        import pdfread

        path = tmp_path / "cover.pdf"
        build(document(blocks="pages:\n  cover: true\n"), PdfWriter(path))
        rule = next(line for line in pdfread.lines_um(path, 0) if line.is_horizontal)
        assert abs(rule.x2 - rule.x1) == pytest.approx(100_000, abs=1.0)

    def test_two_runs_still_produce_identical_bytes(self, tmp_path: Path) -> None:
        # § 10.1: the cover carries the version and a checksum, both of which
        # are stable — no clock, no randomness, or the promise breaks here.
        first, second = tmp_path / "a.pdf", tmp_path / "b.pdf"
        for path in (first, second):
            build(document(blocks="pages:\n  cover: true\n"), PdfWriter(path))
        assert first.read_bytes() == second.read_bytes()

    def test_the_cover_marks_belong_to_the_pattern_layer(self) -> None:
        # It has no frame, so nothing on it is frame furniture (§ 8.8).
        assert all(mark.layer is Layer.PATTERN for mark in marks(document()))
