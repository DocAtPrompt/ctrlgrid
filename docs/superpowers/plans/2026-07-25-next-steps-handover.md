# Next steps — handover to a fresh instance

**Written:** 2026-07-25, at the end of a long session, by the instance that did
the calendar beautification work below. Written *for the next instance* because
this one's context was running out, not because the work is hard.

**Read [`docs/CLAUDE.md`](../../CLAUDE.md) first.** It is the orientation and it
is current. This file only adds *what to do next*, in order.

---

## Where things stand (verified, not remembered)

Verify before trusting any of this — the project's own rule is that a claim is
backed by a command's output:

```bash
uv sync --extra dev && uv run pytest -q && uv run ruff check .
```

At the time of writing: **1000 tests green, ruff clean**, working tree clean,
`main` pushed to `github.com/DocAtPrompt/ctrlgrid` at `9ab9bbf`. The repository
has its **first star** — which is why phase 0 below is the online presence and
not a feature.

### What that session changed (all pushed)

A beautification pass over every calendar view, plus two real features. The
thread running through nearly all of it: **positions were guessed instead of
measured**, and each guess showed up as a misalignment.

| Area | What changed |
|---|---|
| title page | `background_image` (PNG over the colour, `cover`/`contain`), opt-in `header`/`footer` |
| header/footer | `Band.background` (full-width strip, band height only) + `Band.text_color` — tool-wide, every generator |
| contents | one centred column, groups separated by whitespace, vertically centred, optional colour key (`legend`) |
| full-year | one right edge per column, week numbers (linked when week pages exist), month name over its own column, grid sized from content |
| half-year | day number centred in its row, optional `year_view.day_numbers: both` |
| month + week | weekday left / number right-aligned, one shared `date_columns`/`date_label` |
| day | schedule hours right-aligned (were space-padded), one shared left edge for all block rules, opt-in `half_hours` |
| marked days | `Holiday.color` + `holiday_color`, shown behind the day in all five views |
| notes | `notes` takes one pad **or a list**; each pad has its own count, surface, label, numbering from 1, and index; indexes link to each other |
| everywhere | nav strip moved to the right edge (it fought the page title for the left corner) |

Four new pre-flight refusals came with it (contents too tall, mini-month too
wide, `half_hours` on a block with no hours, a legend line with no colour). If
you add a content-sized layout, add its refusal too — that is the pattern.

---

## Phase 0 — the online presence (done, 2026-07-25)

> **Done in the session after this handover.** The README has a
> *"A linked, write-on calendar"* section of its own; `examples/12-calendar-year.yaml`
> is the worked example (405 pages, a day and a month preview, no committed PDF
> — 1.6 MB, one command rebuilds it); the handbook's calendar section was
> rewritten to cover everything below, and the band colours went into its
> header/footer section where they belong.
>
> **The gallery refresh was not needed** — that guess was wrong, and checking
> was cheap: every committed example PDF was rebuilt and compared byte for byte,
> and all thirteen matched (the maze booklet with its documented `--seed 4711`).
> Band colours and the nav strip are calendar-only or default-off, so no blade
> sheet changed. The paragraph below is kept as written; only this note corrects
> it.



A visitor arriving from that star sees the README and the gallery. Both are
behind. **Two gaps found by inspection, both verified:**

1. **`README.md` does not mention the calendar at all** (`grep -c calendar
   README.md` → 0). The largest feature in the project is invisible on its front
   page. The README's "What it generates" section lists the blades; the calendar
   is not a blade but a *document generator*, and it needs its own short section
   — a linked, write-on planner, one PDF, tap a date and land on that day.

2. **There is no calendar example** (`ls examples/ | grep -c calendar` → 0).
   Thirteen examples exist, `01`–`11`, and none is the calendar. Add
   `12-calendar-year.yaml` + its rendered PDF + PNG preview, in the same shape
   as the others, and let `test_every_example_validates` cover it. Keep it
   small — a calendar with every view on is ~460 pages; consider a definition
   that shows the *look* (title page with a background, coloured bands, a couple
   of note pads, a legend) rather than a full year of day pages, or accept the
   size deliberately and say so in the file's comment.

3. **`HANDBOOK.md` § "`calendar` — a linked, write-on planner" (around line 794)
   predates all of the above.** It documents `year`, the views and `calendar-a4`,
   but not: `holidays_file`, `Holiday.color`/`holiday_color`, `legend`,
   `title_page.background_image`/`background_fit`/`header`/`footer`,
   `year_view.day_numbers`, `half_hours`, or note **pads**. The band colours
   (`background`/`text_color`) belong in the handbook's header/footer section,
   not the calendar one — they are handle furniture and work for every generator.

Also refresh the **rendered gallery**: several example PDFs predate the band
colours and the nav move, so their PNG previews no longer match what the tool
produces. Rebuild them from their own definitions.

**Do not invent numbers for the README.** Run the suite and quote what it says.

---

## Phase 1 — the first bulk, in this order

### 1a. An edge ruler (small, high show-value) — **built, 2026-07-25**

> Done. `ruler:` is § 8.12 and decision 47; the design was settled with the user
> first (`docs/superpowers/specs/2026-07-25-edge-ruler-design.md`), then built
> test-first against a plan (`2026-07-25-edge-ruler.md`). The three questions
> below were the ones put to the user: it sits **in** the margin and reserves
> nothing, the edges are physical and listed, and yes — a margin too narrow for
> tick, gap and measured number is refused by name, before page one. The gallery
> sheet is `examples/13-ruler-edge.yaml`.


A printed centimetre/inch scale along one page edge, opt-in. Handle furniture,
not a blade — it belongs beside `hole_marks` and `border` in `frame.py`, drawn
from the sheet, and it is the only feature that *demonstrates the one promise on
every sheet*: lay a real ruler against it. Cheap (`Segment` + `Text`), and the
best screenshot the README could have.

Decide with the user: which edges, whether it sits inside the margin or in it,
and whether it is refused when the margin is too narrow for its labels (it
should be — measure the label and refuse loudly rather than clipping).

### 1b. Angled line families (the leveraged one)

**`lines` has no angle** — verified, there is no `angle` anywhere in
`ctrlgrid/generators/lines.py`. Adding a family of parallel lines at an angle
unlocks two unrelated things at once, which is the signal that it is the right
abstraction and not a special case:

- **calligraphy and handwriting guides** — italic slant lines (typically 5°
  from vertical for the pen angle, 55° for the slant), plus baseline / x-height /
  ascender / descender rulings. § 15 open question 4 already asks about **nib
  widths** as a unit: "x-height = 4 nib widths" is a genuine measure, and would
  be a new unit in `units.py` the way `sp` (staff spaces) already is.
- **origami pre-creasing** — the diagonals of phase 2c.

Design note: the clipping is the interesting part. `perspective` already clips
rays to the pattern area with Liang–Barsky (`ctrlgrid/generators/perspective.py`)
— reuse that, do not write a second clipper.

### 1c. International presets (cheapest reach) — **built, 2026-07-25**

> Done: `seyes-a4`, `mizige-a4` (米字格, whose diagonals 1b made exact) and
> `knitting-chart-a4`. **Genkō yōshi was dropped with its reason** — its
> furigana strip and binding gutter need rules that stop and start again, and
> § 2 rules out a drawing language. A new guard came with it: every shipped
> preset must produce no media findings on its own medium.



Pure preset work, no code:
- **Genkō yōshi** — Japanese manuscript paper, 20×20 squares with a centre gutter.
- **Séyès** — French ruling: 8 mm horizontals with 2 mm subdivisions and verticals.
- **Knitting gauge** — stitches and rows are *not* square; two different axis
  spacings, which `dots`/`grid` already support.

Each is a `.yaml` in `ctrlgrid/data/presets/` plus a line in the preset list.
Presets are documentation (§ 9.3), so comment them the way the shipped ones are.

### 1d. A `notebook` document generator (the big one) — **built, 2026-07-25**

> Done, and the architectural question below was answered the way this file
> guessed it should be: the notebook does **not** reach into blades. A
> `DocumentPage` may carry a `Fill` — a generator name and its validated config
> — and the handle calls the blade. § 7.13, decision 50, preset `notebook-a4`,
> example `15-notebook`. The note-pad reuse this file suggested turned out
> unnecessary: sections are simpler than pads, and the contents page is its own
> small layout.



The calendar built the document-generator seam (`ctrlgrid/document.py`,
`DocumentPage`, the `link` capability, the document page loop in `pages.py`) and
is still its **only** user. Generalise it:

```yaml
generator: notebook
sections:
  - { pages: 40, generator: dots,   spacing: 5mm, label: "Bullet journal" }
  - { pages: 20, generator: grid,   spacing: 5mm, label: "Sums" }
  - { pages: 10, generator: staves, label: "Music" }
```

One PDF, a linked contents page, each section filled by an existing blade. For
an e-ink user this is the missing piece — one notebook on the device, not twelve
PDFs.

The hard part is not the pages, it is the seam: a document generator currently
produces marks itself, while a blade produces marks for *one pattern area*. A
`notebook` has to call blades. Look at how `pages.py` drives a blade
(`_page_marks`) and keep that on the handle side — the notebook should ask the
handle to fill a section, not reach into blades itself. **Design this with the
user before building it**; it is the one item here with a real architectural
choice in it.

Reuse the calendar's note-pad work: `notes` pads, their per-pad numbering and
their cross-linked indexes are the same shape a notebook's sections need.

---

## Phase 2 — the fold-adjacent ones

These came from the user asking about paper-folding templates. **The scope call
is already made, do not re-open it:** a specific paper aeroplane is a *drawing*,
not a structure, and § 2 (line 60 of the spec) rules out a general drawing
language. What follows is the part that is parametric.

### 2a. Fold notation (naming, not new machinery)

Origami's Yoshizawa–Randlett convention: valley fold dashed, mountain fold
dash-dot, reference crease thin. The dash machinery already does this —
`style: dashed | dotted`, `base_dash`, and custom `dash` cycles in
`ctrlgrid/generators/common.py`; `dash: [3, 1, 1, 1]` *is* a dash-dot. What is
missing is the name, not the capability. Consider a documented convention plus
presets rather than new code.

### 2b. Parametric nets — `net` (recommended as the next big blade)

A box of 80×50×30 mm, an envelope for a given card: cut lines solid, fold lines
dashed, glue tabs computed. This **is** a structure — measurements in, a law
computes the net — and it lives or dies by millimetre accuracy: a box 2 mm out
does not close. It demonstrates the promise in a way squared paper never can.

Start with one box style (a simple tuck-top or a tray) and refuse the rest by
name until built, the way every deferred feature in this codebase does. Check
that the net fits the sheet in `check()` and refuse loudly with the size needed.

### 2c. Pre-creasing grids for tessellations

A 16×16 or 32×32 grid plus diagonals, in fold notation. `grid` does the
orthogonal part today; the diagonals are 1b. Mostly a preset once 1b exists.

---

## How to work here (short version — the long one is in `docs/CLAUDE.md`)

- **Measure, never guess.** Almost every bug that session was a guessed
  position: a centred label over left-aligned numbers, a fixed inset in a
  variable-height row, a composed string that could not align, a space used as
  padding (a space is *half* a digit wide — that one shipped for months).
  `q.text_width(...)` is how you find out.
- **One arithmetic, not two.** When drawing and checking both need a size, they
  share a function (`contents_height`, `mini_month_width`, `date_columns`,
  `notes_capacity`). Two copies drift.
- **Test first, then implement.** Where a design is genuinely uncertain, the
  project's own precedent is: validate on a real rendered sheet, then codify it
  in tests (`pattern.align` was built that way, and so was every layout change
  in that session).
- **Read the sheet back.** `pdftoppm -png -r 150 -f N -l N out.pdf crop` and
  actually look at it; `tests/pdfread.py` and `pypdf` for geometry.
- **Fail loudly, before page one.** A content-sized layout needs a `check()`
  refusal naming the size needed and the size available.
- **Commit messages via a file, not `-m`.** A backtick in a `-m` message gets
  executed by the shell — that happened, and ate part of a message.
- Update the spec (`docs/pflichtenheft-vorlagengenerator.md`), `docs/CLAUDE.md`
  and the preset in the *same* commit as the code.
- Push only on the user's word, and **never** `--tags`: an annotated `v0.1.0`
  sits locally and would fire the release workflow.
