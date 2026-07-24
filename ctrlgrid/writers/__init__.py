"""Seam 3 — marks in, metrics out (§ 3.2, § 3.6, § 10.2).

The seam is bidirectional on purpose. § 12 requires every page to be measured
*before* the first one is written, and only the writer knows font metrics,
while § 3.3 forbids the core any contact with the PDF library. So the writer
answers questions as well as taking marks, and those answers are available to
generators too (§ 3.2): a grid label has to fit its cell just as a header has
to fit its band.

Capabilities exist so the vocabulary can be complete from M1 while a writer
still grows into it (§ 14). What a writer cannot do it does not silently drop —
the pre-flight check refuses the run and names the missing feature.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from ctrlgrid.marks import Mark, Mm, Um


@runtime_checkable
class WriterQuery(Protocol):
    """Questions only, no output."""

    def capabilities(self) -> set[str]:
        """e.g. `opacity`, `color`, `text`, `arc`, `polygon`, `image_png`, `vector`."""
        ...

    def text_width(self, content: str, *, family: str, size: Um) -> Um: ...

    def text_metrics(self, *, family: str, size: Um) -> tuple[Um, Um]:
        """Ascent and descent — § 8.4 checks a band's height against them."""
        ...

    def missing_glyphs(self, content: str, *, family: str) -> list[str]:
        """A name with `ł`, `ğ` or `ő` is not an edge case (§ 10.2, § 10.3)."""
        ...


@dataclass(frozen=True, slots=True)
class Attachment:
    """A file to embed in the document (§ 8.8, § 15 point 5).

    `data` is the exact bytes to carry — for `embed_def` the source of the
    definition, unre-encoded — and `filename` the name a viewer offers to save
    it under. A writer that cannot carry a file does not declare the
    `attachment` capability, and the pre-flight refuses the run rather than
    dropping the attachment silently (§ 10.2).
    """

    filename: str
    data: bytes
    description: str = ""


@dataclass(frozen=True, slots=True)
class DocumentMeta:
    """What goes into the PDF information dictionary (§ 10.1).

    No creation timestamp: the date is fixed, or taken from
    `SOURCE_DATE_EPOCH`, so that identical input gives identical bytes.
    """

    title: str = "ctrlgrid template"
    author: str = ""
    subject: str = ""
    #: An optional file to embed alongside the document (§ 8.8). One only: the
    #: single use is the definition carrying its own source.
    attachment: Attachment | None = None


class Writer(WriterQuery, Protocol):
    def begin_document(self, meta: DocumentMeta) -> None: ...
    def begin_page(self, width: Um, height: Um) -> None: ...
    def draw(self, mark: Mark) -> None: ...
    def outline(self, title: str, *, index: int) -> None:
        """Add a table-of-contents entry for the current page (§ 10.1).

        `index` rather than a generated key, so the reference is derived from
        the page and the file stays byte-identical between runs.
        """
        ...

    def end_page(self) -> None: ...
    def end_document(self) -> None: ...


__all__ = ["Attachment", "DocumentMeta", "Mark", "Mm", "Um", "Writer", "WriterQuery"]
