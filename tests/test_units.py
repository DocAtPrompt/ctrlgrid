"""Unit normalisation — the foundation of the one promise (§ 3.3, § 5.1).

Positions become integer micrometres because they accumulate (§ 8.2). Stroke
widths, diameters and opacity stay floating point because they never do, and
because micrometres would be too coarse for them: 0.1 pt is 35 µm, so one
rounding step is 3 %. Both live on the same value object, next to the string
the user actually wrote — "52.9 µm" is useless as error text when the
definition said `0.15pt` (§ 12).
"""

from __future__ import annotations

import pytest

from ctrlgrid.errors import DefinitionError
from ctrlgrid.units import parse_angle, parse_length


class TestLengthConversion:
    def test_millimetres_are_a_thousand_micrometres(self) -> None:
        assert parse_length("5mm").um == 5000

    def test_centimetres(self) -> None:
        assert parse_length("1cm").um == 10000

    def test_inches_are_exact(self) -> None:
        # 8.5 in is 215.9 mm exactly — the US Letter width from § 9.1.
        assert parse_length("8.5in").um == 215900

    def test_points_are_a_seventysecond_of_an_inch(self) -> None:
        assert parse_length("72pt").um == 25400

    def test_a4_height(self) -> None:
        assert parse_length("297mm").um == 297000

    def test_fractional_millimetres(self) -> None:
        assert parse_length("1.75mm").um == 1750

    def test_negative_lengths_parse(self) -> None:
        # `offset` may shift a family backwards (§ 7.1); the sign check belongs
        # to whichever field forbids it, not here.
        assert parse_length("-2mm").um == -2000


class TestRoundingIsDeterministic:
    def test_half_a_micrometre_rounds_away_from_zero(self) -> None:
        # Python's built-in round() is banker's rounding: it would give 0 here
        # and break "same input, same bytes" the moment a value lands on .5.
        assert parse_length("0.0005mm").um == 1

    def test_negative_half_rounds_away_from_zero(self) -> None:
        assert parse_length("-0.0005mm").um == -1

    def test_a_point_is_not_a_whole_number_of_micrometres(self) -> None:
        # 1 pt = 352.777… µm.
        assert parse_length("1pt").um == 353


class TestWeightsStayFloatingPoint:
    def test_thin_stroke_keeps_its_precision_in_millimetres(self) -> None:
        # 0.15 pt = 0.0529166… mm. Rounded to µm it would be 0.053 mm, a 0.2 %
        # error that grows to 3 % for the finest strokes (§ 3.3).
        assert parse_length("0.15pt").mm == pytest.approx(0.05291666, abs=1e-8)

    def test_millimetres_and_micrometres_agree_for_round_values(self) -> None:
        length = parse_length("5mm")
        assert (length.um, length.mm) == (5000, 5.0)


class TestTheRawValueSurvives:
    def test_raw_text_is_kept_verbatim(self) -> None:
        assert parse_length("0.15pt").raw == "0.15pt"

    def test_raw_text_keeps_the_users_spacing(self) -> None:
        assert parse_length("5 mm").raw == "5 mm"

    def test_whitespace_between_number_and_unit_is_accepted(self) -> None:
        assert parse_length("5 mm").um == 5000


class TestRefusals:
    def test_a_bare_number_is_an_error_naming_the_units(self) -> None:
        with pytest.raises(DefinitionError) as excinfo:
            parse_length("5", field="page.margin.top")
        message = str(excinfo.value)
        assert "page.margin.top" in message
        assert "5" in message
        assert "mm" in message and "cm" in message and "in" in message and "pt" in message

    def test_px_names_the_milestone_that_brings_it(self) -> None:
        # § 5.1: px is valid only with a device profile, and those arrive with
        # M5. "unknown unit" would send the user looking for a typo.
        with pytest.raises(DefinitionError) as excinfo:
            parse_length("45px", field="families.0.base_spacing")
        message = str(excinfo.value)
        assert "px" in message
        assert "device" in message.lower()

    def test_an_unknown_unit_is_an_error(self) -> None:
        with pytest.raises(DefinitionError) as excinfo:
            parse_length("5furlong")
        assert "furlong" in str(excinfo.value)

    def test_a_keyword_is_not_a_length(self) -> None:
        # `auto`, `rest` and `none` are instructions, not units (§ 5.1). Where
        # they are allowed, the field accepts them before calling us.
        with pytest.raises(DefinitionError) as excinfo:
            parse_length("auto", field="polar.outer_radius")
        assert "auto" in str(excinfo.value)

    def test_an_angle_is_not_a_length(self) -> None:
        with pytest.raises(DefinitionError):
            parse_length("45deg")

    def test_the_empty_string_is_an_error(self) -> None:
        with pytest.raises(DefinitionError):
            parse_length("")


class TestAngles:
    def test_degrees(self) -> None:
        assert parse_angle("45deg").deg == pytest.approx(45.0)

    def test_negative_degrees(self) -> None:
        assert parse_angle("-30deg").deg == pytest.approx(-30.0)

    def test_raw_text_is_kept(self) -> None:
        assert parse_angle("45deg").raw == "45deg"

    def test_a_bare_number_is_an_error(self) -> None:
        with pytest.raises(DefinitionError) as excinfo:
            parse_angle("45", field="stamp.angle")
        assert "deg" in str(excinfo.value)

    def test_a_length_is_not_an_angle(self) -> None:
        with pytest.raises(DefinitionError):
            parse_angle("45mm")
