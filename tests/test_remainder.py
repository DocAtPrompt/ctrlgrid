"""What is left over after the periods are laid out (§ 8.5).

Handle-side by construction. § 8.3 says it is the *pattern area* that shrinks,
so the handle asks the blade one question — given this much room, how much do
you actually use — then shrinks the area and shifts the origin. The blade goes
on filling an `Area` from zero and learns nothing about page geometry (§ 3.3).

There is deliberately no "stretch until it fits" (§ 8.2). The leftover is
moved, never absorbed.
"""

from __future__ import annotations

import pytest

from ctrlgrid.errors import DefinitionError
from ctrlgrid.loader import loads
from ctrlgrid.marks import Area
from ctrlgrid.model import Margin
from ctrlgrid.pages import Geometry, Sheet
from ctrlgrid.units import parse_length as L

# 100 x 50 mm of usable area, so a 30 mm grid leaves an awkward 20 mm over.
SHEET = Sheet(width=100000, height=50000, margin=Margin.uniform(L("0mm")))


def geometry(definition: str) -> Geometry:
    document = loads(definition, source="test")
    return Geometry.of(
        SHEET,
        header=None,
        footer=None,
        pattern=document.pattern,
        blade_axes=document.axes,
    )


def define(*, remainder: str = "", families: str = "") -> str:
    return f"""
version: 1
{remainder}
generator: lines
families:
{families or '  - {direction: horizontal, base_spacing: 30mm}'}
"""


class TestEnd:
    def test_the_leftover_collects_at_the_far_end(self) -> None:
        # 50 mm of height, 30 mm spacing: marks at 0 and 30, 20 mm left over.
        result = geometry(define(remainder="pattern:\n  remainder: end"))
        assert result.origin.y == 0
        assert result.area.height == 50000

    def test_end_leaves_the_area_exactly_as_section_8_1_computed_it(self) -> None:
        result = geometry(define(remainder="pattern:\n  remainder: end"))
        assert result.area == Area(width=100000, height=50000)


class TestCentre:
    def test_the_leftover_is_split_between_both_sides(self) -> None:
        result = geometry(define(remainder="pattern:\n  remainder: center"))
        assert result.origin.y == 10000
        assert result.area.height == 30000

    def test_an_exact_fit_is_not_moved(self) -> None:
        # 50 mm at 25 mm spacing uses all of it; nothing to centre.
        result = geometry(
            define(
                remainder="pattern:\n  remainder: center",
                families="  - {direction: horizontal, base_spacing: 25mm}",
            )
        )
        assert result.origin.y == 0
        assert result.area.height == 50000

    def test_an_odd_leftover_is_split_deterministically(self) -> None:
        # 50 mm at 30 mm leaves 20 mm; at 27 mm it leaves 23 mm, which cannot
        # be halved evenly in micrometres. It must still be the same every run.
        first = geometry(
            define(
                remainder="pattern:\n  remainder: center",
                families="  - {direction: horizontal, base_spacing: 27mm}",
            )
        )
        second = geometry(
            define(
                remainder="pattern:\n  remainder: center",
                families="  - {direction: horizontal, base_spacing: 27mm}",
            )
        )
        assert first.origin.y == second.origin.y


class TestWholeCycles:
    def test_a_cut_cycle_at_the_end_is_dropped(self) -> None:
        # Cycle [1, 1, 2] at 5 mm is a 20 mm period. 50 mm holds two whole
        # periods; the remaining 10 mm would be half a cycle and goes.
        result = geometry(
            define(
                remainder="pattern:\n  remainder: whole_cycles",
                families="  - {direction: horizontal, base_spacing: 5mm, spacing: [1, 1, 2]}",
            )
        )
        assert result.area.height == 40000

    def test_it_is_for_calligraphy_where_half_a_cycle_is_useless(self) -> None:
        # x-height, ascender, descender, line air — a cut cycle at the foot of
        # the sheet cannot be written in (§ 8.5).
        result = geometry(
            define(
                remainder="pattern:\n  remainder: whole_cycles",
                families="  - {direction: horizontal, base_spacing: 2mm, spacing: [2, 1, 1, 3]}",
            )
        )
        assert result.area.height % 14000 == 0


class TestPerAxis:
    def test_the_axes_are_set_separately(self) -> None:
        # § 8.5: a single value for both would be wrong for calligraphy, where
        # the y axis is cyclic and the x axis is not.
        result = geometry(
            define(
                remainder="pattern:\n  remainder: {x: end, y: center}",
                families=(
                    "  - {direction: horizontal, base_spacing: 30mm}\n"
                    "  - {direction: vertical, base_spacing: 30mm}"
                ),
            )
        )
        assert result.origin.y == 10000  # 50 mm area, 30 mm used
        assert result.origin.x == 0  # 100 mm area, 90 mm used, leftover at end

    def test_a_scalar_is_shorthand_for_both_axes(self) -> None:
        result = geometry(
            define(
                remainder="pattern:\n  remainder: center",
                families=(
                    "  - {direction: horizontal, base_spacing: 30mm}\n"
                    "  - {direction: vertical, base_spacing: 30mm}"
                ),
            )
        )
        assert (result.origin.x, result.origin.y) == (5000, 10000)

    def test_naming_an_axis_with_no_family_is_an_error(self) -> None:
        # § 8.3's principle: whoever writes it down expects an effect.
        with pytest.raises(DefinitionError) as excinfo:
            geometry(
                define(
                    remainder="pattern:\n  remainder: {x: center}",
                    families="  - {direction: horizontal, base_spacing: 30mm}",
                )
            )
        message = str(excinfo.value)
        assert "x" in message

    def test_a_scalar_tolerates_an_axis_with_no_family(self) -> None:
        # The shorthand means "both, where there is anything to place".
        result = geometry(define(remainder="pattern:\n  remainder: center"))
        assert result.origin.x == 0


class TestSeveralFamiliesOnOneAxis:
    def test_families_that_agree_need_no_governing_mark(self) -> None:
        result = geometry(
            define(
                remainder="pattern:\n  remainder: center",
                families=(
                    "  - {direction: horizontal, base_spacing: 30mm}\n"
                    "  - {direction: horizontal, base_spacing: 30mm, offset: 0mm}"
                ),
            )
        )
        assert result.origin.y == 10000

    def test_families_that_disagree_need_one_and_say_so(self) -> None:
        # § 8.3: an error naming the families, not a guess.
        with pytest.raises(DefinitionError) as excinfo:
            geometry(
                define(
                    remainder="pattern:\n  remainder: center",
                    families=(
                        "  - {direction: horizontal, base_spacing: 30mm}\n"
                        "  - {direction: horizontal, base_spacing: 7mm}"
                    ),
                )
            )
        message = str(excinfo.value)
        assert "governing" in message
        assert "30mm" in message and "7mm" in message

    def test_the_governing_family_decides(self) -> None:
        result = geometry(
            define(
                remainder="pattern:\n  remainder: center",
                families=(
                    "  - {direction: horizontal, base_spacing: 30mm, governing: true}\n"
                    "  - {direction: horizontal, base_spacing: 7mm}"
                ),
            )
        )
        assert result.origin.y == 10000

    def test_two_governing_families_on_one_axis_are_an_error(self) -> None:
        with pytest.raises(DefinitionError):
            geometry(
                define(
                    remainder="pattern:\n  remainder: center",
                    families=(
                        "  - {direction: horizontal, base_spacing: 30mm, governing: true}\n"
                        "  - {direction: horizontal, base_spacing: 7mm, governing: true}"
                    ),
                )
            )


class TestTheDefault:
    def test_the_leftover_is_centred_unless_told_otherwise(self) -> None:
        assert geometry(define()).origin.y == 10000

    def test_millimetre_paper_is_unaffected_either_way(self) -> None:
        # A 1 mm grid divides both A4 dimensions exactly, so the M1 reference
        # case looks the same under every remainder mode.
        from ctrlgrid.loader import load_preset

        document = load_preset("millimeter-a4")
        result = Geometry.of(
            document.sheet,
            header=None,
            footer=None,
            pattern=document.pattern,
            blade_axes=document.axes,
        )
        assert (result.origin.x, result.origin.y) == (5000, 5000)
        assert (result.area.width, result.area.height) == (200000, 287000)
