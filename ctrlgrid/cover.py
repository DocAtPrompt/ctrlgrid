"""The cover sheet (§ 8.8) — a calibration figure and a settings summary.

It is one extra first page and it is unlike every other page in three ways, all
of them from § 8.8: it is **not counted** in the numbering, it carries **no
frame furniture** at all — no header, footer, border, hole marks — and because
it names the tool version it is **excluded from golden comparisons** (§ 13.2),
or every version bump would break the suite.

**Why a calibration square is the only possible answer.** § 8.2 promises that
5 mm measures 5 mm, and the one thing that can break that promise sits outside
this program: a print driver quietly scaling to 96 %. We cannot prevent it. We
can make it visible — a labelled 50 mm square and a 100 mm rule that a ruler
either agrees with or does not.

**Why the summary is on its own page and not on every sheet.** Both are meta
information about the print, not properties of the paper — the same reasoning
§ 8.6 gives for the stamp. On every sheet it would be dirt; once at the front
it is documentation.

**Nothing here is ever scaled to fit.** If the figures do not fit the format,
the run is refused (§ 8.2). A cover sheet whose "50 mm" square measures 38 mm
because the paper was small would be worse than no cover sheet at all — it is
the exact failure the page exists to detect.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ctrlgrid import __version__, fonts, generators
from ctrlgrid.errors import DefinitionError
from ctrlgrid.marks import Layer, Mark, Point, Polygon, Segment, Text, Um
from ctrlgrid.writers import WriterQuery

if TYPE_CHECKING:
    from ctrlgrid.loader import Document

#: The two calibration figures. Fixed numbers, not settings: they are the
#: yardstick, and a yardstick nobody can change is the point (§ 8.8).
SQUARE_SIDE = 50_000
RULE_LENGTH = 100_000
TICK = 3_000

TITLE_SIZE = 4_233  # 12pt
BODY_SIZE = 3_175  # 9pt
#: The summary shrinks rather than overflowing, but only so far: below this it
#: stops being readable, and an unreadable summary documents nothing.
MIN_SUMMARY_SIZE = 1_764  # 5pt
LINE_LEADING = 1.5
GAP = 6_000

ELLIPSIS = "…"

#: Two short lines rather than one long one: they have to survive the smallest
#: format the figures themselves still fit on.
INSTRUCTION = (
    "Lay a ruler against both figures.",
    "If they come out short, the print driver scaled: print at 'Actual size' / 100 %.",
)


def cover_marks(document: Document, *, q: WriterQuery) -> list[Mark]:
    """Everything on the cover, in sheet coordinates (§ 8.8).

    Called from the pre-flight (§ 12 point 13) as well as from the page loop,
    so that a format too small for the calibration figures is refused before
    the first byte is written rather than half way through.
    """
    sheet = document.sheet
    left = sheet.margin.inner.um
    right = sheet.width - sheet.margin.outer.um
    top = sheet.height - sheet.margin.top.um
    bottom = sheet.margin.bottom.um

    if right - left < RULE_LENGTH:
        raise DefinitionError(
            f"the cover sheet needs {_mm(RULE_LENGTH)} of width for its calibration rule, "
            f"and this page leaves {_mm(right - left)} between the margins. The figures are "
            "fixed measures and are never scaled to fit (§ 8.2, § 8.8) — use a larger "
            "format, narrower margins, or leave the cover out",
            field="pages.cover",
        )

    marks: list[Mark] = []
    cursor = top

    cursor = _line_of_text(marks, "ctrlgrid — calibration and settings", left, cursor,
                           size=TITLE_SIZE, family="sans", q=q, available=right - left)
    cursor -= GAP // 2
    for sentence in INSTRUCTION:
        cursor = _line_of_text(marks, sentence, left, cursor,
                               size=BODY_SIZE, family="sans", q=q, available=right - left)

    cursor -= GAP
    marks += _square(left, cursor, q=q)
    cursor -= SQUARE_SIDE + _text_height(q, size=BODY_SIZE) + GAP // 2

    cursor -= GAP
    marks += _rule(left, cursor, q=q)
    cursor -= TICK + _text_height(q, size=BODY_SIZE) + GAP // 2

    cursor -= GAP
    cursor = _summary_block(marks, document, left, cursor, width=right - left, q=q)

    if cursor < bottom:
        raise DefinitionError(
            f"the cover sheet does not fit: it needs {_mm(top - cursor)} of height and the "
            f"page leaves {_mm(top - bottom)}. Nothing on it is scaled to fit (§ 8.2, "
            "§ 8.8) — use a larger format or leave the cover out",
            field="pages.cover",
        )
    return marks


def summary(document: Document) -> list[str]:
    """What § 8.8 asks the cover to record, one line per item.

    Generator, format, margins, base values, cycles, effective period in marks
    and in millimetres, snap mode, tool version and the name and checksum of
    the definition underneath. That is the list that makes a sheet which worked
    reproducible years later, without anyone having to find the definition
    again — and the checksum is what separates a bent copy from the preset it
    came from.

    The base values, the cycles and the period come from the blade: only it
    knows its own families (§ 3.6, seam 2), which is what `describe` is for.
    """
    sheet, margin = document.sheet, document.sheet.margin
    pattern = document.pattern

    lines = [
        _entry("generator", document.generator),
        _entry(
            "format",
            f"{document.page.format} {document.page.orientation} — "
            f"{sheet.width / 1000:.1f} x {sheet.height / 1000:.1f} mm",
        ),
        _entry(
            "margins",
            f"top {margin.top.raw}  bottom {margin.bottom.raw}  "
            f"inner {margin.inner.raw}  outer {margin.outer.raw}",
        ),
        _entry(
            "pattern",
            f"snap x {pattern.snap.x or 'none'}, y {pattern.snap.y or 'none'}  —  "
            f"remainder x {pattern.remainder.x}, y {pattern.remainder.y}",
        ),
        _entry("pages", str(document.pages.count)),
    ]
    blade = generators.get(document.generator)
    for description in blade.describe(document.config):
        lines.append(_entry("family", description))
    # § 10.3 asks for file name and font version by name: an embedded font is
    # part of what the sheet is, and two releases of one font are two sheets.
    for section, band in (("header", document.header), ("footer", document.footer)):
        if band is not None and band.font.file is not None:
            font = fonts.load_font(band.font.file)
            lines.append(
                _entry(f"{section} font", f"{font.path.name}  {font.name}  {font.version}")
            )
    lines.append(_entry("definition", f"{document.source}  sha256 {document.digest}"))
    lines.append(_entry("tool", f"ctrlgrid {__version__}"))
    return _aligned(lines)


def _entry(label: str, value: str) -> tuple[str, str]:
    return label, value


def _aligned(entries: list[tuple[str, str]]) -> list[str]:
    """One column for the labels, wide enough for the longest of them.

    Computed rather than fixed: `header font` is longer than every label the
    first draft had, and a hard-coded column ran it into its value —
    `header fontVera.ttf`.
    """
    width = max(len(label) for label, _ in entries) + 2
    return [f"{label:<{width}}{value}" for label, value in entries]


# ------------------------------------------------------------------ the figures


def _square(left: Um, top: Um, *, q: WriterQuery) -> list[Mark]:
    """The 50 mm square with its nominal size written inside it (§ 8.8)."""
    bottom = top - SQUARE_SIDE
    right = left + SQUARE_SIDE
    label = f"{SQUARE_SIDE // 1000} mm"
    ascent, _ = q.text_metrics(family="sans", size=BODY_SIZE)
    return [
        Polygon(
            points=(
                Point(left, bottom),
                Point(right, bottom),
                Point(right, top),
                Point(left, top),
            ),
            closed=True,
            weight=0.3,
            color="#000000",
            fill_color=None,
            layer=Layer.PATTERN,
        ),
        Text(
            pos=Point((left + right) // 2, (bottom + top) // 2 - ascent // 2),
            content=label,
            size=BODY_SIZE,
            family="sans",
            align="center",
            layer=Layer.PATTERN,
        ),
        Text(
            pos=Point(left, bottom - _text_height(q, size=BODY_SIZE)),
            content="each side, edge to edge",
            size=BODY_SIZE,
            family="sans",
            layer=Layer.PATTERN,
        ),
    ]


def _rule(left: Um, top: Um, *, q: WriterQuery) -> list[Mark]:
    """A 100 mm line with a tick at either end, so a ruler can be laid against it."""
    right = left + RULE_LENGTH
    return [
        Segment(
            start=Point(left, top),
            end=Point(right, top),
            weight=0.3,
            layer=Layer.PATTERN,
        ),
        Segment(start=Point(left, top), end=Point(left, top - TICK), weight=0.3,
                layer=Layer.PATTERN),
        Segment(start=Point(right, top), end=Point(right, top - TICK), weight=0.3,
                layer=Layer.PATTERN),
        Text(
            pos=Point(left, top - TICK - _text_height(q, size=BODY_SIZE)),
            content=f"{RULE_LENGTH // 1000} mm",
            size=BODY_SIZE,
            family="sans",
            layer=Layer.PATTERN,
        ),
    ]


# ------------------------------------------------------------------ the summary


def _summary_block(
    marks: list[Mark], document: Document, left: Um, top: Um, *, width: Um, q: WriterQuery
) -> Um:
    """Set the summary in mono, small enough to fit the width it has.

    Mono because the lines are a table of label and value and read as one; and
    small enough because this text is written by the tool, not by the user, so
    § 8.9's refusal is not the right answer here — nobody could act on it. It
    shrinks, and only if even the smallest readable size will not do does a
    line get cut, always with the ellipsis § 8.9 makes mandatory.
    """
    lines = summary(document)
    size = BODY_SIZE
    while size > MIN_SUMMARY_SIZE and any(
        q.text_width(line, family="mono", size=size) > width for line in lines
    ):
        size -= 176  # ~0.5pt

    step = _text_height(q, size=size)
    cursor = top
    for line in lines:
        cursor -= step
        marks.append(
            Text(
                pos=Point(left, cursor),
                content=_fit(line, width=width, size=size, family="mono", q=q),
                size=size,
                family="mono",
                layer=Layer.PATTERN,
            )
        )
    return cursor


def _fit(text: str, *, width: Um, size: Um, family: str, q: WriterQuery) -> str:
    """Cut to width, and mark the cut — § 8.9 makes the ellipsis mandatory."""
    if q.text_width(text, family=family, size=size) <= width:
        return text
    mark = ELLIPSIS if not q.missing_glyphs(ELLIPSIS, family=family) else "..."
    kept = text
    while kept:
        kept = kept[:-1]
        candidate = kept.rstrip() + mark
        if q.text_width(candidate, family=family, size=size) <= width:
            return candidate
    return mark


# ------------------------------------------------------------------- plumbing


def _line_of_text(
    marks: list[Mark],
    text: str,
    left: Um,
    top: Um,
    *,
    size: Um,
    family: str,
    q: WriterQuery,
    available: Um | None = None,
) -> Um:
    """One line of text hanging from `top`; returns the cursor below it."""
    ascent, descent = q.text_metrics(family=family, size=size)
    baseline = top - ascent
    if available is not None:
        text = _fit(text, width=available, size=size, family=family, q=q)
    marks.append(
        Text(pos=Point(left, baseline), content=text, size=size, family=family,
             layer=Layer.PATTERN)
    )
    return baseline - descent


def _text_height(q: WriterQuery, *, size: Um) -> Um:
    ascent, descent = q.text_metrics(family="sans", size=size)
    return int((ascent + descent) * LINE_LEADING)


def _mm(um: Um) -> str:
    return f"{um / 1000:.1f}mm"
