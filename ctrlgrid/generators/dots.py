"""`dots` — dot grids (§ 7.2), two crossed cycles.

The positions are the cartesian product of two families, and the whole of the
blade's own thinking is about what happens *where they meet*. § 7.2 answers
that in two places rather than letting the code invent an answer:

* **`combine`** decides the size at a crossing — `max` for a cross grid,
  `product` for crossings that stand out most, `intersection_only` for emphasis
  only where both cycles agree.
* **Colour needs an axis named.** `max("#888888", "#cc0000")` means nothing and
  every mixing rule would be guessed, so a colour *cycle* without `axis` is a
  validation error, not a default.

Dots are the performance-critical path of § 10.1 — 2500 of them on a page —
which is why `Dot` survives next to `Arc` in the vocabulary at all, and why the
writer draws it as a zero-length stroke with a round cap.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, model_validator

from ctrlgrid.axes import AxisPeriod
from ctrlgrid.cycles import period_in_marks, period_um
from ctrlgrid.generators.common import (
    ONE,
    ColorField,
    CycleField,
    as_colors,
    describe_cycle,
)
from ctrlgrid.marks import Area, Dot, Layer, Mark, Point
from ctrlgrid.model import LengthField, RelativeLengthField, Section
from ctrlgrid.pages import PageContext
from ctrlgrid.units import Length
from ctrlgrid.writers import WriterQuery


class GridAxis(Section):
    """One of the two families that make the grid (§ 7.2)."""

    base_spacing: RelativeLengthField
    spacing: CycleField = ONE
    offset: RelativeLengthField = Length(um=0, mm=0.0, raw="0mm")

    @model_validator(mode="after")
    def _the_axis_advances(self) -> GridAxis:
        """§ 12 point 6, and the same guard `lines` carries on its families.

        Asked here rather than left to the cycle walk: by the time the walk
        sees it the value has travelled through `periodic_axes`, which knows
        neither the field nor the line, and § 12 wants both.
        """
        if self.base_spacing.um <= 0:
            raise ValueError(
                f"`base_spacing` is {self.base_spacing.raw} — an axis whose base is zero "
                "or less never advances and would draw every dot on the first (§ 5.3)"
            )
        return self


class Grid(Section):
    x: GridAxis
    y: GridAxis


class AxisColors(Section):
    """A colour cycle plus the axis it runs along (§ 7.2).

    `x` and `y` give colour stripes down the columns or across the rows;
    `cross` is the colour counterpart of `combine: max` — the accent appears as
    soon as the column *or* the row stands on it.
    """

    axis: Literal["x", "y", "cross"]
    cycle: ColorField


class DotsConfig(BaseModel):
    """The definition section belonging to this blade (§ 3.6, seam 2)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    grid: Grid
    base_size: LengthField = Length(um=300, mm=0.3, raw="0.3mm")
    size_x: CycleField = ONE
    size_y: CycleField = ONE
    combine: Literal["max", "product", "intersection_only"] = "max"
    color: str | AxisColors = "#000000"

    @model_validator(mode="before")
    @classmethod
    def _a_colour_cycle_has_to_name_its_axis(cls, data: Any) -> Any:
        """§ 7.2: a cycle without `axis` is an error, not a guessed default."""
        if isinstance(data, dict) and isinstance(data.get("color"), list):
            raise ValueError(
                "a colour cycle on a dot grid must say which axis it runs along — "
                "`color: { axis: x | y | cross, cycle: [...] }`. There are two cycles "
                "here and no way to mix two colours that would not be invented (§ 7.2)"
            )
        return data

    @model_validator(mode="after")
    def _a_single_colour_is_still_a_colour(self) -> DotsConfig:
        if isinstance(self.color, str):
            as_colors(self.color)
        return self


class DotsGenerator:
    name = "dots"
    config_model = DotsConfig
    supports_snap = True

    def periodic_axes(self, cfg: DotsConfig) -> dict[str, list[AxisPeriod]]:
        """Both axes: a dot grid is periodic in x and in y (§ 8.3, § 8.5)."""
        axes: dict[str, list[AxisPeriod]] = {}
        for name, axis, sizes in (
            ("x", cfg.grid.x, cfg.size_x),
            ("y", cfg.grid.y, cfg.size_y),
        ):
            marks = period_in_marks([len(axis.spacing), len(sizes)])
            axes[name] = [
                AxisPeriod(
                    step_um=axis.base_spacing.um,
                    cycle_um=period_um(
                        axis.spacing, base_um=axis.base_spacing.um, marks=marks
                    ),
                    label=f"{name} base_spacing {axis.base_spacing.raw}",
                    # One family per axis, so there is never anything to
                    # disambiguate: `governing` (§ 8.3) has no work here.
                    governing=False,
                    _spacing=axis.spacing,
                    _base_um=axis.base_spacing.um,
                    _offset_um=axis.offset.um,
                )
            ]
        return axes

    def is_page_invariant(self, cfg: DotsConfig) -> bool:
        return True

    def check(self, cfg: DotsConfig, *, area: Area, q: WriterQuery) -> None:
        """Nothing an area can disprove: every rule here is a rule about a cycle."""

    def describe(self, cfg: DotsConfig) -> list[str]:
        lines = []
        for name, axis, sizes in (
            ("x", cfg.grid.x, cfg.size_x),
            ("y", cfg.grid.y, cfg.size_y),
        ):
            marks = period_in_marks([len(axis.spacing), len(sizes)])
            length = period_um(axis.spacing, base_um=axis.base_spacing.um, marks=marks)
            lines.append(
                f"{name}: spacing {axis.base_spacing.raw} x {describe_cycle(axis.spacing)}, "
                f"size {cfg.base_size.raw} x {describe_cycle(sizes)} — repeats every "
                f"{marks} dot{'s' if marks != 1 else ''} = {length / 1000:.1f} mm"
            )
        lines.append(f"dots: combine {cfg.combine}")
        return lines

    def generate(
        self,
        cfg: DotsConfig,
        *,
        area: Area,
        page: PageContext,
        q: WriterQuery,
    ) -> Iterator[Mark]:
        columns = list(
            cfg.grid.x.spacing.positions(
                base_um=cfg.grid.x.base_spacing.um,
                extent_um=area.width,
                offset_um=cfg.grid.x.offset.um,
                field="grid.x.base_spacing",
                base_raw=cfg.grid.x.base_spacing.raw,
                pixel_dpi=page.pixel_of("x"),
            )
        )
        rows = list(
            cfg.grid.y.spacing.positions(
                base_um=cfg.grid.y.base_spacing.um,
                extent_um=area.height,
                offset_um=cfg.grid.y.offset.um,
                field="grid.y.base_spacing",
                base_raw=cfg.grid.y.base_spacing.raw,
                pixel_dpi=page.pixel_of("y"),
            )
        )
        # Rows outside, columns inside: the writer draws in the order it is
        # given (§ 3.6), and going row by row is what a viewer streams best.
        for row_index, y in rows:
            for column_index, x in columns:
                yield Dot(
                    pos=Point(x, y),
                    diameter=self._size(cfg, column_index, row_index),
                    color=self._color(cfg, column_index, row_index),
                    layer=Layer.PATTERN,
                )

    def _size(self, cfg: DotsConfig, column: int, row: int) -> float:
        """§ 7.2's `combine`, one line per mode and no fourth reading."""
        across = float(cfg.size_x.at(column))
        down = float(cfg.size_y.at(row))
        factor = {
            "max": max(across, down),
            "product": across * down,
            # "only where both cycles are emphasised": the smaller of the two
            # decides, so a lone emphasised column stays plain.
            "intersection_only": min(across, down),
        }[cfg.combine]
        return cfg.base_size.mm * factor

    def _color(self, cfg: DotsConfig, column: int, row: int) -> str:
        if isinstance(cfg.color, str):
            return cfg.color
        cycle = cfg.color.cycle
        if cfg.color.axis == "x":
            index = column
        elif cfg.color.axis == "y":
            index = row
        else:
            # `cross`: the accent as soon as either axis stands on it. Later in
            # the cycle is more emphasised — the convention every preset uses,
            # `[grid, grid, grid, grid, accent]`.
            index = max(column % len(cycle), row % len(cycle))
        return cycle[index % len(cycle)]
