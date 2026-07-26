"""The validated document model — seam 1 of § 3.6.

After validation there are no strings with units left in the core, unknown keys
are errors rather than nearly-right output (§ 5.1), and a key that the
specification describes but this milestone does not implement says so by name
instead of pretending to be a typo.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from ctrlgrid.model import Band, FontSpec, Margin, PageSpec, PagesSpec, PatternSpec


class TestMargin:
    def test_a_scalar_applies_to_all_four_sides(self) -> None:
        margin = Margin.parse("5mm")
        assert (margin.top.um, margin.bottom.um, margin.inner.um, margin.outer.um) == (
            5000,
            5000,
            5000,
            5000,
        )

    def test_sides_can_be_named_individually(self) -> None:
        margin = Margin.parse({"top": "10mm", "bottom": "5mm", "inner": "20mm", "outer": "8mm"})
        assert (margin.top.um, margin.bottom.um, margin.inner.um, margin.outer.um) == (
            10000,
            5000,
            20000,
            8000,
        )

    def test_left_and_right_are_refused_by_name(self) -> None:
        # § 8.1: the binding edge is what matters, so the names are inner and
        # outer. "unknown key" would leave the user guessing at the reason.
        with pytest.raises(ValidationError) as excinfo:
            Margin.parse({"left": "5mm", "right": "5mm"})
        message = str(excinfo.value)
        assert "inner" in message and "outer" in message

    def test_a_four_element_list_is_refused(self) -> None:
        # Ambiguous next to inner/outer — § 8.1 rules it out explicitly.
        with pytest.raises(ValidationError):
            Margin.parse(["5mm", "5mm", "5mm", "5mm"])

    def test_a_negative_margin_is_an_error(self) -> None:
        with pytest.raises(ValidationError):
            Margin.parse("-5mm")


class TestPageSpec:
    def test_the_format_defaults_to_a4(self) -> None:
        assert PageSpec().format == "a4"

    def test_orientation_is_a_closed_set(self) -> None:
        with pytest.raises(ValidationError):
            PageSpec(orientation="sideways")

    def test_the_margin_is_unset_by_default(self) -> None:
        # The default is a property of the format, not of the code (§ 8.1), so
        # the model leaves it open and the loader fills it from formats.yaml.
        assert PageSpec().margin is None

    def test_a_device_is_carried_as_written(self) -> None:
        # Resolved to a profile by the loader (§ 9.2); the model just holds it.
        assert PageSpec(device="remarkable-2").device == "remarkable-2"

    def test_a_device_and_a_written_format_together_are_an_error(self) -> None:
        with pytest.raises(ValidationError) as excinfo:
            PageSpec(device="remarkable-2", format="a4")
        message = str(excinfo.value)
        assert "device" in message and "format" in message

    def test_an_unknown_key_is_an_error(self) -> None:
        with pytest.raises(ValidationError) as excinfo:
            PageSpec(formt="a4")
        assert "formt" in str(excinfo.value)


class TestFontSpec:
    def test_the_three_logical_families(self) -> None:
        for family in ("serif", "sans", "mono"):
            assert FontSpec(family=family).family == family

    def test_a_font_file_is_carried_as_written(self) -> None:
        # Stage 2 of § 10.3. The file is not opened here — validation stays
        # free of disk access, and the loader checks the licence where the
        # line number is still known.
        path = "~/Library/Fonts/EBGaramond-Regular.ttf"
        assert FontSpec(file=path).file == path

    def test_the_size_is_normalised(self) -> None:
        assert FontSpec(size="9pt").size.um == 3175


class TestBand:
    def test_height_and_gap_are_lengths(self) -> None:
        band = Band(height="12mm", gap="4mm")
        assert (band.height.um, band.gap.um) == (12000, 4000)

    def test_cut_defaults_to_false(self) -> None:
        # A truncated name is silent data loss (§ 8.9); the default is to fail.
        assert Band(height="12mm").cut is False

    def test_the_three_fields_default_to_empty(self) -> None:
        band = Band(height="12mm")
        assert (band.left, band.center, band.right) == (None, None, None)

    def test_an_image_field_is_a_block_of_its_own(self) -> None:
        # § 5.2: a band field holds free text or `{ image: …, height: … }`.
        band = Band(height="12mm", left={"image": "logo.png", "height": "8mm"})
        assert band.left.image == "logo.png"
        assert band.left.height.um == 8_000

    def test_an_image_without_a_height_is_an_error(self) -> None:
        # The width follows from the file, the height never does (§ 8.4).
        with pytest.raises(ValidationError) as excinfo:
            Band(height="12mm", left={"image": "logo.png"})
        assert "height" in str(excinfo.value)

    def test_a_missing_height_is_an_error(self) -> None:
        # § 8.4: the height comes from the definition, never from the content.
        with pytest.raises(ValidationError):
            Band(center="Class 3B")


class TestPatternSpec:
    def test_the_only_anchor_in_v1(self) -> None:
        assert PatternSpec().anchor == "pattern_area"

    def test_snapping_defaults_to_none_on_both_axes(self) -> None:
        # § 8.3: snapping changes the geometry § 8.1 computed, so it is never
        # switched on behind the user's back.
        assert (PatternSpec().snap.x, PatternSpec().snap.y) == ("none", "none")

    def test_the_leftover_is_centred_by_default(self) -> None:
        assert (PatternSpec().remainder.x, PatternSpec().remainder.y) == ("center", "center")

    def test_an_unknown_snap_mode_lists_the_real_ones(self) -> None:
        with pytest.raises(ValidationError) as excinfo:
            PatternSpec(snap="grid")
        message = str(excinfo.value)
        assert "cycle" in message and "spacing" in message and "pixel" in message

    def test_an_axis_pair_takes_only_x_and_y(self) -> None:
        with pytest.raises(ValidationError) as excinfo:
            PatternSpec(snap={"horizontal": "cycle"})
        assert "horizontal" in str(excinfo.value)


class TestPagesSpec:
    def test_the_count_defaults_to_one(self) -> None:
        assert PagesSpec().count == 1

    def test_zero_pages_is_an_error(self) -> None:
        with pytest.raises(ValidationError):
            PagesSpec(count=0)

    def test_the_cover_is_off_by_default(self) -> None:
        # § 8.8: only `--cover` or `pages.cover: true` switches it on.
        assert PagesSpec().cover is False


class TestAPartialMargin:
    """`margin: 5mm` works, so setting one side is the obvious next step — and
    it produced `line 2, page.bottom: Field required`.

    Three things wrong at once: `page.bottom` is not a field that exists (it is
    `page.margin.bottom`), the line pointed at `page:` rather than at the margin,
    and "Field required" named one of the three missing sides without saying that
    a margin is all-or-nothing. § 12 asks a message to let the user act.
    """

    DEFINITION = (
        "version: 1\npage:\n  format: a4\n  margin:\n    top: 15mm\n"
        "generator: lines\nfamilies: [{direction: horizontal, base_spacing: 5mm}]\n"
    )

    def test_it_names_the_margin_and_the_sides_that_are_missing(self) -> None:
        from ctrlgrid.errors import DefinitionError
        from ctrlgrid.loader import loads

        with pytest.raises(DefinitionError) as excinfo:
            loads(self.DEFINITION, source="t")
        message = str(excinfo.value)
        assert "page.bottom" not in message
        assert "margin" in message
        for side in ("bottom", "inner", "outer"):
            assert side in message

    def test_the_scalar_shorthand_still_works(self) -> None:
        from ctrlgrid.loader import loads

        text = self.DEFINITION.replace("margin:\n    top: 15mm", "margin: 15mm")
        document = loads(text, source="t")
        assert document.sheet.margin.top.raw == "15mm"
