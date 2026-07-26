"""The frame: header, footer, and — from M2 — border, stamp and hole marks.

Everything here belongs to the handle, not to a blade (§ 3). Two rules from the
specification do the shaping:

**Heights are fixed** (§ 8.4). They come from the definition and never from the
rendered content, or page 1 with "Anna Berger" would have a different pattern
area than page 7 with "Maximilian Sonnenschein-Hofstätter" and the grid would
jump from sheet to sheet. The height is therefore *checked* against the font,
not derived from it.

**Nothing is silently mutilated** (§ 8.9). A field that does not fit is an error
naming the field, the text and the missing millimetres. Only an explicit
`cut: true` truncates, and then always with an ellipsis — a cut string that
looks complete is worse than one that does not fit.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from ctrlgrid import fonts
from ctrlgrid.errors import DefinitionError
from ctrlgrid.images import load_image
from ctrlgrid.marks import Arc, Image, Layer, Mark, Point, Polygon, Segment, Text, Um
from ctrlgrid.model import Band, BorderSpec, ImageSpec, PageSpec, RulerSpec, StampSpec
from ctrlgrid.pages import Box, Geometry, PageContext, Sheet, resolve_placeholders
from ctrlgrid.ruler import (
    LABEL_GAP,
    label_text,
    number_height,
    strip_width,
    tick_length,
    ticks,
)
from ctrlgrid.writers import WriterQuery

ELLIPSIS = "…"
ELLIPSIS_FALLBACK = "..."

# ISO 838 (§ 8.7): two holes 6 mm across, centres 80 mm apart and 12 mm in from
# the binding edge, symmetric about the middle of the sheet.
HOLE_SPACING = 80_000
HOLE_INSET = 12_000
HOLE_DIAMETER = 6_000

#: How much of the sheet an `auto` stamp is asked to span (§ 8.6). Not the full
#: width: a diagonal word that touched both edges would be cropped by the
#: non-printable border on nearly every printer.
STAMP_COVERAGE = 0.8


def background_mark(color: str | None, sheet: Sheet) -> Polygon | None:
    """Paint the whole sheet before anything else (§ 5.2).

    It carries `Layer.PATTERN` and is emitted first rather than getting a layer
    of its own: § 6 fixes the vocabulary at three layers, and since the writer
    draws in the order marks arrive and never sorts (§ 3.6), being first is
    what "underneath" actually means.
    """
    if color is None:
        return None
    return Polygon(
        points=(
            Point(0, 0),
            Point(sheet.width, 0),
            Point(sheet.width, sheet.height),
            Point(0, sheet.height),
        ),
        closed=True,
        weight=0.0,
        color=color,
        fill_color=color,
        layer=Layer.PATTERN,
    )


def border_mark(border: BorderSpec | None, geometry: Geometry) -> Polygon | None:
    """A rule around the pattern area (§ 5.2, § 8.1).

    It sits on the pattern area's edge, and `gap` moves it *outwards* — the
    pattern keeps every millimetre § 8.1 gave it. A quadrilateral rather than a
    rectangle primitive, because § 6 grows the vocabulary by one and not two.
    """
    if border is None:
        return None

    gap = border.gap.um
    left = geometry.origin.x - gap
    bottom = geometry.origin.y - gap
    right = geometry.origin.x + geometry.area.width + gap
    top = geometry.origin.y + geometry.area.height + gap

    if left < 0 or bottom < 0:
        raise DefinitionError(
            f"border.gap of {border.gap.raw} pushes the border off the sheet — "
            f"it would start {_mm(-min(left, bottom))} outside the paper. "
            "Reduce the gap or widen the margin (§ 5.2)",
            field="border.gap",
        )

    return Polygon(
        points=(Point(left, bottom), Point(right, bottom), Point(right, top), Point(left, top)),
        closed=True,
        weight=border.weight.mm,
        color=border.color or "#000000",
        fill_color=None,
        layer=Layer.FRAME,
    )


def hole_marks(page: PageSpec, sheet: Sheet, *, is_even: bool) -> list[Arc]:
    """ISO 838 punch marks at the binding edge (§ 8.7).

    They travel with the orientation. Portrait sheets are filed along the inner
    edge, so under duplex the marks swap sides with it. Landscape sheets are
    filed along the **top** edge, and the top edge does not mirror when a sheet
    is turned over — so there they stay where they are on both sides, while
    `inner` and `outer` go on meaning the sides.

    They sit *in* the pattern area rather than in the margin, and that is the
    normal case, not a fault: with a 5 mm inner margin and hole centres at
    12 mm they necessarily land over the grid. Hence `Layer.FRAME`, so they are
    drawn on top, and no space is reserved for them.
    """
    if not page.hole_marks:
        return []

    if page.orientation == "landscape":
        middle = sheet.width // 2
        centres = [
            Point(middle - HOLE_SPACING // 2, sheet.height - HOLE_INSET),
            Point(middle + HOLE_SPACING // 2, sheet.height - HOLE_INSET),
        ]
    else:
        edge = sheet.width - HOLE_INSET if (page.duplex and is_even) else HOLE_INSET
        middle = sheet.height // 2
        centres = [
            Point(edge, middle - HOLE_SPACING // 2),
            Point(edge, middle + HOLE_SPACING // 2),
        ]

    return [
        Arc(
            center=centre,
            radius=HOLE_DIAMETER // 2,
            start_angle=0.0,
            sweep=360.0,
            weight=0.2,
            layer=Layer.FRAME,
        )
        for centre in centres
    ]


#: Where each edge of the pattern area is, and which way is *away* from it.
#: `along` names the axis the scale runs on, `outward` the sign it grows in on
#: the other axis (§ 8.12).
_EDGES: dict[str, tuple[str, int]] = {
    "bottom": ("x", -1),
    "top": ("x", +1),
    "left": ("y", -1),
    "right": ("y", +1),
}


def _edge_start(edge: str, geometry: Geometry) -> tuple[Point, Um]:
    """Where zero sits for this edge, and how far the scale runs.

    Zero is the pattern area's origin corner — the numbers agree with the grid,
    not with the paper's corner (§ 8.12).
    """
    origin, area = geometry.origin, geometry.area
    if edge == "bottom":
        return Point(origin.x, origin.y), area.width
    if edge == "top":
        return Point(origin.x, origin.y + area.height), area.width
    if edge == "left":
        return Point(origin.x, origin.y), area.height
    return Point(origin.x + area.width, origin.y), area.height


def _at(edge: str, start: Point, *, along: Um, out: Um) -> Point:
    """A point `along` the edge from zero and `out` away from the pattern."""
    axis, sign = _EDGES[edge]
    if axis == "x":
        return Point(start.x + along, start.y + sign * out)
    return Point(start.x + sign * out, start.y + along)


def _zero_on(edge: str, extent: Um, origin: str) -> tuple[Um, int]:
    """Where this edge's nought sits along it, and which way its numbers grow.

    One expression for all five origins (§ 8.12). The axis an edge runs on takes
    its half of the corner name — `top-left` means x from the left and y from
    the top — and `center` puts the nought in the middle of every edge, so the
    numbers before it are negative. That is the case a plotted function needs,
    and it is why a tick carries its *value* separately from its position.
    """
    if origin == "center":
        return extent // 2, +1
    vertical = edge in ("left", "right")
    from_far_end = ("top" in origin) if vertical else ("right" in origin)
    return (extent, -1) if from_far_end else (0, +1)


def ruler_marks(
    ruler: RulerSpec | None,
    geometry: Geometry,
    *,
    q: WriterQuery,
    align: str = "bottom-left",
) -> list[Mark]:
    """The edge scale (§ 8.12), in sheet coordinates.

    The ticks grow *outward* from the pattern edge into the margin, on
    `Layer.FRAME`: no space is reserved and the pattern area never moves, the
    same way a `border` never moves a grid line (§ 8.1). Whether the margin can
    take them is `check_rulers`' question, asked once before page one.

    On the vertical edges the numbers turn 90°, reading bottom to top: the
    strip a ruler needs is then the height of a digit on all four edges instead
    of the full width of a number on two of them.
    """
    if ruler is None:
        return []

    marks: list[Mark] = []
    height = number_height(ruler, q=q)
    # Absent, `origin` follows the pattern's anchor: the ruler exists so the
    # numbers agree with the grid (decision 47), and a grid anchored top-left
    # beside a scale counting from the bottom is that disagreement (§ 8.12).
    origin = ruler.origin or align
    for edge in ruler.edges:
        start, extent = _edge_start(edge, geometry)
        turned = edge in ("left", "right")
        # `direction`, not `sign`: the loop below has its own `sign` for which
        # way is *outward* from the pattern, and one name for two ideas is how
        # a scale ends up counting backwards.
        zero, direction = _zero_on(edge, extent, origin)
        for tick in ticks(ruler, extent=extent, zero=zero):
            length = tick_length(tick.kind)
            marks.append(
                Segment(
                    start=_at(edge, start, along=tick.at, out=0),
                    end=_at(edge, start, along=tick.at, out=length),
                    weight=ruler.weight.mm,
                    color=ruler.color,
                    layer=Layer.FRAME,
                )
            )
            if tick.kind != "label":
                continue
            # A glyph grows from its baseline towards its own "up", which the
            # 90° turn points at the sheet's left. So on `bottom` and `right`
            # the number grows back towards the pattern and its baseline has to
            # start a whole number-height further out.
            _axis, sign = _EDGES[edge]
            grows_outward = sign < 0 if turned else sign > 0
            out = length + LABEL_GAP + (0 if grows_outward else height)
            marks.append(
                Text(
                    pos=_at(edge, start, along=tick.at, out=out),
                    content=label_text(ruler, at=direction * tick.value),
                    size=ruler.font.size.um,
                    family=ruler.font.token,
                    align="center",
                    angle=90.0 if turned else 0.0,
                    color=ruler.color,
                    layer=Layer.FRAME,
                )
            )
    return marks


def _free_strip(edge: str, geometry: Geometry, sheet: Sheet) -> tuple[Um, str | None]:
    """What stands between the pattern area's edge and the sheet's, and what
    ends the space — a band, or nothing but the paper (§ 8.12)."""
    origin, area = geometry.origin, geometry.area
    if edge == "bottom":
        if geometry.footer is not None:
            return origin.y - geometry.footer.top, "footer"
        return origin.y, None
    if edge == "top":
        top = origin.y + area.height
        if geometry.header is not None:
            return geometry.header.bottom - top, "header"
        return sheet.height - top, None
    if edge == "left":
        return origin.x, None
    return sheet.width - (origin.x + area.width), None


def check_rulers(
    ruler: RulerSpec | None, geometry: Geometry, document, *, q: WriterQuery
) -> None:
    """Fit or refuse, before page one (§ 12 point 13, § 8.2).

    Nothing is ever shrunk, clipped or moved to make a ruler fit. The message
    names the edge, the millimetres it needed and the millimetres there are —
    and the band, when a band is what took them.
    """
    if ruler is None:
        return

    needed = strip_width(ruler, q=q)
    for edge in ruler.edges:
        free, cause = _free_strip(edge, geometry, document.sheet)
        if needed > free:
            because = f", where the {cause} band ends" if cause else ""
            raise DefinitionError(
                f"the {edge} ruler needs {_mm(needed)} between the pattern area and the "
                f"edge of the sheet, and there is {_mm(max(free, 0))}{because} — widen "
                "the margin or set a smaller `ruler.font.size` (§ 8.12)",
                field="ruler",
            )

    # Two numbers that overlap read as one wrong number, so the widest is
    # measured rather than assumed (§ 10.2) — and it is measured on the labels
    # this ruler will really draw, minus signs and all: with a centred origin
    # the widest is "-100", not "100" (§ 8.12). Same zeroes as the drawing uses,
    # because two arithmetics for one question drift.
    origin = ruler.origin or document.pattern.align
    widest = 0
    for edge in ruler.edges:
        extent = (
            geometry.area.height if edge in ("left", "right") else geometry.area.width
        )
        zero, direction = _zero_on(edge, extent, origin)
        for tick in ticks(ruler, extent=extent, zero=zero):
            if tick.kind != "label":
                continue
            widest = max(
                widest,
                q.text_width(
                    label_text(ruler, at=direction * tick.value),
                    family=ruler.font.token,
                    size=ruler.font.size.um,
                ),
            )
    if widest > ruler.label_every.um:
        raise DefinitionError(
            f"the ruler's numbers are up to {_mm(widest)} wide and stand "
            f"{ruler.label_every.raw} apart, so they would run into one another — label "
            "further apart or set a smaller `ruler.font.size` (§ 8.12)",
            field="ruler.label_every",
        )


def stamp_mark(stamp: StampSpec | None, sheet: Sheet, *, q: WriterQuery) -> Text | None:
    """A full-page diagonal overprint on the topmost layer (§ 8.6)."""
    if stamp is None:
        return None

    size = (
        _auto_stamp_size(stamp.text, sheet, q=q)
        if stamp.size == "auto"
        else stamp.size.um
    )
    return Text(
        pos=Point(sheet.width // 2, sheet.height // 2),
        content=stamp.text,
        size=size,
        align="center",
        angle=stamp.angle.deg,
        opacity=stamp.opacity,
        layer=Layer.OVERLAY,
    )


def _auto_stamp_size(text: str, sheet: Sheet, *, q: WriterQuery) -> Um:
    """Scale the word to the sheet by measuring it, not by guessing (§ 10.2)."""
    reference = 10_000  # any size will do; text width is linear in it
    width = q.text_width(text, family="sans", size=reference)
    if width <= 0:
        return reference
    target = int(sheet.width * STAMP_COVERAGE)
    return max(1, reference * target // width)


def layout_band(
    band: Band,
    box: Box,
    *,
    q: WriterQuery,
    page: PageContext,
    section: str,
    sheet_width: Um,
    extra: Mapping[str, str] | None = None,
) -> list[Mark]:
    """Lay a header or footer out inside its box, measuring every field.

    Fields hold free text or an image (§ 5.2), and the two are measured the
    same way and refused on the same rule — with one difference § 8.9 is
    explicit about: text may be truncated when `cut: true` says so, an image
    never. A logo fits or it is an error.

    `section` is "header" or "footer" and appears in error messages, because
    "text does not fit" without a field name is not something a user can act on
    (§ 12).
    """
    fields = {"left": band.left, "center": band.center, "right": band.right}
    resolved: dict[str, str | ImageSpec] = {
        align: (
            content
            if isinstance(content, ImageSpec)
            else resolve_placeholders(content, page, field=f"{section}.{align}", extra=extra)
        )
        for align, content in fields.items()
        if content
    }
    # A full-width strip behind the band (band height only, § 8.9). First in the
    # list, so the text paints over it. Layer is not sorted — order is paint order.
    fill = (
        Polygon(
            points=(
                Point(0, box.bottom), Point(sheet_width, box.bottom),
                Point(sheet_width, box.top), Point(0, box.top),
            ),
            closed=True, weight=0.0,
            color=band.background, fill_color=band.background, layer=Layer.FRAME,
        )
        if band.background is not None
        else None
    )
    if not resolved:
        return [fill] if fill is not None else []

    size = band.font.size.um
    # A font token, not a family name: stage 1's three logical families and a
    # file font of stage 2 are two spellings of the same string (§ 10.3).
    family = band.font.token
    pictures = {
        align: _measure_image(content, box, section=section, align=align)
        for align, content in resolved.items()
        if isinstance(content, ImageSpec)
    }
    texts = {align: value for align, value in resolved.items() if isinstance(value, str)}

    baseline = (
        _baseline(box, band, q=q, section=section, size=size, family=family)
        if texts
        else box.bottom
    )
    for align, text in texts.items():
        _check_glyphs(text, family=family, q=q, field=f"{section}.{align}")

    widths = {align: q.text_width(text, family=family, size=size)
              for align, text in texts.items()}
    widths |= {align: picture[0] for align, picture in pictures.items()}
    available = _available(box, centre_width=widths.get("center", 0))

    marks: list[Mark] = [fill] if fill is not None else []
    # The centre field is laid out first: § 8.9 rule 1 gives it the content
    # width, and if it alone is too wide it is the one that gets cut.
    for align in ("center", "left", "right"):
        if align not in resolved:
            continue
        if align in pictures:
            marks.append(
                _image_mark(
                    pictures[align],
                    box=box,
                    align=align,
                    available=available[align],
                    field=f"{section}.{align}",
                )
            )
            continue
        content = _fit(
            texts[align],
            width=widths[align],
            available=available[align],
            band=band,
            q=q,
            family=family,
            size=size,
            field=f"{section}.{align}",
        )
        marks.append(
            Text(
                pos=Point(_anchor(align, box), baseline),
                content=content,
                size=size,
                family=family,
                align=align,
                color=band.text_color or "#000000",
                layer=Layer.FRAME,
            )
        )
    return marks


def _measure_image(
    spec: ImageSpec, box: Box, *, section: str, align: str
) -> tuple[Um, Um, str]:
    """Width, height and resolved path — the height checked against the band.

    § 8.4 fixes band heights in the definition and § 12 point 13 checks them
    against every image before page one. Deriving the height from the picture
    instead would make page 1 with a tall logo a different sheet from page 7.
    """
    image = load_image(spec.image, field=f"{section}.{align}")
    height = spec.height.um
    if height > box.height:
        raise DefinitionError(
            f"{Path(spec.image).name} is {spec.height.raw} tall but {section}.height is "
            f"{_mm(box.height)}. Raise {section}.height or reduce the image height — "
            "the band height comes from the definition and is never derived from "
            "its content (§ 8.4)",
            field=f"{section}.{align}.height",
        )
    return round(height * image.aspect), height, str(image.path)


def _image_mark(
    picture: tuple[Um, Um, str], *, box: Box, align: str, available: Um, field: str
) -> Image:
    """Place a measured image in its field, or refuse — never crop (§ 8.9)."""
    width, height, source = picture
    if width > available:
        raise DefinitionError(
            f"{Path(source).name} is {_mm(width)} wide at a height of {_mm(height)}, and "
            f"only {_mm(available)} is available. An image is never cropped and never "
            "squeezed: reduce its height, shorten the neighbouring field, or use a "
            "narrower picture (§ 8.9)",
            field=field,
        )
    left = {
        "left": box.left,
        "center": (box.left + box.right) // 2 - width // 2,
        "right": box.right - width,
    }[align]
    return Image(
        pos=Point(left, box.bottom + (box.height - height) // 2),
        width=width,
        height=height,
        source=source,
        layer=Layer.FRAME,
    )


def _available(box: Box, *, centre_width: Um) -> dict[str, Um]:
    """Split the content width between the three fields (§ 8.9).

    With a centre field, left and right run up to its edges. Without one there
    is no centre block to derive edges from, so they split at the middle — the
    commonest case of all, name left and page number right.
    """
    middle = (box.left + box.right) // 2
    if centre_width:
        half = centre_width // 2
        return {
            "center": box.width,
            "left": middle - half - box.left,
            "right": box.right - (middle + half),
        }
    return {"center": box.width, "left": middle - box.left, "right": box.right - middle}


def _anchor(align: str, box: Box) -> Um:
    return {
        "left": box.left,
        "center": (box.left + box.right) // 2,
        "right": box.right,
    }[align]


def _baseline(
    box: Box,
    band: Band,
    *,
    q: WriterQuery,
    section: str,
    size: Um,
    family: str,
) -> Um:
    """Centre the text vertically, after checking the band is tall enough (§ 8.4)."""
    ascent, descent = q.text_metrics(family=family, size=size)
    needed = ascent + descent
    if needed > box.height:
        raise DefinitionError(
            f"{section}.height is {_mm(box.height)} but font size {band.font.size.raw} "
            f"needs {_mm(needed)} (ascent {_mm(ascent)} + descent {_mm(descent)}). "
            f"Raise {section}.height or lower the font size (§ 8.4)",
            field=f"{section}.height",
        )
    return box.bottom + (box.height - needed) // 2 + descent


def _check_glyphs(text: str, *, family: str, q: WriterQuery, field: str) -> None:
    """§ 10.2: a name with `ł`, `ğ` or `ő` is not an edge case.

    The message has to name the way out and not just the glyph — whoever reads
    in a class list meets this at the first Polish name, and "missing glyph"
    alone leaves them nowhere to go (§ 10.3).
    """
    missing = q.missing_glyphs(text, family=family)
    if not missing:
        return
    if fonts.is_file_token(family):
        raise DefinitionError(
            f"{', '.join(missing)} — not covered by the font file "
            f"{fonts.load_token(family).path}. Pick a font that has these characters; "
            "substituting another one quietly would change every measurement on the "
            "sheet (§ 10.3)",
            field=field,
        )
    raise DefinitionError(
        f"{', '.join(missing)} — not covered by the standard PDF fonts, which reach "
        "Latin-1 and no further. The way out is naming your own font file: "
        "`font: {file: /path/to/font.ttf}` (stage 2 of § 10.3)",
        field=field,
    )


def _fit(
    text: str,
    *,
    width: Um,
    available: Um,
    band: Band,
    q: WriterQuery,
    family: str,
    size: Um,
    field: str,
) -> str:
    if width <= available:
        return text
    if not band.cut:
        raise DefinitionError(
            f"{text!r} is {_mm(width)} wide but only {_mm(available)} is available — "
            f"{_mm(width - available)} too much. Shorten the text, widen the page, "
            f"or set cut: true to truncate it deliberately (§ 8.9)",
            field=field,
        )
    return _truncate(text, available=available, q=q, family=family, size=size)


def _truncate(text: str, *, available: Um, q: WriterQuery, family: str, size: Um) -> str:
    """Cut and mark the cut. The mark is mandatory (§ 8.9)."""
    mark = ELLIPSIS if not q.missing_glyphs(ELLIPSIS, family=family) else ELLIPSIS_FALLBACK
    kept = text
    while kept:
        kept = kept[:-1]
        candidate = kept.rstrip() + mark
        if q.text_width(candidate, family=family, size=size) <= available:
            return candidate
    return mark


def _mm(um: Um) -> str:
    return f"{um / 1000:.1f}mm"
