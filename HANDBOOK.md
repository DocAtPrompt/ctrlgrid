# Ctrl+Grid — Handbook

A complete guide to generating dimensionally accurate PDF (and PNG) templates:
grid paper, ruled paper, dot grids, staff paper, mazes, polar targets, tilings,
fillable forms, perspective grids and mandalas — for paper formats and for
e-ink devices.

**The one promise:** what says 5 mm measures 5 mm on the printout. No scaling,
no "fit to page", no stretching a grid so it comes out even. If a template does
not fit a page, Ctrl+Grid tells you — it never silently shrinks it.

This handbook is the user-facing manual. For *why* the tool is built the way it
is, see the specification, [`pflichtenheft-vorlagengenerator.md`](docs/pflichtenheft-vorlagengenerator.md)
(German); for the decisions taken where the spec was silent, see
[`implementation-decisions.md`](docs/implementation-decisions.md).

---

## Contents

1. [Installation](#1-installation)
2. [Quick start](#2-quick-start)
3. [How it works: handle and blades](#3-how-it-works-handle-and-blades)
4. [The command line](#4-the-command-line)
5. [The definition file](#5-the-definition-file)
6. [Units and measures](#6-units-and-measures)
7. [The page](#7-the-page)
8. [The pattern area and geometry](#8-the-pattern-area-and-geometry)
9. [The cycle model](#9-the-cycle-model)
10. [Frame furniture](#10-frame-furniture)
11. [The cover sheet and embedding the definition](#11-the-cover-sheet-and-embedding-the-definition)
12. [The generators](#12-the-generators)
13. [E-ink and devices](#13-e-ink-and-devices)
14. [N-up imposition](#14-n-up-imposition)
15. [Output formats](#15-output-formats)
16. [Batch output: name lists](#16-batch-output-name-lists)
17. [Fonts](#17-fonts)
18. [Presets](#18-presets)
19. [Printing accurately](#19-printing-accurately)
20. [Errors and validation](#20-errors-and-validation)
- [Appendix A — units](#appendix-a--units)
- [Appendix B — paper formats](#appendix-b--paper-formats)
- [Appendix C — command-line flags](#appendix-c--command-line-flags)
- [Appendix D — generators at a glance](#appendix-d--generators-at-a-glance)

---

## 1. Installation

Ctrl+Grid is a Python CLI. It is not on PyPI yet, so install it from the Git
repository. The simplest way, with [uv](https://docs.astral.sh/uv/):

```bash
uvx --from git+https://github.com/DocAtPrompt/ctrlgrid.git ctrlgrid --help
```

That runs it without a permanent install. To install it into a tool
environment:

```bash
uv tool install git+https://github.com/DocAtPrompt/ctrlgrid.git
```

Or with pip, from a clone:

```bash
git clone https://github.com/DocAtPrompt/ctrlgrid.git
cd ctrlgrid
pip install .
```

For development (tests and linter):

```bash
uv sync --extra dev && uv run pytest && uv run ruff check .
```

The bundled music font (for staff clefs) and the presets travel with the
package — nothing else to fetch.

---

## 2. Quick start

Generate 5 mm graph paper on A4 from a preset:

```bash
ctrlgrid millimeter-a4 -o grid.pdf
```

List the presets, print one to copy and bend, or list the e-ink devices:

```bash
ctrlgrid presets
ctrlgrid show millimeter-a4 > mine.yaml
ctrlgrid devices
```

Run your own definition file:

```bash
ctrlgrid -d mine.yaml -o out.pdf
```

Validate a definition without writing anything:

```bash
ctrlgrid check mine.yaml
```

Run with no arguments in a terminal to open the interactive preset browser
(pick a preset, page count and output file).

---

## 3. How it works: handle and blades

Ctrl+Grid is a pocket knife: **one handle, several blades.**

- The **handle** owns everything about the page: format, margins, the pattern
  area, the frame, header and footer, stamp, hole marks, the page loop and the
  output file.
- A **blade** (a *generator*) only fills the pattern area with marks. It knows
  nothing about margins or paper size — it is handed a rectangle and asked for
  marks in local coordinates.

Because of that split, the same generator fills A4, A6, US Letter or a 3:4 e-ink
slate without changing a line: only the handle's page settings change. Every
definition names exactly one generator.

Everything is measured, then drawn. A run either aborts completely (with an
error you can act on) or produces the whole document — never half a file.

---

## 4. The command line

### Commands

| Command | What it does |
|---|---|
| `ctrlgrid <preset>` | Build from a shipped preset (e.g. `ctrlgrid millimeter-a4`) |
| `ctrlgrid -d <file>` | Build from your own definition file |
| `ctrlgrid generate …` | The explicit form of the two above |
| `ctrlgrid check <file>` | Validate and write nothing (§ 20) |
| `ctrlgrid presets` | List the shipped presets |
| `ctrlgrid show <preset>` | Print a preset's definition, ready to copy |
| `ctrlgrid devices` | List device profiles, with where their figures come from |
| `ctrlgrid` (no args) | Interactive preset browser (in a terminal) |

### Choosing the output

The **output format follows the file extension** of `-o`:

- `-o out.pdf` → a PDF (vector, the reference output).
- `-o out.png` → one PNG per page at the device's exact pixel size (needs a
  device; see §13).

If a target file already exists, the run refuses rather than overwrite it. Pass
`--force` to overwrite.

### Flags

All flags beat the definition file (the command line always wins). Switch-style
flags (`--cover`, `--strict`, `--embed-def`) only ever turn something *on* — the
definition decides when the flag is absent.

See [Appendix C](#appendix-c--command-line-flags) for the full list. The most
common:

```bash
ctrlgrid millimeter-a4 --pages 30 -o grid.pdf      # 30 numbered sheets
ctrlgrid millimeter-a4 --cover -o grid.pdf         # + a calibration first sheet
ctrlgrid -d mine.yaml --format a5 -o out.pdf       # override the paper format
ctrlgrid -d mine.yaml --device remarkable-paper-pro -o pad.pdf
ctrlgrid millimeter-a4 --names class.txt -o sheets.pdf   # one sheet per name
```

---

## 5. The definition file

A definition is a YAML file. The smallest possible one names a version and a
generator with its settings:

```yaml
version: 1
generator: lines
families:
  - { direction: horizontal, base_spacing: 5mm }
```

The top level has three kinds of key:

1. **`version`** — currently always `1`. Required.
2. **Handle sections** — `page`, `header`, `footer`, `border`, `stamp`,
   `pattern`, `pages`. All optional; each is described below.
3. **The generator** — `generator: <name>` plus that generator's own keys at the
   top level (for example `families:` for `lines`, `cells:` for `grid`).

### Reusing values with anchors

YAML anchors keep a palette in one place. Define them under `defs:` (a reserved
block that is not otherwise interpreted) and reference them with `*name`:

```yaml
defs:
  grid:   &grid   "#7799bb"
  accent: &accent "#4466aa"

# … later …
color: [*grid, *grid, *grid, *grid, *accent]
```

Unknown keys are **rejected**, not ignored — a misspelled `bordr:` is an error,
never a silently dropped border.

---

## 6. Units and measures

Every measurement is written with its unit. There is no bare-number default.

### Lengths

| Suffix | Meaning |
|---|---|
| `mm` | millimetres — `5mm` |
| `cm` | centimetres — `2cm` |
| `in` | inches — `0.5in` |
| `pt` | printer's points, 1/72 in — `0.15pt` (typical stroke width) |

Positions are held internally as exact integer micrometres, so a grid never
drifts: `72pt` is exactly `25400µm`, and repeat runs are byte-identical.

### Relative measures

`%w`, `%h` and `%s` are a fraction of the **pattern area** — its width, its
height, and its shorter side. They let one definition fill both A4 and a 3:4
e-ink slate:

```yaml
outer_radius: 48%s     # 48 % of the shorter side, whatever the format
```

### Device pixels

`px` resolves against a device's pixel density and is only allowed when a
device profile is active (§13). On paper it is refused — a printer has no fixed
pixel.

### Angles

Angles are in degrees: `45deg`. Zero points right; positive is counter-clockwise.

### Staff spaces

Staff paper measures in `sp`, one staff space — the distance between two lines
of a stave. See the `staves` generator (§12).

### Paper formats

Named formats: `a3`, `a4`, `a5`, `a6`, `letter`, `legal`, `tabloid`. Or give an
exact size:

```yaml
page:
  format: 210x99mm      # a DL-ish slip
  # or
  format: 8.5x11in
```

---

## 7. The page

The `page:` section is the handle's description of the sheet.

```yaml
page:
  format: a4              # or a device (below), or an exact size
  orientation: portrait   # or landscape
  duplex: false           # two-sided binding (see margins)
  background: none        # or a colour, painted under everything
  hole_marks: false       # ISO 838 punch marks at the binding edge
  margin: 10mm            # see below
```

### Margins

`margin` can be a single value (all four sides) or the four named edges:

```yaml
page:
  margin:
    top: 15mm
    bottom: 15mm
    inner: 20mm     # the binding edge
    outer: 12mm     # the open edge
```

Margins are named **inner/outer**, not left/right, because of duplex. With
`duplex: true`, `inner` and `outer` swap on even pages so the wide binding
margin always sits at the spine. With duplex off, `inner` is simply the left
margin.

### The device instead of a format

Instead of `format`, name a `device` to target an e-ink screen (§13). Format
and device are mutually exclusive — they are two answers to "what medium".

---

## 8. The pattern area and geometry

The **pattern area** is what is left after margins, header, footer and their
gaps are removed. It is the rectangle the generator fills. Everything the
generator draws lives here; the handle owns the frame around it.

The `pattern:` section tunes how a repeating pattern meets the edges of that
area.

```yaml
pattern:
  align: bottom-left     # which corner the grid is anchored at
  snap: none             # or cycle / pixel, per axis
  remainder: center      # where the leftover space goes, per axis
```

### `align`

Which corner the pattern is anchored to: `bottom-left` (default), `top-left`,
`bottom-right`, `top-right`. The complete block starts at that corner, so any
incomplete block falls to the opposite one. Useful when you want whole cells to
start at the top-left of the page.

### `remainder`

A pattern rarely divides the area exactly. `remainder` decides where the
leftover goes, per axis (`x`, `y`) or both:

- `center` (default) — split evenly on both sides, so the leftover reads as
  breathing room, not a mistake.
- `end` — pattern at the origin, all leftover at the far edge.
- `whole_cycles` — drop the incomplete cycle entirely; the freed space goes to
  the far end.

```yaml
pattern:
  remainder: { x: center, y: end }
```

### `snap`

By default (`none`) the pattern keeps its exact spacing and the leftover is
placed by `remainder`. `snap` instead adjusts the geometry so blocks come out
even:

- `cycle` — shrink the pattern area to a whole number of cycles (whole blocks
  only, no partial cells at the edge).
- `pixel` — round every step to whole device pixels, for a crisp e-ink render
  (needs a device; §13).

`snap` is an **error** for generators whose pattern has a centre rather than an
axis to snap to (`polar`, `mandala`, `staves`, `grid`, `maze`, `tiling`,
`form`) — the tool says so rather than guessing.

---

## 9. The cycle model

The cycle model is the heart of the tool. In `lines`, `dots` and `polar`, each
visual property — spacing, stroke weight, size, dash, colour — follows its own
**repeating list**, and the lists may be different lengths.

"Every fifth line heavier and blue" is one cycle for weight and one for colour,
each five long, running against a one-entry spacing cycle:

```yaml
generator: lines
families:
  - direction: horizontal
    base_spacing: 1mm            # the base value
    spacing: [1]                 # × 1 each step → 1 mm apart
    base_weight: 0.15pt
    weight: [1, 1, 1, 1, 2.7]    # every fifth line 2.7× as thick
    color: ["#7799bb", "#7799bb", "#7799bb", "#7799bb", "#4466aa"]
```

Each cycle is a list of dimensionless multipliers of a `base_…` value. A bare
`base_spacing` with no `spacing:` cycle means "the same every step". Because the
lists run independently and repeat, a short colour cycle against a longer
spacing cycle produces rich, regular patterns from a few numbers.

The `millimeter-a4` preset (run `ctrlgrid show millimeter-a4`) is the canonical
worked example.

---

## 10. Frame furniture

Everything around the pattern area is the handle's. All optional.

### Header and footer

`header` and `footer` are bands of fixed height with three fields — `left`,
`center`, `right`:

```yaml
header:
  height: 8mm
  gap: 4mm            # blank space between the band and the pattern
  font: { family: sans, size: 10pt }
  left: "{name}"
  center: "Week {page} / {page_count}"
  right: "2026"
  cut: false          # what happens if fields collide (below)
```

**Placeholders** are filled per page: `{page}`, `{page_count}`, and `{name}`
(from a name list, §16).

If long fields collide, `cut: false` (the default) refuses the run and names the
field and the missing millimetres; `cut: true` truncates with an ellipsis.

A field may hold an **image** instead of text — a PNG, never cropped:

```yaml
header:
  height: 12mm
  left: { image: logo.png, height: 10mm }
```

### Border, background, hole marks, stamp

```yaml
border:
  weight: 0.3pt
  color: "#333333"
  gap: 2mm            # inset from the pattern area

page:
  background: "#fbfbf7"    # painted under everything
  hole_marks: true         # ISO 838: two marks, 80 mm apart, 12 mm in

stamp:
  text: DRAFT
  angle: 45deg
  opacity: 0.08            # a faint full-page watermark
  size: auto               # sized to ~80 % of the sheet width
```

`--stamp DRAFT` on the command line is the quick route to a stamp.

---

## 11. The cover sheet and embedding the definition

### The calibration cover

`--cover` (or `pages.cover: true`) adds one extra first page carrying three
things:

1. **A calibration square** of exactly 50 mm and a 100 mm rule, each labelled.
   Lay a ruler on them: if the measure is off, your printer scaled.
2. **A stroke-weight ladder** — short lines from 0.1 to 1.0 pt, each labelled,
   so you see how thin each weight really prints (and, on a device, its pixel
   width).
3. **A settings summary** — generator, format, margins, base values, cycles,
   effective period, snap mode, tool version and the definition's checksum. A
   good sheet stays reproducible years later.

The cover is not counted in page numbering (`--pages 30 --cover` gives 30
numbered sheets plus the cover), carries no header/footer/border/stamp, and is
never scaled by imposition.

### Embedding the definition

`--embed-def` (or `pages.embed_def: true`) embeds the definition's **exact
source bytes** in the PDF as a file attachment, so the document literally carries
its own source and can be regenerated later without hunting for the file. PDF
only — on PNG output the run is refused with the reason, rather than dropping
the attachment silently.

---

## 12. The generators

Every generator fills the pattern area. Colours are `#rrggbb`. Stroke widths are
lengths (the defaults below are the shipped values). Each has a worked example in
[`../examples/`](examples/) and, for most, a preset (run `ctrlgrid show <name>`).

### `lines` — ruled, squared, isometric, log

One or more **families** of parallel lines. Cross two families for squared paper;
angle them for isometric; use `law: log10` for graph paper.

```yaml
generator: lines
families:
  - direction: horizontal      # or vertical (required)
    base_spacing: 5mm          # required
    base_weight: 0.15pt
    weight: [1, 1, 1, 1, 2.7]  # every fifth line heavier (the cycle model, §9)
    color: ["#000000"]         # one colour, or a cycle
  - direction: vertical        # cross two families for squared paper
    base_spacing: 5mm
    base_weight: 0.15pt
    weight: [1, 1, 1, 1, 2.7]
```

Each family also takes, all optional:

- `spacing: [ … ]` — a cycle of spacing multipliers (uneven rules).
- `offset: <length>` — shift the whole family across.
- `style: dashed` or `dotted` with `base_dash: <length>` (and `dash:` to set an
  explicit pattern). `base_dash` is refused on a `solid` line — the tool never
  accepts a setting that would do nothing.
- `extent: { start:, end: }` bounds *which* lines are drawn (never how long a
  line is — there is no "draw a stroke here" primitive), or `count: <n>` caps
  the number of lines.
- `law: log10` with `decades: <n>` for logarithmic graph paper; `decades` has no
  meaning on a linear family and is refused there.
- `governing: true` — when two families share an axis and disagree on their
  period, one must be marked to set it.

```yaml
# logarithmic graph paper:
families:
  - { direction: horizontal, base_spacing: 20mm, law: log10, decades: 3 }
```

Example: [`01-lines-squared.yaml`](examples/01-lines-squared.yaml). Preset:
`millimeter-a4`.

### `dots` — dot grids

Two crossed cycles of dots. The interesting question is what happens where they
meet — `combine` decides.

```yaml
generator: dots
grid:
  x: { base_spacing: 5mm, spacing: [1], offset: 0mm }
  y: { base_spacing: 5mm, spacing: [1] }
base_size: 0.3mm
size_x: [1, 1, 1, 1, 1.8]     # every fifth column larger
size_y: [1, 1, 1, 1, 1.8]
combine: max                  # max | product | intersection_only
color:                        # a single colour, or coloured by an axis:
  axis: cross
  cycle: ["#aab4c0", "#aab4c0", "#aab4c0", "#aab4c0", "#5577aa"]
```

`combine: max` gives the full cross grid; `intersection_only` keeps only dots
where both cycles emphasise. A colour cycle must name its `axis`.

Example: [`02-dots-grid.yaml`](examples/02-dots-grid.yaml). Preset: `dots-5mm`.

### `grid` — labelled cell blocks

A count-driven block of square cells with optional labels and fills — battleship
boards, score sheets, seating charts, bingo.

```yaml
generator: grid
cells: { x: 12, y: 12 }        # required
labels:
  columns: "A"                 # A, B, C… (a § 7.10 counting pattern, or a list)
  rows: "n"                    # 1, 2, 3…
weight: 0.3pt
color: "#33475b"
fill: checker                  # none | checker | rows | columns
fill_color: "#eef2f6"
header_row: false
font: { size: 9pt }
```

Label patterns: `n` → 1, 2, 3…; `a`/`A` → a, b, c / A, B, C; or an explicit list.

Example: [`03-grid-battleship.yaml`](examples/03-grid-battleship.yaml).
Preset: `grid-a4`.

### `polar` — targets, score discs, polar paper

Concentric rings and radial spokes about a centre, with optional labels. Built
on the same cycle model as `lines`.

```yaml
generator: polar
center: auto                   # or { x: 105mm, y: 148mm }
outer_radius: 48%s             # auto, a length, or relative
rings:
  base_radius: 10mm            # required
  radius: [1]                  # cycle of ring-spacing multipliers
  base_weight: 0.15pt
  weight: [1, 1, 1, 1, 2]
  color: ["#000000"]
spokes:
  base_angle: 30deg            # required
  angle: [1]
  weight: [1]
  color: ["#000000"]
labels:
  spokes: "n"                  # label each spoke / ring with a pattern or list
  spoke_radius: 0.85
  rings: "n"
  font: { size: 8pt }
```

An optional `radial_extent: { start:, end: }` on `spokes` keeps the spokes clear
of the centre (like a bullseye with an open middle). Ring and spoke families use
the same cycle model as `lines`, so `radius`/`angle` and `weight` follow
repeating lists — every fifth ring heavier, and so on.

Example: [`06-polar-target.yaml`](examples/06-polar-target.yaml). Preset:
`polar-a4`.

### `tiling` — hexagons, triangles, rhombi

An edge net of a regular tiling, drawn once (shared edges are not doubled).

```yaml
generator: tiling
shape: hex                     # hex | tri | square | rhombus | octagon_square
size: 10mm                     # edge length (required; relative allowed)
orientation: pointy            # pointy | flat
weight: 0.4pt
color: "#3a4a5a"
fill: none                     # none | cycle
fill_colors: ["#eef3f7", "#dbe6ef", "#c7d8e8"]   # with fill: cycle
labels: none                   # none | coordinates
font: { size: 7pt }
```

Example: [`07-tiling-hex.yaml`](examples/07-tiling-hex.yaml). Preset:
`tiling-hex-a4`.

### `maze` — rectangular mazes

A perfect maze with an optional drawn solution. Procedural, so it takes a
`seed`.

```yaml
generator: maze
cells: { x: 20, y: 28 }        # required
algorithm: backtracker         # backtracker | prim | kruskal
start: bottom-left             # a corner
goal: top-right                # a corner
min_path_factor: 0.0           # 0–1: bias toward a longer solution path
wall_weight: 0.5pt
color: "#000000"
solution_color: "#cc3333"
seed: 0
solution: none                 # none | overlay | separate_page | back_mirrored
```

`solution: separate_page` prints the solution on the next sheet;
`back_mirrored` puts it on the back for duplex printing. A maze item can span
several sheets — the handle does the doubling and numbering.

Example: [`05-maze-booklet.yaml`](examples/05-maze-booklet.yaml) (a multi-page
booklet). Preset: `maze-medium`.

### `form` — fillable forms

Rows of labelled fields — phone logs, checklists, planners, handover sheets.
One level of nesting (a row of columns, a column of fields).

```yaml
generator: form
title: { position: above, font: { size: 8pt } }   # above | inline | none
gap: 3mm
weight: 0.4pt
color: "#000000"
rows:
  - height: 15%                # a percentage of the pattern-area height, or `rest`
    columns:
      - { title: "Name", width: 70% }         # a text field (writing lines)
      - { title: "Done", kind: check }         # a tick box
  - height: rest
    columns:
      - { title: "Priority", kind: choice, options: ["Lo", "Hi"] }
```

Rows come first, then columns — one level of nesting. A row's `height` is a
percentage or `rest`; a column's `width` is a percentage of the row. A field's
`kind` is `text` (the default: ruled writing lines), `check` (a tick box) or
`choice` (named `options`). Labels like "Ja"/"Nein" come from your file, never
the tool — Ctrl+Grid adds no language of its own.

Example: [`08-form-weekly.yaml`](examples/08-form-weekly.yaml). Preset:
`phone-log-a5`.

### `staves` — music and tab

Grouped systems of staff lines, measured in staff spaces (`sp`). Clefs are real
glyphs from a bundled, subset music font.

```yaml
generator: staves
count: 12                      # number of staves (required)
lines: 5                       # lines per stave (5 = music, 6 = guitar tab)
stave_space: 1.75mm            # the sp unit (or set stave_height)
system_gap: 6.5sp              # space between staves
weight: 0.2pt
color: "#000000"
clef: treble                   # none | treble | bass | alto | tenor
clef_indent: 3mm
```

Example: [`04-staves-treble.yaml`](examples/04-staves-treble.yaml). Preset:
`staves-treble-a4`.

### `perspective` — drawing grids

A horizon with one to three vanishing points, each fanning equally divided rays,
plus optional true verticals. The grid computes its own geometry (it does not use
the cycle model).

```yaml
generator: perspective
horizon:
  at: 0.55                     # height up the area, 0–1
  weight: 0.3pt
  color: "#000000"
vanishing_points:
  - at: [-0.6, 0.55]           # a point as area fractions, usually off the sheet
    count: 16                  # rays in the fan (≥ 2)
    weight: 0.15pt
    color: "#000000"
  - at: [1.6, 0.55]
    count: 16
    weight: 0.15pt
verticals:
  count: 18                    # evenly spaced true verticals (≥ 2)
  weight: 0.12pt
```

A vanishing point's `at` is a point in area fractions (0 = left/bottom edge,
1 = right/top), so a value below 0 or above 1 puts it off the sheet — where
vanishing points usually sit. An optional `base` (`top`/`bottom`/`left`/`right`)
picks which edge is divided into the fan. Rays are clipped to the pattern area.
Example:
[`09-perspective-2pt.yaml`](examples/09-perspective-2pt.yaml). Preset:
`perspective-2pt-a4`.

### `mandala` — rotationally symmetric templates

A template to draw on: an N-fold scaffold plus motif families that carry the
symmetry. Everything faces up (a vertical axis).

```yaml
generator: mandala
sectors: 12                    # order of symmetry (required, ≥ 2)
center: auto                   # or { x: …, y: … }
outer_radius: 48%s             # auto, a length, or relative
```

The motif families (all optional):

| Family | What it draws |
|---|---|
| `rings` | concentric guide circles, evenly spaced (`count`, weight, color) |
| `spokes` | N radial guides (`inner` clears the centre, weight, color) |
| `rosette` | N circles on the spokes (`at`, `radius`, `mirror`) |
| `petals` | a ring of pointed leaves, each two arcs (`inner`, `outer`, `width`, `mirror`) |
| `beads` | dots on a ring (`at`, `count`, `size`, `rotate`) |
| `scallops` | a wavy ring of arcs (`at`, `count`, `depth`, `inward`) |
| `pinwheel` | small polygons round a ring, twisted (`at`, `size`, `sides`, `count`, `twist`) |
| `polygons` | inscribed regular or star polygons (`radius`, `sides`, `step`, `rotate`, `fill_color`) |

`rosette`, `petals`, `beads`, `scallops` and `pinwheel` each take **one entry or
a list** — layered bands at different radii. `at`, `radius`, `inner`, `outer`,
`width`, `depth` and `size` (for pinwheel) are shares of the outer radius (0–1).

```yaml
petals:
  inner: 0.34
  outer: 0.94
  width: 0.12
  mirror: true
beads:
  - { at: 0.99, count: 36, size: 0.9mm }
  - { at: 0.20, count: 12, size: 1.1mm }
rosette:
  - { at: 0.5, radius: 0.16, mirror: true }
```

Examples: [`10-mandala.yaml`](examples/10-mandala.yaml) and
[`10b-mandala-scallops.yaml`](examples/10b-mandala-scallops.yaml). Preset:
`mandala-a4`.

### `calendar` — a linked, write-on planner

Unlike every generator above, `calendar` does not fill one page — it produces a
whole **linked document**: one PDF of about 400 pages you navigate with the pen.
Tap a date and land on that day; tap a note number and land on that note. Built
for the reMarkable (the links are internal PDF links, which it follows), but it
prints on paper too.

```yaml
generator: calendar
year: 2026
week_start: monday          # or sunday
months:   [January, …]      # 12 names; English if omitted
weekdays: [Mon, Tue, …]     # 7 names; English if omitted
holidays:
  - { date: 2026-12-25, label: Christmas }
year_view:  { weekend_shade: "#f0f2f5", cell_link: day }   # day | month | none
month_view: { weekend_shade: "#f0f2f5", surface: lines }
quarter_view: { cell_link: day }          # opt-in: 4 pages of 3 mini-months
week_view:    { surface: lines, tasks: true }   # opt-in: one page per week
day:
  blocks:                   # an ordered list — reorder, resize, repeat
    - { type: schedule, from: 7, to: 22, height: 55%, surface: lines }
    - { type: todo,     rows: 8,          height: 20% }
    - { type: notes,    height: rest,     surface: grid }
notes: { count: 20, surface: dots }        # blank | lines | dots | grid
```

The page types, each **exactly one page** (if a view is small, use the device's
zoom — nothing scrolls or scales):

- **Index** — a hub of links: the year, the twelve months, the notes.
- **Year** — two half-year tables; a month header jumps to its month, a day cell
  to its day.
- **Month** — a list of every day; the date links to its day page, holidays are
  labelled, weekends shaded.
- **Day** — your ordered `blocks` (a timed `schedule`, a `todo` list, `notes`),
  each with a writing `surface` (`blank` / `lines` / `dots` / `grid`).
- **Quarter** (opt-in via `quarter_view`) — four pages, each three mini-months;
  a month name jumps to its month, a day cell to its day.
- **Week** (opt-in via `week_view`) — one page per week (~53), seven day
  sections in `week_start` order with a writing surface and a tasks column; each
  date jumps to its day page. Weeks that straddle the year edge show the
  outside days without a link.
- **Notes** — a numbered index that links to note pages, and the note pages
  themselves. A large `count` paginates the index over several sheets.

Every page carries a small nav strip (Index · Year · Month · Notes) as
underlined text — a link is just underlined text plus its tap box, to save space
and bytes.

Names come from your definition (English by default), so the calendar adds no
language of its own. Dates are computed from `year`, so the same definition
always gives the same PDF. The optional header is constant on every page — set
`header: { center: "{year}", right: "your name" }` for the year and a
personalization (no page numbers). It is **PDF only**: on PNG the run is refused,
because links and text cannot live in a PNG.

Preset: `calendar-a4` (`ctrlgrid show calendar-a4`), which turns on every view.
The only thing not yet built is importing holidays from a *file* — an inline
list works.

---

## 13. E-ink and devices

Instead of a paper format, target an e-ink screen. The device's physical size
comes from its pixel count divided by its density, so the template fits the
screen exactly.

```yaml
page:
  device: remarkable-paper-pro
```

Run `ctrlgrid devices` to list profiles and where their figures come from. Two
ship today: the reMarkable Paper Pro (owner-verified, a colour device) and the
reMarkable 2 (manufacturer-specified, monochrome).

With a device active:

- **`px`** resolves against the density, so you can size things in pixels.
- **`snap: pixel`** rounds every step to whole pixels for a crisp render, and
  the exact resulting size is reported.
- **The media check** runs automatically: it warns when a line is too thin to
  survive the screen's resolution, or when two colours collapse to the same
  grey on a monochrome device. `--strict` turns every such warning into an
  error (good for a CI check of a preset set).

The media check runs whatever the output format — a PDF built for a device is
checked just like a PNG.

---

## 14. N-up imposition

Print several small pages onto one large sheet, **without scaling**:

```bash
ctrlgrid -d card.yaml --format a6 --pages 4 --nup 2x2 --nup-sheet a4 -o sheet.pdf
```

`--nup CxR` lays a C×R grid of pages at 100 %. If the small pages do not fit the
big sheet at full size, the run refuses (it never shrinks them — that would break
the promise). `--crop-marks` adds trim marks. The cover sheet is exempt from
imposition.

---

## 15. Output formats

- **PDF** — the reference output: vector, exact `MediaBox`, embedded and subset
  fonts. Same input produces byte-identical output every run (fixed creation
  date, content-derived document id), so a definition under version control has a
  stable PDF.
- **PNG** — one file per page at the device's exact pixel resolution. Chosen by a
  `.png` extension on `-o`. The PNG writer cannot draw text (the standard fonts
  have no glyph file), so a run that needs text on PNG is refused by name, with
  the way out (name a font file, drop the text, or output PDF).

---

## 16. Batch output: name lists

Give a list of names, one per line, and get one sheet per name with `{name}`
filled in:

```bash
ctrlgrid millimeter-a4 --names class3b.txt -o sheets.pdf
```

```yaml
header:
  height: 8mm
  left: "{name}"
```

With `--names` and no `--pages`, the list leads: one sheet per entry. With a
count as well, the count leads and entries repeat or are cut (a notice tells you
when a list was cut, rather than cutting it silently). Each named page also gets
a PDF bookmark.

---

## 17. Fonts

Text (header/footer, labels, the stamp, form titles) uses one of three logical
families: `serif`, `sans`, `mono`. These map to the standard PDF fonts, whose
metrics are fixed, so geometry is identical on every machine.

For characters outside Latin-1 (`ł`, `ğ`, `ő`), name a font file:

```yaml
header:
  font: { file: fonts/Inter.ttf, size: 10pt }
```

The file is embedded and subset (only the glyphs used travel with the PDF). Its
embedding licence is checked, not assumed: a font whose `fsType` forbids
embedding aborts the run and is named — never quietly swapped for another.

---

## 18. Presets

Presets are ordinary definition files that ship with the tool — they are also
the documentation. There is one for every generator:

```
dots-5mm            grid-a4             mandala-a4          maze-medium
millimeter-a4       perspective-2pt-a4  phone-log-a5        polar-a4
staves-treble-a4    tiling-hex-a4
```

```bash
ctrlgrid presets                       # list them
ctrlgrid show millimeter-a4            # print one
ctrlgrid show millimeter-a4 > mine.yaml   # copy and bend it
ctrlgrid millimeter-a4 --format a5 -o out.pdf   # run one with overrides
```

---

## 19. Printing accurately

The whole point is scale, so a printer that rescales defeats it. Two habits:

1. **Print at 100 %, not "fit to page".** Most viewers default to fitting the
   page and quietly scale to about 96 %. Choose "Actual size" / "100 %". Run with
   `--cover` and measure the 50 mm square and 100 mm rule with a ruler — if they
   are wrong, the driver scaled.
2. **Mind thin lines and character coverage.** On a home printer a 0.1 pt line is
   fine; on an e-ink screen it may vanish — the media check warns. Without a font
   file, `ä ö ü ß é à ñ ç` work but `ł ğ ő` do not; name a font file for those.

The example gallery in [`../examples/`](examples/) shows one rendered sheet per
generator, each with its definition and PDF.

---

## 20. Errors and validation

Ctrl+Grid validates everything **before** writing page one, and either aborts
completely or builds completely — it never leaves a half-written file. `ctrlgrid
check <file>` runs exactly that validation and writes nothing.

The design principle: a PDF that is *almost* right is the worst outcome, so the
tool fails loudly rather than guessing. An error names the field, the value and,
where it can, the fix in your own units. A feature named in the spec but not yet
built refuses with a message naming what is missing — never a silently ignored
key.

---

## Appendix A — units

| Unit | Kind | Where |
|---|---|---|
| `mm` `cm` `in` `pt` | length | everywhere |
| `%w` `%h` `%s` | length, relative to the pattern area (width / height / shorter side) | most length fields |
| `px` | length, device pixels | only with a device profile |
| `deg` | angle | angles |
| `sp` | staff space | `staves` |
| `dpi` | density | device profiles only |

## Appendix B — paper formats

`a3`, `a4`, `a5`, `a6`, `letter`, `legal`, `tabloid`, or an exact size such as
`210x99mm` or `8.5x11in`. Or a device (§13) instead of a format.

## Appendix C — command-line flags

| Flag | Meaning |
|---|---|
| `-d <file>` | build from a definition file |
| `-o <file>` | output path; the extension picks PDF or PNG |
| `--pages <n>` | number of numbered sheets |
| `--names <file>` | one sheet per name; fills `{name}` |
| `--format <name>` | paper format |
| `--device <id>` | e-ink device profile (instead of a format) |
| `--orientation <portrait\|landscape>` | orientation |
| `--stamp <text>` | full-page stamp |
| `--cover` | add the calibration cover sheet |
| `--embed-def` | embed the definition's source in the PDF |
| `--seed <n>` | seed for procedural generators (`maze`) |
| `--strict` | turn media warnings into errors |
| `--nup <CxR>` | N-up imposition, never scaled |
| `--nup-sheet <format>` | the sheet format for imposition |
| `--crop-marks` | trim marks with `--nup` |
| `--force` | overwrite an existing output file |
| `--quiet` | report only the output path |

Switch flags (`--cover`, `--strict`, `--embed-def`, `--crop-marks`) only turn
something on; the definition decides when the flag is absent. All flags beat the
definition.

## Appendix D — generators at a glance

| Generator | Produces | Key required field |
|---|---|---|
| `lines` | squared, ruled, isometric, log/semi-log | `families` |
| `dots` | dot grids with emphasis | `grid` |
| `grid` | labelled cell blocks | `cells` |
| `polar` | targets, score discs, polar paper | — (rings/spokes) |
| `tiling` | hex/tri/square/rhombus/octagon nets | `shape`, `size` |
| `maze` | rectangular mazes, optional solutions | `cells` |
| `form` | fillable forms | `rows` |
| `staves` | music staves, guitar tab, clefs | `count` |
| `perspective` | 1–3 point vanishing-point grids | — (horizon/points) |
| `mandala` | rotationally symmetric templates | `sectors` |
| `calendar` | a linked, write-on planner PDF (many pages) | `year` |
