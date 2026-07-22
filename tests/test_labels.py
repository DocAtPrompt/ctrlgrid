"""Counting patterns (§ 7.10) — shared by `grid`, `polar` and `tiling`.

**Not a range with a beginning and an end, a counting pattern.** How many
labels there are follows from the generator; the pattern only says *how* to
count. That way nobody has to chase the end mark when the number of cells
changes — which is the whole reason § 7.10 exists.
"""

from __future__ import annotations

import pytest

from ctrlgrid.errors import DefinitionError
from ctrlgrid.labels import labels_for


class TestTheCountingCharacters:
    def test_n_counts_in_digits(self) -> None:
        assert labels_for("n", 3) == ["1", "2", "3"]

    def test_lowercase_a_counts_in_letters(self) -> None:
        assert labels_for("a", 3) == ["a", "b", "c"]

    def test_uppercase_a_counts_in_capitals(self) -> None:
        assert labels_for("A", 3) == ["A", "B", "C"]

    def test_everything_else_stands_literally(self) -> None:
        assert labels_for("Feld n", 2) == ["Feld 1", "Feld 2"]


class TestRepetitionSetsTheWidth:
    def test_two_digits_pad_to_two(self) -> None:
        assert labels_for("nn", 10)[:2] == ["01", "02"]
        assert labels_for("nn", 10)[-1] == "10"

    def test_three_digits_pad_to_three(self) -> None:
        assert labels_for("nnn", 1) == ["001"]

    def test_a_number_wider_than_its_pattern_is_not_cut(self) -> None:
        # § 12 forbids silent mutilation, and a cut label is worthless (§ 8.9).
        assert labels_for("nn", 120)[-1] == "120"


class TestLettersCarryOnLikeASpreadsheet:
    def test_after_z_comes_aa(self) -> None:
        assert labels_for("A", 28)[25:28] == ["Z", "AA", "AB"]

    def test_lowercase_does_the_same(self) -> None:
        assert labels_for("a", 27)[-1] == "aa"


class TestTheEscape:
    def test_a_backslash_makes_a_counting_character_literal(self) -> None:
        # § 7.10: `A` has to be able to mean both.
        assert labels_for(r"\An", 3) == ["A1", "A2", "A3"]

    def test_a_literal_backslash_survives(self) -> None:
        assert labels_for(r"\\n", 2) == [r"\1", r"\2"]

    def test_a_trailing_backslash_is_an_error(self) -> None:
        with pytest.raises(DefinitionError) as excinfo:
            labels_for("n\\", 2)
        assert "\\" in str(excinfo.value)


class TestSeveralCountersInOnePattern:
    def test_they_all_count_together(self) -> None:
        # One counter per pattern conceptually — every counting character in
        # the pattern shows the same number, in its own alphabet.
        assert labels_for("n-a", 2) == ["1-a", "2-b"]


class TestExplicitLists:
    def test_a_list_is_used_as_written(self) -> None:
        assert labels_for(["Nord", "Ost"], 2) == ["Nord", "Ost"]

    def test_a_list_of_the_wrong_length_names_both_numbers(self) -> None:
        # § 7.10: not padded and not cut.
        with pytest.raises(DefinitionError) as excinfo:
            labels_for(["Nord", "Ost"], 4)
        message = str(excinfo.value)
        assert "2" in message and "4" in message

    def test_numbers_in_a_list_are_allowed(self) -> None:
        # § 7.6 writes ring scores as `[10, 8, 6, 4]`.
        assert labels_for([10, 8], 2) == ["10", "8"]


class TestNone:
    def test_none_suppresses_the_labels_entirely(self) -> None:
        assert labels_for(None, 3) == []
        assert labels_for("none", 3) == []


class TestRefusals:
    def test_an_empty_pattern_is_an_error(self) -> None:
        with pytest.raises(DefinitionError):
            labels_for("", 3)

    def test_a_pattern_that_never_counts_is_an_error(self) -> None:
        # Ten cells all labelled "Feld" is not something anyone means, and
        # § 5.1 refuses to guess which of them was meant to be the counter.
        with pytest.raises(DefinitionError) as excinfo:
            labels_for("Feld", 3)
        assert "n" in str(excinfo.value)
