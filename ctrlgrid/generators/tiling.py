"""`tiling` — hexagons, triangles, rhombi, octagons (§ 7.7).

One sentence of § 7.7 decides the whole shape of this module, and it is about
drawing rather than geometry: **shared edges may only be drawn once**. A tiling
emitted as closed cells paints every inner edge twice, which is immediately
visible at low opacity and doubles the file size. So the blade yields
`Segment` marks for the edge net — deduplicated by their two endpoints — and
`Polygon` marks only where a tile is filled.

Two rules follow from what the vocabulary does *not* have (§ 6): there is no
clip and no scale, so a tile that does not fit whole is left out, and the block
of whole tiles is centred in the pattern area. § 8.2 rules out the alternative.

Every shape is described the same way: a step vector per column and per row, an
offset for odd rows or columns, and the tile's own outline. Adding a shape is
one entry in `_SHAPES` and nothing else.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Iterator
from typing import Literal

from pydantic import BaseModel, ConfigDict, model_validator

from ctrlgrid.axes import AxisPeriod
from ctrlgrid.errors import DefinitionError
from ctrlgrid.labels import labels_for
from ctrlgrid.marks import Area, Layer, Mark, Point, Polygon, Segment, Text, Um
from ctrlgrid.model import ColorField, FontSpec, LengthField, RelativeLengthField
from ctrlgrid.pages import PageContext
from ctrlgrid.units import Length
from ctrlgrid.writers import WriterQuery

ROOT3 = math.sqrt(3.0)
ROOT2 = math.sqrt(2.0)

Shape = Literal["hex", "tri", "square", "rhombus", "octagon_square"]


class Tile:
    """One tiling's arithmetic: how far cells step, and what one looks like.

    `outline(column, row)` returns the tile's vertices in local micrometres.
    Everything else — deduplicating edges, centring the block, leaving out
    tiles that do not fit — is the same for every shape and lives below.
    """

    __slots__ = ("dx", "dy", "outline", "row_offset")

    def __init__(
        self,
        *,
        dx: float,
        dy: float,
        outline: Callable[[int, int], list[tuple[float, float]]],
        row_offset: float = 0.0,
    ):
        self.dx = dx
        self.dy = dy
        self.outline = outline
        self.row_offset = row_offset


def _polygon(cx: float, cy: float, radius: float, sides: int, start: float) -> list[
    tuple[float, float]
]:
    """A regular polygon by its circumradius — the honest way to keep edges equal."""
    return [
        (
            cx + radius * math.cos(math.radians(start + index * 360 / sides)),
            cy + radius * math.sin(math.radians(start + index * 360 / sides)),
        )
        for index in range(sides)
    ]


def _tile(shape: Shape, orientation: str, size: float) -> Tile:
    """The step vectors and outline of one tiling (§ 7.7).

    `size` is always the **edge length**, for every shape, which is what makes
    `size: 8mm` mean one thing across the five of them.
    """
    if shape == "square":
        return Tile(
            dx=size,
            dy=size,
            outline=lambda column, row: [
                (column * size, row * size),
                ((column + 1) * size, row * size),
                ((column + 1) * size, (row + 1) * size),
                (column * size, (row + 1) * size),
            ],
        )

    if shape == "hex":
        if orientation == "pointy":
            # Width √3·s, height 2s, rows every 1.5s, every other row shifted
            # by half a width — the arrangement with a vertical left edge.
            width, step = ROOT3 * size, 1.5 * size
            return Tile(
                dx=width,
                dy=step,
                row_offset=width / 2,
                outline=lambda column, row: _polygon(
                    column * width + (row % 2) * width / 2 + width / 2,
                    row * step + size,
                    size,
                    6,
                    90,
                ),
            )
        width, step = 1.5 * size, ROOT3 * size
        return Tile(
            dx=width,
            dy=step,
            outline=lambda column, row: _polygon(
                column * width + size,
                row * step + (column % 2) * step / 2 + step / 2,
                size,
                6,
                0,
            ),
        )

    if shape == "tri":
        # Rows of alternating up and down triangles, half an edge apart.
        height = ROOT3 / 2 * size
        def triangle(column: int, row: int) -> list[tuple[float, float]]:
            left = column * size / 2
            bottom = row * height
            if (column + row) % 2 == 0:
                return [
                    (left, bottom),
                    (left + size, bottom),
                    (left + size / 2, bottom + height),
                ]
            return [
                (left + size / 2, bottom),
                (left + size, bottom + height),
                (left, bottom + height),
            ]

        return Tile(dx=size / 2, dy=height, outline=triangle)

    if shape == "rhombus":
        # The 60° rhombus of an isometric sheet: two triangles glued together.
        height = ROOT3 / 2 * size
        return Tile(
            dx=size,
            dy=height,
            row_offset=size / 2,
            outline=lambda column, row: [
                (column * size + (row % 2) * size / 2, row * height),
                (column * size + (row % 2) * size / 2 + size, row * height),
                (column * size + (row % 2) * size / 2 + size + size / 2, (row + 1) * height),
                (column * size + (row % 2) * size / 2 + size / 2, (row + 1) * height),
            ],
        )

    # octagon_square: regular octagons on a square grid. The square holes are
    # made *by* the octagon edges, so nothing else has to be drawn — the
    # truncated square tiling comes out of one shape.
    pitch = size * (1 + ROOT2)
    radius = size / (2 * math.sin(math.radians(22.5)))
    return Tile(
        dx=pitch,
        dy=pitch,
        outline=lambda column, row: _polygon(
            column * pitch + pitch / 2, row * pitch + pitch / 2, radius, 8, 22.5
        ),
    )


class TilingConfig(BaseModel):
    """The definition section belonging to this blade (§ 3.6, seam 2)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    shape: Shape
    #: The **edge length**, for every shape — so `size` means one thing across
    #: all five and a hexagon sheet stays comparable to a triangle one.
    size: RelativeLengthField
    orientation: Literal["pointy", "flat"] = "pointy"
    weight: LengthField = Length(um=141, mm=0.1411111111111111, raw="0.4pt")
    color: ColorField = "#333333"
    fill: Literal["none", "cycle"] = "none"
    fill_colors: list[str] | None = None
    labels: Literal["none", "coordinates"] = "none"
    font: FontSpec = FontSpec(size="7pt")

    @model_validator(mode="after")
    def _a_tile_has_an_edge(self) -> TilingConfig:
        """§ 12 point 6: a tile with no edge length is not a small tile.

        This has to be asked here and not in `check`: `_cells` divides the area
        by the step vector and runs *before* `check` does, so a zero reaches the
        user as a `ZeroDivisionError` traceback. A negative gets further still
        and is answered by `check` with "no tile fits — use a smaller size",
        advice written for the opposite problem. One question closes both, and
        on the model the loader can still name the line (§ 12).
        """
        if self.size.um <= 0:
            raise ValueError(
                f"a tile of {self.size.raw} has no edge to lay out — `size` is the edge "
                "length and must be greater than zero (§ 7.7)"
            )
        return self

    @model_validator(mode="after")
    def _keys_that_need_each_other(self) -> TilingConfig:
        if "orientation" in self.model_fields_set and self.shape != "hex":
            raise ValueError(
                f"`orientation` is a hex property (§ 7.7) and this tiling is "
                f"`{self.shape}` — pointy and flat describe which way a hexagon stands"
            )
        if self.fill == "cycle" and not self.fill_colors:
            raise ValueError(
                "`fill: cycle` needs `fill_colors` — the 2- or 3-colouring is the "
                "colouring-in case § 7.7 has it for"
            )
        return self


class TilingGenerator:
    name = "tiling"
    config_model = TilingConfig

    #: § 8.3 lists `tiling` among the blades where snapping is an error: a
    #: tiling has an edge length, not an axis period, and the two step vectors
    #: are not independent.
    supports_snap = False

    def periodic_axes(self, cfg: TilingConfig) -> dict[str, list[AxisPeriod]]:
        return {}

    def is_page_invariant(self, cfg: TilingConfig) -> bool:
        return True

    def describe(self, cfg: TilingConfig) -> list[str]:
        shape = cfg.shape if cfg.shape != "hex" else f"hex {cfg.orientation}"
        return [f"tiling: {shape}, edge {cfg.size.raw}, fill {cfg.fill}"]

    def check(self, cfg: TilingConfig, *, area: Area, q: WriterQuery) -> None:
        """§ 12 points 10 and 13: does one tile fit, and do the labels fit it?"""
        cells = _cells(cfg, area)
        if not cells:
            raise DefinitionError(
                f"not one {cfg.shape} tile of {cfg.size.raw} fits the pattern area "
                f"({_mm(area.width)} x {_mm(area.height)}). Tiles are never cut and never "
                "scaled (§ 8.2) — use a smaller size or a larger format (§ 7.7)",
                field="size",
            )
        if cfg.labels == "none":
            return

        size = cfg.font.size.um
        family = cfg.font.token
        room = _tile_width(cfg)
        for content in _coordinates(cells):
            width = q.text_width(content, family=family, size=size)
            if width > room:
                raise DefinitionError(
                    f"the tile label {content!r} is {_mm(width)} wide and a tile is "
                    f"{_mm(room)} across. A generator label is never cut (§ 8.9) — use a "
                    "larger `size` or a smaller labels font (§ 7.7)",
                    field="labels",
                )

    def generate(
        self,
        cfg: TilingConfig,
        *,
        area: Area,
        page: PageContext,
        q: WriterQuery,
    ) -> Iterator[Mark]:
        cells = _cells(cfg, area)
        if not cells:
            return

        # Fills first — the writer does not sort (§ 3.6), and a fill drawn
        # afterwards would cover the net.
        if cfg.fill == "cycle" and cfg.fill_colors:
            for index, (_column, _row, outline) in enumerate(cells):
                yield Polygon(
                    points=tuple(Point(x, y) for x, y in outline),
                    closed=True,
                    weight=0.0,
                    color=cfg.fill_colors[index % len(cfg.fill_colors)],
                    fill_color=cfg.fill_colors[index % len(cfg.fill_colors)],
                    layer=Layer.PATTERN,
                )

        if cfg.labels == "coordinates":
            yield from self._labels(cfg, cells, q)

        # § 7.7: every shared edge exactly once. Two tiles meeting produce the
        # same pair of endpoints, so the pair itself is the identity.
        seen: set[tuple[tuple[int, int], tuple[int, int]]] = set()
        for _, _, outline in cells:
            for index, start in enumerate(outline):
                end = outline[(index + 1) % len(outline)]
                key = tuple(sorted((start, end)))
                if key in seen:
                    continue
                seen.add(key)
                yield Segment(
                    start=Point(*key[0]),
                    end=Point(*key[1]),
                    weight=cfg.weight.mm,
                    color=cfg.color or "#333333",
                    layer=Layer.PATTERN,
                )

    def _labels(
        self,
        cfg: TilingConfig,
        cells: list[tuple[int, int, list[tuple[int, int]]]],
        q: WriterQuery,
    ) -> Iterator[Text]:
        size = cfg.font.size.um
        family = cfg.font.token
        ascent, _ = q.text_metrics(family=family, size=size)
        for content, (_, _, outline) in zip(_coordinates(cells), cells, strict=True):
            middle_x = sum(x for x, _ in outline) // len(outline)
            middle_y = sum(y for _, y in outline) // len(outline)
            yield Text(
                pos=Point(middle_x, middle_y - ascent // 2),
                content=content,
                size=size,
                family=family,
                align="center",
                layer=Layer.PATTERN,
            )


# --------------------------------------------------------------------- layout


def _cells(
    cfg: TilingConfig, area: Area
) -> list[tuple[int, int, list[tuple[int, int]]]]:
    """Every tile that fits *whole*, in micrometres, with the block centred.

    Nothing is clipped — the vocabulary of § 6 has no clip and § 8.2 forbids
    scaling — so a tile whose outline leaves the area is simply not there, and
    the air that leaves over is split between the two sides.
    """
    tile = _tile(cfg.shape, cfg.orientation, float(cfg.size.um))
    columns = int(area.width // tile.dx) + 2
    rows = int(area.height // tile.dy) + 2

    kept: list[tuple[int, int, list[tuple[float, float]]]] = []
    for row in range(rows):
        for column in range(columns):
            outline = tile.outline(column, row)
            if all(
                -0.5 <= x <= area.width + 0.5 and -0.5 <= y <= area.height + 0.5
                for x, y in outline
            ):
                kept.append((column, row, outline))
    if not kept:
        return []

    used = [point for _, _, outline in kept for point in outline]
    shift_x = (area.width - (max(x for x, _ in used) + min(x for x, _ in used))) / 2
    shift_y = (area.height - (max(y for _, y in used) + min(y for _, y in used))) / 2
    return [
        (
            column,
            row,
            [(round(x + shift_x), round(y + shift_y)) for x, y in outline],
        )
        for column, row, outline in kept
    ]


def _coordinates(cells: list[tuple[int, int, list[tuple[int, int]]]]) -> list[str]:
    """`A1`, `B1`, … — the column letter and the row number of each tile.

    Rows count from the top down, the way a reader counts (§ 7.10 supplies the
    two counting alphabets).
    """
    top = max(row for _, row, _ in cells)
    letters = labels_for("A", max(column for column, _, _ in cells) + 1)
    numbers = labels_for("n", top + 1)
    return [f"{letters[column]}{numbers[top - row]}" for column, row, _ in cells]


def _tile_width(cfg: TilingConfig) -> Um:
    """How much room a label has across a tile — its narrowest inner width."""
    tile = _tile(cfg.shape, cfg.orientation, float(cfg.size.um))
    outline = tile.outline(0, 0)
    width = max(x for x, _ in outline) - min(x for x, _ in outline)
    height = max(y for _, y in outline) - min(y for _, y in outline)
    return int(min(width, height))


def _mm(um: float) -> str:
    return f"{um / 1000:.1f}mm"
