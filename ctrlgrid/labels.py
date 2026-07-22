"""Counting patterns (§ 7.10) — shared by `grid`, `polar` and `tiling`.

**Not a range with a beginning and an end, a counting pattern.** How many
labels there are follows from the generator — cells, segments, rings — and the
pattern says only *how* to count. Nobody has to chase an end mark when the cell
count changes, which is the entire point of the section.

| character | counts |
|---|---|
| `n` | digits: 1, 2, 3, … |
| `a` | lowercase: a, b, c, … |
| `A` | capitals: A, B, C, … |
| anything else | stands literally |

Repetition sets the width (`nn` gives 01, 02 … 10) and a backslash makes a
counting character literal, which is needed because `A` has to be able to mean
both — `"\\An"` is A1, A2, A3.

An explicit list is allowed wherever a pattern is. If its length does not match
the number of cells that is an error naming both numbers: neither padded nor
cut, because § 12 forbids silent mutilation and a half-labelled sheet is worse
than a refusal.

The count always starts at 1 (or `a`, or `A`). Whoever wants to start elsewhere
writes a list; a `start` key would be a second way of doing the same thing.
"""

from __future__ import annotations

from collections.abc import Sequence

from ctrlgrid.errors import DefinitionError

COUNTERS = "naA"

#: The word that switches labelling off, spelled out rather than left to an
#: empty value — § 5.1 lists `none` among the keywords that stand for "nothing".
NONE = "none"


def labels_for(
    pattern: str | Sequence[object] | None, count: int, *, field: str | None = None
) -> list[str]:
    """The labels for `count` cells, from a pattern or an explicit list."""
    if pattern is None or pattern == NONE:
        return []
    if isinstance(pattern, str):
        return [_render(pattern, index, field=field) for index in range(count)]

    entries = [str(entry) for entry in pattern]
    if len(entries) != count:
        raise DefinitionError(
            f"the label list has {len(entries)} entries but there are {count} to label. "
            "A list is used as written — it is neither padded nor cut (§ 7.10)",
            field=field,
        )
    return entries


def _render(pattern: str, index: int, *, field: str | None) -> str:
    """One label: every counting character shows `index`, in its own alphabet.

    Runs of the same counting character are one counter of that width, so `nn`
    is 01 and `nnn` is 001. A number too wide for its pattern is written in
    full rather than cut — § 12 forbids silent mutilation, and a cut label
    (`A…` for `A10`) is worthless (§ 8.9).
    """
    if not pattern:
        raise DefinitionError(
            "a label pattern cannot be empty — write `none` to leave labels out (§ 7.10)",
            field=field,
        )

    out: list[str] = []
    counted = False
    position = 0
    while position < len(pattern):
        character = pattern[position]
        if character == "\\":
            if position + 1 >= len(pattern):
                raise DefinitionError(
                    f"the label pattern {pattern!r} ends in a backslash, which escapes "
                    "nothing. Write `\\\\` for a literal backslash (§ 7.10)",
                    field=field,
                )
            out.append(pattern[position + 1])
            position += 2
            continue
        if character in COUNTERS:
            width = 0
            while position < len(pattern) and pattern[position] == character:
                width += 1
                position += 1
            out.append(_count(character, index, width))
            counted = True
            continue
        out.append(character)
        position += 1

    if not counted:
        raise DefinitionError(
            f"the label pattern {pattern!r} never counts: every cell would carry the same "
            "text. Use `n`, `a` or `A` to count, or an explicit list (§ 7.10)",
            field=field,
        )
    return "".join(out)


def _count(character: str, index: int, width: int) -> str:
    if character == "n":
        return f"{index + 1:0{width}d}"
    letters = _spreadsheet(index)
    return letters if character == "A" else letters.lower()


def _spreadsheet(index: int) -> str:
    """A, B, … Z, AA, AB — the way a spreadsheet carries on past Z (§ 7.10)."""
    letters = ""
    number = index + 1
    while number > 0:
        number, remainder = divmod(number - 1, 26)
        letters = chr(ord("A") + remainder) + letters
    return letters
