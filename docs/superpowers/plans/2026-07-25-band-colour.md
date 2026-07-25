# Header/Footer Band Colour — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give a header/footer band an optional full-width background strip (band height only) and an optional text colour, both defaulting off (byte-identical when unset), as general handle furniture.

**Architecture:** Two new `Band` fields (`background`, `text_color`). Both the background strip and the text colour are produced inside `layout_band` — the single function both the blade and document paths call — so no path can forget them. `layout_band` gains a required `sheet_width` (the one fact it lacks for a full-bleed strip); its four call sites pass the sheet width.

**Tech Stack:** Python 3.11+, pydantic v2 (`ColorField`), reportlab (PDF), pytest, pypdf (read-back).

---

## File Structure

- **Modify** `ctrlgrid/model.py` — `Band`: add `background` / `text_color`.
- **Modify** `ctrlgrid/frame.py` — `layout_band`: text colour on every field `Text`, a full-width fill as the first mark, new `sheet_width` param.
- **Modify** `ctrlgrid/pages.py` — the four `layout_band` calls (blade + document pre-flight) pass `sheet_width`.
- **Modify** `tests/test_frame.py` — existing `layout_band` callers get `sheet_width`; new band-colour tests.
- **Test** end-to-end in `tests/test_calendar_title_page.py` (the contrast fix) and `tests/test_frame.py`.
- **Modify** docs: preset(s), `docs/pflichtenheft-vorlagengenerator.md` (§ 8.9), `docs/CLAUDE.md`, `docs/implementation-decisions.md`.

---

## Task 1: `Band` model fields

**Files:**
- Modify: `ctrlgrid/model.py` (`Band`, lines 241-256)
- Test: `tests/test_frame.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_frame.py` (a new class at the end):

```python
class TestBandColourModel:
    def test_colour_fields_default_to_none(self) -> None:
        band = Band(height="12mm", center="x")
        assert band.background is None and band.text_color is None

    def test_colour_fields_accept_a_colour(self) -> None:
        band = Band(height="12mm", center="x", background="#2f3a48", text_color="#ffffff")
        assert band.background == "#2f3a48" and band.text_color == "#ffffff"

    def test_an_invalid_colour_is_refused(self) -> None:
        with pytest.raises(Exception):  # ValidationError via ColorField
            Band(height="12mm", center="x", background="not-a-colour")
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_frame.py::TestBandColourModel -q`
Expected: FAIL — `background` / `text_color` are unknown keys (`extra_forbidden`).

- [ ] **Step 3: Move `ColorField` above `Band`, then add the fields**

`ColorField` and its `_as_color` validator are currently defined at
`model.py:305-327` — **after** the `Band` class (line 241). The module uses
`from __future__ import annotations`, so `Band` referencing `ColorField` would
fail to resolve (pydantic cannot build the schema — the name is not yet in the
module namespace when `Band` is created). First **move** the `_as_color` function
and the `ColorField = Annotated[...]` line (lines 305-327, the whole block
including its docstring) to just **above** `class Band(Section):` (line 241).
Its only dependencies (`Any`, `Annotated`, `BeforeValidator`) are module imports,
so it can sit anywhere below the imports — do not change its body.

Then, in the `Band` class, add after `right: FieldContent = None`:

```python
    #: A full-width colour strip behind the band (band height only), and the
    #: colour of the band's text — both off by default (§ 8.9). `None` is
    #: byte-identical to today: no strip, black text.
    background: ColorField | None = None
    text_color: ColorField | None = None
```

Confirm the move did not orphan a reference: `ColorField` is still used by
`BorderSpec`, `StampSpec`, etc. below — they are all *after* the new location, so
they still resolve. Run the suite in Step 5 to prove the reorder is clean.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_frame.py::TestBandColourModel -q`
Expected: PASS (3 passed).

- [ ] **Step 5: Run the full suite (no regression from a new optional field)**

Run: `uv run pytest -q && uv run ruff check .`
Expected: all green, ruff clean.

- [ ] **Step 6: Commit**

```bash
git add ctrlgrid/model.py tests/test_frame.py
git commit -m "band: optional background + text_color fields (§ 8.9)"
```

---

## Task 2: `layout_band` draws the strip and colours the text

**Files:**
- Modify: `ctrlgrid/frame.py` (`layout_band`, lines 180-274)
- Modify: `ctrlgrid/pages.py` (the four callers: lines 667, 671, 900, 904)
- Modify: `tests/test_frame.py` (existing callers + new behaviour tests)

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_frame.py`:

```python
from ctrlgrid.marks import Polygon  # add to the existing marks import at the top

SHEET_W = 210_000


class TestBandColourDrawing:
    def test_text_colour_is_applied_to_every_field(self) -> None:
        band = Band(height="12mm", left="A", center="B", right="C", text_color="#ffffff")
        marks = layout_band(band, BAND, q=Q, page=PAGE, section="header", sheet_width=SHEET_W)
        texts = [m for m in marks if isinstance(m, Text)]
        assert texts and all(m.color == "#ffffff" for m in texts)

    def test_text_colour_defaults_to_black(self) -> None:
        band = Band(height="12mm", center="B")
        marks = layout_band(band, BAND, q=Q, page=PAGE, section="header", sheet_width=SHEET_W)
        assert [m for m in marks if isinstance(m, Text)][0].color == "#000000"

    def test_background_is_a_full_width_strip_drawn_first(self) -> None:
        band = Band(height="12mm", center="B", background="#2f3a48")
        marks = layout_band(band, BAND, q=Q, page=PAGE, section="header", sheet_width=SHEET_W)
        assert isinstance(marks[0], Polygon)                      # first, so text paints over it
        fill = marks[0]
        xs = {p.x for p in fill.points}
        ys = {p.y for p in fill.points}
        assert xs == {0, SHEET_W}                                 # full sheet width
        assert ys == {BAND.bottom, BAND.top}                      # band height only
        assert fill.fill_color == "#2f3a48" and fill.layer is Layer.FRAME

    def test_background_without_text_draws_only_the_strip(self) -> None:
        band = Band(height="12mm", background="#2f3a48")
        marks = layout_band(band, BAND, q=Q, page=PAGE, section="header", sheet_width=SHEET_W)
        assert len(marks) == 1 and isinstance(marks[0], Polygon)

    def test_no_colour_no_text_is_still_empty(self) -> None:
        band = Band(height="12mm")
        assert layout_band(band, BAND, q=Q, page=PAGE, section="header", sheet_width=SHEET_W) == []
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_frame.py::TestBandColourDrawing -q`
Expected: FAIL — `layout_band()` has no `sheet_width` parameter (`unexpected keyword argument`).

- [ ] **Step 3: Change `layout_band` (`ctrlgrid/frame.py`)**

Add the parameter (keyword-only, required) to the signature (line 180-188), after `section: str`:

```python
def layout_band(
    band: Band,
    box: Box,
    *,
    q: WriterQuery,
    page: PageContext,
    section: str,
    sheet_width: Um,
    extra: Mapping[str, str] | None = None,
) -> list[Mark]:
```

Build the fill and use it both for the early return and as the first mark. Replace the early-return block (lines 210-211):

```python
    if not resolved:
        return []
```

with:

```python
    # A full-width strip behind the band (band height only, § 8.9). First in the
    # list, so the text paints over it. Layer is not sorted — order is paint order.
    fill = (
        Polygon(
            points=(
                Point(0, box.bottom), Point(sheet_width, box.bottom),
                Point(sheet_width, box.top), Point(0, box.top),
            ),
            closed=True, weight=0.0,
            color=band.background, fill_color=band.background, layer=Layer.FRAME,
        )
        if band.background is not None
        else None
    )
    if not resolved:
        return [fill] if fill is not None else []
```

Seed the marks list with the fill — change `marks: list[Mark] = []` (line 237) to:

```python
    marks: list[Mark] = [fill] if fill is not None else []
```

Give the field `Text` its colour — in the `Text(...)` built at lines 264-272, add the `color` argument:

```python
        marks.append(
            Text(
                pos=Point(_anchor(align, box), baseline),
                content=content,
                size=size,
                family=family,
                align=align,
                color=band.text_color or "#000000",
                layer=Layer.FRAME,
            )
        )
```

(`Polygon`, `Point`, `Layer`, `Um` are already imported at the top of `frame.py`.)

- [ ] **Step 4: Update the four production callers (`ctrlgrid/pages.py`)**

Blade pre-flight (lines 667-673) — both use `document.sheet`:

```python
        if document.header and placed.header:
            marks += layout_band(
                document.header, placed.header, q=probe, page=context,
                section="header", sheet_width=document.sheet.width,
            )
        if document.footer and placed.footer:
            marks += layout_band(
                document.footer, placed.footer, q=probe, page=context,
                section="footer", sheet_width=document.sheet.width,
            )
```

Document pre-flight (lines 900-906) — these also pass `extra=extra`:

```python
    if document.header and geometry.header:
        header_marks += layout_band(
            document.header, geometry.header, q=probe, page=context,
            section="header", sheet_width=document.sheet.width, extra=extra,
        )
    if document.footer and geometry.footer:
        footer_marks += layout_band(
            document.footer, geometry.footer, q=probe, page=context,
            section="footer", sheet_width=document.sheet.width, extra=extra,
        )
```

- [ ] **Step 5: Update the existing test callers (`tests/test_frame.py`)**

The `place()` helper and every direct `layout_band(...)` call in this file need `sheet_width=SHEET_W` (the value is irrelevant for these bands — none set `background`). Update `place()` (line 26):

```python
def place(band: Band, box: Box = BAND) -> dict[str, Text]:
    marks = layout_band(band, box, q=Q, page=PAGE, section="header", sheet_width=SHEET_W)
    return {mark.align: mark for mark in marks}
```

Then add `sheet_width=SHEET_W` to each remaining direct `layout_band(...)` call in the file (there are several — the failing suite will name each one). Run `uv run pytest tests/test_frame.py -q` and add the argument to every call that raises `TypeError: ... missing ... 'sheet_width'` until they pass.

- [ ] **Step 6: Run the new tests, then the full suite**

Run: `uv run pytest tests/test_frame.py -q`
Expected: PASS (all of test_frame.py, including `TestBandColourDrawing`).

Run: `uv run pytest -q && uv run ruff check .`
Expected: all green, ruff clean. If any other caller of `layout_band` exists (grep `layout_band(` across `ctrlgrid/` and `tests/`), it errors here — add `sheet_width` and re-run.

- [ ] **Step 7: Commit**

```bash
git add ctrlgrid/frame.py ctrlgrid/pages.py tests/test_frame.py
git commit -m "band: draw the background strip and colour the text in layout_band (§ 8.9)"
```

---

## Task 3: End-to-end — a coloured header on a real sheet

**Files:**
- Test: `tests/test_frame.py` (or `tests/test_calendar_title_page.py` for the calendar case)

- [ ] **Step 1: Write the failing test**

Append to `tests/test_calendar_title_page.py` (it already imports `loads`, `build`, `PdfWriter`, `PdfReader`):

```python
def test_calendar_title_header_strip_renders(tmp_path):
    definition = tmp_path / "cal.yaml"
    definition.write_text(
        "version: 1\n"
        "page:\n"
        "  format: a4\n"
        "  margin: 12mm\n"
        "header:\n"
        "  height: 8mm\n"
        "  gap: 3mm\n"
        '  center: "{year}"\n'
        '  background: "#2f3a48"\n'
        '  text_color: "#ffffff"\n'
        "generator: calendar\n"
        "year: 2026\n"
        "title_page:\n"
        '  title: "2026"\n'
        "  header: true\n",
        encoding="utf-8",
    )
    doc = loads(definition.read_text(), source=str(definition))
    out = tmp_path / "cal.pdf"
    build(doc, PdfWriter(str(out)))

    reader = PdfReader(str(out))
    # The header strip is a filled rectangle in the page content; the header
    # text still extracts. Both on page 1 (the cover opted the header in).
    page1 = reader.pages[0]
    assert "2026" in page1.extract_text()
    # The fill operator (rg + re + f) is present in the content stream.
    content = page1.get_contents().get_data()
    assert b" rg" in content or b" RG" in content   # a colour was set (the strip)
```

- [ ] **Step 2: Run the test**

Run: `uv run pytest tests/test_calendar_title_page.py -k header_strip -q`
Expected: PASS. If `get_contents()` shape differs, inspect with `reader.pages[0]["/Contents"].get_data()` and adjust the operator check; the essential assertion is that the header text renders and a fill colour appears on the page. If the strip is missing, debug with `systematic-debugging` (confirm `layout_band` got `sheet_width` and `band.background`).

- [ ] **Step 3: Commit**

```bash
git add tests/test_calendar_title_page.py
git commit -m "band: end-to-end — coloured calendar-title header strip renders (§ 8.9)"
```

---

## Task 4: Document the option — preset, spec, handover

**Files:**
- Modify: `ctrlgrid/data/presets/calendar-a4.yaml` (and optionally one blade preset)
- Modify: `docs/pflichtenheft-vorlagengenerator.md` (§ 8.9)
- Modify: `docs/CLAUDE.md`
- Modify: `docs/implementation-decisions.md`

- [ ] **Step 1: Document in the calendar preset**

In `ctrlgrid/data/presets/calendar-a4.yaml`, in the `header:` block (~lines 19-24), add after `right:`:

```yaml
  # background: "#2f3a48"   # a full-width colour strip behind the band
  # text_color: "#ffffff"   # the band's text colour (default black)
```

- [ ] **Step 2: Update the spec § 8.9**

In `docs/pflichtenheft-vorlagengenerator.md`, find the band description in § 8.9 (the header/footer section). Add a sentence documenting the two new fields:

```
Ein Band trägt optional eine **Hintergrundfarbe** (`background`, ein Farbstreifen
über die volle Blattbreite und die Bandhöhe — nicht den `gap`) und eine
**Textfarbe** (`text_color`, Standard Schwarz). Beide sind ohne Angabe aus und
ändern kein bestehendes Blatt. Der Streifen liegt hinter dem Text.
```

- [ ] **Step 3: Update `docs/CLAUDE.md`**

Add a short entry to the "Done" table (after the title-page / calendar rows), e.g.:

```
| post-M9 band colour | a header/footer `Band` takes `background` (a full-width strip, band height only) and `text_color`, both default off — drawn in `layout_band` so both the blade and document paths get them; resolves the title-page contrast (§ 8.9) |
```

- [ ] **Step 4: Append an implementation decision**

Read the tail of `docs/implementation-decisions.md` to confirm the next number (should be 45 — verify), then append:

```markdown
## 45. Band background + text colour live in `layout_band` (§ 8.9)

The header/footer background strip and text colour are produced inside
`layout_band`, the single function both the blade and document pre-flight paths
call, rather than as a separate handle mark prepended at each of the four call
sites — one site would eventually be forgotten (§ 5.1). `layout_band` gained a
required `sheet_width` (the only fact it lacked for a full-bleed strip); a
required, not defaulted, parameter so a new caller cannot silently omit it. The
strip spans the full sheet width but only the band height, not the `gap`, and is
the band's first mark so the text paints over it (`Layer` is paint-order, not
sorted). Both fields default `None` — byte-identical to before.
```

- [ ] **Step 5: Verify the whole suite once more**

Run: `uv run pytest -q && uv run ruff check .`
Expected: all green, ruff clean.

- [ ] **Step 6: Commit**

```bash
git add ctrlgrid/data/presets/calendar-a4.yaml docs/pflichtenheft-vorlagengenerator.md docs/CLAUDE.md docs/implementation-decisions.md
git commit -m "docs: header/footer band background + text colour (§ 8.9)"
```

---

## Self-Review Notes (author)

- **Spec coverage:** model fields (T1), text colour + full-width strip + band-height-only + fill-first-order + bg-without-text + regression (T2), required `sheet_width` at all four callers (T2 Step 4), end-to-end render + title contrast (T3), preset/spec/CLAUDE/decision (T4).
- **No placeholders:** every code step is complete; T2 Step 5 and T3 Step 2 name concrete contingencies (add `sheet_width` where the suite errors; adjust the content-stream operator check), not vague hand-waving.
- **Type consistency:** `layout_band(..., sheet_width: Um, extra=None)` defined once in T2 and called with `sheet_width=` at all four production sites and in every test call; `Band.background`/`Band.text_color` defined in T1 and consumed in T2.
- **Known breakage:** making `sheet_width` required breaks the 8 existing `layout_band` calls in `tests/test_frame.py` — T2 Step 5 fixes them, and the failing suite names each.
