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
from collections.abc import Iterator
from dataclasses import dataclass
from typing import TYPE_CHECKING

from ctrlgrid.axes import AxisPeriod
from ctrlgrid.errors import DefinitionError
from ctrlgrid.marks import Area, Point, Text, Um, translate
from ctrlgrid.model import Band, Margin, PatternSpec
from ctrlgrid.writers import DocumentMeta, Writer, WriterQuery

if TYPE_CHECKING:  # `loader` imports `Sheet` from here, so the arrow points one way
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


@dataclass(frozen=True, slots=True)
class Sheet:
    """The physical page after orientation has been applied (§ 9.1)."""

    width: Um
    height: Um
    margin: Margin


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

    @classmethod
    def of(
        cls,
        sheet: Sheet,
        *,
        header: Band | None,
        footer: Band | None,
        pattern: PatternSpec | None = None,
        blade_axes: dict[str, list[AxisPeriod]] | None = None,
    ) -> Geometry:
        """Work out § 8.1, and refuse with the arithmetic if nothing is left."""
        margin = sheet.margin
        header_height = header.height.um if header else 0
        header_gap = header.gap.um if header else 0
        footer_height = footer.height.um if footer else 0
        footer_gap = footer.gap.um if footer else 0

        width = sheet.width - margin.inner.um - margin.outer.um
        height = (
            sheet.height
            - margin.top.um
            - margin.bottom.um
            - header_height
            - header_gap
            - footer_height
            - footer_gap
        )

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
        inner_width, shift_x = place_pattern(width, "x", pattern, blade_axes, notices)
        inner_height, shift_y = place_pattern(height, "y", pattern, blade_axes, notices)

        return cls(
            notices=tuple(notices),
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


def _snap(available: Um, mode: str, period: AxisPeriod, axis: str) -> Um:
    """How much room the pattern may use after snapping (§ 8.3)."""
    if mode == "none":
        return available
    if mode == "pixel":
        # § 8.3.1: only ever legal with a device profile. On paper it stays an
        # error for good — `assumed_dpi` (§ 9.1) is a yardstick for warnings,
        # and geometry must never rest on a guessed number.
        raise DefinitionError(
            "`snap: pixel` needs a device profile: it rounds to whole device pixels, "
            "and on a paper format there is no real resolution to round to — "
            "`assumed_dpi` only feeds the media check (§ 8.3.1, § 9.1). "
            "Device profiles arrive with milestone M5",
            field=f"pattern.snap.{axis}",
        )

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
) -> Iterator[PageContext]:
    """The page loop (§ 3.1): one context per sheet."""
    for index in range(count):
        yield PageContext(
            index=index,
            number=index + 1,
            count=count,
            name=names[index % len(names)] if names else None,
            is_even=(index + 1) % 2 == 0,
            seed_material=seed_material(seed, index),
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


def resolve_placeholders(text: str, page: PageContext, *, field: str | None = None) -> str:
    """Replace the four placeholders of § 8.10.

    They apply wherever the definition supplies free text — header and footer
    fields, and form titles — but never in counting patterns (§ 7.10), where
    `n`, `a` and `A` already count and a second substitution mechanism in the
    same string would be a trap.
    """

    def replace(match: re.Match[str]) -> str:
        key = match.group(1)
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
) -> tuple[Geometry, list[PageContext], list[list[Text]]]:
    """Measure every page before a single one is written (§ 12 point 13).

    With thirty names it is the seventeenth that does not fit. Checked during
    rendering, sixteen pages are already in the file by then — so the rule is
    abort completely or build completely.

    This is also what `ctrlgrid check` runs: the same work, minus the writing.
    """
    from ctrlgrid.frame import layout_band

    geometry = Geometry.of(
        document.sheet,
        header=document.header,
        footer=document.footer,
        pattern=document.pattern,
        blade_axes=document.axes,
    )
    contexts = list(page_contexts(count=document.pages.count, names=document.names))

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
                document.header, placed.header, q=q, page=context, section="header"
            )
        if document.footer and placed.footer:
            marks += layout_band(
                document.footer, placed.footer, q=q, page=context, section="footer"
            )
        frames.append(marks)
    return geometry, contexts, frames


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

    geometry, contexts, frames = preflight(document, writer)
    blade = generators.get(document.generator)

    # Pass two — write. Nothing below this line may raise on user input.
    writer.begin_document(DocumentMeta(title=f"ctrlgrid {document.source}"))
    for context, frame in zip(contexts, frames, strict=True):
        writer.begin_page(document.sheet.width, document.sheet.height)
        if context.name is not None:
            # § 10.1: a data-driven run gets a table of contents, so a
            # thirty-page document can be navigated instead of scrolled.
            writer.outline(context.name, index=context.index)
        placed = geometry.for_page(
            is_even=context.is_even, sheet=document.sheet, duplex=document.page.duplex
        )
        # Marks arrive in layer order; the writer does not sort (§ 3.6). The
        # blade is handed the same area every time and never learns which side
        # of the sheet it is on — only the shift below differs (§ 3.3, § 6).
        for mark in blade.generate(document.config, area=placed.area, page=context, q=writer):
            writer.draw(translate(mark, dx=placed.origin.x, dy=placed.origin.y))
        for mark in frame:
            writer.draw(mark)
        writer.end_page()
    writer.end_document()
    return geometry


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
