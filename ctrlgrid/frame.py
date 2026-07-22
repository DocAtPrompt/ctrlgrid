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

from pathlib import Path

from ctrlgrid import fonts
from ctrlgrid.errors import DefinitionError
from ctrlgrid.images import load_image
from ctrlgrid.marks import Arc, Image, Layer, Mark, Point, Polygon, Text, Um
from ctrlgrid.model import Band, BorderSpec, ImageSpec, PageSpec, StampSpec
from ctrlgrid.pages import Box, Geometry, PageContext, Sheet, resolve_placeholders
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
            else resolve_placeholders(content, page, field=f"{section}.{align}")
        )
        for align, content in fields.items()
        if content
    }
    if not resolved:
        return []

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

    marks: list[Mark] = []
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
