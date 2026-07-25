# Ctrl+Grid — orientation

## What this is

A CLI tool that generates **dimensionally accurate PDF templates**: grid paper,
ruled paper, dot grids, staff paper, mazes, polar targets, tilings, fillable
forms, perspective grids, mandalas — and a **linked, write-on calendar** — for
paper formats and for e-ink devices.

**The one promise:** what says 5 mm measures 5 mm on the printout. No scaling,
no "fit to page", no stretching a grid so it comes out even.

## Current state — read this first

**Every milestone (M1–M9) is complete**, and so are the four post-M9 features the
handovers kept circling back to — all ten blades of § 7, device profiles, `px`,
the media check, `snap: pixel`, N-up imposition, the PNG writer, `perspective`
and `mandala` (M8, § 7.11) and the `staves` clefs (M9, § 15.3). Since M9, four
things landed on the handle side, each small and each in the spec: the
**interactive preset browser** (no-args, § 11.2), the **general relative measure**
`%w`/`%h`/`%s` (§ 8.11), the cover sheet's **stroke-weight ladder** (§ 8.8), and
**`pattern.align`** — anchor the grid at a chosen corner (§ 8.5). Since then,
`--embed-def` — **the PDF carries its own source** as a file attachment (§ 8.8,
was § 15 open question 5) — open question 3 closed (reportlab is BSD-3-Clause,
verified), and **`mandala` grew five motif families** — `petals`, `beads`,
`scallops`, `pinwheel` and a single-or-list `rosette` (§ 7.11). **The newest and
largest addition is the `calendar` generator (§ 7.12)** — a linked, write-on
planner PDF and the first *document generator* (owns pages, not one pattern
area). It brought two clean new mechanisms (a `link` writer capability like
`outline`, and a document-mode page loop in `pages.py`) and is **done through all
its views** (title, contents, full-year overview of twelve mini-months, half-year
1 & 2, months, opt-in weeks, days, notes) — and holidays now import from a file
too (`holidays_file`, YAML or `.ics`, § 7.12) — the calendar is complete. Only
M5's two device edges are otherwise left (see *Not done*).
0.1.0 is the version in the code; nothing has been released, because releasing
needs a human *and* the user has chosen to defer PyPI for now (see *Not done*).

```bash
uv sync --extra dev && uv run pytest && uv run ruff check .
```

1141 tests, all green, ruff clean. Sixty-odd commits on `main`, linear history,
pushed to **[github.com/DocAtPrompt/ctrlgrid](https://github.com/DocAtPrompt/ctrlgrid)**
(public); CI runs green there on Linux (3.11–3.13), macOS and Windows. Seventeen
presets — one per blade (`lines`, `dots`, `polar`, `form`, `maze`,
`perspective`, `mandala`, `staves`, `grid`, `tiling`, `net`), the two documents
(`calendar-a4`, `notebook-a4`), and four papers that are all `lines` with
different cycles (`calligraphy-a4`, `seyes-a4`, `mizige-a4`,
`knitting-chart-a4`) — and a
rendered
**example gallery** in [`examples/`](../examples/) — one A4 sheet per generator plus
a multi-page maze booklet, a cover sheet and the calendar, each an ordinary
definition, its PDF and a PNG preview, guarded by `test_every_example_validates`.
The calendar example (`12-calendar-year.yaml`) is the one without a committed
PDF: 405 pages and 1.6 MB, rebuilt in about a second, and the file's own comment
says so.

### Done

| Milestone | State |
|---|---|
| **M1** — the vertical slice | complete; all seven acceptance criteria of § 14 met except the PyPI release, which needs a human (see *Not done* below) |
| **M2** geometry | `count`, `extent`, `remainder`, `snap`, `duplex` |
| **M2** name lists | `--names`, both modes, `{name}`, PDF outline |
| **M2** frame furniture | `border`, `background`, `hole_marks`, `stamp` |
| **M2** cover sheet | `--cover` / `pages.cover`, calibration figures and settings summary |
| **M2** fonts stage 2 | `font: {file: …}`, embedded and subset, with the `fsType` check |
| **M2** dash styles | `style: dashed \| dotted`, `base_dash`, `dash` |
| **M2** free page sizes | `format: 210x99mm`, `format: 8.5x11in` |
| **M2** images in bands | `left: {image: …, height: …}`, PNG, never cropped |
| **M4** `form` | rows then columns, one nesting level, absolute ruling |
| **M4** `maze` | three algorithms, `min_path_factor`, four solution modes |
| **M4** `tiling` | hex/tri/square/rhombus/octagon, edge net drawn once |
| **M4** `staves` | grouped systems, `sp` unit, `stave_space`/`stave_height` |
| **M4** `law: log10` | decade positions, fixed block, placed by `remainder` |
| **M4** `grid` | count-driven block, square cells, § 7.10 labels, fills |
| **M4** `dots` | two crossed cycles, `combine`, colour with a named axis |
| **M3** — `polar` | rings, spokes, segment and ring labels, counting patterns (§ 7.10) |
| **M5** device profiles | `page.device`, physical size from pixels ÷ density (§ 9.2) |
| **M5** the `px` unit | resolves against the device density; refused on paper (§ 8.3.1) |
| **M5** media check | § 12.1 resolution/colour findings, `--strict`, round-to-zero errors |
| **M5** `snap: pixel` | every step to whole pixels, exact size reported (§ 8.3.1) |
| **M6** N-up | `--nup CxR` at 100 %, never scaled, crop marks, cover exempt (§ 14) |
| **M7** PNG writer | raster at exact device resolution, one file per page, text via caps (§ 10.4) |
| **M8** `perspective` | horizon + 1–3 vanishing-point fans, equal base division, Liang–Barsky clip, `verticals` (§ 7.11) |
| **M8** `mandala` | sectors/rings scaffold, rosette of circles (`mirror`), inscribed regular / star polygons, on shared `polar_geometry` (§ 7.11) |
| post-M9 `mandala` motifs | five more families: `petals` (a leaf = two arcs, `Arc` only), `beads` (dots on a ring — introduces `Dot` to the blade, § 7.11 mark line extended), `scallops` (a wavy ring of arcs, `inward` for cusps), `pinwheel` (twisted small polygons on a ring), and `rosette` widened to **single-or-list**; all five ring families take single-or-list (layered bands). `check`/`_max_reach`/`describe` iterate the rings; two gallery entries (`10`, `10b`) show them (§ 7.11) |
| **M9** `staves` clefs | `treble/bass/alto/tenor` as `Text` in a bundled, subset music font (Bravura, OFL→TrueType), SMuFL placement, 5-line only (§ 15.3) |
| **M5** relative measure | `%w`/`%h`/`%s` as a fraction of the pattern area, resolved in seam 1 like `px`, `RelativeLengthField` opt-in across the blades (§ 8.11) |
| post-M9 interactive | `ctrlgrid` with no args → preset browser (preset → pages → output), TTY-guarded, help otherwise (§ 11.2) |
| post-M9 weight ladder | cover sheet's rising stroke-weight samples, with the device pixel width where a device is active (§ 8.8) |
| post-M9 `pattern.align` | anchor at `bottom-left` (default) / `top-left` / … — a `mirror_y` reflection re-anchors the cycle so the incomplete block moves corners (§ 8.5) |
| post-M9 `--embed-def` | the PDF carries its own source: the def's exact bytes as an `EmbeddedFile` in the catalog's `/Names /EmbeddedFiles` tree, built by hand (reportlab has no filespec support), deterministic, PDF-only — PNG refuses it by name via the `attachment` capability (§ 8.8, § 10.2) |
| post-M9 examples | rendered gallery in `examples/`, one per generator + multi-page + cover, `test_every_example_validates` guards it |
| post-M9 `calendar` | a linked, write-on planner PDF (§ 7) — the first **document generator**: it owns heterogeneous, cross-linked pages (Index, Year two-table, Month day-list, configurable Day blocks, paginated Notes-index, Notes) instead of one pattern area. Two new mechanisms modelled on `outline`: a **`link` capability** (writer method + capability, PDF-only, PNG refused; links drawn as underlined Text) and a **document-mode page loop** in `pages.py`. Dates deterministic from the year, names from the def (English default), one-page-per-view fit-or-refuse. Pages: an opt-in **title** page (full-sheet colour via a new `DocumentPage.background` (+ an optional full-sheet `background_image`, `cover`/`contain`, transparency shows the colour), optional `logo`, and independent opt-in `show_header`/`show_footer` (replacing `plain`)), a **contents** hub, a **full-year overview** (twelve mini-months, three across, numbers as links, no cell boxes), **half-year 1 & 2** tables (short months' columns end — no empty cells), months, days, opt-in **weeks** (`week_start`-aligned), and notes. `{year}` header placeholder. Holidays come inline **or from a file** (`holidays_file`: a YAML list or a concrete-dated `.ics`, resolved against `base_dir` like `logo`, filtered to the year, merged with inline — inline wins on a date clash; `.ics` recurring/timed events skipped and counted; source named in the run report). **§ 7.12 is complete.** |
| post-M9 `ruler` | an edge scale as frame furniture (§ 8.12): `ruler: {edges: [bottom, left], unit: cm}`. Zero at the *pattern area's* origin, so the numbers agree with the grid; ticks grow outward into the margin and reserve nothing, so switching it on moves no grid line (§ 8.1's rule for `border`, restated). Physical edges, not `inner`/`outer`. `unit` says what the numbers mean, three lengths say where the ticks are, each a whole multiple of the one below. The ladder arithmetic lives once in `ruler.py` (drawing *and* pre-flight use it); the number's height and width are asked of the writer, never guessed. Four refusals before page one; PNG refused by the existing capability path. Example `13-ruler-edge`, decision 47 |
| post-M9 slanted `lines` | `direction: 55deg` (§ 7.1, decision 48) — spaced *perpendicular*, clipped, and anchored so that **line 0 goes through the pattern area's origin** with an unlimited family growing both ways. `0deg`/`90deg` reproduce `horizontal`/`vertical` mark for mark, which is the test that keeps it one rule. Downwards reads the cycle backwards (`Cycle.positions_between`), the perpendicular's sign points into the area, and negative perpendicular coordinates are legal. A slanted family reports **no** periodic axis, so § 7.1's "no snapping" needs no new machinery; `governing`/`log10` on one are refused. Liang–Barsky moved to `ctrlgrid/clip.py`, shared with `perspective`. Preset `calligraphy-a4`, example `14-calligraphy-italic` |
| post-M9 `net` | the eleventh blade (§ 7.14, decision 51): a `tray` or a `tuck_top` box from its **inner** dimensions, cut lines solid, creases dashed, glue tabs computed, centred and **refused rather than scaled**. The mechanism: a style produces **panels** and one rule makes the marks — an edge two panels share is a fold, an edge only one has is a cut — so a new style is a panel list, never a traced outline, and the match is exact because positions are integer µm. Every flap must span its attachment edge (that is what makes it exact). Two stated conventions: inner dimensions, and one thickness rule (a panel closing *over* a layer is widened, a flap sliding *inside* is shortened); `thickness: 0` gives the ideal net, and a test says so. Preset `box-tuck-a4`, example `16-net-tray` |
| post-M9 `notebook` | the **second document generator**, and the first that composes blades (§ 7.13, decision 50): sections, each filled by an ordinary generator, with a linked contents page, opt-in dividers and a cover. The seam: a `DocumentPage` may carry a `Fill` (generator name + validated config) instead of marks, and **the handle calls the blade** — `pages.document_page_marks` is the one function that says what is on a page, used by the writer, the capability pre-flight and the media check. A section is a definition in miniature, validated by that blade's own `config_model` with the loader's context (so `px`/`%w` resolve there too). Document bands are now laid out **per page**, so `{page}` counts and a per-page `{section}` names the section; `calendar-a4` stayed byte-identical. `page_layout.Page` extracted from `calendar_layout` and shared. Preset `notebook-a4`, example `15-notebook` |
| post-M9 band colour | a header/footer `Band` takes `background` (a full-width strip, band height only) and `text_color`, both default off — drawn in `layout_band` so both the blade and document paths get them; resolves the title-page contrast (§ 8.9) |
| pulled forward into M1 | format table, presets, `check`, overwrite protection, placeholders — the M1 acceptance criteria needed them |

### Not done

**Two small edges of M5 remain**, and each names why:

- **`quirks` ships empty** (decision 31). § 9.2 provides the field with a Boox
  dead-row example, but no shipped profile is a Boox and inventing a dead-row
  pattern for a device nobody here can test is the guessed number § 9.2 warns
  against. Modelled and carried, waiting for a verified contribution.
- The **rM2 numbers** now cite reMarkable's own comparison page (1872×1404 px,
  226 ppi, monochrome) and match it exactly — a primary source, no longer a
  guess — but the device is still not owner-checked the way the Paper Pro is
  (§ 9.2), so its profile says `manufacturer-specified`, not `owner-verified`.
  (The Paper Pro is fully settled: dimensions *and* colour owner-confirmed,
  `color: color` since 2026-07.) The only device gap left is an on-device rM2
  check and the empty `quirks`.

The **general relative measure** (§ 8.11) — the other M5 edge the handovers kept
naming — is now **built**: `%w`/`%h`/`%s` (width, height, shorter side of the
pattern area) resolve in seam 1 against the raw pattern area, the same way `px`
resolves against a device density, so one definition fills paper and a 3:4 e-ink
slate alike. Opted into per field via `RelativeLengthField`; refused in margins,
bands, weights and sizes.

**Every milestone proper is now done — M8 shipped `perspective` and `mandala`**
(§ 7.11). Both compute their own law instead of a cycle (a generator may, § 5.3):
`perspective` divides a base edge equally and clips its rays with Liang–Barsky,
`mandala` counts sectors and rings on the shared `polar_geometry` (extracted
from M3's polar so the two blades share one arithmetic, not two that drift).
The `staves` clef conflict (§ 7.3 wanted stored vector paths, § 6 fixes the
vocabulary at six primitives with no curve path) is **resolved and built**: § 15.3
decided a clef is a `Text` mark in an embedded, subset music font — keeping the
six primitives and § 15.2 intact, self-contained through embedding — and **M9
shipped it**. The bundled font is Bravura (OFL) subset to four glyphs, converted
CFF→TrueType (reportlab embeds no CFF), renamed off its reserved name; placement
is pure SMuFL (`CLEF_FONT`, `CLEFS` in `staves.py`). Three things M3 built are
still there to reuse for any new blade: `labels.py` (§ 7.10) is what `grid` and
`tiling` label with, `generators/common.py` holds the cycle and dash fields
every family needs, and `check()` is where a blade refuses what only the pattern
area can disprove.

**The remote is live and `main` is pushed** (public, CI green on Linux/macOS/
Windows). Install today with `uvx --from git+https://github.com/DocAtPrompt/ctrlgrid.git
ctrlgrid …` (README has the pip/clone forms) — that is verified working, font and
presets included.

**PyPI is deferred by the user's own choice** ("vorerst verzichten"), so `uvx
ctrlgrid` (the bare PyPI form) does not work yet and that is intended, not a gap.
When PyPI is wanted, two things: a human sets up trusted publishing
(https://pypi.org/manage/account/publishing/ for `DocAtPrompt/ctrlgrid`, workflow
`release.yml`, environment `pypi` — a pypi.org login), then a tag `v*` is pushed
to trigger [`.github/workflows/release.yml`](../.github/workflows/release.yml). An
annotated **`v0.1.0` exists locally** but now sits at the M9 commit, ~15 commits
behind HEAD — re-tag at the release commit before pushing. Do **not** run
`git push --tags`/`--follow-tags` casually: it would push that tag and fire the
release. Plain `git push origin main` is safe.

### Deferred features name their milestone

Anything specified but not built refuses with a message naming the milestone,
never silently. `grep -rn "milestone M" ctrlgrid/` lists every one. This is
deliberate: § 5.1 calls a PDF that is *almost* right the worst failure class
there is, so `border:` must never have read as an unknown key while it was
unbuilt, and `snap:` must never have been quietly ignored.

## Read this before writing anything

**The specification is the source of truth, and it is unusually complete** —
~2330 lines covering the architecture, all ten generators, the page model,
validation, milestones and the decisions that were explicitly rejected and why.

Most questions that come up while implementing are already answered there, with
reasoning. Several decisions look arbitrary and are not:

- Why margins are named `inner`/`outer` and not `left`/`right` (§ 8.1)
- Why `snap: none` is the default even though it looks worse (§ 8.3)
- Why N-up refuses to scale, unlike every comparable tool (§ 14, M6)
- Why the mark vocabulary has exactly six primitives (§ 6)
- Why `ruamel.yaml` and not `PyYAML` (§ 13)

If you think a decision is wrong, say so and name the section. Do not silently
work around it.

**Where the specification was genuinely silent**, the resolution is recorded in
[`implementation-decisions.md`](implementation-decisions.md) —
forty-five of them so far, each with the section it belongs to and the
reasoning. Read it before changing a default; several look arbitrary and are not.

## Language split

- **Code, DSL keys, error messages, preset names, README, comments: English.**
- **The specification: German.** It is an internal design document.
- Do not add a translation layer. Form labels like "Ja"/"Nein" come from the
  user's definition file, never from the tool (§ 7.8).

## The architecture as built

A pocket knife: one handle, several blades. The **handle** owns page format,
margins, pattern area, frame, header, footer, stamp, hole marks, the page loop
and output. A **blade** (generator) only produces marks in local coordinates
and knows nothing about margins.

| Module | Holds |
|---|---|
| `cli.py` | `typer` commands, flag→override map, writer choice by `-o` extension, the no-args interactive browser (§ 11.2) |
| `units.py` | `Length`/`Angle`; parsing to exact int µm via `Decimal` |
| `errors.py` | `DefinitionError` with field path and source line |
| `marks.py` | the six primitives, `Layer`, `Point`, `Area`, `translate`, `mirror_x`, `mirror_y` (§ 8.5) |
| `cycles.py` | `Cycle`, drift-free positions, effective period |
| `axes.py` | `AxisPeriod` — what the handle needs from a blade for § 8.3/§ 8.5 |
| `model.py` | pydantic sections; `Section` base with `extra="forbid"` + `deferred` |
| `loader.py` | YAML → `Document`; formats, presets, devices, name lists |
| `pages.py` | `Geometry`, page loop, placeholders, `preflight`, `build`, `snap: pixel` |
| `frame.py` | header/footer layout, border, background, hole marks, the edge ruler's marks and its fit check, stamp |
| `labels.py` | counting patterns `n`/`a`/`A`, explicit lists (§ 7.10) |
| `clip.py` | Liang–Barsky in exact rationals, shared by `perspective` and slanted `lines` |
| `ruler.py` | the edge scale's ladder: tick positions, exact labels, the strip it needs (§ 8.12) |
| `images.py` | PNG sources: signature check, pixel size, aspect (§ 5.2, § 13) |
| `media.py` | the media check: resolution and colour findings (§ 12.1), for blades **and** documents — a document's pages are all walked, one mark kept per distinct weight and colour (decision 49) |
| `impose.py` | N-up layout, the 100 % fit check, crop marks (§ 14) |
| `fonts.py` | font files: `fsType` licence check, version, coverage (§ 10.3) |
| `cover.py` | the cover sheet: calibration figures, the stroke-weight ladder, settings summary (§ 8.8) |
| `generators/` | registry, `common.py` (cycle + dash fields), `polar_geometry.py` (shared by `polar` + `mandala`), the ten blades, and the `calendar` document generator (`calendar.py` + `calendar_layout.py`) |
| `document.py` | the document-generator seam (§ 7): `DocumentPage`, `Link`, `Fill`, the `DocumentGenerator` protocol — a generator that owns pages, not one pattern area |
| `generators/page_layout.py` | the shared page builder both documents draw on (§ 7.13) |
| `generators/net_geometry.py` | panels in, cuts and creases out — the shared-edge rule (§ 7.14) |
| `generators/net_styles.py` | the box styles: `tray` and `tuck_top`, as panel lists (§ 7.14) |
| `writers/` | seam 3 protocols, `pdf.py` (reportlab) and `png.py` (Pillow) |

### The three seams (§ 3.6)

1. **Definition → model.** `loader.load()`. After it there are no unit strings
   left in the core.
2. **Generator → marks.** `generate(cfg, area, page, q) -> Iterator[Mark]`,
   plus the queries `is_page_invariant`, `describe`, `periodic_axes`, `check`,
   and the declaration `supports_snap`.
3. **Marks → writer.** Bidirectional: marks in, font metrics out — plus
   `capabilities()`, the set of mark kinds the writer can render (§ 10.2).

`sheets()` came from M3's successor, `maze` (§ 7.5): a blade may say that one
*item* needs more than one sheet, and the handle does the doubling, the
numbering and the mirroring. Everything about pages stays on the handle side.

**Seam 3 stayed a stub until M7.** `capabilities()` existed from M1 but nothing
consumed it while PDF was the only writer. The PNG writer is the first that
does *less* (no text — the standard fonts have metrics but no file), so the
pre-flight now measures with a metrics **oracle** (a throwaway `PdfWriter`,
because metrics are fixed data, not rendering) and refuses, by name, whatever
the real writer's `capabilities()` cannot draw — found by sampling one page's
marks, not by reading the config (decisions 38–39). The writer is chosen by the
`-o` extension (`.png` → `png.py`), and the media check (§ 12.1) is
output-independent, so PNG inherits it.

**Seam 2 has grown four queries and `generate` has never changed.** When `snap`
and `remainder` needed blade knowledge, the handle got a question to ask
(`periodic_axes`) rather than the blade getting the pattern block. § 8.3 says
the *pattern area* shrinks, so shrinking it is the handle's job. Keep new
handle features on that side of the line: eight of the ten blades would have to
reject a pattern block they were handed.

`check(cfg, area, q)` came from M3 and is the other half of that rule: a blade
may refuse things only the pattern area can disprove, but it refuses them in
the pre-flight, never while pages are being written (§ 12 point 13).

## Non-negotiables

1. `reportlab` only in `ctrlgrid/writers/pdf.py`. `tests/test_architecture.py`
   enforces it and predates the module.
2. Positions as integer micrometres, never accumulated floats. Stroke widths
   and opacity stay float. `Length` carries `um`, `mm` **and** the raw text the
   user wrote, because § 12 requires errors in the user's own units.
3. Generators `yield` marks, they do not build lists.
4. Validate everything before writing page one — `preflight` does this, and
   `check` runs exactly it. Abort completely or build completely.
5. Same input → same bytes. `invariant=1` on the canvas, `Decimal` with
   ties-away-from-zero, outline keys from the page index, no `hash()`, no
   wall-clock time. **Test it whenever you add anything to the writer.**
6. Fail loudly. An error message that does not let the user act is a bug — § 12
   calls error messages "the face of the tool", and means it.

## Working style that has held up

- **Test first, watch it fail, then implement.** Every module here was built
  that way, and it caught real bugs — including two of my own test bugs where
  the loader refused a duplicate `pattern:` key I had spliced in.
- **Comments carry the *why*, with the section number.** The code is dense with
  them because the specification's reasoning is the expensive part.
- **One coherent block per commit**, message explaining the decisions rather
  than the diff. `git log` is where the open-question resolutions live.
- Verify against a real PDF, not just unit tests — `tests/pdfread.py` reads
  geometry back out.

## Where to start

The architecture has held through all nine milestones and every post-M9 feature:
`generate(cfg, area, page, q)` has never changed signature, and every feature
that needed blade knowledge became a *query the handle asks* rather than geometry
pushed into the blade. Keep that line. When a new feature tempts you to hand a
blade the page, the margins, or the device, look first for the question the
handle could ask instead — that is how `periodic_axes`, `check`, `sheets`,
`supports_snap` and `capabilities` all came to be. The recent features held it
too and are worth studying as the pattern: the relative measure resolves in the
*loader's* validation context like `px` (no blade touched), and `pattern.align`
reflects finished marks in `pages.py` with `mirror_y` (the blade never learns
which corner it anchored to, § 3.3).

**Nothing proper is left.** What remains is small, and each names its reason in
*Not done* above: M5's empty `quirks` and the two unverified device figures, plus
the deferred PyPI release (the user's choice). If you add a blade or option, the
recipe is unchanged: for a blade, a registry entry in `generators/__init__.py`
with a `config_model` and the seam-2 methods; for either, a failing test first
(or, when a design is genuinely uncertain, validate on a real sheet then codify —
`pattern.align` was built that way), the *why* in the comment with its § number,
one coherent commit, and a real rendered sheet read back — not just unit tests.
Update the spec and CLAUDE.md in the same breath, so the next instance inherits
the truth; and note the **elements-of-style / verify-before-completion habits**
this project runs on — claims are backed by a command's output, never asserted.

## What to do next

A handover written at the end of the 2026-07-25 session names the order:
[`docs/superpowers/plans/2026-07-25-next-steps-handover.md`](superpowers/plans/2026-07-25-next-steps-handover.md).
**Phase 0 and all of phase 1 (1a–1d) are done.**

Phase 0: the README has its own calendar
section, `examples/12-calendar-year.yaml` is the worked example (405 pages, two
previews, no committed PDF), and the handbook's calendar section now covers
`holidays_file`, marked-day colours, `legend`, the title page's image and bands,
`day_numbers`, `half_hours` and note pads — with the band colours documented
where they belong, in the header/footer section. The gallery itself needed no
rebuild: every committed example PDF was regenerated and compared byte for byte,
and all thirteen matched (the maze booklet with its documented `--seed 4711`).
Phase 1a is built: `ruler:` (§ 8.12, decision 47), designed with the user first
— [`docs/superpowers/specs/2026-07-25-edge-ruler-design.md`](superpowers/specs/2026-07-25-edge-ruler-design.md)
and its plan — and the gallery's `13-ruler-edge` is the sheet you can hold a real
ruler against. **Phase 1b is built too:** slanted `lines` families (§ 7.1,
decision 48, its own design and plan under `docs/superpowers/`), with the
`calligraphy-a4` preset and `14-calligraphy-italic`. The nib-width unit of § 15
question 4 was deliberately left out of it — the angle is what unlocks
calligraphy guides *and* origami pre-creasing; the unit is a convenience on top,
and § 15 says that class waits on real use. 1c shipped `seyes-a4`, `mizige-a4` and `knitting-chart-a4` (Genkō yōshi was
dropped with its reason: its furigana strip needs interrupted rules, and § 2
rules out a drawing language), and 1d shipped `notebook`. **Phase 2b is built too:** `net` (§ 7.14, decision 51), with `box-tuck-a4` and
`16-net-tray`. What is left of the handover is the small rest of phase 2: fold
notation as a *documented convention* (2a — the dash machinery already draws
valley and mountain folds; § 7.14 names them, presets could show them) and
pre-creasing grids for tessellations (2c — `grid` plus the diagonals of 1b,
mostly a preset).
A specific paper aeroplane was considered and **refused**: it is a drawing, not
a structure, and § 2 rules out a drawing language.

## Open questions

Two of § 15's six are now settled since the last handover. **Question 3 closed**
— reportlab 5.0.0 is BSD-3-Clause, verified against the shipped licence text and
package metadata (2026-07-24), permissive-compatible with ctrlgrid's MIT and
nothing to do. **Question 5 is built** — `--embed-def` / `pages.embed_def`
embeds the def as a PDF attachment (§ 8.8); only the original *suspicion* it
carried (how viewers and sync services treat attachments) is left, and that is
for practice to answer, not the code.

The reMarkable 2 figures are now backed by reMarkable's official comparison page
(primary source, matching exactly) — only an on-device check is still missing,
the way the Paper Pro has one. (The Paper Pro colour question is resolved too:
owner-confirmed a colour device, § 9.2.) If you are tempted to guess at a
number, don't — that is exactly the failure mode `source`/`verified` exists to
prevent. The seventh — the `staves` clef — is answered in § 15.3
(embedded music font, built in M9), and it settled part of open question 2: for
the music case, a font *is* shipped. What remains are genuine
*decide-after-experience* calls, not gaps: whether a font must be shipped for
non-Latin-1 names (q2), extra domain units like nib widths / `lpi` / rastral
sizes (q4), and the short-edge duplex flip (q6) — each cheap, each waiting on
real use rather than a design answer.
