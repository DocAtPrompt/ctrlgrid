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

from ctrlgrid.errors import DefinitionError
from ctrlgrid.marks import Area, Point, Text, Um, translate
from ctrlgrid.model import Band, Margin
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

    @classmethod
    def of(cls, sheet: Sheet, *, header: Band | None, footer: Band | None) -> Geometry:
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

        return cls(
            area=Area(width=width, height=height),
            origin=Point(left, bottom),
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
    *,
    names: list[str] | None = None,
) -> tuple[Geometry, list[PageContext], list[list[Text]]]:
    """Measure every page before a single one is written (§ 12 point 13).

    With thirty names it is the seventeenth that does not fit. Checked during
    rendering, sixteen pages are already in the file by then — so the rule is
    abort completely or build completely.

    This is also what `ctrlgrid check` runs: the same work, minus the writing.
    """
    from ctrlgrid.frame import layout_band

    geometry = Geometry.of(document.sheet, header=document.header, footer=document.footer)
    contexts = list(page_contexts(count=document.pages.count, names=names))

    frames: list[list[Text]] = []
    for context in contexts:
        marks: list[Text] = []
        if document.header and geometry.header:
            marks += layout_band(
                document.header, geometry.header, q=q, page=context, section="header"
            )
        if document.footer and geometry.footer:
            marks += layout_band(
                document.footer, geometry.footer, q=q, page=context, section="footer"
            )
        frames.append(marks)
    return geometry, contexts, frames


def build(document: Document, writer: Writer, *, names: list[str] | None = None) -> int:
    """The page loop (§ 3.1): measure everything, then write everything.

    The two halves are not an implementation detail. § 12 point 13 requires all
    pages to be measured *before* the first one is written: with thirty names
    the seventeenth is the one that does not fit, and finding out during
    rendering leaves sixteen pages already in the file. Abort completely or
    build completely.

    Returns the number of pages written.
    """
    from ctrlgrid import generators

    geometry, contexts, frames = preflight(document, writer, names=names)
    blade = generators.get(document.generator)

    # Pass two — write. Nothing below this line may raise on user input.
    writer.begin_document(DocumentMeta(title=f"ctrlgrid {document.source}"))
    for context, frame in zip(contexts, frames, strict=True):
        writer.begin_page(document.sheet.width, document.sheet.height)
        # Marks arrive in layer order; the writer does not sort (§ 3.6).
        for mark in blade.generate(document.config, area=geometry.area, page=context, q=writer):
            writer.draw(translate(mark, dx=geometry.origin.x, dy=geometry.origin.y))
        for mark in frame:
            writer.draw(mark)
        writer.end_page()
    writer.end_document()
    return len(contexts)


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
