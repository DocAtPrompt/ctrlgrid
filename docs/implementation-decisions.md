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
- **`typer` 0.27 vendors click** as `typer._click`. Declaring `click` as a
  direct dependency would install a second copy whose exception classes typer
  never raises, so `cli.py` avoids needing it at all — the preset-as-command
  dispatch overrides `TyperGroup.parse_args` instead.
