# Edge ruler Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** An opt-in printed scale along chosen sheet edges, zeroed on the pattern area, that never moves a grid line and refuses loudly when it does not fit.

**Architecture:** Handle furniture, exactly like `border` and `hole_marks`: a `RulerSpec` section on the document, a `frame.py` function that turns it into `Segment` and `Text` marks on `Layer.FRAME` in sheet coordinates, a fit check shared by the pre-flight and the drawing (one arithmetic, not two), and a call site in `pages.py` beside the other frame furniture. No generator learns of it.

**Tech Stack:** Python 3.11+, pydantic v2 sections (`Section`, `extra="forbid"`), integer micrometres (`Um`), `pytest`, `ruff`, reportlab only behind `writers/pdf.py`.

**Design:** [`docs/superpowers/specs/2026-07-25-edge-ruler-design.md`](../specs/2026-07-25-edge-ruler-design.md) — read it first; it carries the *why* for every decision below.

---

## File structure

| File | Responsibility |
|---|---|
| `ctrlgrid/model.py` | `RulerSpec`: the fields, the per-unit defaults, and every refusal that needs no page |
| `ctrlgrid/loader.py` | `ruler` as a handle key, validated like `border`, carried on `Document` |
| `ctrlgrid/ruler.py` **(new)** | the ladder arithmetic: tick positions, label texts, the strip a ruler needs. Pure, no marks, no page — so both the drawing and the check use one arithmetic |
| `ctrlgrid/frame.py` | `ruler_marks(...)` (marks) and `check_rulers(...)` (refusals), both on top of `ruler.py` |
| `ctrlgrid/pages.py` | the call in `_page_marks`, the check in `preflight` |
| `tests/test_ruler.py` **(new)** | the ladder, the marks, the refusals |
| `tests/test_pdf_ruler.py` **(new)** | one real sheet, measured back out |

`ruler.py` is new rather than more of `frame.py` (451 lines already, and it owns bands): the ladder is self-contained arithmetic with one clear job, and both `frame.py` and the pre-flight need it.

---

### Task 1: `RulerSpec` — the section and its refusals

**Files:**
- Modify: `ctrlgrid/model.py` (beside `BorderSpec`, around line 335)
- Test: `tests/test_ruler.py` (create)

- [ ] **Step 1: Write the failing tests**

```python
"""The edge ruler (§ 8.12): the section, the ladder, the marks, the refusals."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from ctrlgrid.model import RulerSpec


class TestRulerSpec:
    def test_the_metric_default_is_the_one_five_ten_ladder(self) -> None:
        ruler = RulerSpec(edges=["bottom"])
        assert ruler.unit == "mm"
        assert (ruler.step.um, ruler.mid.um, ruler.label.um) == (1000, 5000, 10000)

    def test_centimetres_share_the_ladder_and_change_only_the_numbers(self) -> None:
        ruler = RulerSpec(edges=["bottom"], unit="cm")
        assert (ruler.step.um, ruler.mid.um, ruler.label.um) == (1000, 5000, 10000)

    def test_inches_get_an_eighth_half_one_ladder(self) -> None:
        ruler = RulerSpec(edges=["bottom"], unit="in")
        assert (ruler.step.um, ruler.mid.um, ruler.label.um) == (3175, 12700, 25400)

    def test_an_unknown_edge_is_refused_by_name(self) -> None:
        with pytest.raises(ValidationError) as excinfo:
            RulerSpec(edges=["middle"])
        assert "middle" in str(excinfo.value)

    def test_an_edge_twice_is_refused(self) -> None:
        with pytest.raises(ValidationError) as excinfo:
            RulerSpec(edges=["bottom", "bottom"])
        assert "bottom" in str(excinfo.value)

    def test_no_edge_at_all_is_refused(self) -> None:
        with pytest.raises(ValidationError):
            RulerSpec(edges=[])

    def test_a_label_interval_off_the_ladder_is_refused_naming_both(self) -> None:
        # A numbered tick that sits on no tick of the ladder is the silent
        # almost-right of § 5.1.
        with pytest.raises(ValidationError) as excinfo:
            RulerSpec(edges=["bottom"], step="3mm", label_every="10mm")
        message = str(excinfo.value)
        assert "3mm" in message and "10mm" in message

    def test_a_medium_tick_off_the_ladder_is_refused(self) -> None:
        with pytest.raises(ValidationError):
            RulerSpec(edges=["bottom"], step="2mm", mid_every="5mm", label_every="10mm")

    def test_the_medium_tick_can_be_left_out(self) -> None:
        ruler = RulerSpec(edges=["bottom"], mid_every="none")
        assert ruler.mid is None

    def test_a_step_of_zero_is_refused(self) -> None:
        with pytest.raises(ValidationError):
            RulerSpec(edges=["bottom"], step="0mm")

    def test_an_unknown_key_is_refused(self) -> None:
        with pytest.raises(ValidationError):
            RulerSpec(edges=["bottom"], ticks="every 2mm")
```

- [ ] **Step 2: Run them and watch them fail**

Run: `uv run pytest tests/test_ruler.py -q`
Expected: FAIL — `ImportError: cannot import name 'RulerSpec'`.

- [ ] **Step 3: Implement the section**

In `ctrlgrid/model.py`, after `BorderSpec`:

```python
#: The three ladders, per `unit` (§ 8.12). Fixed data, not settings: the
#: defaults are what a ruler of that unit looks like, and a user who wants
#: another ladder says so with `step`/`mid_every`/`label_every`.
_RULER_LADDERS: dict[str, tuple[str, str, str]] = {
    "mm": ("1mm", "5mm", "10mm"),
    "cm": ("1mm", "5mm", "10mm"),
    "in": ("0.125in", "0.5in", "1in"),
}


class RulerSpec(Section):
    """A printed scale along one or more sheet edges (§ 8.12).

    Zero is the pattern area's origin, so the numbers agree with the grid. It
    is drawn *into the margin* and reserves nothing, so switching it on leaves
    the pattern exactly where it was — the rule § 8.1 already states for
    `border`. `unit` says what the numbers mean; the three intervals say where
    the ticks are, and each must be a whole multiple of the one below it.
    """

    edges: tuple[Literal["bottom", "left", "top", "right"], ...]
    unit: Literal["mm", "cm", "in"] = "mm"
    step: LengthField | None = None
    mid_every: LengthField | Literal["none"] | None = None
    label_every: LengthField | None = None
    weight: LengthField = Length(um=71, mm=0.0706, raw="0.2pt")
    color: ColorField = "#000000"
    font: FontSpec = FontSpec(size=Length(um=2117, mm=2.117, raw="6pt"))

    @field_validator("edges")
    @classmethod
    def _at_least_one_edge_each_named_once(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if not value:
            raise ValueError("a ruler needs at least one edge (§ 8.12)")
        seen = [edge for edge in value if value.count(edge) > 1]
        if seen:
            raise ValueError(f"edge {seen[0]!r} is named twice — once is enough (§ 8.12)")
        return value

    @model_validator(mode="after")
    def _the_ladder(self) -> RulerSpec:
        """Fill the intervals from `unit` and refuse a rung that sits off the
        ladder — checked here rather than while drawing, because it needs no
        page (§ 12 point 13)."""
        step, mid, label = _RULER_LADDERS[self.unit]
        resolved_step = self.step or parse_length(step, field="ruler.step")
        resolved_label = self.label_every or parse_length(label, field="ruler.label_every")
        if self.mid_every == "none":
            resolved_mid = None
        elif self.mid_every is None:
            resolved_mid = parse_length(mid, field="ruler.mid_every")
        else:
            resolved_mid = self.mid_every

        if resolved_step.um <= 0:
            raise ValueError(f"ruler step {resolved_step.raw} must be greater than zero")
        # A default ladder never has to fit a user's `step`: it is the user's
        # step that decides, so an untouched `mid` simply goes when it clashes.
        if resolved_mid is not None and self.mid_every is None and (
            resolved_mid.um % resolved_step.um or resolved_label.um % resolved_mid.um
        ):
            resolved_mid = None
        for name, rung in (("label_every", resolved_label), ("mid_every", resolved_mid)):
            if rung is not None and rung.um % resolved_step.um:
                raise ValueError(
                    f"ruler {name} {rung.raw} is not a whole multiple of step "
                    f"{resolved_step.raw} — a numbered tick would sit on no tick "
                    "of the ladder (§ 8.12)"
                )
        if resolved_mid is not None and resolved_label.um % resolved_mid.um:
            raise ValueError(
                f"ruler label_every {resolved_label.raw} is not a whole multiple of "
                f"mid_every {resolved_mid.raw} (§ 8.12)"
            )
        object.__setattr__(self, "_resolved", (resolved_step, resolved_mid, resolved_label))
        return self

    @property
    def step_length(self) -> Length:
        return self._resolved[0]

    @property
    def mid(self) -> Length | None:
        return self._resolved[1]

    @property
    def label(self) -> Length | None:
        return self._resolved[2]
```

If `Section` is frozen and forbids private attributes, drop the `object.__setattr__`
trick and store the three resolved values as ordinary optional fields set in the
validator (`self.step`, `self.mid_every`, `self.label_every` rewritten to their
resolved values) — check how `Section` is declared before choosing, and prefer the
plainer of the two. Expose them as `step`, `mid`, `label` either way, because the
tests above and every later task use those names.

`parse_length`, `Literal`, `field_validator` and `model_validator` are already
imported in `model.py`; add only what is missing.

- [ ] **Step 4: Run the tests until they pass**

Run: `uv run pytest tests/test_ruler.py -q`
Expected: PASS, 11 tests.

- [ ] **Step 5: Commit**

```bash
git add ctrlgrid/model.py tests/test_ruler.py
git commit -F- <<'EOF'
ruler: the section, and the four things it can refuse without a page

§ 8.12. `unit` says what the numbers mean, three lengths say where the ticks
are, and each rung must be a whole multiple of the one below it: a numbered
tick sitting on no tick of the ladder is the almost-right of § 5.1.
EOF
```

---

### Task 2: `ruler.py` — the ladder arithmetic

**Files:**
- Create: `ctrlgrid/ruler.py`
- Test: `tests/test_ruler.py` (append)

- [ ] **Step 1: Write the failing tests**

```python
from ctrlgrid.ruler import Tick, label_text, strip_width, ticks


class TestTheLadder:
    def test_ticks_start_at_zero_and_stay_inside_the_area(self) -> None:
        ruler = RulerSpec(edges=["bottom"])
        got = ticks(ruler, extent=25_000)          # 25 mm
        assert got[0] == Tick(at=0, kind="label")
        assert [t.at for t in got] == [i * 1000 for i in range(26)]
        assert [t.at for t in got if t.kind == "label"] == [0, 10_000, 20_000]
        assert [t.at for t in got if t.kind == "mid"] == [5000, 15_000, 25_000]

    def test_a_tick_past_the_end_is_not_drawn(self) -> None:
        ruler = RulerSpec(edges=["bottom"])
        assert max(t.at for t in ticks(ruler, extent=25_500)) == 25_000

    def test_positions_are_exact_multiples_not_accumulated(self) -> None:
        # § 3.3: tick 200 is exactly 200 steps, whatever the step.
        ruler = RulerSpec(edges=["bottom"], step="0.125in", label_every="1in")
        got = ticks(ruler, extent=200 * 3175)
        assert got[200].at == 200 * 3175

    def test_millimetre_numbers_count_millimetres(self) -> None:
        ruler = RulerSpec(edges=["bottom"])
        assert label_text(ruler, at=30_000) == "30"

    def test_centimetre_numbers_count_centimetres(self) -> None:
        ruler = RulerSpec(edges=["bottom"], unit="cm")
        assert label_text(ruler, at=30_000) == "3"

    def test_inch_numbers_count_inches(self) -> None:
        ruler = RulerSpec(edges=["bottom"], unit="in")
        assert label_text(ruler, at=2 * 25_400) == "2"

    def test_a_number_states_its_position_exactly(self) -> None:
        # § 8.12: never rounded — a scale that prints a wrong measure is worse
        # than none.
        ruler = RulerSpec(edges=["bottom"], unit="cm", label_every="25mm")
        assert [label_text(ruler, at=at) for at in (25_000, 50_000)] == ["2.5", "5"]

    def test_the_strip_is_tick_plus_gap_plus_cap_height(self) -> None:
        ruler = RulerSpec(edges=["bottom"])
        assert strip_width(ruler) == 3000 + 1000 + (ruler.font.size.um * 7 // 10)
```

- [ ] **Step 2: Run and watch them fail**

Run: `uv run pytest tests/test_ruler.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'ctrlgrid.ruler'`.

- [ ] **Step 3: Implement the arithmetic**

```python
"""The edge ruler's ladder (§ 8.12) — where the ticks are and what they say.

Kept apart from `frame.py` because two callers need exactly this and must not
disagree: the drawing and the pre-flight's fit check. One arithmetic, not two
that drift (the calendar learned this the hard way, § 7.12).

No marks here, and no page: positions along an edge, label strings, and the
width of the strip a ruler needs. Micrometres throughout (§ 3.3).
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

from ctrlgrid.marks import Um
from ctrlgrid.model import RulerSpec

#: Tick lengths, from the pattern edge outwards. Fixed measures, like the cover
#: sheet's figures (§ 8.8): a yardstick nobody can bend is the point.
SHORT_TICK: Um = 1200
MID_TICK: Um = 2000
LONG_TICK: Um = 3000
#: Between the long tick and its number.
LABEL_GAP: Um = 1000
#: Cap height as a share of the font size — enough for digits, which have no
#: descender. Measured text width comes from the writer; this one number is a
#: proportion, not a measurement, and it is only used to reserve space.
CAP_HEIGHT = 7, 10

#: Micrometres per unit of the printed numbers.
_PER_UNIT: dict[str, int] = {"mm": 1000, "cm": 10_000, "in": 25_400}


@dataclass(frozen=True, slots=True)
class Tick:
    at: Um
    """Distance from the pattern area's origin along the edge."""

    kind: Literal["short", "mid", "label"]


def ticks(ruler: RulerSpec, *, extent: Um) -> list[Tick]:
    """Every tick from zero to `extent`, longest kind wins at a shared position."""
    step = ruler.step.um
    marks: list[Tick] = []
    for index in range(extent // step + 1):
        at = index * step                      # exact multiple, never accumulated
        if ruler.label is not None and at % ruler.label.um == 0:
            kind = "label"
        elif ruler.mid is not None and at % ruler.mid.um == 0:
            kind = "mid"
        else:
            kind = "short"
        marks.append(Tick(at=at, kind=kind))
    return marks


def tick_length(kind: str) -> Um:
    return {"short": SHORT_TICK, "mid": MID_TICK, "label": LONG_TICK}[kind]


def label_text(ruler: RulerSpec, *, at: Um) -> str:
    """What the number at `at` reads, exactly — never rounded (§ 8.12)."""
    value = Decimal(at) / Decimal(_PER_UNIT[ruler.unit])
    text = format(value.normalize(), "f")
    return text


def strip_width(ruler: RulerSpec) -> Um:
    """How much room a ruler needs between the pattern edge and whatever is
    next — the long tick, the gap, and the height of a digit."""
    numerator, denominator = CAP_HEIGHT
    return LONG_TICK + LABEL_GAP + ruler.font.size.um * numerator // denominator
```

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/test_ruler.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add ctrlgrid/ruler.py tests/test_ruler.py
git commit -F- <<'EOF'
ruler: the ladder — tick positions, exact numbers, the strip it needs

Its own module, because the drawing and the pre-flight's fit check both need
this arithmetic and must never disagree about it. Positions are exact
multiples of the step (§ 3.3); a number states its position exactly and is
never rounded — a scale that prints a wrong measure is worse than none.
EOF
```

---

### Task 3: the marks

**Files:**
- Modify: `ctrlgrid/frame.py` (after `hole_marks`, around line 147)
- Test: `tests/test_ruler.py` (append)

- [ ] **Step 1: Write the failing tests**

```python
from ctrlgrid.frame import ruler_marks
from ctrlgrid.marks import Area, Layer, Point, Segment, Text
from ctrlgrid.pages import Geometry


def _geometry(**kwargs):
    """An A4 sheet with 20 mm margins and no bands."""
    from ctrlgrid.loader import load_preset
    document = load_preset("millimeter-a4")
    return document, Geometry.of(document.sheet, header=None, footer=None)


class TestTheMarks:
    def test_the_bottom_ruler_zeroes_on_the_pattern_origin(self, q) -> None:
        document, geometry = _geometry()
        ruler = RulerSpec(edges=["bottom"])
        marks = ruler_marks(ruler, geometry, sheet=document.sheet, q=q)
        first = [m for m in marks if isinstance(m, Segment)][0]
        assert first.start.x == geometry.origin.x
        assert first.start.y == geometry.origin.y          # grows outward, downward
        assert first.end.y == geometry.origin.y - 3000     # a labelled tick

    def test_every_mark_is_frame_layer(self, q) -> None:
        document, geometry = _geometry()
        marks = ruler_marks(RulerSpec(edges=["bottom", "left"]), geometry,
                            sheet=document.sheet, q=q)
        assert {m.layer for m in marks} == {Layer.FRAME}

    def test_the_numbers_stand_upright_below_and_turn_on_the_side(self, q) -> None:
        document, geometry = _geometry()
        marks = ruler_marks(RulerSpec(edges=["bottom", "left"]), geometry,
                            sheet=document.sheet, q=q)
        texts = [m for m in marks if isinstance(m, Text)]
        assert {t.angle for t in texts} == {0.0, 90.0}

    def test_a_ruler_draws_nothing_into_the_pattern_area(self, q) -> None:
        document, geometry = _geometry()
        marks = ruler_marks(RulerSpec(edges=["bottom"]), geometry,
                            sheet=document.sheet, q=q)
        assert all(m.start.y <= geometry.origin.y for m in marks if isinstance(m, Segment))
```

Add a `q` fixture to `tests/test_ruler.py` if the suite has none to reuse —
check `tests/conftest.py` first; the project already builds a `PdfWriter` as a
metrics oracle elsewhere (`pages._metrics_oracle`), and the fixture should do the
same rather than invent a second way.

- [ ] **Step 2: Run and watch them fail**

Run: `uv run pytest tests/test_ruler.py -q -k TestTheMarks`
Expected: FAIL — `ImportError: cannot import name 'ruler_marks'`.

- [ ] **Step 3: Implement**

In `ctrlgrid/frame.py`:

```python
def ruler_marks(
    ruler: RulerSpec | None, geometry: Geometry, *, sheet: Sheet, q: WriterQuery
) -> list[Mark]:
    """The edge scale (§ 8.12), in sheet coordinates.

    Zero is the pattern area's origin for that edge and the ticks grow outward
    into the margin, on `Layer.FRAME`: no space is reserved and the pattern area
    never moves, exactly as a `border` never moves a grid line (§ 8.1).
    """
    if ruler is None:
        return []

    marks: list[Mark] = []
    for edge in ruler.edges:
        along, outward, extent = _edge_axes(edge, geometry)
        for tick in ticks(ruler, extent=extent):
            length = tick_length(tick.kind)
            start = _point(along, outward, at=tick.at, out=0)
            end = _point(along, outward, at=tick.at, out=length)
            marks.append(Segment(start=start, end=end, weight=ruler.weight.mm,
                                 color=ruler.color, layer=Layer.FRAME))
            if tick.kind != "label" or ruler.label is None:
                continue
            marks.append(Text(
                pos=_point(along, outward, at=tick.at, out=length + LABEL_GAP),
                content=label_text(ruler, at=tick.at),
                size=ruler.font.size.um,
                family=ruler.font.family,
                align="center",
                angle=90.0 if edge in ("left", "right") else 0.0,
                color=ruler.color,
                layer=Layer.FRAME,
            ))
    return marks
```

`_edge_axes(edge, geometry)` returns the origin point of that edge, the outward
unit direction (`(0, -1)` for `bottom`, `(-1, 0)` for `left`, and so on) and the
extent along it (`geometry.area.width` for the horizontal edges,
`geometry.area.height` for the vertical ones); `_point` combines the two into a
`Point`. Write both as small private helpers in `frame.py` directly under
`ruler_marks` — they are three lines each and belong next to their only caller.

Note for the `Text` baseline: on the horizontal edges the number hangs *below*
its tick, so its position is the tick's outer end minus the gap **and** its cap
height; on the vertical edges the rotation puts the baseline on the other side.
Get this right by rendering, not by reasoning — Task 6 looks at a real sheet.

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/test_ruler.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add ctrlgrid/frame.py tests/test_ruler.py
git commit -F- <<'EOF'
ruler: the marks, growing outward from the pattern edge into the margin

Frame furniture beside hole marks: Layer.FRAME, no space reserved, the
pattern area untouched (§ 8.1). The numbers turn 90° on the vertical edges,
so the strip a ruler needs is the same on all four.
EOF
```

---

### Task 4: the refusals

**Files:**
- Modify: `ctrlgrid/frame.py` (`check_rulers`, below `ruler_marks`)
- Test: `tests/test_ruler.py` (append)

- [ ] **Step 1: Write the failing tests**

```python
from ctrlgrid.errors import DefinitionError
from ctrlgrid.frame import check_rulers


class TestTheRefusals:
    def test_a_margin_too_narrow_names_needed_and_available(self, q) -> None:
        document, geometry = _geometry_with_margin("4mm")
        with pytest.raises(DefinitionError) as excinfo:
            check_rulers(RulerSpec(edges=["bottom"]), geometry,
                         sheet=document.sheet, header=None, footer=None, q=q)
        message = str(excinfo.value)
        assert "4" in message and "mm" in message and "bottom" in message

    def test_a_band_in_the_way_is_named_as_the_cause(self, q) -> None:
        document, geometry = _geometry_with_header("10mm")
        with pytest.raises(DefinitionError) as excinfo:
            check_rulers(RulerSpec(edges=["top"]), geometry, sheet=document.sheet,
                         header=document.header, footer=None, q=q)
        assert "header" in str(excinfo.value)

    def test_numbers_that_would_collide_are_refused_with_the_measured_width(self, q) -> None:
        document, geometry = _geometry()
        ruler = RulerSpec(edges=["bottom"], step="1mm", mid_every="none",
                          label_every="2mm", font={"size": "12pt"})
        with pytest.raises(DefinitionError) as excinfo:
            check_rulers(ruler, geometry, sheet=document.sheet,
                         header=None, footer=None, q=q)
        assert "2mm" in str(excinfo.value)

    def test_a_ruler_that_fits_raises_nothing(self, q) -> None:
        document, geometry = _geometry()
        check_rulers(RulerSpec(edges=["bottom", "left", "top", "right"]), geometry,
                     sheet=document.sheet, header=None, footer=None, q=q)
```

`_geometry_with_margin` and `_geometry_with_header` build a document from an
inline definition through `ctrlgrid.loader.load` on a `tmp_path` file, the way
the existing tests build definitions — copy the nearest existing helper rather
than inventing a third style.

- [ ] **Step 2: Run and watch them fail**

Run: `uv run pytest tests/test_ruler.py -q -k TestTheRefusals`
Expected: FAIL — `ImportError: cannot import name 'check_rulers'`.

- [ ] **Step 3: Implement**

```python
def check_rulers(
    ruler: RulerSpec | None, geometry: Geometry, *, sheet: Sheet,
    header: Band | None, footer: Band | None, q: WriterQuery,
) -> None:
    """Fit or refuse, before page one (§ 12 point 13, § 8.2).

    Nothing is ever shrunk to make a ruler fit; the message names the edge, the
    millimetres it needed and the millimetres there are — and the band, when a
    band is what took them.
    """
    if ruler is None:
        return

    needed = strip_width(ruler)
    for edge in ruler.edges:
        free, cause = _free_strip(edge, geometry, sheet=sheet, header=header, footer=footer)
        if needed > free:
            because = f", because the {cause} band ends there" if cause else ""
            raise DefinitionError(
                f"the {edge} ruler needs {_mm(needed)} between the pattern area and the "
                f"sheet edge and there are {_mm(free)}{because} — widen the margin or "
                "use a smaller font (§ 8.12)",
                field="ruler",
            )

    if ruler.label is None:
        return
    extent = max(geometry.area.width, geometry.area.height)
    widest = max(
        q.text_width(label_text(ruler, at=tick.at), family=ruler.font.family,
                     size=ruler.font.size.um)
        for tick in ticks(ruler, extent=extent) if tick.kind == "label"
    )
    if widest > ruler.label.um:
        raise DefinitionError(
            f"the ruler's numbers are {_mm(widest)} wide and sit {ruler.label.raw} apart, "
            "so they would run into one another — label further apart or use a smaller "
            "font (§ 8.12)",
            field="ruler.label_every",
        )
```

`_free_strip(edge, …)` returns the micrometres between the pattern area's edge
and the sheet edge, minus a band and its gap when one stands there, plus the name
of that band (`"header"`, `"footer"`) or `None`. Derive it from `geometry.origin`,
`geometry.area` and `sheet.width`/`sheet.height`; `geometry.header` and
`geometry.footer` are `Box`es in sheet coordinates and give the exact edge.

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/test_ruler.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add ctrlgrid/frame.py tests/test_ruler.py
git commit -F- <<'EOF'
ruler: refuse before page one, naming the edge and the millimetres

Four refusals (§ 8.12): the strip does not fit, a band took the space, the
numbers would collide, and — from the section — a rung off the ladder. The
widest number is measured with q.text_width, not guessed; guessed positions
were the whole bug list of the calendar session.
EOF
```

---

### Task 5: wire it into the run

**Files:**
- Modify: `ctrlgrid/loader.py` (`HANDLE_KEYS`, `Document`, `section(...)`, the `Document(...)` call)
- Modify: `ctrlgrid/pages.py` (`preflight`, `_page_marks`)
- Test: `tests/test_ruler.py` (append)

- [ ] **Step 1: Write the failing tests**

```python
class TestTheRun:
    def test_a_ruler_does_not_move_the_pattern(self, tmp_path, q) -> None:
        # § 8.1's rule, restated for the ruler: switching it on changes no
        # pattern mark at all.
        without = _pattern_marks(tmp_path, ruler=None)
        with_ruler = _pattern_marks(tmp_path, ruler={"edges": ["bottom", "left"]})
        assert without == with_ruler

    def test_the_same_definition_gives_the_same_bytes(self, tmp_path) -> None:
        first = _build(tmp_path / "a.pdf", ruler={"edges": ["bottom"]})
        second = _build(tmp_path / "b.pdf", ruler={"edges": ["bottom"]})
        assert first.read_bytes() == second.read_bytes()

    def test_an_unfittable_ruler_is_refused_by_check(self, tmp_path) -> None:
        # `ctrlgrid check` runs the same pre-flight, so it must refuse there too.
        with pytest.raises(DefinitionError):
            _check(tmp_path, margin="4mm", ruler={"edges": ["bottom"]})

    def test_png_output_is_refused_naming_text(self, tmp_path) -> None:
        with pytest.raises(DefinitionError) as excinfo:
            _build(tmp_path / "out.png", ruler={"edges": ["bottom"]})
        assert "text" in str(excinfo.value).lower()
```

`_pattern_marks`, `_build` and `_check` are small local helpers over
`ctrlgrid.loader.load` + `ctrlgrid.pages.build` / `preflight`; the PNG case needs
the `png` writer chosen by the `.png` extension, exactly as `cli.py` chooses it.
Look at the existing PNG refusal test (`grep -rn "cannot draw" tests/`) and reuse
its shape.

- [ ] **Step 2: Run and watch them fail**

Run: `uv run pytest tests/test_ruler.py -q -k TestTheRun`
Expected: FAIL — `ruler` is an unknown top-level key.

- [ ] **Step 3: Implement the wiring**

1. `loader.py`: add `"ruler"` to `HANDLE_KEYS`; add `ruler: RulerSpec | None` to
   `Document`; add `"ruler"` to the tuple in `section(...)` that returns `None`
   for an absent optional section; `ruler = section(RulerSpec, "ruler")`; pass
   `ruler=ruler` to `Document(...)`.
2. `pages.py`, in `preflight`, right after `blade.check(...)`:

```python
    # § 8.12: the ruler is measured against the same geometry the pattern got,
    # and refused here rather than while pages are written (§ 12 point 13).
    check_rulers(
        document.ruler, geometry, sheet=document.sheet,
        header=document.header, footer=document.footer, q=probe,
    )
```

   Under duplex the margins swap, so check both sides when
   `document.page.duplex` is on: call it once with the odd-page geometry and once
   with the even one, using `geometry.for_page(...)` the way `_page_marks` does.
3. `pages.py`, in `_page_marks`, directly after the `hole_marks` line:

```python
    yield from ruler_marks(document.ruler, placed, sheet=document.sheet, q=q)
```

   `placed` and not `geometry`: the ruler measures the area this page actually
   got, and under duplex that area sits on the other side of the sheet.
4. Import `check_rulers` and `ruler_marks` from `ctrlgrid.frame` in both places,
   inside the functions, matching the local-import style already there.

- [ ] **Step 4: Run the whole suite**

Run: `uv run pytest -q && uv run ruff check .`
Expected: PASS, and the count is the old 1000 plus the new tests.

- [ ] **Step 5: Commit**

```bash
git add ctrlgrid/loader.py ctrlgrid/pages.py tests/test_ruler.py
git commit -F- <<'EOF'
ruler: into the run — one key, the pre-flight, and the per-page geometry

`ruler:` joins border and stamp as an optional handle section. The marks come
from the *placed* geometry, so under duplex the scale follows the area to the
other side of the sheet; the check runs for both sides before page one. The
PNG writer refuses it by name through the capability pre-flight — the numbers
are Text, and that path already existed.
EOF
```

---

### Task 6: measure a real sheet

**Files:**
- Create: `tests/test_pdf_ruler.py`

- [ ] **Step 1: Write the failing test**

```python
"""The ruler, read back out of a finished PDF — the promise, measured.

Unit tests can agree with a bug. `tests/pdfread.py` reads the geometry out of
the written file, which is the only check that catches a wrong baseline or a
tick drawn the wrong way.
"""

from __future__ import annotations

from ctrlgrid.loader import load
from ctrlgrid.pages import build
from tests.pdfread import segments_of        # match the helper's real name


def test_the_ten_millimetre_tick_lies_ten_millimetres_from_the_origin(tmp_path) -> None:
    definition = tmp_path / "def.yaml"
    definition.write_text(
        "version: 1\n"
        "page: { format: a4, margin: 20mm }\n"
        "generator: lines\n"
        "lines: { spacing: 10mm }\n"
        "ruler: { edges: [bottom] }\n",
        encoding="utf-8",
    )
    out = tmp_path / "out.pdf"
    build(load(definition), out)

    ticks = [s for s in segments_of(out, page=1) if _is_vertical(s)]
    long_ticks = sorted({s.x for s in ticks if s.length_mm > 2.5})
    assert long_ticks[1] - long_ticks[0] == pytest.approx(10.0, abs=0.01)
    assert long_ticks[0] == pytest.approx(20.0, abs=0.01)     # the pattern origin
```

Read `tests/pdfread.py` first and use its actual API; the names above are a
sketch of the shape, not a promise about the helper.

- [ ] **Step 2: Run and watch it fail**

Run: `uv run pytest tests/test_pdf_ruler.py -q`
Expected: FAIL (or an import error until the helper name is right).

- [ ] **Step 3: Make it pass**

If it fails on geometry rather than on the helper's name, the bug is real —
fix `frame.py`, not the test.

- [ ] **Step 4: Look at the sheet**

```bash
uv run ctrlgrid -d /tmp/ruler.yaml -o /tmp/ruler.pdf --force
pdftoppm -png -r 150 -f 1 -l 1 /tmp/ruler.pdf /tmp/ruler
```

Open the PNG and check what no assertion catches: numbers upright below and
turned on the side, no number clipped by the sheet edge, the ladder legible at
print size.

- [ ] **Step 5: Commit**

```bash
git add tests/test_pdf_ruler.py
git commit -F- <<'EOF'
ruler: measured out of a finished PDF, not only asserted in a unit test

A 10 mm labelled tick lies 10 mm from the pattern origin, read back with
tests/pdfread.py. The one check that catches a wrong baseline or a tick drawn
inward.
EOF
```

---

### Task 7: documents, preset comment and the gallery

**Files:**
- Modify: `docs/pflichtenheft-vorlagengenerator.md` (new § 8.12, German, after § 8.11)
- Modify: `docs/implementation-decisions.md` (decision 46)
- Modify: `HANDBOOK.md` (§ 10, after "Border, background, hole marks, stamp")
- Modify: `README.md` (the frame-furniture sentence in the status blurb)
- Modify: `docs/CLAUDE.md` (state, and the *What to do next* list)
- Create: `examples/13-ruler-edge.yaml`, its `.pdf`, `examples/previews/13-ruler-edge.png`
- Modify: `examples/README.md` (the gallery row)

- [ ] **Step 1: Write § 8.12 in the specification**

German, in the voice of the sections around it, and it must carry the *why*:
the working-scale purpose, zero at the pattern origin, physical edges, no
reserved space (with the § 8.1 parallel), the fixed tick ladder, rotated
numbers, exact never-rounded labels, and the four refusals.

- [ ] **Step 2: Add decision 46**

`docs/implementation-decisions.md`, in the file's existing shape: the question,
the decision, the reasoning, and the section it belongs to (§ 8.12).

- [ ] **Step 3: The handbook**

A subsection under § 10 beside the other frame furniture: the YAML block with
every key, the per-unit default table, what the refusals say, and one sentence
that the numbers are zeroed on the pattern area and not on the paper's corner.

- [ ] **Step 4: The example**

```yaml
# ruler — the one promise, on the sheet itself: lay a real ruler against the
# scale and either the numbers agree or the print driver scaled (§ 8.12).
version: 1
page: { format: a4, margin: 18mm }
generator: lines
lines:
  spacing: 10mm
  weight: 0.15pt
ruler:
  edges: [bottom, left]
  unit: cm
```

Then build it and its preview the way the gallery does:

```bash
uv run ctrlgrid -d examples/13-ruler-edge.yaml -o examples/13-ruler-edge.pdf --force
pdftoppm -png -scale-to-x 600 -scale-to-y -1 -f 1 -l 1 \
  examples/13-ruler-edge.pdf examples/previews/13-ruler-edge
```

Rename the produced `13-ruler-edge-01.png` to `13-ruler-edge.png`, add the row
to `examples/README.md` in the shape of the rows around it, and confirm
`test_every_example_validates` still passes.

- [ ] **Step 5: Run everything and commit**

```bash
uv run pytest -q && uv run ruff check .
git add -A
git commit -F- <<'EOF'
ruler: § 8.12, the handbook, and a sheet you can hold a ruler against

The specification gains the section and its reasoning, decision 46 records
what the spec was silent on, and the gallery gains 13-ruler-edge — the one
example that demonstrates the promise instead of describing it.
EOF
```

---

## Self-review

- **Spec coverage.** Purpose → Task 1 + 6; the definition and per-unit defaults →
  Task 1; geometry, zero point, outward growth, exact multiples, rotated numbers,
  exact labels → Tasks 2–3; the four refusals → Tasks 1 and 4; call sites and
  duplex → Task 5; PNG → Task 5; the read-back → Task 6; the documents, the
  cover-sheet exemption (nothing to do, stated in § 8.12) and the gallery →
  Task 7.
- **Names are consistent** across tasks: `RulerSpec.step`/`.mid`/`.label`,
  `ticks()`, `tick_length()`, `label_text()`, `strip_width()`, `ruler_marks()`,
  `check_rulers()`.
- **Open by design, flagged in place:** the exact `Text` baseline on each edge
  (Task 3 says to settle it by rendering, Task 6 looks), the `Section` frozen
  question (Task 1 names both ways out), and the real names in `tests/pdfread.py`
  (Task 6 says to read it first). These are the places where writing code from a
  plan is worse than looking — not placeholders.
