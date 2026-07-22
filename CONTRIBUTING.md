# Contributing to Ctrl+Grid

Thanks for considering it. This file tells you what kinds of contribution fit,
and what the project will not accept — knowing the second saves you more time
than the first.

## Two contributions that need no code

These are the most useful things you can send, and neither requires
understanding the internals.

### 1. A device profile

If you own an e-ink tablet or reader that is not in `ctrlgrid/data/devices.yaml`,
add it:

```yaml
- id: my-device
  name: "Manufacturer Model"
  pixels:   { x: 1620, y: 2160 }        # ALWAYS portrait
  physical: { x: 179.7mm, y: 239.6mm }  # computed from pixels ÷ density
  density: 229dpi
  color: grayscale
  margin: 0mm
  quirks: []
  source: "https://… or 'owner-verified — how you checked'"
  verified: 2026-07
```

**`source` and `verified` are mandatory.** Device specifications are exactly the
kind of data that spreads quietly and becomes quietly wrong. A profile without a
source will not be merged.

**Owner-verified beats a manufacturer page.** If you generated a PDF at those
dimensions and it fit your device exactly, say so — that is stronger evidence
than a spec sheet, and secondary sources are demonstrably unreliable here (one
widely repeated figure for the reMarkable Paper Pro is simply wrong; see
`docs/research.md`).

**Sanity-check before you submit.** Pixels ÷ density should give the physical
size, and the diagonal should match the advertised one. If they disagree, one of
the numbers is wrong — say which you trust and why.

### 2. A preset

Presets live in `ctrlgrid/data/presets/*.yaml` and are ordinary definition files.
There is no separate mechanism for them, which is deliberate: a preset is a
worked example, and **the presets are also the documentation**.

That means a preset should be *readable*, not merely correct. Name it for what it
produces (`millimeter-a4`, `calligraphy-a4`), comment the non-obvious values, and
prefer the plain form over the clever one.

## Contributing code

### Before you start

Read the specification first. It is `pflichtenheft-vorlagengenerator.md` — in
German, and deliberately not part of the shipped package. It records not just
what the tool does but *why*, and most design questions you will have are
answered there with reasoning.

If you disagree with a decision, open an issue naming the section. Several
decisions look arbitrary and are not.

### Rules that are not negotiable

These are architectural, not stylistic. A pull request that breaks one will be
asked to change, however good the rest is.

1. **`reportlab` appears only in `ctrlgrid/writers/pdf.py`**, and
   `tests/test_architecture.py` enforces it. No generator, no model, no CLI code
   imports it. The second writer is dead before it exists otherwise.
2. **Positions are integer micrometres.** Never accumulate floats to compute a
   coordinate. The tool's one promise is dimensional accuracy.
3. **Generators yield marks, they do not build lists.** A 200-page dot grid is
   hundreds of thousands of objects.
4. **Fail loudly, never silently mangle.** Validate before writing the first
   page; abort completely or build completely. An error message that does not
   let the user act is a bug.
5. **Everything user-visible is English** — keys, code, messages, preset names.
   No translation layer.
6. **Reproducible output.** Same input, same bytes. No `hash()`, no wall-clock
   time, no locale-dependent formatting in the document.

### The three interfaces

`ctrlgrid` is a handle with blades. The handle owns page geometry, header,
footer, frame, stamp, page loop and output; a blade only produces marks. Three
interfaces are contracts and are specified with signatures in § 3.6 of the
specification:

- definition file → validated model
- generator → marks
- marks → writer (bidirectional: the writer also answers text-metric queries)

Everything else is an implementation detail and may change.

### Adding a generator

A new blade is a registry entry in `ctrlgrid/generators/__init__.py` plus one
module; `generators/lines.py` is the worked example. It gets the page loop,
header, footer, framing and output for free — and whether that stays true is the
test of whether the architecture holds.

Beyond `generate`, seam 2 asks a blade three questions: `is_page_invariant`
(§ 10.1), `describe` for the run report (§ 5.3), and `periodic_axes`, which is
how the handle snaps and places the surplus without ever reaching into the blade
(§ 8.3, § 8.5). A blade with no periodic families returns nothing from the last
one, and that is what makes `snap` an error there rather than a no-op.

Before proposing one, check § 2 of the specification. Some things are excluded
on purpose: music engraving, free paths and curves, a general drawing language,
a plugin system, a GUI.

### Adding a writer

The mark vocabulary is six primitives (§ 6). It is kept small precisely so that
a foreign writer is an evening's work. A writer that cannot do everything is
fine — report what you support via `capabilities()` and the pre-flight check
will refuse definitions that need more.

## Tests

```bash
uv run pytest
```

The important test is not a unit test: `tests/test_dimensional.py` generates a
PDF, reads it back, and checks the MediaBox and mark coordinates against
expected values. If you touch geometry, that is the one that matters.

Golden-file comparisons check *parsed geometry*, never bytes — otherwise a
`reportlab` update breaks the suite.

## Pull requests

- One concern per pull request.
- Say what you verified, and how. "Tests pass" is less useful than "printed it
  at 100 % and measured 5.0 mm".
- If you changed behaviour the specification describes, update the
  specification in the same pull request. A spec that drifts from the code is
  worse than none.

## Licence

By contributing you agree that your contribution is licensed under the MIT
licence, as in `LICENSE`.
