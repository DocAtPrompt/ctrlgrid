# Competitive research — printable paper generators

**Survey date:** July 2026
**Scope:** ~60 tools — web generators, CTAN/LaTeX packages, GitHub projects, CLI utilities
**Purpose:** feature-gap analysis backing the positioning claims in the Pflichtenheft (§ 1.1)

This file exists so that the claims in the specification remain checkable. Where
the spec says "the research shows…", this is what it refers to.

---

## 1. The headline finding

**No CLI tool occupies the position "definition file → multi-page printable PDF."**

- Of all surveyed generators, **three** can emit more than one page:
  [printablegraphpaper.app](https://printablegraphpaper.app/) (1/5/10/20/50/100),
  [vmaths.fr](https://www.vmaths.fr/apps/generateur-feuilles-lignees.html) (1–50),
  and [Mazerator](https://github.com/erond/Mazerator) (`--pages N`).
- **None** can drive page content from an external list (names, numbers, labels).
- **None** increments a page number across a run. Header "page" fields exist
  (e.g. [calcbe](https://calcbe.com/en/tools/)) but are static.
- Everyone else emits one page and expects the user to print it N times from the
  print dialog — which loses all per-page variation.

The nearest neighbours in adjacent categories are
[latex-yearly-planner](https://github.com/kudrykv/latex-yearly-planner) (hyperlinked
e-ink planners, YAML config chaining) and
[Notebook-Maker](https://github.com/LPBeaulieu/Notebook-Maker-PrintANotebook)
(page numbering, headers/footers, TOC, cover with auto-computed spine width).
Neither is a pattern generator in our sense.

## 2. The most-implemented feature — and our differentiator

**"Heavier line every N"** (accent/index lines) is the single most widely
implemented option: [incompetech](https://incompetech.com/graphpaper/),
[mathster](https://mathster.com/graphpaper/) (every 2–10, 12, 16, 20),
[printablegrid](https://printablegrid.com/graph-paper) (5/10/15/20), calcbe,
and LaTeX [`gridpapers`](https://ctan.org/pkg/gridpapers) (`majmin`).

Its **absence** is the most-cited complaint about tools that lack it
(notably [paperkit](https://paperkit.net/)).

Our cycle model (Pflichtenheft § 5.3) subsumes this and generalises it: multiple
independent cycles of differing length over spacing, weight, size, dash and
colour. Only incompetech's `multiwidth`/`multicolor` (three fixed tiers) comes
close, and it is not composable.

## 3. Capability summary

| Tool | Types | Units | Weight | Colour | Multi-page | Personalisation | Imposition |
|---|---|---|---|---|---|---|---|
| [incompetech](https://incompetech.com/graphpaper/) | 52 | lines/in, lines/cm, mm, in | free pt | line + background hex | — | — | — |
| [calcbe](https://calcbe.com/en/tools/) | ~25 | mm, nib widths, counts | mm per element | per-element + opacity | — | header fields | fold marks only |
| [printablegraphpaper.app](https://printablegraphpaper.app/) | 34 | 1 mm–2 in | yes | 5 named + picker | **1–100** | — | — |
| [blanksheetmusic.net](https://www.blanksheetmusic.net/) | 31 | mm/cm/in | 3 steps | dark…faint | — | — | — |
| [printablegrid](https://printablegrid.com/graph-paper) | 11+ | mm/in, knitting gauge | 0.1–0.8 mm | line + bg + alpha | — | stitch/row numbers | — |
| [gridzzly](https://gridzzly.com/) | 7 | 5–20 mm/in | — | shade 0–50 | — | — | — |
| [desmoulins.fr](http://www.desmoulins.fr/index.php?pg=scripts!online!feuilles) | ~30 | mm | — | per-line | — | — | **recto/verso** |
| [vmaths.fr](https://www.vmaths.fr/apps/generateur-feuilles-lignees.html) | 5 | mm | yes | + opacity | **1–50** | — | ISO hole guides |
| [mkhexgrid](https://www.nomic.net/~uckelman/mkhexgrid/mkhexgrid.html) | hex | px, in, mm, pt | + opacity | + opacity | — | `printf` coord labels | — |
| [`gridpapers`](https://ctan.org/pkg/gridpapers) | 11 | any TeX length | pt | 6 colorsets + overrides | document | LaTeX | via `geometry` |
| [Mazerator](https://github.com/erond/Mazerator) | maze | cells | — | b/w | **`--pages`** | `--locale` (15) | — |
| [bookbinder-js](https://momijizukamori.github.io/bookbinder-js/) | — | pt | — | — | — | — | **full signatures** |

## 4. Features worth copying

Ranked by how many independent tools implement them (i.e. probably genuine needs,
not gimmicks):

1. **Per-side margins** in mm/in — near universal
2. **Accent lines every N** — see § 2
3. **Explicit line weight in pt or mm.** Tools that degrade this to
   thin/medium/thick (paperkit, blanksheetmusic, customgraph) are visibly weaker
4. **Arbitrary hex colour per line class** — incompetech, calcbe, mkhexgrid, gridpapers
5. **Independent X and Y spacing** — required by knitting gauge, ledger, storyboard
6. **Faint / "scan-friendly gray" / non-reproducing blue** — appears independently
   in five places; a real requirement for scanning and photocopying workflows
7. **Background colour as a separate field** — enables tinted and inverted sheets
8. **Hex orientation flat-top vs pointy-top** — every hex tool exposes it
9. **Header block with name/date/title** — teacher-driven, calcbe and others
10. **Shareable/exportable configuration** — only calcbe and blanksheetmusic;
    everything else loses your settings. *(Our def file is this, by construction.)*

## 5. Clever ideas seen once or twice

- **Calibration square printed on the sheet** (calcbe, ~50 mm) — the only direct
  answer to print scaling. → Pflichtenheft § 8.8, on the cover page.
- **Print-settings summary in the margin** (calcbe) — the sheet documents the
  parameters that produced it. → § 8.8.
- **Hole-punch guides**, incl. named **ISO 838** (vmaths, calcbe) → § 8.7.
- **Recto/verso toggle driving mirrored margins** (desmoulins) — the only
  mainstream generator treating duplex as a page-model property → § 8.1.
- **Asymmetric default margins as implicit binding allowance** —
  `left 20 mm / right 10 mm` ([tianzige](https://github.com/hanskohls/tianzige)).
- **Solve cell size from a minimum cell count** (`--min-horizontal`, tianzige)
  instead of specifying the size.
- **Convergence as 0.0–1.0 including off-page vanishing points** (incompetech
  perspective) — better than left/centre/right presets. → § 7.11.
- **Note area as a percentage of printable area** (incompetech Cornell) —
  survives page-size changes.
- **Nib width as a unit**, plus slant angle with script presets
  (Copperplate 55°, Spencerian 52°, Italic 7°) — calcbe. Incompetech has nib
  units but **no slant lines at all**. → Pflichtenheft § 15, item 4.
- **Ratio notation for line bands** (`3:2:3`, `2:5:2`) as the interface to
  multi-line rulings.
- **Rastral sizes for staff paper** and **interstaff distance in staff-line
  units** (calcbe, incompetech) → § 7.3.
- **Guaranteed minimum solution length** in mazes (`--min-path-factor`,
  default 0.5·n², enforced by re-carving; endpoints chosen as the tree-diameter
  pair restricted to border cells) — Mazerator. Naive generators produce
  complex-looking mazes with adjacent entrance and exit. → § 7.5.
- **Seed → byte-identical PDF** as an advertised guarantee (Mazerator) → § 10.1.
- **`printf`-style cell labels** with `%c %r %C %R`, label bearing, distance,
  tilt, row/column skip and origin corner (mkhexgrid) — the most sophisticated
  cell-labelling model found anywhere.
- **`fullpage` vs `textarea`** — does the pattern fill the sheet or only the type
  block (gridpapers). Almost nobody implements the distinction.
- **Dead-pixel compensation for e-ink**: Boox Note destructively downscales the
  template in its toolbar view, dropping roughly every 16th–17th pixel row; the
  generator detects the dead rows and shifts lines ±1 px
  ([BooxNoteGraphPaperGenerator](https://github.com/alansingfield/BooxNoteGraphPaperGenerator)).
  Nothing in a paper-centric model predicts this → § 9.2 `quirks`.
- **Imposition vocabulary worth stealing** (bookbinder-js): folio/quarto/octavo/
  sextodecimo, custom signature length, single-sided vs duplex vs alternate page
  rotation, margins named **fore-edge / binding edge / top / bottom**, markup for
  fold lines, cut lines, signature order marks and sewing marks.

## 6. Common complaints across all tools

1. **Print scaling destroys dimensional accuracy.** Universal. Viewers default to
   "Fit to Page" and silently print at 94–96 %. Browser-print-only tools
   (gridzzly, blanksheetmusic) are entirely hostage to it.
2. **Printer unprintable margins** clip the outer grid lines at small margins.
3. **No multi-page output** (see § 1).
4. **No incrementing page numbers.**
5. **No personalisation from a list.**
6. **No imposition, N-up, booklet, duplex or binding gutter** in any paper
   generator except desmoulins' recto/verso flag.
7. **No state persistence** — incompetech POSTs its form, so configurations are
   not linkable, bookmarkable or diffable.
8. **Line weight reduced to three named steps.**
9. **Fixed-PDF libraries cannot express unanticipated combinations** —
   printablepaper.net ships 3,300 static files; any custom colour or margin is
   unreachable.
10. **Ad and consent walls** — paperkit cites 210 ad partners, blanksheetmusic 1,192.
11. **Link rot** — printfreegraphpaper.com no longer resolves; it was the main
    source of probability paper and Smith charts.
12. **PDF-only output**; SVG from a handful, PNG at a stated DPI rarer still.
13. **Accessibility is a checkbox at best** — the only affordance found anywhere
    is printablepaper.net's static "Low Vision Writing Paper". No generator
    exposes contrast, weight or spacing as accessibility-framed controls.

## 7. Pattern families no generator serves well

German **Lineatur 1–4 / Häuschenpapier** (static PDFs only); parametric
**storyboard frames by aspect ratio** with caption boxes; comic **bleed/trim/
live-area** boards; perspective grids with **cone of vision and measuring
points** (existing tools space rays evenly, which is geometrically wrong);
**回宫格/九宫格** and 四线三格 pinyin grids.

## 8. Open questions this research did not settle

- ~~**reMarkable Paper Pro resolution.** Sources disagree: 1620 × 2160 vs
  2160 × 2880.~~ **Settled, July 2026:** 1620 × 2160 px at 229 dpi, verified on
  the author's own device. Internally consistent — diagonal 11.79 in (marketed
  as 11.8 in), physical 179.7 × 239.6 mm (marketed as 18 × 24 cm), aspect ratio
  exactly 3:4. The 2160 × 2880 figure circulating in secondary sources is wrong.
  Still open: whether the Paper Pro should be profiled as a colour device.
- **reMarkable 2 figures** (1404 × 1872 at 226 dpi) are consistent across
  sources but have **not** been verified against a device.
- **Rastral size conventions.** Two competing systems are in circulation: the
  historical numbered rastrals 0–8, where the number refers to the **total height
  of the five-line staff** (roughly 9 mm down to 4 mm), and modern practice which
  states the **staff space** (distance between adjacent lines; calcbe offers
  1.6 / 2.0 / 3.0 mm). Neither was verified against a primary typographic source.
  → Pflichtenheft § 7.3, § 15 item 4

## 9. Notable LaTeX prior art

Not competitors, but the best-engineered work in the space and worth reading
before designing anything similar:

- [`gridpapers`](https://ctan.org/pkg/gridpapers) — 11 patterns, 6 colour sets,
  per-pattern default sizes, `fullpage`/`textarea`
- [`graphpaper` class](https://ctan.org/pkg/graphpaper) — `\bilinear`,
  `\semilogx`, `\semilogy`, `\loglog`, `\polar`, `\logpolar`, `\smith`
- [`mkhexgrid`](https://github.com/kensanata/mkhexgrid) — ~40 options, best-in-class
  hex labelling
- [`pdfpages`](https://ctan.org/pkg/pdfpages) / [`pgfpages`](https://ctan.org/pkg/pgf) /
  [`paperjam`](https://mj.ucw.cz/sw/paperjam/paperjam.1.html) — imposition
- [`crop`](https://ctan.org/pkg/crop) — crop-mark modes `cam`, `cross`, `frame`,
  with `mount2` to suppress inner marks when 2-up
- [`geometry`](https://ctan.org/pkg/geometry) — `bindingoffset`, `layout=` for
  designing A5 pages on A4 sheets
- [`zitie`](https://ctan.org/pkg/zitie) / [`hanzibox`](https://ctan.org/pkg/hanzibox) —
  CJK practice grids; `zitie`'s own README warns its frame functions are very slow

**Caveat on imposition:** `pdfjam` and every `pdfpages`-based route destroy
hyperlinks, named destinations and bookmarks, because the input PDF is treated as
a vector image. Partial recovery via Oberdiek's `pax`. → Pflichtenheft § 14, M6.
