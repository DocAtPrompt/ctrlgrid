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

from ctrlgrid.errors import DefinitionError
from ctrlgrid.marks import Layer, Point, Text, Um
from ctrlgrid.model import Band
from ctrlgrid.pages import Box, PageContext, resolve_placeholders
from ctrlgrid.writers import WriterQuery

ELLIPSIS = "…"
ELLIPSIS_FALLBACK = "..."


def layout_band(
    band: Band,
    box: Box,
    *,
    q: WriterQuery,
    page: PageContext,
    section: str,
) -> list[Text]:
    """Lay a header or footer out inside its box, measuring every field.

    `section` is "header" or "footer" and appears in error messages, because
    "text does not fit" without a field name is not something a user can act on
    (§ 12).
    """
    fields = {"left": band.left, "center": band.center, "right": band.right}
    resolved = {
        align: resolve_placeholders(text, page, field=f"{section}.{align}")
        for align, text in fields.items()
        if text
    }
    if not resolved:
        return []

    size = band.font.size.um
    family = band.font.family
    baseline = _baseline(box, band, q=q, section=section, size=size, family=family)

    for align, text in resolved.items():
        _check_glyphs(text, family=family, q=q, field=f"{section}.{align}")

    widths = {align: q.text_width(text, family=family, size=size) for align, text in
              resolved.items()}
    available = _available(box, centre_width=widths.get("center", 0))

    marks: list[Text] = []
    # The centre field is laid out first: § 8.9 rule 1 gives it the content
    # width, and if it alone is too wide it is the one that gets cut.
    for align in ("center", "left", "right"):
        if align not in resolved:
            continue
        content = _fit(
            resolved[align],
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
    missing = q.missing_glyphs(text, family=family)
    if missing:
        raise DefinitionError(
            f"{', '.join(missing)} — not covered by the standard PDF fonts, which reach "
            "Latin-1 and no further. The way out is naming your own font file "
            "(`font: {file: ...}`, § 10.3), which arrives with milestone M2",
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
