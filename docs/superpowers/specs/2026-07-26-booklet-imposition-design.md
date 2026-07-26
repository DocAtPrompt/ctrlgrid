# `--booklet` — saddle-stitch imposition. Design

**Date:** 2026-07-26. Settled with the user; belongs in the specification as
part of **§ 14** (with the flag in § 11.1) and in `implementation-decisions.md`
as decision 54.

Fold a stack of sheets down the middle, staple through the fold, and you have a
booklet. Which page goes where on which sheet is not obvious — sheet one carries
pages 8 and 1 on its front and 2 and 7 on its back — and no comparable tool does
it while holding the page at 100 %. This adds it.

## Why it belongs here at all

§ 14 already argues the case for imposition: it works on *finished* pages, so it
does not breach § 2's "no layout system", and it refuses to scale where every
comparable tool shrinks. A booklet is the same argument one step further. It is
also the one thing the specification never described — `--nup` puts pages side
by side, and nothing folds them.

Geometrically a booklet **is** `--nup 2x1`. What it adds is an *order* and a
front/back pairing. That is the whole feature.

## The mechanism: one function, and it knows no millimetres

```python
def slots(page_count: int, imposition: Imposition) -> list[list[int | None]]
```

For every sheet side, which rendered page belongs in which cell. `None` means
the cell stays empty. Two rules live in it:

- **Plain n-up:** reading order, in blocks of `per_sheet` — exactly the loop
  `_write_imposed` runs today.
- **Booklet:** the fold order. With *P* the page count rounded up to a multiple
  of four, sheet *i* (0-based) carries `(P − 2i, 2i + 1)` on its front and
  `(2i + 2, P − 2i − 1)` on its back. For eight pages: `[8,1] [2,7] [6,3] [4,5]`.

Three details the formula alone leaves open, fixed here:

- **The tuple is (left cell, right cell)**, in the order `Imposition.cell` already
  numbers positions — position 0 is the left half of a 2×1 sheet.
- **The returned list is in printing order**, front and back interleaved: sheet 1
  front, sheet 1 back, sheet 2 front … That is what duplex printing consumes, and
  it is why the list has two entries per physical sheet.
- **Which rule applies is a field on `Imposition`**, `booklet: bool = False`. The
  dataclass documents itself as "an `--nup CxR` request with its sheet" — a
  *request*, not pure geometry — and it already carries `crop_marks` on the same
  footing. `cell()` never reads it; only `slots()` does, so the geometry stays
  free of the distinction.

Three things fall out of this rather than being three more rules:

1. **Padding is the `None`.** A page number above the real count has no index,
   so blank leaves need no second mechanism.
2. **`pages.py` loses its chunking loop** and gains one line — `for sheet in
   slots(...)`. Both kinds of imposition go through one function. This codebase
   has learnt four times what two descriptions of one thing cost (`layout_band`,
   the writer wrapper, `document_page_marks`, `page_furniture`); this is the
   fifth time it is applied rather than learnt.
3. **`Imposition` is untouched.** `check_fits`, `cell` and `crop_mark_segments`
   hold for a booklet unchanged, because a booklet is a 2×1. No new geometry
   enters the codebase.

**Where it lives:** in `impose.py`. Its opening line calls the module "pure
geometry" and gets one clause more, because a twenty-line function does not earn
a module of its own.

**Why `slots` and not `sheet_plan`:** `SheetPlan` is taken — `pages.py` uses it
for a blade's sheets-per-item (decision 27). Two names three letters apart
meaning different things is the trap § 7.3 avoids by not calling `system_gap`
`stave_spacing`.

**A padded cell draws nothing at all** — no header, no footer either. It is not
an empty page but the *absence* of a page, and a footer reading "31 / 32" on a
leaf nobody filled would be a claim about content that does not exist.

**The padding is invisible to the page loop**, and that settles a question that
would otherwise be answered twice: `--pages 30 --booklet` renders thirty pages,
so `{page_count}` says **30**, not 32. The two blank leaves are a fact about the
paper, not about the document; nothing is rendered for them and no placeholder
counts them. Only the run report mentions them.

## Decisions the user made

**One signature, gathered inside itself.** Saddle stitch: every sheet nested in
the next, one staple through the fold. Signatures of a chosen size were
considered and left out — they bring a second count (sheets *and* signatures) and
the question of a part-filled last signature, and nobody has asked. Above roughly
forty pages the creep becomes visible and the stack staples badly; that belongs
in the handbook, not in the code.

**A page count that is not a multiple of four is padded, and said out loud.**
`--pages 30 --booklet` produces 32 pages on 8 sheets and reports the two blanks.
Refusing was the alternative and would have been the more characteristic answer
for this tool — but the blank leaf physically exists the moment paper is folded,
so it is not something invented. Nothing is scaled, so § 8.2 is not touched;
§ 5.1 only demands that it not happen silently, and it does not.

**`--booklet` is its own flag.** Two pages per sheet follow from folding once and
are not the user's choice, so `--nup 2x1` would be a spelling of something the
user cannot vary. The sheet is still named by `--nup-sheet` (default a4) so that
"the sheet" has one spelling; `--nup` alongside `--booklet` is an error.

**One turning edge, named loudly, no switch.** The PDF is built for one flip, and
the run report names it — the same discipline § 8.2 applies to print scaling,
where the message says "Actual size / 100 %" rather than "mind the scaling", and
the same one § 7.5 applies to `back_mirrored`, which assumes the long edge and
documents it. A switch would need a default that is right anyway, and its second
setting would be a guessed number in flag form until somebody's printer proved
otherwise. **This is the one place a later switch would attach**, and § 15's open
question 6 should be rewritten to point here instead of standing open in general.

**Documents are refused, with decision 52's reasoning.** `--booklet` on a
`calendar` or `notebook` is refused by name, exactly as `--nup` is: imposition
destroys links, and for those two generators the links are most of the artefact.
A hand-folded notebook is the obvious casualty and was weighed; allowing it would
turn one rule into a rule with an exception, and the document path would have to
learn the sheet order. It stays available as a later decision.

## The surface

`--booklet`, a one-way switch like `--cover` (§ 11, decision 13) — there is no
`--no-booklet`, because "off, whatever else says" needs a spelling nobody
remembers. **Command line only, never a definition:** imposition is a property of
the *print run*, not of the paper, which is already why `--nup` is not a def key.

Refused, all before page one (§ 12 point 13):

1. `--booklet` together with `--nup` — two ways to say one thing.
2. `--booklet` on a document generator — decision 52's message, verbatim beside it.
3. Two pages that do not fit the sheet at 100 % — `check_fits`, unchanged, with
   its existing arithmetic.
4. `--nup-sheet` or `--crop-marks` without `--nup` **or** `--booklet` — the check
   in `cli.py` gains a second permitted partner.

**`--cover` is deliberately not refused.** § 8.8 already decides it: the cover is
exempt from imposition and comes out at page size. The consequence is worth
stating — the PDF then carries two page sizes, an A5 cover ahead of A4 landscape
sheets. That is already true of `--nup` today, so changing it would be a change
to § 8.8 and not to this design.

The run report:

```
booklet — 30 pages padded to 32 on 8 sheets (2 blank)
print double-sided, flipping on the SHORT edge; on the first sheet,
page 2 must come out behind page 1 — if it does not, switch the flip
```

The short edge is right because the fold is vertical: turning a landscape sheet
about its vertical axis is a flip about its *short* edges. The second sentence is
what makes the first actionable — one sheet and one glance decide it, instead of
the user reasoning about axes.

## Testing

**Without a PDF, because an order does not need one.** `slots(8, …)` is
`[8,1] [2,7] [6,3] [4,5]`, written out by hand. Padding rounds up to a multiple
of four. Every page appears **exactly once** across all sheets. The two numbers
on one sheet side always sum to *P* + 1 — the rule by which a binder recognises a
fold order, and an independent second opinion on the formula.

**With a PDF, because that is the promise.** A six-page booklet with `{page}` in
a footer, read back with `texts_um`: which page number stands on which half of
which sheet. A padded cell draws nothing. Two runs are byte-identical (§ 10.1).

**The regression guard for the refactor:** the existing `--nup` tests must stay
green untouched, because `slots` drives them from then on.

## Documents to update in the same commit

§ 14 and the flag table § 11.1 of the specification, HANDBOOK § 14, decision 54
in `implementation-decisions.md`, § 15's question 6 rewritten to point at the
turning-edge decision above, and `docs/CLAUDE.md`.

## Deliberately not in this version

Signatures of a chosen size; creep or shingling compensation (paper-thickness
dependent, and a guessed number — the same refusal § 7.14 makes for a fold
allowance per crease); booklets from a document generator; and any flip switch.
Each is named here so that a later reader knows it was weighed, not forgotten.
