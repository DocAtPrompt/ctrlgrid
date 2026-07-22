"""The command line (§ 11) — and acceptance criteria 1 and 4 of § 14.

Criterion 1: `ctrlgrid millimeter-a4 --pages 3 -o out.pdf` produces a
three-page PDF with no further setup. Criterion 4: `check` reports a
misspelled key *with a suggestion*, and an overlong header field with the field
name, its width and the space available.
"""

from __future__ import annotations

from pathlib import Path

import pdfread
from typer.testing import CliRunner

from ctrlgrid.cli import app

runner = CliRunner()

WITH_HEADER = """
version: 1
page:
  format: a6
header:
  height: 12mm
  gap: 4mm
  center: "Maximilian Sonnenschein-Hofstätter and the whole of class 3B besides"
generator: lines
families:
  - direction: horizontal
    base_spacing: 5mm
"""


def write(tmp_path: Path, text: str, name: str = "def.yaml") -> Path:
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


class TestGenerating:
    def test_a_preset_and_a_page_count_give_a_pdf(self, tmp_path: Path) -> None:
        out = tmp_path / "out.pdf"
        result = runner.invoke(app, ["millimeter-a4", "--pages", "3", "-o", str(out)])
        assert result.exit_code == 0, result.output
        assert pdfread.page_count(out) == 3

    def test_an_own_definition_file_works_too(self, tmp_path: Path) -> None:
        definition = write(tmp_path, "version: 1\ngenerator: lines\nfamilies:\n"
                                     "  - direction: horizontal\n    base_spacing: 5mm\n")
        out = tmp_path / "own.pdf"
        result = runner.invoke(app, ["-d", str(definition), "-o", str(out)])
        assert result.exit_code == 0, result.output
        assert out.exists()

    def test_the_run_reports_the_path_and_the_scaling_setting(self, tmp_path: Path) -> None:
        # § 8.2: we cannot stop a print driver scaling, but we can name the
        # setting concretely instead of saying "mind the scaling".
        out = tmp_path / "out.pdf"
        result = runner.invoke(app, ["millimeter-a4", "-o", str(out)])
        assert str(out) in result.output
        assert "100" in result.output or "Actual size" in result.output

    def test_quiet_reports_only_the_path(self, tmp_path: Path) -> None:
        out = tmp_path / "out.pdf"
        result = runner.invoke(app, ["millimeter-a4", "-o", str(out), "--quiet"])
        assert result.output.strip() == str(out)

    def test_the_effective_period_is_reported(self, tmp_path: Path) -> None:
        # § 5.3: both numbers, marks and millimetres.
        result = runner.invoke(app, ["millimeter-a4", "-o", str(tmp_path / "o.pdf")])
        assert "5" in result.output and "mm" in result.output


class TestNotices:
    """§ 8.3 — a setting that cannot take effect is said once, not per page."""

    POINTLESS = """
version: 1
pattern:
  snap: cycle
  remainder: whole_cycles
generator: lines
families:
  - {direction: horizontal, base_spacing: 5mm, spacing: [1, 1, 2]}
"""

    def test_a_setting_without_effect_is_pointed_out(self, tmp_path: Path) -> None:
        definition = write(tmp_path, self.POINTLESS)
        result = runner.invoke(app, ["-d", str(definition), "-o", str(tmp_path / "o.pdf")])
        assert result.exit_code == 0, result.output
        assert "whole_cycles" in result.output

    def test_it_is_a_notice_and_not_a_refusal(self, tmp_path: Path) -> None:
        definition = write(tmp_path, self.POINTLESS)
        out = tmp_path / "o.pdf"
        runner.invoke(app, ["-d", str(definition), "-o", str(out)])
        assert out.exists()

    def test_check_says_it_too(self, tmp_path: Path) -> None:
        definition = write(tmp_path, self.POINTLESS)
        result = runner.invoke(app, ["check", str(definition)])
        assert result.exit_code == 0, result.output
        assert "whole_cycles" in result.output

    def test_quiet_reports_only_the_path(self, tmp_path: Path) -> None:
        definition = write(tmp_path, self.POINTLESS)
        out = tmp_path / "o.pdf"
        result = runner.invoke(app, ["-d", str(definition), "-o", str(out), "--quiet"])
        assert result.output.strip() == str(out)


class TestNotOverwriting:
    def test_an_existing_file_is_not_overwritten_silently(self, tmp_path: Path) -> None:
        # § 11.3: comparable tools are criticised by name for doing this.
        out = tmp_path / "out.pdf"
        out.write_text("precious", encoding="utf-8")
        result = runner.invoke(app, ["millimeter-a4", "-o", str(out)])
        assert result.exit_code != 0
        assert "--force" in result.output
        assert out.read_text(encoding="utf-8") == "precious"

    def test_force_overwrites(self, tmp_path: Path) -> None:
        out = tmp_path / "out.pdf"
        out.write_text("precious", encoding="utf-8")
        result = runner.invoke(app, ["millimeter-a4", "-o", str(out), "--force"])
        assert result.exit_code == 0, result.output
        assert out.read_bytes().startswith(b"%PDF")


class TestCheck:
    def test_a_valid_definition_passes(self, tmp_path: Path) -> None:
        definition = write(tmp_path, "version: 1\ngenerator: lines\nfamilies:\n"
                                     "  - direction: horizontal\n    base_spacing: 5mm\n")
        result = runner.invoke(app, ["check", str(definition)])
        assert result.exit_code == 0, result.output

    def test_a_misspelled_key_is_reported_with_a_suggestion(self, tmp_path: Path) -> None:
        # Acceptance criterion 4, first half (§ 14).
        definition = write(tmp_path, "version: 1\ngenerator: lines\nfamilies:\n"
                                     "  - direction: horizontal\n    base_spacng: 5mm\n")
        result = runner.invoke(app, ["check", str(definition)])
        assert result.exit_code != 0
        assert "base_spacng" in result.output
        assert "base_spacing" in result.output

    def test_an_overlong_header_names_field_width_and_space(self, tmp_path: Path) -> None:
        # Acceptance criterion 4, second half (§ 14, § 8.9).
        definition = write(tmp_path, WITH_HEADER)
        result = runner.invoke(app, ["check", str(definition)])
        assert result.exit_code != 0
        assert "header.center" in result.output
        assert "mm" in result.output

    def test_check_writes_nothing(self, tmp_path: Path) -> None:
        definition = write(tmp_path, "version: 1\ngenerator: lines\nfamilies:\n"
                                     "  - direction: horizontal\n    base_spacing: 5mm\n")
        runner.invoke(app, ["check", str(definition)])
        assert list(tmp_path.iterdir()) == [definition]


class TestListing:
    def test_presets_are_listed(self) -> None:
        result = runner.invoke(app, ["presets"])
        assert "millimeter-a4" in result.output

    def test_devices_are_listed_with_their_provenance(self) -> None:
        # § 9.2: `source` and `verified` are mandatory, so they are shown.
        result = runner.invoke(app, ["devices"])
        assert "remarkable-paper-pro" in result.output
        assert "2026-07" in result.output

    def test_show_prints_a_definition_ready_to_copy(self) -> None:
        result = runner.invoke(app, ["show", "millimeter-a4"])
        assert "version: 1" in result.output
        assert "base_spacing: 1mm" in result.output


class TestFailingLoudly:
    def test_an_unknown_preset_exits_non_zero_with_a_list(self) -> None:
        result = runner.invoke(app, ["millimeter-a5"])
        assert result.exit_code != 0
        assert "millimeter-a4" in result.output

    def test_a_broken_definition_does_not_leave_half_a_file(self, tmp_path: Path) -> None:
        # § 12: abort completely or build completely.
        definition = write(tmp_path, WITH_HEADER)
        out = tmp_path / "out.pdf"
        result = runner.invoke(app, ["-d", str(definition), "-o", str(out)])
        assert result.exit_code != 0
        assert not out.exists()
