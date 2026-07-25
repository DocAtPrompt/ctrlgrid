# `notebook` — a linked notebook of sections. Design

**Date:** 2026-07-25. Settled with the user; belongs in the specification as
**§ 7.13** and in `implementation-decisions.md` as decision 50.

One PDF: a contents page, then sections, each filled by an existing blade —
forty dotted pages to journal on, twenty squared ones to reckon on, ten of
staves. For an e-ink reader this is the missing piece: one notebook on the
device instead of twelve PDFs.

## The decision that matters: the page describes, the handle fills

A blade produces marks for **one pattern area**; a document generator produces
**pages**. A notebook needs both, and the question is who calls the blade.

**The notebook never calls one.** A `DocumentPage` may carry, instead of its own
marks, a *description* — "this page is `dots` with this configuration" — and the
handle calls the blade exactly as it does on the blade path. That keeps the line
this architecture has held since M1: when a feature needs blade knowledge, the
handle gets something to ask rather than the blade getting the page (§ 3.3, and
the way `periodic_axes`, `check`, `sheets` and `capabilities` all came about).

Rejected: the notebook importing the registry and calling `generate` itself. It
looks smaller — no new mechanism — but a generator would be doing handle work,
and the moment a section wants `snap` or a leftover placed, the notebook would
have to rebuild the geometry machinery the handle already has.

Also rejected: no generator at all, with `sections:` as a handle key beside
`pages:`. The page plan *is* handle territory, but a linked contents page is not,
and the handle has never produced one.

```python
@dataclass(frozen=True, slots=True)
class Fill:
    """A page a blade fills (§ 7.13). The document names the generator and its
    already-validated config; the handle calls it."""
    generator: str
    config: Any
```

One function in `pages.py` yields a document page's marks — its own, then its
fill's — and the writer, the capability pre-flight and the media check all use
that one function. Three copies of "what is on this page" would drift.

## The definition

A section is a small definition: the generator, then that generator's own keys,
exactly as at the top level of any file.

```yaml
generator: notebook
title_page: { title: "Notebook", subtitle: "2026" }   # optional
sections:
  - label: "Bullet journal"
    pages: 40
    divider: true                 # a section sheet before it, with the label
    generator: dots
    grid: { x: { base_spacing: 5mm }, y: { base_spacing: 5mm } }
    base_size: 0.4mm
  - label: "Sums"
    pages: 20
    generator: lines
    families:
      - { direction: horizontal, base_spacing: 5mm }
      - { direction: vertical,   base_spacing: 5mm }
  - label: "Music"
    pages: 10
    generator: staves
    systems: 6
```

Pages, in order: an optional **title**, a **contents** page linking to every
section, then each section — its **divider** if it asked for one, then its
pages. The contents entries link to the divider when there is one and to the
section's first page when there is not.

## Bands become per page

The calendar measures its header and footer **once** and stamps them on every
page, because a calendar's bands are constant and page numbers are meaningless
in a document you navigate by tapping. A notebook is flipped through, so both
things the user asked for need the bands to be laid out per page:

- `{page}` and `{page_count}` — § 8.10 already says placeholders are filled per
  page, and the document path was the exception;
- `{section}` — a **per-page** placeholder, new: `DocumentPage.placeholders`
  carries it, because only the generator knows which section a page belongs to,
  while only the handle knows its number.

`blade.placeholders(cfg)` (document-wide, the calendar's `{year}`) stays as it
is. The band **heights** are unchanged and still fixed (§ 8.4), so no geometry
moves — only the text differs per page.

This changes the calendar too, and deliberately: a `{page}` in a calendar header
used to print "1" on every sheet and will now number them. The shipped
`calendar-a4` has no `{page}`, and a test holds it byte-identical.

## Refusals, before page one

1. A section naming an **unknown generator** — refused with the list of known
   ones, as an unknown preset already is.
2. A section naming a **document generator** (a calendar inside a notebook) —
   refused by name: a document owns pages, and pages are what a section
   supplies. Nesting is not the seam.
3. A section's **own keys** are validated by that blade's `config_model`, so a
   typo inside a section is an error naming the blade, not a silently different
   sheet (§ 5.1).
4. Each section's blade **`check`** runs against the pattern area, so a section
   that cannot fit is refused with its own message (a polar target too large, a
   log block too long) — one section refusing stops the run.
5. **`pages: 0`** and an empty `sections:` list are errors.
6. A **contents page that does not fit** is refused with the height needed and
   the number of sections, the way the calendar's is.

## Deliberately not in this version

- **No per-section `snap`, `remainder` or `align`.** Those are handle geometry
  for the whole document; a section takes the pattern area as it is. Named here
  so the next instance does not think it was forgotten.
- **No per-section page format or margins.** One sheet size per document.
- **No nested notebooks**, per refusal 2.

## Tests

- the pages come in order, with the right count, and each section's pages carry
  that section's marks (a `dots` section really has dots);
- the contents links resolve to destinations that exist — every link target is a
  `dest` of some page;
- a section's blade config is validated by that blade: a typo inside a section
  names the blade;
- an unknown generator, a document generator, `pages: 0`, an empty list, a
  section whose blade `check` refuses — five messages;
- `{page}` counts up and `{section}` names the section, read out of the PDF;
- `calendar-a4` is byte-identical after the band change;
- two runs of the same notebook are byte-identical (§ 10.1);
- PNG is refused, naming `text`/`link`, through the existing capability path.
