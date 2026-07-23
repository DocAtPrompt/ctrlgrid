# Implementation decisions

Where the specification
([`pflichtenheft-vorlagengenerator.md`](../pflichtenheft-vorlagengenerator.md))
was **genuinely silent or internally ambiguous**, and a decision had to be made
to write the code. Each entry names the section it belongs to, what was chosen,
and why.

This file is not a place to record disagreement with the specification. Where
the specification decides something, it decides it — say so and name the
section instead. These are the gaps.

Order is roughly the order they came up.

---

## 1. `extent` bounds which lines exist, not how long they are

**§ 7.1, § 7.6.** The YAML comment in § 7.1 calls `extent` "quer zur
Laufrichtung", which alone could mean either axis.

Two other passages settle it. § 7.6 says "quer zur Laufrichtung **der Linien**"
when it introduces `radial_extent` for the case that runs the other way, and
§ 7.1's slanted-families paragraph says `offset` and `extent` are measured
"**senkrecht zur Linienrichtung**". Both mean perpendicular to the line — the
same axis `offset` and `base_spacing` live on.

So an extent selects *which* lines are drawn. Nothing shortens a line, which
also keeps § 2 intact: there is still no way to put a stroke of chosen length at
a chosen coordinate.

## 2. Snapping and remainder handling stay on the handle side

**§ 8.3, § 8.5, § 3.6.** Both are settings of the handle's `pattern:` block, but
the numbers they need belong to the blade: with a cycle like `[1, 1, 2]` the
leftover does not follow from the base spacing.

The alternative was to pass the pattern block into `generate()`. Rejected: § 8.3
makes `snap` an **error** for `staves`, `grid`, `maze`, `tiling`, `form` and
`polar`, so six of the eight blades would receive a parameter they are required
to reject.

Instead the blade answers a question — `periodic_axes()`, returning `AxisPeriod`
objects that can say how much of a given extent the family actually uses — and
the handle shrinks the pattern area and shifts the origin, exactly as § 8.3
describes it ("kann der Musterbereich verkleinert werden"). `generate()` is
unchanged and blades still know nothing of page geometry (§ 3.3).

## 3. `remainder` defaults to `center`

**§ 8.5.** The specification lists `end | center | whole_cycles` with `end`
first, which elsewhere marks the default — but the sketch in § 5.2 shows
`{x: center, y: center}`, and § 8.3 speaks of centring as the ordinary case
("bei `center` gleichmäßig auf beide Seiten").

Chosen: `center`. On a 5 mm grid over a 287 mm area the 2 mm leftover reads as a
mistake at one edge and as breathing room split across two. It does not affect
`millimeter-a4`, where a 1 mm grid divides both A4 dimensions exactly.

Note the asymmetry with `snap`, which defaults to `none` for a reason
§ 8.3 states outright: snapping changes the geometry § 8.1 computed. `remainder`
only moves what is left over after that computation.

## 4. `governing` is required only when families genuinely disagree

**§ 8.3.** The specification says that with several families on one axis, one
must be marked `governing`, otherwise it is an error naming the families.

Read literally against a `center` default (decision 3), every two-family axis
would fail out of the box — and two families on one axis is ordinary, not
exotic.

Chosen: a marked family wins; families that agree on their period need no mark,
because there is nothing to disambiguate; only real disagreement is an error,
and it names both base spacings. Two marked families on one axis is also an
error.

## 5. An explicitly named axis with nothing periodic on it is an error

**§ 8.3, § 8.5.** § 8.3's principle is that whoever writes a setting down
expects an effect, which is why `snap` on a non-periodic generator is an error
rather than silent ineffectiveness.

Applied to axes: `remainder: {x: center}` on a definition with only horizontal
families is an error. The scalar shorthand `remainder: center` names no axis and
stays quiet where there is nothing to place — it means "both, wherever there is
something".

This is why `AxisPair` carries an `explicit` flag: the distinction is between
the user naming an axis and the user naming a value for both.

## 6. Limited families do not vote on the surplus

**§ 7.1, § 8.3, § 8.5.** A family with `count` or an `extent` does not fill the
pattern area, so it has no say in how that area's leftover is placed, and
`periodic_axes()` leaves it out. Snapping the sheet to the single red margin
rule of an exercise book would be absurd.

## 7. `whole_cycles` leaves its freed space at the far end

**§ 8.5.** The specification says the cut cycle "entfällt" but not where the
space it frees goes. Since the three modes are one enum, `whole_cycles` cannot
also be centred.

Chosen: it behaves like `end` for placement — pattern at the origin, space at
the far end.

## 8. `snap: pixel` refuses on paper permanently, not until M5

**§ 8.3.1, § 9.1.** § 8.3.1 allows it only with a device profile, and those
arrive with M5 — so "arrives with M5" alone would be misleading. § 9.1 is
explicit that `assumed_dpi` is a yardstick for the media check and nothing else,
and geometry must never rest on a guessed number.

The message says both halves: it needs a device profile, and device profiles
arrive with M5.

## 9. The background gets no layer of its own

**§ 5.2, § 6, § 3.6.** A page background must be painted under everything, but
§ 6 fixes the vocabulary at three layers — `pattern`, `frame`, `overlay` — and
the vocabulary is contract, not an ascending scale.

Since the writer draws in the order marks arrive and never sorts (§ 3.6), *being
emitted first* is what "underneath" means. So the background is a `Polygon` on
`Layer.PATTERN`, emitted before the blade's marks. The page loop reads as the
stacking order itself: background, pattern, border, hole marks, bands, stamp.

## 10. The name-list mode turns on whether a count was written down

**§ 9.4.** The two modes are "data-driven, one sheet per entry — the default
with `--names`" and "fixed count, entries repeated or cut". The specification
does not say how to tell them apart when `pages.count` has a default.

Testing the *value* would be wrong: `count` defaults to 1, so a 27-name list
would produce a single sheet. The check therefore asks whether the key was
actually set (`model_fields_set`), which makes the bare
`ctrlgrid millimeter-a4 --names class3b.txt` do the obvious thing while
`--pages 3` or a `pages.count:` in the definition takes the count back over.

## 11. Blank lines in a name list are dropped

**§ 9.4.** Not stated. Every editor leaves a trailing newline, and a nameless
sheet is not something anyone means, so blank lines go — including ones left in
the middle.

## 12. A cover sheet that does not fit is refused, never scaled

**§ 8.8, § 8.2.** § 8.8 fixes the calibration figures at 50 mm and 100 mm and
says nothing about formats too small to hold them. A6 between its margins
leaves 95 mm, so the question is unavoidable.

Shrinking the figures is the one answer that is out of the question: a square
labelled "50 mm" that measures 38 mm would produce exactly the wrong verdict
in the one measurement the page exists for. The run is therefore refused, with
both numbers in the message, and the refusal happens in `preflight` so that
`check` reports it and nothing is written (§ 12 point 13).

The *summary* is treated differently, because it is written by the tool rather
than by the user: it shrinks to fit the width and, at the smallest readable
size, truncates with the ellipsis § 8.9 makes mandatory. § 8.9's refusal is
right for a user's own text — nobody can act on "the tool's own summary line is
2 mm too wide".

## 13. `--cover` only ever switches the cover on

**§ 8.8, § 11.** The flag is a wish for one run. There is no `--no-cover`: the
absent flag means "the definition decides", and a third state would need a
spelling for "off, whatever the definition says" that nobody would remember.
The same holds for `--stamp`, which also has no eraser.

## 14. The cover carries the definition's name *and* a checksum

**§ 8.8.** The specification asks for "name or checksum". It gets both, in one
line: a preset copied with `ctrlgrid show … > mine.yaml` and then bent keeps a
name that says nothing about what changed. Twelve hex digits of SHA-256 over
the definition text — enough for a human comparing two sheets, and explicitly
not a signature.

The cover is otherwise stable input to stable output, so § 10.1's
byte-identical promise survives it: no clock, no randomness, and the version
string only changes when the version does. That is also why § 8.8 excludes the
page from golden comparisons (§ 13.2).

## 15. A font file travels through the seam as a token, not a new mark field

**§ 10.3, § 6, § 3.6.** Stage 2 has to tell the writer *which file* to set text
in, and the obvious move — a second field on the `Text` mark — is the one § 6
forbids: the mark vocabulary is contract, and it does not grow because a
feature arrived.

It does not need to. `family` was always a string the writer resolves; stage
1's `serif | sans | mono` are three spellings of it and `file:/absolute/path`
is a fourth. `FontSpec.token` produces it, `writers/pdf.py` resolves it, and
every other writer inherits the same convention for free. The resolved path
goes in, not the raw text: `~` is expanded once, at the seam, so two
definitions naming the same file in different ways embed one font and not two.

## 16. The licence check runs in the loader, the embedding in the writer

**§ 10.3, § 12, § 3.3.** § 10.3 requires refusing a font whose `fsType` forbids
embedding, and § 12 requires the refusal to point at the line that named it —
which the writer, three seams away from the YAML, cannot do.

So `loader` opens every named font file while it still has the document tree,
and attaches field and line; `fonts.py` parses and judges; `writers/pdf.py`
only embeds. This also satisfies § 12 point 13 without further work: the file
is opened before any page exists, so `check` reports a bad font and a run
aborts completely rather than half way through.

`fontTools` is confined to `fonts.py` by `tests/test_architecture.py`, on the
same reasoning as reportlab: a second writer should inherit the licence check
rather than reimplement it. Reportlab could not do the job anyway — it parses
`OS/2` for metrics and never reads `fsType`.

A font with no `OS/2` table at all is treated as installable. Refusing every
font from before the table existed would be absurd, and it is what every other
PDF producer does.

## 17. The dash cycle is the one cycle that is not position-wise

**§ 5.3, § 7.1.** § 5.3 defines a cycle as a list applied "positionsweise auf
die laufenden Marken" and then lists `dash: [2, 1]` in the same table as
`weight: [1, 1, 2]`. Taken literally that would mean line 0 is dashed 2 mm,
line 1 is dashed 1 mm — which is not what the row is called: it is called a
`Strichel-/Punktmuster`, a dash pattern, and a pattern belongs to one mark.

So `dash` describes *one* mark and applies to every mark of the family, while
every other cycle steps along the marks. Two consequences follow, and both are
tested: the pattern is identical on every line of a family, and the dash cycle
does **not** enter the effective period, which counts marks.

`style` supplies the numbers when none are written: `dashed` is `[3, 2]` and
`dotted` is `[0, 2]`, both against a `base_dash` of 1 mm. A zero-length
on-segment with a round cap *is* a dot — the same trick § 10.1 prescribes for
the `dots` blade, which is why `cap` is in the mark vocabulary at all. Writing
`dash:` or `base_dash:` next to `style: solid` is an error rather than a
no-op (§ 5.1).

## 18. A free page size is taken as written, never stood upright

**§ 9.1.** The format table and the device profiles are stored portrait, "one
single convention for both data files", and `orientation` turns them. A free
size in a definition is not one of those files, and applying the same
normalisation would break § 9.1's own example: `210x99mm` is a wide strip, and
standing it upright hands back a sheet nobody asked for.

So a free size is width first, exactly as written, and `orientation: landscape`
swaps whatever it finds — which is the same sentence for both sources, even
though "portrait" means the table's convention in one case and "as you wrote
it" in the other.

The unit may stand once at the end (`210x99mm`, the form § 9.1 uses) or on both
sides (`210mmx99mm`), because that is what people type. Everything else goes
through the ordinary unit parser, so `px` still refuses by naming device
profiles (§ 9.2) rather than by looking like a typo.

## 19. Image paths are relative to the definition file

**§ 5.2.** The example is `image: "logo.png"`, and nothing says what that is
relative to. The working directory is the wrong answer: a definition and its
logo travel together, and where the shell happens to stand when the command
runs is not a property of the sheet. So paths resolve against the directory of
the definition file, and a definition that arrived as text — a preset — falls
back to the working directory, because it has no directory of its own.

The file is opened in the loader, like a font (decision 16), so the message can
name the line and § 12 point 13 holds without further work.

**PNG is decided by the signature, not the extension** (§ 13). A `.png` that is
really a GIF is named as such, and a `.svg` gets a message about SVG rather
than about a broken file — § 13 rules SVG out for a reason, and "unknown file
type" would hide it.

## 20. An image field is measured like text and refused like nothing else

**§ 8.9, § 8.4.** § 8.9 lays out the three fields and their widths for text,
then adds one sentence about images: the same, only without truncation. So an
image takes part in the width split of § 8.9 with the width its own
proportions give it at the height that was asked for, and `cut: true` does not
reach it — a logo fits or the run is refused.

The height is checked against the band the same way a font size is (§ 8.4,
§ 12 point 13) and never derived from the picture, or page 1 with a tall logo
would have a different pattern area than page 7.

`layout_band` therefore returns `Mark` rather than `Text`. Nothing else in the
seam moved: `Image` has been in the vocabulary since M1 (§ 6), which is what
made this a change to two modules instead of five.

## 21. Seam 2 grew a fourth query rather than letting `generate` raise

**§ 3.6, § 7.6, § 12 point 13.** § 7.6 requires segment labels to be measured
*before* rendering, and only the blade can measure them — but only the handle
knows the pattern area, which is what they have to fit into. The obvious move
is to let `generate` raise when it meets a label that does not fit. That
breaks the rule the whole pre-flight exists for: `generate` runs while pages
are being written, so the file would already be half there.

So the blade got `check(cfg, area, q)`, called once by `preflight` against the
area it will be handed. `generate` is unchanged, as it was through `snap`,
`remainder` and `describe` — four queries now, and the one method that
produces marks has never moved.

This bit for real during M3: the ring-label count mismatch was raised from
`generate` and only surfaced when a real sheet was built, not by any test.
Both the check and a test that nothing is written now sit in the pre-flight.

## 22. `supports_snap` is a statement, not an absence

**§ 8.3, § 7.6.** § 8.3 lists the blades for which snapping is an **error** —
`polar` among them. That could have been inferred from `periodic_axes`
returning nothing, and it would have been wrong: "no periodic family along x"
and "snapping does not apply to this pattern" are different sentences, and only
the second may be answered with a refusal that names the generator.

So the blade declares `supports_snap`, and the handle refuses before it
computes any geometry — no half-fitting answer is produced on the way.

## 23. In polar coordinates the cycles count *drawn* rings

**§ 5.3, § 7.6.** Mark 0 of a family sits on the origin (§ 3.5), and in polar
coordinates the origin is the centre point: a circle of radius 0 is not a mark.
The question the specification does not answer is what happens to the weight
and colour cycles then.

They count drawn rings. `weight: [1, 1, 1, 2]` makes every fourth *visible*
ring heavy, which is what it says; counting the invisible circle at the centre
would put every cycle one step out of phase with what is on the paper.

Two smaller placements go with it, both from what a real sheet looked like:
a **segment** label belongs to the wedge between two spokes, not to a spoke —
§ 7.6's twelve 30° spokes carry 1 … 12 — and **ring** labels run up the
bisector of the segment that contains straight up, because straight up is
where a spoke runs on every family that divides 90°, and a number printed over
a line is unreadable.

## 24. Clefs come from an embedded music font, not a vector path (resolved, § 15.3)

**§ 7.3 against § 6.** § 7.3 originally wanted clef glyphs "as stored vector
paths", which would make the PDF font-free. § 6 fixes the mark vocabulary at six
primitives and calls it contract rather than a build stage — and none of the six
is a curve path. `Arc` and `Polygon` cannot draw a treble clef; they can draw
something that looks nearly like one, which is exactly the "almost right" sheet
§ 5.1 calls the worst failure there is.

**Resolved in § 15.3:** a clef becomes a `Text` mark in an *embedded music
font*, not a seventh primitive. § 7.3's real goal was not "font-free" for its own
sake but *self-contained*, and fonts stage 2 (§ 10.3) already embeds and subsets
— so the PDF carries only the few clef glyphs and stays self-contained, with the
six-primitive vocabulary and § 15.2 (no free paths) both untouched. The two
rejected options are named there: a seventh path primitive (against § 6 / § 15.2,
and work for every future writer) and dropping clefs (§ 7.3 names them, and
pre-printed clefs are genuinely wanted). A small OFL font ships, overridable via
`font: {file:}`.

Until then this is now **deferred work, not an open question**: `clef: none`
works and every named clef refuses with a message that names **M9** (§ 14), the
milestone that builds it — the same "deferred features name their milestone"
discipline every other unbuilt option follows (§ 5.1).

## 25. Staves fill from the top, and the leftover stays at the bottom

**§ 7.3.** Nothing says where a short block of systems sits in a taller
pattern area. Music is read from the top down and a page of manuscript
normally keeps its spare room at the foot, so the first system starts at the
top edge of the pattern area.

Not `remainder` (§ 8.5): that places the leftover of a *periodic* family, and
a stack of systems is a group with a gap rule of its own — the same reason
§ 8.3 refuses snapping here.

## 26. `min_path_factor` is off by default, because the reachable value is the algorithm's

**§ 7.5.** The YAML sketch shows `min_path_factor: 0.5`, and § 7.5 argues well
for the feature: a naive generator regularly produces mazes whose solution is
laughably short behind a complicated-looking picture. What it does not say is
what the default should be — and 0.5 turns out to be unreachable for two of
the three algorithms it also prescribes.

Measured over thirty carvings each, as a share of the cells:

| algorithm | 10x10 | 20x20 |
|---|---|---|
| `backtracker` | 0.44 | 0.36 |
| `kruskal` | 0.23 | 0.14 |
| `prim` | 0.19 | 0.10 |

A single built-in number would therefore be toothless for a backtracker and
unreachable for prim, and it falls further as the grid grows. So the demand is
the user's to make: the default is 0, the presets set a real one, and the
refusal quotes this table so the number can be chosen rather than guessed.

The retry bound is 200. § 7.5 asks for regeneration on a shortfall; it does
not ask for a hang, and a factor nobody can reach has to end in an error that
says how far it got.

## 27. Sheets-per-item is a plan the blade states and the handle carries out

**§ 7.5, § 3.** `solution: separate_page` doubles the sheets, makes odd ones
puzzles and even ones solutions, doubles `{page_count}`, and gives each entry
of a name list two sheets that share a name. All four are properties of the
*page loop*, which is the handle's (§ 3) — but only the blade knows that they
apply.

So the blade returns a `SheetPlan` (`per_item`, and which sub-sheets are
mirrored) and the handle does the rest: it multiplies the count, keeps the
numbering running across every sheet, indexes names by item rather than by
sheet, and mirrors the pattern layer where the plan says so. Default is one
sheet per item, so no other blade has to say anything at all.

Mirroring lives with the handle for a second reason: § 7.5 mirrors about the
**sheet's** vertical centre, not the pattern area's, because the reference is
the physical turning edge — and a blade never learns where the sheet is
(§ 3.3). `mirror_x` sits beside `translate` in `marks.py`, the one other place
where coordinate systems cross, and it deliberately does not reflect *text*:
mirrored writing on the back is the one thing nobody wants.

## 28. `rest` and a measure left out are the same rule

**§ 7.8.** The table lists them separately: `rest` is "the remaining space",
an omitted measure is "an even split of the rest among all without one". Those
are the same sentence twice, so they are one implementation: every entry that
is `rest` or absent takes an equal share of what the fixed and percentage
entries leave.

Keeping both spellings is still right. The omitted one is the commonest case
by far — three equal fields are written by saying nothing — and `rest` is the
written form for when one field among several sized ones should take what is
left, where silence would read like an oversight.

## 29. `form` measures in the pre-flight with the same code it draws with

**§ 7.8, § 12 point 13.** `form` is the first blade whose *layout* depends on
text metrics: a title decides how much room is left below it for the writing
area. That makes the pre-flight more than a check — it has to lay the whole
form out.

So `check()` runs `_place()` in full and measures every title, every option
row and every fixed line count against the cells that will actually be drawn,
and `generate()` calls the same `_place()`. The two cannot disagree, and a
form that does not fit is refused before the file exists rather than half way
through it.

## 30. `px` resolves through pydantic's validation context, not a wrapper

**§ 9.2, § 5.1.** `px` is unlike `sp`: `sp` is generator-local and resolved
late, once `stave_space` is known, so it travels as a wrapper through the whole
seam. `px` is document-global and its resolver — the device density — is known
at load time, before any section is validated. So it needs no wrapper: the
loader settles the medium first, puts the density in pydantic's validation
`context`, and the same `_as_length` that handles every other unit resolves
`px` against it. On paper the context is empty and `px` stays an error, because
a format's `assumed_dpi` is a yardstick and not a resolution (§ 8.3.1).

The medium therefore has to be known before the sections are validated, which
is why `_resolve_device` peeks the device id from the raw value rather than
from the model — the model is exactly what the density is needed to build.

## 31. `quirks` is modelled and carried, but no quirk ships

**§ 9.2.** § 9.2 provides `quirks` deliberately, with a concrete example: a
Boox Note drops roughly every 16th pixel row in one view, and a generator
would have to shift lines by ±1 px to survive it. But no shipped profile is a
Boox, and inventing the dead-row pattern for a device nobody here can test is
exactly the guessed number § 9.2 says is worse than no profile at all.

So `DeviceProfile` carries `quirks` as a validated, empty tuple, and the field
exists for the first verified contribution to fill — not for me to guess.

## 32. The grey-collision check is a threshold, not equality

**§ 12.1.** § 12.1's colour finding is "two colours that yield the *same* grey
value", and its worked example is `#7799bb` and `#4466aa` — the millimetre
preset's own grid and accent. But those are 48 luminance levels apart (Rec.
709), not the same: read strictly, the finding would never fire on the case the
spec chose to illustrate it.

So the check flags two colours whose greys are **within** a threshold, set at 48
so the documented pair fires. The wording is honest about it — "48 grey levels
apart, they read as one tone" — rather than claiming they are identical. The
consequence for a definition is a clear guideline: on a grayscale screen an
accent needs more than ~1/5 of the range between it and the base to survive.

## 33. Two media findings are device-only, and the reason is resolution

**§ 12.1.** § 12.1 lists its findings without splitting them by medium, but two
of them only make sense on a low-resolution screen. The **1–2px stepped** line
is about weak e-ink antialiasing — a 600dpi printer renders 1.9px cleanly. The
**uneven-cells** finding (45.08px drawn as 45/46) is visible on a 229dpi screen
and imperceptible at 600dpi, where the ±1px swing is 1/600 inch.

Both are therefore gated on a device being active. The **sub-1px** and
**under-3px-merge** findings stay general: a stroke that rounds away and a
spacing that flows into a grey area are as real on paper as on a pad.

## 34. Pixel snapping reaches the blade through the page context

**§ 8.3.1, § 3.3.** `snap: pixel` is unlike the other two snap modes: they
shrink the pattern area (handle-side) while the blade fills it with its own
unchanged spacing, but pixel snapping changes the *step* — it rounds every gap
to a whole pixel — so it has to reach where positions are computed, inside the
blade's call to `Cycle.positions`.

That needs the device to reach the blade, which § 3.3 keeps geometry out of.
The resolution: `PageContext` grows a `pixel_snap` field carrying, per axis,
the device density in dpi. A density is a property of the *medium*, not of the
page's layout — it says nothing about margins or where the pattern sits — so
§ 3.3 holds. The handle computes it in `place_pattern`, the blade reads it as
`page.pixel_of(axis)`, and only `lines` and `dots` (the snap-capable periodic
blades) consult it. `generate`'s signature still has not changed.

## 35. Pixel snapping rounds steps in whole pixels, and keeps the pixel exact

**§ 8.3.1.** Two traps, both from the arithmetic. First, § 8.3.1 says round
every *step*, not the accumulated position — because rounding accumulated
micrometre positions leaves a uniform 45.08px grid alternating 45/46px, the
very unevenness the mode removes. `Cycle._walk_pixels` therefore keeps a
running total in whole pixels and turns only the emitted position into µm.

Second, the pixel size must stay exact — `25400 / dpi`, not pre-rounded to a
whole micrometre. Rounding 25400/229 to 111µm and multiplying by 45 gives
4.995mm; the true 45-pixel measure is 4.991mm, which is what § 8.3.1 quotes and
what the device actually draws. So the density is carried, not a rounded pixel,
and the exact size is used in the one final rounding to µm.

## 36. Imposition renders whole pages, then translates them — no PDF post-pass

**§ 14, § 3.3.** § 14 says imposition "works on finished pages", which reads
like a post-process on the output PDF — and a `pypdf`-based re-imposition would
be the obvious route. It is not taken, for two reasons. It would make a
PDF-manipulation library a runtime dependency, and it would put page geometry
in a second place outside `pages.py`.

Instead the page loop renders each logical page to its own coordinates as
before, collects the marks, and the imposed writer translates each whole page
onto its cell of the larger sheet — the same `translate` that already places
the pattern origin, one level up. "Finished pages" is honoured exactly: the
pattern is untouched and complete before anything decides where it lands. The
writer never learns imposition happened; it draws translated marks like any
others, so a second writer (PNG, M7) gets N-up for free.

Two consequences the specification names are carried here. The cover sheet
keeps the page size and its own sheet (§ 8.8) — its 50 mm square must stay
50 mm — and per-page bookmarks are dropped under imposition (§ 14 notes it
destroys links): a bookmark would point at a whole imposed sheet rather than
the page, which is worse than none.

## 37. Crop marks are opt-in, and appear only where the margin holds them

**§ 14.** § 14 asks for "optional crop marks" and the § 11.1 flag table does
not name the switch, so this adds `--crop-marks`, opt-in — most of the time the
pages butt together and the marks would have nowhere to go anyway.

They are cut *guides*, not a frame: short ticks reaching in from the sheet edge
towards each cut line, in the margin strip, never crossing the pages. Where the
block fills the sheet in one direction — a 2×2 of A6 on A4 leaves 0.5 mm top
and bottom — there is no room, and rather than draw a mark over a page the tool
simply omits it on that pair of edges. Every length is clamped to the margin
actually available, so a tight sheet gets shorter marks instead of none.

## 38. The pre-flight measures with an oracle, not with the output writer

**§ 10.2, § 3.6.** Every measurement in the pre-flight — band layout, label
fitting, the media check, the cover — needs font metrics, and § 3.6 makes the
writer the only source of them. That held while PDF was the only writer. The
PNG writer breaks it: it has no font file, so it cannot answer a metric.

The fix keeps the seam honest. Metrics are *data* — the fixed widths of the
standard PDF fonts — not rendering, so the pre-flight measures with a metrics
**oracle** (a `PdfWriter` that never opens a file), and consults the real
writer only for its `capabilities()`. For a PDF run the two are the same
object; for PNG the oracle stands in for measuring while the PNG writer's
missing `text` capability is what the run is checked against.

## 39. What a writer cannot render is refused by sampling the marks

**§ 10.2, § 14.** § 10.2 says the vocabulary is complete from M1 and a writer
grows into it, with the pre-flight refusing the missing feature by name. Until
M7 nothing exercised this — the PDF writer does everything. The PNG writer is
the first that does less (no text), so the check finally had to exist.

It samples one page's marks with the oracle and maps each to the capability it
needs, rather than reading the config — so it is right for every blade without
knowing any of them. Text has three extra sources the sample would miss because
they are the handle's, not the blade's: header and footer fields, the stamp,
and the cover's calibration labels, each added explicitly. The message names
the missing capability and, for text, the three ways out: a font file, no text,
or PDF.

---

## Smaller calls, for completeness

- **Rounding is ties-away-from-zero**, not Python's banker's rounding, and runs
  in `Decimal`. § 14's byte-identical requirement makes tie behaviour a
  correctness question, not a preference (§ 3.3).
- **`none` and an absent key mean the same for colours**, since § 5.1 lists
  `none` among the keywords that stand where a measure could.
- **Mark 0 of a family sits on the pattern origin** — bottom edge for a
  horizontal family, left edge for a vertical one. The only choice consistent
  with the bottom-left origin of § 3.5.
- **The `auto` stamp size targets 80 % of the sheet width**, measured through
  `text_width` rather than guessed. A diagonal word touching both edges would be
  clipped by the non-printable border on nearly every printer (§ 8.6).
- **Outline keys come from the page index**, never a counter or random value, or
  the table of contents alone would break § 10.1's byte-identical guarantee.
- **Angles run in micro-degrees** inside `polar`, for the reason § 3.3 gives
  for micrometres: a full turn is then the exact integer 360 000 000, so twelve
  30° spokes close the circle instead of ending at 359.999999°. It also lets
  the angular family go through the very same `Cycle.positions` as a spacing.
- **`typer` 0.27 vendors click** as `typer._click`. Declaring `click` as a
  direct dependency would install a second copy whose exception classes typer
  never raises, so `cli.py` avoids needing it at all — the preset-as-command
  dispatch overrides `TyperGroup.parse_args` instead.
