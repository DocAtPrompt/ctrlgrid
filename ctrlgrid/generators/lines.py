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

import math
from collections.abc import Iterator
from decimal import Decimal
from typing import Annotated, Any, Literal

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, model_validator

from ctrlgrid.axes import AxisPeriod
from ctrlgrid.clip import clip_to_area
from ctrlgrid.cycles import period_in_marks, period_um
from ctrlgrid.errors import DefinitionError
from ctrlgrid.generators.common import (
    DEFAULT_BASE_DASH,
    DEFAULT_DASH,
    HAIRLINE,
    ONE,
    ColorField,
    CycleField,
    Dashable,
    describe_cycle,
)
from ctrlgrid.marks import Area, Layer, Mark, Point, Segment
from ctrlgrid.model import LengthField, RelativeLengthField, Section
from ctrlgrid.pages import PageContext
from ctrlgrid.units import Length, parse_angle
from ctrlgrid.writers import WriterQuery


def _as_direction(value: Any) -> Any:
    """`horizontal`, `vertical`, or an angle (§ 7.1).

    An angle is kept as the text the user wrote — `55deg`, not 0.9599 rad —
    because § 12 reports back in the user's own units, and because it is what
    `describe` prints. `parse_angle` still runs, so a malformed angle is an
    error here rather than a surprise later.
    """
    if not isinstance(value, str):
        return value
    text = value.strip()
    if text in ("horizontal", "vertical"):
        return text
    if text.endswith("deg"):
        parse_angle(text, field="direction")
        return text
    raise ValueError(
        f"direction must be `horizontal`, `vertical` or an angle such as `55deg`, "
        f"not {value!r} (§ 7.1)"
    )


DirectionField = Annotated[str, BeforeValidator(_as_direction)]


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

    start: RelativeLengthField | None = None
    end: RelativeLengthField | None = None

    @model_validator(mode="after")
    def _ends_are_in_order(self) -> Extent:
        if self.start is not None and self.end is not None and self.start.um > self.end.um:
            raise ValueError(
                f"extent starts at {self.start.raw} and ends at {self.end.raw} — "
                "the end must not come before the start"
            )
        return self


class Family(Section, Dashable):
    """A periodic family of like marks (§ 4, § 7.1)."""

    direction: DirectionField
    base_spacing: RelativeLengthField
    #: Linear or logarithmic (§ 7.9). A log family is periodic per decade, and
    #: `base_spacing` is then the **decade length** rather than a step.
    law: Literal["linear", "log10"] = "linear"
    #: How many decades a log family covers. It acts like `count` does on a
    #: linear family: the block has a fixed length and does not repeat (§ 7.9).
    decades: int | None = Field(default=None, ge=1)
    spacing: CycleField = ONE
    base_weight: LengthField = HAIRLINE
    weight: CycleField = ONE
    style: Literal["solid", "dashed", "dotted"] = "solid"
    base_dash: LengthField = DEFAULT_BASE_DASH
    #: Absent means the style decides (see `DEFAULT_DASH`). Unlike every other
    #: cycle this one is **not** position-wise: § 5.3 calls it a dash pattern,
    #: and a pattern describes one mark rather than a run of them.
    dash: CycleField | None = None
    color: ColorField = ("#000000",)
    offset: RelativeLengthField = Length(um=0, mm=0.0, raw="0mm")
    extent: Extent | None = None
    #: Absent means unlimited. Deliberately no magic string `unlimited`
    #: (§ 7.1): a field that is either a word or a number forces a union in
    #: the model and gives poor error messages.
    count: int | None = Field(default=None, ge=1)
    #: Which family decides for its axis when snapping or placing the leftover
    #: (§ 8.3). Only needed when several families share an axis and disagree.
    governing: bool = False

    @property
    def is_slanted(self) -> bool:
        return self.direction.endswith("deg")

    @property
    def angle_deg(self) -> float:
        """The line's angle, taken **modulo 180°** — a line has no direction, so
        `55deg` and `235deg` are the same family (§ 3.5, § 7.1)."""
        return parse_angle(self.direction, field="direction").deg % 180.0

    @property
    def axis(self) -> str:
        """The axis the family advances along — not the one its lines run along.

        A horizontal family stacks upwards, so its spacing, offset and extent
        all live on y. A slanted family advances along neither axis; it has a
        perpendicular of its own, and nothing may ask it for a cartesian one
        (§ 7.1, § 8.3).
        """
        if self.is_slanted:
            raise AssertionError(
                f"a slanted family ({self.direction}) has no cartesian axis (§ 7.1)"
            )
        return "y" if self.direction == "horizontal" else "x"

    @property
    def is_log(self) -> bool:
        return self.law == "log10"

    @property
    def block_um(self) -> int:
        """The fixed length a log family occupies: decades x decade length (§ 7.9)."""
        return self.base_spacing.um * (self.decades or 0)

    @model_validator(mode="after")
    def _a_log_family_is_described_by_decades_and_nothing_else(self) -> Family:
        """§ 7.9, and § 5.1 on keys that cannot take effect where they stand."""
        if self.is_log and self.decades is None:
            raise ValueError(
                "`law: log10` needs `decades`: a log family has a fixed total length of "
                "decades x base_spacing and does not repeat, so there is nothing to end "
                "it otherwise (§ 7.9)"
            )
        if not self.is_log and self.decades is not None:
            raise ValueError(
                "`decades` only means something with `law: log10` — on a linear family "
                "the pattern area decides how many lines there are, and `count` limits "
                "them (§ 7.1, § 7.9)"
            )
        if self.is_log and "spacing" in self.model_fields_set:
            raise ValueError(
                "`spacing` and `law: log10` are two answers to the same question — the "
                "positions of a log family come from the logarithm, which is the point: "
                "nobody types 0.4771 (§ 7.9)"
            )
        return self

    @model_validator(mode="after")
    def _a_slant_has_neither_decades_nor_a_vote(self) -> Family:
        """§ 7.1: snapping is not supported for a slanted family — an error, not
        a guess. Both of these are that rule seen from the definition's side."""
        if not self.is_slanted:
            return self
        if self.is_log:
            raise ValueError(
                f"`law: log10` needs an axis to lay its decades along and "
                f"`direction: {self.direction}` has none — a logarithmic family is "
                "horizontal or vertical (§ 7.1, § 7.9)"
            )
        if self.governing:
            raise ValueError(
                f"`governing` decides an axis when snapping or placing the leftover, and "
                f"`direction: {self.direction}` has no axis — § 7.1 rules snapping out for "
                "slanted families, so there is nothing here to govern (§ 8.3)"
            )
        return self

    @model_validator(mode="after")
    def _the_dash_pattern_needs_a_style_that_uses_it(self) -> Family:
        self.check_dash(self.model_fields_set)
        return self

    @model_validator(mode="after")
    def _stroke_fits_between_the_lines(self) -> Family:
        """§ 12 point 6: the commonest user error is writing mm where pt was meant.

        A stroke as wide as its spacing turns the grid into a solid area, and
        the factor between the two units — 2.8 — is exactly large enough for
        that to happen unnoticed.
        """
        if self.is_log:
            # The narrowest gap of a decade is log10(10/9) of it, and checking
            # a stroke against a decade length would be meaningless.
            return self
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
            # A slanted family has a period, but not along x or y — and § 7.1
            # rules snapping out for it by name. Reporting nothing is how that
            # rule holds without the handle learning about angles (§ 8.3).
            if family.is_slanted:
                continue
            if family.is_log:
                # A log family has a fixed length and does not repeat, so it
                # cannot say how a leftover should be placed — but it *is* the
                # thing being placed, and § 7.9 sends that to `remainder`
                # (§ 8.5). It reports its block as one indivisible step, and
                # refuses snapping, which § 7.9 rules out by name.
                axes.setdefault(family.axis, []).append(
                    AxisPeriod(
                        step_um=family.block_um,
                        cycle_um=family.block_um,
                        label=f"{family.decades} decades of {family.base_spacing.raw}",
                        governing=family.governing,
                        fixed_block=True,
                        _spacing=ONE,
                        _base_um=family.block_um,
                        _offset_um=family.offset.um,
                    )
                )
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
            if family.is_log:
                # § 7.9: "repeats every N lines" is meaningless for a family
                # that does not repeat; the decade length is what matters.
                lines.append(
                    f"{family.direction}: log10, {family.decades} decades of "
                    f"{family.base_spacing.raw} = "
                    f"{family.block_um / 1000:.1f} mm, weight "
                    f"{family.base_weight.raw} x {describe_cycle(family.weight)}"
                )
                continue
            marks = period_in_marks(
                [len(family.spacing), len(family.weight), len(family.color)]
            )
            length = period_um(family.spacing, base_um=family.base_spacing.um, marks=marks)
            parts = [
                f"spacing {family.base_spacing.raw} x {describe_cycle(family.spacing)}",
                f"weight {family.base_weight.raw} x {describe_cycle(family.weight)}",
            ]
            if family.style != "solid":
                pattern = family.dash or DEFAULT_DASH[family.style]
                parts.append(f"{family.style} {family.base_dash.raw} x {describe_cycle(pattern)}")
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

    #: § 8.3: cartesian families have periods, so snapping means something.
    supports_snap = True

    def check(self, cfg: LinesConfig, *, area: Area, q: WriterQuery) -> None:
        """One thing only an area can disprove: a log block that is too long.

        § 7.9 makes it an error with the arithmetic, the same check § 12
        point 10 prescribes for count-driven generators — and it belongs here
        rather than in `generate`, which runs while pages are written.
        """
        for family in cfg.families:
            if not family.is_log:
                continue
            available = area.height if family.axis == "y" else area.width
            if family.block_um > available:
                raise DefinitionError(
                    f"{family.decades} decades of {family.base_spacing.raw} need "
                    f"{_mm(family.block_um)} on the {family.axis} axis and the pattern "
                    f"area is {_mm(available)}. A log family has a fixed length and is "
                    "never compressed (§ 8.2) — use fewer decades, a shorter decade or "
                    "a larger format (§ 7.9)",
                    field="families",
                )

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
            # A slanted family has no cartesian axis to be pixel-snapped on,
            # and § 7.1 rules snapping out for it — so it is not asked (§ 8.3.1).
            pixel_dpi = None if family.is_slanted else page.pixel_of(family.axis)
            yield from self._family(family, area, pixel_dpi)

    def _log_family(
        self, family: Family, *, span: int, horizontal: bool
    ) -> Iterator[Segment]:
        """The decade pattern of § 7.9, computed rather than typed.

        Nine lines per decade at log10(1…9) plus the one that closes the last
        decade. The index runs on across decade boundaries, so a nine-entry
        weight cycle marks every decade start — which is exactly the example
        § 7.9 gives.
        """
        for index, position in enumerate(_log_positions(family)):
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
                dash=family.dash_pattern,
                cap=family.cap,
                layer=Layer.PATTERN,
            )

    def _slanted_family(self, family: Family, area: Area) -> Iterator[Segment]:
        """A family at an angle (§ 7.1): spaced perpendicular, clipped to the area.

        Line 0 goes through the pattern area's origin — the same rule a
        horizontal family follows, generalised — and an unlimited family grows
        to **both** sides of it. For a horizontal or vertical family the whole
        area lies on the positive side, so that is not a second rule; for a 45°
        family it is the only way to cover the sheet, since the line through
        one corner leaves half the area behind it.
        """
        radians = math.radians(family.angle_deg)
        along = (math.cos(radians), math.sin(radians))
        # The perpendicular is the line direction turned 90°, with its sign
        # chosen so it points into the area: that is what makes `90deg` count
        # into the sheet exactly as `vertical` does, rather than backwards. A
        # square's diagonal leaves the centre exactly on line 0; there the
        # canonical turn stands, so the choice is never arbitrary.
        normal = (-along[1], along[0])
        centre = _project(area.width / 2, area.height / 2, normal)
        if centre < 0:
            normal = (-normal[0], -normal[1])

        corners = [
            _project(x, y, normal)
            for x, y in ((0, 0), (area.width, 0), (0, area.height), (area.width, area.height))
        ]
        lower, upper = min(corners), max(corners)
        if family.extent is not None:
            if family.extent.start is not None:
                lower = max(lower, family.extent.start.um)
            if family.extent.end is not None:
                upper = min(upper, family.extent.end.um)
        if family.count is not None:
            lower = max(lower, 0)  # `count` counts from line 0, in cycle order

        # Long enough to cross the area from any point on it, so the clip and
        # not the length decides where a line ends.
        reach = area.width + area.height
        drawn = 0

        for index, distance in family.spacing.positions_between(
            base_um=family.base_spacing.um,
            lower_um=math.floor(lower),
            upper_um=math.ceil(upper),
            offset_um=family.offset.um,
            field="families",
        ):
            foot = Point(round(distance * normal[0]), round(distance * normal[1]))
            clipped = clip_to_area(
                Point(round(foot.x - reach * along[0]), round(foot.y - reach * along[1])),
                Point(round(foot.x + reach * along[0]), round(foot.y + reach * along[1])),
                area,
            )
            if clipped is None:
                continue  # this line does not cross the area at all
            yield Segment(
                start=clipped[0],
                end=clipped[1],
                weight=family.base_weight.mm * float(family.weight.at(index)),
                color=family.color[index % len(family.color)],
                dash=family.dash_pattern,
                cap=family.cap,
                layer=Layer.PATTERN,
            )
            drawn += 1
            if family.count is not None and drawn >= family.count:
                return

    def _family(
        self, family: Family, area: Area, pixel_dpi: int | None = None
    ) -> Iterator[Segment]:
        if family.is_slanted:
            # Snapping is refused for a slanted family upstream (§ 7.1), so no
            # pixel density can reach here.
            yield from self._slanted_family(family, area)
            return

        horizontal = family.direction == "horizontal"
        extent = area.height if horizontal else area.width
        span = area.width if horizontal else area.height

        if family.is_log:
            # A log family is `fixed_block` and snapping is refused for it
            # upstream (§ 7.9), so it never reaches here pixel-snapped.
            yield from self._log_family(family, span=span, horizontal=horizontal)
            return

        lower = family.extent.start.um if family.extent and family.extent.start else 0
        upper = family.extent.end.um if family.extent and family.extent.end else extent
        drawn = 0

        for index, position in family.spacing.positions(
            base_um=family.base_spacing.um,
            extent_um=extent,
            offset_um=family.offset.um,
            pixel_dpi=pixel_dpi,
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
                # The dash pattern belongs to the family, not to the position:
                # every line of it is dashed the same way (§ 5.3).
                dash=family.dash_pattern,
                cap=family.cap,
                layer=Layer.PATTERN,
            )

            drawn += 1
            if family.count is not None and drawn >= family.count:
                return


def _log_positions(family: Family) -> list[int]:
    """Every line of a log family, in micrometres from its own start (§ 7.9).

    Rounded once, from the exact value: § 8.2 forbids accumulated drift, and
    every position here is computed from the logarithm rather than from its
    neighbour.
    """
    decade = family.base_spacing.um
    offset = family.offset.um
    positions = [
        offset + round(decade * (index + math.log10(step)))
        for index in range(family.decades or 0)
        for step in range(1, 10)
    ]
    positions.append(offset + decade * (family.decades or 0))
    return positions


def _mm(um: int) -> str:
    return f"{um / 1000:.1f}mm"


def _project(x: float, y: float, normal: tuple[float, float]) -> float:
    """A point's coordinate along the perpendicular — how far it is from line 0."""
    return x * normal[0] + y * normal[1]
