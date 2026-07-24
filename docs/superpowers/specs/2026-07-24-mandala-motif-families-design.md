# Mandala — more varied motif families

**Date:** 2026-07-24
**Status:** approved (brainstorming), ready for implementation
**Touches:** `ctrlgrid/generators/mandala.py`, its tests, the mandala example/preset,
spec § 7.11, CLAUDE.md, `docs/implementation-decisions.md`.

## Goal

Make `mandala` visibly more varied without leaving its design (§ 7.11): a
*template to draw on*, parametric, not a shape language (§ 2). Today it offers
`rings`, `spokes`, `rosette` (one ring of circles), and `polygons`. The output
reads as "overlapping circles + straight polygons" and misses the most iconic
mandala elements: **petals, bead borders, and layered motif bands**.

Three additions, all built from existing primitives (§ 6), all N-fold and
facing up (90°) like the rest of the blade.

## Unifying principle: a stackable motif ring

The three families share one shape — an N-fold-repeated ring — and each may be
given **once or as a list** (layered bands). The existing `rosette` becomes
single-or-list too, which is backward compatible: a single mapping still
validates. `polygons` stays a plain list as it is today.

Internally each single-or-list field normalises to a tuple via a small helper,
so `generate`/`check`/`describe` always iterate.

## 1. `petals` — a ring of pointed leaves (new; only `Arc`)

Each petal is two circular arcs meeting at a base point and a tip point, bulging
symmetrically to either side — a vesica/leaf. One petal per sector.

```yaml
petals:                 # single, or a list of these
  inner: 0.30           # share of outer radius: where the base sits
  outer: 0.95           # share: how far the tips reach
  width: 0.12           # half-width at the widest, share of outer radius (the bulge)
  mirror: false         # also a petal on each sector bisector (count doubles)
  weight: 0.2pt
  color: "#8aa0b8"
```

- Count = `sectors` (×2 with `mirror`), exactly like `rosette`.
- Validation: `inner < outer` and `width > 0` (a degenerate petal is refused
  loudly, § 12, never bent).

### Petal geometry (two arcs)

Petal centred on angle `a`. Base `B = polar(inner·R, a)`, tip `T = polar(outer·R, a)`;
the chord `B→T` is radial, length `c = (outer−inner)·R`. Each side arc passes
through `B` and `T` with sagitta `s = width·R` to opposite sides.

For one side (unit perpendicular `u`, unit chord `t`, midpoint `M`):

- radius `r = s/2 + c²/(8s)`
- centre `O = M − (r − s)·u`  (opposite the bulge)
- `start = atan2(B − O)`, `end = atan2(T − O)`, `sweep` = the minor-arc signed
  difference (|sweep| < 180) with the sign that bulges toward `+u`.

The two arcs use `+u` and `−u`. Emitted as two `Arc(center=O, radius=r,
start_angle, sweep, …)` marks — no new primitive, our `Arc` already draws an
arbitrary circular arc from centre + radius + start + sweep.

## 3. `beads` — dots on a ring (new; introduces `Dot`)

```yaml
beads:                  # single, or a list of these
  - at: 0.62            # share of outer radius (which ring)
    count: 24           # default = sectors; a multiple reads calmly
    size: 0.8mm         # bead diameter, absolute (or relative %s)
    rotate: 0.0         # optional angular offset, degrees
    color: "#2f5686"
```

- `count` defaults to `sectors`; any integer ≥ 1 is allowed (a non-multiple
  still draws, it just relaxes strict N-fold — the user's call).
- `size` is a `LengthField` (absolute mm, or relative `%s` via
  `RelativeLengthField` — decision: relative, to match `at` scaling and the rest
  of the blade). Emitted as `Dot(pos, diameter=size, color)`.

**Spec note:** § 7.11 currently lists Arc/Segment/Polygon as the mandala marks.
`Dot` is a core primitive (§ 6); the spec line is extended to include it —
honestly, not silently. No new primitive.

## 4. `rosette` — now single **or** list

Form unchanged (`at`, `radius`, `mirror`, weight, color); only the type widens
to single-or-list so flower bands can stack. Existing example and preset run
unchanged.

## Integration (the existing seams, no new ones)

- **`check` / `_max_reach`** — every ring reports its reach so a motif that runs
  past the pattern area is refused before page one, named, never clipped or
  scaled (§ 8.2, § 12 point 13):
  - petal reach = `max(outer, sqrt(((inner+outer)/2)² + width²))·R` (the tip
    dominates in practice; the lateral term is there for rigour).
  - bead reach = `at·R + size/2`.
  - rosette reach unchanged (`at + radius`).
  - Over a list, the max over all rings.
- **`describe`** — one line per ring (e.g. `petals: 12, mirrored`, `beads: 24 at
  0.62 of the radius`).
- **`generate`** — draw order: scaffold (rings, spokes) first, then the motif
  families (rosette, petals, beads, polygons), so guides sit under motifs.

## Testing (test-first, this project's discipline)

- Unit tests per family: count of marks, angles face up, geometry lands where
  asked (petal base at `inner·R` on the sector angle, bead on its ring), the
  single-or-list normalisation, and the validation refusals.
- `check` refuses an over-reaching petal ring and an over-reaching bead ring,
  before page one, naming the family and the overflow.
- A real rendered PDF read back with `pdfread` / an independent parser — not
  only unit tests — and a rasterised look.
- Refresh `examples/10-mandala.*` (and/or the preset) to show the new families;
  `test_every_example_validates` guards it.

## Docs updated in the same breath

Spec § 7.11 (the new families + the `Dot` mark note), CLAUDE.md (mandala row),
`docs/implementation-decisions.md` (the single-or-list rule, the `Dot`
extension, the petal two-arc construction).

## Out of scope (YAGNI, revisit on request)

Scalloped rings (motif 2) and the polygon pinwheel (motif 5) — each overlaps
conceptually with petals / polygons and would be added later as a *mode*, not a
new family.
