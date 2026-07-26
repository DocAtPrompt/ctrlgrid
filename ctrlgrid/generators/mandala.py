"""`mandala` — rotationally symmetric templates (§ 7.11), the second blade on
the polar geometry of § 7.6.

A mandala here is a **template to draw on**, not a finished drawing. That is the
whole reason it is parametric and not a shape language (§ 2): the tool lays down
the scaffold and a few motif families that carry the N-fold symmetry, and the
hand fills the rest. So the motif is built-in elements the user parameterises —
rings and spokes as a scaffold, and on top of it rosettes, petals, beads,
scallops, pinwheels and inscribed regular or star polygons — the seven families
§ 7.11 names. They need four of the six primitives (§ 6): `Arc`, `Segment`,
`Polygon` and — for a ring of beads — `Dot`. No primitive was added for any of
them, which is the point: a petal is two arcs, not a path (decision 41).

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
from ctrlgrid.marks import Arc, Area, Dot, Layer, Mark, Point, Polygon, Segment, Um
from ctrlgrid.model import ColorField, LengthField, RelativeLengthField, Section
from ctrlgrid.pages import PageContext
from ctrlgrid.writers import WriterQuery

#: Straight up. A mandala has a vertical axis, so everything is measured from
#: the top of the sheet, not from the right the way bare polar coordinates run.
UP = 90.0


class Center(Section):
    """A point in pattern-local coordinates, origin bottom left (§ 3.5)."""

    x: RelativeLengthField
    y: RelativeLengthField


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


class Petals(Section):
    """A ring of N pointed leaves, each two arcs (§ 7.11). Only `Arc`.

    A petal is a leaf whose base sits at `inner` of the outer radius and whose
    tip reaches `outer`, both on the sector's own angle; `width` is the half-
    width at the widest as a share of the outer radius — the bulge of the two
    sides. `mirror` puts a second petal on every sector bisector, the same
    "repeated *and* mirrored" the rosette does. One petal per sector.
    """

    inner: float = Field(default=0.30, gt=0.0, lt=1.0)
    outer: float = Field(default=0.95, gt=0.0, le=1.0)
    width: float = Field(default=0.12, gt=0.0)
    mirror: bool = False
    weight: LengthField = HAIRLINE
    color: ColorField = "#000000"

    @model_validator(mode="after")
    def _base_below_tip(self) -> Petals:
        # A degenerate petal (base at or past the tip) has no leaf to draw. § 12
        # refuses it loudly rather than bending it into something.
        if self.inner >= self.outer:
            raise ValueError(
                f"petals.inner ({self.inner}) must be less than petals.outer "
                f"({self.outer}): the base sits below the tip (§ 7.11)"
            )
        return self


class Beads(Section):
    """Dots evenly spaced on a ring (§ 7.11). Introduces the `Dot` primitive.

    `at` is the ring's share of the outer radius; `count` defaults to the sector
    count (a whole multiple keeps the N-fold symmetry, but any count is allowed
    — the user's call). `size` is the bead diameter, absolute (`0.8mm`) or
    relative (`%s`). `rotate` offsets the ring by a few degrees where two rings
    should interleave.
    """

    at: float = Field(gt=0.0)
    count: int | None = Field(default=None, ge=1)
    size: RelativeLengthField
    rotate: float = 0.0
    color: ColorField = "#000000"


class Scallops(Section):
    """A wavy ring: N arcs bulging out from (or into) a base circle (§ 7.11).

    The scallops sit on a base circle at `at` of the outer radius; each arc runs
    between two adjacent points and bulges by `depth` (a share of the outer
    radius). `inward` turns the bulge in, for a ring of cusps rather than lobes.
    Only `Arc`. Count defaults to the sector count.
    """

    at: float = Field(gt=0.0)
    count: int | None = Field(default=None, ge=1)
    depth: float = Field(default=0.06, gt=0.0)
    inward: bool = False
    weight: LengthField = HAIRLINE
    color: ColorField = "#000000"


class Pinwheel(Section):
    """Small polygons repeated round a ring, each twisted (§ 7.11).

    N little `sides`-gons of circumradius `size` (a share of the outer radius)
    sit on a ring at `at`. Each is turned with its position and by an extra
    `twist`, which is what makes the ring spin rather than sit still. Only
    `Polygon`. Count defaults to the sector count.
    """

    at: float = Field(gt=0.0)
    size: float = Field(gt=0.0)
    sides: int = Field(default=4, ge=3)
    count: int | None = Field(default=None, ge=1)
    twist: float = 0.0
    weight: LengthField = HAIRLINE
    color: ColorField = "#000000"
    fill_color: ColorField = None


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
    outer_radius: RelativeLengthField | Literal["auto"] = "auto"
    rings: Rings | None = None
    spokes: Spokes | None = None
    #: A motif ring given once or as a list — layered bands (§ 7.11). A single
    #: mapping still validates, so older definitions are unchanged.
    rosette: Rosette | tuple[Rosette, ...] | None = None
    petals: Petals | tuple[Petals, ...] | None = None
    beads: Beads | tuple[Beads, ...] | None = None
    scallops: Scallops | tuple[Scallops, ...] | None = None
    pinwheel: Pinwheel | tuple[Pinwheel, ...] | None = None
    polygons: tuple[PolygonSpec, ...] | None = None

    @property
    def rosettes(self) -> tuple[Rosette, ...]:
        return _as_rings(self.rosette)

    @property
    def petal_rings(self) -> tuple[Petals, ...]:
        return _as_rings(self.petals)

    @property
    def bead_rings(self) -> tuple[Beads, ...]:
        return _as_rings(self.beads)

    @property
    def scallop_rings(self) -> tuple[Scallops, ...]:
        return _as_rings(self.scallops)

    @property
    def pinwheels(self) -> tuple[Pinwheel, ...]:
        return _as_rings(self.pinwheel)

    @model_validator(mode="after")
    def _something_has_to_be_drawn(self) -> MandalaConfig:
        if not any((
            self.rings, self.spokes, self.rosette, self.petals, self.beads,
            self.scallops, self.pinwheel, self.polygons,
        )):
            raise ValueError(
                "a mandala needs `rings`, `spokes`, a `rosette`, `petals`, `beads`, "
                "`scallops`, a `pinwheel` or `polygons` — with none there is only an "
                "empty disc (§ 7.11)"
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
        for rosette in cfg.rosettes:
            count = cfg.sectors * (2 if rosette.mirror else 1)
            lines.append(f"rosette: {count} circles at {rosette.at:.2f} of the radius")
        for petals in cfg.petal_rings:
            count = cfg.sectors * (2 if petals.mirror else 1)
            lines.append(f"petals: {count}, tips at {petals.outer:.2f} of the radius")
        for beads in cfg.bead_rings:
            count = beads.count if beads.count is not None else cfg.sectors
            lines.append(f"beads: {count} at {beads.at:.2f} of the radius")
        for scallops in cfg.scallop_rings:
            count = scallops.count if scallops.count is not None else cfg.sectors
            lines.append(f"scallops: {count} at {scallops.at:.2f} of the radius")
        for pinwheel in cfg.pinwheels:
            count = pinwheel.count if pinwheel.count is not None else cfg.sectors
            lines.append(
                f"pinwheel: {count} {pinwheel.sides}-gons at {pinwheel.at:.2f} of the radius"
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
        # Scaffold first, then the motif families, so guides sit under motifs.
        if cfg.rings is not None:
            yield from _rings(cfg.rings, center, outer)
        if cfg.spokes is not None:
            yield from _spokes(cfg.spokes, cfg.sectors, center, outer)
        for rosette in cfg.rosettes:
            yield from _rosette(rosette, cfg.sectors, center, outer)
        for petals in cfg.petal_rings:
            yield from _petals(petals, cfg.sectors, center, outer)
        for beads in cfg.bead_rings:
            yield from _beads(beads, cfg.sectors, center, outer)
        for scallops in cfg.scallop_rings:
            yield from _scallops(scallops, cfg.sectors, center, outer)
        for pinwheel in cfg.pinwheels:
            yield from _pinwheel(pinwheel, cfg.sectors, center, outer)
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


def _as_rings(value: object) -> tuple:
    """Normalise a single-or-list motif field to a tuple (§ 7.11).

    `None` is no ring, a single mapping is one, a list is itself — so a blade
    method iterates one shape whether the definition wrote one ring or several.
    """
    if value is None:
        return ()
    if isinstance(value, tuple):
        return value
    return (value,)


def _petals(petals: Petals, sectors: int, center: Point, outer: Um) -> Iterator[Arc]:
    """A ring of leaves, each two arcs from base to tip (§ 7.11)."""
    inner = round(petals.inner * outer)
    tip = round(petals.outer * outer)
    sagitta = round(petals.width * outer)
    # On the spokes; and, mirrored, on the bisectors half a sector round.
    offsets = [0.0, 0.5] if petals.mirror else [0.0]
    for offset in offsets:
        for i in range(sectors):
            angle = UP + (i + offset) * 360.0 / sectors
            base = polar_point(center, inner, angle)
            apex = polar_point(center, tip, angle)
            for side in (1.0, -1.0):
                o, radius, start, sweep = _arc_geometry(base, apex, sagitta, side)
                yield Arc(
                    center=o,
                    radius=radius,
                    start_angle=start,
                    sweep=sweep,
                    weight=petals.weight.mm,
                    color=petals.color or "#000000",
                    layer=Layer.PATTERN,
                )


def _arc_geometry(b: Point, t: Point, sagitta: Um, side: float) -> tuple[Point, Um, float, float]:
    """A circular arc through `b` and `t` bulging `sagitta` to one side.

    The chord `b→t` is radial; the arc deviates tangentially by `sagitta` at its
    middle. From the chord length `c`, `r = sagitta/2 + c²/(8·sagitta)`, and the
    centre sits `r − sagitta` back along the perpendicular. The start/sweep are
    read off the rounded centre so the drawn arc lands on `b` and `t` (§ 8.2).
    Two of these, `side = ±1`, make the two sides of one petal.
    """
    mx, my = (b.x + t.x) / 2, (b.y + t.y) / 2
    dx, dy = t.x - b.x, t.y - b.y
    chord = math.hypot(dx, dy)
    ux, uy = -dy / chord * side, dx / chord * side
    r = sagitta / 2 + chord * chord / (8 * sagitta)
    o = Point(round(mx - (r - sagitta) * ux), round(my - (r - sagitta) * uy))
    start = math.degrees(math.atan2(b.y - o.y, b.x - o.x))
    end = math.degrees(math.atan2(t.y - o.y, t.x - o.x))
    sweep = end - start
    # The minor arc: the leaf side, not the long way round the circle.
    while sweep <= -180.0:
        sweep += 360.0
    while sweep > 180.0:
        sweep -= 360.0
    return o, round(r), start, sweep


def _beads(beads: Beads, sectors: int, center: Point, outer: Um) -> Iterator[Dot]:
    """Dots evenly spaced on a ring (§ 7.11)."""
    count = beads.count if beads.count is not None else sectors
    at = round(beads.at * outer)
    for i in range(count):
        angle = UP + beads.rotate + i * 360.0 / count
        yield Dot(
            pos=polar_point(center, at, angle),
            diameter=beads.size.mm,
            color=beads.color or "#000000",
            layer=Layer.PATTERN,
        )


def _scallops(scallops: Scallops, sectors: int, center: Point, outer: Um) -> Iterator[Arc]:
    """A closed wavy ring: one arc between each pair of adjacent base points."""
    count = scallops.count if scallops.count is not None else sectors
    at = round(scallops.at * outer)
    depth = round(scallops.depth * outer)
    points = [polar_point(center, at, UP + i * 360.0 / count) for i in range(count)]
    for i in range(count):
        p1, p2 = points[i], points[(i + 1) % count]
        side = _outward_side(p1, p2, center, inward=scallops.inward)
        o, radius, start, sweep = _arc_geometry(p1, p2, depth, side)
        yield Arc(
            center=o,
            radius=radius,
            start_angle=start,
            sweep=sweep,
            weight=scallops.weight.mm,
            color=scallops.color or "#000000",
            layer=Layer.PATTERN,
        )


def _outward_side(p1: Point, p2: Point, center: Point, *, inward: bool) -> float:
    """Which side of the chord bulges away from the centre (§ 7.11).

    `_arc_geometry` bulges toward the perpendicular `(-dy, dx)` scaled by the
    returned sign; picking the sign that points away from the centre makes a
    lobe, its opposite makes a cusp.
    """
    mx, my = (p1.x + p2.x) / 2, (p1.y + p2.y) / 2
    dx, dy = p2.x - p1.x, p2.y - p1.y
    outward = (-dy) * (mx - center.x) + dx * (my - center.y)
    side = 1.0 if outward >= 0 else -1.0
    return -side if inward else side


def _pinwheel(pinwheel: Pinwheel, sectors: int, center: Point, outer: Um) -> Iterator[Polygon]:
    """Small polygons round a ring, each turned with its place and by `twist`."""
    count = pinwheel.count if pinwheel.count is not None else sectors
    at = round(pinwheel.at * outer)
    size = round(pinwheel.size * outer)
    for i in range(count):
        angle = UP + i * 360.0 / count
        hub = polar_point(center, at, angle)
        points = tuple(
            polar_point(hub, size, angle + pinwheel.twist + k * 360.0 / pinwheel.sides)
            for k in range(pinwheel.sides)
        )
        yield Polygon(
            points=points,
            closed=True,
            weight=pinwheel.weight.mm,
            color=pinwheel.color or "#000000",
            fill_color=pinwheel.fill_color,
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

    Every family is asked, because most of them can reach past the rim: a
    rosette `at + radius`, a petal its tip (plus a lateral term for a fat leaf),
    a bead ring `at + size / 2`, a scallop `at + depth`, a pinwheel `at + size`,
    and a polygon its own `radius`, which is unbounded. The scaffold reaches
    `outer` — which is itself a candidate, since an explicit `outer_radius` is
    honoured as written and only `auto` fits by construction. Whichever is
    farthest decides whether the disc fits (§ 8.2).
    """
    reaches: list[tuple[Um, str]] = []
    if cfg.rings is not None or cfg.spokes is not None:
        reaches.append((outer, "outer radius"))
    for rosette in cfg.rosettes:
        reaches.append((round((rosette.at + rosette.radius) * outer), "rosette"))
    for petals in cfg.petal_rings:
        # The tip reaches `outer`; a wide petal's sides can reach a touch farther
        # out at their bulge, so the lateral term guards the rare fat leaf.
        share = max(petals.outer, math.hypot((petals.inner + petals.outer) / 2, petals.width))
        reaches.append((round(share * outer), "petals"))
    for beads in cfg.bead_rings:
        reaches.append((round(beads.at * outer) + round(beads.size.um / 2), "beads"))
    for scallops in cfg.scallop_rings:
        # Outward lobes reach `at + depth`; cusps turned in reach only the ring.
        share = scallops.at + (0.0 if scallops.inward else scallops.depth)
        reaches.append((round(share * outer), "scallops"))
    for pinwheel in cfg.pinwheels:
        reaches.append((round((pinwheel.at + pinwheel.size) * outer), "pinwheel"))
    for index, spec in enumerate(cfg.polygons or ()):
        reaches.append((round(spec.radius * outer), f"polygons.{index}"))
    return max(reaches, key=lambda item: item[0])


def _mm(um: Um) -> str:
    return f"{um / 1000:.1f}mm"
