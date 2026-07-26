"""`grid` — labelled cell blocks (§ 7.4): battleship, score sheets, bingo.

**Count-driven, not spacing-driven.** Everywhere else in this tool you say
5 mm and the sheet holds as many as it holds. Here you say ten by ten and the
cells take their size from the pattern area — which is why § 12 point 10 makes
"count-driven content fits the pattern area" a pre-flight check of its own.

**Exactly one block per page, centred** (§ 7.4). Several positioned blocks
would be a layout system through the back door, and § 2 rules that out.

Two consequences of those two sentences together:

* **Cells come out square.** The cell size is the smaller of the two the area
  allows, and the leftover becomes air around the block. Filling the area
  outright would stretch the cells, which § 8.2 forbids — and it would make
  "centred" a word with nothing behind it.
* **Labels take their room out of the area first**, before the cells are
  measured, exactly as a header band does in § 8.1. Written over the block
  afterwards they would sit on the lines.

Shared edges are drawn once. § 7.7 says it for tilings and it holds here: a
grid emitted as closed cells draws every inner edge twice, which shows at low
opacity and doubles the file size.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ctrlgrid.axes import AxisPeriod
from ctrlgrid.errors import DefinitionError
from ctrlgrid.labels import labels_for
from ctrlgrid.marks import Area, Layer, Mark, Point, Polygon, Segment, Text, Um
from ctrlgrid.model import ColorField, FontSpec, LengthField, Section
from ctrlgrid.pages import PageContext
from ctrlgrid.units import Length
from ctrlgrid.writers import WriterQuery

#: Air between a label and the block it names. A share of the font size rather
#: than a millimetre figure, so the gutter follows the labels when they grow.
LABEL_GAP = 0.4


class Cells(Section):
    x: int = Field(ge=1)
    y: int = Field(ge=1)


class GridLabels(Section):
    """Counting patterns for the two edges (§ 7.10)."""

    columns: str | list[object] | None = None
    rows: str | list[object] | None = None


class GridConfig(BaseModel):
    """The definition section belonging to this blade (§ 3.6, seam 2)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    cells: Cells
    labels: GridLabels | None = None
    weight: LengthField = Length(um=105, mm=0.10583333333333333, raw="0.3pt")
    color: ColorField = "#000000"
    fill: Literal["none", "checker", "rows", "columns"] = "none"
    fill_color: ColorField = "#eeeeee"
    #: § 7.4 names the key and nothing more: the top row is marked off by a
    #: heavier rule beneath it, which is what a score sheet needs it for.
    header_row: bool = False
    font: FontSpec = FontSpec(size="8pt")

    @model_validator(mode="before")
    @classmethod
    def _labels_none_is_the_documented_spelling(cls, data: Any) -> Any:
        """§ 7.10: "`labels: none` unterdrückt die Beschriftung ganz."

        Leaving the key out has always done that, but the spelling the
        specification documents met pydantic's "Input should be a valid
        dictionary or instance of ...LabelS" — an internal class name in answer
        to a definition copied out of § 7.10. `none` is one of the keywords
        § 5.1 lists as standing where a value could, so it is accepted here and
        means exactly what an absent key means.
        """
        if isinstance(data, dict) and data.get("labels") == "none":
            data = {key: value for key, value in data.items() if key != "labels"}
        return data
class GridGenerator:
    name = "grid"
    config_model = GridConfig

    #: § 8.3 lists `grid` among the blades where snapping is an error: the
    #: block has a cell count, not a period, and there is nothing to snap to.
    supports_snap = False

    def periodic_axes(self, cfg: GridConfig) -> dict[str, list[AxisPeriod]]:
        return {}

    def is_page_invariant(self, cfg: GridConfig) -> bool:
        return True

    def describe(self, cfg: GridConfig) -> list[str]:
        return [
            f"grid: {cfg.cells.x} x {cfg.cells.y} cells, square, centred in the "
            f"pattern area — fill {cfg.fill}"
        ]

    def check(self, cfg: GridConfig, *, area: Area, q: WriterQuery) -> None:
        """Labels are measured before page one (§ 10.2, § 12 points 10 and 13).

        A grid label that does not fit its cell is an error and never a
        truncation: § 8.9 withholds `cut` from generator labels because `A…`
        instead of `A10` is worthless.
        """
        block = _block(cfg, area, q)
        if block.cell <= 0:
            raise DefinitionError(
                f"{cfg.cells.x} x {cfg.cells.y} cells do not fit the pattern area "
                f"({_mm(area.width)} x {_mm(area.height)}) once the labels have their "
                "room. Use fewer cells, a larger format or a smaller label font "
                "(§ 7.4, § 12 point 10)",
                field="cells",
            )

        size = cfg.font.size.um
        family = cfg.font.token
        for content in _edge_labels(cfg, "columns"):
            width = q.text_width(content, family=family, size=size)
            if width > block.cell:
                raise DefinitionError(
                    f"the column label {content!r} is {_mm(width)} wide and a cell is "
                    f"{_mm(block.cell)}. A grid label is never cut — `A…` instead of "
                    "`A10` is worthless (§ 8.9) — so use fewer cells or a smaller "
                    "labels font (§ 7.4)",
                    field="labels.columns",
                )
        for content in _edge_labels(cfg, "rows"):
            width = q.text_width(content, family=family, size=size)
            if width > block.left:
                raise DefinitionError(
                    f"the row label {content!r} is {_mm(width)} wide and only "
                    f"{_mm(block.left)} is left of the block. Widen the pattern area or "
                    "use a smaller labels font (§ 7.4)",
                    field="labels.rows",
                )

    def generate(
        self,
        cfg: GridConfig,
        *,
        area: Area,
        page: PageContext,
        q: WriterQuery,
    ) -> Iterator[Mark]:
        block = _block(cfg, area, q)
        # Fills first: the writer does not sort (§ 3.6), so what arrives first
        # is underneath, and a fill drawn afterwards would cover the lines.
        yield from self._fills(cfg, block)
        yield from self._lines(cfg, block)
        yield from self._labels(cfg, block, q)

    def _fills(self, cfg: GridConfig, block: _Block) -> Iterator[Polygon]:
        if cfg.fill == "none":
            return
        for row in range(cfg.cells.y):
            for column in range(cfg.cells.x):
                if not _is_filled(cfg.fill, column, row):
                    continue
                left = block.x(column)
                bottom = block.y(row)
                yield Polygon(
                    points=(
                        Point(left, bottom),
                        Point(left + block.cell, bottom),
                        Point(left + block.cell, bottom + block.cell),
                        Point(left, bottom + block.cell),
                    ),
                    closed=True,
                    weight=0.0,
                    color=cfg.fill_color or "#eeeeee",
                    fill_color=cfg.fill_color or "#eeeeee",
                    layer=Layer.PATTERN,
                )

    def _lines(self, cfg: GridConfig, block: _Block) -> Iterator[Segment]:
        weight = cfg.weight.mm
        color = cfg.color or "#000000"
        top = block.y(cfg.cells.y)
        right = block.x(cfg.cells.x)
        # The rule under the header row, when there is one: the same line, at
        # double weight, so the top row reads as a heading (§ 7.4).
        header = block.y(cfg.cells.y - 1) if cfg.header_row else None

        for column in range(cfg.cells.x + 1):
            x = block.x(column)
            yield Segment(
                start=Point(x, block.bottom),
                end=Point(x, top),
                weight=weight,
                color=color,
                layer=Layer.PATTERN,
            )
        for row in range(cfg.cells.y + 1):
            y = block.y(row)
            yield Segment(
                start=Point(block.left, y),
                end=Point(right, y),
                weight=weight * (2 if y == header else 1),
                color=color,
                layer=Layer.PATTERN,
            )

    def _labels(self, cfg: GridConfig, block: _Block, q: WriterQuery) -> Iterator[Text]:
        size = cfg.font.size.um
        family = cfg.font.token
        ascent, descent = q.text_metrics(family=family, size=size)
        gap = int(size * LABEL_GAP)

        for column, content in enumerate(_edge_labels(cfg, "columns")):
            yield Text(
                pos=Point(block.x(column) + block.cell // 2, block.top + gap + descent),
                content=content,
                size=size,
                family=family,
                align="center",
                layer=Layer.PATTERN,
            )
        # Rows are numbered from the top down: "1" is the first row of the
        # block as it is read, not the first one drawn (§ 7.10 counts, and a
        # reader counts downwards).
        for index, content in enumerate(_edge_labels(cfg, "rows")):
            row = cfg.cells.y - 1 - index
            middle = block.y(row) + block.cell // 2
            yield Text(
                pos=Point(block.left - gap, middle - ascent // 2),
                content=content,
                size=size,
                family=family,
                align="right",
                layer=Layer.PATTERN,
            )


# --------------------------------------------------------------------- layout


class _Block:
    """Where the block sits and how big a cell is — computed once, used twice."""

    __slots__ = ("bottom", "cell", "left", "top")

    def __init__(self, left: Um, bottom: Um, cell: Um, cells: Cells):
        self.left = left
        self.bottom = bottom
        self.cell = cell
        self.top = bottom + cell * cells.y

    def x(self, column: int) -> Um:
        return self.left + self.cell * column

    def y(self, row: int) -> Um:
        return self.bottom + self.cell * row


def _block(cfg: GridConfig, area: Area, q: WriterQuery) -> _Block:
    """The label gutters come off first, then the cells divide what is left.

    The same order § 8.1 uses for header and footer: fixed furniture first, the
    pattern area is what remains. Labels that took their room afterwards would
    be printed over the block.
    """
    size = cfg.font.size.um
    ascent, descent = q.text_metrics(family=cfg.font.token, size=size)
    gap = int(size * LABEL_GAP)

    top_gutter = ascent + descent + gap if _edge_labels(cfg, "columns") else 0
    left_gutter = (
        max(
            (q.text_width(content, family=cfg.font.token, size=size)
             for content in _edge_labels(cfg, "rows")),
            default=0,
        )
        + gap
        if _edge_labels(cfg, "rows")
        else 0
    )

    width = area.width - left_gutter
    height = area.height - top_gutter
    cell = min(width // cfg.cells.x, height // cfg.cells.y)

    # Centred in what is left, which is what makes a square cell possible at
    # all: the surplus of the longer axis becomes air, never stretch (§ 8.2).
    block_width = cell * cfg.cells.x
    block_height = cell * cfg.cells.y
    return _Block(
        left=left_gutter + (width - block_width) // 2,
        bottom=(height - block_height) // 2,
        cell=cell,
        cells=cfg.cells,
    )


def _edge_labels(cfg: GridConfig, edge: str) -> list[str]:
    if cfg.labels is None:
        return []
    pattern = getattr(cfg.labels, edge)
    count = cfg.cells.x if edge == "columns" else cfg.cells.y
    return labels_for(pattern, count, field=f"labels.{edge}")


def _is_filled(fill: str, column: int, row: int) -> bool:
    if fill == "checker":
        return (column + row) % 2 == 0
    if fill == "rows":
        return row % 2 == 0
    return column % 2 == 0


def _mm(um: Um) -> str:
    return f"{um / 1000:.1f}mm"
