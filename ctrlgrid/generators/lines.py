"""`lines` — the blade M1 carries (§ 7.1).

Any number of families. Squared, ruled, isometric, calligraphic, logarithmic
and Cornell paper are all this one generator with different cycles; the ones
this milestone does not reach yet say so by name rather than failing as typos.

The blade computes in local coordinates with the origin at the bottom left of
the pattern area (§ 3.5) and never learns what a margin is (§ 3.3). Mark 0 of a
family sits on that origin — for a horizontal family at the bottom edge, for a
vertical one at the left — and `offset` moves the start of the cycle from there.
"""

from __future__ import annotations

from collections.abc import Iterator
from decimal import Decimal, InvalidOperation
from typing import Annotated, Any, ClassVar, Literal

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, model_validator

from ctrlgrid.axes import AxisPeriod
from ctrlgrid.cycles import Cycle, period_in_marks, period_um
from ctrlgrid.marks import Area, Layer, Mark, Point, Segment
from ctrlgrid.model import LengthField, Section
from ctrlgrid.pages import PageContext
from ctrlgrid.units import Length
from ctrlgrid.writers import WriterQuery

_HEX = "0123456789abcdefABCDEF"


def _as_cycle(value: Any) -> Any:
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


def _as_colors(value: Any) -> Any:
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


def _as_direction(value: Any) -> Any:
    if isinstance(value, str) and value.strip().endswith("deg"):
        raise ValueError(
            f"slanted families ({value!r}, § 7.1) need clipping against the pattern area "
            "and are not implemented yet — this milestone takes horizontal and vertical"
        )
    return value


CycleField = Annotated[Cycle, BeforeValidator(_as_cycle)]
ColorField = Annotated[tuple[str, ...], BeforeValidator(_as_colors)]
DirectionField = Annotated[Literal["horizontal", "vertical"], BeforeValidator(_as_direction)]


class Extent(Section):
    """Where a family is allowed to sit (§ 7.1).

    Measured **perpendicular to the line direction** — the same axis as
    `offset` and `base_spacing`, as § 7.1 states for slanted families and § 7.6
    repeats when it introduces `radial_extent` for the case that runs the other
    way. So an extent decides *which lines exist*, never how long they are:
    § 2 rules out placing a stroke of chosen length at a chosen coordinate, and
    that stays true.

    Either end may be left out, in which case the pattern area bounds it.
    """

    start: LengthField | None = None
    end: LengthField | None = None

    @model_validator(mode="after")
    def _ends_are_in_order(self) -> Extent:
        if self.start is not None and self.end is not None and self.start.um > self.end.um:
            raise ValueError(
                f"extent starts at {self.start.raw} and ends at {self.end.raw} — "
                "the end must not come before the start"
            )
        return self


class Family(Section):
    """A periodic family of like marks (§ 4, § 7.1)."""

    deferred: ClassVar[dict[str, str]] = {
        "law": "— logarithmic axes (§ 7.9) arrive with milestone M4",
        "base_dash": "— dashed and dotted styles arrive with milestone M2 (§ 7.1)",
        "dash": "— dashed and dotted styles arrive with milestone M2 (§ 7.1)",
    }

    direction: DirectionField
    base_spacing: LengthField
    spacing: CycleField = Cycle.of([Decimal(1)])
    base_weight: LengthField = Length(um=53, mm=0.052916666666666667, raw="0.15pt")
    weight: CycleField = Cycle.of([Decimal(1)])
    style: Literal["solid"] = "solid"
    color: ColorField = ("#000000",)
    offset: LengthField = Length(um=0, mm=0.0, raw="0mm")
    extent: Extent | None = None
    #: Absent means unlimited. Deliberately no magic string `unlimited`
    #: (§ 7.1): a field that is either a word or a number forces a union in
    #: the model and gives poor error messages.
    count: int | None = Field(default=None, ge=1)
    #: Which family decides for its axis when snapping or placing the leftover
    #: (§ 8.3). Only needed when several families share an axis and disagree.
    governing: bool = False

    @property
    def axis(self) -> str:
        """The axis the family advances along — not the one its lines run along.

        A horizontal family stacks upwards, so its spacing, offset and extent
        all live on y.
        """
        return "y" if self.direction == "horizontal" else "x"

    @model_validator(mode="before")
    @classmethod
    def _name_the_deferred_styles(cls, data: Any) -> Any:
        if isinstance(data, dict) and data.get("style") in {"dashed", "dotted"}:
            raise ValueError(
                f"style {data['style']!r} arrives with milestone M2 (§ 7.1); "
                "this milestone draws solid lines"
            )
        return data

    @model_validator(mode="after")
    def _stroke_fits_between_the_lines(self) -> Family:
        """§ 12 point 6: the commonest user error is writing mm where pt was meant.

        A stroke as wide as its spacing turns the grid into a solid area, and
        the factor between the two units — 2.8 — is exactly large enough for
        that to happen unnoticed.
        """
        widest = self.base_weight.mm * float(max(self.weight.values))
        narrowest_multiple = min((v for v in self.spacing.values if v > 0), default=Decimal(1))
        narrowest = self.base_spacing.mm * float(narrowest_multiple)
        if widest >= narrowest:
            raise ValueError(
                f"stroke width {self.base_weight.raw} is not narrower than the spacing "
                f"{self.base_spacing.raw} — the lines would close into a solid area. "
                "A common cause is writing mm where pt was meant (§ 12)"
            )
        return self


def _cycle(cycle: Cycle) -> str:
    """A cycle the way it was written: `[1, 1, 2.7]`, without Decimal noise."""
    return "[" + ", ".join(f"{value:f}".rstrip("0").rstrip(".") or "0"
                           for value in cycle.values) + "]"


class LinesConfig(BaseModel):
    """The definition section belonging to this blade (§ 3.6, seam 2)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    families: list[Family] = Field(min_length=1)


class LinesGenerator:
    name = "lines"
    config_model = LinesConfig

    def periodic_axes(self, cfg: LinesConfig) -> dict[str, list[AxisPeriod]]:
        """Every unlimited family, keyed by the axis it advances along (§ 8.3, § 8.5).

        Limited families are left out on purpose: a family with `count` or an
        `extent` does not fill the area, so it has no say in how the leftover
        of that area is placed. Snapping to the single red margin rule of an
        exercise book would be absurd.
        """
        axes: dict[str, list[AxisPeriod]] = {}
        for family in cfg.families:
            if family.count is not None or family.extent is not None:
                continue
            marks = period_in_marks(
                [len(family.spacing), len(family.weight), len(family.color)]
            )
            axes.setdefault(family.axis, []).append(
                AxisPeriod(
                    step_um=family.base_spacing.um,
                    cycle_um=period_um(
                        family.spacing, base_um=family.base_spacing.um, marks=marks
                    ),
                    label=f"base_spacing {family.base_spacing.raw}",
                    governing=family.governing,
                    _spacing=family.spacing,
                    _base_um=family.base_spacing.um,
                    _offset_um=family.offset.um,
                )
            )
        return axes

    def describe(self, cfg: LinesConfig) -> list[str]:
        """Base values, cycles, and the effective period in both sizes.

        Only the blade knows its own cycles, so only the blade can report this
        — and it has to be reported twice over: § 5.3 requires the period in
        marks *and* in millimetres, because the two are easy to confuse and
        snapping (§ 8.3) works on the second; § 8.8 requires the base values
        and the cycles besides, so that a sheet which came out right stays
        reproducible years later without the definition in hand.

        The base value is quoted **as the user wrote it** (`0.15pt`, not
        `0.05mm`): § 12 asks for the user's own units, and a summary that
        silently converts is a summary nobody recognises their own file in.
        """
        lines = []
        for family in cfg.families:
            marks = period_in_marks(
                [len(family.spacing), len(family.weight), len(family.color)]
            )
            length = period_um(family.spacing, base_um=family.base_spacing.um, marks=marks)
            parts = [
                f"spacing {family.base_spacing.raw} x {_cycle(family.spacing)}",
                f"weight {family.base_weight.raw} x {_cycle(family.weight)}",
            ]
            if len(family.color) > 1:
                parts.append(f"{len(family.color)} colours")
            if family.offset.um:
                parts.append(f"offset {family.offset.raw}")
            if family.count is not None:
                parts.append(f"count {family.count}")
            lines.append(
                f"{family.direction}: {', '.join(parts)} — repeats every {marks} "
                f"line{'s' if marks != 1 else ''} = {length / 1000:.1f} mm"
            )
        return lines

    def is_page_invariant(self, cfg: LinesConfig) -> bool:
        """Always: a family depends on the pattern area, never on the page (§ 10.1)."""
        return True

    def generate(
        self,
        cfg: LinesConfig,
        *,
        area: Area,
        page: PageContext,
        q: WriterQuery,
    ) -> Iterator[Mark]:
        for family in cfg.families:
            yield from self._family(family, area)

    def _family(self, family: Family, area: Area) -> Iterator[Segment]:
        horizontal = family.direction == "horizontal"
        extent = area.height if horizontal else area.width
        span = area.width if horizontal else area.height

        lower = family.extent.start.um if family.extent and family.extent.start else 0
        upper = family.extent.end.um if family.extent and family.extent.end else extent
        drawn = 0

        for index, position in family.spacing.positions(
            base_um=family.base_spacing.um,
            extent_um=extent,
            offset_um=family.offset.um,
        ):
            # The index keeps counting through positions that are skipped, so
            # weight and colour stay in step with the spacing cycle. Otherwise
            # moving an extent would quietly recolour the family.
            if position > upper:
                return
            if position < lower:
                continue

            start, end = (
                (Point(0, position), Point(span, position))
                if horizontal
                else (Point(position, 0), Point(position, span))
            )
            yield Segment(
                start=start,
                end=end,
                weight=family.base_weight.mm * float(family.weight.at(index)),
                color=family.color[index % len(family.color)],
                layer=Layer.PATTERN,
            )

            drawn += 1
            if family.count is not None and drawn >= family.count:
                return
