"""What the handle needs to know about a blade's periodic axes (§ 8.3, § 8.5).

Its own module because both sides of seam 2 need it: the blade fills it in,
the handle reads it, and neither may import the other (§ 3.3).
"""

from __future__ import annotations

from dataclasses import dataclass

from ctrlgrid.cycles import Cycle


@dataclass(frozen=True, slots=True)
class AxisPeriod:
    """What the handle needs to know about one periodic axis (§ 8.3, § 8.5).

    Snapping and remainder handling are settings of the handle, but the numbers
    they need are the blade's: with a cycle like `[1, 1, 2]` the leftover
    cannot be worked out from the base spacing alone. Rather than push page
    geometry down into the blade — which § 3.3 forbids — the blade answers
    questions and the handle shrinks the pattern area (§ 8.3).

    A blade with no periodic families returns nothing, and that is exactly how
    § 8.3 wants `snap` refused for `staves`, `grid`, `maze`, `tiling` and
    `form`: not as silent ineffectiveness, but as an error.
    """

    step_um: int
    """One base step — the granularity of `snap: spacing`."""

    cycle_um: int
    """The period in millimetres of § 5.3 — the granularity of `snap: cycle`."""

    label: str
    """How to name this family in an error message, e.g. its base spacing."""

    governing: bool
    """Set by the definition to settle an axis several families share (§ 8.3)."""

    _spacing: Cycle
    _base_um: int
    _offset_um: int

    fixed_block: bool = False
    """Whether this is one indivisible block rather than a repeating period.

    A logarithmic family is one (§ 7.9): it has a fixed length of
    `decades x base_spacing`, it does not repeat when the area is longer, and
    snapping to a decade length would be meaningless. It reports itself here
    all the same, because § 7.9 sends the question of *where the block sits*
    to `remainder` (§ 8.5) — and remainder works on exactly these numbers."""


    def used(self, available_um: int) -> int:
        """How much of `available_um` the family actually reaches."""
        if self.fixed_block:
            return min(self.cycle_um, available_um)
        last = 0
        for _, position in self._spacing.positions(
            base_um=self._base_um, extent_um=available_um, offset_um=self._offset_um
        ):
            last = position
        return last

    def used_whole_cycles(self, available_um: int) -> int:
        """The same, but stopping at the last complete cycle (§ 8.5)."""
        if self.fixed_block:
            return self.used(available_um)
        length = len(self._spacing)
        last = 0
        for index, position in self._spacing.positions(
            base_um=self._base_um, extent_um=available_um, offset_um=self._offset_um
        ):
            if index % length == 0:
                last = position
        return last
