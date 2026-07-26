# A sheet plan inside a notebook section. Design

**Date:** 2026-07-26. Settled with the user; belongs in the specification as part
of **§ 7.13** and in `implementation-decisions.md` as decision 55. It replaces
the fourth, deliberately temporary refusal of decision 52.

A notebook section filled by `maze` with `solution: separate_page` is refused
today. Decision 52 recorded why — § 7.13 said nothing about what a per-section
sheet plan should mean, and answering it wrongly had produced solutions printed
*before* their puzzles. This says what it means.

## What is actually broken, measured rather than assumed

`maze` is the **only** blade with a `sheets()` method, so this touches exactly one
generator, and no shipped preset or example uses it inside a notebook — nothing
committed can move.

`maze.generate` reads `page.index` twice: `page.index % 2` decides whether the
sheet is a puzzle or its solution, and `page.index // 2` is the item number that
feeds the seed. On the blade path that index counts the sheets of the run and
starts at zero. Inside a notebook it is the **document** page index, which is why
both readings were wrong and why adding a title page silently redrew every maze.

## The mechanism

**The notebook emits the pages; the handle fills them.** § 7.13's rule is
unchanged. `pages()` already decides which pages exist, so it asks the section's
blade for its `sheets()` and yields as many `DocumentPage`s per item as the plan
states.

Rejected: letting the handle expand a section. A document's page plan belongs to
the document, and the handle knows nothing about sections — teaching it would put
document internals on the handle side, against § 3.3 and against decision 50,
which settled that the notebook never touches a blade and the handle never learns
what a section is.

**A `Fill` carries the page's index within its section**, and
`pages.document_page_marks` builds the `PageContext` from that: index 0…n−1,
`count` the section's sheet total. This is the single change that fixes both
failures at once, and it is § 7.13's own sentence made true — *a section is a
definition in miniature*. A maze section now behaves page for page like a run of
its own: the parity is right, the item number is right, and unrelated furniture
before it moves nothing, because the section has its own zero.

Note what does **not** change: `{page}` in a band still counts document pages
(§ 7.13), because a notebook is flipped through. Two indices coexist and always
did — the document's, carried by the handle, and the section's, carried by the
page.

**Mirroring stays handle work.** `DocumentPage` gains `mirrored: bool`. The
reflection is about the **sheet's** vertical centre and not the pattern area's
(§ 7.5) — the reference is the physical turning edge — and only the handle knows
where the sheet is. This is exactly parallel to `SheetPlan.mirrored` on the blade
path, and it reuses `marks.mirror_x`, which already declines to reflect text.

**The reflection is applied in `pages.document_page_marks`**, the one function
that says what is on a document page — used by the writer, by the capability
pre-flight and by the media check alike (decision 50). Applying it in the write
path instead would leave the other two measuring an unmirrored page, which is the
same half-a-tool failure decision 52 is about. Mirroring changes no colour and no
stroke width, so nothing those two conclude would differ today; it would differ
the first time a check looked at a position, and that is exactly the kind of
latent split this codebase keeps paying for.

## `back_mirrored`: the pairing is forced, and said

`back_mirrored` puts the solution on the **back of the same physical sheet**, so
that holding the paper to the light lays it over the puzzle. In duplex printing
page 1 is the front of sheet 1 and page 2 its back, so a page is a front exactly
when its number is **odd**.

On the blade path that is free: the run starts at sheet one. Inside a notebook it
is not — whether a section's content begins on a front depends on the title page
and on every divider before it, which is unrelated furniture.

**So the notebook inserts one blank leaf** where the alignment needs it: if the
section's content would begin on an even page number, a blank page goes in front
of it. Measured **after** the divider, because a divider is a page like any other.
Once aligned, every following pair stays aligned, since a pair is two pages long.

The alternative — refusing `back_mirrored` in a section — was weighed and not
taken. The pairing is computable, so refusing would push arithmetic onto the user
that the tool can do. What is not acceptable is doing it silently, so the run
report says it, in the form the booklet already uses:

```
  section "Rätsel" starts on an even page, so a blank leaf was inserted before
  it — with `back_mirrored` each puzzle has to sit on the front of its sheet,
  or the solution shows through on the wrong one (§ 7.5)
```

**The blank leaf is a page, and that is not the same call the booklet made.**
`--booklet`'s padded cell draws nothing at all, because it is the *absence* of a
page — no number is printed and `{page_count}` does not count it (§ 14). This
leaf is the opposite: it is a real page of the notebook, it occupies a number a
reader will turn past, and the contents pages after it shift accordingly. So it
carries the bands like any other page and answers `{section}` with the section it
precedes — § 7.13 makes an unknown placeholder an error, and that has to stay
true on every page, including this one. Only the pattern area is empty.

**Two refusals are inherited from § 7.5 and must reach the document path.**
`back_mirrored` needs `duplex: false` or equal `inner`/`outer` margins: the
alternating gutter would shift the solution by exactly that amount. That check
exists on the blade path as `_refuse_mirroring_that_cannot_line_up`, and it has to
cover documents too — otherwise it is a check that lives on half the tool, which
is the failure decision 52 was written about.

## What `pages:` means

`pages: 10` on a section whose blade needs two sheets per item means **ten items
on twenty pages**, exactly as § 7.5 reads it for `--pages 10` on the blade path
("zehn Rätsel auf zwanzig Blättern"). One rule for both paths, and `pages:` goes
on counting items rather than switching meaning by generator.

The consequences are arithmetic and belong in the two functions that already
share it: `page_count` and `_section_starts` both count the same pages in the
same order, so the contents page keeps printing the number a reader will find.
Both now multiply a section by its plan and add the alignment leaf.

## Testing

**Without a PDF:** `page_count` and `_section_starts` agree for a maze section
with and without a divider, with and without a title page, and with an alignment
leaf; a section of ten items yields twenty pages.

**With a PDF, because that is what went wrong before:** build a notebook whose
second section is a maze with `solution: separate_page`, read it back, and check
that the solution page's drawn walls are a **subset** of the puzzle page's — that
is what "this solution belongs to that puzzle" means geometrically, and it is the
failure decision 52 describes. Then add a title page to the same definition and
confirm the maze pages come out **byte-identical**, which is the seed-stability
half of the bug.

For `back_mirrored`: the blank leaf appears only where the parity needs it (test
both parities), the mirrored page's walls are the puzzle's reflected about the
sheet's centre, and the run reports the insertion.

## Deliberately not in this version

Signature-aware placement of any other kind; a section that asks for a sheet plan
*and* an explicit page count in sheets; and `back_mirrored` across a section
boundary. Each is named so a later reader knows it was weighed.
