# Ctrl+Grid — orientation

## What this is

A CLI tool that generates **dimensionally accurate PDF templates**: grid paper,
ruled paper, dot grids, staff paper, mazes, polar targets, tilings and fillable
forms — for paper formats and for e-ink devices.

**The one promise:** what says 5 mm measures 5 mm on the printout. No scaling,
no "fit to page", no stretching a grid so it comes out even.

## Current state — read this first

**M1, M2 and M3 are complete.** 0.1.0 is the version in the code; nothing since
M1 has been released, because releasing needs a human (see *Not done*).

```bash
uv sync --extra dev && uv run pytest && uv run ruff check .
```

481 tests, all green, ruff clean. Twelve commits on `main`, linear history, **no
remote configured — nothing has ever been pushed.**

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
| **M4** `dots` | two crossed cycles, `combine`, colour with a named axis |
| **M3** — `polar` | rings, spokes, segment and ring labels, counting patterns (§ 7.10) |
| pulled forward into M1 | format table, presets, `check`, overwrite protection, placeholders — the M1 acceptance criteria needed them |

### Not done

**M4 is under way** — `dots` is done; `staves`, `grid`, `maze`, `tiling`,
`form` and `law: log10` (§ 7.9) are not. Three things M3 built are
there to be reused: `labels.py` (§ 7.10) is what `grid` and `tiling` label
with, `generators/common.py` holds the cycle and dash fields every family
needs, and `check()` is where a blade refuses what only the pattern area can
disprove.

**Later milestones**, untouched: M5 device profiles, M6 N-up, M7 PNG,
M8 `perspective`/`mandala`.

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
twenty-three of them so far, each with the section it belongs to and the
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
| `units.py` | `Length`/`Angle`; parsing to exact int µm via `Decimal` |
| `errors.py` | `DefinitionError` with field path and source line |
| `marks.py` | the six primitives, `Layer`, `Point`, `Area`, `translate` |
| `cycles.py` | `Cycle`, drift-free positions, effective period |
| `axes.py` | `AxisPeriod` — what the handle needs from a blade for § 8.3/§ 8.5 |
| `model.py` | pydantic sections; `Section` base with `extra="forbid"` + `deferred` |
| `loader.py` | YAML → `Document`; formats, presets, devices, name lists |
| `pages.py` | `Geometry`, page loop, placeholders, `preflight`, `build` |
| `frame.py` | header/footer layout, border, background, hole marks, stamp |
| `labels.py` | counting patterns `n`/`a`/`A`, explicit lists (§ 7.10) |
| `images.py` | PNG sources: signature check, pixel size, aspect (§ 5.2, § 13) |
| `fonts.py` | font files: `fsType` licence check, version, coverage (§ 10.3) |
| `cover.py` | the cover sheet: calibration figures and settings summary (§ 8.8) |
| `generators/` | registry, `common.py` (cycle + dash fields), `lines`, `polar` |
| `writers/` | seam 3 protocols + `pdf.py`, the only reportlab module |

### The three seams (§ 3.6)

1. **Definition → model.** `loader.load()`. After it there are no unit strings
   left in the core.
2. **Generator → marks.** `generate(cfg, area, page, q) -> Iterator[Mark]`,
   plus the queries `is_page_invariant`, `describe`, `periodic_axes`, `check`,
   and the declaration `supports_snap`.
3. **Marks → writer.** Bidirectional: marks in, font metrics out.

**Seam 2 has grown four queries and `generate` has never changed.** When `snap`
and `remainder` needed blade knowledge, the handle got a question to ask
(`periodic_axes`) rather than the blade getting the pattern block. § 8.3 says
the *pattern area* shrinks, so shrinking it is the handle's job. Keep new
handle features on that side of the line: six of the eight blades would have to
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

`polar` passed the test § 14 designed it to be: the handle needed no change
for a non-cartesian blade beyond one new query (`check`) and one declaration
(`supports_snap`), and `generate` did not move. The pressure came where it was
expected — not in the geometry but in *when* a refusal happens.

So M4 is the next step, and the cheapest of the remaining blades is `dots`:
it is two cycles crossed, and § 10.1 already prescribes how a dot is drawn.

## Open questions

Six in § 15, none blocking. Two need a device or a source rather than a decision
(reMarkable 2 figures, whether the Paper Pro counts as a colour device). If you
are tempted to guess at a number, don't — that is exactly the failure mode
`source`/`verified` exists to prevent.
