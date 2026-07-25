# `net` — parametric box nets. Design

**Date:** 2026-07-26. Settled with the user; belongs in the specification as
**§ 7.14** and in `implementation-decisions.md` as decision 51.

Measurements in, a law computes the net: cut lines solid, fold lines dashed,
glue tabs computed. It is the feature that *proves* the one promise instead of
describing it — a box 2 mm out does not close.

## Why this is not a drawing language (§ 2)

§ 2 rules out free strokes at chosen coordinates, and allows a generator its own
law: "die Def beschreibt, *was* dasteht, und nicht, *wo* jeder Strich anfängt".
A net is exactly that shape of thing. The definition says **a tuck-top box,
80 × 50 × 30 mm, 0.3 mm card**; every coordinate follows from that. What would
cross the line is a key that places a panel — and there is none.

## The mechanism: panels, and edges that appear twice

A style produces **panels** — closed polygons in area-local micrometres — and
nothing else. Then one rule turns them into marks:

> An edge shared by two panels is a **fold**. An edge belonging to one panel is
> a **cut**.

That is the whole cut/fold distinction, and it falls out of the geometry instead
of being maintained by hand. It also makes a new style a matter of listing
panels: no style ever traces an outline, so no style can trace one wrongly.

The dedupe is exact, because positions are integer micrometres (§ 3.3) — two
panels either share an edge or they do not, with no tolerance to tune. For that
to hold, **every flap spans its attachment edge completely** and tapers only on
its free side, which is also how a real carton is cut.

## The definition

```yaml
generator: net
style: tuck_top          # tuck_top | tray
length: 80mm             # inner dimensions — the space inside the box
width: 50mm
height: 30mm
thickness: 0.3mm         # material; 0 for thin paper
glue_tab: 12mm           # the tab that closes the wall strip
tuck: 15mm               # the tongue that slides into the front wall (tuck_top)
dust: auto               # the flaps under the lid (tuck_top); auto = length/3, ≤ 25 mm
cut:  { weight: 0.4pt, color: "#000000" }
fold: { weight: 0.25pt, color: "#888888", style: dashed }
```

**Dimensions are inner dimensions.** The number a user has is the thing that has
to go in the box, so that is the number they type.

**Thickness has one rule, stated once:** a panel that closes *over* another
layer is widened by `thickness`; a flap that slides *inside* one is shortened by
it. With `thickness: 0` every allowance vanishes and the net is the ideal one —
a test asserts exactly that, which is what keeps the rule honest.

## The two styles

**`tray`** — an open box. A base of `length × width`, four walls of `height`,
and a corner tab at each end of the two end walls, tapered so it slides. Flat
size `length + 2·height` by `width + 2·height`.

**`tuck_top`** — the classic carton. One strip of four walls
(`length`, `width`, `length`, `width`) with a glue tab at the end; at the top, a
lid panel on the back wall (`width + thickness` deep) carrying the tuck tongue
(`tuck − thickness`), and a dust flap on each side wall; the same closure
mirrored at the bottom. Flat size
`2·(length + width) + glue_tab` by `height + 2·(width + tuck)`.

The **fold notation** is § 2a's, and needs no new machinery: cut lines solid,
fold lines dashed by default, both restyled through the ordinary `weight`,
`color`, `style` and `dash` keys the rest of the tool uses.

## Refusals, before page one

1. **The net does not fit the pattern area** — refused with the flat size it
   needs and the size there is, in millimetres, and a note that a net is never
   scaled (§ 8.2). This is `check`'s job, and the one refusal a net cannot avoid.
2. **A dimension that is not positive**, and a `thickness` at or above half the
   smallest dimension — a box whose walls meet in the middle is not a box.
3. **A key that means nothing for the chosen style** — `tuck` or `dust` on a
   `tray` — refused by name rather than ignored (§ 5.1).
4. **An unknown `style`**, listing the two that exist. Anything else named in
   this file's *Later* section refuses with the name of the thing it would be.

## Deliberately not in this version

- **No other styles yet.** An envelope, a wrap-around sleeve and a lidded
  two-piece box are all the same mechanism with different panel lists; they
  arrive when someone wants one, and until then `style:` refuses them by name.
- **No labels on the panels.** § 2: the tool describes structure, and a printed
  "FRONT" is a drawing decision.
- **No nesting or imposition of several nets on one sheet.** `--nup` already
  places whole pages, and a net that does not fit is a refusal, not a puzzle.
- **No creasing allowance per fold** (the small gap a crease consumes on thick
  board). `thickness` covers the case that closes a box; this one is a
  press-shop refinement and would be a guessed number here.

## Tests

- **`thickness: 0` gives the ideal net**: every panel is exactly its nominal
  size, for both styles;
- with `thickness: 0.3mm` the lid is 0.3 mm deeper and the tongue 0.3 mm
  shorter — the rule, in both directions;
- **fold and cut are told apart by the shared-edge rule**: a tray has exactly
  eight folds (four base edges, four tab edges) and its cut length equals the
  outline;
- the flat size matches the formula above, for both styles;
- the four refusals, by message;
- **read back from a real PDF**: the base of an 80 × 50 tray measures 80 × 50 mm
  out of the file, and the total ink stays inside the pattern area;
- two runs, identical bytes.

And one thing no test can do: **cut one out and fold it.** A tray of
80 × 50 × 30 mm printed at 100 %, cut, folded — if it does not close, the
arithmetic is wrong and the tests were agreeing with it.
