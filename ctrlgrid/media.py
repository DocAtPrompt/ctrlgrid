"""The media check (§ 12.1) — the definition measured against the medium.

Run as soon as the medium is fixed, a device profile or a paper format, and
**not** by the writer: a 0.2 pt line is 0.64 px on a 229 dpi device whether the
output is PDF or PNG, and hanging the check on the PNG writer would find it only
when it is already visible — on the ordinary PDF path (§ 9.2), never.

Every finding carries the concrete number, because "line too thin" is not
something a user can act on and "0.2pt = 0.64px at 229dpi" is (§ 12). They are
warnings, said once before rendering; two things make them errors instead —
a value that rounds to **zero** pixels, which vanishes outright, and `--strict`,
which turns every warning into an error so a CI run can guard a preset set.

The check reads the marks themselves rather than asking each generator about its
weights and colours: one medium-agnostic pass serves every one of them, exactly
as § 12.1 wants — resolution is a property of the sheet, not of the generator.
A blade is sampled on page 0, which shows everything a repeating pattern has; a
document generator has unequal pages, so **all** of them are walked and one mark
is kept per distinct weight and colour (decision 49).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ctrlgrid.errors import DefinitionError
from ctrlgrid.marks import Arc, Dot, Point, Polygon, Segment
from ctrlgrid.writers import WriterQuery

if TYPE_CHECKING:
    from ctrlgrid.loader import Document

MM_PER_INCH = 25.4

#: Below this the antialiasing on e-ink gives up and a line looks stepped
#: (§ 12.1). On a real printer it is fine, so the finding is device-only.
STEPPED_PX = 2.0

#: Adjacent marks closer than this flow into one another (§ 12.1).
MERGE_PX = 3.0

#: Two greys within this share of the 0…255 range read as the same tone, so an
#: emphasis built on the colour difference between them vanishes. § 12.1 gives
#: `#7799bb` / `#4466aa` as the case that must fire, and those are 48 levels
#: apart — see docs/implementation-decisions.md 32 for why a threshold, not
#: equality.
GREY_COLLISION = 48


def media_findings(
    document: Document,
    q: WriterQuery,
    *,
    strict: bool = False,
    snapped: set[str] | None = None,
) -> list[str]:
    """What will not work on this medium (§ 12.1), gathered before rendering.

    Returns the warnings as strings. A value that rounds to zero pixels is
    raised straight away; `strict` raises the first of everything else.

    `snapped` names the axes under `snap: pixel` (§ 8.3.1): pixel snapping lands
    every position on a whole pixel, which is exactly what the uneven-cells
    finding warns is missing, so that finding is cancelled there — § 8.3.1 says
    so outright.
    """
    dpi = _dpi(document)
    marks = list(_sample(document, q))

    warnings: list[str] = []
    warnings += _weight_findings(marks, dpi, document)
    warnings += _spacing_findings(document, dpi, snapped or set())
    warnings += _colour_findings(marks, document)

    if strict and warnings:
        raise DefinitionError(
            "media check under --strict (§ 12.1):\n  " + "\n  ".join(warnings)
        )
    return warnings


def _px(mm: float, dpi: int) -> float:
    return mm / MM_PER_INCH * dpi


def _weight_findings(marks: list[object], dpi: int, document: Document) -> list[str]:
    """Stroke widths and dot diameters against one pixel (§ 12.1)."""
    on_eink = document.device is not None
    findings: list[str] = []
    for weight, raw in sorted(_weights(marks)):
        px = _px(weight, dpi)
        if round(px) == 0:
            # § 12.1: a warning does not abort, but a mark that rounds away to
            # nothing does — it is not on the sheet at all.
            raise DefinitionError(
                f"a stroke of {raw} is {px:.2f}px at {dpi}dpi — it rounds to zero pixels "
                f"and would not be drawn at all on this medium. Thicken it (§ 12.1)"
            )
        if px < 1.0:
            findings.append(
                f"stroke {raw} = {px:.2f}px at {dpi}dpi — under one pixel, so it "
                "disappears or lands on a random single pixel row (§ 12.1)"
            )
        elif on_eink and px < STEPPED_PX:
            findings.append(
                f"stroke {raw} = {px:.2f}px at {dpi}dpi — 1–2px on e-ink looks stepped, "
                "the antialiasing there is weak (§ 12.1)"
            )
    return findings


def _spacing_findings(document: Document, dpi: int, snapped: set[str]) -> list[str]:
    """Periodic spacings against the pixel grid (§ 12.1).

    Only periodic families have a spacing to check, so this reads
    `periodic_axes` — the same numbers snapping and remainder work on. A block
    generator (`grid`, `maze`, `form`) has cells, not a repeating step, and is
    silent here on purpose.
    """
    # The uneven-cells finding is device-only: on e-ink the ±1px swing on a
    # 45.08px cell is visible, on a 600dpi printer it is 1/600 inch and no eye
    # resolves it. The merge finding stays general — a spacing under three
    # device pixels flows into a grey area on paper too.
    on_device = document.device is not None
    findings: list[str] = []
    for axis, periods in document.axes.items():
        for period in periods:
            px = _px(period.step_um / 1000, dpi)
            if px < MERGE_PX:
                findings.append(
                    f"{axis} spacing {period.label} = {px:.1f}px at {dpi}dpi — under "
                    "three pixels, so neighbouring lines flow into one grey area (§ 12.1)"
                )
            elif on_device and axis not in snapped and abs(px - round(px)) > 0.02:
                low, high = int(px), int(px) + 1
                findings.append(
                    f"{axis} cells are {px:.2f}px at {dpi}dpi ({period.label}), so the "
                    f"device draws them alternately {low} and {high} pixels wide — the "
                    "grid looks uneven though it is computed exactly. `snap: pixel` "
                    "trades the nominal size for even cells (§ 8.3.1, § 12.1)"
                )
    return findings


def _colour_findings(marks: list[object], document: Document) -> list[str]:
    """What a grayscale screen does to colour (§ 12.1)."""
    if document.device is None or document.device.color != "grayscale":
        return []

    colours = _colours(marks)
    findings: list[str] = []
    for colour in sorted(colours):
        if not _is_grey(colour):
            grey = _grey(colour)
            findings.append(
                f"colour {colour} becomes grey #{grey:02x}{grey:02x}{grey:02x} on a "
                f"{document.device.name} — it is a grayscale screen (§ 12.1)"
            )

    ordered = sorted(colours)
    for i, first in enumerate(ordered):
        for second in ordered[i + 1:]:
            if abs(_grey(first) - _grey(second)) <= GREY_COLLISION:
                findings.append(
                    f"{first} and {second} are {abs(_grey(first) - _grey(second))} grey "
                    "levels apart — on a grayscale screen they read as one tone, so an "
                    "emphasis built on telling them apart vanishes (§ 12.1)"
                )
    return findings


# --------------------------------------------------------------- extraction


def _sample(document: Document, q: WriterQuery):
    """The marks to read weights and colours off (§ 12.1).

    A blade fills one pattern area with one repeating pattern, so page 0 shows
    everything it has. A **document generator** owns heterogeneous pages
    instead (§ 7), and there every page is walked — see `_document_sample` for
    why one page per kind would be cheaper and wrong.
    """
    from ctrlgrid import generators
    from ctrlgrid.document import is_document_generator
    from ctrlgrid.pages import Geometry, page_contexts

    geometry = Geometry.of(
        document.sheet,
        header=document.header,
        footer=document.footer,
        pattern=document.pattern,
        blade_axes=document.axes,
        density=document.device.density if document.device else None,
    )
    blade = generators.get(document.generator)
    if is_document_generator(blade):
        return _document_sample(document, blade, geometry, q)
    page = next(page_contexts(count=1, snap=geometry.pixel_snap))
    return blade.generate(document.config, area=geometry.area, page=page, q=q)


def _document_sample(document: Document, blade: object, geometry, q: WriterQuery):
    """One mark per distinct stroke width and colour, across **every** page.

    Every page, not the first of each `kind`: a marked day carries its own
    colour and appears on exactly the pages holding that date, so a shortcut
    would measure January and miss a birthday in May — the silent almost-right
    of § 5.1. The full walk of a 456-page year planner costs about a fifth of a
    second, once per run, and only one mark per distinct (weight, colour) is
    kept, so a document is no heavier here than a sheet.

    A page's `background` is a colour too. The handle paints that fill rather
    than the generator (§ 3.3), so it is no mark — but on a grayscale screen it
    is exactly what goes flat, and § 12.1 has to say so.
    """
    from ctrlgrid.pages import document_page_marks, page_contexts

    context = next(page_contexts(count=1, snap=()))
    seen: set[tuple] = set()
    for page in blade.pages(document.config, area=geometry.area, q=q):
        if page.background is not None:
            key = ("background", page.background)
            if key not in seen:
                seen.add(key)
                yield Segment(
                    start=Point(0, 0), end=Point(0, 0), weight=0.0, color=page.background
                )
        for mark in document_page_marks(
            page, area=geometry.area, context=context, q=q
        ):
            key = (
                type(mark).__name__,
                getattr(mark, "weight", None),
                getattr(mark, "diameter", None),
                getattr(mark, "color", None),
            )
            if key in seen:
                continue
            seen.add(key)
            yield mark


def _weights(marks: list[object]) -> set[tuple[float, str]]:
    """Distinct stroke widths and dot diameters, labelled in points.

    A mark carries millimetres, not the `0.15pt` the user wrote — but stroke
    widths are conventionally points, and § 12.1's own example is in points, so
    the label converts to pt. It is exact: 0.0705…mm is 0.2pt to the digit.
    """
    found: dict[float, str] = {}
    for mark in marks:
        if isinstance(mark, Dot):
            found.setdefault(mark.diameter, f"{mark.diameter:g}mm")
        elif isinstance(mark, Segment | Arc | Polygon) and mark.weight > 0:
            found.setdefault(mark.weight, f"{mark.weight * 72 / MM_PER_INCH:g}pt")
    return {(weight, label) for weight, label in found.items()}


def _colours(marks: list[object]) -> set[str]:
    found: set[str] = set()
    for mark in marks:
        colour = getattr(mark, "color", None)
        if colour:
            found.add(colour)
        fill = getattr(mark, "fill_color", None)
        if fill:
            found.add(fill)
    return found


def _grey(colour: str) -> int:
    """The Rec. 709 luminance of a `#rrggbb`, 0…255 — how grey it turns."""
    r, g, b = (int(colour[i : i + 2], 16) for i in (1, 3, 5))
    return round(0.2126 * r + 0.7152 * g + 0.0722 * b)


def _is_grey(colour: str) -> bool:
    return colour[1:3] == colour[3:5] == colour[5:7]


def _dpi(document: Document) -> int:
    """The medium's resolution: a device's density, or a format's assumed_dpi.

    § 12.1 runs on paper too, against `assumed_dpi` — a check yardstick, not a
    real resolution, which is exactly why `px` and `snap: pixel` still refuse to
    rest on it (§ 8.3.1). A free size has no entry, so it takes the general
    default the format table uses.
    """
    from ctrlgrid.loader import formats

    if document.device is not None:
        return document.device.density
    table = formats()
    if document.page.format in table:
        return table[document.page.format].assumed_dpi
    return 600
