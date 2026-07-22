# Ctrl+Grid

Generate **dimensionally accurate** PDF templates from a small definition file:
grid paper, ruled paper, dot grids, staff paper, mazes, polar targets, tilings
and fillable forms — for paper formats **and** for e-ink tablets.

> **Status: milestone M1 complete, M2 well under way.** One blade is sharp:
> `lines` works end to end and is covered by the dimensional test described
> below. The handle around it is nearly finished — multi-page output, headers
> and footers, name lists, snapping, remainder handling, double-sided margins,
> border, background, hole marks, stamp, the calibration cover sheet and
> embedded font files.
>
> The other generators in the table further down, and the options marked below
> as arriving later, are specified but not built yet. Asking for one gets you a
> message naming the milestone it arrives with — never a silently different
> sheet.
>
> Working today:
>
> ```bash
> ctrlgrid millimeter-a4 --pages 30 -o grid.pdf
> ctrlgrid millimeter-a4 --names class3b.txt      # a sheet per name
> ctrlgrid -d my-def.yaml --stamp DRAFT
> ctrlgrid millimeter-a4 --cover              # + a calibration first sheet
> ctrlgrid check my-def.yaml
> ctrlgrid presets | show <name> | devices
> ```
>
> Flags: `--pages`, `--names`, `--format`, `--orientation`, `--stamp`,
> `--cover`, `-o`, `--force`, `--quiet`.
>
> Not yet: `--device`, `--nup`, `--seed`, `--strict`,
> `--skip-unsupported`, and the interactive mode.
>
> **Not on PyPI yet**, so the `uvx`/`pip` lines below do not work until the
> first release is published.

## The one promise

**What says 5 mm measures 5 mm on the printout.** No scaling, no "fit to page",
no stretching a grid so it comes out even. If a grid does not fit the page, you
are told — it is never quietly adjusted.

That promise is enforced by a test that generates a PDF, reads it back and
measures it, on every commit.

## Why another one

Of roughly 60 comparable tools surveyed ([`docs/research.md`](docs/research.md)),
three can emit more than one page and **none** can drive page content from a
list. Ctrl+Grid is built around exactly that: one command, one finished
multi-page PDF.

```bash
# 30 sheets of millimetre paper
ctrlgrid millimeter-a4 --pages 30 -o grid.pdf

# one sheet per name, each with the name in the header
ctrlgrid millimeter-a4 --names class3b.txt

# a different maze on every page, reproducibly
ctrlgrid maze-medium --pages 20 --seed 4711

# your own definition, on Letter, with a calibration cover sheet
ctrlgrid -d my-def.yaml --format letter --pages 5 --cover

# no arguments: pick a preset interactively
ctrlgrid
```

*Some of those need milestones that are not finished — see the status note
above for what runs today.*

## Installation

```bash
uvx ctrlgrid --help          # no installation
pip install ctrlgrid         # or the usual way
```

There are no double-clickable installers, and none are planned.

## What it generates

| Generator | Produces |
|---|---|
| `lines` | squared, ruled, isometric, calligraphy, Cornell, log/semi-log |
| `dots` | dot grids with emphasised rows and columns |
| `staves` | blank music staves and guitar tab |
| `grid` | labelled cell blocks — battleship, score sheets |
| `maze` | rectangular mazes, optionally with solutions |
| `polar` | targets, score discs, polar paper |
| `tiling` | hexagons, triangles, rhombi — including colouring patterns |
| `form` | fillable forms: phone logs, checklists, handover sheets |

The interesting part is the **cycle model**: spacing, stroke weight, size, dash
pattern and colour each follow their own repeating list, and the lists may have
different lengths. "Every fifth line heavier and blue, every third dashed" is one
definition, not a special case.

## Definition files

A definition is YAML with a version line. Start from a preset and change it:

```bash
ctrlgrid presets              # list them
ctrlgrid show millimeter-a4   # print one, ready to copy
ctrlgrid check my-def.yaml    # validate without generating
```

**The presets are the documentation.** They are ordinary definition files, not a
separate mechanism, so anything a preset does you can do too — and there is no
second syntax reference here to drift out of date.

## E-ink devices

```bash
ctrlgrid devices                              # list known profiles
ctrlgrid dots-5mm --device remarkable-paper-pro
```

Device profiles carry pixels **and** physical size, so millimetres stay
millimetres. Using a profile also makes the PDF page match the screen exactly,
which is what makes the usual "fit page" view show it at true size.

Adding a profile for your device is the easiest useful contribution — see
[`CONTRIBUTING.md`](CONTRIBUTING.md).

## Known limitations

Please read these. Each one is a real constraint, and each looks like a bug if
you meet it without warning.

**1. Print at 100 %, not "fit to page".** Most PDF viewers default to fitting the
page and silently scale to about 96 %. Choose "Actual size" / "100 %". Run with
`--cover` to get a first sheet with a 50 mm calibration square and a 100 mm rule:
measure them with a ruler and you will know immediately whether your printer
scaled. That sheet also records the settings that produced the document — format,
margins, base values, cycles, effective period, tool version and a checksum of
the definition — so a print that came out right stays reproducible. It is not
counted in the page numbering, and it is never scaled to fit: on a format too
narrow for the 100 mm rule the run is refused rather than shrunk.

**2. Character coverage is Latin-1 by default.** Without a font file of your own,
`ä ö ü ß é à ñ ç` work but `ł ğ ő` do not — you will hit this on the first Polish
or Turkish name in a list. The fix is to point at a font *file* — a path, never
a font name, because name lookup finds different fonts on different machines:

```yaml
header:
  height: 12mm
  left: "{name}"
  font: { file: "~/Library/Fonts/EBGaramond-Regular.ttf", size: 11pt }
```

The font is embedded and subset, so the PDF is the same everywhere. Its
embedding licence is **checked, not assumed**: a font whose `fsType` forbids
embedding aborts the run and is named — never quietly swapped for another one,
which would change every measurement on the sheet. A character the file itself
lacks is still an error, now naming the file.

**3. Margins below about 5 mm get clipped** by most printers. The default comes
from the paper format and reflects the typical non-printable border; e-ink
profiles use 0.

**4. N-up does not scale.** `--nup` places pages at 100 % and fails if they do not
fit, unlike `pdfjam` and `pdfcpu`. Define a small format and impose it onto a
large sheet; do not expect four A4 pages to be shrunk onto one.

**5. `{date}` makes output date-dependent.** Two runs on different days produce
different files. If you want a reproducible sheet, write the date as text.

**6. Solutions printed on the back need long-edge duplex.** `solution:
back_mirrored` prints the maze solution mirrored on the reverse so it lines up
when held to the light. Short-edge flipping puts it upside down, and whether it
shows through at all depends on your paper.

**7. There is no GUI**, and none is planned. `ctrlgrid` with no arguments gives
you an interactive preset picker, which is as far as it goes.

## Documentation

- [`pflichtenheft-vorlagengenerator.md`](pflichtenheft-vorlagengenerator.md) —
  the full specification, in German. Records not just what the tool does but why.
- [`docs/implementation-decisions.md`](docs/implementation-decisions.md) — the
  points where the specification was silent, and what was decided instead.
- [`docs/research.md`](docs/research.md) — survey of comparable tools, July 2026.
- [`CONTRIBUTING.md`](CONTRIBUTING.md) — how to add device profiles, presets and
  code.

## Licence

MIT — see [`LICENSE`](LICENSE).
