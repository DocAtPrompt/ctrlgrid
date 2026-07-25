# The media check for document generators — design

**Date:** 2026-07-25. Small, and it closes the gap the preset guard found:
§ 12.1 never reaches a document generator, so a calendar's weights and colours
are measured against no medium at all.

## Why it is missing

`media.py` reads a *blade's* marks — `_sample` builds a geometry, takes page 0's
context and calls `generate`. A document generator refuses `generate` by design
(it owns pages), so `media_findings` raises on one, and `_document_preflight`
never calls it. Both halves have to change.

## What it will do

1. **`_sample` learns the document seam.** For a document generator it walks
   `blade.pages(cfg, area, q)` — the same seam the capability check already
   samples — and keeps **one representative mark per distinct (kind, weight,
   colour)**. Bounded memory (a dozen marks, not the 74 580 a year planner
   draws), and complete: every page is looked at.

2. **Every page, not one per page kind.** Sampling the first page of each kind
   would be cheaper and would silently miss the case that matters — a marked
   day's own colour appears only on the pages carrying that date, so a birthday
   in May would go unmeasured. The full walk costs 0.17 s on a 456-page
   calendar, once per run.

3. **A page's `background` is a colour too.** The title page's full-sheet fill
   is a page property the handle paints, not a mark, so the walk feeds it into
   the colour findings as well — on a grayscale device that fill is precisely
   the thing that turns to mud.

4. **`_document_preflight` runs the check** and folds its findings into the
   geometry's notices, exactly as `preflight` does, so `--strict` works there
   too and the run report says the same kind of thing for both paths.

Spacing findings need no work: they read `periodic_axes`, and a document
reports none — a calendar has no repeating step to land on a pixel grid.

## Tests

- a document on a grayscale device names a colour that appears **only on a late
  page** — the one-page-per-kind shortcut would pass this and be wrong;
- a hairline in a document raises the round-to-zero error, as it does for a blade;
- `calendar-a4` on paper is clean, and `test_every_shipped_preset_is_clean_on_its_own_medium`
  drops its skip — the skip is the bug this fixes;
- `--strict` turns a document's finding into an error.
