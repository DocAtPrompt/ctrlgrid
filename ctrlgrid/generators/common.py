"""What every blade with families needs — cycles, colours and dash patterns.

§ 5.3 calls the cycle model "the load-bearing idea", and § 7.6 claims it
carries over to polar coordinates *unchanged*. A claim like that is only true
if the same code serves both, so the field types and the dash rules live here
rather than being written twice with a drift between them.

Nothing about geometry is in this module. A blade decides what a cycle counts
— millimetres along an axis, micro-degrees around a circle — and that decision
stays with the blade.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Annotated, Any

from pydantic import BeforeValidator

from ctrlgrid.cycles import Cycle
from ctrlgrid.units import Length

_HEX = "0123456789abcdefABCDEF"


def as_cycle(value: Any) -> Any:
    """Turn a list of bare numbers into a `Cycle`.

    § 5.1: number cycles hold bare numbers only; absolute values belong in the
    matching `base_*`. A length here would make `spacing: [5]` and
    `base_spacing: 5mm` two different things that look alike.
    """
    if isinstance(value, Cycle):
        return value
    if not isinstance(value, list):
        raise ValueError(
            f"a cycle is a list of bare numbers, for example [1, 1, 2] — got {value!r} (§ 5.3)"
        )
    entries = []
    for entry in value:
        if isinstance(entry, str):
            raise ValueError(
                f"cycle entries are bare multiples of the base, not lengths — got {entry!r}; "
                "absolute values belong in the matching base_* key (§ 5.1)"
            )
        try:
            entries.append(Decimal(str(entry)))
        except (InvalidOperation, TypeError):
            raise ValueError(f"cycle entries must be numbers, got {entry!r}") from None
    return Cycle.of(entries)


def as_colors(value: Any) -> Any:
    """A colour field is either one `#rrggbb` or a cycle of them (§ 5.3)."""
    values = value if isinstance(value, list) else [value]
    for entry in values:
        if not (
            isinstance(entry, str)
            and len(entry) == 7
            and entry.startswith("#")
            and all(character in _HEX for character in entry[1:])
        ):
            raise ValueError(
                f"colour must be #rrggbb, six digits, RGB — got {entry!r}. "
                "No names, no eight-digit alpha, no CMYK; opacity is its own field (§ 5.3)"
            )
    return tuple(values)


CycleField = Annotated[Cycle, BeforeValidator(as_cycle)]
ColorField = Annotated[tuple[str, ...], BeforeValidator(as_colors)]

ONE = Cycle.of([Decimal(1)])
HAIRLINE = Length(um=53, mm=0.052916666666666667, raw="0.15pt")

#: What a style dashes with when no cycle is written (§ 7.1). `dotted` is
#: `[0, 2]` because a zero-length on-segment with a round cap is a dot — the
#: trick § 10.1 prescribes for the `dots` blade, and the reason `cap` is in the
#: mark vocabulary at all. `dashed` is the 3:2 that reads as a dash at every
#: sensible line weight.
DEFAULT_DASH = {
    "dashed": Cycle.of([Decimal(3), Decimal(2)]),
    "dotted": Cycle.of([Decimal(0), Decimal(2)]),
}

DEFAULT_BASE_DASH = Length(um=1000, mm=1.0, raw="1mm")


class Dashable:
    """The dash half of a family: `style`, `base_dash`, `dash` (§ 5.3, § 7.1).

    The dash cycle is the one cycle that is **not** position-wise. Every other
    cycle steps along the marks — "every third line heavier"; this one
    describes a single mark and applies to all of them, which is why it also
    stays out of the effective period, and the period counts marks.
    """

    style: str
    base_dash: Length
    dash: Cycle | None

    @property
    def dash_pattern(self) -> tuple[float, ...]:
        """The stroke's dash array in millimetres, or empty for a solid line."""
        if self.style == "solid":
            return ()
        cycle = self.dash or DEFAULT_DASH[self.style]
        return tuple(self.base_dash.mm * float(value) for value in cycle.values)

    @property
    def cap(self) -> str:
        return "round" if self.style == "dotted" else "butt"

    def check_dash(self, model_fields_set: set[str]) -> None:
        """§ 5.1: a key that cannot take effect where it stands is an error."""
        named = {key for key in ("dash", "base_dash") if key in model_fields_set}
        if self.style == "solid" and named:
            raise ValueError(
                f"{', '.join(sorted(named))} given, but style is `solid` — a solid line "
                "has no dash pattern. Set style: dashed or dotted (§ 7.1)"
            )
        if self.style != "solid" and not any(self.dash_pattern):
            raise ValueError(
                f"the dash pattern of this {self.style} family is all zeros, which draws "
                "nothing at all. At least one entry must be positive (§ 5.3)"
            )


def describe_cycle(cycle: Cycle) -> str:
    """A cycle the way it was written: `[1, 1, 2.7]`, without Decimal noise."""
    return "[" + ", ".join(f"{value:f}".rstrip("0").rstrip(".") or "0"
                           for value in cycle.values) + "]"
