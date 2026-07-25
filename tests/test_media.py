"""The media check (§ 12.1) — the definition against the medium's resolution.

As soon as the medium is fixed — a device profile or a paper format — the tool
checks the definition against it and reports what will not work there. § 12.1 is
emphatic that this is **not the writer's job**: a 0.2 pt line is 0.64 px on a
229 dpi device whether the output is PDF or PNG, and hanging the check on the
PNG writer would find the fault only when it is already visible — and on the
usual PDF path, never.

The findings are warnings, not errors — the medium may be wanted anyway — with
two exceptions: a value that rounds to **zero** pixels is an error, and
`--strict` turns every warning into one so a CI run can guard a preset set.
Every finding carries the concrete number: "0.2pt = 0.64px at 229dpi", never
"line too thin".
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ctrlgrid.errors import DefinitionError
from ctrlgrid.loader import loads
from ctrlgrid.media import media_findings
from ctrlgrid.pages import preflight
from ctrlgrid.writers.pdf import PdfWriter

Q = PdfWriter("unused.pdf")


def findings(definition: str) -> list[str]:
    document = loads(definition, source="test")
    return media_findings(document, Q)


DEVICE = "version: 1\npage:\n  device: remarkable-paper-pro\n"
# The Paper Pro is a colour device (owner-confirmed, § 15 item 1), so the
# grayscale colour findings are tested against the rM2, which is grayscale.
GRAY = "version: 1\npage:\n  device: remarkable-2\n"
PAPER = "version: 1\npage:\n  format: a4\n"


class TestResolutionFindings:
    def test_a_thin_line_on_e_ink_is_flagged_with_the_number(self) -> None:
        # § 12.1's own example: 0.2pt at 229dpi is 0.64px.
        notes = findings(
            DEVICE + "generator: lines\nfamilies:\n"
            "  - {direction: horizontal, base_spacing: 5mm, base_weight: 0.2pt}\n"
        )
        assert any("0.2pt" in note and "0.6" in note and "px" in note for note in notes)

    def test_a_line_that_rounds_to_zero_pixels_is_an_error(self) -> None:
        # § 12.1: warnings do not abort, but a value that vanishes entirely does.
        with pytest.raises(DefinitionError) as excinfo:
            findings(
                DEVICE + "generator: lines\nfamilies:\n"
                "  - {direction: horizontal, base_spacing: 5mm, base_weight: 0.02pt}\n"
            )
        assert "px" in str(excinfo.value)

    def test_a_comfortable_line_says_nothing(self) -> None:
        # 0.9pt at 229dpi is 2.86px — clear of both the <1px and the 1-2px
        # e-ink findings.
        notes = findings(
            DEVICE + "generator: lines\nfamilies:\n"
            "  - {direction: horizontal, base_spacing: 5mm, base_weight: 0.9pt}\n"
        )
        assert not any("stroke" in note.lower() for note in notes)

    def test_cells_that_do_not_land_on_whole_pixels_are_flagged(self) -> None:
        # § 12.1: a 5 mm grid is 45.08 px at 229 dpi — alternately 45 and 46,
        # and the message names the cell width and the swing, not "not integer".
        notes = findings(
            DEVICE + "generator: lines\nfamilies:\n"
            "  - {direction: horizontal, base_spacing: 5mm, base_weight: 0.6pt}\n"
        )
        assert any("45" in note and "px" in note for note in notes)

    def test_spacing_below_three_pixels_is_flagged(self) -> None:
        notes = findings(
            DEVICE + "generator: lines\nfamilies:\n"
            "  - {direction: horizontal, base_spacing: 0.3mm, base_weight: 0.2pt}\n"
        )
        assert any("merge" in note.lower() or "flow" in note.lower() for note in notes)


class TestColourFindings:
    def test_colour_on_a_grayscale_device_names_the_grey(self) -> None:
        notes = findings(
            GRAY + "generator: lines\nfamilies:\n"
            "  - {direction: horizontal, base_spacing: 5mm, base_weight: 0.6pt, "
            "color: '#cc0000'}\n"
        )
        assert any("grey" in note.lower() or "gray" in note.lower() for note in notes)

    def test_two_colours_that_collapse_to_one_grey_are_flagged(self) -> None:
        # § 12.1's insidious case: #7799bb and #4466aa are a clear difference in
        # colour and nearly the same grey — the emphasis vanishes.
        notes = findings(
            GRAY + "generator: lines\nfamilies:\n"
            "  - direction: horizontal\n    base_spacing: 5mm\n    base_weight: 0.6pt\n"
            "    color: ['#7799bb', '#7799bb', '#7799bb', '#7799bb', '#4466aa']\n"
        )
        assert any("emphasis" in note.lower() or "same grey" in note.lower()
                   or "same gray" in note.lower() for note in notes)

    def test_a_grayscale_definition_says_nothing_about_colour(self) -> None:
        notes = findings(
            GRAY + "generator: lines\nfamilies:\n"
            "  - {direction: horizontal, base_spacing: 5mm, base_weight: 0.6pt, "
            "color: '#000000'}\n"
        )
        assert not any("grey" in note.lower() for note in notes)

    def test_a_colour_device_says_nothing_about_grey(self) -> None:
        # The Paper Pro is a colour device (owner-confirmed, § 15 item 1): a red
        # line stays red, so there is no grey finding — unlike on the rM2.
        notes = findings(
            DEVICE + "generator: lines\nfamilies:\n"
            "  - {direction: horizontal, base_spacing: 5mm, base_weight: 0.6pt, "
            "color: '#cc0000'}\n"
        )
        assert not any("grey" in note.lower() or "gray" in note.lower() for note in notes)


class TestPaperUsesAssumedDpi:
    def test_a_thin_line_on_paper_is_measured_against_assumed_dpi(self) -> None:
        # § 12.1: the check runs on paper too, against the format's assumed_dpi.
        # 0.15pt at 600dpi is 1.25px — fine — but 0.08pt is 0.67px.
        notes = findings(
            PAPER + "generator: lines\nfamilies:\n"
            "  - {direction: horizontal, base_spacing: 5mm, base_weight: 0.08pt}\n"
        )
        assert any("600" in note and "px" in note for note in notes)

    def test_the_ordinary_millimetre_preset_is_clean_on_paper(self) -> None:
        from ctrlgrid.loader import load_preset

        document = load_preset("millimeter-a4")
        assert media_findings(document, Q) == []

    def test_every_shipped_preset_is_clean_on_its_own_medium(self) -> None:
        # A preset is documentation (§ 9.3), and one that warns about itself
        # teaches the wrong thing. This caught a 0.1pt stroke — 0.83px at
        # 600 dpi — in two presets on the day it was written.
        from ctrlgrid.loader import load_preset, preset_names

        for name in preset_names():
            document = load_preset(name)
            assert media_findings(document, Q) == [], f"{name} warns about itself"


class TestStrict:
    def test_strict_turns_a_warning_into_an_error(self) -> None:
        definition = (
            GRAY + "generator: lines\nfamilies:\n"
            "  - {direction: horizontal, base_spacing: 5mm, base_weight: 0.6pt, "
            "color: '#cc0000'}\n"
        )
        # Not strict: a notice.
        assert media_findings(loads(definition, source="test"), Q)
        # Strict: the same finding raised.
        with pytest.raises(DefinitionError):
            media_findings(loads(definition, source="test"), Q, strict=True)


class TestInThePreflight:
    def test_findings_reach_the_run_as_notices(self) -> None:
        document = loads(
            DEVICE + "generator: lines\nfamilies:\n"
            "  - {direction: horizontal, base_spacing: 5mm, base_weight: 0.2pt}\n",
            source="test",
        )
        geometry, _, _, _ = preflight(document, Q)
        assert any("px" in note for note in geometry.notices)

    def test_a_round_to_zero_stops_the_preflight(self, tmp_path: Path) -> None:
        from ctrlgrid.pages import build

        document = loads(
            DEVICE + "generator: lines\nfamilies:\n"
            "  - {direction: horizontal, base_spacing: 5mm, base_weight: 0.01pt}\n",
            source="test",
        )
        path = tmp_path / "never.pdf"
        with pytest.raises(DefinitionError):
            build(document, PdfWriter(path))
        assert not path.exists()


class TestDocumentGenerators:
    """§ 12.1 for a generator that owns its pages (§ 7).

    The check reads marks, and a document has no single pattern area to read
    them from — it has pages. Every page is walked, not one per page kind: a
    marked day's own colour appears only on the pages carrying that date, so a
    shortcut would measure January and miss a birthday in May.
    """

    CALENDAR = (
        "generator: calendar\nyear: 2026\n"
        "holiday_color: '#fce9e4'\n"
        "holidays:\n"
        "  - {date: 2026-05-03, label: 'a birthday', color: '#cc4488'}\n"
        "notes: {count: 2}\n"
    )

    def test_a_colour_that_appears_only_on_a_late_page_is_still_found(self) -> None:
        # The birthday is in May; its colour is on no page before it. On a
        # grayscale device it turns to mud, and that has to be said.
        notes = findings(GRAY + self.CALENDAR)
        assert any("#cc4488" in note for note in notes)

    def test_the_title_pages_full_sheet_colour_counts_as_a_colour(self) -> None:
        # The fill is a page property the handle paints, not a mark — but on a
        # grayscale screen it is exactly what goes flat.
        notes = findings(
            GRAY + self.CALENDAR + "title_page: {title: '2026', background: '#2f3a48'}\n"
        )
        assert any("#2f3a48" in note for note in notes)

    def test_a_calendar_on_paper_says_nothing(self) -> None:
        from ctrlgrid.loader import load_preset

        assert media_findings(load_preset("calendar-a4"), Q) == []

    def test_strict_turns_a_documents_finding_into_an_error(self) -> None:
        document = loads(GRAY + self.CALENDAR, None, source="test")
        with pytest.raises(DefinitionError):
            media_findings(document, Q, strict=True)


class TestDocumentsInTheRun:
    """The check has to be *called* on the document path, not merely callable.

    A calendar wants a wide sheet — the twelve mini-months of its year page are
    refused on a portrait e-ink screen (§ 9) — so the medium here is a landscape
    reMarkable 2, which is also the case a user would actually meet.
    """

    ON_A_GRAYSCALE_SCREEN = (
        "version: 1\npage:\n  device: remarkable-2\n  orientation: landscape\n"
        "  margin: 0mm\n"
        "generator: calendar\nyear: 2026\n"
        "holidays:\n  - {date: 2026-05-03, label: 'a birthday', color: '#cc4488'}\n"
    )

    def test_the_preflight_reports_a_documents_findings_as_notices(self) -> None:
        document = loads(self.ON_A_GRAYSCALE_SCREEN, None, source="test")
        geometry, _contexts, _bands, _cover = preflight(document, Q)
        # The link blue and the birthday pink read as one tone there — a real
        # finding, and one nothing said before the check reached documents.
        assert any("#cc4488" in note for note in geometry.notices)

    def test_strict_stops_a_document_run_at_the_preflight(self) -> None:
        document = loads(self.ON_A_GRAYSCALE_SCREEN, {"strict": True}, source="test")
        with pytest.raises(DefinitionError):
            preflight(document, Q)
