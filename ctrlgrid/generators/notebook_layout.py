"""Drawing for `notebook` (§ 7.13) — the three pages the notebook draws itself.

Everything else on its pages is a blade's work, reached through the page's
`Fill` and drawn by the handle; what is left here is the cover, the contents and
the dividers. It draws on the shared `Page` builder, the same one the calendar
uses.

The contents' height lives in **one** function, used by the drawing and by the
refusal in `notebook.check`. Two copies drift, and a contents page that is
checked against one arithmetic and drawn with another is exactly the sheet § 5.1
calls the worst failure class.
"""

from __future__ import annotations

from ctrlgrid.document import DocumentPage
from ctrlgrid.generators.page_layout import GUIDE, INK, Page, pt
from ctrlgrid.marks import Area
from ctrlgrid.writers import WriterQuery

CONTENTS_DEST = "contents"

#: The contents page's proportions, in points. Fixed measures, like the cover
#: sheet's figures (§ 8.8) — a contents page is read, not configured.
TITLE_SIZE = pt(18)
ENTRY_SIZE = pt(11)
LINE_STEP = pt(20)
TOP_MARGIN = pt(24)
TITLE_GAP = pt(28)


def contents_height(sections: int, *, q: WriterQuery) -> int:
    """How tall the contents page's block is, for the drawing and the refusal.

    `q` is taken though the arithmetic does not need it yet: the sizes here are
    fixed measures, and a caller that had to know *which* of them need measuring
    would be a caller that can get it wrong.
    """
    return TOP_MARGIN + TITLE_SIZE + TITLE_GAP + sections * LINE_STEP


def title_page(spec, area: Area, *, q: WriterQuery) -> DocumentPage:
    """The cover: a full-sheet colour with a centred title and subtitle."""
    page = Page(area, q)
    middle = area.width // 2
    page.text(middle, area.height * 0.38, spec.title, pt(30), spec.text_color, "center")
    if spec.subtitle:
        page.text(
            middle, area.height * 0.38 + pt(46), spec.subtitle, pt(13),
            spec.text_color, "center",
        )
    return DocumentPage(
        dest="title",
        kind="title",
        marks=tuple(page.marks),
        title=spec.title,
        background=spec.background,
        show_header=False,
        show_footer=False,
        placeholders=(("section", spec.title),),
    )


def contents_page(cfg, starts: list[int], area: Area, *, q: WriterQuery) -> DocumentPage:
    """The hub: one line per section, its name a link and its first page number.

    The page number is printed as well as linked, because a notebook is a
    physical object too — on paper the link is nothing but underlined text, and
    the number is what makes it usable there (§ 7.13).
    """
    from ctrlgrid.generators.notebook import _section_dest

    page = Page(area, q)
    top = TOP_MARGIN
    page.text(0, top, cfg.contents_title, TITLE_SIZE, INK)
    top += TITLE_SIZE + TITLE_GAP

    for index, section in enumerate(cfg.sections):
        name = section.name(index)
        page.link_text(0, top, name, _section_dest(index), ENTRY_SIZE)
        page.text(area.width, top, str(starts[index]), ENTRY_SIZE, INK, "right")
        top += LINE_STEP

    return DocumentPage(
        dest=CONTENTS_DEST,
        kind="contents",
        marks=tuple(page.marks),
        links=tuple(page.links),
        title=cfg.contents_title,
        # Every page of a notebook answers `{section}` — a header that names
        # the section must not fail on the two pages that are not in one
        # (§ 8.10 refuses an unknown placeholder, and rightly).
        placeholders=(("section", cfg.contents_title),),
    )


def divider_page(
    name: str, section, area: Area, *, dest: str, q: WriterQuery, placeholders,
    contents_title: str = "Contents",
) -> DocumentPage:
    """A sheet before a section: its name, a rule to write a subtitle under, and
    the way back to the contents."""
    page = Page(area, q)
    top = area.height * 0.32
    page.text(0, top, name, pt(26), INK)
    page.hline(0, area.width, top + pt(26) + pt(14), 0.6, INK)
    page.hline(0, area.width, top + pt(26) + pt(52), 0.25, GUIDE)
    # The way back, at the top right — where the calendar's nav strip sits, so
    # the two documents are read the same way.
    back = contents_title
    width = q.text_width(back, family="sans", size=pt(10))
    page.link_text(area.width - width, TOP_MARGIN, back, CONTENTS_DEST, pt(10))
    return DocumentPage(
        dest=dest,
        kind="divider",
        marks=tuple(page.marks),
        links=tuple(page.links),
        title=name,
        placeholders=placeholders,
    )
