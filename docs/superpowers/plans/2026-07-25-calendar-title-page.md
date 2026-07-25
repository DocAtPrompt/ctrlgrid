# Calendar Title-Page Beautifications — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the calendar's opt-in title page a full-sheet background PNG (drawn over the background colour, so transparent areas show the colour), with a selectable `cover`/`contain` fit, and independent opt-in header/footer.

**Architecture:** Both are handle-drawn, because only the handle knows the sheet (§ 3.3) — exactly like the background *colour* already is. `DocumentPage` gains `background_image`/`background_fit` and, replacing the all-or-nothing `plain`, independent `show_header`/`show_footer`. A pure `background_image_rect()` computes the cover/contain rectangle in integer µm. `TitlePage` gains the matching config fields, the image validated at load like `logo`.

**Tech Stack:** Python 3.11+, pydantic v2, reportlab (PDF, honours PNG alpha), Pillow (test PNGs), pytest, pypdf (read-back).

---

## File Structure

- **Modify** `ctrlgrid/pages.py` — new pure `background_image_rect()` helper; `_document_preflight` splits header/footer marks; `_build_document` draws the background image and selective header/footer; the document call site passes both mark lists.
- **Modify** `ctrlgrid/document.py` — `DocumentPage`: add `background_image`, `background_fit`, `show_header`, `show_footer`; remove `plain`.
- **Modify** `ctrlgrid/generators/calendar.py` — `TitlePage`: add the four fields; extract a shared `_resolve_def_image` helper (used by both `logo` and `background_image`).
- **Modify** `ctrlgrid/generators/calendar_layout.py` — `title_page()` passes the new fields through; drop `plain=True`.
- **Test** `tests/test_calendar_title_page.py` (new).
- **Modify** docs: `docs/pflichtenheft-vorlagengenerator.md` (§ 7.12), `docs/CLAUDE.md`, `docs/implementation-decisions.md`.

---

## Task 1: The `background_image_rect` geometry helper (pure)

**Files:**
- Modify: `ctrlgrid/pages.py`
- Test: `tests/test_calendar_title_page.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_calendar_title_page.py`:

```python
"""Calendar title-page beautifications — § 7.12.

A background PNG over the colour (transparency shows the colour), fit
cover|contain, and independent opt-in header/footer on the title page.
"""

from __future__ import annotations

import pytest

from ctrlgrid.pages import background_image_rect

# A4 portrait in µm.
W, H = 210_000, 297_000


def test_contain_square_fits_inside_and_centres():
    # aspect 1.0 >= sheet aspect (0.707): contain binds width.
    assert background_image_rect(W, H, 1.0, "contain") == (0, 43_500, 210_000, 210_000)


def test_cover_square_fills_and_overhangs():
    # aspect 1.0: cover binds height, overhangs left/right (negative x).
    assert background_image_rect(W, H, 1.0, "cover") == (-43_500, 0, 297_000, 297_000)


def test_contain_wide_image_binds_width():
    # aspect 2.0 (wider than sheet): contain → full width, short height.
    assert background_image_rect(W, H, 2.0, "contain") == (0, 96_000, 210_000, 105_000)


def test_cover_tall_image_binds_width():
    # aspect 0.5 (taller than sheet 0.707): cover binds width, overhangs top/bottom.
    x, y, w, h = background_image_rect(W, H, 0.5, "cover")
    assert (x, w) == (0, 210_000)
    assert h == 420_000 and y == round((H - 420_000) / 2)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_calendar_title_page.py -q`
Expected: FAIL — `ImportError: cannot import name 'background_image_rect'`.

- [ ] **Step 3: Implement the helper**

In `ctrlgrid/pages.py`, add at module level (near the other geometry helpers):

```python
def background_image_rect(
    sheet_w: int, sheet_h: int, aspect: float, fit: str
) -> tuple[int, int, int, int]:
    """The (x, y, width, height) in sheet µm for a full-sheet background image
    of the given pixel `aspect` (width / height), fitted `cover` or `contain`
    (§ 7.12). `contain` fits the whole image inside the sheet (the colour fills
    the rest); `cover` fills the sheet and may overhang (the PDF MediaBox crops
    it). Centred; integer µm so the same input gives the same bytes (#5)."""
    sheet_aspect = sheet_w / sheet_h
    # Width-bound when: contain and the image is relatively wider than the sheet,
    # or cover and it is relatively taller. Otherwise height-bound.
    width_bound = (aspect >= sheet_aspect) if fit == "contain" else (aspect < sheet_aspect)
    if width_bound:
        width = sheet_w
        height = round(sheet_w / aspect)
    else:
        height = sheet_h
        width = round(sheet_h * aspect)
    x = round((sheet_w - width) / 2)
    y = round((sheet_h - height) / 2)
    return x, y, width, height
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_calendar_title_page.py -q`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add ctrlgrid/pages.py tests/test_calendar_title_page.py
git commit -m "calendar: background_image_rect — cover/contain fit for the title (§ 7.12)"
```

---

## Task 2: `TitlePage` config fields + shared image-resolve helper

**Files:**
- Modify: `ctrlgrid/generators/calendar.py` (the `TitlePage` class, ~lines 103-129)
- Test: `tests/test_calendar_title_page.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_calendar_title_page.py`:

```python
from pathlib import Path

from pydantic import ValidationError
from PIL import Image as PILImage

from ctrlgrid.generators.calendar import CalendarConfig, TitlePage


def _png(path: Path, w: int, h: int, *, transparent: bool = False) -> Path:
    mode, color = ("RGBA", (200, 60, 60, 128)) if transparent else ("RGB", (200, 60, 60))
    PILImage.new(mode, (w, h), color).save(path)
    return path


def _title(tmp_path, **kw):
    return TitlePage.model_validate(
        {"title": "2026", **kw}, context={"base_dir": tmp_path}
    )


def test_defaults_are_conservative(tmp_path):
    tp = _title(tmp_path)
    assert tp.background_image is None
    assert tp.background_fit == "cover"
    assert tp.header is False and tp.footer is False


def test_background_image_is_resolved_and_validated(tmp_path):
    _png(tmp_path / "bg.png", 200, 100)
    tp = _title(tmp_path, background_image="bg.png")
    assert tp.background_image == str(tmp_path / "bg.png")


def test_missing_background_image_is_refused_before_page_one(tmp_path):
    with pytest.raises(ValidationError, match="no image file"):
        _title(tmp_path, background_image="nope.png")


def test_bad_background_fit_is_refused(tmp_path):
    _png(tmp_path / "bg.png", 200, 100)
    with pytest.raises(ValidationError):
        _title(tmp_path, background_image="bg.png", background_fit="stretch")


def test_header_footer_flags_take_booleans(tmp_path):
    tp = _title(tmp_path, header=True, footer=True)
    assert tp.header is True and tp.footer is True
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_calendar_title_page.py -k "title or fit or flag or background or default" -q`
Expected: FAIL — `background_image` / `background_fit` / `header` / `footer` are extra keys (`extra_forbidden`).

- [ ] **Step 3: Add the fields and the shared helper**

In `ctrlgrid/generators/calendar.py`, add this module-level helper (place it above the `Holiday`/`TitlePage` classes, near the other module helpers):

```python
def _resolve_def_image(value: str | None, info, field: str) -> str | None:
    """Anchor an image path to the definition (§ 5.2) and check it loads — here,
    in validation, so a missing or unreadable PNG is refused before page one
    (§ 12). Shared by the title page's `logo` and `background_image`."""
    if value is None:
        return None
    from pathlib import Path

    from ctrlgrid.images import load_image

    base = (info.context or {}).get("base_dir")
    path = Path(value)
    if base is not None and not path.is_absolute():
        path = Path(base) / path
    load_image(str(path), field=field)
    return str(path)
```

In the `TitlePage` class, add the four fields after `logo`:

```python
    background_image: str | None = None
    background_fit: Literal["cover", "contain"] = "cover"
    header: bool = False
    footer: bool = False
```

Replace the existing `_resolve_logo` validator body so it delegates to the helper, and add the matching `background_image` validator:

```python
    @field_validator("logo")
    @classmethod
    def _resolve_logo(cls, value: str | None, info) -> str | None:
        return _resolve_def_image(value, info, "title_page.logo")

    @field_validator("background_image")
    @classmethod
    def _resolve_background_image(cls, value: str | None, info) -> str | None:
        return _resolve_def_image(value, info, "title_page.background_image")
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_calendar_title_page.py -q`
Expected: PASS (9 passed — Task 1's 4 plus these 5).

- [ ] **Step 5: Run the full suite (the logo refactor must not regress)**

Run: `uv run pytest -q && uv run ruff check .`
Expected: all green, ruff clean. (Existing `title_page.logo` tests still pass — same behaviour, shared helper.)

- [ ] **Step 6: Commit**

```bash
git add ctrlgrid/generators/calendar.py tests/test_calendar_title_page.py
git commit -m "calendar: TitlePage background_image/fit + header/footer opt-ins (§ 7.12)"
```

---

## Task 3: `DocumentPage` fields, handle drawing, and layout wiring

**Files:**
- Modify: `ctrlgrid/document.py` (`DocumentPage`, ~lines 51-71)
- Modify: `ctrlgrid/pages.py` (`_document_preflight` ~873-882; `_build_document` ~912-957; the document call site ~982-983; the marks import)
- Modify: `ctrlgrid/generators/calendar_layout.py` (`title_page` ~202-205)
- Test: `tests/test_calendar_title_page.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_calendar_title_page.py`:

```python
from types import SimpleNamespace

from ctrlgrid.document import DocumentPage
from ctrlgrid.marks import Area, Image, Point, Polygon, Segment, Text
from ctrlgrid.pages import _build_document


class _Recorder:
    """A minimal Writer double that records draw() calls in order."""

    def __init__(self):
        self.drawn = []

    def begin_document(self, meta): pass
    def begin_page(self, width, height): pass
    def define_dest(self, key): pass
    def draw(self, mark): self.drawn.append(mark)
    def link(self, lower_left, upper_right, target): pass
    def outline(self, title, *, index): pass
    def end_page(self): pass
    def end_document(self): pass


def _run(page, tmp_path):
    """Drive `_build_document` for a single page with a recorder, returning it."""
    doc = SimpleNamespace(
        source="t.yaml",
        pages=SimpleNamespace(embed_def=False),
        sheet=SimpleNamespace(width=W, height=H),
        config=object(),
    )
    blade = SimpleNamespace(pages=lambda cfg, *, area, q: iter([page]))
    geometry = SimpleNamespace(
        origin=SimpleNamespace(x=0, y=0), area=Area(width=W, height=H)
    )
    rec = _Recorder()
    header_marks = [Text(pos=Point(0, H - 1000), content="HDR", size=2000,
                         family="sans", align="left", color="#000000")]
    footer_marks = [Text(pos=Point(0, 1000), content="FTR", size=2000,
                         family="sans", align="left", color="#000000")]
    _build_document(doc, blade, rec, geometry, header_marks, footer_marks)
    return rec


def _title_page(tmp_path, **kw):
    _png(tmp_path / "bg.png", 200, 100, transparent=True)
    return DocumentPage(
        dest="title", kind="title", marks=(), links=(),
        background="#123456", background_image=str(tmp_path / "bg.png"), **kw,
    )


def test_colour_is_drawn_before_the_background_image(tmp_path):
    rec = _run(_title_page(tmp_path, show_header=False, show_footer=False), tmp_path)
    kinds = [type(m).__name__ for m in rec.drawn]
    # Polygon (the colour) must precede the Image, so transparency shows colour.
    assert kinds.index("Polygon") < kinds.index("Image")


def test_background_image_rect_is_used(tmp_path):
    rec = _run(_title_page(tmp_path, background_fit="contain",
                           show_header=False, show_footer=False), tmp_path)
    img = next(m for m in rec.drawn if isinstance(m, Image))
    # 200x100 → aspect 2.0, contain on A4: full width, centred vertically.
    assert (img.pos.x, img.width, img.height) == (0, 210_000, 105_000)


def test_header_shown_footer_hidden_per_flags(tmp_path):
    rec = _run(_title_page(tmp_path, show_header=True, show_footer=False), tmp_path)
    texts = [m.content for m in rec.drawn if isinstance(m, Text)]
    assert "HDR" in texts and "FTR" not in texts


def test_default_document_page_shows_both_bands(tmp_path):
    plain_marks = DocumentPage(dest="d", kind="month", marks=())
    rec = _run(plain_marks, tmp_path)
    texts = [m.content for m in rec.drawn if isinstance(m, Text)]
    assert "HDR" in texts and "FTR" in texts
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_calendar_title_page.py -k "colour or rect_is_used or per_flags or both_bands" -q`
Expected: FAIL — `DocumentPage.__init__` rejects `background_image`/`show_header`/`show_footer` (unknown kwargs), and `_build_document` takes only one `frame_marks` list.

- [ ] **Step 3a: Update `DocumentPage` (`ctrlgrid/document.py`)**

Replace the `background`/`plain` field block (lines ~66-71) with:

```python
    background: str | None = None
    """A full-sheet colour fill painted under everything — the title page's
    colour (§ 7). The handle paints it, because only it knows the sheet
    (§ 3.3); the generator just names the colour."""
    background_image: str | None = None
    """A resolved PNG path painted full-sheet over the colour, so transparent
    areas show the colour through (§ 7.12). Handle-drawn like the colour."""
    background_fit: str = "cover"
    """`cover` (fill, crop overflow) or `contain` (fit inside) for the image."""
    show_header: bool = True
    """Draw the document's header band on this page (§ 7.12). The title page
    turns it off unless `title_page.header` opts back in."""
    show_footer: bool = True
    """Draw the document's footer band on this page (§ 7.12)."""
```

- [ ] **Step 3b: Split the frame marks in `_document_preflight` (`ctrlgrid/pages.py`)**

Replace the combined `frame_marks` block (lines ~873-882) with:

```python
    header_marks: list[Text] = []
    footer_marks: list[Text] = []
    if document.header and geometry.header:
        header_marks += layout_band(
            document.header, geometry.header, q=probe, page=context, section="header", extra=extra
        )
    if document.footer and geometry.footer:
        footer_marks += layout_band(
            document.footer, geometry.footer, q=probe, page=context, section="footer", extra=extra
        )
    # Two entries: [header, footer], so the title page can show either alone.
    return geometry, [], [header_marks, footer_marks], []
```

- [ ] **Step 3c: Update the document call site (`ctrlgrid/pages.py`, ~982-983)**

Replace:

```python
    if is_document_generator(blade):
        return _build_document(document, blade, writer, geometry, frames[0] if frames else [])
```

with:

```python
    if is_document_generator(blade):
        header_marks = frames[0] if len(frames) > 0 else []
        footer_marks = frames[1] if len(frames) > 1 else []
        return _build_document(document, blade, writer, geometry, header_marks, footer_marks)
```

- [ ] **Step 3d: Draw the image + selective bands in `_build_document` (`ctrlgrid/pages.py`)**

Change the signature (line ~912-914) from `frame_marks: list[Text],` to:

```python
def _build_document(
    document: Document, blade: object, writer: Writer, geometry: Geometry,
    header_marks: list[Text], footer_marks: list[Text],
) -> Geometry:
```

Replace the background-and-frame block (the `if page.background:` polygon through `if not page.plain:` loop, lines ~932-944) with:

```python
        # A full-sheet colour fill, painted under everything (§ 7 — the title).
        if page.background:
            writer.draw(Polygon(
                points=(
                    Point(0, 0), Point(document.sheet.width, 0),
                    Point(document.sheet.width, document.sheet.height),
                    Point(0, document.sheet.height),
                ),
                closed=True, weight=0.0, fill_color=page.background,
            ))
        # ...then the background image over it, so its transparent areas show the
        # colour through (§ 7.12). Validated in the pre-flight, so no raise here.
        if page.background_image:
            from ctrlgrid.images import load_image

            image = load_image(page.background_image, field="title_page.background_image")
            x, y, w, h = background_image_rect(
                document.sheet.width, document.sheet.height, image.aspect, page.background_fit
            )
            writer.draw(Image(pos=Point(x, y), width=w, height=h, source=str(image.path)))
        if page.show_header:
            for mark in header_marks:
                writer.draw(mark)
        if page.show_footer:
            for mark in footer_marks:
                writer.draw(mark)
```

Add `Image` to the marks import at the top of `ctrlgrid/pages.py` (it already imports `Point`, `Polygon`, `translate`, `Text` from `ctrlgrid.marks` — add `Image` to that line).

- [ ] **Step 3e: Wire the fields through `title_page` (`ctrlgrid/generators/calendar_layout.py`, ~202-205)**

Replace the returned `DocumentPage(...)`:

```python
    return DocumentPage(
        dest="title", kind="title", marks=tuple(page.marks), links=(),
        title=tp.title, background=tp.background,
        background_image=tp.background_image, background_fit=tp.background_fit,
        show_header=tp.header, show_footer=tp.footer,
    )
```

(Drop `plain=True`. The docstring's "No nav, no header — `plain`" line should read "No nav; header/footer only if `title_page` opts in (§ 7.12)".)

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_calendar_title_page.py -q`
Expected: PASS (13 passed).

- [ ] **Step 5: Run the full suite**

Run: `uv run pytest -q && uv run ruff check .`
Expected: all green, ruff clean. **Known breakage:** `tests/test_calendar.py:231` asserts `title.plain and title.background is not None and title.links == ()`. `plain` is gone; the title now defaults `header=False`/`footer=False`, so `title_page()` sets `show_header=False`/`show_footer=False`. Update that line to:

```python
        assert not title.show_header and not title.show_footer
        assert title.background is not None and title.links == ()
```

Confirm no other `.plain` references remain: `grep -rn "\.plain\|plain=" tests/ ctrlgrid/` should return nothing after this task.

- [ ] **Step 6: Commit**

```bash
git add ctrlgrid/document.py ctrlgrid/pages.py ctrlgrid/generators/calendar_layout.py tests/test_calendar_title_page.py
git commit -m "calendar: draw title background image + selective header/footer (§ 7.12)"
```

---

## Task 4: End-to-end — a real PDF, read back

**Files:**
- Test: `tests/test_calendar_title_page.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_calendar_title_page.py`:

```python
from pypdf import PdfReader

from ctrlgrid.loader import loads
from ctrlgrid.pages import build
from ctrlgrid.writers.pdf import PdfWriter


def test_title_background_image_and_header_render(tmp_path):
    _png(tmp_path / "bg.png", 400, 560, transparent=True)
    definition = tmp_path / "cal.yaml"
    definition.write_text(
        "version: 1\n"
        "page:\n"
        "  format: a4\n"
        "  margin: 12mm\n"
        "header:\n"
        "  height: 7mm\n"
        "  gap: 3mm\n"
        '  center: "HDR"\n'
        "footer:\n"
        "  height: 7mm\n"
        "  gap: 3mm\n"
        '  center: "FTR"\n'
        "generator: calendar\n"
        "year: 2026\n"
        "title_page:\n"
        '  title: "2026"\n'
        "  background_image: bg.png\n"
        "  header: true\n"
        "  footer: false\n",
        encoding="utf-8",
    )
    doc = loads(definition.read_text(), source=str(definition))
    out = tmp_path / "cal.pdf"
    build(doc, PdfWriter(str(out)))

    reader = PdfReader(str(out))
    page1 = reader.pages[0]
    # The background image is an XObject on page 1.
    assert "/XObject" in (page1.get("/Resources") or {})
    text1 = page1.extract_text()
    assert "HDR" in text1 and "FTR" not in text1   # header opted in, footer not
    # A sub-page (contents) still shows both bands.
    text2 = reader.pages[1].extract_text()
    assert "HDR" in text2 and "FTR" in text2
```

- [ ] **Step 2: Run the test**

Run: `uv run pytest tests/test_calendar_title_page.py -k render -q`
Expected: PASS. If page 1 has no `/XObject`, the image was not drawn — debug with `systematic-debugging` (check `title_page` passes `background_image`, and `_build_document` draws it). If `extract_text` is empty/garbled, fall back to checking the content stream (`page1.get_contents().get_data()`) for the header text bytes, and note the fallback.

- [ ] **Step 3: Commit**

```bash
git add tests/test_calendar_title_page.py
git commit -m "calendar: end-to-end — title background image + opt-in header render (§ 7.12)"
```

---

## Task 5: Update the preset, spec, and handover docs

**Files:**
- Modify: `ctrlgrid/data/presets/calendar-a4.yaml` (document the new title options)
- Modify: `docs/pflichtenheft-vorlagengenerator.md` (§ 7.12 title-page sentence)
- Modify: `docs/CLAUDE.md` (the calendar row)
- Modify: `docs/implementation-decisions.md` (append a numbered decision)

- [ ] **Step 1: Document the options in the preset**

In `ctrlgrid/data/presets/calendar-a4.yaml`, in the `title_page:` block (~lines 53-58), add commented options after the `logo:` line:

```yaml
  # background_image: cover.png   # a full-sheet PNG over the colour; transparent
  #                               # areas show `background` through (path relative
  #                               # to this file)
  # background_fit: cover         # cover (fill, crop) | contain (fit inside)
  # header: false                 # show the header band on the cover too
  # footer: false                 # show the footer band on the cover too
```

- [ ] **Step 2: Update the spec § 7.12**

In `docs/pflichtenheft-vorlagengenerator.md`, find the title-page sentence in § 7.12 (the `**Titelblatt**` description, ~line 1158-1159: "über ein neues `DocumentPage.background`/`plain`, vom Griff gezeichnet"). Replace `/`plain`` and extend it to read:

```
über ein neues `DocumentPage.background`, vom Griff gezeichnet, optional mit
einem **Vollflächen-PNG** darüber (`background_image`, `cover`/`contain`, dessen
transparente Stellen die Farbe durchlassen) und **optional Kopf-/Fußzeile**
(`header`/`footer` je einzeln; `plain` wich `show_header`/`show_footer`)
```

- [ ] **Step 3: Update `docs/CLAUDE.md`**

In the `post-M9 calendar` "Done"-table row, find `a new DocumentPage.background/plain` and change it to:

```
a new `DocumentPage.background` (+ an optional full-sheet `background_image`, `cover`/`contain`, transparency shows the colour), optional `logo`, and independent opt-in `show_header`/`show_footer` (replacing `plain`)
```

- [ ] **Step 4: Append an implementation decision**

Read the tail of `docs/implementation-decisions.md` to confirm the next number (it should be Decision 44 — verify), then append:

```markdown
## 44. Title background image and header/footer are handle-drawn (§ 7.12)

The title page's background PNG and its optional header/footer are drawn by the
handle, not the generator, for the same reason the background *colour* already
is: only the handle knows the sheet (§ 3.3). `DocumentPage` carries the resolved
image path and fit; `pages.background_image_rect` computes the cover/contain
rectangle in integer µm (determinism, #5), and the PDF MediaBox — not an
explicit clip — crops a `cover` overhang. `plain` (all-or-nothing) became
independent `show_header`/`show_footer` so the cover can show one band alone.
The image is validated at load time like `logo`, via a shared `_resolve_def_image`
helper. Header/footer band *colours* are deliberately out of scope — a later
step gives each band its own background and text colour; until then contrast on
a dark cover is the user's to manage.
```

- [ ] **Step 5: Verify the whole suite once more**

Run: `uv run pytest -q && uv run ruff check .`
Expected: all green, ruff clean.

- [ ] **Step 6: Commit**

```bash
git add ctrlgrid/data/presets/calendar-a4.yaml docs/pflichtenheft-vorlagengenerator.md docs/CLAUDE.md docs/implementation-decisions.md
git commit -m "docs: title background image + opt-in header/footer (§ 7.12)"
```

---

## Self-Review Notes (author)

- **Spec coverage:** background image with cover/contain (T1 helper, T3 draw), transparency-shows-colour (T3 order test), independent header/footer (T3 flags + preflight split), model validation like logo (T2), preset+spec+docs (T5), real render (T4).
- **No placeholders:** every code step is complete; T3 Step 5 and T4 Step 2 name concrete contingencies (update `.plain` references; content-stream fallback), not vague "handle errors".
- **Type consistency:** `background_image_rect(sheet_w, sheet_h, aspect, fit) -> (x,y,w,h)` defined in T1, used unchanged in T3; `DocumentPage` fields `background_image`/`background_fit`/`show_header`/`show_footer` defined in T3a, produced by `title_page` in T3e and by `TitlePage` config in T2; `_resolve_def_image(value, info, field)` defined once in T2 and used by both image validators.
- **Known coupling:** removing `DocumentPage.plain` requires updating any test/code referencing it (called out in T3 Step 5) — grep before committing.
