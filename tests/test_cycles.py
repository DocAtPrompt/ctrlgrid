"""Cycles — the load-bearing idea of the tool (§ 5.3).

One mechanism, seven applications: a repeating list of dimensionless multiples
applied position by position, against an absolute base. "every Nth line
heavier" is the special case; several independent cycles of different lengths
are the general one.

The other half of this module is § 8.2: **positions are never computed by
accumulation.** A position is derived from its index — whole cycles plus a
partial sum — and rounded to micrometres exactly once. Repeated addition drifts
over 300 lines, and drift is the one thing this tool cannot afford.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from ctrlgrid.cycles import Cycle
from ctrlgrid.errors import DefinitionError


def cycle(*values: str) -> Cycle:
    return Cycle.of([Decimal(v) for v in values])


class TestCycleLookup:
    def test_entries_repeat(self) -> None:
        weights = cycle("1", "1", "1", "1", "2.7")
        assert [weights.at(i) for i in range(7)] == [
            Decimal("1"),
            Decimal("1"),
            Decimal("1"),
            Decimal("1"),
            Decimal("2.7"),
            Decimal("1"),
            Decimal("1"),
        ]

    def test_a_single_entry_applies_to_everything(self) -> None:
        assert cycle("1").at(999) == Decimal("1")

    def test_an_empty_cycle_is_an_error(self) -> None:
        with pytest.raises(DefinitionError):
            Cycle.of([])


class TestPositions:
    def test_a_uniform_cycle_lays_out_a_millimetre_grid(self) -> None:
        positions = list(Cycle.of([Decimal(1)]).positions(base_um=1000, extent_um=10000))
        assert positions == [(i, i * 1000) for i in range(11)]

    def test_an_uneven_cycle_repeats_its_pattern(self) -> None:
        # base 2 mm, multiples 1, 1, 2 -> gaps of 2, 2, 4 mm
        positions = [p for _, p in Cycle.of(
            [Decimal(1), Decimal(1), Decimal(2)]
        ).positions(base_um=2000, extent_um=20000)]
        assert positions == [0, 2000, 4000, 8000, 10000, 12000, 16000, 18000, 20000]

    def test_the_last_position_may_touch_the_far_edge(self) -> None:
        positions = [p for _, p in Cycle.of([Decimal(1)]).positions(base_um=1000, extent_um=3000)]
        assert positions[-1] == 3000

    def test_nothing_is_emitted_beyond_the_extent(self) -> None:
        positions = [p for _, p in Cycle.of([Decimal(1)]).positions(base_um=1000, extent_um=2500)]
        assert positions == [0, 1000, 2000]

    def test_an_offset_shifts_the_start_of_the_cycle(self) -> None:
        positions = [
            p
            for _, p in Cycle.of([Decimal(1)]).positions(
                base_um=1000, extent_um=3000, offset_um=500
            )
        ]
        assert positions == [500, 1500, 2500]

    def test_a_negative_offset_still_starts_inside_the_area(self) -> None:
        # Shifting the cycle backwards must not emit marks outside the pattern
        # area; the first line inside it is the first one drawn.
        positions = [
            p
            for _, p in Cycle.of([Decimal(1)]).positions(
                base_um=1000, extent_um=3000, offset_um=-2500
            )
        ]
        assert positions == [500, 1500, 2500]


class TestNoDrift:
    def test_the_three_hundredth_line_is_exactly_where_it_belongs(self) -> None:
        # 0.1 mm steps: adding 0.1 three hundred times in floating point misses
        # by ~4e-14 mm; deriving from the index cannot miss at all (§ 8.2).
        positions = dict(Cycle.of([Decimal("0.1")]).positions(base_um=1000, extent_um=30000))
        assert positions[300] == 30000

    def test_fractional_multiples_land_on_whole_micrometres(self) -> None:
        positions = [
            p
            for _, p in Cycle.of([Decimal("0.5"), Decimal("1.5")]).positions(
                base_um=1000, extent_um=4000
            )
        ]
        assert positions == [0, 500, 2000, 2500, 4000]


class TestRefusals:
    def test_a_cycle_that_never_advances_is_an_error(self) -> None:
        # Without this the position loop never terminates.
        with pytest.raises(DefinitionError) as excinfo:
            Cycle.of([Decimal(0)]).positions(base_um=1000, extent_um=10000)
        assert "0" in str(excinfo.value)

    def test_a_negative_multiple_is_an_error(self) -> None:
        with pytest.raises(DefinitionError):
            Cycle.of([Decimal(1), Decimal(-1)])

    def test_a_zero_base_is_an_error(self) -> None:
        with pytest.raises(DefinitionError):
            Cycle.of([Decimal(1)]).positions(base_um=0, extent_um=10000)

    def test_the_refusals_speak_the_user_s_units_and_not_micrometres(self) -> None:
        # § 3.3 and § 12: values are named in the unit the user wrote. "-5000 µm"
        # to someone who typed `-5mm` is the message § 12 calls unusable, and
        # `Length` carries `.raw` for exactly this.
        with pytest.raises(DefinitionError) as excinfo:
            Cycle.of([Decimal(1)]).positions(base_um=-5000, extent_um=10000, base_raw="-5mm")
        message = str(excinfo.value)
        assert "-5mm" in message and "µm" not in message

    def test_a_refusal_quotes_the_cycle_as_it_was_written(self) -> None:
        # `[Decimal('0'), Decimal('0')]` is Python's repr, not the user's `[0, 0]`.
        with pytest.raises(DefinitionError) as excinfo:
            Cycle.of([Decimal(0), Decimal(0)]).positions(base_um=1000, extent_um=10000)
        message = str(excinfo.value)
        assert "[0, 0]" in message and "Decimal" not in message

    def test_the_both_ways_walk_refuses_the_same_two_things(self) -> None:
        # `positions_between` is the slanted family's path (§ 7.1), and it walks
        # outwards from line 0 until a position falls past the bound. A cycle
        # that never advances means that never happens — the loop runs forever
        # and `ctrlgrid check`, of all commands, hangs. The upward-only
        # `positions` has guarded this since M1; both entry points need it, or
        # the one without it is the one a user finds.
        never_advances = Cycle.of([Decimal(0)])
        with pytest.raises(DefinitionError):
            list(never_advances.positions_between(base_um=1000, lower_um=-5000, upper_um=5000))
        no_base = Cycle.of([Decimal(1)])
        with pytest.raises(DefinitionError):
            list(no_base.positions_between(base_um=0, lower_um=-5000, upper_um=5000))


class TestEffectivePeriod:
    def test_the_period_in_marks_is_the_lcm_of_the_cycle_lengths(self) -> None:
        # § 5.3: cycles of different applications may differ in length and run
        # independently.
        from ctrlgrid.cycles import period_in_marks

        assert period_in_marks([3, 5]) == 15
        assert period_in_marks([1, 5]) == 5
        assert period_in_marks([]) == 1

    def test_the_period_in_millimetres_follows_the_specified_formula(self) -> None:
        # sum(spacing) x base_spacing x (mark period / len(spacing))
        from ctrlgrid.cycles import period_um

        spacing = Cycle.of([Decimal(1), Decimal(1), Decimal(2)])
        # 5 marks per period would be the lcm with a 5-long weight cycle:
        # sum = 4, base = 2 mm, 15 marks / 3 entries = 5 repeats -> 40 mm
        assert period_um(spacing, base_um=2000, marks=15) == 40000


class TestPositionsBothWays:
    """§ 7.1: a slanted family's line 0 goes through the origin, so the cycle
    has to be read *downwards* from it as well as upwards."""

    def test_from_zero_it_is_the_ordinary_walk(self) -> None:
        cycle = Cycle.of([Decimal(2), Decimal(1)])
        upward = list(cycle.positions(base_um=1000, extent_um=10_000))
        both = list(cycle.positions_between(base_um=1000, lower_um=0, upper_um=10_000))
        assert both == upward

    def test_below_zero_the_index_runs_negative(self) -> None:
        cycle = Cycle.of([Decimal(1)])
        got = list(cycle.positions_between(base_um=1000, lower_um=-3000, upper_um=2000))
        assert got == [(-3, -3000), (-2, -2000), (-1, -1000), (0, 0), (1, 1000), (2, 2000)]

    def test_the_cycle_is_read_backwards_not_negated(self) -> None:
        # [2, 1] downwards from zero steps 1 first and then 2 — the cycle read
        # in reverse. Negating the upward positions would give -2000, -3000 and
        # silently mirror the pattern.
        cycle = Cycle.of([Decimal(2), Decimal(1)])
        got = list(cycle.positions_between(base_um=1000, lower_um=-4000, upper_um=3000))
        assert [position for _index, position in got] == [-4000, -3000, -1000, 0, 2000, 3000]

    def test_the_index_keeps_the_other_cycles_in_step(self) -> None:
        # weight.at(index) and color[index % len] must go on meaning the same
        # thing below zero, so the index continues rather than restarting.
        cycle = Cycle.of([Decimal(2), Decimal(1)])
        got = dict(
            (index, position)
            for index, position in cycle.positions_between(
                base_um=1000, lower_um=-4000, upper_um=3000
            )
        )
        assert got[-1] == -1000 and got[-2] == -3000 and got[0] == 0

    def test_an_offset_moves_line_zero_and_nothing_else(self) -> None:
        cycle = Cycle.of([Decimal(1)])
        got = list(
            cycle.positions_between(base_um=1000, lower_um=-2000, upper_um=2000, offset_um=500)
        )
        assert [position for _index, position in got] == [-1500, -500, 500, 1500]
