"""The document-generator seam (§ 7) — `calendar` and `notebook` stand on it.

An ordinary generator (a *blade*) fills one pattern area and knows nothing of
pages (§ 3.3). A **document generator** is the opposite: it owns pages and their
links. So instead of `generate(cfg, area, page, q) -> marks` it offers
`pages(cfg, area, q) -> Iterator[DocumentPage]`, a sequence of typed pages, each
carrying its own marks (the six primitives, area-local), its link rectangles and
its destination key.

The handle (`pages.build`) detects a document generator by the presence of
`pages` and runs a *document mode*: for each page it takes that sheet side's
geometry (duplex swaps the margins), lays out the bands, sets the page size,
defines the destination, and draws — the page's own full-sheet colour and
image, its marks or the blade that fills it, and everything `page_furniture`
puts around them — then the links and the bookmark, and moves on. Existing
blades are untouched: they keep `generate` exactly as it is. Everything about
page geometry still stays on the handle side — the generator is handed the same
pattern area every blade gets and translates nothing itself (§ 3.3).

Links are annotations, not drawing primitives, so — like the bookmark
`outline()` — they live outside the six primitives (§ 6). A `Link` names two
corners in area-local micrometres and a destination key; its *visible* part is an
ordinary `Text` mark plus a `Segment` underline the page also emits (minimal ink
and bytes).
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel

from ctrlgrid.marks import Area, Mark, Point
from ctrlgrid.writers import WriterQuery


@dataclass(frozen=True, slots=True)
class Link:
    """A tappable rectangle jumping to a named destination (§ 10.2).

    `lower_left` and `upper_right` are two corners in the page's area-local
    micrometres; the handle translates them onto the sheet exactly as it does
    the marks. `target` is the `dest` of the page to jump to.
    """

    lower_left: Point
    upper_right: Point
    target: str


@dataclass(frozen=True, slots=True)
class Fill:
    """A page a blade fills, instead of the document drawing it (§ 7.13).

    The document names the generator and the config it has already validated;
    the **handle** calls the blade, exactly as it does on the ordinary page
    path. That is the whole seam of the notebook: a document that composes
    blades never touches one, so geometry, page context and every future handle
    feature go on living on the handle's side of the line (§ 3.3).
    """

    generator: str
    config: Any


@dataclass(frozen=True, slots=True)
class DocumentPage:
    """One page a document generator produces.

    `marks` are materialised per page (a page is bounded, unlike the whole
    document), the same way the blade path already lists one page's marks before
    writing it. `dest` is this page's destination key, referenced by links from
    other pages; `kind` names the page type for the run report and tests.
    """

    dest: str
    kind: str
    marks: tuple[Mark, ...]
    links: tuple[Link, ...] = ()
    fill: Fill | None = None
    """A blade that fills this page (§ 7.13).

    Drawn **after** the page's own marks, and so over them: `document_page_marks`
    yields `marks` first and the writer does not sort (§ 3.6). No page uses both
    today — a filled page carries no marks of its own — but the order is the one
    that holds if one ever does."""
    title: str | None = None
    background: str | None = None
    """A full-sheet colour fill painted under everything — the title page's
    colour (§ 7). The handle paints it, because only it knows the sheet
    (§ 3.3); the generator just names the colour."""
    background_image: str | None = None
    """A resolved PNG path painted full-sheet over the colour, so transparent
    areas show the colour through (§ 7.12). Handle-drawn like the colour."""
    background_fit: str = "cover"
    """`cover` (fill, crop overflow) or `contain` (fit inside) for the image."""
    show_header: bool = True
    """Draw the document's header band on this page (§ 7.12). The title page
    turns it off unless it opts back in — which only the calendar's title page
    can do; the notebook's has no such key and always hides both (§ 7.13)."""
    show_footer: bool = True
    """Draw the document's footer band on this page (§ 7.12)."""

    placeholders: tuple[tuple[str, str], ...] = ()
    """Per-page band placeholders, as pairs (§ 8.10, § 7.13).

    `{section}` in a notebook is the case: only the generator knows which
    section a page belongs to, while only the handle knows its number. Pairs
    rather than a mapping so the page stays frozen and hashable, like every
    other mark-carrying value in this codebase (§ 3.3)."""


@runtime_checkable
class DocumentGenerator(Protocol):
    """Seam 2 for a document (§ 3.6), alongside the blade `Generator`.

    A document generator keeps the seam-1 queries a blade has — `periodic_axes`
    (the loader asks it; a document has none, so it returns `{}`) and `check`
    (the pre-flight asks it) — and replaces `generate` with `pages`.
    """

    name: str
    config_model: type[BaseModel]

    def periodic_axes(self, cfg: BaseModel) -> dict[str, list]:
        """None: a document has no periodic axis to snap to (§ 8.3)."""
        ...

    def check(self, cfg: BaseModel, *, area: Area, q: WriterQuery) -> None:
        """Refuse what only the area can disprove, before page one (§ 12)."""
        ...

    def pages(self, cfg: BaseModel, *, area: Area, q: WriterQuery) -> Iterator[DocumentPage]:
        """The document's pages, in order — the seam the handle drives."""
        ...

    def page_count(self, cfg: BaseModel, *, area: Area) -> int:
        """How many pages there will be, without drawing any.

        The run report names it (§ 11.3) and `{page_count}` prints it (§ 8.10),
        so it is part of the seam rather than a convenience: a document that
        could only answer by generating every page would have to generate them
        twice.
        """
        ...


def is_document_generator(blade: object) -> bool:
    """A document generator is told from a blade by offering `pages` (§ 7)."""
    return hasattr(blade, "pages")
