"""`form` — fillable forms (§ 7.8): phone logs, checklists, handover sheets.

**Rows first, then columns.** Not a global raster like CSS Grid but a sequence
of rows, each with its own column split, because that is how forms are thought
and described: "three fields across the top, a wide note area under them". A
global column raster forces the common denominator — three equal fields over a
25/50/25 row would need twelve columns and spans of 4/4/4 and 3/6/3, which is
technically possible and unreadable, and the presets are documentation (§ 9.3).

**Nesting is exactly one level deep.** A column may hold rows, which covers a
tall field beside two short ones and every form anybody fills in by hand.
Deeper would be a general layout language, and § 2 rules that out.

**The raster is relative, the ruling is absolute.** Row and column measures
divide the room available; `line_spacing: 8mm` means 8 mm and the number of
lines follows from what fits. The other way round would be a stretched grid
(§ 8.2) — and it is what keeps one definition usable on A4 and A5 alike: the
fields change size, the writing lines do not.

This is also the first blade whose **layout** depends on text metrics rather
than only its checks: a title decides how much room is left for the writing
area beneath it, so § 10.2's query API is a precondition and not a nicety.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ctrlgrid.axes import AxisPeriod
from ctrlgrid.errors import DefinitionError
from ctrlgrid.marks import Area, Layer, Mark, Point, Polygon, Segment, Text, Um
from ctrlgrid.model import ColorField, FontSpec, LengthField, Section
from ctrlgrid.pages import PageContext, resolve_placeholders
from ctrlgrid.units import Length, parse_length
from ctrlgrid.writers import WriterQuery

#: Air between a field's border and what stands inside it, as a share of the
#: title size — so the padding follows the type rather than a fixed millimetre.
PADDING = 0.5

#: A tick box, as a share of the title font size (§ 7.8), overridable per field.
BOX_SIZE = 1.0

REST = "rest"


def _as_measure(value: Any) -> Any:
    """`20%`, `40mm`, `rest`, or nothing at all (§ 7.8)."""
    if value is None or isinstance(value, Measure):
        return value
    text = str(value).strip()
    if text == REST:
        return Measure(rest=True)
    if text.endswith("%"):
        try:
            return Measure(share=float(text[:-1]))
        except ValueError:
            raise ValueError(f"{value!r} is not a percentage (§ 7.8)") from None
    try:
        return Measure(length=parse_length(text))
    except DefinitionError as error:
        raise ValueError(
            f"{error.message} — a row or column measure is `20%`, `40mm`, `rest`, "
            "or left out for an equal share (§ 7.8)"
        ) from None


@dataclass(frozen=True, slots=True)
class Measure:
    """One of the four ways § 7.8 lets a row or column be sized."""

    length: Length | None = None
    share: float | None = None
    rest: bool = False

    @property
    def raw(self) -> str:
        if self.length is not None:
            return self.length.raw
        return f"{self.share:g}%" if self.share is not None else REST


class Field_(Section):
    """One cell: a field, or a nest of rows (§ 7.8) — never both."""

    title: str | None = None
    kind: Literal["text", "check", "choice"] = "text"
    options: list[str] | None = None
    width: Any = None
    line_spacing: LengthField | None = None
    lines: int | None = Field(default=None, ge=1)
    box_size: LengthField | None = None
    rows: list[Row] | None = None

    @model_validator(mode="before")
    @classmethod
    def _parse_the_measure(cls, data: Any) -> Any:
        if isinstance(data, dict) and "width" in data:
            data = {**data, "width": _as_measure(data["width"])}
        return data

    @model_validator(mode="after")
    def _a_field_or_a_nest(self) -> Field_:
        if self.rows is not None and (self.title is not None or self.options):
            raise ValueError(
                "a column either holds a field or holds rows, not both — nesting is "
                "how a tall field stands beside two short ones (§ 7.8)"
            )
        if self.kind == "choice" and not self.options:
            raise ValueError(
                "`kind: choice` needs `options`: the labels belong to the language of "
                "the form and therefore to the definition, never to the tool (§ 7.8)"
            )
        if self.kind != "choice" and self.options:
            raise ValueError(
                f"`options` only means something with `kind: choice`, and this field is "
                f"`{self.kind}` (§ 5.1, § 7.8)"
            )
        return self


class Row(Section):
    height: Any = None
    columns: list[Field_] = Field(min_length=1)

    @model_validator(mode="before")
    @classmethod
    def _parse_the_measure(cls, data: Any) -> Any:
        if isinstance(data, dict) and "height" in data:
            data = {**data, "height": _as_measure(data["height"])}
        return data


class TitleSpec(Section):
    font: FontSpec = FontSpec(size="7pt")
    position: Literal["above", "inline", "none"] = "above"


class FormConfig(BaseModel):
    """The definition section belonging to this blade (§ 3.6, seam 2)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    rows: list[Row] = Field(min_length=1)
    gap: LengthField = Length(um=2000, mm=2.0, raw="2mm")
    weight: LengthField = Length(um=105, mm=0.10583333333333333, raw="0.3pt")
    color: ColorField = "#000000"
    title: TitleSpec = TitleSpec()

    @model_validator(mode="after")
    def _nesting_stops_at_one_level(self) -> FormConfig:
        """§ 7.8, and § 2 behind it: no general layout language."""
        for row in self.rows:
            for column in row.columns:
                for nested in column.rows or ():
                    for inner in nested.columns:
                        if inner.rows is not None:
                            raise ValueError(
                                "nesting goes exactly one level deep (§ 7.8): a column "
                                "may hold rows, and those rows hold fields. Deeper than "
                                "that would be a layout language, which § 2 rules out"
                            )
        return self


@dataclass(frozen=True, slots=True)
class Cell:
    """A placed field: where it is, and what it holds."""

    field: Field_
    left: Um
    bottom: Um
    width: Um
    height: Um


class FormGenerator:
    name = "form"
    config_model = FormConfig

    #: § 8.3 lists `form` among the blades where snapping is an error: the
    #: raster divides the area, it does not step through it.
    supports_snap = False

    def periodic_axes(self, cfg: FormConfig) -> dict[str, list[AxisPeriod]]:
        return {}

    def is_page_invariant(self, cfg: FormConfig) -> bool:
        """True while no field title holds a placeholder (§ 7.8, § 8.10)."""
        return not any(
            "{" in (field.title or "")
            for row in cfg.rows
            for column in row.columns
            for field in [column, *(inner for nested in (column.rows or ())
                                   for inner in nested.columns)]
        )

    def describe(self, cfg: FormConfig) -> list[str]:
        fields = sum(len(row.columns) for row in cfg.rows)
        return [
            f"form: {len(cfg.rows)} rows, {fields} fields, gap {cfg.gap.raw}, titles "
            f"{cfg.title.position}"
        ]

    def check(self, cfg: FormConfig, *, area: Area, q: WriterQuery) -> None:
        """Lay the whole form out and measure every title (§ 12 point 13).

        The layout runs here in full, so a form that does not fit is refused
        before page one rather than half way through the file — and it is the
        same code `generate` uses, so the two cannot disagree.
        """
        for cell in _place(cfg, area):
            _measure_field(cfg, cell, q)

    def generate(
        self,
        cfg: FormConfig,
        *,
        area: Area,
        page: PageContext,
        q: WriterQuery,
    ) -> Iterator[Mark]:
        for cell in _place(cfg, area):
            yield from self._field(cfg, cell, page, q)

    def _field(
        self, cfg: FormConfig, cell: Cell, page: PageContext, q: WriterQuery
    ) -> Iterator[Mark]:
        yield Polygon(
            points=(
                Point(cell.left, cell.bottom),
                Point(cell.left + cell.width, cell.bottom),
                Point(cell.left + cell.width, cell.bottom + cell.height),
                Point(cell.left, cell.bottom + cell.height),
            ),
            closed=True,
            weight=cfg.weight.mm,
            color=cfg.color or "#000000",
            fill_color=None,
            layer=Layer.PATTERN,
        )

        size = cfg.title.font.size.um
        family = cfg.title.font.token
        padding = int(size * PADDING)
        ascent, descent = q.text_metrics(family=family, size=size)
        title = _title_of(cell.field, page)

        top = cell.bottom + cell.height - padding - ascent
        if title and cfg.title.position != "none":
            yield Text(
                pos=Point(cell.left + padding, top),
                content=title,
                size=size,
                family=family,
                layer=Layer.PATTERN,
            )

        # Below the title when it stands above, beside it when it is inline —
        # § 7.8 puts the boxes and the writing area either way.
        used = (ascent + descent + padding) if (title and cfg.title.position == "above") else 0
        inner_top = cell.bottom + cell.height - padding - used
        inner_left = cell.left + padding
        if title and cfg.title.position == "inline":
            inner_left += q.text_width(title, family=family, size=size) + padding

        if cell.field.kind in ("check", "choice"):
            yield from self._boxes(cfg, cell, inner_left, inner_top, q)
        elif cell.field.line_spacing is not None:
            yield from self._ruling(cfg, cell, inner_top)

    def _boxes(
        self, cfg: FormConfig, cell: Cell, left: Um, top: Um, q: WriterQuery
    ) -> Iterator[Mark]:
        """Box before label, in the order of the definition (§ 7.8).

        An empty box and nothing else: there is no pre-selection and no
        exclusivity — on paper the pen decides, and `choice` describes the
        offer rather than a rule.
        """
        size = cfg.title.font.size.um
        family = cfg.title.font.token
        box = cell.field.box_size.um if cell.field.box_size else int(size * BOX_SIZE)
        gap = int(size * PADDING)
        options = cell.field.options or [""]

        x, y = left, top - box
        for option in options:
            label = q.text_width(option, family=family, size=size) if option else 0
            needed = box + (gap + label if option else 0)
            if x + needed > cell.left + cell.width - gap and x > left:
                # § 7.8: wrap to the next line when the row of options runs out
                # of width. Whether even one line fits is settled in `check`.
                x, y = left, y - box - gap
            yield Polygon(
                points=(
                    Point(x, y),
                    Point(x + box, y),
                    Point(x + box, y + box),
                    Point(x, y + box),
                ),
                closed=True,
                weight=cfg.weight.mm,
                color=cfg.color or "#000000",
                fill_color=None,
                layer=Layer.PATTERN,
            )
            if option:
                ascent, _ = q.text_metrics(family=family, size=size)
                yield Text(
                    pos=Point(x + box + gap, y + (box - ascent) // 2 + ascent // 8),
                    content=option,
                    size=size,
                    family=family,
                    layer=Layer.PATTERN,
                )
            x += needed + gap * 2

    def _ruling(self, cfg: FormConfig, cell: Cell, top: Um) -> Iterator[Segment]:
        """Writing lines, absolute (§ 7.8) — the point of the whole section."""
        spacing = cell.field.line_spacing
        assert spacing is not None
        padding = int(cfg.title.font.size.um * PADDING)
        for index in range(_line_count(cfg, cell, top)):
            y = top - (index + 1) * spacing.um
            yield Segment(
                start=Point(cell.left + padding, y),
                end=Point(cell.left + cell.width - padding, y),
                weight=cfg.weight.mm,
                color=cfg.color or "#000000",
                layer=Layer.PATTERN,
            )


# --------------------------------------------------------------------- layout


def _place(cfg: FormConfig, area: Area) -> list[Cell]:
    """Every field of the form, placed — rows first, then columns (§ 7.8)."""
    cells: list[Cell] = []
    heights = _share(
        [row.height for row in cfg.rows], area.height, cfg.gap.um, "height", "rows"
    )
    top = area.height
    for row, height in zip(cfg.rows, heights, strict=True):
        widths = _share(
            [column.width for column in row.columns],
            area.width,
            cfg.gap.um,
            "width",
            "columns",
        )
        left = 0
        for column, width in zip(row.columns, widths, strict=True):
            if column.rows is None:
                cells.append(
                    Cell(field=column, left=left, bottom=top - height,
                         width=width, height=height)
                )
            else:
                # One level of nesting: the same routine inside the column.
                inner_heights = _share(
                    [nested.height for nested in column.rows],
                    height,
                    cfg.gap.um,
                    "height",
                    "rows",
                )
                inner_top = top
                for nested, inner_height in zip(column.rows, inner_heights, strict=True):
                    inner_widths = _share(
                        [field.width for field in nested.columns],
                        width,
                        cfg.gap.um,
                        "width",
                        "columns",
                    )
                    inner_left = left
                    for field, inner_width in zip(
                        nested.columns, inner_widths, strict=True
                    ):
                        cells.append(
                            Cell(
                                field=field,
                                left=inner_left,
                                bottom=inner_top - inner_height,
                                width=inner_width,
                                height=inner_height,
                            )
                        )
                        inner_left += inner_width + cfg.gap.um
                    inner_top -= inner_height + cfg.gap.um
            left += width + cfg.gap.um
        top -= height + cfg.gap.um
    return cells


def _share(
    measures: list[Measure | None], total: Um, gap: Um, what: str, of: str
) -> list[Um]:
    """Divide `total` among the measures of § 7.8, gaps taken off first.

    "Available" means after every gap — otherwise several percentages together
    would come to more than the sheet. `rest` and a measure left out are the
    same rule: both take what remains and share it equally; `rest` is only the
    written form of it, and § 7.8 makes the unwritten one the default because
    it is the commonest case by far.
    """
    available = total - gap * (len(measures) - 1)
    if available <= 0:
        raise DefinitionError(
            f"the gaps alone take {_mm(gap * (len(measures) - 1))} of "
            f"{_mm(total)} — there is no room left for {len(measures)} {of} (§ 7.8)",
            field="gap",
        )

    fixed: dict[int, Um] = {}
    for index, measure in enumerate(measures):
        if measure is None or measure.rest:
            continue
        if measure.length is not None:
            fixed[index] = measure.length.um
        elif measure.share is not None:
            fixed[index] = round(available * measure.share / 100)

    taken = sum(fixed.values())
    flexible = [index for index in range(len(measures)) if index not in fixed]
    if taken > available:
        written = ", ".join(
            measure.raw for measure in measures if measure is not None and not measure.rest
        )
        raise DefinitionError(
            f"the {of} ask for {_mm(taken)} of {what} and only {_mm(available)} is "
            f"available after the gaps ({written}). Nothing is squeezed to fit "
            "(§ 8.2) — reduce a measure, or leave one out so it takes what is left",
            field=of,
        )

    remainder = available - taken
    each = remainder // len(flexible) if flexible else 0
    return [
        fixed.get(index, each + (remainder - each * len(flexible) if index == flexible[-1] else 0))
        if index in fixed or flexible
        else 0
        for index in range(len(measures))
    ]


def _measure_field(cfg: FormConfig, cell: Cell, q: WriterQuery) -> None:
    """§ 7.8: titles are measured beforehand, and a title that does not fit is
    an error — `cut` (§ 8.9) does not reach generator labels."""
    size = cfg.title.font.size.um
    family = cfg.title.font.token
    padding = int(size * PADDING)
    title = cell.field.title

    if title and cfg.title.position != "none":
        width = q.text_width(title, family=family, size=size)
        if width > cell.width - 2 * padding:
            raise DefinitionError(
                f"the title {title!r} is {_mm(width)} wide and its field is "
                f"{_mm(cell.width)}. A field title is never cut (§ 8.9) — widen the "
                "column, shorten the title or lower title.font.size (§ 7.8)",
                field="rows",
            )

    if cell.field.kind in ("check", "choice"):
        box = cell.field.box_size.um if cell.field.box_size else int(size * BOX_SIZE)
        widest = max(
            (
                box + padding + q.text_width(option, family=family, size=size)
                for option in (cell.field.options or [""])
                if option
            ),
            default=box,
        )
        if widest > cell.width - 2 * padding:
            raise DefinitionError(
                f"an option of {title!r} needs {_mm(widest)} and its field is "
                f"{_mm(cell.width)} — even one per line does not fit. Widen the column "
                "or shorten the option labels (§ 7.8)",
                field="rows",
            )

    if cell.field.lines is not None:
        if cell.field.line_spacing is None:
            raise DefinitionError(
                "`lines` needs `line_spacing`: the ruling is absolute, so a line count "
                "without a line distance says nothing (§ 7.8)",
                field="rows",
            )
        ascent, descent = q.text_metrics(family=family, size=size)
        used = (ascent + descent + padding) if (title and cfg.title.position == "above") else 0
        room = cell.height - padding - used
        fits = room // cell.field.line_spacing.um
        if cell.field.lines > fits:
            raise DefinitionError(
                f"{cell.field.lines} writing lines of {cell.field.line_spacing.raw} need "
                f"{_mm(cell.field.lines * cell.field.line_spacing.um)} and the field "
                f"leaves {_mm(room)} — {fits} fit. The ruling is absolute and is never "
                "compressed (§ 7.8, § 8.2): ask for fewer lines, a smaller spacing or a "
                "taller row",
                field="rows",
            )


def _line_count(cfg: FormConfig, cell: Cell, top: Um) -> int:
    spacing = cell.field.line_spacing
    assert spacing is not None
    padding = int(cfg.title.font.size.um * PADDING)
    room = top - (cell.bottom + padding)
    fits = max(0, room // spacing.um)
    return min(fits, cell.field.lines) if cell.field.lines is not None else fits


def _title_of(field: Field_, page: PageContext) -> str | None:
    """§ 8.10: placeholders hold in form titles, named there by name."""
    if not field.title:
        return None
    return resolve_placeholders(field.title, page, field="rows")


def _mm(um: Um) -> str:
    return f"{um / 1000:.1f}mm"


Field_.model_rebuild()
Row.model_rebuild()
