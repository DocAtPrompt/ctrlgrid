# Notebook Sheet Plan Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A notebook section filled by `maze` with `solution: separate_page` or
`back_mirrored` builds instead of being refused, with every solution paired to its
own puzzle and every maze stable against unrelated pages before it.

**Architecture:** `Fill` carries the page's index within its section, so
`document_page_marks` hands the blade a page context of the section's own — index
0…n−1 — which makes a section behave exactly like a small standalone run. The
notebook asks each section's blade for its `sheets()` and emits that many pages
per item. Mirroring is handle work applied in `_document_content`, where marks
reach sheet coordinates.

**Tech Stack:** Python ≥ 3.11, `pytest`, `pypdf` via `tests/pdfread.py`.

**Design:** [`docs/superpowers/specs/2026-07-26-notebook-sheet-plan-design.md`](../specs/2026-07-26-notebook-sheet-plan-design.md)

---

## File Structure

| File | Responsibility | Change |
|---|---|---|
| `ctrlgrid/document.py` | the document seam: `DocumentPage`, `Fill` | Modify: `Fill.index`/`Fill.count`, `DocumentPage.mirrored` |
| `ctrlgrid/pages.py` | page loop; what is on a document page | Modify: section-local context in `document_page_marks`; mirror in `_document_content`; the § 7.5 duplex refusal reaches documents |
| `ctrlgrid/generators/notebook.py` | the section page plan | Modify: `pages`, `page_count`, `_section_starts`, `check` |
| `ctrlgrid/cli.py` | the run report | Modify: report an inserted alignment leaf |
| `tests/test_notebook_sheets.py` | the whole feature | Create |

---

### Task 1: a section's blade sees a run of its own

The smallest change that fixes the seed instability, and it stands alone: with
`per_item` still 1 everywhere, nothing about the page plan moves yet.

**Files:**
- Modify: `ctrlgrid/document.py` (the `Fill` dataclass, ~line 53)
- Modify: `ctrlgrid/pages.py:1120-1137` (`document_page_marks`)
- Modify: `ctrlgrid/generators/notebook.py:224-230` (the `Fill(...)` it builds)
- Test: `tests/test_notebook_sheets.py` (create)

- [ ] **Step 1: Write the failing test**

Create `tests/test_notebook_sheets.py`:

```python
"""A sheet plan inside a notebook section (§ 7.13, decision 55).

Decision 52 refused this and said why: § 7.13 did not settle what a per-section
sheet plan means. It does now — a section is a definition in miniature, so its
blade sees a page context of the section's own.
"""

from __future__ import annotations

from pathlib import Path

import pdfread
import pytest

from ctrlgrid.errors import DefinitionError
from ctrlgrid.loader import loads
from ctrlgrid.pages import build
from ctrlgrid.writers.pdf import PdfWriter


def notebook(sections: str, *, title: bool = False) -> str:
    return (
        "version: 1\n"
        "page: {format: a5, margin: 10mm}\n"
        "generator: notebook\n"
        + ('title_page: {title: "N"}\n' if title else "")
        + "sections:\n" + sections
    )


DOTS = (
    '  - {label: "Dots", pages: 2, generator: dots,\n'
    "     grid: {x: {base_spacing: 5mm}, y: {base_spacing: 5mm}}}\n"
)


def maze_section(pages: int, solution: str, label: str = "Mazes") -> str:
    return (
        f'  - {{label: "{label}", pages: {pages}, generator: maze,\n'
        f"     cells: {{x: 8, y: 10}}, seed: 4711, solution: {solution}}}\n"
    )


def sheet(tmp_path: Path, definition: str, name: str = "n.pdf") -> Path:
    path = tmp_path / name
    build(loads(definition, source="test"), PdfWriter(path))
    return path


class TestASectionIsARunOfItsOwn:
    """§ 7.13: "Ein Abschnitt ist eine Definition im Kleinen." So what precedes
    a section must not reach into it — the bug decision 52 recorded was a title
    page silently redrawing every maze."""

    def test_a_title_page_before_it_does_not_change_the_mazes(
        self, tmp_path: Path
    ) -> None:
        plain = sheet(tmp_path, notebook(maze_section(2, "none")), "plain.pdf")
        titled = sheet(
            tmp_path, notebook(maze_section(2, "none"), title=True), "titled.pdf"
        )
        # The maze pages are the last two of each document. Their walls must be
        # identical drawings, not merely the same count.
        for offset in (2, 1):
            a = pdfread.subpaths_um(plain, pdfread.page_count(plain) - offset)
            b = pdfread.subpaths_um(titled, pdfread.page_count(titled) - offset)
            assert a == b

    def test_two_sections_of_the_same_maze_draw_the_same_pages(
        self, tmp_path: Path
    ) -> None:
        # Two identical sections are two identical runs, so page 1 of each is
        # the same maze. Before this, the second section's index carried on
        # from the first and every maze differed.
        path = sheet(
            tmp_path,
            notebook(maze_section(1, "none", "A") + maze_section(1, "none", "B")),
        )
        pages = pdfread.page_count(path)
        assert pdfread.subpaths_um(path, pages - 2) == pdfread.subpaths_um(path, pages - 1)
```

- [ ] **Step 2: Run it and watch it fail**

Run: `uv run pytest tests/test_notebook_sheets.py -q`
Expected: FAIL, both tests — the mazes differ, because the blade is handed the
document page index.

- [ ] **Step 3: Give `Fill` the section-local position**

In `ctrlgrid/document.py`, in the `Fill` dataclass, after `config: Any`:

```python
    generator: str
    config: Any
    index: int = 0
    """This page's 0-based position **within its section** (§ 7.13).

    A section is a definition in miniature, so its blade is handed a page
    context of the section's own rather than the document's. That is what makes
    a maze section stable against a title page in front of it — and what makes
    `page.index % 2` mean puzzle-or-solution again (§ 7.5)."""
    count: int = 1
    """How many pages the section has, for that context's `count`."""
```

- [ ] **Step 4: Build the section's context in `document_page_marks`**

In `ctrlgrid/pages.py`, replace the body of `document_page_marks` (lines
1132-1137):

```python
    yield from page.marks
    if page.fill is not None:
        from ctrlgrid import generators

        blade = generators.get(page.fill.generator)
        yield from blade.generate(
            page.fill.config, area=area, page=_fill_context(page.fill, context), q=q
        )
```

And add, directly after the function:

```python
def _fill_context(fill: Fill, document_context: PageContext) -> PageContext:
    """The page context a filled page's blade is handed (§ 7.13).

    Not the document's: a section is a definition in miniature, so its blade
    counts from the section's own zero. Two readings depend on it — `maze` takes
    `page.index % 2` for puzzle-or-solution and `page.index // 2` for the item
    behind the seed (§ 7.5) — and both were wrong while the document's index
    reached through, which is why an unrelated title page redrew every maze.

    The name stays the document's: `{name}` belongs to the run, and a notebook
    has no name list. The seed material is rebuilt from the section index, so
    the same section in two documents draws the same pages (§ 10.1) — with no
    run seed, because a document path has none (`_document_context` passes
    empty material today). `maze` does not read it at all; it seeds from its own
    `seed` field and `page.index`. This is here for the blade that one day does.
    """
    return PageContext(
        index=fill.index,
        number=fill.index + 1,
        count=fill.count,
        name=document_context.name,
        is_even=(fill.index + 1) % 2 == 0,
        seed_material=seed_material(0, fill.index),
        pixel_snap=document_context.pixel_snap,
    )
```

Add `Fill` to the imports from `ctrlgrid.document` at the top of `pages.py`.

- [ ] **Step 5: Have the notebook number its section's pages**

In `ctrlgrid/generators/notebook.py`, in `pages`, replace the `DocumentPage(...)`
built in the section loop (lines 224-230):

```python
                yield DocumentPage(
                    dest=dest,
                    kind="section",
                    marks=(),
                    fill=Fill(
                        section.generator, section.config,
                        index=number - 1, count=section.pages,
                    ),
                    placeholders=placeholders,
                )
```

- [ ] **Step 6: Run the tests**

Run: `uv run pytest tests/test_notebook_sheets.py tests/test_notebook.py -q`
Expected: PASS.

- [ ] **Step 7: Confirm the gallery has not moved**

The notebook example and preset use only page-invariant blades, so their bytes
must be untouched. This is the guard that says the change reaches only what it
should.

```bash
uv run ctrlgrid -d examples/15-notebook.yaml -o /tmp/nb-check.pdf --force --quiet
cmp /tmp/nb-check.pdf examples/15-notebook.pdf && echo "byte-identical"
```

Expected: `byte-identical`.

- [ ] **Step 8: Commit**

```bash
git add ctrlgrid/document.py ctrlgrid/pages.py ctrlgrid/generators/notebook.py tests/test_notebook_sheets.py
git commit -m "notebook: a section's blade is handed a run of its own (§ 7.13)"
```

---

### Task 2: a section that needs two sheets per item gets them

**Files:**
- Modify: `ctrlgrid/generators/notebook.py` (`pages`, `page_count`, `_section_starts`, and the refusal in `check` at lines 158-177)
- Test: `tests/test_notebook_sheets.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_notebook_sheets.py`:

```python
class TestTheSheetPlanIsCarriedOut:
    """§ 7.5 on the blade path: "`--pages 10` ergibt zehn Rätsel auf zwanzig
    Blättern." One rule for both paths, so `pages:` counts items here too."""

    def test_ten_puzzles_take_twenty_pages(self, tmp_path: Path) -> None:
        path = sheet(tmp_path, notebook(maze_section(10, "separate_page")))
        # contents + 20 maze pages, no title page and no divider asked for.
        assert pdfread.page_count(path) == 1 + 20

    def test_the_solution_belongs_to_the_puzzle_before_it(
        self, tmp_path: Path
    ) -> None:
        # § 7.5: odd sheets are puzzles, even ones their solutions. What makes
        # a solution *that* puzzle's is geometric: the maze walls are the same
        # drawing, and the solution page adds a path on top. So the puzzle's
        # walls must all appear on the solution page.
        path = sheet(tmp_path, notebook(maze_section(2, "separate_page")))
        first = pdfread.page_count(path) - 4
        puzzle = {tuple(p) for p in pdfread.subpaths_um(path, first)}
        solution = {tuple(p) for p in pdfread.subpaths_um(path, first + 1)}
        assert puzzle and puzzle <= solution
        assert len(solution) > len(puzzle)

    def test_a_second_puzzle_is_a_different_maze(self, tmp_path: Path) -> None:
        path = sheet(tmp_path, notebook(maze_section(2, "separate_page")))
        first = pdfread.page_count(path) - 4
        assert pdfread.subpaths_um(path, first) != pdfread.subpaths_um(path, first + 2)

    def test_the_contents_still_names_the_page_the_next_section_starts_on(
        self, tmp_path: Path
    ) -> None:
        # `page_count` and `_section_starts` share one arithmetic, and doubling
        # a section must move both. The contents page prints the number, and the
        # section's own header answers `{section}` — two independent facts.
        definition = (
            "version: 1\n"
            "page: {format: a5, margin: 10mm}\n"
            'header: {height: 8mm, gap: 2mm, left: "{section}"}\n'
            'footer: {height: 8mm, gap: 2mm, right: "{page}"}\n'
            "generator: notebook\n"
            "sections:\n" + maze_section(2, "separate_page") + DOTS
        )
        path = sheet(tmp_path, definition)
        listed = {}
        for text in pdfread.texts_um(path, 0):
            listed[round(text.y)] = listed.get(round(text.y), []) + [text]
        entries = {}
        for line in listed.values():
            words = sorted(line, key=lambda t: t.x)
            if len(words) == 2 and words[1].content.isdigit():
                entries[words[0].content] = int(words[1].content)
        assert entries["Mazes"] == 2          # straight after the contents
        assert entries["Dots"] == 2 + 4       # four maze pages, then Dots
```

- [ ] **Step 2: Run them and watch them fail**

Run: `uv run pytest tests/test_notebook_sheets.py -q -k TestTheSheetPlan`
Expected: FAIL — the run is still refused by `check`.

- [ ] **Step 3: Drop the refusal, ask the blade instead**

In `ctrlgrid/generators/notebook.py`, replace the block at lines 158-177 (the
`sheets`/`plan` refusal) with:

```python
            # A blade may state that one *item* needs more than one sheet —
            # `maze` with separate solution pages (§ 7.5, decision 27). § 7.13
            # now says what that means in a section: `pages:` goes on counting
            # items, so the section is that many sheets longer (decision 55).
```

- [ ] **Step 4: Add the plan to the three places that count pages**

In `ctrlgrid/generators/notebook.py`, add a helper after `_section_starts`:

```python
    def _sheets_per_item(self, section) -> int:
        """§ 7.5's sheet plan for one section's blade, or 1 (decision 55)."""
        from ctrlgrid.generators import get

        sheets = getattr(get(section.generator), "sheets", None)
        plan = sheets(section.config) if sheets else None
        return plan.per_item if plan else 1

    def _section_pages(self, section) -> int:
        """How many pages the section occupies, dividers excluded."""
        return section.pages * self._sheets_per_item(section)
```

Then in `page_count`, replace `total += section.pages + (1 if section.divider else 0)`:

```python
            total += self._section_pages(section) + (1 if section.divider else 0)
```

And in `_section_starts`, replace `number += section.pages + (1 if section.divider else 0)`:

```python
            number += self._section_pages(section) + (1 if section.divider else 0)
```

- [ ] **Step 5: Emit the pages**

In `ctrlgrid/generators/notebook.py`, in `pages`, replace the
`for number in range(1, section.pages + 1):` loop with:

```python
            for number in range(1, self._section_pages(section) + 1):
                dest = (
                    _page_dest(index, number)
                    if section.divider or number > 1
                    else _section_dest(index)
                )
                yield DocumentPage(
                    dest=dest,
                    kind="section",
                    marks=(),
                    fill=Fill(
                        section.generator, section.config,
                        index=number - 1, count=self._section_pages(section),
                    ),
                    placeholders=placeholders,
                )
```

- [ ] **Step 6: Run the tests**

Run: `uv run pytest tests/test_notebook_sheets.py tests/test_notebook.py -q`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add ctrlgrid/generators/notebook.py tests/test_notebook_sheets.py
git commit -m "notebook: a section carries out its blade's sheet plan (§ 7.13, § 7.5)"
```

---

### Task 3: `back_mirrored` — the mirror, and the refusal it inherits

**Files:**
- Modify: `ctrlgrid/document.py` (`DocumentPage.mirrored`)
- Modify: `ctrlgrid/pages.py:1241-1242` (`_document_content`) and the pre-flight
  around line 611 (`_refuse_mirroring_that_cannot_line_up`)
- Modify: `ctrlgrid/generators/notebook.py` (`pages` sets `mirrored`)
- Test: `tests/test_notebook_sheets.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_notebook_sheets.py`:

```python
class TestBackMirrored:
    """§ 7.5: the solution goes on the back of the same sheet, mirrored about
    the **sheet's** vertical centre, so it shows through against the light."""

    def test_the_solution_page_is_the_mirror_of_the_puzzle(
        self, tmp_path: Path
    ) -> None:
        path = sheet(tmp_path, notebook(maze_section(1, "back_mirrored")))
        pages = pdfread.page_count(path)
        puzzle = pdfread.subpaths_um(path, pages - 2)
        solution = pdfread.subpaths_um(path, pages - 1)
        # A5 is 148 mm wide. Mirroring about the sheet's centre sends x to
        # 148000 - x, and the reference is the sheet, not the pattern area
        # (§ 7.5) — that is the physical turning edge.
        flipped = {
            tuple(sorted((round(148_000 - x), round(y)) for x, y in path_))
            for path_ in solution
        }
        for wall in puzzle:
            assert tuple(sorted((round(x), round(y)) for x, y in wall)) in flipped

    def test_duplex_with_unequal_margins_is_refused_on_the_document_path_too(
        self, tmp_path: Path
    ) -> None:
        # § 7.5: the alternating gutter moves the pattern area between front
        # and back, and the solution would miss the maze by exactly that. The
        # blade path has refused this since M2; the document path must too.
        definition = (
            "version: 1\n"
            "page: {format: a5, margin: {top: 10mm, bottom: 10mm, "
            "inner: 20mm, outer: 8mm}, duplex: true}\n"
            "generator: notebook\n"
            "sections:\n" + maze_section(1, "back_mirrored")
        )
        with pytest.raises(DefinitionError) as excinfo:
            build(loads(definition, source="t"), PdfWriter(tmp_path / "never.pdf"))
        assert "back_mirrored" in str(excinfo.value)
```

- [ ] **Step 2: Run them and watch them fail**

Run: `uv run pytest tests/test_notebook_sheets.py -q -k TestBackMirrored`
Expected: FAIL — nothing mirrors, and the duplex refusal never runs for a document.

- [ ] **Step 3: Add the flag to the page**

In `ctrlgrid/document.py`, in `DocumentPage`, after `show_footer`:

```python
    mirrored: bool = False
    """Draw this page's pattern reflected about the **sheet's** vertical centre
    (§ 7.5's `back_mirrored`). The sheet's and not the pattern area's: the
    reference is the physical turning edge, and only the handle knows where the
    sheet is (§ 3.3). Set by a document whose section's blade states it in its
    `SheetPlan`; carried out in `pages._document_content`."""
```

- [ ] **Step 4: Mirror where the marks reach the sheet**

In `ctrlgrid/pages.py`, replace the last two lines of `_document_content`
(lines 1241-1242):

```python
    for mark in document_page_marks(page, area=geometry.area, context=context, q=q):
        placed = translate(mark, dx=ox, dy=oy)
        if page.mirrored:
            # § 7.5, and it has to be here rather than in `document_page_marks`:
            # that function yields area-local marks, and the reflection is about
            # the sheet. The three other callers — the capability pre-flight, the
            # glyph check and the media check — therefore see an unmirrored page,
            # which is right: a reflection preserves a mark's kind, weight,
            # colour and text, and those four are all they look at.
            placed = mirror_x(placed, about=document.sheet.width)
        yield placed
```

- [ ] **Step 5: Set it in the notebook**

In `ctrlgrid/generators/notebook.py`, in `pages`, the section loop needs the
plan's mirrored set. Replace the `for number in ...` loop's `yield` with:

```python
            per_item = self._sheets_per_item(section)
            mirrored = self._mirrored_sub_sheets(section)
            for number in range(1, self._section_pages(section) + 1):
                dest = (
                    _page_dest(index, number)
                    if section.divider or number > 1
                    else _section_dest(index)
                )
                yield DocumentPage(
                    dest=dest,
                    kind="section",
                    marks=(),
                    fill=Fill(
                        section.generator, section.config,
                        index=number - 1, count=self._section_pages(section),
                    ),
                    placeholders=placeholders,
                    mirrored=(number - 1) % per_item in mirrored,
                )
```

And add beside `_sheets_per_item`:

```python
    def _mirrored_sub_sheets(self, section) -> frozenset[int]:
        """Which sub-sheet of an item is drawn mirrored (§ 7.5, decision 27)."""
        from ctrlgrid.generators import get

        sheets = getattr(get(section.generator), "sheets", None)
        plan = sheets(section.config) if sheets else None
        return plan.mirrored if plan else frozenset()
```

- [ ] **Step 6: Make the § 7.5 duplex refusal reach documents**

In `ctrlgrid/pages.py`, `preflight` calls
`_refuse_mirroring_that_cannot_line_up(document, plan)` at line 611 with the
*blade path's* plan. A document has no such plan, so add, right after the
document generator's own `check` in the pre-flight:

```python
    if is_document_generator(blade) and hasattr(blade, "mirrored_sections"):
        # § 7.5's refusal is about the page model, not about the blade, so it
        # holds wherever a mirrored sheet is drawn. It lived on the blade path
        # only, which is the half-a-tool split decision 52 was written about.
        for label in blade.mirrored_sections(document.config):
            _refuse_mirroring_that_cannot_line_up(
                document, SheetPlan(per_item=2, mirrored=frozenset({1})), section=label
            )
```

And in `_refuse_mirroring_that_cannot_line_up`, add an optional section name so
the message can say which one:

```python
def _refuse_mirroring_that_cannot_line_up(
    document: Document, plan: SheetPlan, *, section: str | None = None
) -> None:
```

with the message gaining, when `section` is given, `f" in section `{section}`"`
after `back_mirrored`.

In `ctrlgrid/generators/notebook.py`, add the query the pre-flight asks:

```python
    def mirrored_sections(self, cfg: NotebookConfig) -> list[str]:
        """Sections whose blade draws a mirrored sheet (§ 7.5), by label.

        A query the handle asks rather than geometry pushed into the notebook —
        the same shape as `periodic_axes` and `sheets` (§ 3.6).
        """
        return [
            section.name(index)
            for index, section in enumerate(cfg.sections)
            if self._mirrored_sub_sheets(section)
        ]
```

- [ ] **Step 7: Run the tests**

Run: `uv run pytest tests/test_notebook_sheets.py tests/test_notebook.py tests/test_maze.py -q`
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add ctrlgrid/document.py ctrlgrid/pages.py ctrlgrid/generators/notebook.py tests/test_notebook_sheets.py
git commit -m "notebook: back_mirrored in a section, and the refusal it inherits (§ 7.5)"
```

---

### Task 4: the alignment leaf

**Files:**
- Modify: `ctrlgrid/generators/notebook.py` (`pages`, `page_count`, `_section_starts`)
- Modify: `ctrlgrid/cli.py` (`_report`)
- Test: `tests/test_notebook_sheets.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_notebook_sheets.py`:

```python
class TestTheAlignmentLeaf:
    """§ 7.5 needs each puzzle on the *front* of a sheet, which in duplex means
    an odd page number. Whether a section starts there depends on the title page
    and the dividers before it — unrelated furniture — so the notebook inserts a
    blank leaf where the parity needs one (decision 55)."""

    def walls(self, path: Path, page: int) -> int:
        return len([p for p in pdfread.subpaths_um(path, page) if len(p) == 2])

    def test_no_leaf_when_the_section_already_starts_on_a_front(
        self, tmp_path: Path
    ) -> None:
        # Title 1, contents 2, so the puzzle would land on 3 — odd, a front.
        # Nothing is inserted, and the puzzle really is the third page.
        path = sheet(
            tmp_path, notebook(maze_section(1, "back_mirrored"), title=True), "a.pdf"
        )
        assert pdfread.page_count(path) == 1 + 1 + 2
        assert self.walls(path, 2) > 0

    def test_a_leaf_is_inserted_when_it_would_start_on_a_back(
        self, tmp_path: Path
    ) -> None:
        # Contents 1, so the puzzle would land on 2 — a back. A leaf goes in,
        # and the puzzle moves to page 3.
        #
        # Both documents are four pages long, so the page *count* distinguishes
        # nothing: what distinguishes them is which page carries the maze. An
        # assertion that both are four pages would pass either way, and a probe
        # that cannot fail proves nothing.
        path = sheet(tmp_path, notebook(maze_section(1, "back_mirrored")), "b.pdf")
        assert pdfread.page_count(path) == 1 + 1 + 2
        assert self.walls(path, 1) == 0
        assert self.walls(path, 2) > 0

    def test_the_leaf_is_empty_but_still_a_page(self, tmp_path: Path) -> None:
        # Unlike a booklet's padded cell (§ 14), this is a real page: it carries
        # the bands and answers {section}, and only its pattern area is empty.
        definition = (
            "version: 1\n"
            "page: {format: a5, margin: 10mm}\n"
            'header: {height: 8mm, gap: 2mm, left: "{section}"}\n'
            "generator: notebook\n"
            "sections:\n" + maze_section(1, "back_mirrored")
        )
        path = sheet(tmp_path, definition)
        leaf = 1                                    # contents is 0, leaf is 1
        assert "Mazes" in pdfread.text_on(path, leaf)
        assert not [p for p in pdfread.subpaths_um(path, leaf) if len(p) == 2]

    def test_the_run_says_it_inserted_one(self, tmp_path: Path) -> None:
        from typer.testing import CliRunner

        from ctrlgrid.cli import app

        definition = tmp_path / "d.yaml"
        definition.write_text(
            notebook(maze_section(1, "back_mirrored")), encoding="utf-8"
        )
        result = CliRunner().invoke(
            app, ["-d", str(definition), "-o", str(tmp_path / "o.pdf")]
        )
        assert result.exit_code == 0, result.output
        assert "blank leaf" in result.output
        assert "Mazes" in result.output
```

- [ ] **Step 2: Run them and watch them fail**

Run: `uv run pytest tests/test_notebook_sheets.py -q -k TestTheAlignmentLeaf`
Expected: FAIL — no leaf is inserted and the report says nothing.

- [ ] **Step 3: Compute the leaves once**

In `ctrlgrid/generators/notebook.py`, add beside `_section_starts`:

```python
    def _alignment_leaves(self, cfg: NotebookConfig) -> dict[int, bool]:
        """Which sections need a blank leaf before their content (decision 55).

        `back_mirrored` puts the solution on the back of the same physical
        sheet, so the puzzle has to sit on a front — an odd 1-based page number
        under duplex. Where a section lands depends on the title page and on
        every divider before it, so the parity is computed here, once, and the
        two functions that count pages both read it.
        """
        needed: dict[int, bool] = {}
        number = 1 + (1 if cfg.title_page is not None else 0) + 1
        for index, section in enumerate(cfg.sections):
            if section.divider:
                number += 1
            leaf = bool(self._mirrored_sub_sheets(section)) and number % 2 == 0
            needed[index] = leaf
            number += self._section_pages(section) + (1 if leaf else 0)
        return needed
```

Then make `page_count` and `_section_starts` read it. In `page_count`:

```python
    def page_count(self, cfg: NotebookConfig, *, area: Area) -> int:
        """Title (opt-in) + contents + each section's divider, alignment leaf
        and pages."""
        leaves = self._alignment_leaves(cfg)
        total = 1 + (1 if cfg.title_page is not None else 0)
        for index, section in enumerate(cfg.sections):
            total += self._section_pages(section) + (1 if section.divider else 0)
            total += 1 if leaves[index] else 0
        return total
```

In `_section_starts`, the number a section *starts* on stays the divider (or the
leaf) — the first thing a reader turns to:

```python
    def _section_starts(self, cfg: NotebookConfig) -> list[int]:
        """The 1-based page number each section starts on, for the contents.

        One arithmetic with `page_count` above: both count the same pages in
        the same order, and the contents prints what the reader will find.
        """
        leaves = self._alignment_leaves(cfg)
        number = 1 + (1 if cfg.title_page is not None else 0) + 1  # title, contents
        starts = []
        for index, section in enumerate(cfg.sections):
            starts.append(number)
            number += self._section_pages(section) + (1 if section.divider else 0)
            number += 1 if leaves[index] else 0
        return starts
```

- [ ] **Step 4: Emit the leaf**

In `ctrlgrid/generators/notebook.py`, in `pages`, before the `for number in ...`
loop and after the divider:

```python
            if leaves[index]:
                yield DocumentPage(
                    dest=f"leaf-{index}",
                    kind="alignment-leaf",
                    marks=(),
                    placeholders=placeholders,
                )
```

with `leaves = self._alignment_leaves(cfg)` computed once at the top of `pages`,
beside `starts`.

- [ ] **Step 5: Report it**

In `ctrlgrid/cli.py`, in `_report`, after the blade's `describe` lines:

```python
    leaves = getattr(blade, "alignment_leaves_report", None)
    for line in leaves(document.config) if leaves else []:
        typer.echo(f"  {line}")
```

And in `ctrlgrid/generators/notebook.py`:

```python
    def alignment_leaves_report(self, cfg: NotebookConfig) -> list[str]:
        """§ 12: a page nobody asked for is never inserted silently."""
        leaves = self._alignment_leaves(cfg)
        return [
            f'section "{section.name(index)}" starts on an even page, so a blank '
            "leaf was inserted before it — with `back_mirrored` each puzzle has to "
            "sit on the front of its sheet, or the solution shows through on the "
            "wrong one (§ 7.5)"
            for index, section in enumerate(cfg.sections)
            if leaves[index]
        ]
```

- [ ] **Step 6: Run the tests**

Run: `uv run pytest tests/test_notebook_sheets.py -q`
Expected: PASS.

- [ ] **Step 7: Run everything, and check the gallery again**

```bash
uv run pytest -q 2>&1 | tail -2
uv run ruff check .
uv run ctrlgrid -d examples/15-notebook.yaml -o /tmp/nb-check.pdf --force --quiet
cmp /tmp/nb-check.pdf examples/15-notebook.pdf && echo "byte-identical"
```

Expected: all green, ruff clean, `byte-identical`.

- [ ] **Step 8: Commit**

```bash
git add ctrlgrid/generators/notebook.py ctrlgrid/cli.py tests/test_notebook_sheets.py
git commit -m "notebook: the blank leaf that keeps a puzzle on its front (§ 7.5)"
```

---

### Task 5: the documents

**Files:**
- Modify: `docs/pflichtenheft-vorlagengenerator.md` (§ 7.13)
- Modify: `docs/implementation-decisions.md` (decision 55; amend decision 52)
- Modify: `HANDBOOK.md` (§ 12, the notebook part)
- Modify: `docs/CLAUDE.md` (the `notebook` row, the test count)

- [ ] **Step 1: § 7.13 — replace the refusal with the rule**

§ 7.13's "Abgelehnt wird, vor Seite eins" list currently implies a multi-sheet
blade is refused. Replace that implication with:

```markdown
**Ein Abschnitt mit mehreren Blättern je Stück** (§ 7.5, `maze` mit
`solution: separate_page` oder `back_mirrored`) wird ausgeführt, nicht mehr
abgelehnt (Entscheidung 55). `pages:` zählt weiterhin **Stücke**, wie § 7.5 es
auf dem Klingenweg liest — `pages: 10` sind also zehn Rätsel auf zwanzig Seiten.

**Ein Abschnitt ist eine Definition im Kleinen, und das gilt jetzt auch für den
Seitenkontext:** die Klinge eines Abschnitts bekommt Index 0…n−1 *seines*
Abschnitts, nicht den der Dokumentseite. Damit stimmen die beiden Ablesungen aus
§ 7.5 wieder (Parität für Rätsel/Lösung, `index // 2` für den Seed), und ein
Titelblatt davor verschiebt kein Labyrinth mehr.

**Bei `back_mirrored` schiebt das Notizbuch ein leeres Blatt ein**, wenn der
Abschnitt sonst auf einer Rückseite begänne — beim Duplexdruck ist eine Seite
genau dann vorne, wenn ihre Nummer ungerade ist. Gemessen nach dem Trennblatt.
Das Blatt ist eine **echte Seite**: es trägt die Bänder, beantwortet `{section}`
und zählt in `{page}`; nur sein Musterbereich bleibt leer. (Anders als die
aufgefüllte Zelle eines Hefts, § 14 — die ist die *Abwesenheit* einer Seite.)
Der Laufbericht nennt jede Einfügung.

Die Bedingung aus § 7.5 gilt unverändert: `back_mirrored` verlangt
`duplex: false` oder gleiche `inner`/`outer`, sonst wird abgelehnt — auf dem
Dokumentweg genauso wie auf dem Klingenweg.
```

- [ ] **Step 2: decision 55, and amend 52**

Append decision 55 to `docs/implementation-decisions.md`, covering: the
section-local page context as the one idea that fixes both readings; `pages:`
counting items; the alignment leaf and why it is a page while a booklet's padded
cell is not; and the mirroring placement, including that the first answer
(`document_page_marks`) was wrong because that function is area-local while
§ 7.5 mirrors about the sheet.

In decision 52, mark the fourth refusal as resolved with a pointer:

```markdown
**A fourth refusal, and this one was deliberately temporary — now lifted.**
...unchanged text... Resolved by **decision 55** (2026-07-26): a section's blade
is handed a page context of its own, so the parity and the seed are right, and
`pages:` goes on counting items.
```

- [ ] **Step 3: HANDBOOK**

In the notebook section, add that a section may use `maze` with separate
solutions, that `pages:` then counts puzzles, and that `back_mirrored` may insert
a blank leaf, which the run reports.

- [ ] **Step 4: `docs/CLAUDE.md`**

Update the test count from `uv run pytest 2>&1 | tail -1`, and add to the
`notebook` row that a section now carries out its blade's sheet plan
(decision 55), replacing decision 52's temporary refusal.

- [ ] **Step 5: Verify and commit**

```bash
uv run pytest -q 2>&1 | tail -2 && uv run ruff check .
git add -A
git commit -m "docs: a sheet plan inside a notebook section (§ 7.13, decision 55)"
```

---

## Self-Review

**Spec coverage.** The section-local context → Task 1. `pages:` counting items and
the three counting functions → Task 2. Mirroring and § 7.5's inherited refusal →
Task 3. The alignment leaf, its identity as a real page, and the report → Task 4.
The documents → Task 5. The design's "deliberately not in this version" list needs
no task.

**Placeholders.** None: every step that changes code shows the code.

**Types.** `Fill(generator: str, config: Any, index: int = 0, count: int = 1)` is
constructed in Task 1 Step 5 and Task 2 Step 5 and Task 3 Step 5 with those names,
and read in `_fill_context` (Task 1 Step 4). `DocumentPage.mirrored: bool` is added
in Task 3 Step 3 and read in Task 3 Step 4, set in Task 3 Step 5.
`_sheets_per_item`, `_section_pages`, `_mirrored_sub_sheets`, `_alignment_leaves`,
`mirrored_sections` and `alignment_leaves_report` are each defined once and used
with the same signature everywhere.

**One risk worth naming before starting.** Task 3 Step 6 adds a query
(`mirrored_sections`) that the pre-flight asks a document generator for. If the
calendar ever gains a mirrored page, that same query serves it — but today only
the notebook answers, so the `hasattr` guard is what keeps the calendar
unaffected. That is the established shape for handle-asks-blade (§ 3.6), not a
special case.
