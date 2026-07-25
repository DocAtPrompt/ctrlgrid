# Header/Footer band colour

**Date:** 2026-07-25
**Status:** approved (brainstorming), ready for implementation
**Touches:** `ctrlgrid/model.py`, `ctrlgrid/frame.py`, `ctrlgrid/pages.py`, their
tests, spec § 8.9, `docs/CLAUDE.md`, `docs/implementation-decisions.md`.

## Goal

Give a header/footer band an optional **background colour** (a full-width fill
behind the band) and an optional **text colour**. Both default off, so every
existing sheet is byte-identical. This is general handle furniture — it applies
to every generator's header/footer, not just the calendar — and as a side effect
it resolves the title-page contrast deferred from the title-page work: a cover
header becomes legible with `header: {background: "#2f3a48", text_color: "#ffffff"}`.

## Decisions (from brainstorming)

| Question | Decision |
|---|---|
| Background extent | **Full sheet width** — an edge-to-edge strip over the band height. Drawn in the handle path (it knows the sheet). |
| Vertical extent | **Band height only** — the `gap` (space to the pattern area) is not tinted. |
| Text colour scope | **One `text_color` per band** — it applies to all three fields (left/center/right). Per-field colour rejected (YAGNI). |
| Field names | `background` / `text_color`, mirroring `TitlePage`. |
| Where it is drawn | Inside **`layout_band`** — the single choke point both the blade and document paths already call — not a separate handle mark prepended at four sites (one path would eventually be forgotten). |

## Model — `Band` (`model.py:241`)

Two new fields beside the existing `height`, `gap`, `cut`, `font`,
`left`/`center`/`right`:

```python
background: ColorField | None = None
text_color: ColorField | None = None
```

`ColorField` (`model.py:327`) already coerces and validates the colour string.
Both default `None`: no fill, and text stays the current `Text` default `#000000`.

## Text colour — `layout_band` (`frame.py:264`)

Each band `Text` mark is built with an explicit colour:

```python
Text(..., color=band.text_color or "#000000")
```

`None` reproduces today's black exactly (`Text.color` already defaults
`#000000`, `marks.py:115`).

## Background strip — `layout_band` (`frame.py:180`)

`layout_band` gains a `sheet_width: Um` parameter (the only new fact it needs —
the box already carries the band's vertical extent and content x-extent). When
`band.background` is set, a full-width fill is the band's **first** mark, so it
sits behind the text:

```python
Polygon(
    points=(
        Point(0, box.bottom), Point(sheet_width, box.bottom),
        Point(sheet_width, box.top), Point(0, box.top),
    ),
    closed=True, weight=0.0,
    fill_color=band.background,
    layer=Layer.FRAME,
)
```

- `x` spans `0 … sheet_width` (full bleed); `y` spans the band box's own
  `bottom … top` (band height only — the `gap` is untouched).
- Emission order in the returned list: **fill first, then the field marks**, so
  the text paints over the strip (`Layer` is not sorted — order is paint order).
- A band with a `background` but no text fields still draws the strip: the early
  `if not resolved: return []` becomes "return the fill alone if there is one".

## Wiring — the four `layout_band` call sites (`pages.py`)

Each call passes `sheet_width=<the sheet width>`:
- blade pre-flight header + footer (`pages.py:643`, `:647`),
- document pre-flight header + footer (`pages.py:875`, `:879`).

All four already have the sheet in scope (`document.sheet.width`). No path can
forget the fill, because the fill lives in the one function all four call.

## Determinism

Colours are validated strings; the fill's corners are integer µm from the
existing band box and the sheet width. No wall-clock, no hash, no float
accumulation (non-negotiable #5).

## Testing (TDD, failing first)

- Model: `background` / `text_color` accept a colour and default `None`; an
  invalid colour is refused (via `ColorField`).
- `layout_band`: with `text_color` set, every field `Text` carries that colour;
  without it, `#000000` (unchanged).
- `layout_band`: with `background` set, the first returned mark is a `Polygon`
  spanning `0..sheet_width` × the band box's `bottom..top`, `fill_color` = the
  colour, and it precedes every `Text`.
- `layout_band`: a band with `background` and **no** text fields returns exactly
  the fill (not `[]`); a band with neither still returns `[]`.
- Regression: a band with neither field is byte-identical to today (no `Polygon`,
  text `#000000`).
- End-to-end: a real sheet (any generator) with a coloured header — read the PDF
  back (`tests/pdfread.py` / pypdf) and confirm the strip and the coloured text
  are on the page; and the calendar title with `header: {background, text_color}`
  renders the legible strip on page 1.

## Out of scope (named, § 5)

- Per-field text colours.
- Tinting the `gap`, a border around the strip, padding, or rounded corners.
- Any colour on the pattern-area side (this is header/footer furniture only).
