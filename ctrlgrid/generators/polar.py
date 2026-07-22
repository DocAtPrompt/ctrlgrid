"""`polar` — rings and spokes (§ 7.6), and the hard test of § 14.

Every other blade is cartesian. This one is deliberately the *second*, not the
last: if the handle copes with a polar generator — pattern area, frame,
capability check, label measurement — the architecture holds, and if it does
not, that is better learnt after blade two than after blade seven.

**The cycle model carries over unchanged**, which § 7.6 claims and this module
has to make true. It does it by running the very same `Cycle` in another unit:
rings step in micrometres along the radius, spokes step in **micro-degrees**
around the circle, and both call `Cycle.positions`. Nothing about the cycle
machinery knows which of the two it is serving.

Three rules of § 7.6 shape the rest:

* **Centre** is the middle of the pattern area, **outer radius** half the
  shorter side, both overridable.
* **`radial_extent`, not `extent`.** In § 7.1 an extent is measured *across*
  the direction of the lines; here the bound runs *along* the spoke. The same
  key name for two reference axes would be a trap, so it gets its own.
* **Snapping is not supported** — an error, never a guess (§ 8.3). The blade
  says so once, through `supports_snap`, and the handle refuses before it
  computes any geometry.

Labels are measured before the first page is written (§ 10.2, § 12 point 13):
"12" in a 15° segment near the centre does not fit, and finding that out on the
sheet is exactly what the pre-flight exists to prevent.
"""

from __future__ import annotations

import math
from collections.abc import Iterator
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ctrlgrid.axes import AxisPeriod
from ctrlgrid.cycles import period_in_marks, period_um
from ctrlgrid.errors import DefinitionError
from ctrlgrid.generators.common import (
    DEFAULT_BASE_DASH,
    HAIRLINE,
    ONE,
    ColorField,
    CycleField,
    Dashable,
    describe_cycle,
)
from ctrlgrid.labels import labels_for
from ctrlgrid.marks import Arc, Area, Layer, Mark, Point, Segment, Text, Um
from ctrlgrid.model import AngleField, FontSpec, LengthField, Section
from ctrlgrid.pages import PageContext
from ctrlgrid.writers import WriterQuery

#: Angles run in micro-degrees for the same reason lengths run in micrometres
#: (§ 3.3): a full turn is an exact integer, 360_000_000, so twelve 30° spokes
#: close the circle exactly instead of ending at 359.999999°.
FULL_TURN = 360_000_000
PER_DEGREE = 1_000_000


class Center(Section):
    """A point in pattern-local coordinates, origin bottom left (§ 3.5)."""

    x: LengthField
    y: LengthField


class RadialExtent(Section):
    """From where to where a spoke runs — *along* the spoke (§ 7.6).

    Either end may be left out, and then the ring of the outer radius bounds
    it. Deliberately not called `extent`: § 7.1 measures that one across the
    direction of the lines, and one name for two reference axes is a trap.
    """

    start: LengthField | None = None
    end: LengthField | None = None

    @model_validator(mode="after")
    def _ends_are_in_order(self) -> RadialExtent:
        if self.start is not None and self.end is not None and self.start.um > self.end.um:
            raise ValueError(
                f"radial_extent starts at {self.start.raw} and ends at {self.end.raw} — "
                "the end must not come before the start"
            )
        return self


class Rings(Section, Dashable):
    """Concentric circles: the radial family (§ 7.6)."""

    base_radius: LengthField
    radius: CycleField = ONE
    base_weight: LengthField = HAIRLINE
    weight: CycleField = ONE
    style: Literal["solid", "dashed", "dotted"] = "solid"
    base_dash: LengthField = DEFAULT_BASE_DASH
    dash: CycleField | None = None
    color: ColorField = ("#000000",)

    @model_validator(mode="after")
    def _the_dash_pattern_needs_a_style_that_uses_it(self) -> Rings:
        self.check_dash(self.model_fields_set)
        return self


class Spokes(Section, Dashable):
    """Radial lines: the angular family (§ 7.6)."""

    base_angle: AngleField
    angle: CycleField = ONE
    base_weight: LengthField = HAIRLINE
    weight: CycleField = ONE
    style: Literal["solid", "dashed", "dotted"] = "solid"
    base_dash: LengthField = DEFAULT_BASE_DASH
    dash: CycleField | None = None
    color: ColorField = ("#000000",)
    radial_extent: RadialExtent | None = None

    @model_validator(mode="after")
    def _the_dash_pattern_needs_a_style_that_uses_it(self) -> Spokes:
        self.check_dash(self.model_fields_set)
        return self

    @model_validator(mode="after")
    def _a_spoke_family_has_to_advance(self) -> Spokes:
        if self.base_angle.deg <= 0:
            raise ValueError(
                f"base_angle must be greater than 0deg, got {self.base_angle.raw} — "
                "a family that does not advance would draw one spoke for ever"
            )
        if self.base_angle.deg >= 360:
            raise ValueError(
                f"base_angle {self.base_angle.raw} is a full turn or more, so there would "
                "be a single spoke. Use a smaller angle (§ 7.6)"
            )
        return self


class PolarLabels(Section):
    """Segment and ring labels (§ 7.6, § 7.10)."""

    #: A counting pattern (§ 7.10) or an explicit list; `none` leaves them out.
    spokes: str | list[object] | None = None
    #: Where the segment labels sit, as a share of the outer radius.
    spoke_radius: float = Field(default=0.85, gt=0.0, le=1.0)
    #: § 7.6 writes these as a score, outermost first: [10, 8, 6, 4].
    rings: str | list[object] | None = None
    font: FontSpec = FontSpec(size="8pt")


class PolarConfig(BaseModel):
    """The definition section belonging to this blade (§ 3.6, seam 2)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    center: Center | Literal["auto"] = "auto"
    outer_radius: LengthField | Literal["auto"] = "auto"
    rings: Rings | None = None
    spokes: Spokes | None = None
    labels: PolarLabels | None = None

    @model_validator(mode="after")
    def _something_has_to_be_drawn(self) -> PolarConfig:
        if self.rings is None and self.spokes is None:
            raise ValueError(
                "a polar pattern needs `rings`, `spokes` or both — with neither there is "
                "nothing to draw (§ 7.6)"
            )
        return self


class PolarGenerator:
    name = "polar"
    config_model = PolarConfig

    #: § 8.3 and § 7.6: snapping is an error here, not a guess. There is no
    #: axis to snap to — the pattern has a centre, not a grid — so the blade
    #: says no once and the handle refuses before computing any geometry.
    supports_snap = False

    def periodic_axes(self, cfg: PolarConfig) -> dict[str, list[AxisPeriod]]:
        """None: nothing in a polar pattern advances along x or y (§ 8.3)."""
        return {}

    def is_page_invariant(self, cfg: PolarConfig) -> bool:
        """Always: the pattern depends on the area, never on the page (§ 10.1)."""
        return True

    def describe(self, cfg: PolarConfig) -> list[str]:
        """Base values, cycles and the effective period of both families (§ 5.3)."""
        lines: list[str] = []
        if cfg.rings is not None:
            rings = cfg.rings
            marks = period_in_marks(
                [len(rings.radius), len(rings.weight), len(rings.color)]
            )
            length = period_um(rings.radius, base_um=rings.base_radius.um, marks=marks)
            lines.append(
                f"rings: base_radius {rings.base_radius.raw} x {describe_cycle(rings.radius)}"
                f", weight {rings.base_weight.raw} x {describe_cycle(rings.weight)} — "
                f"repeats every {marks} ring{'s' if marks != 1 else ''} = "
                f"{length / 1000:.1f} mm"
            )
        if cfg.spokes is not None:
            spokes = cfg.spokes
            marks = period_in_marks(
                [len(spokes.angle), len(spokes.weight), len(spokes.color)]
            )
            period = period_um(
                spokes.angle, base_um=_udeg(spokes.base_angle.deg), marks=marks
            )
            lines.append(
                f"spokes: base_angle {spokes.base_angle.raw} x "
                f"{describe_cycle(spokes.angle)} — repeats every {marks} "
                f"spoke{'s' if marks != 1 else ''} = {period / PER_DEGREE:.1f}deg"
            )
            if FULL_TURN % period:
                # Not an error: a 100° fan is a legitimate thing to draw. But
                # the gap next to 0° is narrower than the rest, and § 12 would
                # rather say so once than let it look like a bug on paper.
                lines.append(
                    f"spokes: the cycle does not close the circle — "
                    f"{(FULL_TURN % period) / PER_DEGREE:.1f}deg is left over at the end"
                )
        return lines

    def check(self, cfg: PolarConfig, *, area: Area, q: WriterQuery) -> None:
        """Everything that must be refused before page one (§ 12 point 13).

        Two things can only be known here: whether the circle fits the pattern
        area it was handed, and whether the segment labels fit the segments.
        § 7.6 asks for the second by name — "12" in a 15° segment at the inner
        radius does not fit — and § 10.2 supplies the measuring tape.
        """
        center, outer = _frame(cfg, area)
        self._circle_fits(cfg, center, outer, area)
        self._labels_fit(cfg, outer, q)

    def _circle_fits(
        self, cfg: PolarConfig, center: Point, outer: Um, area: Area
    ) -> None:
        overflow = max(
            outer - center.x,
            outer - center.y,
            center.x + outer - area.width,
            center.y + outer - area.height,
        )
        if overflow <= 0:
            return
        radius = cfg.outer_radius.raw if cfg.outer_radius != "auto" else _mm(outer)
        raise DefinitionError(
            f"an outer radius of {radius} runs {_mm(overflow)} outside the pattern area "
            f"({_mm(area.width)} x {_mm(area.height)}). Nothing is clipped and nothing is "
            "scaled (§ 8.2): reduce outer_radius, move the centre, or widen the pattern "
            "area by reducing a margin (§ 7.6, § 8.1)",
            field="outer_radius",
        )

    def _labels_fit(self, cfg: PolarConfig, outer: Um, q: WriterQuery) -> None:
        if cfg.labels is None:
            return

        # Counting the labels is itself a refusal that belongs here: a list of
        # the wrong length is an error (§ 7.10), and raising it from `generate`
        # would raise it half way through writing the file (§ 12 point 13).
        if cfg.labels.rings and cfg.rings is not None:
            labels_for(
                cfg.labels.rings, len(_ring_radii(cfg.rings, outer)), field="labels.rings"
            )

        if cfg.spokes is None or not cfg.labels.spokes:
            return
        angles = _spoke_angles(cfg.spokes)
        contents = labels_for(cfg.labels.spokes, len(angles), field="labels.spokes")
        if not contents:
            return

        size = cfg.labels.font.size.um
        family = cfg.labels.font.token
        radius = int(outer * cfg.labels.spoke_radius)
        for index, content in enumerate(contents):
            span = _segment_span(angles, index)
            # The chord of the segment at the label's radius: the widest text
            # that can stand inside the wedge without crossing a spoke.
            room = int(2 * radius * math.sin(math.radians(span / PER_DEGREE / 2)))
            width = q.text_width(content, family=family, size=size)
            if width > room:
                raise DefinitionError(
                    f"the label {content!r} is {_mm(width)} wide and its segment is "
                    f"{_mm(room)} across at {_mm(radius)} from the centre "
                    f"({span / PER_DEGREE:.1f}deg wide). A segment label is never cut — "
                    "it would be worthless (§ 8.9) — so lower labels.font.size, raise "
                    "labels.spoke_radius, or use fewer spokes (§ 7.6)",
                    field="labels.spokes",
                )

    def generate(
        self,
        cfg: PolarConfig,
        *,
        area: Area,
        page: PageContext,
        q: WriterQuery,
    ) -> Iterator[Mark]:
        center, outer = _frame(cfg, area)
        if cfg.rings is not None:
            yield from self._rings(cfg.rings, center, outer)
        if cfg.spokes is not None:
            yield from self._spokes(cfg.spokes, center, outer)
        if cfg.labels is not None:
            yield from self._labels(cfg, center, outer, q)

    def _rings(self, rings: Rings, center: Point, outer: Um) -> Iterator[Arc]:
        # Mark 0 of a family sits on the origin, and in polar coordinates the
        # origin is the centre point — a circle of radius 0 is not a mark. So
        # the weight and colour cycles count *drawn* rings: `weight: [1,1,1,2]`
        # makes every fourth visible ring heavy, which is what it says.
        for index, radius in enumerate(_ring_radii(rings, outer)):
            yield Arc(
                center=center,
                radius=radius,
                start_angle=0.0,
                sweep=360.0,
                weight=rings.base_weight.mm * float(rings.weight.at(index)),
                color=rings.color[index % len(rings.color)],
                dash=rings.dash_pattern,
                layer=Layer.PATTERN,
            )

    def _spokes(self, spokes: Spokes, center: Point, outer: Um) -> Iterator[Segment]:
        extent = spokes.radial_extent
        inner_um = extent.start.um if extent and extent.start else 0
        outer_um = extent.end.um if extent and extent.end else outer

        for index, angle in _spoke_positions(spokes):
            yield Segment(
                start=_polar(center, inner_um, angle),
                end=_polar(center, outer_um, angle),
                weight=spokes.base_weight.mm * float(spokes.weight.at(index)),
                color=spokes.color[index % len(spokes.color)],
                dash=spokes.dash_pattern,
                cap=spokes.cap,
                layer=Layer.PATTERN,
            )

    def _labels(
        self, cfg: PolarConfig, center: Point, outer: Um, q: WriterQuery
    ) -> Iterator[Text]:
        labels = cfg.labels
        assert labels is not None
        size = labels.font.size.um
        family = labels.font.token
        ascent, _ = q.text_metrics(family=family, size=size)

        if labels.spokes and cfg.spokes is not None:
            angles = _spoke_angles(cfg.spokes)
            radius = int(outer * labels.spoke_radius)
            for index, content in enumerate(
                labels_for(labels.spokes, len(angles), field="labels.spokes")
            ):
                # The label belongs to the *segment* between two spokes, not to
                # a spoke: § 7.6's twelve 30° spokes carry 1 … 12 in the wedges.
                middle = angles[index] + _segment_span(angles, index) // 2
                position = _polar(center, radius, middle % FULL_TURN)
                yield Text(
                    pos=Point(position.x, position.y - ascent // 2),
                    content=content,
                    size=size,
                    family=family,
                    align="center",
                    layer=Layer.PATTERN,
                )

        if labels.rings and cfg.rings is not None:
            radii = _ring_radii(cfg.rings, outer)
            angle = _ring_label_angle(cfg)
            # Outermost first, the way § 7.6 writes a score: [10, 8, 6, 4]. Each
            # label sits in the middle of its band, between its ring and the
            # next one inwards.
            for content, (radius, inner) in zip(
                labels_for(labels.rings, len(radii), field="labels.rings"),
                [(radii[index], radii[index - 1] if index else 0)
                 for index in reversed(range(len(radii)))],
                strict=True,
            ):
                position = _polar(center, (radius + inner) // 2, angle)
                yield Text(
                    pos=Point(position.x, position.y - ascent // 2),
                    content=content,
                    size=size,
                    family=family,
                    align="center",
                    layer=Layer.PATTERN,
                )


# ------------------------------------------------------------------ geometry


def _frame(cfg: PolarConfig, area: Area) -> tuple[Point, Um]:
    """Centre and outer radius, both defaulting as § 7.6 prescribes."""
    center = (
        Point(area.width // 2, area.height // 2)
        if cfg.center == "auto"
        else Point(cfg.center.x.um, cfg.center.y.um)
    )
    outer = (
        min(area.width, area.height) // 2
        if cfg.outer_radius == "auto"
        else cfg.outer_radius.um
    )
    return center, outer


def _polar(center: Point, radius: Um, angle_udeg: int) -> Point:
    """A point at `radius` and `angle`, mathematically positive from the right.

    Computed from the exact angle every time rather than by stepping around the
    circle: § 8.2 forbids accumulated drift, and the angles themselves are
    exact integers of micro-degrees (§ 3.3, § 3.5).
    """
    radians = math.radians(angle_udeg / PER_DEGREE)
    return Point(
        center.x + round(radius * math.cos(radians)),
        center.y + round(radius * math.sin(radians)),
    )


def _spoke_positions(spokes: Spokes) -> list[tuple[int, int]]:
    """`(index, angle)` for one full turn, in micro-degrees.

    The very same `Cycle.positions` the cartesian families use, in another
    unit — which is what § 7.6's "the cycle model carries over unchanged" has
    to mean if it is to mean anything.
    """
    return [
        (index, angle)
        for index, angle in spokes.angle.positions(
            base_um=_udeg(spokes.base_angle.deg),
            extent_um=FULL_TURN,
            field="spokes.base_angle",
        )
        # A spoke at 360° is the one at 0°, and two strokes on one line print
        # heavier than the rest of the family.
        if angle < FULL_TURN
    ]


def _spoke_angles(spokes: Spokes) -> list[int]:
    return [angle for _, angle in _spoke_positions(spokes)]


def _segment_span(angles: list[int], index: int) -> int:
    """How wide the segment starting at `angles[index]` is, in micro-degrees."""
    if len(angles) == 1:
        return FULL_TURN
    following = angles[index + 1] if index + 1 < len(angles) else angles[0] + FULL_TURN
    return following - angles[index]


def _ring_label_angle(cfg: PolarConfig) -> int:
    """Where the ring labels run, in micro-degrees.

    Straight up, unless a spoke runs there — which it does for every family
    that divides 90°, and a number printed over a line is unreadable. In that
    case they move to the bisector of the segment that contains straight up:
    still the top of the disc, and never on a stroke.
    """
    up = FULL_TURN // 4
    if cfg.spokes is None:
        return up
    angles = _spoke_angles(cfg.spokes)
    index = max(
        (index for index, angle in enumerate(angles) if angle <= up), default=len(angles) - 1
    )
    return (angles[index] + _segment_span(angles, index) // 2) % FULL_TURN


def _ring_radii(rings: Rings, outer: Um) -> list[Um]:
    return [
        radius
        for _, radius in rings.radius.positions(
            base_um=rings.base_radius.um, extent_um=outer, field="rings.base_radius"
        )
        if radius > 0
    ]


def _udeg(degrees: float) -> int:
    return round(degrees * PER_DEGREE)


def _mm(um: Um) -> str:
    return f"{um / 1000:.1f}mm"
