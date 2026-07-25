# Slanted line families — design

**Date:** 2026-07-25. **Status:** the two open forks settled with the user;
ready for an implementation plan. Everything else is already **specified**:
§ 7.1 fixes the DSL and the semantics, and `lines.py` has refused
`direction: <angle>deg` by name since M1. This file records only what § 7.1
leaves open, and why each answer is the one that keeps a single rule instead of
two.

## What § 7.1 already decides (not up for discussion)

```yaml
families:
  - direction: 55deg        # horizontal | vertical | <angle>deg
    base_spacing: 8mm       # the PERPENDICULAR distance between neighbours
    offset: 2mm             # also perpendicular
    extent: { start: …, end: … }   # also perpendicular
```

- Every line is **clipped to the pattern-area rectangle**.
- **Snapping is not supported** for a slanted family — an error, never a guess.
- `extent` decides *which lines exist*, never how long they are (§ 7.1, § 2).

## The two decisions

### 1. Line 0 goes through the origin, and an unlimited family grows both ways

The existing rule is "mark 0 sits on the origin — for a horizontal family at
the bottom edge, for a vertical one at the left" (`lines.py`). A slanted family
keeps exactly that rule: **line 0 is the line through the pattern area's local
origin (0, 0) at the family's angle**, and `offset` moves the start of the cycle
along the perpendicular, as everywhere else.

An unlimited family then fills the area in **both** perpendicular directions.
This is not a second rule: for a horizontal or vertical family the whole area
lies on the positive side of line 0, so growing both ways changes nothing, and
today's output stays byte-identical. For a 45° family it is the only way to
cover the sheet, since the line through one corner leaves half the area behind
it.

`count: n` keeps its meaning — n lines from line 0 in the cycle's direction —
so the single red margin rule and the two Cornell verticals go on meaning what
they mean, and a `count`ed slanted family draws a fan on one side only.

Rejected: anchoring at "the corner with the smallest perpendicular coordinate"
(the anchor would move with the angle, so a 1° change could jump the whole
family across the sheet) and anchoring at the area's centre (a second rule for
where mark 0 sits, contradicting the one horizontal and vertical follow).

**Consequence, deliberately accepted:** with lines on both sides of the origin,
a perpendicular coordinate can be negative, so `extent: { start: -40mm }` is
meaningful and allowed. `parse_length` already accepts a negative length; the
existing "start before end" check still holds.

### 2. Scope: the angle, plus the guide sheet it exists for

Slanted families, and a `calligraphy-a4` preset plus a gallery sheet showing an
italic guide: a ruled cycle of body/ascender/descender heights crossed by 55°
slant lines. Measures in millimetres.

The **nib-width unit** (`nib: 2mm` in the definition, then `base_spacing: 4nw`)
is *not* in scope. It is § 15 open question 4, it needs an anchor field of its
own, and the specification says that class of decision waits on real use rather
than on a design answer. The angle is what unlocks both calligraphy guides and
origami pre-creasing; the unit is a convenience on top of it.

## Geometry

For a family at angle θ (mathematically positive, 0° pointing right, § 3.5):

- The **perpendicular axis** is the unit vector `n = (-sin θ, cos θ)`; a line's
  identity is its signed perpendicular coordinate `d`, and line 0 has `d = 0`
  because it passes through the origin.
- The positions of the ticks along `d` come from the existing `Cycle`
  machinery, exactly as for a horizontal family — the cycle is a cycle whatever
  axis it sits on, so `spacing`, `weight`, `color` and `dash` need no new code.
- Growing both ways means walking the cycle forwards from 0 and **backwards**
  from 0. Backwards is not "negate the forward positions": the cycle is a list
  and running it in reverse is what keeps `spacing: [2, 1]` symmetric about
  line 0 rather than shifted by one step.
- The **span** to walk is bounded by the four corners: project each corner onto
  `n`, and the family only needs lines between the smallest and largest
  projection. No line outside that range can cross the area, so the loop
  terminates without trial and error.
- Each line is **clipped with Liang–Barsky** — the exact function
  `perspective.py` already uses, in exact rationals, moved to a shared module
  rather than copied. A line whose clipped length is empty is not drawn.
- Angles are taken **modulo 180°**: a line has no direction, so `55deg` and
  `235deg` are the same family. `0deg` and `90deg` are allowed and produce
  exactly what `horizontal` and `vertical` produce.

## Refusals, all before page one

1. **`snap` and a slanted family on the same axis** — § 7.1 rules snapping out
   by name. A slanted family reports **no periodic axis** (it has no cartesian
   period), so `governing: true` on one is refused too, naming § 7.1.
2. **A family that crosses nothing** — an `extent` or `count` that puts every
   line outside the pattern area is refused with the arithmetic rather than
   drawing an empty sheet, the way `perspective.check` already refuses a fan
   that misses the area.
3. The existing per-family refusals (stroke not narrower than spacing, log +
   slant, dash without a style that uses it) keep working unchanged; `law:
   log10` on a slanted family is refused, because a decade's positions are
   defined along an axis.

## Where it lives

| File | Change |
|---|---|
| `ctrlgrid/units.py` | nothing — `parse_angle` already exists |
| `ctrlgrid/clip.py` **(new)** | Liang–Barsky, moved out of `perspective.py` unchanged, with its tests |
| `ctrlgrid/generators/lines.py` | `DirectionField` accepts an angle; `Family.angle`, the perpendicular walk, no axis for slanted families |
| `ctrlgrid/generators/perspective.py` | imports the clipper instead of holding it |
| spec § 7.1 | the two decisions written in, in German |
| `implementation-decisions.md` | decision 48 |
| `HANDBOOK.md` | § 12 `lines`, and the calligraphy example |
| `ctrlgrid/data/presets/calligraphy-a4.yaml`, `examples/14-calligraphy-italic.yaml` | the payoff |

## Testing

- the angle parses, is taken modulo 180, and `0deg`/`90deg` equal `horizontal`/
  `vertical` **mark for mark** — the sharpest possible test of the general case;
- an existing horizontal definition is **byte-identical** after the change;
- a 45° family on a square area: line 0 runs corner to corner, the count of
  lines matches the corner projections, and every mark lies inside the area;
- `spacing: [2, 1]` is symmetric about line 0;
- the three refusals, by message;
- a real sheet read back with `tests/pdfread.py`: the perpendicular distance
  between two neighbouring 55° lines is the `base_spacing`, measured out of the
  PDF — that is the promise for slanted families, and nothing else proves it.
