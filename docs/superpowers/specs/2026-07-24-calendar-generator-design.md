# Calendar generator — a linked, write-on planner PDF

**Date:** 2026-07-24
**Status:** approved (brainstorming); awaiting spec review before implementation
**Touches:** a new document-generator seam, a link capability in the writers, a
new `calendar` generator, the page loop in `pages.py`, the spec (§ 7 new blade,
§ 6/§ 10 the link capability), CLAUDE.md, `docs/implementation-decisions.md`,
the handbook, and a preset/example.

## 1. Goal

A complete, self-navigating calendar PDF to write on — built for the reMarkable
(and any e-ink or paper). The pen taps an underlined date and lands on that day;
taps a note number and lands on that note. It is a *template to draw on*
(§ 7.11's philosophy), scaled up from one page to a linked document.

Two properties drive the whole design:

- **One page per view, never scrolling and never scaled.** Each view fills its
  page exactly; if the content cannot fit at a sensible minimum size, the run is
  refused by name (§ 8.2). Detail is the reader's job via the device's zoom.
- **Links are the navigation.** Extensive internal PDF links, drawn as
  underlined text (minimal ink and bytes), turn the document into a planner you
  move through with the pen.

## 2. Scope

**Core first** (this design): six page types — Index, Year, Month, Day,
Notes-index, Notes — fully linked. **Later** (a second pass, same architecture):
Quarter and Week views. Out of scope entirely for now: per-day dedicated note
pages (would be 365), academic/arbitrary start month, recurring events.

## 3. Architecture

Two new mechanisms, each modelled on something the codebase already has.

### 3.1 The document-generator seam (new)

An ordinary generator (a *blade*) fills one pattern area and knows nothing of
pages (§ 3.3). A calendar is the opposite: it *owns* pages and their links. So it
is not a blade — it is a new generator kind, a **document generator**, that
produces a **sequence of typed pages** instead of marks for one rectangle.

Seam-2 shape (new, alongside the existing `generate`):

```
pages(cfg, area, q) -> Iterator[DocumentPage]

DocumentPage:
    dest:  str                 # this page's destination key (for links & bookmark)
    kind:  str                 # "index" | "year" | "month" | "day" | "notes_index" | "notes"
    marks: Iterator[Mark]      # the six primitives, in area-local coordinates
    links: list[Link]          # link rectangles → destination keys
    title: str | None          # optional bookmark label
```

The handle's page loop (`pages.py`) gains a **document mode**: when the generator
is a document generator, instead of looping N identical pages it iterates
`pages()`, and for each page: sets the page size, defines the destination
(`bookmarkPage(dest)`), draws the marks, draws the links, and adds a bookmark.
Existing blades are untouched — they keep `generate()` exactly as it is. The
`area` a document page is handed is the same pattern area every blade gets (after
margins and the optional constant header/footer), so the calendar still knows
nothing about page furniture.

Destination keys are deterministic strings: `index`, `year`, `month-01` …
`month-12`, `day-2026-01-05` (ISO), `notes-index`, `note-01` … `note-NN`. Same
input → same keys → same bytes (§ 10.1).

### 3.2 The link capability (new, like `outline`)

A link is a PDF **annotation** (a GoTo action over a rectangle), not a drawing
primitive — exactly like a bookmark, which already lives *outside* the six
primitives as the writer method `outline()`. So a link follows that precedent, it
does **not** become a seventh primitive (§ 6 untouched):

- `Writer.define_dest(key)` — mark the current page as a named destination.
- `Writer.link(rect, target)` — a link annotation over `rect` → destination
  `target`. (reportlab: `bookmarkPage` + `linkRect`/`linkAbsolute`.)
- New capability string `"link"`. **PDF declares it; PNG does not.** A calendar
  needs links, so a calendar output to PNG is refused before page one, by name,
  with the way out (output PDF) — the same mechanism that refuses text on PNG
  (§ 10.2).

`Link` is a small value object `{rect: Area, target: str}` carried on the
`DocumentPage`, not a mark. Its **visible** part is drawn by the generator as an
ordinary `Text` mark plus a thin `Segment` underline — so the six primitives draw
everything you *see*, and the annotation only adds the tap behaviour. This keeps
the vocabulary pure and the bytes minimal.

### 3.3 Why not the alternatives

- *A blade that asks for 380 pages via `sheets()`* — it would need its page index
  and page type, reaching into page concerns the blade model forbids (§ 3.3).
  Rejected.
- *Emit many sub-definitions and stitch them* — heavy indirection and a global
  link-resolution pass. Rejected.

## 4. Page types (core), each exactly one page

Every page carries the **nav strip**: a line of minimal underlined links
`Index · Year · Month · Notes` (the "Month" link is contextual — the month of the
current page). The optional, constant header/footer (§ 7) sit above/below and the
content ignores them.

| Page | Layout | Links out |
|---|---|---|
| **Index** | the hub: underlined `Year`, `Jan … Dec`, `Notes` | → year, each month, notes-index |
| **Year** | two half-year **tables** (H1 Jan–Jun, H2 Jul–Dec), each 6 month-columns × 31 day-rows, weekends shaded, short months' surplus rows greyed | month header → month; day cell → day (`year_view.cell_link`) |
| **Month** | a **vertical list of every day**, one row each: an underlined date (`Mon 5`) on the left → its day page, a writing line to the right; weekends shaded, holidays labelled | date → day; ‹ › prev/next month; header → year |
| **Day** | configurable blocks top-to-bottom (see §6): optional schedule (hour rows), optional to-do, optional notes; each block's writing surface selectable | ‹ › prev/next day; header → month |
| **Notes-index** | **numbered rows** 1…N; the underlined number → that note page; you write the title on the line | number → note page |
| **Notes** | a writing page (lines/dots/blank) | ‹ › prev/next; → notes-index |

Page count for a year: 1 + 1 + 12 + 365/366 + 1 + N ≈ 380 + N.

## 5. The navigation graph

```
Index ──▶ Year, Month×12, Notes-index         (hub)
Year  ──▶ Month (month header),  ▶ Day (day cell, optional)
Month ──▶ Day (date),  ◀▶ Month±1 (prev/next),  ▶ Year (header)
Day   ──▶ Month (header),  ◀▶ Day±1 (prev/next)
Notes-index ──▶ Note×N (numbers)
Notes ◀▶ Note±1 (prev/next),  ▶ Notes-index
every page: nav strip ──▶ Index, Year, Month(context), Notes-index
```

## 6. YAML

```yaml
version: 1
page: { format: a4, margin: 10mm }        # or device: remarkable-paper-pro
header: { center: "{year}", right: "Alexander" }   # optional, constant; no page numbers

generator: calendar
year: 2026
week_start: monday          # monday | sunday
months:   [January, …]      # 12 names; English default if omitted
weekdays: [Mo, Tu, We, Th, Fr, Sa, Su]     # 7 names; English default if omitted

holidays:                   # an inline list …
  - { date: 2026-01-01, label: New Year }
  - { date: 2026-12-25, label: Christmas }
# holidays: holidays-2026.yaml    # … or a file path with the same shape

year_view:  { weekend_shade: "#f0f2f5", cell_link: day }   # day | month | none
month_view: { weekend_shade: "#f0f2f5", surface: lines }   # lines | dots | blank

day:                        # every block optional; omit = not drawn
  schedule: { from: 7, to: 22, surface: lines }
  todo:     { rows: 8 }
  notes:    { surface: lines }

notes: { count: 20, surface: lines }       # a numbered index page + N note pages
```

`{year}` is a new header placeholder the calendar supplies (alongside the
existing `{page}`/`{name}`); page-number placeholders are meaningless here and
simply left unused.

## 7. Dates and reproducibility

All dates are computed from `year` and `week_start` with the standard library's
proleptic Gregorian calendar — deterministic, no wall-clock (`Date.now()` is
already forbidden in this codebase). Holidays come only from the given list/file.
Same definition → same document → same bytes (§ 10.1), which a determinism test
guards, as for every writer addition.

## 8. Names and localization

Strictly language-neutral (§ 7.8): `months` and `weekdays` are taken from the
definition, with English defaults when omitted. No locale table ships. The
German user lists German names once.

## 9. Fit-or-refuse

Each page sizes its rows/columns to fill the pattern area. If the content cannot
fit at a sensible minimum (e.g. `notes.count` so high the numbered rows fall
below a readable minimum height, or a day `schedule` hour-range too tall), the
run is **refused in the pre-flight**, naming what does not fit and by how much —
never scaled, never scrolled (§ 8.2, § 12 point 13). The reader zooms for detail;
the geometry stays true.

## 10. Fonts

The calendar draws text (dates, names, numbers, labels), so it needs a font. The
standard logical families (`serif`/`sans`/`mono`) cover Latin names; a font file
is only needed for names outside Latin-1 (§ 10.3), exactly as elsewhere. On PNG
the run is refused for want of both text and links.

## 11. Testing

- Unit tests per page type: the right pages in the right order with the right
  destination keys; a month row per day; a day's blocks present/absent per
  config; the notes-index has N numbered links to N note pages.
- Link tests: every `Link.target` resolves to a `dest` that exists (no dangling
  links); a day cell's link points at the matching `day-YYYY-MM-DD`.
- Fit-or-refuse: an over-full notes count / schedule range is refused in
  pre-flight, named.
- Determinism: two runs, byte-identical.
- PNG refusal: a calendar to `.png` is refused by name.
- A real rendered PDF read back (pypdf: page count, that the annotations exist
  and resolve), plus a rasterised look — not only unit tests.

## 12. Implementation phases (all test-first)

1. **The link capability** — `define_dest`/`link` on the PDF writer, the `"link"`
   capability, PNG refusal. Determinism test. (No calendar yet; test with a tiny
   two-page linked fixture.)
2. **The document-generator seam** — `DocumentPage`, the handle's document mode
   in `pages.py`, bookmark + link wiring. Test with a trivial two-page document
   generator fixture.
3. **The calendar model + dates** — the YAML config, name defaults, holiday
   import, deterministic date computation, fit-or-refuse checks.
4. **The pages** — Index, Year (two half-year tables), Month (day list), Day
   (configurable blocks), Notes-index, Notes; the nav strip; all links wired.
5. **Polish** — the `{year}` header placeholder, a preset (`calendar-a4`), an
   example, the handbook section, spec + CLAUDE.md + implementation-decisions.

Then, as a separate design/effort on the same architecture: Quarter and Week.

## 13. Open risks

- **reMarkable link fidelity** — internal GoTo links work in synced PDFs, but the
  exact tap target and zoom behaviour should be checked on a real device once
  phase 1–2 produce a linked fixture. (Manufacturer-agnostic PDF links; standard
  and widely used by planner templates.)
- **Byte size** — ~380 pages with many annotations each. Underlined-text links
  and reportlab's compression keep it reasonable, but the size should be measured
  and reported, not assumed.
