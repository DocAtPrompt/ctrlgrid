"""`net` — parametric box nets (§ 7.14).

Measurements in, a law computes the net: a tray or a tuck-top box from its
**inner** dimensions, cut lines solid, fold lines dashed, glue tabs computed.
It is the generator that *proves* the one promise rather than describing it — a
box 2 mm out does not close.

§ 2 rules out free strokes at chosen coordinates and allows a generator its own
law. A net is the second of those: the definition says *a tuck-top box,
80 × 50 × 30 mm, 0.3 mm card*, and every coordinate follows. There is no key
that places a panel, and there must never be one.

The geometry lives next door: `net_styles` lists the panels of a style,
`net_geometry` turns panels into cuts and creases by the one rule that an edge
two panels share is a fold. This module is the config, the fit-or-refuse, and
the marks.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Literal

from pydantic import BaseModel, ConfigDict, model_validator

from ctrlgrid.errors import DefinitionError
from ctrlgrid.generators.net_geometry import Panel, edges
from ctrlgrid.generators.net_styles import STYLES, net_panels
from ctrlgrid.marks import Area, Layer, Mark, Point, Segment, Um
from ctrlgrid.model import ColorField, LengthField, Section
from ctrlgrid.pages import PageContext
from ctrlgrid.units import Length
from ctrlgrid.writers import WriterQuery

#: Keys that only mean something for some styles (§ 5.1: a key that cannot take
#: effect where it stands is an error, not a silent no-op).
_STYLE_KEYS: dict[str, tuple[str, ...]] = {
    "tray": (),
    "tuck_top": ("tuck", "dust"),
}


class LineStyle(Section):
    """How the cuts or the creases are drawn (§ 7.14, § 2a's fold notation).

    Nothing new: the same `weight`, `color`, `style` and `dash` the rest of the
    tool uses — a valley fold is `dashed`, a mountain fold `dash: [3, 1, 1, 1]`.
    """

    weight: LengthField = Length(um=141, mm=0.1411, raw="0.4pt")
    color: ColorField = "#000000"
    style: Literal["solid", "dashed", "dotted"] = "solid"
    base_dash: LengthField = Length(um=1500, mm=1.5, raw="1.5mm")
    dash: tuple[float, ...] | None = None

    def pattern(self) -> tuple[float, ...]:
        if self.style == "solid":
            return ()
        base = self.base_dash.mm
        if self.dash is not None:
            return tuple(base * value for value in self.dash)
        return (base, base) if self.style == "dashed" else (0.0, base)


class NetConfig(BaseModel):
    """The definition section belonging to this blade (§ 3.6, seam 2)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    style: Literal["tray", "tuck_top"] = "tray"
    #: Inner dimensions — the space inside the box. The number a user has is the
    #: thing that has to go in it, so that is the number they type.
    length: LengthField
    width: LengthField
    height: LengthField
    #: The material. A panel that closes over a layer is widened by it, a flap
    #: that slides inside one is shortened by it; 0 is thin paper (§ 7.14).
    thickness: LengthField = Length(um=0, mm=0.0, raw="0mm")
    glue_tab: LengthField = Length(um=12_000, mm=12.0, raw="12mm")
    tuck: LengthField = Length(um=15_000, mm=15.0, raw="15mm")
    #: The flaps under the lid. Absent means `length / 3`, capped at 25 mm.
    dust: LengthField | None = None
    cut: LineStyle = LineStyle()
    fold: LineStyle = LineStyle(
        weight=Length(um=88, mm=0.0882, raw="0.25pt"), color="#888888", style="dashed"
    )

    @model_validator(mode="after")
    def _the_box_has_to_be_a_box(self) -> NetConfig:
        for field in ("length", "width", "height", "glue_tab"):
            value = getattr(self, field)
            if value.um <= 0:
                raise ValueError(f"`{field}` must be greater than zero, got {value.raw}")
        smallest = min(self.length.um, self.width.um, self.height.um)
        if self.thickness.um * 2 >= smallest:
            raise ValueError(
                f"a thickness of {self.thickness.raw} is half the smallest dimension or "
                "more — the walls would meet in the middle and there would be no box "
                "left (§ 7.14)"
            )
        for key in ("tuck", "dust"):
            if key in self.model_fields_set and key not in _STYLE_KEYS[self.style]:
                raise ValueError(
                    f"`{key}` belongs to a closing lid and `style: {self.style}` has "
                    f"none — it would do nothing here (§ 5.1). Styles with a lid: "
                    f"{', '.join(s for s, keys in _STYLE_KEYS.items() if key in keys)}"
                )
        return self

    def spec(self) -> dict[str, object]:
        """The style's arguments, in micrometres — seam 1 is over (§ 3.6)."""
        return {
            "length": self.length.um,
            "width": self.width.um,
            "height": self.height.um,
            "thickness": self.thickness.um,
            "glue_tab": self.glue_tab.um,
            "tuck": self.tuck.um,
            "dust": self.dust.um if self.dust is not None else None,
        }

    def panels(self) -> list[Panel]:
        return net_panels(self.style, **self.spec())


def flat_size(panels: list[Panel]) -> tuple[Um, Um]:
    """The sheet a net needs: the bounding box of every panel it has."""
    xs = [point.x for panel in panels for point in panel.points]
    ys = [point.y for panel in panels for point in panel.points]
    return max(xs) - min(xs), max(ys) - min(ys)


class NetGenerator:
    name = "net"
    config_model = NetConfig

    #: § 8.3: a net has no periodic axis — it is one figure, not a pattern.
    supports_snap = False

    def is_page_invariant(self, cfg: NetConfig) -> bool:
        """True: the net depends on its dimensions, never on the page (§ 10.1)."""
        return True

    def periodic_axes(self, cfg: NetConfig) -> dict[str, list]:
        return {}

    def describe(self, cfg: NetConfig) -> list[str]:
        panels = cfg.panels()
        cuts, folds = edges(panels)
        width, height = flat_size(panels)
        return [
            f"{cfg.style} box, inner {cfg.length.raw} x {cfg.width.raw} x {cfg.height.raw}"
            + (f", material {cfg.thickness.raw}" if cfg.thickness.um else ""),
            f"flat {width / 1000:.1f} x {height / 1000:.1f} mm, {len(panels)} panels, "
            f"{len(cuts)} cut lines, {len(folds)} creases",
        ]

    def check(self, cfg: NetConfig, *, area: Area, q: WriterQuery) -> None:
        """The one thing only the area can disprove: whether the net fits it.

        Never scaled (§ 8.2) — a net that is 96 % of itself is a box that does
        not close, which is exactly the almost-right sheet § 5.1 refuses. So the
        message carries the flat size and the area, both in millimetres.
        """
        width, height = flat_size(cfg.panels())
        if width > area.width or height > area.height:
            raise DefinitionError(
                f"the net is {width / 1000:.1f} x {height / 1000:.1f} mm flat and the "
                f"pattern area is {area.width / 1000:.1f} x {area.height / 1000:.1f} mm. "
                "A net is never scaled — a box 2 mm out does not close — so use a larger "
                "format, smaller margins or a smaller box (§ 8.2, § 7.14)",
                field="length",
            )

    def generate(
        self, cfg: NetConfig, *, area: Area, page: PageContext, q: WriterQuery
    ) -> Iterator[Mark]:
        panels = cfg.panels()
        cuts, folds = edges(panels)
        width, height = flat_size(panels)
        xs = [point.x for panel in panels for point in panel.points]
        ys = [point.y for panel in panels for point in panel.points]
        # Centred in the pattern area: a net is one figure, and a figure in a
        # corner wastes the sheet it is going to be cut out of.
        dx = (area.width - width) // 2 - min(xs)
        dy = (area.height - height) // 2 - min(ys)

        # Creases first, cuts over them: where a line is both drawn and cut the
        # cut is what the knife follows. Layer order is paint order (§ 3.6).
        for kind, line in ((folds, cfg.fold), (cuts, cfg.cut)):
            pattern = line.pattern()
            for start, end in kind:
                yield Segment(
                    start=Point(start.x + dx, start.y + dy),
                    end=Point(end.x + dx, end.y + dy),
                    weight=line.weight.mm,
                    color=line.color or "#000000",
                    dash=pattern,
                    layer=Layer.PATTERN,
                )


assert set(STYLES) == set(_STYLE_KEYS), "every style names the keys it takes"
