"""Parsing and normalisation of the units a definition file may use (§ 5.1).

Everything the loader touches passes through here, and nothing downstream ever
sees a string with a unit again (§ 3.6, seam 1).

Two representations, because § 3.3 demands two:

* **`um`** — integer micrometres, for positions and spacings. They accumulate,
  and repeated float addition drifts over 300 lines, destabilises golden
  comparisons and is no foundation for a tool whose promise is dimensional
  accuracy (§ 8.2).
* **`mm`** — unrounded float, for stroke widths, diameters and opacity. Those
  never accumulate, and micrometres would be too coarse: 0.1 pt is 35 µm, so a
  single rounding step is 3 % — visible on a fine grid.

Both sit on one value object together with **`raw`**, the text the user wrote.
Reporting "52.9 µm" back to someone who wrote `0.15pt` is exactly the kind of
unusable error message § 12 forbids.

Conversion runs in `Decimal`, not float: 8.5 in must be 215900 µm exactly, and
ties must fall the same way on every platform and every Python version, or
acceptance criterion 3 — byte-identical repeat runs — is lost.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from ctrlgrid.errors import DefinitionError

# Micrometres per unit. `pt` is the printer's point, 1/72 in, and stays a
# fraction rather than a rounded decimal so that 72pt is 25400 µm exactly.
_LENGTH_UNITS: dict[str, Decimal] = {
    "mm": Decimal(1000),
    "cm": Decimal(10000),
    "in": Decimal(25400),
    "pt": Decimal(25400) / Decimal(72),
}

# Units that exist in the specification but cannot be resolved here.
# Naming them separately is the difference between an answer and a hunt for a
# typo: `px` is not misspelled, it is unavailable (§ 5.1).
_DEFERRED_UNITS: dict[str, str] = {
    "px": (
        "unit 'px' requires a device profile, which resolves pixels to a physical "
        "size (§ 9.2) — device profiles arrive with milestone M5; use mm, cm, in or pt"
    ),
    "sp": (
        "unit 'sp' (stave spaces) is local to the `staves` generator (§ 7.3) and has "
        "no meaning outside it"
    ),
    "%": "unit '%' is only allowed where a reference measure is fixed (§ 7.8)",
    "dpi": "unit 'dpi' is only allowed in device profiles (§ 9.2)",
}

_ANGLE_UNITS = {"deg"}

# A number, optional whitespace, then the unit. `%` is matched so that it can
# be refused by name rather than as "no unit at all".
_QUANTITY = re.compile(r"^([+-]?(?:\d+\.?\d*|\.\d+))\s*([A-Za-z%]*)$")


@dataclass(frozen=True, slots=True)
class Length:
    """A length, in both representations § 3.3 requires, plus its source text."""

    um: int
    mm: float
    raw: str

    def __str__(self) -> str:
        return self.raw


@dataclass(frozen=True, slots=True)
class Angle:
    """An angle in degrees, mathematically positive, 0° pointing right (§ 3.5)."""

    deg: float
    raw: str

    def __str__(self) -> str:
        return self.raw


def parse_length(value: object, *, field: str | None = None) -> Length:
    """Normalise a length such as `5mm`, `8.5in` or `0.15pt`.

    A bare number is refused rather than assumed to be millimetres: § 5.1 puts
    the unit on the value, and bare numbers are cycle multiples elsewhere in
    the same file. Guessing here would make `spacing: 5` and `base_spacing: 5`
    mean two different things that look the same.
    """
    text, number, unit = _split(value, field=field, expected="a length")

    if unit in _LENGTH_UNITS:
        exact = number * _LENGTH_UNITS[unit]
        return Length(um=_to_micrometres(exact), mm=float(exact / 1000), raw=text)

    if not unit:
        raise DefinitionError(
            f"{text!r} has no unit — write a length with one of mm, cm, in, pt "
            f"(for example {text.strip()}mm). Bare numbers are cycle multiples (§ 5.1)",
            field=field,
        )

    raise DefinitionError(
        _unknown_unit(unit, expected="a length", known=_LENGTH_UNITS), field=field
    )


def parse_angle(value: object, *, field: str | None = None) -> Angle:
    """Normalise an angle such as `45deg`."""
    text, number, unit = _split(value, field=field, expected="an angle")

    if unit in _ANGLE_UNITS:
        return Angle(deg=float(number), raw=text)

    if not unit:
        raise DefinitionError(
            f"{text!r} has no unit — write an angle as deg (for example {text.strip()}deg)",
            field=field,
        )

    raise DefinitionError(_unknown_unit(unit, expected="an angle", known=_ANGLE_UNITS), field=field)


def _split(value: object, *, field: str | None, expected: str) -> tuple[str, Decimal, str]:
    """Return the source text, its numeric part and its unit."""
    if not isinstance(value, str):
        raise DefinitionError(
            f"expected {expected} written as text with a unit, got {value!r}",
            field=field,
        )

    text = value
    match = _QUANTITY.match(text.strip())
    if match is None:
        raise DefinitionError(
            f"{text!r} is not {expected} — expected a number followed by a unit",
            field=field,
        )

    try:
        number = Decimal(match.group(1))
    except InvalidOperation:  # pragma: no cover — the regex already guarantees this
        raise DefinitionError(f"{text!r} is not a number", field=field) from None

    return text, number, match.group(2)


def _to_micrometres(exact: Decimal) -> int:
    """Round to whole micrometres, ties away from zero.

    Not `round()`: that rounds ties to even, so a value landing exactly on .5
    would depend on which side of it the last digit fell. Determinism is an
    acceptance criterion (§ 14, point 3), not a preference.
    """
    return int(exact.quantize(Decimal(1), rounding=ROUND_HALF_UP))


def _unknown_unit(unit: str, *, expected: str, known: object) -> str:
    if unit in _DEFERRED_UNITS:
        return _DEFERRED_UNITS[unit]
    allowed = ", ".join(sorted(known))  # type: ignore[arg-type]
    return f"unknown unit {unit!r} — {expected} takes one of: {allowed}"
