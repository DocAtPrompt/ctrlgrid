"""`staves` — music and tablature paper (§ 7.3).

Internally a grouped line family: `count` systems of `lines` lines each, with
`system_gap` between them. Three of § 7.3's decisions do the shaping.

**Two ways of saying the same size, and they exclude each other.**
`stave_space` is the distance between neighbouring lines, `stave_height` the
span from top line to bottom line, and they convert by `lines − 1` — *not* by
four, because tablature has six lines. Both at once is an error.

**`system_gap` is the gap, not the pitch.** Measured from the bottom line of
one system to the top line of the next, which makes it independent of `lines`:
switching a sheet from notation to tablature must not change how far apart the
systems look. The name is deliberately not `stave_spacing`, which differs from
`stave_space` by three letters and means something else entirely.

**`sp` is a generator-local unit** (§ 5.1). It means stave spaces, it is
resolved here once `stave_space` is known, and it exists because a system gap
written in stave spaces keeps the sheet proportioned at every stave size.

Clefs are refused, and the reason is in `_CLEF_REFUSAL` — see there.
"""

from __future__ import annotations

from collections.abc import Iterator
from decimal import Decimal, InvalidOperation
from typing import Annotated, Any, Literal

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, model_validator

from ctrlgrid.axes import AxisPeriod
from ctrlgrid.errors import DefinitionError
from ctrlgrid.marks import Area, Layer, Mark, Point, Segment, Um
from ctrlgrid.model import ColorField, LengthField
from ctrlgrid.pages import PageContext
from ctrlgrid.units import Length, parse_length
from ctrlgrid.writers import WriterQuery

#: The § 7.3-against-§ 6 conflict is now decided (§ 15.3): a clef is a `Text`
#: mark in an embedded, subset music font — not a seventh primitive and not a
#: vector path, so § 6 and § 15.2 stay untouched, and the PDF stays
#: self-contained through embedding rather than font-freeness. That is real
#: work, scheduled as M9 (§ 14), so this now refuses like every other unbuilt
#: option: by naming its milestone, not an open question (§ 5.1).
_CLEF_REFUSAL = (
    "clef {value!r} is not drawn yet: it arrives with M9 (§ 7.3, § 15.3), which renders "
    "clefs as text from an embedded music font. The mark vocabulary of § 6 has no curve "
    "path, so a clef is never approximated from polygons — a sheet that is almost right is "
    "the worst failure class there is (§ 5.1). Use clef: none until then, and write the "
    "clef by hand"
)


class StaveLength:
    """A length that may be written in `sp`, resolved once the size is known."""

    __slots__ = ("length", "spaces")

    def __init__(self, length: Length | None = None, spaces: Decimal | None = None):
        self.length = length
        self.spaces = spaces

    def um(self, stave_space: Um) -> Um:
        if self.length is not None:
            return self.length.um
        return int(Decimal(stave_space) * (self.spaces or Decimal(0)))

    @property
    def raw(self) -> str:
        return self.length.raw if self.length is not None else f"{self.spaces}sp"


def _as_stave_length(value: Any) -> Any:
    """Accept `4sp` here and nowhere else (§ 5.1, § 7.3)."""
    if isinstance(value, StaveLength):
        return value
    if isinstance(value, str) and value.strip().endswith("sp"):
        text = value.strip()[:-2].strip()
        try:
            return StaveLength(spaces=Decimal(text))
        except InvalidOperation:
            raise ValueError(f"`sp` takes a number, got {value!r} (§ 7.3)") from None
    try:
        return StaveLength(length=parse_length(value))
    except DefinitionError as error:
        raise ValueError(error.message) from None


StaveLengthField = Annotated[StaveLength, BeforeValidator(_as_stave_length)]


class StavesConfig(BaseModel):
    """The definition section belonging to this blade (§ 3.6, seam 2)."""

    model_config = ConfigDict(extra="forbid", frozen=True, arbitrary_types_allowed=True)

    count: int = Field(ge=1)
    lines: int = Field(default=5, ge=2)
    stave_space: LengthField | None = None
    stave_height: LengthField | None = None
    system_gap: StaveLengthField = StaveLength(spaces=Decimal(4))
    weight: LengthField = Length(um=70, mm=0.07055555555555555, raw="0.2pt")
    color: ColorField = "#000000"
    clef: Literal["none"] = "none"
    clef_indent: StaveLengthField = StaveLength(length=Length(um=3000, mm=3.0, raw="3mm"))

    @model_validator(mode="before")
    @classmethod
    def _a_named_clef_says_why_it_cannot_be_drawn(cls, data: Any) -> Any:
        if isinstance(data, dict) and data.get("clef") not in (None, "none"):
            raise ValueError(_CLEF_REFUSAL.format(value=data["clef"]))
        return data

    @model_validator(mode="after")
    def _exactly_one_way_of_saying_the_size(self) -> StavesConfig:
        """§ 7.3: the two are the same measure said differently, so both is an error."""
        if self.stave_space is not None and self.stave_height is not None:
            raise ValueError(
                f"stave_space ({self.stave_space.raw}) and stave_height "
                f"({self.stave_height.raw}) are two ways of saying one size and exclude "
                f"each other: stave_space = stave_height / (lines - 1) (§ 7.3)"
            )
        if self.stave_space is None and self.stave_height is None:
            raise ValueError(
                "a stave needs its size: `stave_space` (distance between neighbouring "
                "lines) or `stave_height` (top line to bottom line) — § 7.3"
            )
        return self

    @property
    def space_um(self) -> Um:
        """The distance between neighbouring lines, whichever way it was given.

        The divisor is `lines - 1` and not four: with `lines: 6` — tablature —
        a 7 mm span makes 1.4 mm steps, not 1.75 mm (§ 7.3).
        """
        if self.stave_space is not None:
            return self.stave_space.um
        assert self.stave_height is not None
        return round(self.stave_height.um / (self.lines - 1))

    @property
    def system_um(self) -> Um:
        """Top line to bottom line of one system."""
        return self.space_um * (self.lines - 1)

    def block_um(self) -> Um:
        """What all the systems together need, gaps included."""
        gap = self.system_gap.um(self.space_um)
        return self.count * self.system_um + (self.count - 1) * gap


class StavesGenerator:
    name = "staves"
    config_model = StavesConfig

    #: § 8.3 lists `staves` among the blades where snapping is an error: a
    #: system is a group, not a period, and snapping to a stave space would
    #: cut a system in half.
    supports_snap = False

    def periodic_axes(self, cfg: StavesConfig) -> dict[str, list[AxisPeriod]]:
        return {}

    def is_page_invariant(self, cfg: StavesConfig) -> bool:
        return True

    def describe(self, cfg: StavesConfig) -> list[str]:
        return [
            f"staves: {cfg.count} systems of {cfg.lines} lines, stave_space "
            f"{cfg.space_um / 1000:.2f}mm, system height {cfg.system_um / 1000:.1f}mm, "
            f"gap {cfg.system_gap.raw} — {cfg.block_um() / 1000:.1f} mm in all"
        ]

    def check(self, cfg: StavesConfig, *, area: Area, q: WriterQuery) -> None:
        """§ 12 point 10: count-driven content has to fit, and is never squeezed."""
        needed = cfg.block_um()
        if needed > area.height:
            gap = cfg.system_gap.um(cfg.space_um)
            raise DefinitionError(
                f"{cfg.count} systems need {_mm(needed)} of height and the pattern area "
                f"is {_mm(area.height)}:\n"
                f"  {cfg.count} x system   {_mm(cfg.count * cfg.system_um):>10}\n"
                f"  {cfg.count - 1} x gap      {_mm((cfg.count - 1) * gap):>10}\n"
                f"  = needed       {_mm(needed):>10}\n"
                "Nothing is compressed to fit (§ 8.2): use fewer systems, a smaller "
                "stave_space or a smaller system_gap",
                field="count",
            )

    def generate(
        self,
        cfg: StavesConfig,
        *,
        area: Area,
        page: PageContext,
        q: WriterQuery,
    ) -> Iterator[Mark]:
        space = cfg.space_um
        gap = cfg.system_gap.um(space)
        # Music is read from the top down, so that is where the sheet fills;
        # whatever is left over stays at the bottom, where a page of music
        # normally has room for a note about it.
        top = area.height
        for system in range(cfg.count):
            first = top - system * (cfg.system_um + gap)
            for line in range(cfg.lines):
                y = first - line * space
                yield Segment(
                    start=Point(0, y),
                    end=Point(area.width, y),
                    weight=cfg.weight.mm,
                    color=cfg.color or "#000000",
                    layer=Layer.PATTERN,
                )


def _mm(um: Um) -> str:
    return f"{um / 1000:.1f}mm"
