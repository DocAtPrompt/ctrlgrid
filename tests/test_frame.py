"""Header and footer layout (§ 8.4, § 8.9) — measured, never estimated.

Acceptance criterion 5 of § 14: the pre-flight query API is really used. These
tests use the actual PDF writer as the query side, because a stub would prove
nothing about the metrics the output is built from.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from ctrlgrid.errors import DefinitionError
from ctrlgrid.frame import layout_band
from ctrlgrid.marks import Layer, Polygon, Text
from ctrlgrid.model import Band
from ctrlgrid.pages import Box, PageContext
from ctrlgrid.writers.pdf import PdfWriter

Q = PdfWriter("unused.pdf")
BAND = Box(left=5000, bottom=280000, right=205000, top=292000)
PAGE = PageContext(index=0, number=7, count=30, name="Anna Berger", is_even=False,
                   seed_material=b"")
SHEET_W = 210_000


def place(band: Band, box: Box = BAND) -> dict[str, Text]:
    marks = layout_band(band, box, q=Q, page=PAGE, section="header", sheet_width=SHEET_W)
    return {mark.align: mark for mark in marks}


class TestPlacement:
    def test_the_left_field_starts_at_the_left_edge(self) -> None:
        assert place(Band(height="12mm", left="Anna"))["left"].pos.x == BAND.left

    def test_the_right_field_ends_at_the_right_edge(self) -> None:
        assert place(Band(height="12mm", right="7 / 30"))["right"].pos.x == BAND.right

    def test_the_centre_field_sits_in_the_middle_of_the_content_width(self) -> None:
        assert place(Band(height="12mm", center="Class 3B"))["center"].pos.x == 105000

    def test_text_is_placed_within_the_band(self) -> None:
        mark = place(Band(height="12mm", center="Class 3B"))["center"]
        assert BAND.bottom < mark.pos.y < BAND.top

    def test_header_and_footer_marks_belong_to_the_frame(self) -> None:
        assert place(Band(height="12mm", center="x"))["center"].layer is Layer.FRAME

    def test_empty_fields_produce_no_marks(self) -> None:
        assert layout_band(
            Band(height="12mm"), BAND, q=Q, page=PAGE, section="header", sheet_width=SHEET_W
        ) == []

    def test_placeholders_are_resolved(self) -> None:
        assert place(Band(height="12mm", center="{page} / {page_count}"))["center"].content == (
            "7 / 30"
        )


class TestOverflow:
    """§ 8.9 — a truncated name is silent data loss, so the default is an error."""

    def test_a_field_that_does_not_fit_names_field_text_and_the_missing_space(self) -> None:
        narrow = Box(left=0, bottom=0, right=20000, top=12000)
        with pytest.raises(DefinitionError) as excinfo:
            layout_band(
                Band(height="12mm", left="Maximilian Sonnenschein-Hofstätter"),
                narrow,
                q=Q,
                page=PAGE,
                section="header",
                sheet_width=SHEET_W,
            )
        message = str(excinfo.value)
        assert "header.left" in message
        assert "Maximilian Sonnenschein-Hofstätter" in message
        assert "mm" in message

    def test_cut_truncates_and_marks_it(self) -> None:
        # The ellipsis is mandatory: without it a cut string looks complete.
        narrow = Box(left=0, bottom=0, right=20000, top=12000)
        marks = layout_band(
            Band(height="12mm", cut=True, left="Maximilian Sonnenschein-Hofstätter"),
            narrow,
            q=Q,
            page=PAGE,
            section="header",
            sheet_width=SHEET_W,
        )
        content = marks[0].content
        assert content.endswith("…")
        assert content.startswith("Max")
        assert Q.text_width(content, family="sans", size=marks[0].size) <= 20000

    def test_the_centre_field_bounds_its_neighbours(self) -> None:
        # § 8.9 rules 2 and 3: left runs up to the centre block, not to the
        # middle of the page.
        wide_centre = Band(height="12mm", center="A very wide centre field indeed", left="Anna")
        marks = place(wide_centre)
        assert marks["left"].pos.x == BAND.left

    def test_without_a_centre_field_left_and_right_split_at_the_middle(self) -> None:
        # § 8.9 rule 5 — the commonest case of all: name left, page right.
        narrow = Box(left=0, bottom=0, right=40000, top=12000)
        with pytest.raises(DefinitionError) as excinfo:
            layout_band(
                Band(height="12mm", left="A rather long name here", right="7 / 30"),
                narrow,
                q=Q,
                page=PAGE,
                section="footer",
                sheet_width=SHEET_W,
            )
        assert "footer.left" in str(excinfo.value)


class TestBandHeight:
    def test_a_band_too_short_for_its_font_is_an_error(self) -> None:
        # § 8.4: the height stays the one from the definition, but it has to be
        # enough — otherwise the text runs into the pattern area unnoticed.
        flat = Box(left=0, bottom=0, right=200000, top=1000)
        with pytest.raises(DefinitionError) as excinfo:
            layout_band(
                Band(height="1mm", center="Class 3B", font={"size": "9pt"}),
                flat,
                q=Q,
                page=PAGE,
                section="header",
                sheet_width=SHEET_W,
            )
        message = str(excinfo.value)
        assert "header.height" in message and "9pt" in message


class TestGlyphCoverage:
    def test_a_glyph_outside_latin_1_names_the_way_out(self) -> None:
        # § 10.3: the answer to a Polish name is a font file, and the message
        # has to say so rather than just naming the character.
        with pytest.raises(DefinitionError) as excinfo:
            layout_band(
                Band(height="12mm", center="Michał"),
                BAND,
                q=Q,
                page=PAGE,
                section="header",
                sheet_width=SHEET_W,
            )
        message = str(excinfo.value)
        assert "ł" in message
        assert "font" in message.lower()


class TestBandColourModel:
    def test_colour_fields_default_to_none(self) -> None:
        band = Band(height="12mm", center="x")
        assert band.background is None and band.text_color is None

    def test_colour_fields_accept_a_colour(self) -> None:
        band = Band(height="12mm", center="x", background="#2f3a48", text_color="#ffffff")
        assert band.background == "#2f3a48" and band.text_color == "#ffffff"

    def test_an_invalid_colour_is_refused(self) -> None:
        with pytest.raises(ValidationError):  # via ColorField
            Band(height="12mm", center="x", background="not-a-colour")


class TestBandColourDrawing:
    def test_text_colour_is_applied_to_every_field(self) -> None:
        band = Band(height="12mm", left="A", center="B", right="C", text_color="#ffffff")
        marks = layout_band(band, BAND, q=Q, page=PAGE, section="header", sheet_width=SHEET_W)
        texts = [m for m in marks if isinstance(m, Text)]
        assert texts and all(m.color == "#ffffff" for m in texts)

    def test_text_colour_defaults_to_black(self) -> None:
        band = Band(height="12mm", center="B")
        marks = layout_band(band, BAND, q=Q, page=PAGE, section="header", sheet_width=SHEET_W)
        assert [m for m in marks if isinstance(m, Text)][0].color == "#000000"

    def test_background_is_a_full_width_strip_drawn_first(self) -> None:
        band = Band(height="12mm", center="B", background="#2f3a48")
        marks = layout_band(band, BAND, q=Q, page=PAGE, section="header", sheet_width=SHEET_W)
        assert isinstance(marks[0], Polygon)                      # first, so text paints over it
        fill = marks[0]
        xs = {p.x for p in fill.points}
        ys = {p.y for p in fill.points}
        assert xs == {0, SHEET_W}                                 # full sheet width
        assert ys == {BAND.bottom, BAND.top}                      # band height only
        assert fill.fill_color == "#2f3a48" and fill.layer is Layer.FRAME

    def test_background_without_text_draws_only_the_strip(self) -> None:
        band = Band(height="12mm", background="#2f3a48")
        marks = layout_band(band, BAND, q=Q, page=PAGE, section="header", sheet_width=SHEET_W)
        assert len(marks) == 1 and isinstance(marks[0], Polygon)

    def test_no_colour_no_text_is_still_empty(self) -> None:
        band = Band(height="12mm")
        assert layout_band(band, BAND, q=Q, page=PAGE, section="header", sheet_width=SHEET_W) == []
