# Calendar — title-page beautifications

**Date:** 2026-07-25
**Status:** approved (brainstorming), ready for implementation
**Touches:** `ctrlgrid/document.py`, `ctrlgrid/generators/calendar.py`,
`ctrlgrid/generators/calendar_layout.py`, `ctrlgrid/pages.py`, their tests,
spec § 7.12, `docs/CLAUDE.md`, `docs/implementation-decisions.md`.

## Goal

Two additions to the calendar's opt-in title page (§ 7.12):

1. **A background image.** The title page can carry a full-sheet PNG on top of
   its background colour. Where the PNG is transparent, the colour shows through.
   The fit is selectable: `cover` (full-bleed, aspect preserved, overflow
   cropped) or `contain` (whole image centred, colour fills the rest).
2. **Optional header / footer on the title.** If the definition has a header
   and/or footer band, the title page can show either or both — independently —
   instead of always being a bare cover.

Both are the user's aesthetic choice; neither changes any sub-page.

## Decisions (from brainstorming)

| Question | Decision |
|---|---|
| Background PNG fit | **`cover` or `contain`, selectable** (a `background_fit` setting); default `cover`. Stretch-to-sheet was rejected (it distorts — against the tool's anti-stretch ethos). |
| Header/footer control | **Independent** `header` / `footer` booleans on `title_page` (matches "einen header ODER footer"). |
| Colour vs image shape | `background_image` / `background_fit` are **sibling fields** to the existing `background` colour, not a nested map — keeps the existing `background: "#..."` string form working. |
| Header/footer contrast on a dark cover | **Left to the user.** Header/footer will later gain their own background + text colour (a separate future step); until then the cover colour and band styling are the user's responsibility — noted, not solved here. |

## Model — `TitlePage` (`calendar.py`)

New fields beside the existing `title`, `subtitle`, `background`, `text_color`,
`logo`:

```python
background_image: str | None = None
background_fit: Literal["cover", "contain"] = "cover"
header: bool = False   # show the definition's header band on the title page
footer: bool = False   # show the definition's footer band on the title page
```

A `field_validator` resolves `background_image` against `base_dir` from the
validation context and calls `images.load_image(...)` — exactly like the existing
`logo` validator (`calendar.py:113`) — so a missing or unreadable PNG is refused
before page one (§ 12). `background_fit` is only meaningful when
`background_image` is set (a lone `background_fit` is harmless — it simply has no
image to fit).

## Layer A — the background image (handle side, `pages.py`)

The generator cannot place a full-sheet mark: it knows only the pattern area, not
the sheet or margins (§ 3.3). So — exactly as the background *colour* is already
handle-painted — the **handle** draws the background image.

`DocumentPage` gains:

```python
background_image: str | None = None
background_fit: str = "cover"
```

In `_build_document`, after painting the colour polygon and before anything else,
if `page.background_image` is set:

1. `load_image(page.background_image)` (already validated in the model, so it
   cannot raise on user input here — § 12 point 13) to get its pixel aspect.
2. Compute the draw rectangle against the sheet `(W, H)` from the image aspect
   `a = imgW / imgH` alone (the PNG's pixel count carries no physical size — only
   its shape matters here). Let the sheet aspect be `s = W / H`.
   - **contain** (fit inside, centred; colour fills the rest):
     - if `a >= s` (image relatively wider): `drawW = W`, `drawH = round(W / a)`.
     - else: `drawH = H`, `drawW = round(H * a)`.
   - **cover** (fill the sheet, overflow cropped by the MediaBox): swap the
     branch — the image covers rather than fits:
     - if `a >= s`: `drawH = H`, `drawW = round(H * a)` (overhangs left/right).
     - else: `drawW = W`, `drawH = round(W / a)` (overhangs top/bottom).
   - Centre in both: `x = round((W - drawW) / 2)`, `y = round((H - drawH) / 2)`
     (negative for cover overhang — the PDF page clips it, no explicit clip).
   All in integer µm (determinism, non-negotiable #5).
3. Draw one `Image(pos=Point(x, y), width=drawW, height=drawH, source=path)`.

Stacking on the title page becomes: colour → background image → logo → title →
subtitle (logo/title/subtitle are the page's own area-local marks, drawn after
and translated by the origin as today).

## Layer B — optional header / footer on the title

Today `DocumentPage.plain` is all-or-nothing (title = `plain=True` → no
header/footer). Replace it with two independent flags:

```python
show_header: bool = True
show_footer: bool = True
```

Both default `True`, so every sub-page is unchanged. The title page sets them
from `title_page.header` / `title_page.footer` (both default `False`).

`_preflight_document` currently builds one combined `frame_marks` list (header
band + footer band, both measured and refused in the pre-flight). Split it into
`header_marks` and `footer_marks`, carried separately. `_build_document` then
draws `header_marks` when `page.show_header` and `footer_marks` when
`page.show_footer`.

The `plain` field is removed (only the title page used it, and only internally).

## `calendar_layout.title_page`

Pass the new fields through into the returned `DocumentPage`:
`background_image=<resolved path>`, `background_fit=tp.background_fit`,
`show_header=tp.header`, `show_footer=tp.footer`. Drop `plain=True`.

## Testing (TDD, failing first)

- Model: a missing/unreadable `background_image` is refused before page one; a
  bad `background_fit` value is refused (enum); `header`/`footer` default `False`.
- Handle geometry: with a known image aspect and A4 sheet, the drawn `Image`
  mark's `pos`/`width`/`height` match the expected **cover** rect (covers the
  sheet, centred, may overhang) and **contain** rect (fits inside, centred).
  Read the mark back — no rendering needed for geometry.
- Stacking/order: the colour polygon is emitted before the background image (so
  transparency shows the colour) — assert draw order.
- Header/footer: on a title with `header: true, footer: false`, the header band
  marks appear and the footer band marks do not; both absent by default; every
  non-title page still shows both.
- End-to-end: build a real calendar PDF with a title `background_image` + a
  header, read it back (pypdf / `tests/pdfread.py`) — the header text and the
  image XObject are present on page 1.

## Out of scope (named, § 5)

- Header/footer background + text colour (a separate future step — the contrast
  concern is deferred to it).
- Background images on any page other than the title, or on the blade path.
- Stretch-to-sheet fit (rejected).
