"""`mandala` — rotationally symmetric templates (§ 7.11), the second blade on
the polar geometry of § 7.6.

A mandala here is a **template to draw on**, not a finished drawing. That is the
whole reason it is parametric and not a shape language (§ 2): the tool lays down
the scaffold and a few motif families that carry the N-fold symmetry, and the
hand fills the rest. So the motif is built-in elements the user parameterises —
a rosette of overlapping circles (`Arc`) and inscribed regular or star polygons
(`Polygon`) — the two § 7.11 names, each needing one of the two curved-or-many
primitives (§ 6).

It shares the coordinate arithmetic of `polar` through `polar_geometry` — centre,
outer radius, the point at a radius and an angle — but **not** the cycle model
(§ 15.1). Sectors and rings are plain counts: a mandala is defined by its order
of symmetry, not by a base value stepped through multiples (§ 5.3). Everything
faces **up** (90°): a mandala has a vertical axis, so a spoke, the first polygon
vertex and the top of the rosette all point to the top of the sheet.

`supports_snap=False`, `periodic_axes={}` — there is no axis to snap to, a disc
has a centre, not a grid (§ 8.3) — and `check` refuses what only the pattern
area can disprove: a rosette whose circles reach past the area (§ 8.2, § 12
point 13).
"""

from __future__ import annotations

import math
from collections.abc import Iterator
from fractions import Fraction
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ctrlgrid.axes import AxisPeriod
from ctrlgrid.errors import DefinitionError
from ctrlgrid.generators.common import HAIRLINE
from ctrlgrid.generators.polar_geometry import default_center, default_outer, polar_point
from ctrlgrid.marks import Arc, Area, Layer, Mark, Point, Polygon, Segment, Um
from ctrlgrid.model import ColorField, LengthField, Section
from ctrlgrid.pages import PageContext
from ctrlgrid.writers import WriterQuery

#: Straight up. A mandala has a vertical axis, so everything is measured from
#: the top of the sheet, not from the right the way bare polar coordinates run.
UP = 90.0


class Center(Section):
    """A point in pattern-local coordinates, origin bottom left (§ 3.5)."""

    x: LengthField
    y: LengthField


class Rings(Section):
    """Concentric guide circles, evenly spaced out to the rim (§ 7.11)."""

    count: int = Field(ge=1)
    weight: LengthField = HAIRLINE
    color: ColorField = "#000000"


class Spokes(Section):
    """The N radial guide lines, one per sector (§ 7.11)."""

    #: A share of the outer radius left clear at the centre, so N spokes do not
    #: meet in one ink blot — the same worry § 7.6 answers with `radial_extent`.
    inner: float = Field(default=0.0, ge=0.0, lt=1.0)
    weight: LengthField = HAIRLINE
    color: ColorField = "#000000"


class Rosette(Section):
    """The motif: N overlapping circles, one on each spoke (§ 7.11).

    `at` and `radius` are shares of the outer radius, so the flower scales with
    the disc and follows the page. `mirror` doubles the ring of circles onto the
    sector bisectors — § 7.11's "repeated *and* mirrored" made a switch, since a
    circle on its own spoke is already symmetric across it.
    """

    at: float = Field(gt=0.0)
    radius: float = Field(gt=0.0)
    mirror: bool = False
    weight: LengthField = HAIRLINE
    color: ColorField = "#000000"


class PolygonSpec(Section):
    """An inscribed regular polygon or star polygon (§ 7.11).

    `sides` defaults to the sector count, so the polygon lands on the scaffold.
    `step` makes a star {sides/step}: the path visits every `step`-th vertex.
    """

    radius: float = Field(gt=0.0)
    sides: int | None = Field(default=None, ge=3)
    step: int = Field(default=1, ge=1)
    rotate: float = 0.0
    weight: LengthField = HAIRLINE
    color: ColorField = "#000000"
    fill_color: ColorField = None


class MandalaConfig(BaseModel):
    """The definition section for this blade (§ 3.6, seam 2)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    #: The order of symmetry: a mandala is defined by it, so it is required and
    #: never a cycle. Two is the fewest that repeats.
    sectors: int = Field(ge=2)
    center: Center | Literal["auto"] = "auto"
    outer_radius: LengthField | Literal["auto"] = "auto"
    rings: Rings | None = None
    spokes: Spokes | None = None
    rosette: Rosette | None = None
    polygons: tuple[PolygonSpec, ...] | None = None

    @model_validator(mode="after")
    def _something_has_to_be_drawn(self) -> MandalaConfig:
        if (
            self.rings is None
            and self.spokes is None
            and self.rosette is None
            and self.polygons is None
        ):
            raise ValueError(
                "a mandala needs `rings`, `spokes`, a `rosette` or `polygons` — with none "
                "there is only an empty disc (§ 7.11)"
            )
        return self

    @model_validator(mode="after")
    def _stars_are_proper_not_compound(self) -> MandalaConfig:
        # {6/2} is not a star but two overlaid triangles: gcd(sides, step) > 1
        # splits the path into that many separate components, and a single
        # `Polygon` would draw a broken one. Refused loudly (§ 12), never bent.
        for index, spec in enumerate(self.polygons or ()):
            sides = spec.sides if spec.sides is not None else self.sectors
            if spec.step >= sides:
                raise ValueError(
                    f"polygons.{index}.step ({spec.step}) must be less than the "
                    f"{sides} sides it steps over (§ 7.11)"
                )
            if spec.step > 1 and math.gcd(sides, spec.step) != 1:
                raise ValueError(
                    f"polygons.{index}: a star {{{sides}/{spec.step}}} is compound — "
                    f"gcd({sides}, {spec.step}) is {math.gcd(sides, spec.step)}, so it is "
                    f"{math.gcd(sides, spec.step)} overlaid polygons, not one path. Use a "
                    "step coprime with the side count (§ 7.11)"
                )
        return self


class MandalaGenerator:
    name = "mandala"
    config_model = MandalaConfig

    #: § 8.3, § 7.11: a disc has a centre, not an axis, so there is nothing to
    #: snap to. An error, said once, refused before any geometry is computed.
    supports_snap = False

    def periodic_axes(self, cfg: MandalaConfig) -> dict[str, list[AxisPeriod]]:
        """None: nothing advances along x or y by a fixed period (§ 8.3)."""
        return {}

    def is_page_invariant(self, cfg: MandalaConfig) -> bool:
        """Always: it depends on the pattern area, never the page (§ 10.1)."""
        return True

    def describe(self, cfg: MandalaConfig) -> list[str]:
        """Sectors and the families drawn, for the run report (§ 5.3)."""
        lines = [f"{cfg.sectors}-fold symmetry"]
        if cfg.rings is not None:
            lines.append(f"rings: {cfg.rings.count}, evenly spaced")
        if cfg.spokes is not None:
            lines.append(f"spokes: {cfg.sectors}")
        if cfg.rosette is not None:
            count = cfg.sectors * (2 if cfg.rosette.mirror else 1)
            lines.append(
                f"rosette: {count} circles at {cfg.rosette.at:.2f} of the radius"
            )
        for index, spec in enumerate(cfg.polygons or ()):
            sides = spec.sides if spec.sides is not None else cfg.sectors
            shape = f"{{{sides}/{spec.step}}}" if spec.step > 1 else f"{sides}-gon"
            lines.append(f"polygon {index + 1}: {shape} at {spec.radius:.2f} of the radius")
        return lines

    def check(self, cfg: MandalaConfig, *, area: Area, q: WriterQuery) -> None:
        """Refuse what only the pattern area can disprove (§ 12 point 13).

        The scaffold fits by construction — the outer radius is at most half the
        shorter side. A rosette does not: its circles are centred out along the
        radius and reach `at + radius` of it, which can poke past the disc and
        out of the area. Nothing is clipped or scaled (§ 8.2), so it is refused
        here, before page one, naming what reaches out and by how much.
        """
        center, outer = _frame(cfg, area)
        reach, what = _max_reach(cfg, outer)
        overflow = max(
            reach - center.x,
            reach - center.y,
            center.x + reach - area.width,
            center.y + reach - area.height,
        )
        if overflow > 0:
            raise DefinitionError(
                f"the {what} reaches {_mm(reach)} from the centre and runs {_mm(overflow)} "
                f"outside the pattern area ({_mm(area.width)} x {_mm(area.height)}). Nothing "
                "is clipped and nothing is scaled (§ 8.2): lower `at` or `radius`, or widen "
                "the area by reducing a margin (§ 7.11, § 8.1)",
                field=what.split()[0],
            )

    def generate(
        self,
        cfg: MandalaConfig,
        *,
        area: Area,
        page: PageContext,
        q: WriterQuery,
    ) -> Iterator[Mark]:
        center, outer = _frame(cfg, area)
        if cfg.rings is not None:
            yield from _rings(cfg.rings, center, outer)
        if cfg.spokes is not None:
            yield from _spokes(cfg.spokes, cfg.sectors, center, outer)
        if cfg.rosette is not None:
            yield from _rosette(cfg.rosette, cfg.sectors, center, outer)
        for spec in cfg.polygons or ():
            yield _polygon(spec, cfg.sectors, center, outer)


# ------------------------------------------------------------------ geometry


def _frame(cfg: MandalaConfig, area: Area) -> tuple[Point, Um]:
    """Centre and outer radius, defaulting as § 7.6 prescribes."""
    center = (
        default_center(area)
        if cfg.center == "auto"
        else Point(cfg.center.x.um, cfg.center.y.um)
    )
    outer = default_outer(area) if cfg.outer_radius == "auto" else cfg.outer_radius.um
    return center, outer


def _rings(rings: Rings, center: Point, outer: Um) -> Iterator[Arc]:
    for k in range(1, rings.count + 1):
        # Each radius from its exact fraction of the rim, never stepped (§ 8.2).
        radius = round(Fraction(k * outer, rings.count))
        yield Arc(
            center=center,
            radius=radius,
            start_angle=0.0,
            sweep=360.0,
            weight=rings.weight.mm,
            color=rings.color or "#000000",
            layer=Layer.PATTERN,
        )


def _spokes(spokes: Spokes, sectors: int, center: Point, outer: Um) -> Iterator[Segment]:
    inner = round(spokes.inner * outer)
    for i in range(sectors):
        angle = UP + i * 360.0 / sectors
        yield Segment(
            start=polar_point(center, inner, angle),
            end=polar_point(center, outer, angle),
            weight=spokes.weight.mm,
            color=spokes.color or "#000000",
            layer=Layer.PATTERN,
        )


def _rosette(rosette: Rosette, sectors: int, center: Point, outer: Um) -> Iterator[Arc]:
    at = round(rosette.at * outer)
    radius = round(rosette.radius * outer)
    # On the spokes; and, mirrored, on the bisectors between them — the second
    # ring half a sector round, which is what "repeated and mirrored" draws.
    offsets = [0.0, 0.5] if rosette.mirror else [0.0]
    for offset in offsets:
        for i in range(sectors):
            angle = UP + (i + offset) * 360.0 / sectors
            yield Arc(
                center=polar_point(center, at, angle),
                radius=radius,
                start_angle=0.0,
                sweep=360.0,
                weight=rosette.weight.mm,
                color=rosette.color or "#000000",
                layer=Layer.PATTERN,
            )


def _polygon(spec: PolygonSpec, sectors: int, center: Point, outer: Um) -> Polygon:
    sides = spec.sides if spec.sides is not None else sectors
    radius = round(spec.radius * outer)
    # For a star {sides/step} the path visits every step-th vertex; step 1 is
    # the plain convex polygon. The vertices themselves sit at equal angles from
    # up, and the path just names them in a different order.
    points = tuple(
        polar_point(center, radius, UP + spec.rotate + (i * spec.step % sides) * 360.0 / sides)
        for i in range(sides)
    )
    return Polygon(
        points=points,
        closed=True,
        weight=spec.weight.mm,
        color=spec.color or "#000000",
        fill_color=spec.fill_color,
        layer=Layer.PATTERN,
    )


def _max_reach(cfg: MandalaConfig, outer: Um) -> tuple[Um, str]:
    """The farthest any mark reaches from the centre, and what reaches it.

    The scaffold and the polygons reach the rim at most; a rosette reaches
    `at + radius`. Whichever is farthest decides whether the disc fits (§ 8.2).
    """
    reaches: list[tuple[Um, str]] = []
    if cfg.rings is not None or cfg.spokes is not None:
        reaches.append((outer, "outer radius"))
    if cfg.rosette is not None:
        reaches.append((round((cfg.rosette.at + cfg.rosette.radius) * outer), "rosette"))
    for index, spec in enumerate(cfg.polygons or ()):
        reaches.append((round(spec.radius * outer), f"polygons.{index}"))
    return max(reaches, key=lambda item: item[0])


def _mm(um: Um) -> str:
    return f"{um / 1000:.1f}mm"
