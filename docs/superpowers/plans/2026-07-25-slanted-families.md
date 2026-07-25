# Slanted line families Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `direction: 55deg` on a `lines` family — parallel lines at any angle, spaced perpendicular, clipped to the pattern area — and the calligraphy guide sheet it exists for.

**Architecture:** No new seam and no new query. The cycle machinery is reused unchanged on the *perpendicular* axis; the existing Liang–Barsky clipper moves out of `perspective.py` into a shared module so there is one clipper, not two. A slanted family reports no periodic axis, which is how § 7.1's "no snapping" falls out of the existing § 8.3 machinery instead of a new rule.

**Tech Stack:** Python 3.11+, pydantic v2, integer micrometres, `Fraction` for exact clipping, `pytest`, `ruff`.

**Design:** [`2026-07-25-slanted-families-design.md`](../specs/2026-07-25-slanted-families-design.md) — the two decisions and their reasoning. § 7.1 of the specification decides everything else and was written years before this.

---

### Task 1: one clipper, in one place

**Files:** create `ctrlgrid/clip.py`; modify `ctrlgrid/generators/perspective.py`; create `tests/test_clip.py`

- [ ] **Step 1** — move `_clip` from `perspective.py` into `ctrlgrid/clip.py` as `clip_to_area(a, b, area)`, docstring and exact-`Fraction` body unchanged, and import it in `perspective.py`.
- [ ] **Step 2** — `tests/test_clip.py`: a segment wholly inside is returned unchanged; one crossing two edges is cut at both; one that misses returns `None`; one that grazes a corner returns `None`; the ends are each rounded once (a 45° ray through a 100 × 100 area ends exactly on the corner).
- [ ] **Step 3** — `uv run pytest -q` — the perspective suite must stay green *without edits*, which is the point of a pure move.
- [ ] **Step 4** — commit: `clip: one Liang-Barsky, shared — perspective keeps using it, lines is next`.

### Task 2: the cycle, read backwards

**Files:** modify `ctrlgrid/cycles.py`; modify `tests/test_cycles.py`

- [ ] **Step 1** — failing tests for a new `Cycle.positions_between(base_um=…, lower_um=…, upper_um=…, offset_um=0)`:
  - with `lower_um=0` it yields exactly what `positions(extent_um=upper)` yields, index for index;
  - with a negative `lower_um` it also yields indices −1, −2, … below the offset;
  - `spacing: [2, 1]` about zero gives −1000, 0, 2000, 3000 for `base_um=1000` — the cycle read backwards, **not** the forward positions negated;
  - the index of a position below zero is negative, so `weight.at(index)` and `color[index % len]` keep running in step.
- [ ] **Step 2** — implement. The existing position formula already works for negative indices, because Python's floor division makes `(index // n) * total + prefix_sums[index % n]` continue the cycle downwards; walk down from −1 while the position is at or above `lower_um`, reverse, then walk up from 0 as `_walk` does. Say so in the comment — it is the whole reason no new arithmetic is needed.
- [ ] **Step 3** — `uv run pytest tests/test_cycles.py -q`.
- [ ] **Step 4** — commit: `cycles: positions below zero, the cycle read backwards (§ 7.1)`.

### Task 3: the angle on a family

**Files:** modify `ctrlgrid/generators/lines.py`; create `tests/test_slanted.py`

- [ ] **Step 1** — failing tests:
  - `direction: 55deg` validates and `Family.angle_deg` is 55.0;
  - `direction: 235deg` is the same family as `55deg` (angles are taken modulo 180 — a line has no direction);
  - `horizontal` and `vertical` still validate and keep `Family.axis`;
  - `law: log10` with an angle is refused, naming both;
  - `governing: true` with an angle is refused, naming § 7.1 (snapping is ruled out, so there is nothing to govern);
  - `periodic_axes` returns nothing for a slanted family.
- [ ] **Step 2** — implement: `DirectionField` accepts `<number>deg` through `parse_angle` instead of refusing it; `Family.is_slanted`, `Family.angle_deg`; `axis` raises for a slanted family (nothing may ask); the two refusals as model validators; `periodic_axes` skips slanted families.
- [ ] **Step 3** — run; the existing `tests/test_lines.py` must stay green untouched.
- [ ] **Step 4** — commit: `lines: a family may be given an angle (§ 7.1)`.

### Task 4: drawing it

**Files:** modify `ctrlgrid/generators/lines.py`; modify `tests/test_slanted.py`

- [ ] **Step 1** — failing tests, the first two being the ones that matter:
  - **`0deg` equals `horizontal` mark for mark**, and `90deg` equals `vertical` — same positions, same weights, same colours, same order. The sharpest test there is: the general path has to reproduce the special case exactly.
  - **the perpendicular distance between neighbouring 55° lines is `base_spacing`**, computed from the drawn endpoints rather than from the code's own numbers.
  - every mark lies inside the pattern area (clipped);
  - a 45° family on a square area has a line running corner to corner;
  - `spacing: [2, 1]` is symmetric about line 0;
  - `count: 3` draws three lines, all on the positive side of line 0;
  - `extent: { start: -40mm, end: 0mm }` keeps only the lines below line 0.
- [ ] **Step 2** — implement `_slanted_family`:
  - the perpendicular `n` is the line direction turned 90°, its **sign chosen so it points towards the area's centre** (so `90deg` counts into the sheet, like `vertical`; when the centre lies exactly on line 0 — a square's diagonal — keep the canonical `(-sin, cos)`);
  - project the four corners onto `n` for the range to walk;
  - for each `(index, d)` from `positions_between`, build the line through `d · n` along the direction and clip it with `clip_to_area`; skip what does not cross;
  - weight, colour, dash and cap exactly as the straight path does — one expression, not a copy.
- [ ] **Step 3** — run; then `uv run pytest -q` whole.
- [ ] **Step 4** — commit: `lines: slanted families, spaced perpendicular and clipped to the area`.

### Task 5: measure a real sheet

**Files:** create `tests/test_pdf_slanted.py`

- [ ] **Step 1** — a definition with a single 55° family at `base_spacing: 8mm`, built to a real PDF; read the segments back with `tests/pdfread.py`, take two neighbouring lines and compute the perpendicular distance between them out of the file. It must be 8 mm to within a micrometre-level tolerance. Also assert the drawn angle is 55° to within a hundredth of a degree.
- [ ] **Step 2** — render it and *look* at it (`pdftoppm -png -r 150`): the slant fills the sheet corner to corner and no line runs outside the area.
- [ ] **Step 3** — commit: `lines: the slant measured out of a finished PDF`.

### Task 6: the guide sheet, and the documents

**Files:** `ctrlgrid/data/presets/calligraphy-a4.yaml`, `examples/14-calligraphy-italic.yaml` (+ PDF + preview), `examples/README.md`, `HANDBOOK.md`, `README.md`, `docs/pflichtenheft-vorlagengenerator.md` (§ 7.1), `docs/implementation-decisions.md` (48), `docs/CLAUDE.md`

- [ ] **Step 1** — the preset: an italic guide — a ruled cycle of ascender / body / descender / air (`spacing: [2, 1, 1, 3]`, which is § 7.1's own example) crossed by a 55° family. Comment it the way the shipped presets are commented: the preset is the documentation (§ 9.3).
- [ ] **Step 2** — the gallery example, its PDF and its 600 px preview, plus its row in `examples/README.md`.
- [ ] **Step 3** — § 7.1 gains the two decisions in German (line 0 through the origin, both directions, negative perpendicular coordinates allowed); decision 48 records why the anchor is the origin and not a corner or the centre; the handbook's `lines` section gains the angle with the calligraphy example; the README's generator table line for `lines` gains "slanted".
- [ ] **Step 4** — `uv run pytest -q && uv run ruff check .`, then commit everything in one block.

---

## Self-review

Spec coverage: § 7.1's perpendicular spacing/offset/extent → task 4; clipping → tasks 1 and 4; "no snapping" → task 3 (no axis reported, `governing` refused) plus the handle's existing § 8.3 path, which already errors on a named axis with nothing periodic; the design's anchor decision → task 4; its scope decision (no `nw` unit) → nothing to build, recorded in task 6's decision 48.

Names used consistently: `clip_to_area`, `Cycle.positions_between`, `Family.is_slanted`, `Family.angle_deg`, `_slanted_family`.

Left to looking rather than reasoning, deliberately: the sign rule for the perpendicular (task 4 states it, the `90deg == vertical` test proves it) and the rendered sheet in task 5.
