"""Device profiles and the `px` unit (§ 9.2, § 5.1) — the start of M5.

A profile carries **pixels and physical size**, and the density falls out of
the two; paper is simply the profile without pixels. Once a device is fixed,
`px` resolves — and only then: a paper format's `assumed_dpi` is a yardstick
for warnings (§ 12.1), never a real resolution, so `px` on paper stays an
error because geometry may not rest on a guessed number (§ 8.3.1).

The numbers here are the tool's most dangerous data: § 9.2 says a wrong device
figure is worse than no profile at all, which is why `source` and `verified`
are mandatory and why the Paper Pro is owner-verified while the rM2 is marked
unverified.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ctrlgrid.errors import DefinitionError
from ctrlgrid.loader import devices, loads
from ctrlgrid.pages import build
from ctrlgrid.writers.pdf import PdfWriter

BASE = (
    "generator: lines\n"
    "families:\n"
    "  - {direction: horizontal, base_spacing: 5mm}\n"
)


def sheet(page: str, blade: str = BASE, overrides: dict | None = None):
    return loads(f"version: 1\npage:\n{page}{blade}", overrides, source="test").sheet


class TestResolvingTheSheet:
    def test_a_device_gives_its_physical_size(self) -> None:
        # § 9.2: 1620 x 2160 px at 229 dpi is 179.7 x 239.6 mm, portrait.
        s = sheet("  device: remarkable-paper-pro\n")
        assert (s.width, s.height) == (179_700, 239_600)

    def test_e_ink_has_no_non_printable_margin(self) -> None:
        # § 8.1, § 9.2: a device has no unprintable border, so the default is 0.
        assert sheet("  device: remarkable-paper-pro\n").margin.top.um == 0

    def test_a_written_margin_still_wins(self) -> None:
        s = sheet("  device: remarkable-2\n  margin: 6mm\n")
        assert s.margin.inner.um == 6_000

    def test_landscape_swaps_the_stored_portrait(self) -> None:
        s = sheet("  device: remarkable-paper-pro\n  orientation: landscape\n")
        assert (s.width, s.height) == (239_600, 179_700)

    def test_an_unknown_device_lists_the_known_ones(self) -> None:
        with pytest.raises(DefinitionError) as excinfo:
            sheet("  device: remarkable-9\n")
        message = str(excinfo.value)
        assert "remarkable-paper-pro" in message and "remarkable-2" in message

    def test_device_and_format_together_are_an_error(self) -> None:
        # They are two answers to "what medium", pointing at different sizes.
        with pytest.raises(DefinitionError) as excinfo:
            sheet("  device: remarkable-2\n  format: a4\n")
        message = str(excinfo.value)
        assert "device" in message and "format" in message

    def test_the_device_flag_beats_the_definition(self) -> None:
        # § 11: the medium belongs to the call as much as the format does.
        s = sheet("  format: a4\n", overrides={"device": "remarkable-2"})
        assert (s.width, s.height) == (157_800, 210_400)


class TestThePixelUnit:
    def test_px_resolves_against_the_device_density(self) -> None:
        # § 9.2: 1 px at 229 dpi is 25400/229 = 110.92 um, to the micrometre.
        document = loads(
            "version: 1\npage:\n  device: remarkable-paper-pro\n"
            "generator: lines\nfamilies:\n"
            "  - {direction: horizontal, base_spacing: 45px}\n",
            source="test",
        )
        assert document.config.families[0].base_spacing.um == round(45 * 25400 / 229)
        assert document.config.families[0].base_spacing.raw == "45px"

    def test_px_on_a_paper_format_is_still_an_error(self) -> None:
        # § 8.3.1: assumed_dpi is a yardstick, not a resolution — px may not
        # rest on it.
        with pytest.raises(DefinitionError) as excinfo:
            sheet(
                "  format: a4\n",
                blade="generator: lines\nfamilies:\n"
                "  - {direction: horizontal, base_spacing: 45px}\n",
            )
        message = str(excinfo.value)
        assert "px" in message and "device" in message

    def test_px_without_any_medium_key_is_an_error(self) -> None:
        with pytest.raises(DefinitionError):
            loads(
                "version: 1\ngenerator: lines\nfamilies:\n"
                "  - {direction: horizontal, base_spacing: 45px}\n",
                source="test",
            )

    def test_px_no_longer_names_a_milestone(self) -> None:
        # M5 is here; the message should be about a device, not about waiting.
        with pytest.raises(DefinitionError) as excinfo:
            loads(
                "version: 1\ngenerator: lines\nfamilies:\n"
                "  - {direction: horizontal, base_spacing: 45px}\n",
                source="test",
            )
        assert "M5" not in str(excinfo.value)


class TestTheShippedProfiles:
    def test_the_pixels_are_stored_portrait(self) -> None:
        # § 9.2: portrait even where the maker counts landscape.
        for device in devices():
            assert device["pixels"]["y"] > device["pixels"]["x"]

    def test_the_physical_size_matches_pixels_over_density(self) -> None:
        # § 9.2: computed, not copied from marketing figures.
        for device in devices():
            px = device["pixels"]["x"]
            dpi = int(str(device["density"]).removesuffix("dpi"))
            expected_mm = px / dpi * 25.4
            written = float(str(device["physical"]["x"]).removesuffix("mm"))
            assert written == pytest.approx(expected_mm, abs=0.2)

    def test_source_and_verified_are_present(self) -> None:
        # § 9.2: mandatory on shipped profiles — device data goes quietly wrong.
        for device in devices():
            assert device["source"]
            assert device["verified"]

    def test_the_paper_pro_is_owner_verified(self) -> None:
        pro = next(d for d in devices() if d["id"] == "remarkable-paper-pro")
        assert "owner-verified" in pro["source"]

    def test_the_rm2_is_marked_unverified(self) -> None:
        # § 15 item 1: its numbers are only source-consistent, not checked.
        rm2 = next(d for d in devices() if d["id"] == "remarkable-2")
        assert "UNVERIFIED" in rm2["source"].upper()


class TestOnTheSheet:
    def test_a_device_page_reaches_the_pdf(self, tmp_path: Path) -> None:
        import pdfread

        path = tmp_path / "device.pdf"
        build(
            loads(
                "version: 1\npage:\n  device: remarkable-paper-pro\n" + BASE,
                source="test",
            ),
            PdfWriter(path),
        )
        width, height = pdfread.media_box_um(path)
        assert width == pytest.approx(179_700, abs=2)
        assert height == pytest.approx(239_600, abs=2)
