"""The validated document model — seam 1 of § 3.6.

Everything the handle owns lives here: page format, margins, header, footer,
the pattern block and the page count (§ 3). What a blade owns lives with the
blade, as `config_model` on the generator (§ 3.6, seam 2) — this module never
learns what a family is.

Three rules from the specification shape the whole file:

* **Unknown keys are errors** (§ 5.1). A typo in a bent preset copy otherwise
  produces a PDF that is *almost* right, which is the worst failure class there
  is. `extra="forbid"` does that work.
* **A key the specification describes but this milestone does not implement
  says so by name.** Reporting `border` as an unknown key would be a lying
  error message: it is not a typo, it is M2. Silence would be worse still — the
  user would get a PDF without the border they asked for.
* **After validation there are no unit strings left** (§ 3.6). Lengths arrive
  as text and leave as `Length`.
"""

from __future__ import annotations

from typing import Annotated, Any, ClassVar, Literal

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, model_validator

from ctrlgrid.errors import DefinitionError
from ctrlgrid.units import Length, parse_length


def _as_length(value: Any) -> Any:
    """Turn definition text into a `Length`, leaving anything else to pydantic."""
    if isinstance(value, Length):
        return value
    try:
        return parse_length(value)
    except DefinitionError as error:
        raise ValueError(error.message) from None


def _non_negative(value: Length) -> Length:
    if value.um < 0:
        raise ValueError(f"must not be negative, got {value.raw}")
    return value


def _plain_text(value: Any) -> Any:
    """Refuse the `{ image: … }` form of a header field until it is supported."""
    if isinstance(value, dict):
        raise ValueError(
            "images in headers and footers arrive with milestone M2 (§ 5.2); "
            "this milestone takes plain text"
        )
    return value


LengthField = Annotated[Length, BeforeValidator(_as_length)]
TextField = Annotated[str | None, BeforeValidator(_plain_text)]


class Section(BaseModel):
    """Common base: no unknown keys, and a name for every deferred one."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    #: Keys the specification defines and this milestone does not implement,
    #: mapped to the sentence the user gets instead of "unknown key".
    deferred: ClassVar[dict[str, str]] = {}

    @model_validator(mode="before")
    @classmethod
    def _refuse_deferred_keys(cls, data: Any) -> Any:
        if isinstance(data, dict):
            for key, note in cls.deferred.items():
                if key in data:
                    raise ValueError(f"`{key}` {note}")
        return data


class Margin(Section):
    """The non-printable border (§ 8.1) — a device property, not a design size.

    Named `inner`/`outer` rather than `left`/`right` so the wider margin stays
    at the binding edge when `duplex` swaps them on even pages. On single-sided
    output `inner` is simply always left.
    """

    deferred: ClassVar[dict[str, str]] = {
        "left": (
            "is not a margin name — margins are `inner` and `outer` so that the wider one "
            "stays at the binding edge under duplex (§ 8.1); on single-sided pages "
            "`inner` is the left one"
        ),
        "right": (
            "is not a margin name — margins are `inner` and `outer` so that the wider one "
            "stays at the binding edge under duplex (§ 8.1); on single-sided pages "
            "`outer` is the right one"
        ),
    }

    top: LengthField
    bottom: LengthField
    inner: LengthField
    outer: LengthField

    @model_validator(mode="after")
    def _all_non_negative(self) -> Margin:
        for side in ("top", "bottom", "inner", "outer"):
            _non_negative(getattr(self, side))
        return self

    @classmethod
    def parse(cls, value: Any) -> Margin:
        """Accept the scalar shorthand `margin: 5mm` as well as the named form.

        There is deliberately no four-element list: next to `inner`/`outer` its
        order would be ambiguous (§ 8.1).
        """
        if isinstance(value, str):
            value = dict.fromkeys(("top", "bottom", "inner", "outer"), value)
        return cls.model_validate(value)

    @classmethod
    def uniform(cls, length: Length) -> Margin:
        return cls(top=length, bottom=length, inner=length, outer=length)


class FontSpec(Section):
    """Stage 1 of § 10.3: the three logical families, resolved to the 14 standard
    PDF fonts.

    Not a fallback to system fonts. The objection to those was reproducibility,
    and it does not apply here: the metrics of the standard fonts are part of
    the PDF specification, so character widths — and therefore the geometry —
    are identical everywhere. Only the drawn glyph may be substituted, and for
    a tool whose promise is dimensional accuracy the geometry is what counts.
    """

    deferred: ClassVar[dict[str, str]] = {
        "file": (
            "— naming a font file (stage 2 of § 10.3, with embedding and an fsType check) "
            "arrives with milestone M2; this milestone offers family: serif | sans | mono"
        ),
    }

    family: Literal["serif", "sans", "mono"] = "sans"
    size: LengthField = Length(um=3175, mm=3.175, raw="9pt")


class Band(Section):
    """A header or footer: three fields on a fixed height (§ 8.4, § 8.9).

    The height comes from the definition and never from the rendered content.
    Otherwise page 1 with "Anna Berger" has a different pattern area than page 7
    with "Maximilian Sonnenschein-Hofstätter", and the grid jumps from sheet to
    sheet. An empty field is not a band of height zero — leave the section out.
    """

    height: LengthField
    gap: LengthField = Length(um=0, mm=0.0, raw="0mm")
    cut: bool = False
    font: FontSpec = FontSpec()
    left: TextField = None
    center: TextField = None
    right: TextField = None

    @model_validator(mode="after")
    def _heights_are_non_negative(self) -> Band:
        _non_negative(self.height)
        _non_negative(self.gap)
        return self


class AxisPair(Section):
    """A setting given per axis, with a scalar as shorthand for both (§ 8.5).

    One value for both axes would be wrong for calligraphy, where the y axis is
    cyclically structured and the x axis is not — so the two are separable. The
    scalar form records that the user did not name an axis, which matters: an
    explicitly named axis with nothing periodic on it is an error, while the
    shorthand simply means "both, wherever there is something to place".
    """

    x: str | None = None
    y: str | None = None
    explicit: bool = False

    @classmethod
    def parse(cls, value: Any, *, allowed: set[str], field: str) -> AxisPair:
        if isinstance(value, str):
            _check(value, allowed, field)
            return cls(x=value, y=value, explicit=False)
        if isinstance(value, dict):
            pair = {axis: value.get(axis) for axis in ("x", "y")}
            for axis, entry in pair.items():
                if entry is not None:
                    _check(entry, allowed, f"{field}.{axis}")
            unknown = set(value) - {"x", "y"}
            if unknown:
                raise ValueError(f"{field} takes x and y, not {', '.join(sorted(unknown))}")
            return cls(**pair, explicit=True)
        raise ValueError(f"{field} is a value or a mapping of x and y, got {value!r}")


def _check(value: str, allowed: set[str], field: str) -> None:
    if value not in allowed:
        raise ValueError(f"{field}: {value!r} is not one of {', '.join(sorted(allowed))}")


REMAINDER_MODES = {"end", "center", "whole_cycles"}
SNAP_MODES = {"none", "spacing", "cycle", "pixel"}


class PatternSpec(Section):
    """The pattern block — anchor, snapping and remainder handling (§ 5.2).

    Not the pattern area itself; that is computed in § 8.1.
    """

    anchor: Literal["pattern_area"] = "pattern_area"
    #: § 8.3. `none` by default, because snapping changes the geometry § 8.1
    #: computed: whoever writes a 10 mm margin and a header height would
    #: otherwise quietly get a smaller pattern area than that arithmetic gives.
    snap: AxisPair = AxisPair(x="none", y="none")
    #: § 8.5. `center` rather than `end`, following the sketch in § 5.2 and the
    #: way § 8.3 speaks of centring as the ordinary case: a 2 mm leftover reads
    #: as a mistake at one edge and as breathing room split across two.
    remainder: AxisPair = AxisPair(x="center", y="center")

    @model_validator(mode="before")
    @classmethod
    def _accept_the_axis_shorthands(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        for key, modes in (("remainder", REMAINDER_MODES), ("snap", SNAP_MODES)):
            if data.get(key) is not None:
                data = {
                    **data,
                    key: AxisPair.parse(data[key], allowed=modes, field=f"pattern.{key}"),
                }
        return data


class PagesSpec(Section):
    deferred: ClassVar[dict[str, str]] = {
        "cover": "arrives with milestone M2 (§ 8.8)",
    }

    count: int = Field(default=1, ge=1)
    #: § 9.4 allows an inline list for the one-off case but does not encourage
    #: it: the structure is the form, the list is a throwaway file. `--names`
    #: is the intended route and beats this one (§ 11).
    names: list[str] | None = None

    @property
    def count_was_given(self) -> bool:
        """Whether a page count was actually written down.

        It decides the mode of § 9.4: with a list and no count the data leads
        and there is one sheet per entry; with a count the count leads and
        entries repeat or are cut.
        """
        return "count" in self.model_fields_set


class PageSpec(Section):
    """The sheet: format, orientation and the non-printable border (§ 8.1)."""

    deferred: ClassVar[dict[str, str]] = {
        "device": "— device profiles arrive with milestone M5 (§ 9.2)",
        "background": "arrives with milestone M2 (§ 5.2)",
        "hole_marks": "arrives with milestone M2 (§ 8.7)",
    }

    format: str = "a4"
    orientation: Literal["portrait", "landscape"] = "portrait"
    #: § 8.1. With duplex on, `inner` and `outer` swap on even pages so the
    #: wider margin stays at the binding edge. With it off, `inner` is simply
    #: always the left one.
    duplex: bool = False
    #: Left unset on purpose: the default is a property of the paper format,
    #: not of the code (§ 8.1), so the loader fills it from formats.yaml.
    margin: Margin | None = None

    @model_validator(mode="before")
    @classmethod
    def _accept_the_margin_shorthand(cls, data: Any) -> Any:
        if isinstance(data, dict) and data.get("margin") is not None:
            data = {**data, "margin": Margin.parse(data["margin"])}
        return data
