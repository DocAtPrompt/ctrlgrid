# Ctrl+Grid — orientation

## What this is

A CLI tool that generates **dimensionally accurate PDF templates**: grid paper,
ruled paper, dot grids, staff paper, mazes, polar targets, tilings and fillable
forms — for paper formats and for e-ink devices.

**The one promise:** what says 5 mm measures 5 mm on the printout. No scaling,
no "fit to page", no stretching a grid so it comes out even.

## Current state

**Specification plus an empty scaffold. No functionality exists yet.**

| File | What it is |
|---|---|
| `pflichtenheft-vorlagengenerator.md` | The specification. **German.** Deliberately not shipped with the package. |
| `docs/research.md` | Competitive analysis of ~60 comparable tools, July 2026. Backs the positioning claims. |
| `pyproject.toml` | Packaging, dependencies, entry point. Builds and installs. |
| `ctrlgrid/cli.py` | Stub. Prints "not implemented" and exits 1. |
| `ctrlgrid/data/*.yaml` | **Real data.** Seven paper formats, two device profiles — already in the schema § 9.1/§ 9.2 specify. |
| `tests/test_architecture.py` | **Live.** Enforces that `reportlab` stays in `writers/pdf.py`. |
| `tests/test_dimensional.py` | Skipped placeholder. The test the project exists for; write it in M1. |
| `.github/workflows/ci.yml` | Lint, test, build on Linux/macOS/Windows. Green today. |
| `README.md`, `CONTRIBUTING.md`, `LICENSE` | Public face, English, MIT. |

```bash
uv sync --extra dev && uv run pytest && uv run ruff check .
```

CI is green from the first commit and stays that way — do not merge red. The
architecture test already guards rule 1 below, before there is any code to
break it.

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

## Language split

- **Code, DSL keys, error messages, preset names, README, comments: English.**
- **The specification: German.** It is an internal design document.
- Do not add a translation layer. Form labels like "Ja"/"Nein" come from the
  user's definition file, never from the tool (§ 7.8).

## The architecture in one paragraph

A pocket knife: one handle, several blades. The **handle** owns page format,
margins, pattern area, frame, header, footer, stamp, hole marks, the page loop
and output. A **blade** (generator) only produces marks in local coordinates and
knows nothing about margins. Three interfaces are contracts with signatures in
§ 3.6; everything else is an implementation detail.

## Non-negotiables

1. `reportlab` only in `ctrlgrid/writers/pdf.py`. The module arrives with M1; the
   test that guards it already runs.
2. Positions as integer micrometres, never accumulated floats. Stroke widths and
   opacity stay float.
3. Generators `yield` marks, they do not build lists.
4. Validate everything before writing page one. Abort completely or build
   completely.
5. Same input → same bytes. No `hash()`, no wall-clock time in the document.
6. Fail loudly. An error message that does not let the user act is a bug — § 12
   calls error messages "the face of the tool", and means it.

## Where to start

**M1** (§ 14), and it is scoped as a vertical slice through every layer rather
than a broad foundation: parser, model, units, *one* generator (`lines`), the
PDF writer, the page loop with header and footer, the writer query API, the
dimensional test with CI, and a PyPI release reachable via `uvx`.

M1 has **seven explicit acceptance criteria** in § 14. Two of them are the kind
you cannot retrofit without rebuilding — byte-identical repeat runs, and the
import test for `reportlab`. Do those early rather than last.

Do not start further blades before M1 stands. The point of a vertical slice is
to find out whether the seams hold.

## Open questions

Six, all listed in § 15, none blocking M1. Two need a device or a source rather
than a decision (reMarkable 2 figures, whether the Paper Pro counts as a colour
device). If you are tempted to guess at a number, don't — that is exactly the
failure mode `source`/`verified` exists to prevent.
