# `--booklet` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `ctrlgrid <preset> --pages 8 --booklet --nup-sheet 297x210mm` writes four
sheet sides carrying pages 8-1, 2-7, 6-3, 4-5, at 100 %, ready to print
double-sided and fold.

**Architecture:** One new function, `impose.slots()`, says which rendered page
belongs in which cell of which sheet side — for plain n-up (reading order) and
for a booklet (fold order) alike. `Imposition` gains one `booklet: bool` field
that only `slots()` reads; its geometry (`check_fits`, `cell`,
`crop_mark_segments`) is untouched, because a booklet *is* a 2×1. `pages.py`
loses its chunking loop and iterates `slots()` instead, so both kinds of
imposition go through one description.

**Tech Stack:** Python ≥ 3.11, `pytest`, `pypdf` (via `tests/pdfread.py`) for
reading geometry back out, `typer` for the flag.

**Design:** [`docs/superpowers/specs/2026-07-26-booklet-imposition-design.md`](../specs/2026-07-26-booklet-imposition-design.md)

---

## File Structure

| File | Responsibility | Change |
|---|---|---|
| `ctrlgrid/impose.py` | Imposition geometry **and now the sheet order** | Modify: add `booklet` field and `slots()` |
| `ctrlgrid/pages.py` | Page loop; `_write_imposed` places pages | Modify: iterate `slots()`; name `--booklet` in the document refusal |
| `ctrlgrid/loader.py` | Builds `Imposition` from the overrides | Modify: `_resolve_nup` handles `booklet` |
| `ctrlgrid/cli.py` | The flag, the conflict checks, the run report | Modify: `--booklet`, `_overrides`, `_writer_for`, `_report` |
| `tests/test_booklet.py` | The fold order as a pure function, and a booklet read back out of a PDF | Create |
| `tests/test_impose.py` | Plain n-up — the regression guard for the refactor | Unchanged; must stay green |

---

### Task 1: `slots()` — the sheet order, plain n-up first

Doing plain n-up first means the refactor lands with the existing suite as its
guard, before any booklet behaviour exists to confuse a failure.

**Files:**
- Modify: `ctrlgrid/impose.py` (add `slots` after the `Imposition` class, ~line 133)
- Modify: `ctrlgrid/pages.py:1546-1569` (`_write_imposed`)
- Test: `tests/test_booklet.py` (create)

- [ ] **Step 1: Write the failing test**

Create `tests/test_booklet.py`:

```python
"""The sheet order: which page lands in which cell (§ 14).

`impose.slots` is the whole of booklet imposition that is not already there —
an order, and a front/back pairing. It knows no millimetres, so most of this
file needs no PDF at all: a fold order is arithmetic a binder can check.
"""

from __future__ import annotations

from pathlib import Path

import pdfread
import pytest

from ctrlgrid.errors import DefinitionError
from ctrlgrid.impose import Imposition, slots
from ctrlgrid.loader import loads
from ctrlgrid.pages import build
from ctrlgrid.writers.pdf import PdfWriter


def imposition(cols: int, rows: int, *, booklet: bool = False) -> Imposition:
    return Imposition(
        cols=cols,
        rows=rows,
        sheet_width=210_000,
        sheet_height=297_000,
        sheet_name="a4",
        booklet=booklet,
    )


class TestPlainNup:
    """Reading order, in blocks — what `_write_imposed` did by hand."""

    def test_four_pages_on_one_two_by_two_sheet(self) -> None:
        assert slots(4, imposition(2, 2)) == [[0, 1, 2, 3]]

    def test_a_part_full_last_sheet_leaves_empty_cells(self) -> None:
        # Five pages on 2x2: the sixth, seventh and eighth cells hold nothing.
        assert slots(5, imposition(2, 2)) == [[0, 1, 2, 3], [4, None, None, None]]
```

- [ ] **Step 2: Run it and watch it fail**

Run: `uv run pytest tests/test_booklet.py -q`
Expected: FAIL — `ImportError: cannot import name 'slots' from 'ctrlgrid.impose'`

- [ ] **Step 3: Add the `booklet` field to `Imposition`**

In `ctrlgrid/impose.py`, in the `Imposition` dataclass, after `crop_marks`:

```python
    crop_marks: bool = False
    #: § 14: saddle-stitch order rather than reading order. A booklet *is* a
    #: 2x1 imposition, so no geometry changes — `cell`, `check_fits` and
    #: `crop_mark_segments` never read this. Only `slots` does, which is why it
    #: sits on the request beside `crop_marks` and not in the geometry.
    booklet: bool = False
```

- [ ] **Step 4: Write `slots` for the plain case**

In `ctrlgrid/impose.py`, after the `Imposition` class and before `_tick`:

```python
def slots(page_count: int, imposition: Imposition) -> list[list[int | None]]:
    """For every sheet side, which rendered page goes in which cell (§ 14).

    `None` means the cell stays empty — a part-full last sheet in plain n-up,
    or a blank leaf in a booklet. Both kinds of imposition are described here
    and nowhere else: a second description of "what is on this sheet" would
    drift from this one the first time either changed, which this codebase has
    now learnt four times over (`layout_band`, the writer wrapper,
    `document_page_marks`, `page_furniture`).

    Indices are into the rendered pages, 0-based. Position within a sheet is
    the one `Imposition.cell` numbers: 0 is top-left, reading order.
    """
    if imposition.booklet:
        return _folded(page_count)
    per = imposition.per_sheet
    return [
        [index if index < page_count else None for index in range(start, start + per)]
        for start in range(0, max(page_count, 1), per)
    ]
```

- [ ] **Step 5: Run the test again**

Run: `uv run pytest tests/test_booklet.py -q`
Expected: FAIL — `NameError: name '_folded' is not defined`. That is expected at
this step; Task 2 writes it. To see Task 1 green on its own, temporarily nothing
is needed: `_folded` is only reached when `booklet=True`, and no test here sets
it yet — so the failure will instead be at import time only if you typed the name
wrong. If the two tests pass, move on.

- [ ] **Step 6: Add the stub so the module imports**

In `ctrlgrid/impose.py`, directly after `slots`:

```python
def _folded(page_count: int) -> list[list[int | None]]:
    raise NotImplementedError  # Task 2
```

Run: `uv run pytest tests/test_booklet.py -q`
Expected: PASS, 2 tests.

- [ ] **Step 7: Make `_write_imposed` use it**

In `ctrlgrid/pages.py`, replace the body of `_write_imposed` (lines 1559-1569)
with:

```python
    page_w, page_h = document.sheet.width, document.sheet.height
    for sheet in slots(len(rendered), nup):
        writer.begin_page(nup.sheet_width, nup.sheet_height)
        for position, index in enumerate(sheet):
            if index is None:
                continue
            cell = nup.cell(position, page_w, page_h)
            for mark in rendered[index][1]:
                writer.draw(translate(mark, dx=cell.x, dy=cell.y))
        for mark in nup.crop_mark_segments(page_w, page_h):
            writer.draw(mark)
        writer.end_page()
```

And change the import at `ctrlgrid/pages.py:26`:

```python
from ctrlgrid.impose import Imposition, slots
```

- [ ] **Step 8: Run the existing imposition suite — the regression guard**

Run: `uv run pytest tests/test_impose.py -q`
Expected: PASS, all of them. These tests were written against the hand-rolled
loop; they are now the proof that `slots` reproduces it exactly.

- [ ] **Step 9: Commit**

```bash
git add ctrlgrid/impose.py ctrlgrid/pages.py tests/test_booklet.py
git commit -m "impose: one function says what is on a sheet (§ 14)"
```

---

### Task 2: the fold order

**Files:**
- Modify: `ctrlgrid/impose.py` (`_folded`)
- Test: `tests/test_booklet.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_booklet.py`:

```python
class TestTheFoldOrder:
    """§ 14: sheet *i* carries (P-2i, 2i+1) on its front and (2i+2, P-2i-1) on
    its back, with P the count rounded up to a multiple of four. The numbers
    below are 1-based page numbers turned into 0-based indices by hand, so the
    test states the binder's rule and not the code's arithmetic."""

    def test_eight_pages_are_the_classic_order(self) -> None:
        # Pages 8-1, 2-7, 6-3, 4-5 — front and back of two sheets, interleaved.
        assert slots(8, imposition(2, 1, booklet=True)) == [
            [7, 0],
            [1, 6],
            [5, 2],
            [3, 4],
        ]

    def test_six_pages_are_padded_to_eight_and_the_blanks_are_the_outer_leaf(
        self,
    ) -> None:
        # Six pages still need two sheets; pages 7 and 8 do not exist, so the
        # cells that would hold them stay empty — and they are the two halves
        # of the outermost leaf, which is where a binder expects the blanks.
        assert slots(6, imposition(2, 1, booklet=True)) == [
            [None, 0],
            [1, None],
            [5, 2],
            [3, 4],
        ]

    @pytest.mark.parametrize("pages", [4, 8, 12, 16, 20, 40])
    def test_every_page_appears_exactly_once(self, pages: int) -> None:
        placed = [
            index
            for sheet in slots(pages, imposition(2, 1, booklet=True))
            for index in sheet
            if index is not None
        ]
        assert sorted(placed) == list(range(pages))

    @pytest.mark.parametrize("pages", [5, 6, 7, 9, 30])
    def test_the_two_numbers_on_a_sheet_side_always_sum_to_p_plus_one(
        self, pages: int
    ) -> None:
        # The rule a binder recognises a fold order by: on any side of any
        # sheet, the two page numbers add up to one more than the total. It is
        # an independent second opinion on the formula, the way math.log10 is
        # for the logarithmic axis.
        padded = -(-pages // 4) * 4
        for side in slots(pages, imposition(2, 1, booklet=True)):
            left, right = side
            # 0-based indices back to 1-based page numbers; a blank stands for
            # the padded page whose number the sum still needs.
            numbers = [
                (index + 1) if index is not None else None for index in side
            ]
            known = [n for n in numbers if n is not None]
            if len(known) == 2:
                assert sum(known) == padded + 1, (left, right)

    def test_the_sheet_count_is_the_padded_page_count_over_two(self) -> None:
        # Two sides per physical sheet, four pages per sheet: 30 pages padded
        # to 32 is 8 sheets, so 16 sides in the PDF.
        assert len(slots(30, imposition(2, 1, booklet=True))) == 16
```

- [ ] **Step 2: Run them and watch them fail**

Run: `uv run pytest tests/test_booklet.py -q`
Expected: FAIL, 5 tests, `NotImplementedError`.

- [ ] **Step 3: Implement `_folded`**

Replace the stub in `ctrlgrid/impose.py`:

```python
def _folded(page_count: int) -> list[list[int | None]]:
    """Saddle stitch: every sheet nested inside the next (§ 14).

    With *P* the page count rounded up to a multiple of four — a folded sheet
    carries four pages, so the count cannot be anything else — sheet *i*
    carries pages `P - 2i` and `2i + 1` on its front and `2i + 2` and
    `P - 2i - 1` on its back. Returned in printing order, front and back
    interleaved, which is what duplex printing consumes.

    Padding is not a second mechanism: a page number above the real count has
    no index, so it comes back as `None` and nothing is drawn for it.
    """
    padded = -(-page_count // 4) * 4
    sides: list[list[int | None]] = []
    for sheet in range(padded // 4):
        front = (padded - 1 - 2 * sheet, 2 * sheet)
        back = (2 * sheet + 1, padded - 2 - 2 * sheet)
        for side in (front, back):
            sides.append([index if index < page_count else None for index in side])
    return sides
```

- [ ] **Step 4: Run them again**

Run: `uv run pytest tests/test_booklet.py -q`
Expected: PASS, 7 tests.

- [ ] **Step 5: Commit**

```bash
git add ctrlgrid/impose.py tests/test_booklet.py
git commit -m "impose: the saddle-stitch fold order (§ 14)"
```

---

### Task 3: the flag, the wiring and the refusals

**Files:**
- Modify: `ctrlgrid/loader.py:574-584` (`_resolve_nup`)
- Modify: `ctrlgrid/cli.py` (flag ~line 168, `_overrides` 318-367, `_writer_for` 394-396)
- Modify: `ctrlgrid/pages.py:988-995` (the document refusal's wording)
- Test: `tests/test_booklet.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_booklet.py`:

```python
# A5 is 148 x 210 mm; two side by side are 296 x 210, which needs a landscape
# sheet. `--nup-sheet` takes a free size, so the sheet is written out.
A5_LINES = (
    "version: 1\n"
    "page:\n  format: a5\n  margin: 0mm\n"
    "generator: lines\n"
    "families:\n"
    "  - {direction: horizontal, base_spacing: 10mm}\n"
)


def booklet(pages: int, **extra):
    overrides = {
        "pages": pages,
        "booklet": True,
        "nup_sheet": "297x210mm",
        **extra,
    }
    return loads(A5_LINES, overrides, source="test")


class TestTheRun:
    def test_eight_pages_come_out_as_four_sheet_sides(self, tmp_path: Path) -> None:
        path = tmp_path / "b.pdf"
        build(booklet(8), PdfWriter(path))
        assert pdfread.page_count(path) == 4
        width, height = pdfread.media_box_um(path)
        assert (round(width), round(height)) == (297_000, 210_000)

    def test_six_pages_still_take_two_sheets(self, tmp_path: Path) -> None:
        path = tmp_path / "b.pdf"
        build(booklet(6), PdfWriter(path))
        assert pdfread.page_count(path) == 4

    def test_booklet_and_nup_together_are_refused(self) -> None:
        from ctrlgrid.cli import _overrides
        from ctrlgrid.errors import CtrlGridError

        with pytest.raises(CtrlGridError) as excinfo:
            _overrides(
                None, None, None, None, nup="2x2", booklet=True,
            )
        assert "--booklet" in str(excinfo.value) and "--nup" in str(excinfo.value)

    def test_a_document_generator_refuses_the_booklet_by_name(self) -> None:
        text = (
            "version: 1\n"
            "page: {format: a5, margin: 10mm}\n"
            "generator: notebook\n"
            "sections:\n"
            "  - {label: 'Dots', pages: 2, generator: dots,\n"
            "     grid: {x: {base_spacing: 5mm}, y: {base_spacing: 5mm}}}\n"
        )
        with pytest.raises(DefinitionError) as excinfo:
            build(
                loads(text, {"booklet": True, "nup_sheet": "297x210mm"}, source="t"),
                PdfWriter(Path("never-written.pdf")),
            )
        assert "--booklet" in str(excinfo.value)

    def test_a_portrait_sheet_is_refused_with_the_landscape_hint(self) -> None:
        # Two A5 pages need 296 mm of width; A4 portrait has 210. The message
        # has to name the sheet that would work, or the user is left doing the
        # arithmetic the tool just did (§ 12). The named size is the block
        # itself — 296 x 210 — which is a legal free size and fits exactly;
        # A4 landscape (297 x 210) is the same sheet with a millimetre spare.
        with pytest.raises(DefinitionError) as excinfo:
            build(
                loads(A5_LINES, {"pages": 4, "booklet": True}, source="t"),
                PdfWriter(Path("never-written.pdf")),
            )
        assert "296x210mm" in str(excinfo.value)
```

- [ ] **Step 2: Run them and watch them fail**

Run: `uv run pytest tests/test_booklet.py -q -k TestTheRun`
Expected: FAIL — the loader ignores `booklet`, so nothing is imposed.

- [ ] **Step 3: Teach the loader the booklet**

In `ctrlgrid/loader.py`, replace `_resolve_nup` (lines 574-584):

```python
def _resolve_nup(overrides: Mapping[str, Any]) -> Imposition | None:
    """§ 14: build the imposition from `--nup` / `--booklet`, or None."""
    from dataclasses import replace

    crop = bool(overrides.get("crop_marks"))
    if overrides.get("booklet"):
        # § 14: two pages per sheet follow from folding once — they are not the
        # user's to vary, which is why there is no `--nup 2x1` to write here.
        sheet = overrides.get("nup_sheet") or "a4"
        width, height = resolve_size(sheet)
        return Imposition(
            cols=2,
            rows=1,
            sheet_width=width,
            sheet_height=height,
            sheet_name=sheet,
            crop_marks=crop,
            booklet=True,
        )
    if "nup" not in overrides:
        return None
    imposition = parse_nup(overrides["nup"], overrides.get("nup_sheet") or "a4", resolve_size)
    if crop:
        imposition = replace(imposition, crop_marks=True)
    return imposition
```

- [ ] **Step 4: Add the landscape hint to the fit refusal**

In `ctrlgrid/impose.py`, in `check_fits`, replace the `raise` with:

```python
        hint = (
            f"Use a larger --nup-sheet, a smaller page format, or a smaller --nup"
            if not self.booklet
            else
            # § 12: the sheet that *would* work, spelled out. A booklet always
            # needs a landscape sheet — two portrait pages side by side — and
            # the format table stores sizes portrait (§ 9.1), so `--nup-sheet
            # a4` cannot be it. Naming the free size turns the refusal into a
            # copy-paste rather than arithmetic the user repeats.
            f"A booklet needs a landscape sheet: try "
            f"--nup-sheet {_mm(block_w)[:-2]}x{_mm(block_h)[:-2]}mm or larger"
        )
        raise DefinitionError(
            f"{self.cols}x{self.rows} pages at 100 % need {_mm(block_w)} x {_mm(block_h)}, "
            f"sheet {self.sheet_name} is {_mm(self.sheet_width)} x {_mm(self.sheet_height)} "
            f"— imposition never scales (§ 8.2, § 14). {hint}",
            field="booklet" if self.booklet else "nup",
        )
```

- [ ] **Step 5: Add the flag and the conflict check**

In `ctrlgrid/cli.py`, after the `crop_marks` option (line 168):

```python
    booklet: Annotated[
        bool,
        typer.Option("--booklet", help="Impose as a folded, saddle-stitched booklet (§ 14)."),
    ] = False,
```

Pass it through at the `_overrides(...)` call (line 196-199), adding `booklet`
after `crop_marks`:

```python
                nup, nup_sheet, crop_marks, embed_def, skip_unsupported, booklet,
```

In `_overrides`, add the parameter after `skip_unsupported: bool = False`:

```python
    booklet: bool = False,
```

Replace the `nup`/`nup_sheet` guard (lines 338-339) with:

```python
    if nup is not None and booklet:
        # § 14: a booklet is a 2x1 whose order the user cannot vary, so --nup
        # beside it would be a second spelling of one thing.
        raise CtrlGridError("--booklet already imposes 2x1 — drop --nup (§ 14)")
    if nup is None and not booklet and (nup_sheet is not None or crop_marks):
        raise CtrlGridError(
            "--nup-sheet and --crop-marks only mean something with --nup or --booklet (§ 14)"
        )
```

And in the returned dict, beside `"crop_marks"`:

```python
        # § 14: the same one-way switch as --cover — a definition cannot ask
        # for it, because imposition is a property of the print run.
        "booklet": True if booklet else None,
```

- [ ] **Step 6: Name `--booklet` in the document refusal**

In `ctrlgrid/pages.py`, in the refusal at lines 988-995, replace the message:

```python
    if document.nup is not None:
        flag = "--booklet" if document.nup.booklet else "--nup"
        raise DefinitionError(
            f"generator `{document.generator}` writes its own pages, and imposition "
            "works on a page loop it does not have (§ 14). Its links and bookmarks "
            f"would not survive being imposed either — drop {flag}, or impose the "
            "finished PDF with a separate tool",
            field="booklet" if document.nup.booklet else "nup",
        )
```

- [ ] **Step 7: Fix the PNG sheet count**

In `ctrlgrid/cli.py`, in `_writer_for` (lines 394-396), replace the two lines
that compute `sheets`:

```python
    from ctrlgrid.impose import slots

    pages = document.pages.count * sheet_plan(document).per_item
    sheets = pages if document.nup is None else len(slots(pages, document.nup))
```

Reason: the old `-(-pages // per_sheet)` is right for plain n-up and wrong for a
booklet, which pads to a multiple of four — 30 pages are 16 sides, not 15.
`slots` already knows; asking it means the two cannot disagree.

- [ ] **Step 8: Run the tests**

Run: `uv run pytest tests/test_booklet.py tests/test_impose.py tests/test_cli.py -q`
Expected: PASS, all of them.

- [ ] **Step 9: Commit**

```bash
git add ctrlgrid/impose.py ctrlgrid/loader.py ctrlgrid/cli.py ctrlgrid/pages.py tests/test_booklet.py
git commit -m "booklet: the flag, the sheet, and four refusals (§ 14, § 11.1)"
```

---

### Task 4: the run report

**Files:**
- Modify: `ctrlgrid/cli.py:429-436` (`_report`)
- Test: `tests/test_booklet.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_booklet.py`:

```python
class TestTheReport:
    def test_it_names_the_padding_the_sheets_and_the_turning_edge(
        self, tmp_path: Path
    ) -> None:
        # § 8.2's discipline: name the setting, do not say "mind the flip".
        from typer.testing import CliRunner

        from ctrlgrid.cli import app

        definition = tmp_path / "d.yaml"
        definition.write_text(A5_LINES, encoding="utf-8")
        result = CliRunner().invoke(
            app,
            ["-d", str(definition), "--pages", "6", "--booklet",
             "--nup-sheet", "297x210mm", "-o", str(tmp_path / "b.pdf")],
        )
        assert result.exit_code == 0, result.output
        assert "padded to 8" in result.output
        assert "2 sheet(s)" in result.output
        assert "SHORT edge" in result.output
        assert "page 2" in result.output
```

- [ ] **Step 2: Run it and watch it fail**

Run: `uv run pytest tests/test_booklet.py -q -k TestTheReport`
Expected: FAIL — the output still reads "imposed 2x1 …".

- [ ] **Step 3: Write the report branch**

In `ctrlgrid/cli.py`, replace the `if document.nup is not None:` block in
`_report` (lines 429-436):

```python
    if document.nup is not None:
        nup = document.nup
        if nup.booklet:
            padded = -(-pages // 4) * 4
            blanks = padded - pages
            padding = f" padded to {padded}" if blanks else ""
            typer.echo(
                f"  booklet — {pages} page(s){padding} on {padded // 4} sheet(s)"
                + (f" ({blanks} blank)" if blanks else "")
                + f", {nup.sheet_name} at 100 %"
            )
            # § 8.2's rule for the scaling hint, applied to the turning edge:
            # name the setting, and give the one glance that checks it.
            typer.echo(
                "  print double-sided, flipping on the SHORT edge; on the first "
                "sheet, page 2 must come out behind page 1 — if it does not, "
                "switch the flip"
            )
        else:
            sheets = -(-pages // nup.per_sheet)  # ceil
            typer.echo(
                f"  imposed {nup.cols}x{nup.rows} on {nup.sheet_name} "
                f"({nup.sheet_width / 1000:.0f} x {nup.sheet_height / 1000:.0f} mm) — "
                f"{sheets} sheet(s), at 100 %, cut to size"
            )
```

- [ ] **Step 4: Run it again**

Run: `uv run pytest tests/test_booklet.py -q -k TestTheReport`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add ctrlgrid/cli.py tests/test_booklet.py
git commit -m "booklet: the run report names the flip and the blanks (§ 8.2)"
```

---

### Task 5: read the booklet back out of the PDF

The order is proved; this proves the *paper*.

**Files:**
- Test: `tests/test_booklet.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_booklet.py`:

```python
NUMBERED = (
    "version: 1\n"
    "page:\n  format: a5\n  margin: 10mm\n"
    "footer:\n  height: 8mm\n  gap: 2mm\n  center: '{page}'\n"
    "generator: lines\n"
    "families:\n"
    "  - {direction: horizontal, base_spacing: 10mm}\n"
)


class TestTheSheetsThemselves:
    """The order, read off the artefact rather than out of the function."""

    def sides(self, path: Path) -> list[list[str]]:
        """Each sheet side as [left page number, right page number]."""
        found = []
        for index in range(pdfread.page_count(path)):
            numbers = [
                text for text in pdfread.texts_um(path, index)
                if text.content.isdigit()
            ]
            found.append([t.content for t in sorted(numbers, key=lambda t: t.x)])
        return found

    def test_eight_pages_fold_into_eight_one_two_seven_six_three_four_five(
        self, tmp_path: Path
    ) -> None:
        path = tmp_path / "b.pdf"
        build(
            loads(NUMBERED, {"pages": 8, "booklet": True,
                             "nup_sheet": "297x210mm"}, source="t"),
            PdfWriter(path),
        )
        assert self.sides(path) == [
            ["8", "1"], ["2", "7"], ["6", "3"], ["4", "5"],
        ]

    def test_a_padded_cell_draws_nothing_at_all(self, tmp_path: Path) -> None:
        # Not an empty page — the absence of one. A footer reading "7 / 8" on a
        # leaf nobody filled would claim content that does not exist.
        path = tmp_path / "b.pdf"
        build(
            loads(NUMBERED, {"pages": 6, "booklet": True,
                             "nup_sheet": "297x210mm"}, source="t"),
            PdfWriter(path),
        )
        assert self.sides(path) == [["1"], ["2"], ["6", "3"], ["4", "5"]]

    def test_two_runs_are_byte_identical(self, tmp_path: Path) -> None:
        # § 10.1, and it is checked whenever anything is added to the writer.
        first, second = tmp_path / "1.pdf", tmp_path / "2.pdf"
        for path in (first, second):
            build(
                loads(NUMBERED, {"pages": 6, "booklet": True,
                                 "nup_sheet": "297x210mm"}, source="t"),
                PdfWriter(path),
            )
        assert first.read_bytes() == second.read_bytes()
```

- [ ] **Step 2: Run them**

Run: `uv run pytest tests/test_booklet.py -q -k TestTheSheetsThemselves`
Expected: PASS. If the first fails on the *left/right* order, the bug is in
`Imposition.cell`'s position numbering, not in `_folded` — check that position 0
is the left cell of a 2×1 before changing the order.

- [ ] **Step 3: Make one probe fail on purpose**

A probe that cannot fail proves nothing — five did exactly that during the
release sessions, and none of them was the code's fault. Temporarily swap
`front` and `back` in `_folded`, run the test, and confirm
`test_eight_pages_fold_into_eight_one_two_seven_six_three_four_five` fails with
`[['2','7'], ['8','1'], …]`. Then put it back and re-run to green.

- [ ] **Step 4: Run the whole suite**

Run: `uv run pytest -q 2>&1 | tail -2 && uv run ruff check .`
Expected: all green, ruff clean.

- [ ] **Step 5: Commit**

```bash
git add tests/test_booklet.py
git commit -m "booklet: the fold order read back off the sheets (§ 13.2)"
```

---

### Task 6: the documents, in the same breath

**Files:**
- Modify: `docs/pflichtenheft-vorlagengenerator.md` (§ 14 M6 block, § 11.1 flag table, § 15 question 6)
- Modify: `docs/implementation-decisions.md` (decision 54)
- Modify: `HANDBOOK.md` (§ 14)
- Modify: `docs/CLAUDE.md` (feature list, test count)

- [ ] **Step 1: § 11.1 — the flag table**

Add a row after `--nup-sheet`:

```markdown
| `--booklet` | Als gefalztes Heft ausschießen, **ohne Skalierung** | § 14 |
```

- [ ] **Step 2: § 14 — the M6 block**

After the "Ausschießen skaliert nicht — niemals" passage, add:

```markdown
**`--booklet` — Rückstichheftung (2026-07-26).** Ein gefalztes Heft: Bogen *i*
trägt vorne die Seiten `P − 2i` und `2i + 1`, hinten `2i + 2` und `P − 2i − 1`,
mit *P* der auf ein Vielfaches von vier aufgerundeten Seitenzahl. Geometrisch
ist das ein 2×1, also gilt alles oben Gesagte unverändert — insbesondere, dass
nicht skaliert wird. Was hinzukommt, ist allein die **Reihenfolge**.

Eine Seitenzahl, die kein Vielfaches von vier ist, wird **aufgefüllt und
gemeldet**, nicht abgelehnt: Das leere Blatt entsteht physisch, sobald man
faltet, und es wird kein Maß verändert. Eine aufgefüllte Zelle zeichnet gar
nichts — auch keinen Kopf und keinen Fuß —, und `{page_count}` zählt sie nicht:
Sie ist eine Tatsache über das Papier, nicht über das Dokument.

**Eine Lage**, ineinandergelegt und durch den Falz geheftet. Lagen wählbarer
Größe sind bewusst nicht gebaut. Ab etwa vierzig Seiten wird der Falzversatz
sichtbar; eine Falzversatz-Kompensation wäre eine geratene Zahl und entfällt aus
demselben Grund wie die Falzzugabe je Rille (§ 7.14).

**Eine Wendekante, laut benannt.** Das PDF ist für das Wenden über die **kurze
Kante** gebaut — der Falz läuft senkrecht, das Blatt wird also um seine
senkrechte Achse gedreht. Der Laufbericht nennt die Einstellung und den einen
Handgriff, der sie prüft (Seite 2 muss hinter Seite 1 liegen), wie § 8.2 es für
die Skalierung verlangt. Kein Schalter: siehe § 15 Punkt 6.

**Abgelehnt wird, vor Seite eins:** `--booklet` neben `--nup` (zwei Wege für
dasselbe), `--booklet` an einem Dokument-Generator (wie `--nup`, Entscheidung
52), und ein Bogen, auf den zwei Seiten bei 100 % nicht passen — mit dem
Landschaftsformat in der Meldung, denn die Formattabelle steht im Hochformat
(§ 9.1) und `--nup-sheet a4` kann es deshalb nie sein. `--cover` bleibt erlaubt
und vom Ausschießen ausgenommen (§ 8.8).
```

- [ ] **Step 3: § 15 question 6 — point it here**

Replace question 6 with:

```markdown
6. **Wendekante beim Duplexdruck.** Zwei Stellen setzen eine voraus:
   `back_mirrored` (§ 7.5) die lange Kante, `--booklet` (§ 14) die kurze — beide
   nennen sie im Laufbericht bzw. im README, statt zu raten. Ob ein Schalter
   nötig ist, zeigt erst die Praxis; er wäre eine einzige Fallunterscheidung und
   säße bei `--booklet` in `_folded`, wo die Vorder- und Rückseite eines Bogens
   entstehen.
```

- [ ] **Step 4: decision 54**

Append to `docs/implementation-decisions.md`:

```markdown
## 54. A booklet is an order, not a geometry (§ 14)

The specification described `--nup` and nothing that folds. Booklet imposition
was the one feature genuinely absent from it, and building it turned out to need
no new geometry at all: a booklet **is** a 2×1 imposition, so `check_fits`,
`cell` and `crop_mark_segments` hold unchanged. What it adds is which page goes
in which cell.

So `impose.slots()` answers that for *both* kinds of imposition, and
`_write_imposed` lost its own chunking loop. One description of "what is on this
sheet", for the same reason `layout_band`, the writer wrapper,
`document_page_marks` and `page_furniture` each exist: two descriptions drift the
first time either changes. `Imposition` gained one field, `booklet`, which only
`slots` reads — it sits beside `crop_marks` because the dataclass is a *request*,
not the geometry.

Four calls were made where the specification was silent:

- **A page count off a multiple of four is padded and reported, not refused.**
  Refusing is the more characteristic answer for this tool, and it is the wrong
  one here: the blank leaf exists the moment paper is folded, so nothing is
  invented, and no measure is changed, so § 8.2 is untouched. § 5.1 asks only
  that it not happen silently. The padding never reaches the page loop, so
  `{page_count}` still reports what the user asked for.
- **`--booklet` is its own flag**, not `--nup 2x1 --booklet-order`: two pages per
  sheet follow from folding once and are not the user's to vary. The sheet keeps
  one spelling, `--nup-sheet`.
- **One turning edge, named in the run report, no switch.** The same discipline
  § 8.2 applies to print scaling and § 7.5 to `back_mirrored`. A switch would
  need a right default anyway, and its second setting would be untested. § 15
  point 6 now names `_folded` as the place it would attach.
- **Documents are refused**, inheriting decision 52 — a hand-folded notebook is
  the obvious casualty, and it was weighed rather than overlooked. Allowing it
  would make one rule a rule with an exception and would put the sheet order on
  the document path.

One usability call the design had not foreseen and the plan added: a booklet
always needs a **landscape** sheet, and the format table stores sizes portrait
(§ 9.1), so `--nup-sheet a4` can never be right. Rather than turn the sheet
silently — that would be the tool deciding, against § 9.1's one convention — the
fit refusal names the free size that works, so the fix is a copy-paste.
```

- [ ] **Step 5: HANDBOOK § 14**

Add a subsection under "14. N-up imposition" showing the command and the two
sentences a reader needs: the landscape sheet, and the short-edge flip.

```markdown
### Booklets

    ctrlgrid millimeter-a4 --format a5 --pages 8 --booklet \
        --nup-sheet 297x210mm -o booklet.pdf

Four sheet sides carrying pages 8-1, 2-7, 6-3, 4-5. Print double-sided,
flipping on the **short** edge, fold the stack in half and staple through the
fold.

Two things to know. The sheet must be **landscape** — two portrait pages sit
side by side — and `--nup-sheet a4` is portrait, so write the size out. And a
page count that is not a multiple of four is padded with blank leaves, which the
run reports; nothing is scaled to make it come out even.
```

- [ ] **Step 6: `docs/CLAUDE.md`**

Add a row to the *Done* table and update the test count from 1247 to whatever
`uv run pytest 2>&1 | tail -1` reports:

```markdown
| post-0.11 `--booklet` | saddle-stitch imposition (§ 14, decision 54) — the one feature the specification never described. A booklet *is* a 2×1, so no geometry was added: `impose.slots()` says which page goes in which cell for both kinds of imposition, and `_write_imposed` lost its own loop. Padding is the `None` a missing page has; a padded cell draws nothing and `{page_count}` does not count it. One turning edge, named in the run report, no switch |
```

- [ ] **Step 7: Verify and commit**

```bash
uv run pytest -q 2>&1 | tail -2 && uv run ruff check .
git add -A
git commit -m "docs: --booklet in the specification, the handbook and decision 54"
```

---

## Self-Review

**Spec coverage.** Every section of the design maps to a task: the mechanism and
`slots` → Task 1–2; the tuple order, interleaving and the `booklet` field → Task 1
Step 3 and Task 2 Step 3; the surface and all four refusals → Task 3; the run
report → Task 4; the testing section → Tasks 1, 2 and 5; the documents → Task 6.
The design's "deliberately not in this version" list needs no task by definition.

**One thing the design did not settle, added here:** a booklet always needs a
landscape sheet, and `--nup-sheet a4` is portrait. Task 3 Step 4 answers it with
a refusal that names the working size rather than turning the sheet silently.
This is flagged to the user rather than buried.

**Types.** `slots(page_count: int, imposition: Imposition) -> list[list[int | None]]`
is used with that signature in `pages.py` (Task 1 Step 7), `cli.py` (Task 3
Step 7) and every test. `_folded(page_count: int)` is stubbed in Task 1 Step 6
and implemented in Task 2 Step 3 with the same signature. `Imposition.booklet`
is added in Task 1 Step 3 and read in Task 1 Step 4, Task 3 Steps 4 and 6, and
Task 4 Step 3.

**Placeholders.** None: every step that changes code shows the code, every
command shows what to expect.
