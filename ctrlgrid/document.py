"""The document-generator seam (§ 7, the calendar).

An ordinary generator (a *blade*) fills one pattern area and knows nothing of
pages (§ 3.3). A **document generator** is the opposite: it owns pages and their
links. So instead of `generate(cfg, area, page, q) -> marks` it offers
`pages(cfg, area, q) -> Iterator[DocumentPage]`, a sequence of typed pages, each
carrying its own marks (the six primitives, area-local), its link rectangles and
its destination key.

The handle (`pages.build`) detects a document generator by the presence of
`pages` and runs a *document mode*: for each page it sets the page size, defines
the destination (a bookmark), draws the marks translated onto the sheet, draws
the links, and moves on. Existing blades are untouched — they keep `generate`
exactly as it is. Everything about page geometry still stays on the handle side:
the generator is handed the same pattern area every blade gets and translates
nothing itself (§ 3.3).

Links are annotations, not drawing primitives, so — like the bookmark
`outline()` — they live outside the six primitives (§ 6). A `Link` names two
corners in area-local micrometres and a destination key; its *visible* part is an
ordinary `Text` mark plus a `Segment` underline the page also emits (minimal ink
and bytes).
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

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
    title: str | None = None


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


def is_document_generator(blade: object) -> bool:
    """A document generator is told from a blade by offering `pages` (§ 7)."""
    return hasattr(blade, "pages")
