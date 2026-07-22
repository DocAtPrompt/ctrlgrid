"""Page geometry, the page loop and placeholders (§ 8.1, § 8.10).

The pattern area is what remains after margins, header, footer and their gaps.
It is the origin of every pattern coordinate, which is what makes one
definition work on A4, Letter and a pad alike.
"""

from __future__ import annotations

import pytest

from ctrlgrid.errors import DefinitionError
from ctrlgrid.model import Band, Margin
from ctrlgrid.pages import Geometry, PageContext, Sheet, page_contexts, resolve_placeholders
from ctrlgrid.units import parse_length as L

A4 = Sheet(width=210000, height=297000, margin=Margin.uniform(L("5mm")))


class TestThePatternArea:
    def test_without_header_and_footer_it_is_the_page_less_the_margins(self) -> None:
        geometry = Geometry.of(A4, header=None, footer=None)
        assert (geometry.area.width, geometry.area.height) == (200000, 287000)

    def test_its_origin_sits_at_the_inner_and_bottom_margin(self) -> None:
        geometry = Geometry.of(A4, header=None, footer=None)
        assert (geometry.origin.x, geometry.origin.y) == (5000, 5000)

    def test_header_and_footer_and_both_their_gaps_come_off_the_height(self) -> None:
        # 297 - 5 - 5 - 12 - 4 - 8 - 4 = 259 mm
        geometry = Geometry.of(
            A4,
            header=Band(height="12mm", gap="4mm"),
            footer=Band(height="8mm", gap="4mm"),
        )
        assert geometry.area.height == 259000

    def test_the_origin_rises_above_the_footer_and_its_gap(self) -> None:
        geometry = Geometry.of(A4, header=None, footer=Band(height="8mm", gap="4mm"))
        assert geometry.origin.y == 5000 + 8000 + 4000

    def test_the_width_is_unaffected_by_bands(self) -> None:
        # § 8.1: header, footer and pattern area share one content width.
        geometry = Geometry.of(A4, header=Band(height="12mm", gap="4mm"), footer=None)
        assert geometry.area.width == 200000

    def test_a_gap_without_its_band_does_not_exist(self) -> None:
        # § 8.1: the gap belongs to the element and goes with it.
        assert Geometry.of(A4, header=None, footer=None).area.height == 287000

    def test_no_margins_and_no_bands_fill_the_whole_sheet(self) -> None:
        bare = Sheet(width=210000, height=297000, margin=Margin.uniform(L("0mm")))
        geometry = Geometry.of(bare, header=None, footer=None)
        assert (geometry.area.width, geometry.area.height) == (210000, 297000)
        assert (geometry.origin.x, geometry.origin.y) == (0, 0)


class TestTheBandBoxes:
    def test_the_header_sits_directly_below_the_top_margin(self) -> None:
        geometry = Geometry.of(A4, header=Band(height="12mm", gap="4mm"), footer=None)
        assert geometry.header is not None
        assert geometry.header.top == 297000 - 5000
        assert geometry.header.bottom == 297000 - 5000 - 12000

    def test_the_footer_sits_directly_above_the_bottom_margin(self) -> None:
        geometry = Geometry.of(A4, header=None, footer=Band(height="8mm", gap="4mm"))
        assert geometry.footer is not None
        assert (geometry.footer.bottom, geometry.footer.top) == (5000, 13000)

    def test_a_band_box_spans_the_content_width(self) -> None:
        geometry = Geometry.of(A4, header=Band(height="12mm"), footer=None)
        assert geometry.header is not None
        assert (geometry.header.left, geometry.header.right) == (5000, 205000)


class TestWhenNothingIsLeft:
    def test_a_negative_pattern_area_names_every_deduction(self) -> None:
        # § 12 point 9: with six deductions, "pattern area is negative" is
        # useless. The message has to show the arithmetic item by item.
        with pytest.raises(DefinitionError) as excinfo:
            Geometry.of(
                A4,
                header=Band(height="150mm", gap="4mm"),
                footer=Band(height="150mm", gap="4mm"),
            )
        message = str(excinfo.value)
        for item in ("297", "margin.top", "margin.bottom", "header.height", "footer.gap"):
            assert item in message

    def test_margins_wider_than_the_sheet_are_an_error(self) -> None:
        narrow = Sheet(width=210000, height=297000, margin=Margin.uniform(L("120mm")))
        with pytest.raises(DefinitionError):
            Geometry.of(narrow, header=None, footer=None)


class TestThePageLoop:
    def test_pages_are_numbered_from_one_and_indexed_from_zero(self) -> None:
        contexts = list(page_contexts(count=3))
        assert [(c.index, c.number) for c in contexts] == [(0, 1), (1, 2), (2, 3)]

    def test_every_page_knows_the_total(self) -> None:
        assert {c.count for c in page_contexts(count=3)} == {3}

    def test_even_pages_are_marked(self) -> None:
        assert [c.is_even for c in page_contexts(count=4)] == [False, True, False, True]

    def test_the_seed_material_is_stable_across_processes(self) -> None:
        # § 3.3: a stable named hash, never Python's hash(), or the
        # reproducibility promise breaks at the next Python release.
        first = [c.seed_material for c in page_contexts(count=2, seed=4711)]
        second = [c.seed_material for c in page_contexts(count=2, seed=4711)]
        assert first == second
        assert first[0] != first[1]


class TestPlaceholders:
    def page(self, number: int = 7, count: int = 30, name: str | None = None) -> PageContext:
        return PageContext(
            index=number - 1,
            number=number,
            count=count,
            name=name,
            is_even=number % 2 == 0,
            seed_material=b"",
        )

    def test_the_page_number_and_the_total(self) -> None:
        assert resolve_placeholders("{page} / {page_count}", self.page()) == "7 / 30"

    def test_text_without_placeholders_is_untouched(self) -> None:
        assert resolve_placeholders("Class 3B", self.page()) == "Class 3B"

    def test_the_name_comes_from_the_list(self) -> None:
        assert resolve_placeholders("{name}", self.page(name="Anna Berger")) == "Anna Berger"

    def test_a_name_without_a_list_is_an_error(self) -> None:
        # § 8.10: not an empty string — that would silently produce a sheet
        # with a blank header where one was expected.
        with pytest.raises(DefinitionError) as excinfo:
            resolve_placeholders("{name}", self.page(name=None), field="header.right")
        assert "header.right" in str(excinfo.value)

    def test_an_unknown_placeholder_is_an_error_listing_the_known_ones(self) -> None:
        with pytest.raises(DefinitionError) as excinfo:
            resolve_placeholders("{pages}", self.page())
        message = str(excinfo.value)
        assert "{pages}" in message and "{page_count}" in message

    def test_the_date_is_the_run_date(self) -> None:
        import datetime

        today = datetime.date.today().isoformat()
        assert resolve_placeholders("{date}", self.page()) == today
