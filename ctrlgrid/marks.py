"""The mark vocabulary — seam 2 of § 3.6, and complete from M1 on.

Six primitives, deliberately. Every primitive is work for *every* future
writer, and that bareness is what makes a foreign writer something one can
finish in an evening (§ 6). The vocabulary is contract, not a build stage: the
PDF writer may do less at first and says what it can do through
`capabilities()` (§ 10.2), but the interface never grows later.

Why exactly these six:

* `Arc` covers full circles, rings and segment arcs, and is the precondition
  for polar grids (§ 7.6) and for `mandala`, where a petal is two arcs rather
  than a path (§ 7.11). PDF, SVG and Pillow all have arcs.
* `Polygon` replaces a rectangle primitive — a rectangle is a quadrilateral,
  and hexagons, triangles and rhombi of the tiling generators come free.
* `Dot` survives next to `Arc` because dot grids are the performance-critical
  path (§ 10.1) and need their own optimisation in the writer.

Units follow § 3.3 without exception: positions and lengths are `int`
micrometres, stroke widths, diameters and opacity are `float` millimetres,
angles are degrees, mathematically positive with 0° pointing right (§ 3.5).
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import IntEnum

Um = int
"""A length in micrometres (§ 3.6)."""

Mm = float
"""A length in millimetres, for widths and sizes that never accumulate."""

Color = str
"""`#rrggbb`, six digits, RGB. No eight-digit alpha, no names, no CMYK (§ 5.3)."""


class Layer(IntEnum):
    """Paint order. The writer does not sort — marks arrive ordered (§ 3.6)."""

    PATTERN = 1  # the generator's own output
    FRAME = 2  # header, footer, border, hole marks
    OVERLAY = 3  # the stamp


@dataclass(frozen=True, slots=True)
class Point:
    """A position in micrometres, origin bottom left (§ 3.5)."""

    x: Um
    y: Um


@dataclass(frozen=True, slots=True)
class Area:
    """The pattern area in LOCAL coordinates; the origin is always (0, 0)."""

    width: Um
    height: Um


@dataclass(frozen=True, slots=True)
class Segment:
    start: Point
    end: Point
    weight: Mm = 0.1
    color: Color = "#000000"
    dash: tuple[Mm, ...] = ()
    cap: str = "butt"
    opacity: float = 1.0
    layer: Layer = Layer.PATTERN


@dataclass(frozen=True, slots=True)
class Arc:
    center: Point
    radius: Um
    start_angle: float
    sweep: float
    weight: Mm = 0.1
    color: Color = "#000000"
    dash: tuple[Mm, ...] = ()
    opacity: float = 1.0
    layer: Layer = Layer.PATTERN


@dataclass(frozen=True, slots=True)
class Dot:
    pos: Point
    diameter: Mm
    color: Color = "#000000"
    opacity: float = 1.0
    layer: Layer = Layer.PATTERN


@dataclass(frozen=True, slots=True)
class Polygon:
    points: tuple[Point, ...]
    closed: bool = True
    weight: Mm = 0.1
    color: Color = "#000000"
    fill_color: Color | None = None
    opacity: float = 1.0
    layer: Layer = Layer.PATTERN


@dataclass(frozen=True, slots=True)
class Text:
    pos: Point
    content: str
    size: Um
    family: str = "sans"
    align: str = "left"
    angle: float = 0.0
    color: Color = "#000000"
    opacity: float = 1.0
    layer: Layer = Layer.PATTERN


@dataclass(frozen=True, slots=True)
class Image:
    pos: Point
    width: Um
    height: Um
    source: str
    opacity: float = 1.0
    layer: Layer = Layer.PATTERN


Mark = Segment | Arc | Dot | Polygon | Text | Image


def translate(mark: Mark, *, dx: Um, dy: Um) -> Mark:
    """Move a mark from pattern-local into sheet coordinates.

    This is the whole of § 6's "two systems, one crossing". It lives in one
    function so that § 3.3 stays true — generators never learn the page
    geometry, because the handle does this for them on the way out.
    """
    match mark:
        case Segment():
            return replace(mark, start=_move(mark.start, dx, dy), end=_move(mark.end, dx, dy))
        case Arc():
            return replace(mark, center=_move(mark.center, dx, dy))
        case Polygon():
            return replace(mark, points=tuple(_move(p, dx, dy) for p in mark.points))
        case Dot() | Text() | Image():
            return replace(mark, pos=_move(mark.pos, dx, dy))
    raise TypeError(f"not a mark: {mark!r}")  # pragma: no cover


def _move(point: Point, dx: Um, dy: Um) -> Point:
    return Point(point.x + dx, point.y + dy)


def mirror_x(mark: Mark, *, about: Um) -> Mark:
    """Reflect a mark in the vertical line at `about / 2` (§ 7.5).

    The second crossing of § 6, and it exists for one reason: a maze solution
    printed on the back of its puzzle only lines up when it is mirrored,
    because the back of a sheet appears mirrored when held to the light.

    Text is *not* reflected — mirrored writing on the back would be the one
    thing nobody wants — only its anchor moves, and its alignment flips with
    it so a right-aligned label stays inside the same box.
    """
    def flip(point: Point) -> Point:
        return Point(about - point.x, point.y)

    match mark:
        case Segment():
            return replace(mark, start=flip(mark.start), end=flip(mark.end))
        case Arc():
            return replace(
                mark,
                center=flip(mark.center),
                start_angle=180.0 - mark.start_angle - mark.sweep,
            )
        case Polygon():
            return replace(mark, points=tuple(flip(point) for point in mark.points))
        case Dot():
            return replace(mark, pos=flip(mark.pos))
        case Image():
            return replace(mark, pos=Point(about - mark.pos.x - mark.width, mark.pos.y))
        case Text():
            flipped = {"left": "right", "right": "left", "center": "center"}[mark.align]
            return replace(mark, pos=flip(mark.pos), align=flipped)
    raise TypeError(f"not a mark: {mark!r}")  # pragma: no cover


def mirror_y(mark: Mark, *, about: Um) -> Mark:
    """Reflect a mark in the horizontal line at `about / 2` (§ 8.5).

    The vertical counterpart of `mirror_x`. It exists so a pattern can anchor at
    the top instead of the bottom: reflecting a grid about the middle of its area
    swaps which edge its cycle counts from, so the heavy origin line — and with
    it the incomplete block at the far end — moves from the bottom to the top.

    Text is *not* turned over — upside-down writing is never wanted — only its
    anchor moves. A label's horizontal alignment is unaffected, since the
    reflection is vertical.
    """
    def flip(point: Point) -> Point:
        return Point(point.x, about - point.y)

    match mark:
        case Segment():
            return replace(mark, start=flip(mark.start), end=flip(mark.end))
        case Arc():
            return replace(
                mark,
                center=flip(mark.center),
                start_angle=-mark.start_angle - mark.sweep,
            )
        case Polygon():
            return replace(mark, points=tuple(flip(point) for point in mark.points))
        case Dot():
            return replace(mark, pos=flip(mark.pos))
        case Image():
            return replace(mark, pos=Point(mark.pos.x, about - mark.pos.y - mark.height))
        case Text():
            return replace(mark, pos=flip(mark.pos))
    raise TypeError(f"not a mark: {mark!r}")  # pragma: no cover
