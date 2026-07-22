"""Free page sizes (§ 9.1) — `format: 210x99mm`.

The format table is world knowledge and stays out of definitions; a free size
is the other half of the same sentence in § 9.1: the definition *references*
(`format: a4`) or *states* (`format: 8.5x11in`, "and then the general defaults
apply").

**A free size is taken exactly as written**, width first. The table is always
portrait and `orientation` turns it, but `210x99mm` is 210 wide and 99 high —
normalising it to portrait would silently produce a sheet nobody asked for, and
the example in § 9.1 is precisely such a wide strip.
"""

from __future__ import annotations

import pytest

from ctrlgrid.errors import DefinitionError
from ctrlgrid.loader import loads

BASE = (
    "generator: lines\n"
    "families:\n"
    "  - {direction: horizontal, base_spacing: 10mm}\n"
)


def sheet(spec: str, extra: str = "", overrides: dict | None = None):
    return loads(
        f"version: 1\npage:\n  format: {spec}\n{extra}{BASE}", overrides, source="test"
    ).sheet


class TestTheSyntax:
    def test_millimetres(self) -> None:
        assert (sheet("210x99mm").width, sheet("210x99mm").height) == (210_000, 99_000)

    def test_inches(self) -> None:
        # 8.5 in is 215900 µm exactly — § 3.3 runs the conversion in Decimal.
        assert sheet("8.5x11in").width == 215_900
        assert sheet("8.5x11in").height == 279_400

    def test_decimals_and_spaces_are_allowed(self) -> None:
        assert sheet("'105.5 x 74.25 mm'").width == 105_500

    def test_a_unit_on_each_side_is_allowed(self) -> None:
        assert sheet("210mmx99mm").height == 99_000

    def test_the_capital_x_reads_the_same(self) -> None:
        assert sheet("210X99mm").width == 210_000


class TestTheDefaults:
    def test_the_margin_is_the_general_default(self) -> None:
        # § 9.1: a free size takes the general defaults, not a format's.
        assert sheet("210x99mm").margin.top.um == 5_000

    def test_a_written_margin_still_wins(self) -> None:
        assert sheet("210x99mm", extra="  margin: 8mm\n").margin.inner.um == 8_000


class TestOrientation:
    def test_the_size_is_taken_as_written(self) -> None:
        # Not normalised to portrait: `210x99mm` is a wide strip, and turning
        # it upright would be a different sheet from the one asked for.
        assert sheet("210x99mm").width > sheet("210x99mm").height

    def test_landscape_swaps_whatever_was_written(self) -> None:
        turned = sheet("210x99mm", extra="  orientation: landscape\n")
        assert (turned.width, turned.height) == (99_000, 210_000)


class TestRefusals:
    def test_an_unknown_name_still_lists_the_known_ones(self) -> None:
        with pytest.raises(DefinitionError) as excinfo:
            sheet("a9")
        message = str(excinfo.value)
        assert "a4" in message and "210x99mm" in message

    def test_a_zero_side_is_an_error(self) -> None:
        with pytest.raises(DefinitionError) as excinfo:
            sheet("0x99mm")
        assert "0" in str(excinfo.value)

    def test_a_missing_unit_is_an_error_that_says_so(self) -> None:
        with pytest.raises(DefinitionError) as excinfo:
            sheet("210x99")
        assert "mm" in str(excinfo.value)

    def test_pixels_still_need_a_device_profile(self) -> None:
        # § 9.2: `px` is not a length until something resolves it (M5).
        with pytest.raises(DefinitionError) as excinfo:
            sheet("1404x1872px")
        assert "device" in str(excinfo.value).lower() or "px" in str(excinfo.value)


class TestFromTheCommandLine:
    def test_the_flag_takes_a_free_size_too(self) -> None:
        # § 11: the format belongs to the call, and the call beats the file.
        assert sheet("a4", overrides={"format": "148x105mm"}).width == 148_000
