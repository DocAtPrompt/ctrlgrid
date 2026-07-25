"""The edge ruler (§ 8.12): the section, the ladder, the marks, the refusals.

A working scale, not a second calibration figure: zero sits at the origin of
the *pattern area*, so the numbers agree with the grid rather than with the
paper's corner. It is drawn into the margin and reserves nothing, so switching
it on leaves the pattern exactly where it was — the rule § 8.1 already states
for `border`.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from ctrlgrid.errors import CtrlGridError, DefinitionError
from ctrlgrid.frame import check_rulers, ruler_marks
from ctrlgrid.loader import loads
from ctrlgrid.marks import Layer, Point, Segment, Text
from ctrlgrid.model import RulerSpec
from ctrlgrid.pages import Geometry
from ctrlgrid.ruler import (
    LABEL_GAP,
    LONG_TICK,
    Tick,
    label_text,
    number_height,
    strip_width,
    ticks,
)
from ctrlgrid.writers.pdf import PdfWriter

#: A metrics oracle: font metrics are fixed data, not rendering (§ 10.2), and
#: this is how the rest of the suite asks for them.
Q = PdfWriter("unused.pdf")


class TestTheSection:
    def test_the_metric_default_is_the_one_five_ten_ladder(self) -> None:
        ruler = RulerSpec(edges=["bottom"])
        assert ruler.unit == "mm"
        assert (ruler.step.um, ruler.mid_every.um, ruler.label_every.um) == (
            1000, 5000, 10_000,
        )

    def test_centimetres_share_the_ladder_and_change_only_the_numbers(self) -> None:
        ruler = RulerSpec(edges=["bottom"], unit="cm")
        assert (ruler.step.um, ruler.mid_every.um, ruler.label_every.um) == (
            1000, 5000, 10_000,
        )

    def test_inches_get_an_eighth_half_one_ladder(self) -> None:
        ruler = RulerSpec(edges=["bottom"], unit="in")
        assert (ruler.step.um, ruler.mid_every.um, ruler.label_every.um) == (
            3175, 12_700, 25_400,
        )

    def test_an_unknown_edge_is_refused_by_name(self) -> None:
        with pytest.raises(ValidationError) as excinfo:
            RulerSpec(edges=["middle"])
        assert "middle" in str(excinfo.value)

    def test_an_edge_twice_is_refused(self) -> None:
        with pytest.raises(ValidationError) as excinfo:
            RulerSpec(edges=["bottom", "bottom"])
        assert "bottom" in str(excinfo.value)

    def test_no_edge_at_all_is_refused(self) -> None:
        with pytest.raises(ValidationError):
            RulerSpec(edges=[])

    def test_a_label_interval_off_the_ladder_is_refused_naming_both(self) -> None:
        # § 5.1: a numbered tick that sits on no tick of the ladder is the
        # silent almost-right, so it is refused rather than drawn.
        with pytest.raises(ValidationError) as excinfo:
            RulerSpec(edges=["bottom"], step="3mm", mid_every="none", label_every="10mm")
        message = str(excinfo.value)
        assert "3mm" in message and "10mm" in message

    def test_a_medium_tick_off_the_ladder_is_refused(self) -> None:
        with pytest.raises(ValidationError):
            RulerSpec(edges=["bottom"], step="2mm", mid_every="5mm", label_every="10mm")

    def test_a_custom_step_that_the_default_ladder_cannot_take_says_so(self) -> None:
        # The default 5/10 mm rungs cannot sit on a 3 mm ladder. Told, not
        # silently dropped: the message names both values and the way out.
        with pytest.raises(ValidationError) as excinfo:
            RulerSpec(edges=["bottom"], step="3mm")
        message = str(excinfo.value)
        assert "3mm" in message and "10mm" in message and "none" in message

    def test_the_medium_tick_can_be_left_out(self) -> None:
        ruler = RulerSpec(edges=["bottom"], mid_every="none")
        assert ruler.mid_every is None

    def test_a_step_of_zero_is_refused(self) -> None:
        with pytest.raises(ValidationError):
            RulerSpec(edges=["bottom"], step="0mm")

    def test_an_unknown_key_is_refused(self) -> None:
        with pytest.raises(ValidationError):
            RulerSpec(edges=["bottom"], ticks="every 2mm")


class TestTheLadder:
    def test_ticks_start_at_zero_and_stay_inside_the_area(self) -> None:
        ruler = RulerSpec(edges=["bottom"])
        got = ticks(ruler, extent=25_000)
        assert got[0] == Tick(at=0, kind="label")
        assert [tick.at for tick in got] == [i * 1000 for i in range(26)]
        assert [t.at for t in got if t.kind == "label"] == [0, 10_000, 20_000]
        assert [t.at for t in got if t.kind == "mid"] == [5000, 15_000, 25_000]

    def test_a_tick_past_the_end_is_not_drawn(self) -> None:
        # The scale measures the area it borders; it does not run into the
        # corner (§ 8.12).
        ruler = RulerSpec(edges=["bottom"])
        assert max(tick.at for tick in ticks(ruler, extent=25_500)) == 25_000

    def test_positions_are_exact_multiples_not_accumulated(self) -> None:
        # § 3.3: tick 200 is exactly 200 steps, whatever the step.
        ruler = RulerSpec(edges=["bottom"], unit="in")
        assert ticks(ruler, extent=200 * 3175)[200].at == 200 * 3175

    def test_the_medium_tick_can_be_absent(self) -> None:
        ruler = RulerSpec(edges=["bottom"], mid_every="none")
        assert {tick.kind for tick in ticks(ruler, extent=25_000)} == {"short", "label"}

    def test_millimetre_numbers_count_millimetres(self) -> None:
        assert label_text(RulerSpec(edges=["bottom"]), at=30_000) == "30"

    def test_centimetre_numbers_count_centimetres(self) -> None:
        assert label_text(RulerSpec(edges=["bottom"], unit="cm"), at=30_000) == "3"

    def test_inch_numbers_count_inches(self) -> None:
        assert label_text(RulerSpec(edges=["bottom"], unit="in"), at=2 * 25_400) == "2"

    def test_zero_reads_zero(self) -> None:
        assert label_text(RulerSpec(edges=["bottom"]), at=0) == "0"

    def test_a_number_states_its_position_exactly(self) -> None:
        # § 8.12: never rounded — a scale that prints a wrong measure is worse
        # than no scale at all.
        ruler = RulerSpec(edges=["bottom"], unit="cm", mid_every="none", label_every="25mm")
        assert [label_text(ruler, at=at) for at in (25_000, 50_000)] == ["2.5", "5"]

    def test_the_strip_is_tick_plus_gap_plus_the_measured_number(self) -> None:
        # Measured, not guessed: the writer knows how tall a digit is (§ 10.2).
        ruler = RulerSpec(edges=["bottom"])
        ascent, _ = Q.text_metrics(family=ruler.font.family, size=ruler.font.size.um)
        assert strip_width(ruler, q=Q) == LONG_TICK + LABEL_GAP + ascent
        assert number_height(ruler, q=Q) == ascent


def document(page: str = "", blocks: str = ""):
    """A minimal A4 definition, in the shape the rest of the suite uses."""
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
    return loads(text, None, source="test")


def geometry(doc) -> Geometry:
    return Geometry.of(
        doc.sheet,
        header=doc.header,
        footer=doc.footer,
        pattern=doc.pattern,
        blade_axes=doc.axes,
    )


class TestTheMarks:
    def test_the_bottom_ruler_zeroes_on_the_pattern_origin(self) -> None:
        doc = document(page="  margin: 20mm\n")
        area = geometry(doc)
        marks = ruler_marks(RulerSpec(edges=["bottom"]), area, q=Q)
        first = next(m for m in marks if isinstance(m, Segment))
        assert first.start == Point(area.origin.x, area.origin.y)
        assert first.end.y == area.origin.y - LONG_TICK  # outward, into the margin

    def test_the_left_ruler_zeroes_on_the_same_corner(self) -> None:
        doc = document(page="  margin: 20mm\n")
        area = geometry(doc)
        marks = ruler_marks(RulerSpec(edges=["left"]), area, q=Q)
        first = next(m for m in marks if isinstance(m, Segment))
        assert first.start == Point(area.origin.x, area.origin.y)
        assert first.end.x == area.origin.x - LONG_TICK

    def test_the_far_edges_grow_away_from_the_pattern_too(self) -> None:
        doc = document(page="  margin: 20mm\n")
        area = geometry(doc)
        top = ruler_marks(RulerSpec(edges=["top"]), area, q=Q)
        right = ruler_marks(RulerSpec(edges=["right"]), area, q=Q)
        first_top = next(m for m in top if isinstance(m, Segment))
        first_right = next(m for m in right if isinstance(m, Segment))
        assert first_top.start.y == area.origin.y + area.area.height
        assert first_top.end.y == first_top.start.y + LONG_TICK
        assert first_right.start.x == area.origin.x + area.area.width
        assert first_right.end.x == first_right.start.x + LONG_TICK

    def test_every_mark_is_frame_layer(self) -> None:
        doc = document(page="  margin: 20mm\n")
        marks = ruler_marks(RulerSpec(edges=["bottom", "left"]), geometry(doc), q=Q)
        assert {mark.layer for mark in marks} == {Layer.FRAME}

    def test_the_numbers_stand_upright_below_and_turn_on_the_side(self) -> None:
        # § 8.12: rotated on the vertical edges, so the strip is the same width
        # on all four.
        doc = document(page="  margin: 20mm\n")
        marks = ruler_marks(RulerSpec(edges=["bottom", "left"]), geometry(doc), q=Q)
        angles = {mark.angle for mark in marks if isinstance(mark, Text)}
        assert angles == {0.0, 90.0}

    def test_nothing_is_drawn_into_the_pattern_area(self) -> None:
        doc = document(page="  margin: 20mm\n")
        area = geometry(doc)
        marks = ruler_marks(RulerSpec(edges=["bottom"]), area, q=Q)
        assert all(
            mark.start.y <= area.origin.y and mark.end.y <= area.origin.y
            for mark in marks
            if isinstance(mark, Segment)
        )
        assert all(mark.pos.y < area.origin.y for mark in marks if isinstance(mark, Text))

    def test_the_numbers_stay_inside_the_sheet(self) -> None:
        # A number hangs below its tick: with a 20 mm margin it has room, and
        # the check of the next class is what refuses when it has not.
        doc = document(page="  margin: 20mm\n")
        marks = ruler_marks(RulerSpec(edges=["bottom"]), geometry(doc), q=Q)
        assert all(mark.pos.y > 0 for mark in marks if isinstance(mark, Text))

    def test_it_draws_nothing_when_there_is_no_ruler(self) -> None:
        assert ruler_marks(None, geometry(document()), q=Q) == []


class TestTheRefusals:
    def test_a_margin_too_narrow_names_the_edge_and_both_measures(self) -> None:
        # § 8.2: nothing is shrunk to make a ruler fit. The message has to let
        # the user act, which means the millimetres (§ 12).
        doc = document(page="  margin: 4mm\n")
        with pytest.raises(DefinitionError) as excinfo:
            check_rulers(RulerSpec(edges=["left"]), geometry(doc), doc, q=Q)
        message = str(excinfo.value)
        assert "left" in message and "4.0mm" in message

    def test_the_leftover_of_a_shrunken_area_counts_as_room(self) -> None:
        # The scale is measured against the area the pattern actually got, not
        # against the margin: `remainder` may have left it more room (§ 8.5).
        # 4 mm of margin plus half the 9 mm leftover is enough at the bottom,
        # while the same 4 mm on the left — where nothing was left over — is
        # not, and that is the assertion above.
        doc = document(page="  margin: 4mm\n")
        check_rulers(RulerSpec(edges=["bottom"]), geometry(doc), doc, q=Q)

    def test_a_band_in_the_way_is_named_as_the_cause(self) -> None:
        doc = document(
            page="  margin: 20mm\n",
            blocks="header:\n  height: 8mm\n  gap: 2mm\n  center: hi\n",
        )
        with pytest.raises(DefinitionError) as excinfo:
            check_rulers(RulerSpec(edges=["top"]), geometry(doc), doc, q=Q)
        assert "header" in str(excinfo.value)

    def test_the_other_edges_are_unaffected_by_that_band(self) -> None:
        doc = document(
            page="  margin: 20mm\n",
            blocks="header:\n  height: 8mm\n  gap: 2mm\n  center: hi\n",
        )
        check_rulers(RulerSpec(edges=["bottom", "left", "right"]), geometry(doc), doc, q=Q)

    def test_numbers_that_would_collide_are_refused_with_the_measured_width(self) -> None:
        doc = document(page="  margin: 20mm\n")
        ruler = RulerSpec(
            edges=["bottom"], mid_every="none", label_every="2mm",
            font={"size": "12pt"},
        )
        with pytest.raises(DefinitionError) as excinfo:
            check_rulers(ruler, geometry(doc), doc, q=Q)
        assert "2mm" in str(excinfo.value)

    def test_a_ruler_that_fits_raises_nothing(self) -> None:
        doc = document(page="  margin: 20mm\n")
        check_rulers(
            RulerSpec(edges=["bottom", "left", "top", "right"]), geometry(doc), doc, q=Q
        )

    def test_no_ruler_raises_nothing(self) -> None:
        check_rulers(None, geometry(document()), document(), q=Q)


def render(tmp_path, definition: str, name: str = "out.pdf", **overrides):
    """Build a definition into a real file, the way the CLI does."""
    from ctrlgrid.cli import _writer_for
    from ctrlgrid.pages import build

    doc = loads(definition, overrides or None, source="test")
    path = tmp_path / name
    build(doc, _writer_for(path, doc))
    return path


RULED = (
    "version: 1\n"
    "page:\n  format: a4\n  margin: 20mm\n"
    "generator: lines\n"
    "families:\n  - {direction: horizontal, base_spacing: 10mm}\n"
)


class TestTheRun:
    def test_a_ruler_does_not_move_the_pattern(self, tmp_path) -> None:
        # § 8.1's rule, restated for the ruler: switching it on moves no
        # pattern mark at all.
        def pattern_marks(text: str):
            from ctrlgrid import generators
            from ctrlgrid.pages import _page_marks, preflight, sheet_plan

            doc = loads(text, None, source="test")
            geo, contexts, bands, _cover = preflight(doc, Q)
            marks = _page_marks(
                doc, geo, generators.get(doc.generator), sheet_plan(doc),
                contexts[0], bands[0], Q,
            )
            return [mark for mark in marks if mark.layer == Layer.PATTERN]

        assert pattern_marks(RULED) == pattern_marks(
            RULED + "ruler:\n  edges: [bottom, left]\n"
        )

    def test_the_same_definition_gives_the_same_bytes(self, tmp_path) -> None:
        text = RULED + "ruler:\n  edges: [bottom]\n"
        first = render(tmp_path, text, name="a.pdf")
        second = render(tmp_path, text, name="b.pdf")
        assert first.read_bytes() == second.read_bytes()

    def test_a_ruler_that_does_not_fit_is_refused_by_the_run(self, tmp_path) -> None:
        text = (
            "version: 1\npage:\n  format: a4\n  margin: 3mm\n"
            "generator: lines\nfamilies:\n  - {direction: vertical, base_spacing: 10mm}\n"
            "ruler:\n  edges: [bottom]\n"
        )
        with pytest.raises(DefinitionError) as excinfo:
            render(tmp_path, text)
        assert "bottom" in str(excinfo.value)

    def test_png_output_is_refused_naming_text(self, tmp_path) -> None:
        # The numbers are Text marks, and the PNG writer has no font file
        # (§ 10.2, § 10.4) — the capability pre-flight catches it by itself.
        text = (
            "version: 1\npage:\n  device: remarkable-paper-pro\n  margin: 10mm\n"
            "generator: dots\ngrid:\n  x: {base_spacing: 5mm}\n  y: {base_spacing: 5mm}\n"
            "base_size: 0.5mm\n"
            "ruler:\n  edges: [bottom]\n"
        )
        with pytest.raises((DefinitionError, CtrlGridError)) as excinfo:
            render(tmp_path, text, name="out.png")
        assert "text" in str(excinfo.value).lower()

    def test_an_unknown_ruler_key_is_refused_by_the_loader(self) -> None:
        with pytest.raises(DefinitionError):
            loads(RULED + "ruler:\n  edges: [bottom]\n  every: 2mm\n", None, source="test")
