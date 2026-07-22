"""Seam 1 — definition file to validated model (§ 3.6, § 5, § 12).

The reason `ruamel.yaml` is a requirement rather than a preference lives here
(§ 13): the loader must be able to say *line 47*, not
`families.2.base_spacing`. On an eighty-line preset copy the difference is
between an answer and a search.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ctrlgrid.errors import DefinitionError
from ctrlgrid.loader import formats, load, load_preset, preset_names

MINIMAL = """
version: 1
generator: lines
families:
  - direction: horizontal
    base_spacing: 5mm
"""


def write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "def.yaml"
    path.write_text(text, encoding="utf-8")
    return path


class TestLoading:
    def test_a_minimal_definition_loads(self, tmp_path: Path) -> None:
        document = load(write(tmp_path, MINIMAL))
        assert document.generator == "lines"
        assert len(document.config.families) == 1

    def test_units_are_gone_afterwards(self, tmp_path: Path) -> None:
        # § 3.6: after load there are no strings with units left in the core.
        document = load(write(tmp_path, MINIMAL))
        assert document.config.families[0].base_spacing.um == 5000

    def test_the_version_line_is_mandatory(self, tmp_path: Path) -> None:
        with pytest.raises(DefinitionError) as excinfo:
            load(write(tmp_path, "generator: lines\nfamilies: []\n"))
        assert "version" in str(excinfo.value)

    def test_an_unsupported_version_is_an_error(self, tmp_path: Path) -> None:
        with pytest.raises(DefinitionError) as excinfo:
            load(write(tmp_path, MINIMAL.replace("version: 1", "version: 2")))
        assert "2" in str(excinfo.value)

    def test_a_missing_file_says_so(self, tmp_path: Path) -> None:
        with pytest.raises(DefinitionError) as excinfo:
            load(tmp_path / "nope.yaml")
        assert "nope.yaml" in str(excinfo.value)


class TestErrorsPointAtTheLine:
    def test_a_syntax_error_carries_its_line(self, tmp_path: Path) -> None:
        with pytest.raises(DefinitionError) as excinfo:
            load(write(tmp_path, "version: 1\npage:\n  format: a4\n   bad: indent\n"))
        assert "line" in str(excinfo.value)

    def test_a_bad_value_carries_its_line(self, tmp_path: Path) -> None:
        # The whole reason ruamel.yaml is a requirement (§ 13).
        text = MINIMAL.replace("base_spacing: 5mm", "base_spacing: 5")
        with pytest.raises(DefinitionError) as excinfo:
            load(write(tmp_path, text))
        message = str(excinfo.value)
        assert "line 6" in message
        assert "base_spacing" in message


class TestUnknownKeys:
    def test_a_typo_gets_a_suggestion(self, tmp_path: Path) -> None:
        # § 12 point 4. Without this the tool produces a PDF that is *almost*
        # right, which is the worst failure class there is.
        with pytest.raises(DefinitionError) as excinfo:
            load(write(tmp_path, MINIMAL + "pge:\n  format: a4\n"))
        message = str(excinfo.value)
        assert "pge" in message and "page" in message

    def test_a_typo_inside_a_section_gets_a_suggestion(self, tmp_path: Path) -> None:
        text = MINIMAL.replace("base_spacing: 5mm", "base_spacng: 5mm")
        with pytest.raises(DefinitionError) as excinfo:
            load(write(tmp_path, text))
        message = str(excinfo.value)
        assert "base_spacng" in message and "base_spacing" in message


class TestAnchorsAndAliases:
    def test_defs_is_skipped_by_validation(self, tmp_path: Path) -> None:
        text = """
version: 1
defs:
  grid: &grid "#7799bb"
generator: lines
families:
  - direction: horizontal
    base_spacing: 5mm
    color: [*grid, *grid, "#4466aa"]
"""
        document = load(write(tmp_path, text))
        assert document.config.families[0].color == ("#7799bb", "#7799bb", "#4466aa")

    def test_merge_keys_are_refused(self, tmp_path: Path) -> None:
        # § 5.4: merge keys are inheritance, and inheritance is a non-goal —
        # one the parser just happens to bring along.
        text = """
version: 1
defs:
  base: &base { direction: horizontal, base_spacing: 5mm }
generator: lines
families:
  - <<: *base
"""
        with pytest.raises(DefinitionError) as excinfo:
            load(write(tmp_path, text))
        message = str(excinfo.value)
        assert "merge" in message.lower() and "copy" in message.lower()

    def test_an_oversized_expansion_is_refused(self, tmp_path: Path) -> None:
        # § 5.4: safe loading does not protect against expansion, and defs get
        # copied out of other people's repositories.
        bomb = "version: 1\ndefs:\n  a: &a [x, x, x, x, x, x, x, x, x]\n"
        for letter, previous in zip("bcdefghi", "abcdefgh", strict=True):
            bomb += f"  {letter}: &{letter} [{', '.join(['*' + previous] * 9)}]\n"
        bomb += "generator: lines\nfamilies: []\n"
        with pytest.raises(DefinitionError) as excinfo:
            load(write(tmp_path, bomb))
        assert "expansion" in str(excinfo.value).lower()


class TestGenerators:
    def test_an_unknown_generator_gets_a_suggestion(self, tmp_path: Path) -> None:
        with pytest.raises(DefinitionError) as excinfo:
            load(write(tmp_path, MINIMAL.replace("generator: lines", "generator: line")))
        message = str(excinfo.value)
        assert "line" in message and "lines" in message

    def test_the_generator_key_is_mandatory(self, tmp_path: Path) -> None:
        with pytest.raises(DefinitionError) as excinfo:
            load(write(tmp_path, "version: 1\nfamilies: []\n"))
        assert "generator" in str(excinfo.value)


class TestFormats:
    def test_a4_comes_from_the_table_not_from_the_code(self) -> None:
        a4 = formats()["a4"]
        assert (a4.width.um, a4.height.um) == (210000, 297000)

    def test_the_margin_default_is_a_property_of_the_format(self, tmp_path: Path) -> None:
        # § 8.1: paper carries 5 mm, device profiles carry 0.
        document = load(write(tmp_path, MINIMAL))
        assert document.sheet.margin.top.um == 5000

    def test_a_definition_margin_wins_over_the_format_default(self, tmp_path: Path) -> None:
        text = MINIMAL.replace("version: 1", "version: 1\npage:\n  margin: 10mm")
        assert load(write(tmp_path, text)).sheet.margin.top.um == 10000

    def test_landscape_swaps_the_sides(self, tmp_path: Path) -> None:
        text = MINIMAL.replace("version: 1", "version: 1\npage:\n  orientation: landscape")
        sheet = load(write(tmp_path, text)).sheet
        assert (sheet.width, sheet.height) == (297000, 210000)

    def test_an_unknown_format_lists_the_known_ones(self, tmp_path: Path) -> None:
        text = MINIMAL.replace("version: 1", "version: 1\npage:\n  format: a9")
        with pytest.raises(DefinitionError) as excinfo:
            load(write(tmp_path, text))
        message = str(excinfo.value)
        assert "a9" in message and "a4" in message and "letter" in message


class TestOverrides:
    def test_the_command_line_beats_the_definition(self, tmp_path: Path) -> None:
        # § 11, without exception: the definition gives the default, the call
        # gives the deviation for this one run.
        text = MINIMAL.replace("version: 1", "version: 1\npages:\n  count: 30")
        document = load(write(tmp_path, text), {"pages": 3})
        assert document.pages.count == 3

    def test_an_override_of_none_leaves_the_definition_alone(self, tmp_path: Path) -> None:
        text = MINIMAL.replace("version: 1", "version: 1\npages:\n  count: 30")
        assert load(write(tmp_path, text), {"pages": None}).pages.count == 30

    def test_the_format_can_be_overridden(self, tmp_path: Path) -> None:
        document = load(write(tmp_path, MINIMAL), {"format": "letter"})
        assert document.sheet.width == 215900


class TestPresets:
    def test_millimeter_a4_ships(self) -> None:
        # Acceptance criterion 1 of § 14 rests on this one existing.
        assert "millimeter-a4" in preset_names()

    def test_a_preset_is_an_ordinary_definition_file(self) -> None:
        # § 9.3: not a special path through the code, or the tool splits into
        # preset land and custom land.
        document = load_preset("millimeter-a4")
        assert document.generator == "lines"

    def test_every_shipped_preset_validates(self) -> None:
        for name in preset_names():
            load_preset(name)

    def test_an_unknown_preset_lists_the_known_ones(self) -> None:
        with pytest.raises(DefinitionError) as excinfo:
            load_preset("millimeter-a5")
        message = str(excinfo.value)
        assert "millimeter-a5" in message and "millimeter-a4" in message
