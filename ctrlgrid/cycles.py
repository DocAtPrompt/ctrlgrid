"""Cycle evaluation — the load-bearing idea (§ 5.3), and the no-drift rule (§ 8.2).

A cycle is a list of dimensionless multiples applied position by position
against an absolute base. The single most implemented feature of every
comparable tool — "every Nth line heavier" — is the two-entry case of this;
several independent cycles of different lengths for spacing, weight, size, dash
and colour are the general one.

Multiples are kept as `Decimal`, not `float`. A definition may write `2.7`, and
`0.1` three hundred times over is not 30 in binary floating point. Since a
position is one multiplication away from its index, `Decimal` costs nothing
here and buys exactness.

**Positions are derived, never accumulated.** For index k with an n-entry
cycle:

    position(k) = offset + base x (k // n x sum(cycle) + prefix_sum(k mod n))

Whole cycles times the cycle sum, plus the partial sum within the current
cycle, rounded to micrometres exactly once. Repeated float addition drifts over
300 lines, destabilises golden comparisons and would undermine the one promise
the tool makes (§ 8.2).
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from ctrlgrid.errors import DefinitionError


@dataclass(frozen=True, slots=True)
class Cycle:
    """A repeating list of dimensionless multiples."""

    values: tuple[Decimal, ...]
    #: prefix_sums[j] is the sum of the first j entries; prefix_sums[n] is the
    #: sum of the whole cycle. Precomputed so a position costs one lookup.
    prefix_sums: tuple[Decimal, ...]

    @classmethod
    def of(cls, values: Iterable[Decimal], *, field: str | None = None) -> Cycle:
        entries = tuple(values)
        if not entries:
            raise DefinitionError("a cycle needs at least one entry (§ 5.3)", field=field)
        for entry in entries:
            if entry < 0:
                raise DefinitionError(
                    f"cycle entries are multiples of the base and cannot be negative, got {entry}",
                    field=field,
                )
        prefix: list[Decimal] = [Decimal(0)]
        for entry in entries:
            prefix.append(prefix[-1] + entry)
        return cls(values=entries, prefix_sums=tuple(prefix))

    def __len__(self) -> int:
        return len(self.values)

    @property
    def total(self) -> Decimal:
        """The sum of one full cycle."""
        return self.prefix_sums[-1]

    def at(self, index: int) -> Decimal:
        """The multiple that applies to mark `index`."""
        return self.values[index % len(self.values)]

    def positions(
        self,
        *,
        base_um: int,
        extent_um: int,
        offset_um: int = 0,
        field: str | None = None,
    ) -> Iterator[tuple[int, int]]:
        """Yield `(index, position)` for every mark inside `[0, extent_um]`.

        The index keeps counting through positions that fall outside the area,
        so a negative offset shifts the pattern without renumbering it — the
        weight and colour cycles must stay in step with the spacing cycle.
        """
        if base_um <= 0:
            raise DefinitionError(
                f"the base value must be greater than zero, got {base_um} µm", field=field
            )
        if self.total <= 0:
            raise DefinitionError(
                f"the spacing cycle {list(self.values)} sums to zero, so the pattern would "
                "never advance — at least one entry must be greater than zero (§ 5.3)",
                field=field,
            )
        return self._walk(base_um=base_um, extent_um=extent_um, offset_um=offset_um)

    def _walk(self, *, base_um: int, extent_um: int, offset_um: int) -> Iterator[tuple[int, int]]:
        n = len(self.values)
        base = Decimal(base_um)
        index = 0
        while True:
            exact = Decimal(offset_um) + base * (
                Decimal(index // n) * self.total + self.prefix_sums[index % n]
            )
            position = _round(exact)
            if position > extent_um:
                return
            if position >= 0:
                yield index, position
            index += 1


def period_in_marks(cycle_lengths: Sequence[int]) -> int:
    """The effective period in marks: the lcm of all cycle lengths of a family.

    Not to be confused with the period in millimetres — § 5.3 warns about that
    explicitly, and snapping (§ 8.3) uses the millimetre one.
    """
    return math.lcm(*cycle_lengths) if cycle_lengths else 1


def period_um(spacing: Cycle, *, base_um: int, marks: int) -> int:
    """The effective period in micrometres, per the formula in § 5.3.

        sum(spacing) x base_spacing x (mark period / len(spacing))
    """
    repeats = Decimal(marks) / Decimal(len(spacing))
    return _round(Decimal(base_um) * spacing.total * repeats)


def _round(exact: Decimal) -> int:
    """Round to whole micrometres, ties away from zero — as in `units` (§ 14.3)."""
    return int(exact.quantize(Decimal(1), rounding=ROUND_HALF_UP))
