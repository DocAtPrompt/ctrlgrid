"""Page geometry, the page loop, the page context and placeholders (§ 8.1, § 8.10).

The paper format is the base, and everything else is computed from it — which
is why it can be exchanged without touching the definition. The pattern area is
what remains after margins, header, footer and their gaps, and it is the origin
of every pattern coordinate (§ 8.1).

The page context is what a blade learns about the sheet, and deliberately no
more. It carries no geometry: the pattern area arrives separately as an `Area`
in local coordinates, so that § 3.3 stays true and a generator never learns
what a margin is.
"""

from __future__ import annotations

import datetime
import hashlib
import re
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass, replace
from pathlib import Path
from typing import TYPE_CHECKING

from ctrlgrid.axes import AxisPeriod
from ctrlgrid.errors import DefinitionError
from ctrlgrid.impose import Imposition, slots
from ctrlgrid.marks import (
    Arc,
    Area,
    Image,
    Mark,
    Point,
    Polygon,
    Text,
    Um,
    mirror_x,
    mirror_y,
    translate,
)
from ctrlgrid.model import Band, Margin, PatternSpec
from ctrlgrid.writers import Attachment, DocumentMeta, Writer, WriterQuery

if TYPE_CHECKING:
    # `loader` imports `Sheet` from here, so the arrow points one way.
    from ctrlgrid.document import DocumentPage
    from ctrlgrid.loader import Document


@dataclass(frozen=True, slots=True)
class PageContext:
    """Everything a blade may know about the page it is drawing (§ 3.6)."""

    index: int
    """0-based; a cover sheet is not counted (§ 8.8)."""

    number: int
    """1-based — what `{page}` resolves to."""

    count: int
    """What `{page_count}` resolves to."""

    name: str | None
    """The entry from the name list, otherwise None (§ 9.4)."""

    is_even: bool
    """For duplex, where inner and outer swap (§ 8.1)."""

    seed_material: bytes
    """Stable bytes from seed and index, for procedural blades (§ 3.3)."""

    pixel_snap: tuple[tuple[str, int], ...] = ()
    """Axes under `snap: pixel`, each with the device density in dpi (§ 8.3.1).

    A medium property, not a geometry one: it tells a periodic blade to round
    every step to whole pixels, and it carries no margin or origin, so § 3.3
    still holds. Empty on paper and wherever pixel snapping is off — which is
    almost always. A blade reads it as `self.pixel_of(axis)`."""

    def pixel_of(self, axis: str) -> int | None:
        """The device density in dpi for `axis`, if it is pixel-snapped (§ 8.3.1)."""
        return dict(self.pixel_snap).get(axis)


@dataclass(frozen=True, slots=True)
class SheetPlan:
    """How many sheets one *item* of a run needs, and which of them mirror.

    Almost always one sheet per item — that is the default and no blade has to
    say anything. `maze` is the exception § 7.5 writes out: with
    `solution: separate_page` every puzzle needs a second sheet, so `--pages 10`
    means ten puzzles on twenty sheets, `{page_count}` is twenty, and a name
    list gives each entry both of its sheets.

    The blade only *states* this. Doubling the loop, numbering the sheets and
    mirroring one of them stay with the handle, because all three are
    properties of the page rather than of the pattern (§ 3).
    """

    per_item: int = 1
    mirrored: frozenset[int] = frozenset()
    """Sub-indices (0-based within an item) drawn mirrored about the **sheet's**
    vertical centre — § 7.5's `back_mirrored`, so the solution shows through
    when the sheet is held against the light. The sheet's centre and not the
    pattern area's: the reference is the physical turning edge."""


@dataclass(frozen=True, slots=True)
class Sheet:
    """The physical page after orientation has been applied (§ 9.1)."""

    width: Um
    height: Um
    margin: Margin


def raw_extent(sheet: Sheet, header: Band | None, footer: Band | None) -> tuple[Um, Um]:
    """The pattern area before snapping — sheet minus margins and bands (§ 8.1).

    Shared with the loader (seam 1) so a relative measure (`%w`/`%h`/`%s`, § 8.11)
    takes its fraction of the very width and height the pattern area is built
    from — fixed here, before `place_pattern` shrinks it to whole periods
    (§ 8.3). Keeping it in one function is what stops the two from drifting.
    """
    margin = sheet.margin
    width = sheet.width - margin.inner.um - margin.outer.um
    height = (
        sheet.height
        - margin.top.um
        - margin.bottom.um
        - (header.height.um + header.gap.um if header else 0)
        - (footer.height.um + footer.gap.um if footer else 0)
    )
    return width, height


def background_image_rect(
    sheet_w: int, sheet_h: int, aspect: float, fit: str
) -> tuple[int, int, int, int]:
    """The (x, y, width, height) in sheet µm for a full-sheet background image
    of the given pixel `aspect` (width / height), fitted `cover` or `contain`
    (§ 7.12). `contain` fits the whole image inside the sheet (the colour fills
    the rest); `cover` fills the sheet and may overhang (the PDF MediaBox crops
    it). Centred; integer µm so the same input gives the same bytes (#5)."""
    sheet_aspect = sheet_w / sheet_h
    # Width-bound when: contain and the image is relatively wider than the sheet,
    # or cover and it is relatively taller. Otherwise height-bound.
    width_bound = (aspect >= sheet_aspect) if fit == "contain" else (aspect < sheet_aspect)
    if width_bound:
        width = sheet_w
        height = round(sheet_w / aspect)
    else:
        height = sheet_h
        width = round(sheet_h * aspect)
    x = round((sheet_w - width) / 2)
    y = round((sheet_h - height) / 2)
    return x, y, width, height


@dataclass(frozen=True, slots=True)
class Box:
    """A rectangle in sheet coordinates — a header or footer band."""

    left: Um
    bottom: Um
    right: Um
    top: Um

    @property
    def width(self) -> Um:
        return self.right - self.left

    @property
    def height(self) -> Um:
        return self.top - self.bottom


@dataclass(frozen=True, slots=True)
class Geometry:
    """The page broken down: where the pattern goes and where the bands go."""

    area: Area
    """The pattern area, in local coordinates — origin (0, 0) (§ 3.6)."""

    origin: Point
    """Where that local origin sits on the sheet; the one place marks are shifted."""

    header: Box | None
    footer: Box | None

    notices: tuple[str, ...] = ()
    """Things worth saying but not worth refusing over — a setting that cannot
    take effect where it stands (§ 8.3). Reported once per run, never per page."""

    pixel_snap: tuple[tuple[str, int], ...] = ()
    """Axes set to `snap: pixel`, each with the device density in dpi (§ 8.3.1).
    The handle passes it to the blade through the page context so the blade
    rounds every *step* to whole pixels — the one thing that lands fractional
    cycle multiples on the pixel grid too. The density and not a rounded pixel
    size, so the grid stays exact (25400 / dpi per pixel)."""

    @classmethod
    def of(
        cls,
        sheet: Sheet,
        *,
        header: Band | None,
        footer: Band | None,
        pattern: PatternSpec | None = None,
        blade_axes: dict[str, list[AxisPeriod]] | None = None,
        density: int | None = None,
    ) -> Geometry:
        """Work out § 8.1, and refuse with the arithmetic if nothing is left."""
        margin = sheet.margin
        header_height = header.height.um if header else 0
        header_gap = header.gap.um if header else 0
        footer_height = footer.height.um if footer else 0
        footer_gap = footer.gap.um if footer else 0

        # The same raw extent the loader resolved relative measures against
        # (§ 8.11), before this shrinks it to whole periods (§ 8.3).
        width, height = raw_extent(sheet, header, footer)

        if width <= 0:
            raise _no_room(
                "width",
                sheet.width,
                [("margin.inner", margin.inner.um), ("margin.outer", margin.outer.um)],
                width,
            )
        if height <= 0:
            raise _no_room(
                "height",
                sheet.height,
                [
                    ("margin.top", margin.top.um),
                    ("margin.bottom", margin.bottom.um),
                    ("header.height", header_height),
                    ("header.gap", header_gap),
                    ("footer.height", footer_height),
                    ("footer.gap", footer_gap),
                ],
                height,
            )

        left = margin.inner.um
        bottom = margin.bottom.um + footer_height + footer_gap
        right = left + width

        # The bands keep the full content width; only the pattern area shrinks
        # and moves when it snaps and its surplus is placed (§ 8.3, § 8.5).
        notices: list[str] = []
        snapped: dict[str, int] = {}
        inner_width, shift_x = place_pattern(
            width, "x", pattern, blade_axes, notices, density, snapped
        )
        inner_height, shift_y = place_pattern(
            height, "y", pattern, blade_axes, notices, density, snapped
        )

        return cls(
            notices=tuple(notices),
            pixel_snap=tuple(sorted(snapped.items())),
            area=Area(width=inner_width, height=inner_height),
            origin=Point(left + shift_x, bottom + shift_y),
            header=(
                Box(
                    left=left,
                    bottom=sheet.height - margin.top.um - header_height,
                    right=right,
                    top=sheet.height - margin.top.um,
                )
                if header
                else None
            ),
            footer=(
                Box(
                    left=left,
                    bottom=margin.bottom.um,
                    right=right,
                    top=margin.bottom.um + footer_height,
                )
                if footer
                else None
            ),
        )


    def for_page(self, *, is_even: bool, sheet: Sheet, duplex: bool) -> Geometry:
        """The same geometry as it sits on this particular sheet side (§ 8.1).

        Under duplex the margins swap on even pages, so everything inside them
        — pattern area, header, footer — moves sideways by the difference.
        Nothing is recomputed: the size is identical either way, since
        `content_width = page - inner - outer` whichever way round the two go.
        That is also what makes § 3.3's demand hold by construction — snapping
        is solved once, for both page sorts at a time, and can never resolve
        differently on the two sides of a sheet.
        """
        if not (duplex and is_even):
            return self
        shift = sheet.margin.outer.um - sheet.margin.inner.um
        if shift == 0:
            return self
        return Geometry(
            area=self.area,
            origin=Point(self.origin.x + shift, self.origin.y),
            header=_shift(self.header, shift),
            footer=_shift(self.footer, shift),
            notices=self.notices,
            pixel_snap=self.pixel_snap,
        )


def _shift(box: Box | None, dx: Um) -> Box | None:
    if box is None:
        return None
    return Box(left=box.left + dx, bottom=box.bottom, right=box.right + dx, top=box.top)


def is_page_invariant(document: Document) -> bool:
    """Whether the writer may store the pattern once and reference it (§ 10.1).

    § 3.3 is explicit that duplex overrides the blade here: with the pattern
    area sitting somewhere else on every other sheet, a single stored form
    cannot serve both sorts. The blade is not asked in that case — its answer
    would be about its own marks, not about where they land.
    """
    from ctrlgrid import generators

    if document.page.duplex:
        return False
    return generators.get(document.generator).is_page_invariant(document.config)


def place_pattern(
    available: Um,
    axis: str,
    pattern: PatternSpec | None,
    blade_axes: dict[str, list[AxisPeriod]] | None,
    notices: list[str],
    density: int | None = None,
    snapped: dict[str, int] | None = None,
) -> tuple[Um, Um]:
    """Snap one axis and place its surplus (§ 8.3, § 8.5).

    Returns how much of the axis the pattern occupies and how far to shift it.
    The two settings work in that order and are not alternatives: snapping
    decides how much room the pattern may use, and `remainder` decides where
    the space it does not use ends up. § 8.3 puts it exactly so — snapping does
    not remove the surplus, it *relocates* it, turning a cut period at the edge
    into contiguous free space.

    There is no "stretch until it fits" anywhere in here: § 8.2 rules it out
    and deliberately offers no option for it.
    """
    if pattern is None:
        return available, 0

    mode = getattr(pattern.remainder, axis)
    snap = getattr(pattern.snap, axis) or "none"
    periods = (blade_axes or {}).get(axis, [])

    if not periods:
        # Whoever names an axis expects an effect there (§ 8.3). The scalar
        # shorthand names no axis, so it stays silent where nothing is periodic.
        for setting, pair in (("remainder", pattern.remainder), ("snap", pattern.snap)):
            named = getattr(pair, axis)
            if pair.explicit and named is not None and named != "none":
                raise DefinitionError(
                    f"pattern.{setting} names the {axis} axis, but the generator has no "
                    f"periodic family running along {axis}. Snapping and remainder "
                    "handling need a period to work with (§ 8.3, § 8.5)",
                    field=f"pattern.{setting}.{axis}",
                )
        return available, 0

    period = _governing(periods, axis)
    if snap != "none" and period.fixed_block:
        # § 7.9: a log family is not snappable, and saying so beats snapping to
        # a decade length that means nothing as a grid step.
        raise DefinitionError(
            f"`snap: {snap}` is not supported on the {axis} axis: it is governed by "
            f"{period.label}, and § 7.9 rules snapping out for `law: log10` — decade "
            "lengths do not divide into grid steps. Remove pattern.snap",
            field=f"pattern.snap.{axis}",
        )

    if snap == "pixel":
        # § 8.3.1: the one exception to dimensional accuracy, and unlike the
        # other two it does not shrink the area — it changes the step, so the
        # blade does the rounding and the area is left whole. The handle only
        # says which axis is snapped, at what density, and reports the cost.
        _require_device(density, axis)
        if snapped is not None:
            snapped[axis] = density  # type: ignore[assignment]
        _report_pixel_snap(period, density, notices)
        return available, 0

    room = _snap(available, snap, period, axis)

    if snap == "cycle" and mode == "whole_cycles":
        # § 8.3: ineffective beside `snap: cycle`, since only whole cycles
        # arise there anyway. Said once, so nobody keeps adjusting a setting
        # that cannot do anything.
        notices.append(
            f"pattern.remainder.{axis}: `whole_cycles` has no effect beside `snap: cycle` "
            "— whole cycles are all that arise there (§ 8.3)"
        )

    used = (
        period.used_whole_cycles(room) if mode == "whole_cycles" else period.used(room)
    )
    surplus = available - used

    if mode == "center":
        return used, surplus // 2
    # `end` and `whole_cycles` both leave the pattern at the origin and let the
    # surplus collect at the far end. Unsnapped `end` keeps the area exactly as
    # § 8.1 computed it, which is the whole reason `none` is the default.
    return (available if (snap == "none" and mode == "end") else used), 0


def _require_device(density: int | None, axis: str) -> None:
    """§ 8.3.1: `snap: pixel` is legal only with a device profile.

    On a paper format `assumed_dpi` is a yardstick for the media check and not
    a real resolution — geometry must never rest on a guessed number.
    """
    if density is None:
        raise DefinitionError(
            "`snap: pixel` needs a device profile: it rounds to whole device pixels, "
            "and a paper format has no real resolution to round to — its `assumed_dpi` "
            "is a yardstick for the media check, not a raster (§ 8.3.1, § 9.1). Set "
            "`page.device`",
            field=f"pattern.snap.{axis}",
        )


def _report_pixel_snap(period: AxisPeriod, density: int, notices: list[str]) -> None:
    """§ 8.3.1: report the actual measure, unprompted, in both units.

    "spacing 5mm → 4.991mm (45px at 229dpi)" — a silent change of size is the
    breach of trust § 8.2 exists to prevent, so pixel snapping says what it did.
    The pixel size is kept exact so the reported millimetre is the true one.
    """
    pixel = 25400 / density
    pixels = round(period.step_um / pixel)
    rounded = round(pixels * pixel)
    notices.append(
        f"snap: pixel — {period.label} → {rounded / 1000:.3f}mm ({pixels}px at "
        f"{density}dpi): even cells, at the cost of the nominal size (§ 8.3.1)"
    )


def _snap(available: Um, mode: str, period: AxisPeriod, axis: str) -> Um:
    """How much room the pattern may use after snapping (§ 8.3)."""
    if mode == "none":
        return available

    granularity = period.step_um if mode == "spacing" else period.cycle_um
    whole = (available // granularity) * granularity
    if whole <= 0:
        raise DefinitionError(
            f"`snap: {mode}` cannot fit a single {'step' if mode == 'spacing' else 'cycle'} "
            f"on the {axis} axis: one measures {_mm(granularity)}, the pattern area is "
            f"{_mm(available)}. Reduce the spacing, shorten the cycle, or drop the snap "
            "(§ 8.3)",
            field=f"pattern.snap.{axis}",
        )
    return whole


def _governing(periods: list[AxisPeriod], axis: str) -> AxisPeriod:
    """Which family decides for this axis (§ 8.3).

    Marked ones win. Failing that, families that agree need no mark — there is
    nothing to disambiguate. Only genuine disagreement is an error, and then it
    names the families rather than guessing.
    """
    marked = [period for period in periods if period.governing]
    if len(marked) == 1:
        return marked[0]
    if len(marked) > 1:
        raise DefinitionError(
            f"{len(marked)} families on the {axis} axis are marked `governing` "
            f"({', '.join(period.label for period in marked)}) — exactly one may be (§ 8.3)",
            field="families",
        )
    if len({(period.step_um, period.cycle_um) for period in periods}) == 1:
        return periods[0]
    raise DefinitionError(
        f"several families run along the {axis} axis and they do not agree on a period "
        f"({', '.join(period.label for period in periods)}) — mark one with "
        "`governing: true` to say which one decides (§ 8.3)",
        field="families",
    )


def page_contexts(
    *,
    count: int,
    names: list[str] | None = None,
    seed: int = 0,
    per_item: int = 1,
    snap: tuple[tuple[str, int], ...] = (),
) -> Iterator[PageContext]:
    """The page loop (§ 3.1): one context per sheet.

    `per_item` is how many sheets one entry of the run occupies (§ 7.5). It
    only affects the *name*: both sheets of a maze carry the same `{name}`,
    while the numbering counts sheets, as § 7.5 states outright. `snap` is the
    pixel-snapped axes (§ 8.3.1), the same on every page.
    """
    for index in range(count):
        yield PageContext(
            index=index,
            number=index + 1,
            count=count,
            name=names[(index // per_item) % len(names)] if names else None,
            is_even=(index + 1) % 2 == 0,
            seed_material=seed_material(seed, index),
            pixel_snap=snap,
        )


def seed_material(seed: int, index: int) -> bytes:
    """A stable hash over seed and page index (§ 3.3).

    Explicitly named and explicitly not Python's `hash()`: that is not
    guaranteed across versions and is process-dependent for strings, so the
    reproducibility promise of § 10.1 would break at the next Python release.
    Addition (`seed + i`) is no good either — some PRNGs correlate neighbouring
    pages seeded that way.
    """
    return hashlib.blake2b(f"{seed}:{index}".encode(), digest_size=32).digest()


_PLACEHOLDER = re.compile(r"\{([a-z_]*)\}")
_KNOWN = ("{name}", "{page}", "{page_count}", "{date}")


def resolve_placeholders(
    text: str,
    page: PageContext,
    *,
    field: str | None = None,
    extra: Mapping[str, str] | None = None,
) -> str:
    """Replace the four placeholders of § 8.10.

    They apply wherever the definition supplies free text — header and footer
    fields, and form titles — but never in counting patterns (§ 7.10), where
    `n`, `a` and `A` already count and a second substitution mechanism in the
    same string would be a trap.

    `extra` carries document-supplied placeholders — the calendar's `{year}`
    (§ 7) — which fill any key the four built-ins do not.
    """

    def replace(match: re.Match[str]) -> str:
        key = match.group(1)
        if extra and key in extra:
            return extra[key]
        if key == "page":
            return str(page.number)
        if key == "page_count":
            return str(page.count)
        if key == "date":
            # § 8.10: this makes the result depend on the day it was made. That
            # is the user's explicit choice, and the tool says so once per run.
            return datetime.date.today().isoformat()
        if key == "name":
            if page.name is None:
                raise DefinitionError(
                    "`{name}` needs a name list — pass one with --names (§ 9.4). "
                    "An empty header would be silent data loss",
                    field=field,
                )
            return page.name
        raise DefinitionError(
            f"unknown placeholder `{match.group(0)}` — known are {', '.join(_KNOWN)} (§ 8.10)",
            field=field,
        )

    return _PLACEHOLDER.sub(replace, text)


def preflight(
    document: Document,
    q: WriterQuery,
) -> tuple[Geometry, list[PageContext], list[list[Text]], list[Mark]]:
    """Measure every page before a single one is written (§ 12 point 13).

    With thirty names it is the seventeenth that does not fit. Checked during
    rendering, sixteen pages are already in the file by then — so the rule is
    abort completely or build completely.

    This is also what `ctrlgrid check` runs: the same work, minus the writing.
    """
    from ctrlgrid import generators
    from ctrlgrid.cover import cover_marks
    from ctrlgrid.document import is_document_generator
    from ctrlgrid.frame import layout_band

    blade = generators.get(document.generator)
    if is_document_generator(blade):
        return _document_preflight(document, blade, q)

    _refuse_snap_where_it_has_no_meaning(document, blade)
    plan = sheet_plan(document)
    _refuse_mirroring_that_cannot_line_up(document, plan)

    # Everything in the pre-flight is *measuring*, and only the writer knows
    # font metrics (§ 10.2). The PNG writer cannot answer — it has no font file
    # to measure against — so measuring uses a metrics oracle, and the real
    # writer is consulted only for its capabilities (§ 10.4). For PDF the two
    # are the same object.
    probe = _metrics_oracle(q)

    geometry = Geometry.of(
        document.sheet,
        header=document.header,
        footer=document.footer,
        pattern=document.pattern,
        blade_axes=document.axes,
        density=document.device.density if document.device else None,
    )
    # The blade's own pre-flight, once, against the area it will be handed
    # (§ 12 point 13). `polar` needs it for the two questions only the area can
    # answer: does the circle fit, and do the segment labels fit (§ 7.6).
    blade.check(document.config, area=geometry.area, q=probe)

    check_page_furniture(document, geometry, q=probe)
    check_text_glyphs(document, geometry, blade, q=probe)

    # § 10.2: what the writer cannot render is refused here, before a page is
    # written, naming the missing feature — the PNG writer's lack of text is
    # the first case this has ever caught.
    skipped = _refuse_marks_the_writer_cannot_render(document, geometry, blade, plan, q, probe)
    if skipped:
        geometry = replace(geometry, notices=geometry.notices + (skipped,))

    # § 12.1: the definition against the medium's resolution, once the medium
    # is fixed. A round-to-zero stroke raises here; the rest become notices,
    # and `--strict` (carried on the document) turns them into errors.
    from ctrlgrid.media import media_findings

    findings = media_findings(
        document,
        probe,
        strict=document.strict,
        snapped={axis for axis, _ in geometry.pixel_snap},
    )
    geometry = replace(geometry, notices=geometry.notices + tuple(findings))
    date_notice = _date_notice(document)
    if date_notice:
        geometry = replace(geometry, notices=geometry.notices + (date_notice,))

    contexts = list(
        page_contexts(
            count=document.pages.count * plan.per_item,
            names=document.names,
            per_item=plan.per_item,
            snap=geometry.pixel_snap,
        )
    )

    frames: list[list[Text]] = []
    for context in contexts:
        # Under duplex the bands move with the margins, so each page is
        # measured against the boxes it will actually be drawn in (§ 8.1).
        placed = geometry.for_page(
            is_even=context.is_even, sheet=document.sheet, duplex=document.page.duplex
        )
        marks: list[Text] = []
        if document.header and placed.header:
            marks += layout_band(
                document.header, placed.header, q=probe, page=context,
                section="header", sheet_width=document.sheet.width,
            )
        if document.footer and placed.footer:
            marks += layout_band(
                document.footer, placed.footer, q=probe, page=context,
                section="footer", sheet_width=document.sheet.width,
            )
        frames.append(marks)

    # Measured here too, and for the same reason: a format too narrow for the
    # 100 mm rule (§ 8.8) has to be refused before page one, not discovered
    # once the file is half written.
    cover = cover_marks(document, q=probe) if document.pages.cover else []

    # § 14: imposition never scales, so a page that does not fit its cell is an
    # error with the arithmetic — refused here, before anything is written.
    if document.nup is not None:
        document.nup.check_fits(document.sheet.width, document.sheet.height)

    return geometry, contexts, frames, cover


def sheet_plan(document: Document) -> SheetPlan:
    """What the blade says about sheets per item (§ 7.5). Usually nothing."""
    from ctrlgrid import generators

    blade = generators.get(document.generator)
    getter = getattr(blade, "sheets", None)
    return getter(document.config) if getter else SheetPlan()


def _refuse_mirroring_that_cannot_line_up(document: Document, plan: SheetPlan) -> None:
    """§ 7.5: `back_mirrored` and a shifting gutter cannot both be had.

    Under duplex the margins swap on even pages (§ 8.1), so the pattern area
    sits somewhere else on the back — and the solution would miss the maze by
    exactly that difference. Either the sides are symmetric or duplex is off.
    """
    margin = document.sheet.margin
    if not plan.mirrored or not document.page.duplex:
        return
    if margin.inner.um == margin.outer.um:
        return
    raise DefinitionError(
        f"`back_mirrored` needs the pattern area to sit in the same place on both "
        f"sides, but duplex is on and margin.inner ({margin.inner.raw}) differs from "
        f"margin.outer ({margin.outer.raw}) — the solution would land "
        f"{abs(margin.inner.um - margin.outer.um) / 1000:.1f}mm off the maze. Set "
        "duplex: false or make the two margins equal (§ 7.5, § 8.1)",
        field="page.duplex",
    )


#: Every capability a mark can call for (§ 10.2). A writer holding all of them
#: renders anything, so the check below can skip the sampling entirely.
_ALL_CAPABILITIES = {
    "vector", "color", "opacity", "arc", "polygon", "image_png", "text",
    # Not mark kinds: § 10.2 lists what `--skip-unsupported` leaves out as
    # "Links, Lesezeichen und den Anhang", and the wrapper below guards all
    # three. `outline` was missing here, so its guard could never fire — the
    # set had been extended for `attachment` and for `link` as each guard was
    # written, and this one was not.
    "attachment", "link", "outline",
}


def _def_filename(source: str) -> str:
    """A filename for the embedded definition (§ 8.8).

    The source's own basename — `my-grid.yaml` stays that. A preset name like
    `millimeter-a4` has no extension, so `.yaml` is added, otherwise a viewer
    would not know what it is opening.
    """
    name = Path(source).name
    if not Path(name).suffix:
        name = f"{name}.yaml"
    return name

_MARK_CAPABILITY = {
    Text: "text",
    Arc: "arc",
    Polygon: "polygon",
}


def _metrics_oracle(q: WriterQuery) -> WriterQuery:
    """A query that can answer font metrics (§ 10.2).

    Every measurement in the pre-flight needs them, and the PNG writer cannot
    give them — it has no font file. So when the real writer cannot measure
    text, a PDF writer stands in as a pure metrics oracle: it never opens a
    file, its font metrics are the fixed data of the PDF standard fonts, and
    nothing it returns depends on which writer will finally draw.
    """
    if "text" in q.capabilities():
        return q
    from ctrlgrid.writers.pdf import PdfWriter

    return PdfWriter("unused-metrics-only")


def _skipping_notice(missing: set[str]) -> str:
    """What `--skip-unsupported` left out, in the user's terms (§ 10.2, § 12)."""
    return (
        f"--skip-unsupported: leaving out {', '.join(sorted(missing))} — the writer "
        "cannot draw it, so those marks are not on the sheet at all (§ 10.2)"
    )


def _refuse_marks_the_writer_cannot_render(
    document: Document,
    geometry: Geometry,
    blade: object,
    plan: SheetPlan,
    writer: WriterQuery,
    probe: WriterQuery,
) -> str | None:
    """§ 10.2: refuse before rendering what the writer cannot draw, and name it.

    The vocabulary is complete from M1 and a writer grows into it; the missing
    feature is caught here rather than dropped mid-file. It samples one page's
    worth of marks with the metrics oracle — the marks themselves, not a guess
    from the config — so it is right for every blade without knowing any of them.
    """
    caps = writer.capabilities()
    if caps >= _ALL_CAPABILITIES:
        return None

    from ctrlgrid.frame import stamp_mark

    context = next(page_contexts(count=1, snap=geometry.pixel_snap))
    needed: set[str] = set()
    for mark in blade.generate(document.config, area=geometry.area, page=context, q=probe):
        needed.add(_MARK_CAPABILITY.get(type(mark), "vector"))
    if _band_has_text(document.header) or _band_has_text(document.footer):
        needed.add("text")
    if stamp_mark(document.stamp, document.sheet, q=probe) is not None:
        needed.add("text")
    if document.pages.cover:
        needed.add("text")  # the cover carries the calibration labels (§ 8.8)
    if document.pages.embed_def:
        needed.add("attachment")  # the def rides along as a file (§ 8.8)
    if document.ruler is not None:
        needed.add("text")  # the ruler's numbers are Text marks (§ 8.12)

    missing = needed - caps
    if not missing:
        return None
    if document.skip_unsupported:
        # § 10.2: leaving a feature out is the user's explicit decision, and it
        # is never silent — the run says what it dropped, once.
        return _skipping_notice(missing)
    if "text" in missing:
        hint = (
            " — the PNG writer has no font file to draw glyphs with (§ 10.4). Name a font "
            "file (`font: {file: ...}`), leave the text off, or output PDF instead"
        )
    elif "attachment" in missing:
        hint = (
            " — the PNG writer cannot carry a file. Drop `embed_def`, or output PDF, "
            "which embeds the definition as an attachment (§ 8.8)"
        )
    else:
        hint = " — output PDF, which renders the full mark vocabulary (§ 10.2)"
    raise DefinitionError(
        f"this run needs {', '.join(sorted(missing))} and the PNG writer does not "
        f"support it{hint}"
    )


def _band_has_text(band: Band | None) -> bool:
    if band is None:
        return False
    return any(isinstance(getattr(band, side), str) for side in ("left", "center", "right"))


def check_text_glyphs(
    document: Document, geometry: Geometry, blade: object, *, q: WriterQuery
) -> None:
    """Every glyph a generator draws must exist in the font (§ 12 point 13).

    § 12 point 13 asks the pre-flight to measure "Kopf-, Fuß- und
    Beschriftungstext" and then whether all glyphs are present. Only the bands
    were ever asked (`layout_band`), so a grid label, a segment label, a form
    title or a calendar's month name went unchecked — and the standard PDF fonts
    reach Latin-1 and no further (§ 10.3). `months: [styczeń, …]` therefore
    passed `check`, reported success, and put a box on the paper: the silent
    almost-right of § 5.1, in the one place the tool had a query built to
    prevent it.

    Characters are collected as a **set per font**, not strings: a year planner
    draws tens of thousands of them and has a few dozen distinct ones, so the
    cost is the walk and not the checking. For a document that walk is every
    page, for the same reason the media check walks every page (decision 49) — a
    month name only appears on its own month's pages.
    """
    from ctrlgrid.document import is_document_generator

    seen: dict[str, set[str]] = {}
    source: dict[tuple[str, str], str] = {}

    def take(mark: Mark) -> None:
        if not isinstance(mark, Text) or not mark.content:
            return
        chars = seen.setdefault(mark.family, set())
        for char in mark.content:
            if char not in chars:
                chars.add(char)
                source[(mark.family, char)] = mark.content

    if is_document_generator(blade):
        total = _document_page_total(blade, document, geometry)
        for index, page in enumerate(blade.pages(document.config, area=geometry.area, q=q)):
            for mark in document_page_marks(
                page, area=geometry.area, context=_document_context(index, total), q=q
            ):
                take(mark)
    else:
        context = next(page_contexts(count=1, snap=geometry.pixel_snap))
        for mark in blade.generate(document.config, area=geometry.area, page=context, q=q):
            take(mark)

    for family, chars in sorted(seen.items()):
        missing = q.missing_glyphs("".join(sorted(chars)), family=family)
        if not missing:
            continue
        where = source[(family, missing[0])]
        raise DefinitionError(
            f"{' '.join(missing)} — not covered by the font this generator draws with"
            f" (in {where!r}). The standard PDF fonts reach Latin-1 and no further,"
            " so Polish, Czech, Hungarian, Turkish and Romanian text needs a font of"
            " its own: name one with `font: {file: /path/to/font.ttf}` (§ 10.3)"
        )


def _refuse_snap_where_it_has_no_meaning(document: Document, blade: object) -> None:
    """§ 8.3: for some blades snapping is an error, never a guess.

    § 8.3 names them — `polar`, `staves`, `grid`, `maze`, `tiling`, `form` —
    and the reason is not that they have nothing to snap to but that snapping
    is not a thing their pattern does. That is a statement about the blade, so
    the blade makes it (`supports_snap`) and the handle acts on it here, before
    any geometry is computed and therefore before any half-fitting answer can
    be produced.
    """
    if getattr(blade, "supports_snap", True):
        return
    for axis in ("x", "y"):
        mode = getattr(document.pattern.snap, axis)
        if mode and mode != "none":
            raise DefinitionError(
                f"generator `{document.generator}` does not support snapping, and "
                f"pattern.snap asks for `{mode}`. Its pattern has a centre rather than "
                "an axis to snap to, so § 8.3 makes this an error instead of a guess — "
                "remove pattern.snap",
                field="pattern.snap",
            )


def _attachment(document: Document) -> Attachment | None:
    """The embedded-def attachment, or None (§ 8.8). Shared by both write paths."""
    if not document.pages.embed_def:
        return None
    # The exact bytes the user wrote, so a sheet reproduces itself years later.
    return Attachment(
        filename=_def_filename(document.source),
        data=document.source_text.encode("utf-8"),
        description="ctrlgrid definition — this document's own source (§ 8.8)",
    )


def _date_notice(document: Document) -> str | None:
    """§ 8.10's second demand about `{date}`, which had never been built.

    The first — that `{date}` is allowed and makes the result depend on the day
    it was made — was. The second is that the tool **says so once per run**,
    because otherwise a definition in version control quietly produces different
    bytes tomorrow and the byte comparison that guards this project's own
    gallery fails with nothing to explain it. The comment beside the
    substitution claimed this notice existed; it did not.
    """
    fields = []
    for band in (document.header, document.footer):
        if band is None:
            continue
        fields += [band.left, band.center, band.right]
    if any(isinstance(value, str) and "{date}" in value for value in fields):
        return (
            "{date} makes this run depend on the day it was made — the same definition "
            "will produce different bytes tomorrow (§ 8.10). Write the date as text if "
            "you want the sheet to be reproducible"
        )
    return None


def _refuse_what_a_document_has_no_page_loop_for(document: Document) -> None:
    """Three settings a document generator cannot honour — said, not ignored.

    Decision 42 settled that a document takes its own write path: no cover, no
    imposition, no snap. What it did not settle is what happens when a run asks
    for one anyway, and the answer had been *nothing*. `--nup` was worse than
    silent — `cli` printed the imposition summary from `document.nup` without
    asking whether it had been applied, so the run reported four-up on a sheet
    of plain pages. § 12 counts a report that misleads as worse than none.

    So each is refused by name, before page one, which is what the deferred-key
    machinery of § 5.1 exists for: a key the tool does not honour never reads as
    though it worked.
    """
    if document.nup is not None:
        raise DefinitionError(
            f"generator `{document.generator}` writes its own pages, and imposition "
            "works on a page loop it does not have (§ 14). Its links and bookmarks "
            "would not survive being imposed either — drop --nup, or impose the "
            "finished PDF with a separate tool",
            field="nup",
        )
    if document.pages.cover:
        raise DefinitionError(
            f"generator `{document.generator}` writes its own pages, so there is no "
            "cover sheet to add in front of them (§ 8.8) — drop --cover. A document's "
            "own title page is the place for that (§ 7.12, § 7.13)",
            field="pages.cover",
        )
    if document.pattern.align != "bottom-left":
        raise DefinitionError(
            f"pattern.align asks for `{document.pattern.align}`, and generator "
            f"`{document.generator}` has no single pattern to anchor — it owns its "
            "pages, each laid out on its own (§ 8.5, § 7.13). Remove pattern.align",
            field="pattern.align",
        )


def check_page_furniture(document: Document, geometry: Geometry, *, q: WriterQuery) -> None:
    """Refuse the frame that cannot fit, before page one (§ 12 point 13).

    The counterpart of `page_furniture`, and it exists for the same reason. That
    function unified what the two page paths *draw*; the checking stayed in two
    places, and the document path promptly went without — so a notebook drew a
    ruler whose strip does not fit the margin while the blade path refused the
    identical page. Drawing and checking are one feature and belong to one pair
    of functions, both called from both paths.

    Under duplex the margins swap, so both sides of the sheet are asked (§ 8.1).
    """
    from ctrlgrid.frame import check_rulers

    for is_even in ((False, True) if document.page.duplex else (False,)):
        check_rulers(
            document.ruler,
            geometry.for_page(
                is_even=is_even, sheet=document.sheet, duplex=document.page.duplex
            ),
            document,
            q=q,
        )


def _document_preflight(
    document: Document, blade: object, q: WriterQuery
) -> tuple[Geometry, list[PageContext], list[list[Text]], list[Mark]]:
    """Measure and validate a document generator (§ 7), the calendar's path.

    None of the blade-specific machinery applies — no snap, no sheet plan, no
    page cycle, no cover: a document owns its own pages. What *does* apply is
    everything about the page itself: it measures the pattern area every page is
    handed, runs the generator's own `check`, checks the frame furniture with
    `check_page_furniture` exactly as the blade path does, lays out the bands per
    page, and refuses on a writer that cannot carry its links or text (§ 10.2). Returns the
    same tuple shape as `preflight` so `check` and `build` share one entry point;
    the three page-loop lists are empty because a document does not use them.
    """
    _refuse_what_a_document_has_no_page_loop_for(document)
    probe = _metrics_oracle(q)
    geometry = Geometry.of(
        document.sheet,
        header=document.header,
        footer=document.footer,
        pattern=document.pattern,
        blade_axes=document.axes,
        density=document.device.density if document.device else None,
    )
    blade.check(document.config, area=geometry.area, q=probe)
    check_page_furniture(document, geometry, q=probe)
    check_text_glyphs(document, geometry, blade, q=probe)
    skipped = _refuse_writer_cannot_render_document(document, blade, geometry, q, probe)
    if skipped:
        geometry = replace(geometry, notices=geometry.notices + (skipped,))

    # § 12.1 reaches a document too: its pages are walked for the weights and
    # colours the medium has to carry. A round-to-zero stroke raises, the rest
    # become notices, and `--strict` turns them into errors — the same
    # treatment the blade path gets, from the same function.
    from ctrlgrid.media import media_findings

    findings = media_findings(document, probe, strict=document.strict)
    geometry = replace(geometry, notices=geometry.notices + tuple(findings))
    date_notice = _date_notice(document)
    if date_notice:
        geometry = replace(geometry, notices=geometry.notices + (date_notice,))

    # The bands are laid out **per page** when they are written (§ 8.10:
    # placeholders are filled per page, and this path was the one exception).
    # So they are measured per page here too: with `{page}` and `{section}` in
    # them it is the last page that overflows, not the first, and § 12 point 13
    # allows no half-written document. Skipped outright when the document has
    # no bands, which is the common case and the whole cost.
    if document.header is not None or document.footer is not None:
        total = _document_page_total(blade, document, geometry)
        for index, page in enumerate(
            blade.pages(document.config, area=geometry.area, q=probe)
        ):
            document_bands(
                document, geometry, blade, _document_context(index, total), q=probe, page=page
            )
    return geometry, [], [], []


def _document_page_total(blade: object, document: Document, geometry: Geometry) -> int:
    """How many pages the document will have (§ 8.10's `{page_count}`).

    Part of the document seam, not a convenience: asking the generator is the
    only way that does not generate every page twice.
    """
    if not hasattr(blade, "page_count"):
        raise AssertionError(
            f"the document generator `{blade.name}` has no `page_count` — it is part "
            "of the seam (§ 7), because {page_count} and the run report both need it"
        )
    return blade.page_count(document.config, area=geometry.area)


def _document_context(index: int, total: int) -> PageContext:
    """The page context a document's bands are filled against (§ 8.10)."""
    return PageContext(
        index=index, number=index + 1, count=total, name=None, is_even=index % 2 == 1,
        seed_material=b"",
    )


def document_page_marks(
    page: DocumentPage, *, area: Area, context: PageContext, q: WriterQuery
) -> Iterator[Mark]:
    """What is on one document page: its own marks, then its fill's (§ 7.13).

    One function, because three callers ask the same question — the writer, the
    capability pre-flight and the media check — and three answers would drift
    apart the first time a page kind changed.

    The blade is called here, on the handle's side: a document generator names
    a generator and its config and never reaches into one (§ 3.3).
    """
    yield from page.marks
    if page.fill is not None:
        from ctrlgrid import generators

        blade = generators.get(page.fill.generator)
        yield from blade.generate(page.fill.config, area=area, page=context, q=q)


def document_bands(
    document: Document,
    geometry: Geometry,
    blade: object,
    context: PageContext,
    *,
    q: WriterQuery,
    page: DocumentPage | None = None,
) -> tuple[list[Text], list[Text]]:
    """The header and footer of one document page (§ 7, § 8.10).

    Two kinds of placeholder meet here: the generator's document-wide ones
    (`{year}`) and the page's own (`{section}`) — only the generator knows
    which section a page belongs to, and only the handle knows its number.
    """
    from ctrlgrid.frame import layout_band

    extra = dict(blade.placeholders(document.config)) if hasattr(blade, "placeholders") else {}
    if page is not None:
        extra.update(dict(page.placeholders))
    header_marks: list[Text] = []
    footer_marks: list[Text] = []
    if document.header and geometry.header:
        header_marks += layout_band(
            document.header, geometry.header, q=q, page=context,
            section="header", sheet_width=document.sheet.width, extra=extra,
        )
    if document.footer and geometry.footer:
        footer_marks += layout_band(
            document.footer, geometry.footer, q=q, page=context,
            section="footer", sheet_width=document.sheet.width, extra=extra,
        )
    return header_marks, footer_marks


def _refuse_writer_cannot_render_document(
    document: Document, blade: object, geometry: Geometry, writer: WriterQuery, probe: WriterQuery
) -> str | None:
    """§ 10.2 for a document: refuse before page one what the writer cannot do.

    A document navigates by links, so it always needs `link`; the first page's
    marks say what else (text, above all). The PNG writer has neither, so a
    calendar to PNG is refused by name, with the way out — the same rule that
    refuses text on PNG for a blade.
    """
    caps = writer.capabilities()
    if caps >= _ALL_CAPABILITIES:
        return None
    needed = {"link"}
    first = next(iter(blade.pages(document.config, area=geometry.area, q=probe)), None)
    if first is not None:
        context = _document_context(0, 1)
        for mark in document_page_marks(
            first, area=geometry.area, context=context, q=probe
        ):
            needed.add(_MARK_CAPABILITY.get(type(mark), "vector"))
    missing = needed - caps
    if not missing:
        return None
    if document.skip_unsupported:
        return _skipping_notice(missing)
    raise DefinitionError(
        f"this run needs {', '.join(sorted(missing))} and the PNG writer does not "
        "support it — a calendar's links and text need a PDF; output PDF instead (§ 10.2)"
    )


def _document_content(
    document: Document,
    page: DocumentPage,
    geometry: Geometry,
    context: PageContext,
    ox: Um,
    oy: Um,
    q: WriterQuery,
) -> Iterator[Mark]:
    """A document page's own layer: its full-sheet fills, then its marks.

    These sit between the definition's `page.background` and the frame, which
    is what `page_furniture` calls `content` — the title page's colour must
    cover the sheet's, and the frame must sit over both (§ 7.12).
    """
    if page.background:
        yield Polygon(
            points=(
                Point(0, 0), Point(document.sheet.width, 0),
                Point(document.sheet.width, document.sheet.height),
                Point(0, document.sheet.height),
            ),
            closed=True, weight=0.0, fill_color=page.background,
        )
    # ...then the background image over it, so its transparent areas show the
    # colour through (§ 7.12). Validated in the pre-flight, so no raise here.
    if page.background_image:
        from ctrlgrid.images import load_image

        image = load_image(page.background_image, field="title_page.background_image")
        x, y, w, h = background_image_rect(
            document.sheet.width, document.sheet.height, image.aspect, page.background_fit
        )
        yield Image(pos=Point(x, y), width=w, height=h, source=str(image.path))
    for mark in document_page_marks(page, area=geometry.area, context=context, q=q):
        yield translate(mark, dx=ox, dy=oy)


def _build_document(
    document: Document, blade: object, writer: Writer, geometry: Geometry,
) -> Geometry:
    """Write a document generator's pages (§ 7). Nothing here may raise on user
    input — the pre-flight has already measured and refused (§ 12 point 13).

    Each page's marks and links come in area-local coordinates (§ 3.3); the
    handle translates both onto the sheet by the one origin the geometry holds,
    exactly as the blade path does. The destination is defined before the marks,
    so links from other pages resolve to it.

    The bands are laid out **per page**, not once for the run: `{page}` counts
    and `{section}` names the section a page belongs to (§ 8.10, § 7.13). And the
    geometry is taken per page too, because under duplex the margins swap and a
    notebook is a bound book (§ 8.1). Everything around a page's own marks —
    background, border, hole marks, ruler, bands, stamp — comes from
    `page_furniture`, the one function the blade path uses as well.
    """
    writer.begin_document(
        DocumentMeta(title=f"ctrlgrid {document.source}", attachment=_attachment(document))
    )
    # Bands are *measured* with the metrics oracle, never with the writer: the
    # numbers are the same either way (§ 10.2), and a writer that cannot answer
    # would break a path the pre-flight already approved.
    probe = _metrics_oracle(writer)
    total = _document_page_total(blade, document, geometry)
    # The pages are measured with the oracle, not with the writer: a generator
    # asking for text metrics must get the same numbers whatever will finally
    # draw them (§ 10.2), and a writer that cannot answer must not break a run
    # the pre-flight approved — which is what `--skip-unsupported` needs.
    for index, page in enumerate(blade.pages(document.config, area=geometry.area, q=probe)):
        context = _document_context(index, total)
        # The geometry of *this* sheet side: under duplex the margins swap, and
        # a document is the artefact that needs it most — a notebook is bound
        # (§ 8.1). This path used one origin for the whole run and so printed
        # every page as if it were a front.
        placed = geometry.for_page(
            is_even=context.is_even, sheet=document.sheet, duplex=document.page.duplex
        )
        ox, oy = placed.origin.x, placed.origin.y
        header_marks, footer_marks = document_bands(
            document, placed, blade, context, q=probe, page=page
        )
        bands: list[Mark] = []
        if page.show_header:
            bands += header_marks
        if page.show_footer:
            bands += footer_marks
        writer.begin_page(document.sheet.width, document.sheet.height)
        writer.define_dest(page.dest)
        for mark in page_furniture(
            document,
            placed,
            is_even=context.is_even,
            content=_document_content(document, page, geometry, context, ox, oy, probe),
            bands=bands,
            q=probe,
        ):
            writer.draw(mark)
        for link in page.links:
            writer.link(
                Point(link.lower_left.x + ox, link.lower_left.y + oy),
                Point(link.upper_right.x + ox, link.upper_right.y + oy),
                link.target,
            )
        if page.title:
            writer.outline(page.title, index=index)
        writer.end_page()
    writer.end_document()
    return geometry


class _LeavingOutWhatItCannotDraw:
    """A writer that drops what it cannot render, instead of the run being
    refused (§ 10.2, `--skip-unsupported`).

    A wrapper rather than a check at every `writer.draw(...)`: there are a dozen
    of those and one would eventually be forgotten (§ 5.1). Everything it does
    not override is forwarded untouched, so it stays a writer in every other
    respect — including as a metrics oracle.
    """

    def __init__(self, writer: Writer) -> None:
        self._writer = writer
        self._missing = _ALL_CAPABILITIES - writer.capabilities()

    def __getattr__(self, name: str):
        return getattr(self._writer, name)

    def draw(self, mark: Mark) -> None:
        if _MARK_CAPABILITY.get(type(mark), "vector") in self._missing:
            return
        self._writer.draw(mark)

    def link(self, lower_left, upper_right, target) -> None:
        if "link" in self._missing:
            return
        self._writer.link(lower_left, upper_right, target)

    def outline(self, title: str, *, index: int) -> None:
        if "outline" in self._missing:
            return
        self._writer.outline(title, index=index)

    def begin_document(self, meta: DocumentMeta) -> None:
        if meta.attachment is not None and "attachment" in self._missing:
            meta = replace(meta, attachment=None)
        self._writer.begin_document(meta)


def build(document: Document, writer: Writer) -> Geometry:
    """The page loop (§ 3.1): measure everything, then write everything.

    The two halves are not an implementation detail. § 12 point 13 requires all
    pages to be measured *before* the first one is written: with thirty names
    the seventeenth is the one that does not fit, and finding out during
    rendering leaves sixteen pages already in the file. Abort completely or
    build completely.

    Returns the geometry it built on, so the caller can report what the run
    settled on — including any notice the settings earned (§ 8.3).
    """
    from ctrlgrid import generators
    from ctrlgrid.document import is_document_generator

    geometry, contexts, frames, cover = preflight(document, writer)
    if document.skip_unsupported:
        # § 10.2: the pre-flight has already said what will be left out; from
        # here on the writer simply leaves it out.
        writer = _LeavingOutWhatItCannotDraw(writer)

    blade = generators.get(document.generator)

    # § 7: a document generator owns its own heterogeneous, linked pages, so it
    # takes a separate write path — no cover, no imposition, no cycle. It keeps
    # the optional header/footer, laid out per page as it writes (§ 8.10).
    if is_document_generator(blade):
        return _build_document(document, blade, writer, geometry)

    plan = sheet_plan(document)

    # Pass two — write. Nothing below this line may raise on user input.
    writer.begin_document(
        DocumentMeta(title=f"ctrlgrid {document.source}", attachment=_attachment(document))
    )

    # § 8.8: an additional first page, outside the numbering and outside the
    # page loop entirely — it gets no background, no pattern, no frame, no
    # stamp, and no `PageContext`. It is also exempt from imposition (§ 14):
    # the calibration square is a real 50 mm, so it keeps the page size.
    if cover:
        writer.begin_page(document.sheet.width, document.sheet.height)
        for mark in cover:
            writer.draw(mark)
        writer.end_page()

    rendered = [
        (context, list(_page_marks(document, geometry, blade, plan, context, frame, writer)))
        for context, frame in zip(contexts, frames, strict=True)
    ]

    if document.nup is None:
        _write_one_per_sheet(document, writer, rendered)
    else:
        _write_imposed(document, writer, rendered, document.nup)

    writer.end_document()
    return geometry


def _page_marks(
    document: Document,
    geometry: Geometry,
    blade: object,
    plan: SheetPlan,
    context: PageContext,
    frame: list[Text],
    q: WriterQuery,
) -> Iterator[Mark]:
    """Every mark of one logical page, in sheet coordinates (§ 3.6).

    This is what "imposition works on finished pages" (§ 14) means in practice:
    a page is rendered whole, into the small sheet's coordinates, and whether it
    then lands on its own sheet or in a cell of a larger one is a separate,
    later decision that only translates it.
    """
    placed = geometry.for_page(
        is_even=context.is_even, sheet=document.sheet, duplex=document.page.duplex
    )
    yield from page_furniture(
        document,
        placed,
        is_even=context.is_even,
        content=_pattern_marks(document, placed, blade, plan, context, q),
        bands=frame,
        q=q,
    )


def _pattern_marks(
    document: Document,
    placed: Geometry,
    blade: object,
    plan: SheetPlan,
    context: PageContext,
    q: WriterQuery,
) -> Iterator[Mark]:
    """The blade's own marks, mirrored and moved into sheet coordinates."""
    # § 7.5's `back_mirrored` is the one exception to a blade never knowing
    # which side of the sheet it is on: the handle mirrors, about the sheet's
    # centre (the physical turning edge), and only the pattern layer so header
    # and footer stay readable on the back.
    mirrored = (context.index % plan.per_item) in plan.mirrored
    # § 8.5: `pattern.align` reflects the pattern within its own area so its
    # cycle counts from the chosen corner. Done here, in local coordinates,
    # before the mark ever reaches sheet space — the blade stays unaware (§ 3.3).
    align = document.pattern.align
    flip_x = "right" in align
    flip_y = "top" in align
    for mark in blade.generate(document.config, area=placed.area, page=context, q=q):
        if flip_y:
            mark = mirror_y(mark, about=placed.area.height)
        if flip_x:
            mark = mirror_x(mark, about=placed.area.width)
        placed_mark = translate(mark, dx=placed.origin.x, dy=placed.origin.y)
        if mirrored:
            placed_mark = mirror_x(placed_mark, about=document.sheet.width)
        yield placed_mark


def page_furniture(
    document: Document,
    placed: Geometry,
    *,
    is_even: bool,
    content: Iterable[Mark],
    bands: Iterable[Mark],
    q: WriterQuery,
) -> Iterator[Mark]:
    """Everything the handle draws around one page's own marks (§ 8.1).

    **One function, because there are two page paths.** The frame belongs to the
    *page* — § 8.1 puts background, border, hole marks, the edge ruler and the
    stamp there, not in the pattern — and a document generator owns pages just
    as the page loop does. `_build_document` was written without this and drew
    none of them for two whole generators, while the loader went on accepting
    every key: a notebook with `hole_marks: true` validated, reported success,
    and came out unpunched. § 5.1 calls that the worst failure class there is.

    The lesson is this codebase's own, three times over — `layout_band`, the
    writer wrapper and `document_page_marks` all exist because one site out of
    several is eventually forgotten. So a feature added here now reaches both
    paths or neither.

    Marks arrive in layer order and the writer does not sort (§ 3.6), so this
    sequence *is* the stacking: background, content, frame, bands, stamp.
    `placed` is the geometry of *this* sheet side, so everything follows the
    pattern area when duplex moves it (§ 8.1, § 8.12).
    """
    from ctrlgrid.frame import (
        background_mark,
        border_mark,
        hole_marks,
        ruler_marks,
        stamp_mark,
    )

    background = background_mark(document.page.background, document.sheet)
    if background is not None:
        yield background

    yield from content

    border = border_mark(document.border, placed)
    if border is not None:
        yield border
    yield from hole_marks(document.page, document.sheet, is_even=is_even)
    # `placed` and not the run's geometry: the scale measures the area *this*
    # page got, and under duplex that area sits on the other side of the sheet.
    yield from ruler_marks(document.ruler, placed, q=q, align=document.pattern.align)
    yield from bands

    stamp = stamp_mark(document.stamp, document.sheet, q=q)
    if stamp is not None:
        yield stamp


def _write_one_per_sheet(
    document: Document, writer: Writer, rendered: list[tuple[PageContext, list[Mark]]]
) -> None:
    """The ordinary run: one logical page per physical sheet."""
    for context, marks in rendered:
        writer.begin_page(document.sheet.width, document.sheet.height)
        if context.name is not None:
            # § 10.1: a data-driven run gets a table of contents, so a
            # thirty-page document can be navigated instead of scrolled.
            writer.outline(context.name, index=context.index)
        for mark in marks:
            writer.draw(mark)
        writer.end_page()


def _write_imposed(
    document: Document,
    writer: Writer,
    rendered: list[tuple[PageContext, list[Mark]]],
    nup: Imposition,
) -> None:
    """N-up: whole pages translated onto a larger sheet, never scaled (§ 14).

    Bookmarks are dropped here on purpose. § 14 notes that imposition destroys
    links and outlines, and a per-page bookmark would point at a whole imposed
    sheet rather than the page — worse than none. Whoever needs both builds the
    outline after imposing.
    """
    page_w, page_h = document.sheet.width, document.sheet.height
    for sheet in slots(len(rendered), nup):
        writer.begin_page(nup.sheet_width, nup.sheet_height)
        for position, index in enumerate(sheet):
            if index is None:
                continue
            cell = nup.cell(position, page_w, page_h)
            for mark in rendered[index][1]:
                writer.draw(translate(mark, dx=cell.x, dy=cell.y))
        for mark in nup.crop_mark_segments(page_w, page_h):
            writer.draw(mark)
        writer.end_page()


def _no_room(
    dimension: str,
    sheet: Um,
    deductions: list[tuple[str, Um]],
    result: Um,
) -> DefinitionError:
    """Show the arithmetic item by item (§ 12 point 9)."""
    lines = [f"  page {dimension:<6} {_mm(sheet):>10}"]
    lines += [f"  - {name:<12} {_mm(value):>10}" for name, value in deductions if value]
    lines.append(f"  = pattern {dimension:<3} {_mm(result):>10}")
    return DefinitionError(
        f"nothing is left of the pattern area in the {dimension} (§ 8.1):\n"
        + "\n".join(lines)
        + "\nReduce a margin, a band height or a gap."
    )


def _mm(um: Um) -> str:
    return f"{um / 1000:.1f}mm"
