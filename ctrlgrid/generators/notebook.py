"""`notebook` — a linked notebook of sections, each filled by a blade (§ 7.13).

The second document generator, and the first that **composes** blades: forty
dotted pages to journal on, twenty squared ones to reckon on, ten of staves,
in one PDF with a contents page that links to each.

The seam it stands on is the one thing worth reading twice. A page may carry a
`Fill` — a generator's name and its already-validated config — instead of its
own marks, and the **handle** calls that blade (`pages.document_page_marks`).
The notebook never touches one. That keeps every future handle feature — page
context, snapping, the leftover, imposition — on the handle's side of the line,
which is the rule this architecture has held since M1 (§ 3.3).

A section is a *small definition*: `generator:` plus that generator's own keys,
exactly as at the top level of a file. So the blade validates its own section,
and a typo inside one is an error in the blade's own words (§ 5.1).
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ctrlgrid.document import DocumentPage, Fill
from ctrlgrid.errors import DefinitionError
from ctrlgrid.marks import Area
from ctrlgrid.model import ColorField, Section
from ctrlgrid.writers import WriterQuery

#: The keys a section owns. Everything else belongs to the blade it names.
_SECTION_KEYS = ("label", "pages", "divider", "generator", "config")


class NotebookSection(Section):
    """One run of pages filled by one blade (§ 7.13)."""

    label: str | None = None
    pages: int = Field(ge=1)
    #: A sheet before the section carrying its name, to write on and to find
    #: while flipping.
    divider: bool = False
    generator: str
    #: The blade's own section, validated by that blade's `config_model` in the
    #: before-validator. Never written by the user.
    config: Any = None

    @model_validator(mode="before")
    @classmethod
    def _the_blade_validates_its_own_keys(cls, data: Any, info) -> Any:
        """Move the blade's keys out and let the blade validate them (§ 7.13).

        The validation context is passed on, so `px` and `%w`/`%h`/`%s` resolve
        inside a section exactly as they do in a definition (§ 8.3.1, § 8.11) —
        seam 1 stays one seam.
        """
        if not isinstance(data, dict):
            return data
        from ctrlgrid import generators
        from ctrlgrid.document import is_document_generator

        name = data.get("generator")
        if not isinstance(name, str):
            return data  # let the `generator` field report its own error

        blade = generators.get(name)  # raises, listing the known generators
        if is_document_generator(blade):
            raise ValueError(
                f"`{name}` owns its own pages, so it cannot fill a section: a section "
                "*is* pages, and a document generator is the thing that produces them. "
                "Notebooks do not nest (§ 7.13)"
            )
        own = {key: value for key, value in data.items() if key not in _SECTION_KEYS}
        kept = {key: value for key, value in data.items() if key in _SECTION_KEYS}
        kept.pop("config", None)  # computed here, never user input
        kept["config"] = blade.config_model.model_validate(own, context=info.context)
        return kept

    def name(self, index: int) -> str:
        """What this section is called — its label, else a number. Two sections
        must never answer to the same name in the contents."""
        return self.label or f"Section {index + 1}"


class TitlePage(Section):
    """An opt-in cover: a title and an optional subtitle, and nothing else.

    Deliberately smaller than the calendar's title page (§ 7.12), which also
    carries a background colour and image, a logo and per-band opt-ins. A
    notebook divider does that job here if one is wanted."""

    title: str
    subtitle: str | None = None
    background: ColorField = "#2f3a48"
    text_color: ColorField = "#ffffff"


class NotebookConfig(BaseModel):
    """The definition section belonging to this document generator (§ 7.13)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    sections: tuple[NotebookSection, ...] = Field(min_length=1)
    title_page: TitlePage | None = None
    contents_title: str = "Contents"


class NotebookGenerator:
    name = "notebook"
    config_model = NotebookConfig

    #: § 8.3: a document has no pattern axis of its own to snap to. A section's
    #: blade may have one, but the area it is handed is the document's.
    supports_snap = False

    def is_page_invariant(self, cfg: NotebookConfig) -> bool:
        """False: the pages differ — contents, dividers, several patterns."""
        return False

    def periodic_axes(self, cfg: NotebookConfig) -> dict[str, list]:
        """None (§ 8.3). A section takes the pattern area as the document has
        it; per-section geometry is deliberately not in this version (§ 7.13)."""
        return {}

    def describe(self, cfg: NotebookConfig) -> list[str]:
        lines = []
        for index, section in enumerate(cfg.sections):
            divider = " + divider" if section.divider else ""
            lines.append(
                f"{section.name(index)}: {section.pages} page(s) of "
                f"`{section.generator}`{divider}"
            )
        return lines

    def placeholders(self, cfg: NotebookConfig) -> dict[str, str]:
        """Document-wide placeholders (§ 8.10). `{section}` is *not* one of
        them: it differs per page, so each page carries it itself."""
        return {}

    def check(self, cfg: NotebookConfig, *, area: Area, q: WriterQuery) -> None:
        """Fit or refuse, before page one (§ 12 point 13).

        Two kinds of refusal meet here: each section's blade refuses what only
        the area can disprove — in its own words, which is why the blade's own
        `check` is called rather than reimplemented — and the contents page
        refuses when it cannot hold its own list.
        """
        from ctrlgrid.generators import get
        from ctrlgrid.generators import notebook_layout as layout

        for index, section in enumerate(cfg.sections):
            blade = get(section.generator)
            get(section.generator).check(section.config, area=area, q=q)
            # A blade may state that one *item* needs more than one sheet —
            # `maze` with separate solution pages (§ 7.5, decision 27). On the
            # blade path the handle carries that plan out: it doubles the count,
            # numbers across, and mirrors where asked. A notebook has no such
            # loop, and asking for it silently produced solutions printed
            # *before* their puzzles — and mazes that changed when an unrelated
            # title page shifted the page index. § 7.13 does not say what a
            # per-section sheet plan should mean, so it is refused until it does
            # rather than answered wrongly (§ 5.1).
            sheets = getattr(blade, "sheets", None)
            plan = sheets(section.config) if sheets else None
            if plan is not None and plan.per_item > 1:
                raise DefinitionError(
                    f"section `{section.label}` uses `{section.generator}` in a mode that "
                    f"needs {plan.per_item} sheets per item, and a notebook lays out one "
                    "page at a time (§ 7.13) — the solution pages would not pair with "
                    "their puzzles. Use `solution: none` or `solution: overlay` here, or "
                    "build the mazes as their own document",
                    field=f"sections.{index}.solution",
                )

        needed = layout.contents_height(len(cfg.sections), q=q)
        if needed > area.height:
            raise DefinitionError(
                f"the contents page needs about {round(needed / 1000)} mm of height for "
                f"{len(cfg.sections)} sections and the pattern area is "
                f"{round(area.height / 1000)} mm — use a taller page, smaller margins or "
                "fewer sections (§ 7.13)",
                field="sections",
            )

    def generate(self, cfg, *, area, page, q):  # never called — a document
        raise AssertionError("notebook is a document generator; it produces pages")

    def page_count(self, cfg: NotebookConfig, *, area: Area) -> int:
        """Title (opt-in) + contents + each section's divider and pages."""
        total = 1 + (1 if cfg.title_page is not None else 0)
        for section in cfg.sections:
            total += section.pages + (1 if section.divider else 0)
        return total

    def pages(
        self, cfg: NotebookConfig, *, area: Area, q: WriterQuery
    ) -> Iterator[DocumentPage]:
        from ctrlgrid.generators import notebook_layout as layout

        starts = self._section_starts(cfg)
        if cfg.title_page is not None:
            yield layout.title_page(cfg.title_page, area, q=q)
        yield layout.contents_page(cfg, starts, area, q=q)

        for index, section in enumerate(cfg.sections):
            name = section.name(index)
            placeholders = (("section", name),)
            if section.divider:
                yield layout.divider_page(
                    name, section, area, dest=_section_dest(index), q=q,
                    placeholders=placeholders,
                )
            for number in range(1, section.pages + 1):
                dest = (
                    _page_dest(index, number)
                    if section.divider or number > 1
                    else _section_dest(index)
                )
                yield DocumentPage(
                    dest=dest,
                    kind="section",
                    marks=(),
                    fill=Fill(section.generator, section.config),
                    placeholders=placeholders,
                )

    def _section_starts(self, cfg: NotebookConfig) -> list[int]:
        """The 1-based page number each section starts on, for the contents.

        One arithmetic with `page_count` above: both count the same pages in
        the same order, and the contents prints what the reader will find.
        """
        number = 1 + (1 if cfg.title_page is not None else 0) + 1  # title, contents
        starts = []
        for section in cfg.sections:
            starts.append(number)
            number += section.pages + (1 if section.divider else 0)
        return starts


def _section_dest(index: int) -> str:
    """Where a contents entry lands: the section's divider, or its first page."""
    return f"section-{index + 1}"


def _page_dest(index: int, number: int) -> str:
    return f"section-{index + 1}-p{number}"
