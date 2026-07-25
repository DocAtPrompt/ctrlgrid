"""The edge ruler (§ 8.12): the section, the ladder, the marks, the refusals.

A working scale, not a second calibration figure: zero sits at the origin of
the *pattern area*, so the numbers agree with the grid rather than with the
paper's corner. It is drawn into the margin and reserves nothing, so switching
it on leaves the pattern exactly where it was — the rule § 8.1 already states
for `border`.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from ctrlgrid.model import RulerSpec


class TestTheSection:
    def test_the_metric_default_is_the_one_five_ten_ladder(self) -> None:
        ruler = RulerSpec(edges=["bottom"])
        assert ruler.unit == "mm"
        assert (ruler.step.um, ruler.mid_every.um, ruler.label_every.um) == (
            1000, 5000, 10_000,
        )

    def test_centimetres_share_the_ladder_and_change_only_the_numbers(self) -> None:
        ruler = RulerSpec(edges=["bottom"], unit="cm")
        assert (ruler.step.um, ruler.mid_every.um, ruler.label_every.um) == (
            1000, 5000, 10_000,
        )

    def test_inches_get_an_eighth_half_one_ladder(self) -> None:
        ruler = RulerSpec(edges=["bottom"], unit="in")
        assert (ruler.step.um, ruler.mid_every.um, ruler.label_every.um) == (
            3175, 12_700, 25_400,
        )

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
        # § 5.1: a numbered tick that sits on no tick of the ladder is the
        # silent almost-right, so it is refused rather than drawn.
        with pytest.raises(ValidationError) as excinfo:
            RulerSpec(edges=["bottom"], step="3mm", mid_every="none", label_every="10mm")
        message = str(excinfo.value)
        assert "3mm" in message and "10mm" in message

    def test_a_medium_tick_off_the_ladder_is_refused(self) -> None:
        with pytest.raises(ValidationError):
            RulerSpec(edges=["bottom"], step="2mm", mid_every="5mm", label_every="10mm")

    def test_a_custom_step_that_the_default_ladder_cannot_take_says_so(self) -> None:
        # The default 5/10 mm rungs cannot sit on a 3 mm ladder. Told, not
        # silently dropped: the message names both values and the way out.
        with pytest.raises(ValidationError) as excinfo:
            RulerSpec(edges=["bottom"], step="3mm")
        message = str(excinfo.value)
        assert "3mm" in message and "10mm" in message and "none" in message

    def test_the_medium_tick_can_be_left_out(self) -> None:
        ruler = RulerSpec(edges=["bottom"], mid_every="none")
        assert ruler.mid_every is None

    def test_a_step_of_zero_is_refused(self) -> None:
        with pytest.raises(ValidationError):
            RulerSpec(edges=["bottom"], step="0mm")

    def test_an_unknown_key_is_refused(self) -> None:
        with pytest.raises(ValidationError):
            RulerSpec(edges=["bottom"], ticks="every 2mm")
