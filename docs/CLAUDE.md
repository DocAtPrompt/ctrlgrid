# Ctrl+Grid — orientation

## What this is

A CLI tool that generates **dimensionally accurate PDF templates**: grid paper,
ruled paper, dot grids, staff paper, mazes, polar targets, tilings, fillable
forms, perspective grids, mandalas — and a **linked, write-on calendar** — for
paper formats and for e-ink devices.

**The one promise:** what says 5 mm measures 5 mm on the printout. No scaling,
no "fit to page", no stretching a grid so it comes out even.

## Current state — read this first

**Everything the specification describes is built** (2026-07-26). All eleven
blades of § 7 — `lines`, `dots`, `grid`, `polar`, `tiling`, `maze`, `form`,
`staves`, `perspective`, `mandala`, `net` — plus the two **document
generators**, `calendar` (§ 7.12) and `notebook` (§ 7.13), which own their pages
instead of one pattern area. The handle carries the whole page model: margins,
bands, border, background, hole marks, stamp, the edge ruler (§ 8.12), the
calibration cover, N-up, device profiles with `px` and `snap: pixel`, the media
check, relative measures, embedded fonts, `--embed-def` and
`--skip-unsupported`. The table below says which milestone each piece came from
and what it decided; *Not done* says what is left, and it is short.

Nothing refuses with "a later milestone" any more — that mechanism is still
there (`Section.deferred`, `loader.DEFERRED_KEYS`) and currently empty, which is
worth knowing when the next unbuilt key arrives.

**0.11.1** is the version in the code (2026-07-26) — 0.11.0 plus the PyPI
metadata it should have shipped with (see *Not done*); nothing about the tool
itself changed. 0.9.0 said the features were
complete; 0.10.0 said they had been **audited against a first user**; 0.11.0 adds
what that audit's last question turned up — every blade's geometry read back out
of a finished PDF (`tests/test_geometry_readback.py`), a glyph check on generator
text, and the two DSL keys a non-English calendar needs (`words:` and `font:` on
a document). It is a minor and not a patch because a definition with Polish month
names built at 0.10.0 and is refused now: silently losing a character was the
bug, and refusing it is the fix. What that audit found is in the
five commits before this one and summarised under *The release-readiness pass*
below; the short version is that the core promises — dimensional accuracy and
byte-identical output — held under measurement, and the edges did not.

The only thing between here and 1.0.0 is still *use*: nobody outside has written
a definition, and nobody has yet cut a net out and folded it. 1.0.0 is a promise
about the **DSL**, and it should wait until that promise has been checked against
paper by someone other than the test suite.

The version lives in **one** place, `ctrlgrid/__init__.py`; `pyproject.toml`
reads it dynamically and the release workflow compares the git tag against it.
It is also in every PDF's `/Creator` and `/Producer`, so **bumping it makes every
committed gallery PDF stale** — rebuild them in the same commit, and the cover
sheet's preview with them, since that sheet prints the version.

```bash
uv sync --extra dev && uv run pytest && uv run ruff check .
```

1231 tests, all green, ruff clean, linear history on
**[github.com/DocAtPrompt/ctrlgrid](https://github.com/DocAtPrompt/ctrlgrid)**
(public); CI runs green there on Linux (3.11–3.13), macOS and Windows. Nineteen
presets — twelve that show a generator (`dots-5mm`, `grid-a4`, `mandala-a4`,
`maze-medium`, `perspective-2pt-a4`, `phone-log-a5`, `polar-a4`,
`staves-treble-a4`, `tiling-hex-a4`, `box-tuck-a4`, and the two documents
`calendar-a4` and `notebook-a4`) and **seven papers that are all `lines` with
different cycles** (`millimeter-a4`, `calligraphy-a4`, `seyes-a4`, `mizige-a4`,
`knitting-chart-a4`, `precrease-16-a4`, `plot-a4`) — and a rendered
**example gallery** in [`examples/`](../examples/) — eighteen definitions:
one A4 sheet per blade, a multi-page maze booklet, the cover sheet, a notebook,
a calligraphy guide, an edge-ruler sheet, a box net and the calendar. Each is an
ordinary definition with its PDF and a PNG preview, guarded by
`test_every_example_validates`. The **calendar** is the one without a committed
PDF (405 pages, 1.6 MB, rebuilt in about a second — its own comment says so).
Before committing a rebuilt gallery, compare byte for byte: the maze booklet
needs its documented `--seed 4711`, and everything else must come out identical
unless the change was meant to move it.

### Done

| Milestone | State |
|---|---|
| **M1** — the vertical slice | complete, and since 2026-07-26 **all seven** acceptance criteria of § 14 are met: the last one was the PyPI release, verified with `uvx` against the published package |
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
| post-M9 `ruler` | an edge scale as frame furniture (§ 8.12): `ruler: {edges: [bottom, left], unit: cm}`. Zero at the *pattern area's* origin, so the numbers agree with the grid; ticks grow outward into the margin and reserve nothing, so switching it on moves no grid line (§ 8.1's rule for `border`, restated). Physical edges, not `inner`/`outer`. **`origin`** (2026-07-26) says where the
nought sits and which way numbers grow — `bottom-left` (technical), `top-left`
(screen, counting down), `center` (plotting, with negatives), plus the two right
corners from the same formula; absent it **follows `pattern.align`**, which
closes a real inconsistency: an anchored grid used to sit beside a scale that
still counted from the bottom. The ladder hangs on the zero rather than the
edge, so a tick now carries its position *and* its value separately. `unit` says what the numbers mean, three lengths say where the ticks are, each a whole multiple of the one below. The ladder arithmetic lives once in `ruler.py` (drawing *and* pre-flight use it); the number's height and width are asked of the writer, never guessed. Four refusals before page one; PNG refused by the existing capability path. Example `13-ruler-edge`, decision 47 |
| post-M9 slanted `lines` | `direction: 55deg` (§ 7.1, decision 48) — spaced *perpendicular*, clipped, and anchored so that **line 0 goes through the pattern area's origin** with an unlimited family growing both ways. `0deg`/`90deg` reproduce `horizontal`/`vertical` mark for mark, which is the test that keeps it one rule. Downwards reads the cycle backwards (`Cycle.positions_between`), the perpendicular's sign points into the area, and negative perpendicular coordinates are legal. A slanted family reports **no** periodic axis, so § 7.1's "no snapping" needs no new machinery; `governing`/`log10` on one are refused. Liang–Barsky moved to `ctrlgrid/clip.py`, shared with `perspective`. Preset `calligraphy-a4`, example `14-calligraphy-italic` |
| post-M9 `--skip-unsupported` | § 10.2's escape hatch, the last unbuilt thing the spec described: leave out what the writer cannot draw and carry on, as the user's explicit decision only (command line, never a def) and never silently — the pre-flight turns its refusal into one notice naming what will go. Implemented as a **wrapper around the writer** (`_LeavingOutWhatItCannotDraw`) rather than a check at each of the dozen `draw` sites, one of which would eventually be forgotten (§ 5.1); it drops marks by capability, plus links, bookmarks and the attachment. Also fixed on the way: a document's pages are now measured with the metrics oracle, not the writer |
| post-M9 `net` | the eleventh blade (§ 7.14, decision 51): a `tray` or a `tuck_top` box from its **inner** dimensions, cut lines solid, creases dashed, glue tabs computed, centred and **refused rather than scaled**. The mechanism: a style produces **panels** and one rule makes the marks — an edge two panels share is a fold, an edge only one has is a cut — so a new style is a panel list, never a traced outline, and the match is exact because positions are integer µm. Every flap must span its attachment edge (that is what makes it exact). Two stated conventions: inner dimensions, and one thickness rule (a panel closing *over* a layer is widened, a flap sliding *inside* is shortened); `thickness: 0` gives the ideal net, and a test says so. Preset `box-tuck-a4`, example `16-net-tray` |
| post-M9 `notebook` | the **second document generator**, and the first that composes blades (§ 7.13, decision 50): sections, each filled by an ordinary generator, with a linked contents page, opt-in dividers and a cover. The seam: a `DocumentPage` may carry a `Fill` (generator name + validated config) instead of marks, and **the handle calls the blade** — `pages.document_page_marks` is the one function that says what is on a page, used by the writer, the capability pre-flight and the media check. A section is a definition in miniature, validated by that blade's own `config_model` with the loader's context (so `px`/`%w` resolve there too). Document bands are now laid out **per page**, so `{page}` counts and a per-page `{section}` names the section; `calendar-a4` stayed byte-identical. `page_layout.Page` extracted from `calendar_layout` and shared. Preset `notebook-a4`, example `15-notebook` |
| post-M9 band colour | a header/footer `Band` takes `background` (a full-width strip, band height only) and `text_color`, both default off — drawn in `layout_band` so both the blade and document paths get them; resolves the title-page contrast (§ 8.9) |
| pulled forward into M1 | format table, presets, `check`, overwrite protection, placeholders — the M1 acceptance criteria needed them |
| 0.11.x — after the audit | **`tests/test_geometry_readback.py`**: every blade's geometry measured out of a finished PDF against numbers taken from the definition, never from the code — a hexagon's every edge exactly `size`, ring radii against the cumulative series, a mandala mapped onto itself by a twelfth of a turn, a perspective fan concurrent within a millimetre, `form`'s 8 mm ruling identical on A4 and A5, log positions against `math.log10`. **`check_page_furniture`**: the frame is checked on both page paths, not only drawn on both. **`check_text_glyphs`**: a generator's text is checked for missing glyphs (§ 12 point 13), which no code had ever done. **`words:` and `font:`** on the document generators, so every word on the sheet comes from the definition and there is a way out of Latin-1 for it (decision 53). **`labels: none`** accepted on `grid` and `polar`, the spelling § 7.10 documents |
| 0.10.0 release-readiness | the audit above, in five commits: three degenerate values that hung or crashed instead of refusing; **`page_furniture`**, so the document path carries the page model (duplex, border, hole marks, ruler, stamp, background) instead of dropping it silently, plus three keys refused by name and a fourth (a multi-sheet blade in a notebook section) refused for now (decision 52); five messages made actionable and `--version` added; a ruler tick that ran off the edge, a ruler font that was never opened, an unreachable bookmark guard; and twenty-six stale comments |

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

**Two more things wait, and neither of them is code:**

- ~~**PyPI.**~~ **Published on 2026-07-26 — `ctrlgrid`, MIT, Python ≥ 3.11, wheel
  and sdist. Two releases so far: `v0.11.0`, the repository's first tag ever, and
  `v0.11.1` for the metadata it should have carried.** M1's first
  acceptance criterion is met at last, and measured rather than assumed: `uvx
  ctrlgrid millimeter-a4 --pages 3 -o out.pdf` installs from the network and
  produces a sheet whose MediaBox reads 210.000 × 297.000 mm with a 1.000 mm line
  spacing, and two runs of it are byte-identical (§ 14, criteria 1–3). From the
  published wheel: `--version` answers, all 19 presets are there, and
  `staves-treble-a4` draws its clef, so the bundled music font resolves too.

  Releasing again is one tag: `git tag -aM vX.Y.Z && git push origin vX.Y.Z`.
  `release.yml` runs ruff and the suite, refuses a tag that disagrees with
  `ctrlgrid.__version__`, builds, and publishes through **trusted publishing** —
  no token in the repository. The publisher is configured for
  `DocAtPrompt/ctrlgrid`, workflow `release.yml`, environment `pypi`; if a
  release ever fails with `invalid-publisher`, that quartet is what PyPI matches
  on, and the failing run prints the claims GitHub actually sent.

  Two things to remember before the next one: **a version can never be
  re-uploaded to PyPI, only yanked** — so the number is decided once — and the
  README's links are absolute on purpose, because a relative one resolves against
  pypi.org on the project page and dies there.

  A third, learnt on 0.11.1: **the summary, keywords and classifiers are part of
  a release and cannot be edited afterwards.** 0.11.0 went out naming six blades
  and none of the documents, so `calendar`, `notebook` and `net` — one of them
  the highest-volume search term in the package — were findable nowhere. Check
  `pyproject.toml`'s `description` against what the tool actually does before a
  release, not after. GitHub's description, topics and homepage are the other
  half of the same question and can be changed at any time.
- **Nobody has cut a net out and folded it.** `examples/16-net-tray.yaml` checks
  the geometry, `box-tuck-a4` also checks the thickness rule. The tests agree
  with the arithmetic; only paper can disagree with it (§ 7.14).
- **1.0.0 waits on use**, not on features — see the version note at the top.

### Deferred features named their milestone — and the list is now empty

Anything specified but not built refused with a message naming the milestone,
never silently: § 5.1 calls a PDF that is *almost* right the worst failure class
there is, so `border:` must never have read as an unknown key while it was
unbuilt, and `snap:` must never have been quietly ignored.

**`grep -rn "milestone M" ctrlgrid/` and `grep -rn "this milestone" ctrlgrid/`
both find nothing**, and neither does a search for TODO, FIXME or HACK. Both
greps are needed: the first alone was the claim this file used to make, and it
missed four live present-tense milestone comments that said "this milestone"
without an M — including one declaring `border` unbuilt. Everything the
specification describes is built; `--skip-unsupported` (§ 10.2) was the last of
it. The remaining `M1`/`M6`/`M9` mentions are lineage ("complete from M1 on"),
not claims about the present.

The machinery stays and is worth knowing about, because the next unbuilt key
will need it: `Section.deferred` (a per-section map of key → sentence) and
`loader.DEFERRED_KEYS` (the same for the top level) both still work and are
currently empty, except for `Margin.deferred`, which explains why margins are
named `inner`/`outer` rather than `left`/`right` (§ 8.1). It also has a second
use now, shown by the document generators: a key the tool **will not** honour on
this path is refused by name rather than ignored (`--nup`, `--cover`,
`pattern.align` on a `calendar` or `notebook` — decision 52).

### The release-readiness pass (2026-07-26)

Before publishing, the code was audited as a stranger would meet it — a wheel
installed into a fresh venv and driven, plus four parallel readers over all 45
modules. Worth knowing, because it says what has and has not been checked:

**Measured and holding.** Integer micrometres: every one of the 19 presets and 18
examples built with an instrumented writer, **zero** non-integer coordinates in
anything drawn. Determinism: ten preset pairs built twice, byte-identical.
Library confinement, `yield`-not-list, no silent `except` — clean across all 45
modules. The blade→handle direction of § 3.3 is intact: no blade reaches up, no
handle module names a blade.

**What it found, and what was done.** Two `ZeroDivisionError` tracebacks and one
infinite loop in `ctrlgrid check` (all three were degenerate zeros that arrived
before the check that would judge them); the document write path silently
dropping most of the page model; five error messages that could not be acted on,
one of which printed raw micrometres against § 3.3; a missing `--version`; three
things accepted and then ignored (a ruler font file, a tick off the edge, an
unreachable capability guard); and twenty-six comments the code beside them had
outgrown. All fixed, each test-first, one commit per coherent block.

**Why the tests had not caught the biggest one:** they exercise the blade path.
The document path is young, has two generators and far thinner coverage, and four
of the five serious findings were there. That is where to look first.

## Read this before writing anything

**The specification is the source of truth, and it is unusually complete** —
~2800 lines covering the architecture, all thirteen generators — eleven blades
and two documents — the page model,
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
fifty-three of them so far, each with the section it belongs to and the
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
| `pages.py` | `Geometry`, page loop, placeholders, `preflight`, `build`, `snap: pixel`, and the three functions both page paths share: **`page_furniture`** (what the handle draws around a page's own marks), **`check_page_furniture`** (whether it fits) and **`check_text_glyphs`** (whether the font can draw it). Each exists because the blade path had it and the document path did not |
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
  geometry back out (lines, dash arrays, whole subpaths and fitted circles), and
  `tests/test_dimensional.py` plus `tests/test_geometry_readback.py` are where
  that is done for every blade. **Every expected number in them comes from the
  definition or from a sentence of the specification — never from the code.**

## Where to start

The architecture has held through every milestone and everything after them:
`generate(cfg, area, page, q)` has never changed signature, and every feature
that needed blade knowledge became a *query the handle asks* rather than geometry
pushed into the blade. Keep that line. When a new feature tempts you to hand a
blade the page, the margins, or the device, look first for the question the
handle could ask instead — that is how `periodic_axes`, `check`, `sheets`,
`supports_snap` and `capabilities` all came to be. Five recent features are the
pattern worth studying: the relative measure resolves in the *loader's*
validation context like `px` (no blade touched); `pattern.align` reflects
finished marks in `pages.py` with `mirror_y` (the blade never learns which
corner it anchored to, § 3.3); the edge ruler is drawn by the handle from the
geometry, so no blade knows it exists; `notebook` — the hardest case, since
it *composes* blades — still touches none, because a page carries a `Fill` and
the **handle** calls the generator (§ 7.13, decision 50); and `page_furniture`,
which is the negative lesson made positive. It exists because the frame was
written twice — once on the blade path, not at all on the document path — and
six features were silently missing from half the tool for two whole generators
(decision 52). **When something is drawn on more than one path, one function
must say what it is.** That is the fourth time this codebase has learnt it, after
`layout_band`, the writer wrapper and `document_page_marks`.

**Nothing proper is left**; *Not done* above lists what is, and none of it is
code. If you add a blade or option, the
recipe is unchanged: for a blade, a registry entry in `generators/__init__.py`
with a `config_model` and the seam-2 methods; for either, a failing test first
(or, when a design is genuinely uncertain, validate on a real sheet then codify —
`pattern.align` was built that way), the *why* in the comment with its § number,
one coherent commit, and a real rendered sheet read back — not just unit tests.
Update the spec and CLAUDE.md in the same breath, so the next instance inherits
the truth; and note the **elements-of-style / verify-before-completion habits**
this project runs on — claims are backed by a command's output, never asserted.

## What to do next

**Nothing in the specification is unbuilt.** As of 2026-07-26 the tool is also
*published* — the sessions since 0.9.0 audited it as a stranger meets it, read
every blade's geometry back out of a finished PDF, and put it on PyPI. The user
has said there is more to do and will say what; nothing below is a queue they
have asked for, it is the state to start from.

Nothing from the 2026-07-25 handover is left either. That handover
([`docs/superpowers/plans/2026-07-25-next-steps-handover.md`](superpowers/plans/2026-07-25-next-steps-handover.md))
carries a *done* note on each of its phases saying what was built and what was
decided against; the designs and plans behind the larger ones live beside it in
`docs/superpowers/specs/` and `docs/superpowers/plans/`, and the reasoning of
every one is in `git log`. Read those when you need the *why* of something you
find in the code.

So there is no queue. What remains needs something this session could not
supply:

| Waiting on | What |
|---|---|
| a device | the empty `quirks` (decision 31), and the rM2 figures nobody has measured on the device — the Paper Pro is owner-checked, the rM2 is not |
| a pair of scissors | print `examples/16-net-tray.yaml` and `box-tuck-a4` at 100 %, cut, fold. The tray checks the geometry; the tuck-top also checks the thickness rule. **No test can do this**, and until someone does, the tests only agree with themselves |
| use | the three § 15 questions below, and 1.0.0 itself. The DSL can now meet someone other than the test suite, which is the one thing 1.0.0 has always been waiting for |

If a new feature *is* wanted, the recipe has not changed since M1: a design
settled with the user first when there is a real fork in it, then a plan, then
test-first with the *why* and its § number in the comment, one coherent commit,
a real rendered sheet read back — and the spec, `implementation-decisions.md`
and this file updated in the same breath.

Three habits earned their place the hard way and are worth keeping:

- **Measure against the declared value, never against the drawing.** An angle
  read back with `atan2` from rounded endpoints, a position measured from the
  sheet's corner instead of the pattern's origin, a dash length judged by
  arithmetic instead of by looking — each of those cost a debugging round, and
  in every case the code was right and the ruler was wrong.
- **A check that compares two things computed from the same number proves
  nothing.** `plot-a4` shipped with its axes half a millimetre off the grid
  because "the cross agrees with the scale" was verified — and both came from
  the same centre. The third quantity, the grid, was the only one that could
  have contradicted it, and it was not looked at until the user did.
- **A probe that does not fire proves nothing either — suspect the probe first.**
  This happened *five* times over the release sessions, and not once was the code
  at fault: a name list without `{name}` in any band draws no text, so the glyph
  check had nothing to refuse; a pipeline's `$?` is `head`'s exit code, not the
  tool's; a `--seed` that never reached the loop made the maze booklet look like
  a regression; Vera has 256 glyphs and no Polish, so "a font file fixes it"
  failed for the fixture's reason and not the check's; and a grep for a claim in
  `docs/CLAUDE.md` missed it because the sentence wrapped across two lines.
  Every one of them was about to be written up as a bug. **Before writing "X is
  not checked", make the probe fail on purpose.**

A specific paper aeroplane was considered and **refused**: it is a drawing, not
a structure, and § 2 rules out a drawing language.

## Open questions

Of § 15's questions, only three remain, and all three are
*decide-after-experience* calls rather than gaps. **Question 3 closed**
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
the music case, a font *is* shipped. The three that remain: whether a font must be shipped for non-Latin-1 names
(q2), extra domain units like nib widths / `lpi` / rastral sizes (q4), and the
short-edge duplex flip (q6). Each is cheap and each waits on real use rather
than on a design answer — **q4 was put to the user in July 2026 while building
the slanted families and deliberately left out**: the angle is what unlocks
calligraphy guides and origami pre-creasing, the unit would be a convenience on
top of it (§ 7.1).

**q2 changed shape on 2026-07-26 and is worth re-reading in § 15.** It used to be
theoretical, because a missing glyph in a generator's text was never noticed: the
check ran over the bands only, a Polish month name printed as a box, and a
document generator took no font at all — so the documented remedy did not exist
for it. Both are fixed (decision 53). Stage 2 is now *reachable* everywhere, and
the question is no longer "does it work" but "is it reasonable to ask, or should
a broad OFL font travel with the tool?". Still for use to answer — but now the
user is shown the choice instead of a box.
