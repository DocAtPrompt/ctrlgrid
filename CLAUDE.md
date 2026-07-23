# Ctrl+Grid — orientation

## What this is

A CLI tool that generates **dimensionally accurate PDF templates**: grid paper,
ruled paper, dot grids, staff paper, mazes, polar targets, tilings and fillable
forms — for paper formats and for e-ink devices.

**The one promise:** what says 5 mm measures 5 mm on the printout. No scaling,
no "fit to page", no stretching a grid so it comes out even.

## Current state — read this first

**M1 to M8 are complete but for M5's small edges** — the handle, all ten blades
of § 7, device profiles, `px`, the media check, `snap: pixel`, N-up imposition,
and the PNG writer. **M8 is now done too**: `perspective` and `mandala`, the two
blades that compute their own law instead of a cycle (§ 7.11).
0.1.0 is the version in the code; nothing since M1 has been released, because
releasing needs a human (see *Not done*).

```bash
uv sync --extra dev && uv run pytest && uv run ruff check .
```

763 tests, all green, ruff clean. Twenty-nine commits on `main`, linear history, **no
remote configured — nothing has ever been pushed.** Seven presets (one each for
`lines`, `dots`, `polar`, `form`, `maze`, `perspective`, `mandala`); `staves`,
`grid` and `tiling` have none yet, though every blade is documented here and in
the specification.

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
| pulled forward into M1 | format table, presets, `check`, overwrite protection, placeholders — the M1 acceptance criteria needed them |

### Not done

**M5's small edges are all that remain of M1–M7.** M5's core shipped; three
pieces are left, and each names why:

- **`quirks` ships empty** (decision 31). § 9.2 provides the field with a Boox
  dead-row example, but no shipped profile is a Boox and inventing a dead-row
  pattern for a device nobody here can test is the guessed number § 9.2 warns
  against. Modelled and carried, waiting for a verified contribution.
- **Relative measures** (§ 9.2) — the 3:4 e-ink aspect is not A4's 1:√2, so a
  fixed-mm definition does not fill a device the way it fills paper. `px` and a
  device's own pixels are a device-relative measure already; a general
  "fraction of the pattern area" mechanism at the handle level would be a new
  design decision and is not built. `form` has `%`, but only inside its own
  block.
- Two of § 15's open questions are still device figures nobody has verified —
  the rM2 numbers and whether the Paper Pro is a colour device — and § 9.2 is
  explicit that a wrong number there is worse than no profile at all.

**Every milestone proper is now done — M8 shipped `perspective` and `mandala`**
(§ 7.11). Both compute their own law instead of a cycle (a generator may, § 5.3):
`perspective` divides a base edge equally and clips its rays with Liang–Barsky,
`mandala` counts sectors and rings on the shared `polar_geometry` (extracted
from M3's polar so the two blades share one arithmetic, not two that drift).
What is left of `staves` is now **decided, not open**: the clef conflict (§ 7.3
wanted stored vector paths, § 6 fixes the vocabulary at six primitives with no
curve path) is resolved in **§ 15.3** — a clef is a `Text` mark in an embedded,
subset music font, which keeps the six primitives and § 15.2 intact and stays
self-contained through embedding. That is real work, scheduled as **M9** (§ 14),
so a named clef now refuses by naming its milestone like every other unbuilt
option (§ 5.1), not as an open question. Three things M3 built are there to be
reused: `labels.py` (§ 7.10) is what `grid` and `tiling` label with,
`generators/common.py` holds the cycle and dash fields every family needs, and
`check()` is where a blade refuses what only the pattern area can disprove.

**Two things only a human can do**, both needed before `uvx ctrlgrid` works:
configure a git remote and push; set up trusted publishing on PyPI plus a
`pypi` environment, then tag `v0.1.0` to trigger
[`.github/workflows/release.yml`](.github/workflows/release.yml). CI has
therefore **never actually run** — it is green locally on macOS only.

### Deferred features name their milestone

Anything specified but not built refuses with a message naming the milestone,
never silently. `grep -rn "milestone M" ctrlgrid/` lists every one. This is
deliberate: § 5.1 calls a PDF that is *almost* right the worst failure class
there is, so `border:` must never have read as an unknown key while it was
unbuilt, and `snap:` must never have been quietly ignored.

## Read this before writing anything

**The specification is the source of truth, and it is unusually complete** —
~2200 lines covering the architecture, all eleven generators, the page model,
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
[`docs/implementation-decisions.md`](docs/implementation-decisions.md) —
thirty-nine of them so far, each with the section it belongs to and the
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
| `cli.py` | `typer` commands, flag→override map, writer choice by `-o` extension |
| `units.py` | `Length`/`Angle`; parsing to exact int µm via `Decimal` |
| `errors.py` | `DefinitionError` with field path and source line |
| `marks.py` | the six primitives, `Layer`, `Point`, `Area`, `translate`, `mirror_x` |
| `cycles.py` | `Cycle`, drift-free positions, effective period |
| `axes.py` | `AxisPeriod` — what the handle needs from a blade for § 8.3/§ 8.5 |
| `model.py` | pydantic sections; `Section` base with `extra="forbid"` + `deferred` |
| `loader.py` | YAML → `Document`; formats, presets, devices, name lists |
| `pages.py` | `Geometry`, page loop, placeholders, `preflight`, `build`, `snap: pixel` |
| `frame.py` | header/footer layout, border, background, hole marks, stamp |
| `labels.py` | counting patterns `n`/`a`/`A`, explicit lists (§ 7.10) |
| `images.py` | PNG sources: signature check, pixel size, aspect (§ 5.2, § 13) |
| `media.py` | the media check: resolution and colour findings (§ 12.1) |
| `impose.py` | N-up layout, the 100 % fit check, crop marks (§ 14) |
| `fonts.py` | font files: `fsType` licence check, version, coverage (§ 10.3) |
| `cover.py` | the cover sheet: calibration figures and settings summary (§ 8.8) |
| `generators/` | registry, `common.py` (cycle + dash fields), `polar_geometry.py` (shared by `polar` + `mandala`), and the ten blades |
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

The architecture has held through all eight milestones: `generate(cfg, area,
page, q)` has never changed signature, and every feature that needed blade
knowledge became a *query the handle asks* rather than geometry pushed into the
blade. Keep that line. When a new feature tempts you to hand a blade the page,
the margins, or the device, look first for the question the handle could ask
instead — that is how `periodic_axes`, `check`, `sheets`, `supports_snap` and
`capabilities` all came to be. M8's two blades held it too: `perspective` and
`mandala` compute their own law (§ 5.3) yet added nothing to the seam.

**No milestone proper is left, and the one open *decision* is now made too** —
the `staves` clef question is resolved in § 15.3 (embedded music font), leaving
its build as **M9** (§ 14). What remains is small, and each names its reason in
*Not done* above: M5's empty `quirks`, a general relative-measure mechanism, the
two unverified device figures, and M9 itself (clefs). If you build M9 or add a
blade, the recipe is unchanged: a registry entry in `generators/__init__.py`
with a `config_model` and the seam-2 methods, a failing test first, the *why* in
the comment with its § number, one coherent commit, and a real rendered sheet
read back — not just unit tests.

## Open questions

Six in § 15, none blocking. Two need a device or a source rather than a decision
(reMarkable 2 figures, whether the Paper Pro counts as a colour device). If you
are tempted to guess at a number, don't — that is exactly the failure mode
`source`/`verified` exists to prevent. The seventh — the `staves` clef — is now
answered in § 15.3 (embedded music font, built in M9), and it settled part of
open question 2: for the music case, a font *is* shipped.
