"""`perspective` — a vanishing-point grid (§ 7.11), and the first blade whose
law is *convergence*, not a cycle.

§ 5.3 makes the cycle model load-bearing, and § 7.6 proved it carries into
polar coordinates unchanged. A perspective grid is where it stops: the spacing
between rays is not a base value times dimensionless multiples but a function
of distance to the point, and § 7.11 says so — "the ray spacings converge,
that is a law of its own". So this blade computes its own geometry (§ 5.3
grants it) and holds no `Cycle`.

What it *keeps* from `polar` is the shape of the seam, not the machinery: own
geometry means `supports_snap=False` and `periodic_axes={}` (there is no axis
to snap to, § 8.3), `is_page_invariant=True` (it depends on the pattern area,
never the page), and a `check` that refuses what only the area can disprove
(§ 12 point 13).

The law is **equal base division** — the reading of § 7.11's two possibilities
that draws a receding floor rather than a sunburst. Each vanishing point owns
one edge of the pattern area, that edge is cut into equal steps, and a ray runs
from every step to the point, **clipped to the area** (§ 8.2: nothing is drawn
outside it, nothing is scaled). Towards the point the steps crowd together on
their own — that convergence is the whole picture.

Vanishing points are given as a **share** of the pattern area, not a sheet
coordinate, and may lie outside it (§ 7.11): a point at `[-0.5, 0.5]` sits half
an area-width off the left edge, which is exactly where a two-point grid wants
it, and it still follows the page when the format changes.
"""

from __future__ import annotations

from collections.abc import Iterator
from fractions import Fraction
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ctrlgrid.axes import AxisPeriod
from ctrlgrid.errors import DefinitionError
from ctrlgrid.generators.common import HAIRLINE
from ctrlgrid.marks import Area, Layer, Mark, Point, Segment
from ctrlgrid.model import ColorField, LengthField, Section
from ctrlgrid.pages import PageContext
from ctrlgrid.writers import WriterQuery

Edge = Literal["top", "bottom", "left", "right"]


class Horizon(Section):
    """The horizon line: a horizontal rule across the pattern area (§ 7.11).

    `at` is a share of the height, so it follows the page. A bare number is the
    shorthand — `horizon: 0.5` — turned into this block by the config below.
    """

    at: float = Field(ge=0.0, le=1.0)
    weight: LengthField = HAIRLINE
    color: ColorField = "#000000"


class VanishingPoint(Section):
    """One point that a fan of rays converges to (§ 7.11)."""

    #: Position as a share of the pattern area, origin bottom left (§ 3.5). May
    #: lie outside 0..1 — a two-point grid wants its points off the sheet.
    at: tuple[float, float]
    #: Rays in the fan, counted as the equal steps of the base edge, both
    #: corners included. Two is the fewest that is still a fan.
    count: int = Field(ge=2)
    #: Which edge is cut into equal steps. Left out, it is the edge farthest
    #: from the point — the visible foreground opposite the vanishing direction.
    base: Edge | None = None
    weight: LengthField = HAIRLINE
    color: ColorField = "#000000"


class Verticals(Section):
    """The parallel family: evenly spaced uprights that do *not* converge.

    § 7.11's two-point grid keeps its verticals vertical — that is what makes
    it two-point and not three. So these are plain `lines`, drawn here only so
    a perspective sheet needs a single generator (one document, one blade).
    """

    count: int = Field(ge=2)
    weight: LengthField = HAIRLINE
    color: ColorField = "#000000"


class PerspectiveConfig(BaseModel):
    """The definition section for this blade (§ 3.6, seam 2)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    horizon: Horizon | None = None
    vanishing_points: tuple[VanishingPoint, ...] | None = None
    verticals: Verticals | None = None

    @model_validator(mode="before")
    @classmethod
    def _a_bare_horizon_is_its_height(cls, data: object) -> object:
        # `horizon: 0.5` is the shorthand every drawing tutorial writes; the
        # block form carries weight and colour. Both reach the same model.
        if isinstance(data, dict) and isinstance(data.get("horizon"), (int, float)):
            data = {**data, "horizon": {"at": data["horizon"]}}
        return data

    @model_validator(mode="after")
    def _at_most_three_points(self) -> PerspectiveConfig:
        # § 7.11 names one, two or three vanishing points. A fourth is not a
        # perspective any eye reads — better refused than silently drawn.
        if self.vanishing_points is not None and len(self.vanishing_points) > 3:
            raise ValueError(
                f"a perspective grid has one, two or three vanishing points, got "
                f"{len(self.vanishing_points)} (§ 7.11)"
            )
        return self

    @model_validator(mode="after")
    def _something_has_to_be_drawn(self) -> PerspectiveConfig:
        if self.horizon is None and self.vanishing_points is None and self.verticals is None:
            raise ValueError(
                "a perspective pattern needs `vanishing_points`, `verticals` or a "
                "`horizon` — with none there is nothing to draw (§ 7.11)"
            )
        return self


class PerspectiveGenerator:
    name = "perspective"
    config_model = PerspectiveConfig

    #: § 8.3, § 7.11: there is no axis to snap to — a vanishing-point grid has a
    #: point, not a grid — so snapping is an error, said once, and the handle
    #: refuses before it computes any geometry.
    supports_snap = False

    def periodic_axes(self, cfg: PerspectiveConfig) -> dict[str, list[AxisPeriod]]:
        """None: nothing here advances along x or y by a fixed period (§ 8.3)."""
        return {}

    def is_page_invariant(self, cfg: PerspectiveConfig) -> bool:
        """Always: the grid depends on the area, never on the page (§ 10.1)."""
        return True

    def describe(self, cfg: PerspectiveConfig) -> list[str]:
        """The points, their base edges and the horizon, for the report (§ 5.3)."""
        lines: list[str] = []
        if cfg.horizon is not None:
            lines.append(f"horizon: at {cfg.horizon.at:.2f} of the height")
        for index, vp in enumerate(cfg.vanishing_points or ()):
            # The base edge is reported resolved, not as written: "farthest"
            # only means something once the area is known, and describe runs
            # before it, so name the rule and the count it will draw.
            edge = vp.base if vp.base is not None else "the farthest edge"
            lines.append(
                f"vanishing point {index + 1} at ({vp.at[0]:.2f}, {vp.at[1]:.2f}): "
                f"{vp.count} rays from {edge}"
            )
        if cfg.verticals is not None:
            lines.append(f"verticals: {cfg.verticals.count}, evenly spaced")
        return lines

    def check(self, cfg: PerspectiveConfig, *, area: Area, q: WriterQuery) -> None:
        """Refuse what only the pattern area can disprove (§ 12 point 13).

        A vanishing point can be placed, or its base edge named, such that every
        ray runs along the outside of the area and never enters it — a fan that
        draws nothing. That is knowable only against the area, so it is refused
        here, before page one, and never left as a silently empty sheet.
        """
        for index, vp in enumerate(cfg.vanishing_points or ()):
            if not any(_clip(point, foot, area) for point, foot in _rays(vp, area)):
                edge = vp.base if vp.base is not None else _base_edge(vp, area)
                raise DefinitionError(
                    f"vanishing point {index + 1} at ({vp.at[0]}, {vp.at[1]}) has no ray "
                    f"that crosses the pattern area: its base edge ({edge}) lies on the "
                    "same side as the point, so every ray runs outside it. Move the point, "
                    "or name a different `base` (§ 7.11, § 8.2)",
                    field=f"vanishing_points.{index}",
                )

    def generate(
        self,
        cfg: PerspectiveConfig,
        *,
        area: Area,
        page: PageContext,
        q: WriterQuery,
    ) -> Iterator[Mark]:
        if cfg.horizon is not None:
            y = round(cfg.horizon.at * area.height)
            yield Segment(
                start=Point(0, y),
                end=Point(area.width, y),
                weight=cfg.horizon.weight.mm,
                color=cfg.horizon.color or "#000000",
                layer=Layer.PATTERN,
            )
        for vp in cfg.vanishing_points or ():
            yield from self._fan(vp, area)
        if cfg.verticals is not None:
            yield from self._verticals(cfg.verticals, area)

    def _fan(self, vp: VanishingPoint, area: Area) -> Iterator[Segment]:
        for point, foot in _rays(vp, area):
            clipped = _clip(point, foot, area)
            if clipped is None:
                # A corner ray can graze the edge and never enter; it is simply
                # absent, not an error. `check` has already made sure at least
                # one ray of the fan survives (§ 12 point 13).
                continue
            start, end = clipped
            yield Segment(
                start=start,
                end=end,
                weight=vp.weight.mm,
                color=vp.color or "#000000",
                layer=Layer.PATTERN,
            )

    def _verticals(self, verticals: Verticals, area: Area) -> Iterator[Segment]:
        for index in range(verticals.count):
            # Equal steps across the width, both edges included — computed from
            # the exact fraction each time, never stepped, so no drift (§ 8.2).
            x = round(Fraction(index * area.width, verticals.count - 1))
            yield Segment(
                start=Point(x, 0),
                end=Point(x, area.height),
                weight=verticals.weight.mm,
                color=verticals.color or "#000000",
                layer=Layer.PATTERN,
            )


# ------------------------------------------------------------------ geometry


def _point(vp: VanishingPoint, area: Area) -> Point:
    """The vanishing point in µm — a share of the area, possibly outside it."""
    return Point(round(vp.at[0] * area.width), round(vp.at[1] * area.height))


def _base_edge(vp: VanishingPoint, area: Area) -> Edge:
    """The edge whose midpoint is farthest from the point — the foreground.

    Not a dominant-axis guess (§ 7.11 warns off arbitrary choices): the plain
    distance from the point to each edge's middle, with a fixed order breaking
    ties so the same input always resolves the same way (§ 3.3 rule 5).
    """
    point = _point(vp, area)
    midpoints: list[tuple[Edge, Point]] = [
        ("bottom", Point(area.width // 2, 0)),
        ("top", Point(area.width // 2, area.height)),
        ("left", Point(0, area.height // 2)),
        ("right", Point(area.width, area.height // 2)),
    ]
    return max(
        midpoints,
        key=lambda item: (point.x - item[1].x) ** 2 + (point.y - item[1].y) ** 2,
    )[0]


def _rays(vp: VanishingPoint, area: Area) -> list[tuple[Point, Point]]:
    """`(point, foot)` for every ray: the vanishing point and its base step.

    The base edge is cut into `count - 1` equal steps, so `count` feet fall on
    it, both corners included. Each foot is computed from its exact fraction of
    the edge, never accumulated (§ 8.2).
    """
    point = _point(vp, area)
    edge = vp.base if vp.base is not None else _base_edge(vp, area)
    steps = vp.count - 1
    feet: list[Point] = []
    for index in range(vp.count):
        along = Fraction(index, steps)
        if edge in ("bottom", "top"):
            x = round(along * area.width)
            y = 0 if edge == "bottom" else area.height
        else:
            x = 0 if edge == "left" else area.width
            y = round(along * area.height)
        feet.append(Point(x, y))
    return [(point, foot) for foot in feet]


def _clip(a: Point, b: Point, area: Area) -> tuple[Point, Point] | None:
    """The part of segment `a`–`b` inside the area, or None if it never enters.

    Liang–Barsky, in exact rationals so the two clipped ends are each rounded
    once from their true position (§ 8.2 forbids accumulated drift). A segment
    that only touches the boundary at a single point returns None: a ray of zero
    length is not a mark.
    """
    dx, dy = b.x - a.x, b.y - a.y
    limits = (
        (-dx, a.x - 0),  # left:   x >= 0
        (dx, area.width - a.x),  # right:  x <= width
        (-dy, a.y - 0),  # bottom: y >= 0
        (dy, area.height - a.y),  # top:    y <= height
    )
    t0, t1 = Fraction(0), Fraction(1)
    for p, q in limits:
        if p == 0:
            if q < 0:  # parallel to this edge and wholly outside it
                return None
            continue
        r = Fraction(q, p)
        if p < 0:
            if r > t0:
                t0 = r
        else:
            if r < t1:
                t1 = r
    if t0 >= t1:
        return None
    return (
        Point(a.x + round(t0 * dx), a.y + round(t0 * dy)),
        Point(a.x + round(t1 * dx), a.y + round(t1 * dy)),
    )
