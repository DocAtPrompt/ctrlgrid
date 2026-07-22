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

from ctrlgrid import fonts
from ctrlgrid.errors import DefinitionError
from ctrlgrid.units import Angle, Length, parse_angle, parse_length


def _as_length(value: Any) -> Any:
    """Turn definition text into a `Length`, leaving anything else to pydantic."""
    if isinstance(value, Length):
        return value
    try:
        return parse_length(value)
    except DefinitionError as error:
        raise ValueError(error.message) from None


def _as_angle(value: Any) -> Any:
    if isinstance(value, Angle):
        return value
    try:
        return parse_angle(value)
    except DefinitionError as error:
        raise ValueError(error.message) from None


def _non_negative(value: Length) -> Length:
    if value.um < 0:
        raise ValueError(f"must not be negative, got {value.raw}")
    return value


LengthField = Annotated[Length, BeforeValidator(_as_length)]
AngleField = Annotated[Angle, BeforeValidator(_as_angle)]


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

    family: Literal["serif", "sans", "mono"] = "sans"
    size: LengthField = Length(um=3175, mm=3.175, raw="9pt")
    #: Stage 2 of § 10.3: a path to a font file, embedded and subset. A path
    #: and not a name — name lookup finds different fonts on different
    #: machines, which is the unreliability the tool exists to avoid.
    file: str | None = None

    @model_validator(mode="after")
    def _one_way_of_naming_the_font(self) -> FontSpec:
        """§ 10.3: `family` and `file` are the two stages, not two settings.

        Both at once would be two answers to one question, pointing at
        different fonts — and § 5.1 refuses to guess which one was meant. The
        default `family` does not count as an answer, only a written one does.
        """
        if self.file is not None and "family" in self.model_fields_set:
            raise ValueError(
                f"a font is named either by `family` ({self.family}) or by `file` "
                f"({self.file}), not both — they are the two stages of § 10.3 and "
                "would point at different fonts"
            )
        return self

    @property
    def token(self) -> str:
        """How the writer is told which font this is (§ 3.6, seam 3).

        The mark vocabulary does not grow for stage 2 (§ 6): `family` on a
        `Text` mark was always a string the writer resolves, and a file font is
        one more spelling of it.
        """
        return fonts.token_for(self.file) if self.file else self.family


class ImageSpec(Section):
    """A header or footer field that holds a picture instead of text (§ 5.2).

    Only the height is given. The width follows from the file's own
    proportions, because a logo stretched to a width somebody typed is not the
    logo any more — and § 8.9 withholds `cut` from images for the same reason:
    it fits or it is an error.
    """

    image: str
    height: LengthField

    @model_validator(mode="after")
    def _a_height_of_nothing_is_not_a_height(self) -> ImageSpec:
        if self.height.um <= 0:
            raise ValueError(f"image height must be positive, got {self.height.raw}")
        return self


def _text_or_image(value: Any) -> Any:
    """A band field is free text or a `{ image: …, height: … }` block (§ 5.2)."""
    if isinstance(value, dict):
        return ImageSpec.model_validate(value)
    return value


FieldContent = Annotated[str | ImageSpec | None, BeforeValidator(_text_or_image)]


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
    left: FieldContent = None
    center: FieldContent = None
    right: FieldContent = None

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


def _as_color(value: Any) -> Any:
    """`#rrggbb`, six digits, RGB — no names, no alpha, no CMYK (§ 5.3).

    `none` and an absent key mean the same thing: no colour. § 5.1 lists `none`
    among the keywords that stand where a measure could, so it is spelled out
    rather than left to an empty value.
    """
    if value is None or value == "none":
        return None
    if not (
        isinstance(value, str)
        and len(value) == 7
        and value.startswith("#")
        and all(character in "0123456789abcdefABCDEF" for character in value[1:])
    ):
        raise ValueError(
            f"colour must be #rrggbb, six digits, RGB — got {value!r}. "
            "Opacity is a field of its own (§ 5.3)"
        )
    return value


ColorField = Annotated[str | None, BeforeValidator(_as_color)]


class BorderSpec(Section):
    """An optional rule around the pattern area (§ 5.2, § 8.1).

    It sits exactly on the pattern area's edge and `gap` pushes it *outwards*,
    so switching a border on never moves a grid line: § 8.1 computes the
    pattern area from margins and bands alone, and nothing here feeds back
    into it.
    """

    weight: LengthField
    color: ColorField = "#000000"
    gap: LengthField = Length(um=0, mm=0.0, raw="0mm")


class StampSpec(Section):
    """A full-page diagonal overprint (§ 8.6).

    "Draft" is a transient state of a run, not a property of the paper, which
    is why `--stamp` is the intended route and this section exists mainly so
    the definition *can* say it.
    """

    text: str
    angle: AngleField = Angle(deg=45.0, raw="45deg")
    opacity: float = Field(default=0.08, gt=0.0, le=1.0)
    #: `auto` sizes the text to the sheet; a length is taken as written (§ 5.1).
    size: LengthField | Literal["auto"] = "auto"


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
    count: int = Field(default=1, ge=1)
    #: § 8.8. Off by default, and never counted: `--pages 30 --cover` gives 30
    #: numbered sheets *plus* a cover, and `{page} / {page_count}` goes on
    #: meaning 1…30. `--cover` is the intended route, as with the stamp (§ 8.6).
    cover: bool = False
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
    }

    format: str = "a4"
    orientation: Literal["portrait", "landscape"] = "portrait"
    #: § 8.1. With duplex on, `inner` and `outer` swap on even pages so the
    #: wider margin stays at the binding edge. With it off, `inner` is simply
    #: always the left one.
    duplex: bool = False
    #: `none` or a colour; the sheet is painted before anything else (§ 5.2).
    background: ColorField = None
    #: ISO 838 punch marks at the binding edge (§ 8.7). One line, one switch.
    hole_marks: bool = False
    #: Left unset on purpose: the default is a property of the paper format,
    #: not of the code (§ 8.1), so the loader fills it from formats.yaml.
    margin: Margin | None = None

    @model_validator(mode="before")
    @classmethod
    def _accept_the_margin_shorthand(cls, data: Any) -> Any:
        if isinstance(data, dict) and data.get("margin") is not None:
            data = {**data, "margin": Margin.parse(data["margin"])}
        return data
