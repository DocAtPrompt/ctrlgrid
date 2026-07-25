# Edge ruler — design

**Date:** 2026-07-25. **Status:** approved by the user, ready for an
implementation plan. **Belongs in the specification as § 8.12** (after the
relative measure, § 8.11), and in `implementation-decisions.md` as decision 46.

## What it is

A printed scale along one or more edges of the sheet, opt-in: `ruler:` beside
`border`, `background`, `hole_marks` and `stamp`. Handle furniture, not a blade
— it is drawn from the sheet and the pattern area, and no generator learns of
it.

It is the only feature that demonstrates the one promise **on every sheet**: lay
a real ruler against it, and either the numbers agree or the print driver scaled.

## Purpose (decided, and it drives everything else)

A **working scale**, not a second calibration figure: zero sits at the origin of
the *pattern area*, so the numbers agree with the grid — 0 at the first grid
line, not at the paper's corner. Measuring what is drawn on the sheet and
cutting to a mark are the cases; the calibration case already has the cover
sheet (§ 8.8), which is not touched.

## The definition

```yaml
ruler:
  edges: [bottom, left]     # bottom | left | top | right — at least one, no duplicates
  unit: mm                  # mm | cm | in — what the numbers mean
  step: 1mm                 # the smallest tick
  mid_every: 5mm            # the medium tick; `none` leaves it out
  label_every: 10mm         # the long tick, and the number beside it
  weight: 0.2               # pt, like the other frame furniture
  color: "#000000"
  font: { size: 6pt }       # the numbers
```

Defaults follow `unit`, and only the numbers differ between `mm` and `cm`:

| `unit` | `step` | `mid_every` | `label_every` | numbers read |
|---|---|---|---|---|
| `mm` (default) | 1mm | 5mm | 10mm | `10 20 30 …` |
| `cm` | 1mm | 5mm | 10mm | `1 2 3 …` |
| `in` | 0.125in | 0.5in | 1in | `1 2 3 …` |

The three intervals are ordinary lengths, so `step: 2mm` or `label_every: 0.25in`
are equally sayable — the unit decides what the numbers *mean*, the intervals
decide where the ticks *are*.

**Edges are physical**, not `inner`/`outer`: a scale is a thing at the edge of
the paper and does not swap sides under duplex the way a margin does (§ 8.1).

## Geometry

- Zero is the pattern area's origin corner for that edge; numbers grow along +x
  (`bottom`, `top`) and +y (`left`, `right`).
- Ticks grow **outward from the pattern edge into the margin**, on
  `Layer.FRAME`. The pattern area is not shrunk and no space is reserved: a
  definition's grid is byte-identical with the ruler on and off, which is the
  rule § 8.1 already states for `border`.
- Tick lengths are fixed measures — 1.2 mm, 2.0 mm, 3.0 mm — and the numbers sit
  1 mm beyond the long tick, the way the cover sheet's figures are fixed
  (§ 8.8). A yardstick nobody can bend is the point.
- A number states its position exactly, with the fewest digits that do so:
  `label_every: 25mm` under `unit: cm` prints `2.5`, `5`, `7.5`. It is never
  rounded — a scale that prints a wrong measure is worse than none.
- `mid_every: none` (or leaving it out under a non-default `step`) draws no
  medium tick.
- A tick that would fall past the end of the pattern area is simply not drawn.
  The scale measures the area it borders; it does not run into the corner.
- On the **vertical** edges the numbers are rotated 90°, reading bottom to top.
  The strip a ruler needs is then the same on all four edges — tick + gap + cap
  height — instead of the full width of a number on the left and right.
- Positions are integer micrometre multiples of `step` counted from the origin,
  never accumulated (§ 3.3), so tick 200 is exactly 200 × `step`.

## Refusals, all before page one

Each names the millimetres, in the user's own units where the value came from
one (§ 12):

1. **The strip does not fit.** The free space between the pattern edge and the
   sheet edge is smaller than tick + gap + cap height → refused, naming needed
   and available for that edge.
2. **A band is in the way.** On `top`/`bottom` with a header or footer, the free
   space ends at the band, and the message names the band as the cause rather
   than only the arithmetic.
3. **The numbers would collide.** The widest label, measured with
   `q.text_width`, is wider than `label_every` → refused, naming the measured
   width and the spacing it needs.
4. **An interval is not a whole multiple.** `mid_every` or `label_every` is not
   a whole multiple of `step` (and `label_every` not of `mid_every` when the
   medium tick is on) → refused, naming both values. A numbered tick that sits
   on no tick of the ladder is the silent almost-right of § 5.1.
5. **An unknown or repeated edge**, or an empty `edges` list → refused by name.

Nothing is ever shrunk, clipped or moved to make a ruler fit (§ 8.2).

## Where it lives

| File | Change |
|---|---|
| `model.py` | `RulerSpec` section, `ruler` field on the document, `extra="forbid"` as everywhere |
| `frame.py` | `ruler_marks(ruler, geometry, sheet, *, q) -> list[Mark]` beside `hole_marks`, plus the fit check it shares with the pre-flight — **one arithmetic**, not one for drawing and one for checking |
| `pages.py` | the call in `_frame_marks`, and the check in `preflight` |
| spec | § 8.12, German, with the reasoning |
| `implementation-decisions.md` | decision 46: physical edges, no reserved space, zero at the pattern origin, rotated numbers |
| `HANDBOOK.md` | § 10 (frame furniture), beside border/hole marks/stamp |
| `README.md` | one line in the frame furniture list |
| `examples/13-ruler-edge.yaml` | the gallery entry, with its PDF and preview |

The **cover sheet keeps its own figures** and gets no ruler: it already carries
a 50 mm square and a 100 mm rule, and a third scale on the same page says
nothing new.

## Writers

The numbers are `Text` marks, so **PNG output is refused by the existing
capability pre-flight**, naming `text` and the way out (a font file, or PDF).
That is inherited, not new code — and it gets a test rather than an assertion.

## Testing

Test first, watch it fail, then implement — and read a real sheet back, not only
unit tests:

- validation: unknown edge, repeated edge, empty list, an interval that is not a
  whole multiple, a negative or zero `step`;
- geometry: on A4 with 20 mm margins, the first tick sits at the pattern origin,
  the labelled ticks at 10 mm intervals, the last tick inside the area;
- **the pattern does not move**: the same definition with and without `ruler`
  produces identical pattern marks;
- each of the four refusals, by message;
- determinism: two runs, identical bytes;
- PNG: refused, naming `text`;
- **read back from a real PDF** with `tests/pdfread.py`: the 10 mm labelled tick
  lies 10 mm from the pattern origin, measured out of the finished file.

## Deliberately not in scope

- Configurable tick lengths — the ladder is a yardstick (§ 8.8).
- A ruler that reserves space and shrinks the pattern — rejected above.
- `inner`/`outer` edge names — rejected above.
- A numbers-off mode for PNG. If it turns out that e-ink pads want tick-only
  rulers, that is a later, evidence-backed addition; the refusal names the
  limit clearly in the meantime.
