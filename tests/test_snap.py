"""Snapping — shrinking the pattern area so the period comes out whole (§ 8.3).

Not a violation of § 8.2: the grid is never stretched to fit. The *area* gets
smaller and the surplus becomes free space between margin and pattern, while
the period stays exactly what the definition asked for.

`none` is the default because snapping changes the geometry § 8.1 computed:
someone who writes a 10 mm margin and a header height would otherwise silently
get a smaller pattern area than that arithmetic gives.
"""

from __future__ import annotations

import pytest

from ctrlgrid.errors import DefinitionError
from ctrlgrid.loader import loads
from ctrlgrid.model import Margin
from ctrlgrid.pages import Geometry, Sheet
from ctrlgrid.units import parse_length as L

# 50 mm of height against a 5 mm base spacing whose cycle [1, 1, 2] spans
# 20 mm: two whole cycles fit, and 10 mm is left over. That gap between
# "whole spacings" and "whole cycles" is what the two modes differ on.
SHEET = Sheet(width=100000, height=50000, margin=Margin.uniform(L("0mm")))

CYCLED = "  - {direction: horizontal, base_spacing: 5mm, spacing: [1, 1, 2]}"


def geometry(pattern: str, families: str = CYCLED) -> Geometry:
    document = loads(
        f"version: 1\n{pattern}\ngenerator: lines\nfamilies:\n{families}\n", source="test"
    )
    return Geometry.of(
        SHEET,
        header=None,
        footer=None,
        pattern=document.pattern,
        blade_axes=document.axes,
    )


class TestTheDefault:
    def test_nothing_snaps_unless_asked(self) -> None:
        # § 8.3: `none` keeps the pattern area exactly as § 8.1 computed it.
        assert geometry("").area.height == 50000

    def test_none_can_be_written_out(self) -> None:
        assert geometry("pattern:\n  snap: none").area.height == 50000


class TestSnapToSpacing:
    def test_the_area_becomes_a_whole_number_of_base_steps(self) -> None:
        result = geometry(
            "pattern:\n  snap: spacing\n  remainder: end",
            families="  - {direction: horizontal, base_spacing: 7mm}",
        )
        assert result.area.height == 49000  # 7 x 7 mm, 1 mm surplus

    def test_an_exact_fit_is_left_alone(self) -> None:
        result = geometry(
            "pattern:\n  snap: spacing\n  remainder: end",
            families="  - {direction: horizontal, base_spacing: 25mm}",
        )
        assert result.area.height == 50000


class TestSnapToCycle:
    def test_the_area_becomes_a_whole_number_of_cycles(self) -> None:
        # § 8.3: usually the visually right one. Snapping to the base spacing
        # leaves the grid neat but the emphasised lines lopsided — and those
        # are exactly the ones the eye picks out.
        result = geometry("pattern:\n  snap: cycle\n  remainder: end")
        assert result.area.height == 40000  # two 20 mm cycles

    def test_it_differs_from_snapping_to_the_spacing(self) -> None:
        to_spacing = geometry("pattern:\n  snap: spacing\n  remainder: end").area.height
        to_cycle = geometry("pattern:\n  snap: cycle\n  remainder: end").area.height
        assert to_spacing == 50000
        assert to_cycle == 40000


class TestSnapAndRemainderTogether:
    def test_snapping_relocates_the_surplus_rather_than_removing_it(self) -> None:
        # § 8.3: a cut period at the end becomes contiguous free space, and
        # `remainder` still decides where that space lands.
        centred = geometry("pattern:\n  snap: cycle\n  remainder: center")
        assert centred.area.height == 40000
        assert centred.origin.y == 5000  # 10 mm surplus, split

    def test_at_the_end_the_surplus_collects_in_one_place(self) -> None:
        ended = geometry("pattern:\n  snap: cycle\n  remainder: end")
        assert ended.area.height == 40000
        assert ended.origin.y == 0

    def test_whole_cycles_beside_snap_cycle_is_pointed_out_once(self) -> None:
        # § 8.3: it is ineffective there, since only whole cycles arise anyway.
        # Said once, so nobody keeps adjusting a setting with no effect.
        result = geometry("pattern:\n  snap: cycle\n  remainder: whole_cycles")
        assert any("whole_cycles" in notice for notice in result.notices)

    def test_that_notice_is_not_an_error(self) -> None:
        result = geometry("pattern:\n  snap: cycle\n  remainder: whole_cycles")
        assert result.area.height == 40000


class TestPerAxis:
    def test_the_axes_snap_separately(self) -> None:
        result = geometry(
            "pattern:\n  snap: {y: cycle}\n  remainder: end",
            families=(
                f"{CYCLED}\n"
                "  - {direction: vertical, base_spacing: 5mm, spacing: [1, 1, 2]}"
            ),
        )
        assert result.area.height == 40000  # snapped
        assert result.area.width == 100000  # untouched

    def test_naming_an_axis_with_no_periodic_family_is_an_error(self) -> None:
        # § 8.3: not silent ineffectiveness. Whoever writes it expects an effect.
        with pytest.raises(DefinitionError) as excinfo:
            geometry("pattern:\n  snap: {x: cycle}")
        assert "x" in str(excinfo.value)


class TestSnapToPixel:
    def test_it_needs_a_device_profile(self) -> None:
        # § 8.3.1: on paper formats it is an error for good — `assumed_dpi` is
        # a yardstick for warnings (§ 9.1), and geometry must never rest on a
        # guessed number. M5 (test_snap_pixel.py) makes it work on a device.
        with pytest.raises(DefinitionError) as excinfo:
            geometry("pattern:\n  snap: pixel")
        message = str(excinfo.value)
        assert "device" in message.lower()
        assert "M5" not in message


class TestWhenItCannotBeDone:
    def test_an_area_smaller_than_one_cycle_is_an_error_with_the_numbers(self) -> None:
        tiny = Sheet(width=100000, height=15000, margin=Margin.uniform(L("0mm")))
        document = loads(
            f"version: 1\npattern:\n  snap: cycle\ngenerator: lines\nfamilies:\n{CYCLED}\n",
            source="test",
        )
        with pytest.raises(DefinitionError) as excinfo:
            Geometry.of(
                tiny,
                header=None,
                footer=None,
                pattern=document.pattern,
                blade_axes=document.axes,
            )
        message = str(excinfo.value)
        assert "20" in message and "15" in message

    def test_disagreeing_families_still_need_a_governing_mark(self) -> None:
        with pytest.raises(DefinitionError) as excinfo:
            geometry(
                "pattern:\n  snap: cycle",
                families=(
                    "  - {direction: horizontal, base_spacing: 5mm}\n"
                    "  - {direction: horizontal, base_spacing: 8mm}"
                ),
            )
        assert "governing" in str(excinfo.value)
