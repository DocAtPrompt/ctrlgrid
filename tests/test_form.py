"""The `form` blade (§ 7.8) — rows first, then columns.

Not a global grid like CSS Grid: a sequence of rows, each with its own column
split. § 7.8 gives the reason and it is a good one — forms are *thought* and
*described* row by row ("three fields across the top, a wide note area under
them"), and a global column raster forces the common denominator: three equal
fields over a 25/50/25 row would need twelve columns and spans of 4/4/4 and
3/6/3. Technically possible, unreadable, and the presets are documentation.

The most important sentence of the section is about two kinds of measure:
**row and column sizes are relative** — they divide the room available — **but
the writing lines inside a field are absolute.** `line_spacing: 8mm` means
8 mm, and how many lines fit follows from that. The other way round would be a
stretched grid, which § 8.2 rules out.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from ctrlgrid.errors import DefinitionError
from ctrlgrid.generators.form import FormConfig, FormGenerator
from ctrlgrid.loader import loads
from ctrlgrid.marks import Area, Polygon, Segment, Text
from ctrlgrid.pages import PageContext, build
from ctrlgrid.writers.pdf import PdfWriter

AREA = Area(width=100_000, height=100_000)
PAGE = PageContext(index=0, number=1, count=1, name=None, is_even=False, seed_material=b"")
NAMED = PageContext(
    index=0, number=1, count=1, name="Ada", is_even=False, seed_material=b""
)
Q = PdfWriter("unused.pdf")

THREE = {
    "rows": [
        {"columns": [{"title": "Datum"}, {"title": "Uhrzeit"}, {"title": "Anrufer"}]}
    ]
}


def marks(definition: dict, page: PageContext = PAGE, area: Area = AREA) -> list:
    config = FormConfig.model_validate(definition)
    return list(FormGenerator().generate(config, area=area, page=page, q=Q))


def boxes(definition: dict, page: PageContext = PAGE) -> list[Polygon]:
    return [mark for mark in marks(definition, page) if isinstance(mark, Polygon)]


def texts(definition: dict, page: PageContext = PAGE) -> list[Text]:
    return [mark for mark in marks(definition, page) if isinstance(mark, Text)]


def width_of(box: Polygon) -> int:
    return max(p.x for p in box.points) - min(p.x for p in box.points)


def height_of(box: Polygon) -> int:
    return max(p.y for p in box.points) - min(p.y for p in box.points)


class TestTheDefaultSplit:
    def test_columns_without_a_width_share_equally(self) -> None:
        # § 7.8: the commonest case, and therefore the default — three equal
        # fields are written by saying nothing about their width.
        drawn = boxes({**THREE, "gap": "2mm"})
        assert len(drawn) == 3
        assert len({width_of(box) for box in drawn}) == 1

    def test_the_gaps_come_off_before_the_share(self) -> None:
        # § 7.8: "available" means the pattern area *after* every gap, or
        # several percentages together would add up to more than the sheet.
        drawn = boxes({**THREE, "gap": "2mm"})
        assert sum(width_of(box) for box in drawn) == 100_000 - 2 * 2_000

    def test_one_row_fills_the_height(self) -> None:
        assert height_of(boxes(THREE)[0]) == 100_000


class TestMeasures:
    def test_a_percentage_is_a_share_of_what_is_available(self) -> None:
        drawn = boxes(
            {
                "gap": "0mm",
                "rows": [
                    {"height": "20%", "columns": [{"title": "a"}]},
                    {"columns": [{"title": "b"}]},
                ],
            }
        )
        assert height_of(drawn[0]) == 20_000

    def test_an_absolute_measure_is_taken_as_written(self) -> None:
        drawn = boxes(
            {
                "gap": "0mm",
                "rows": [
                    {"height": "40mm", "columns": [{"title": "a"}]},
                    {"columns": [{"title": "b"}]},
                ],
            }
        )
        assert height_of(drawn[0]) == 40_000

    def test_rest_takes_what_is_left(self) -> None:
        drawn = boxes(
            {
                "gap": "0mm",
                "rows": [
                    {"height": "30mm", "columns": [{"title": "a"}]},
                    {"height": "rest", "columns": [{"title": "b"}]},
                ],
            }
        )
        assert height_of(drawn[1]) == 70_000

    def test_several_rests_share_equally(self) -> None:
        drawn = boxes(
            {
                "gap": "0mm",
                "rows": [
                    {"height": "20mm", "columns": [{"title": "a"}]},
                    {"height": "rest", "columns": [{"title": "b"}]},
                    {"height": "rest", "columns": [{"title": "c"}]},
                ],
            }
        )
        assert height_of(drawn[1]) == height_of(drawn[2]) == 40_000

    def test_the_named_column_of_the_example_leaves_the_rest_to_share(self) -> None:
        # § 7.8's own example: `width: 50%` on the middle field, the other two
        # share 25 / 25.
        drawn = boxes(
            {
                "gap": "0mm",
                "rows": [
                    {
                        "columns": [
                            {"title": "Firma"},
                            {"title": "Betreff", "width": "50%"},
                            {"title": "Dringend"},
                        ]
                    }
                ],
            }
        )
        assert [width_of(box) for box in drawn] == [25_000, 50_000, 25_000]

    def test_more_than_the_room_is_an_error_with_both_numbers(self) -> None:
        # § 8.2: not squeezed.
        config = FormConfig.model_validate(
            {
                "gap": "0mm",
                "rows": [
                    {"height": "70mm", "columns": [{"title": "a"}]},
                    {"height": "60mm", "columns": [{"title": "b"}]},
                ],
            }
        )
        with pytest.raises(DefinitionError) as excinfo:
            FormGenerator().check(config, area=AREA, q=Q)
        message = str(excinfo.value)
        assert "130.0mm" in message and "100.0mm" in message


class TestNesting:
    def test_a_column_may_hold_rows(self) -> None:
        # § 7.8: exactly one level, for a tall field beside two short ones.
        drawn = boxes(
            {
                "gap": "0mm",
                "rows": [
                    {
                        "columns": [
                            {
                                "width": "40%",
                                "rows": [
                                    {"columns": [{"title": "from"}]},
                                    {"columns": [{"title": "to"}]},
                                ],
                            },
                            {"title": "Notiz"},
                        ]
                    }
                ],
            }
        )
        assert len(drawn) == 3
        assert sorted(height_of(box) for box in drawn) == [50_000, 50_000, 100_000]

    def test_two_levels_are_refused(self) -> None:
        # Deeper than one level would be a general layout language, and § 2
        # rules that out.
        with pytest.raises(ValidationError) as excinfo:
            FormConfig.model_validate(
                {
                    "rows": [
                        {
                            "columns": [
                                {
                                    "rows": [
                                        {"columns": [{"rows": [{"columns": [{"title": "x"}]}]}]}
                                    ]
                                }
                            ]
                        }
                    ]
                }
            )
        assert "one level" in str(excinfo.value)

    def test_a_column_is_a_field_or_a_nest_but_not_both(self) -> None:
        with pytest.raises(ValidationError):
            FormConfig.model_validate(
                {
                    "rows": [
                        {
                            "columns": [
                                {"title": "x", "rows": [{"columns": [{"title": "y"}]}]}
                            ]
                        }
                    ]
                }
            )


class TestFieldKinds:
    def test_text_is_the_default(self) -> None:
        assert texts(THREE)[0].content == "Datum"

    def test_check_draws_one_box(self) -> None:
        drawn = boxes(
            {"rows": [{"columns": [{"title": "Erledigt", "kind": "check"}]}]}
        )
        # The field itself plus the tick box.
        assert len(drawn) == 2

    def test_choice_draws_a_box_for_every_option(self) -> None:
        # § 7.8: Ja/Nein is not a type of its own, it is the two-case of the
        # general one — and the words come from the definition (§ 3.4).
        definition = {
            "rows": [
                {
                    "columns": [
                        {
                            "title": "Dringend",
                            "kind": "choice",
                            "options": ["Ja", "Nein", "Unklar"],
                        }
                    ]
                }
            ]
        }
        assert len(boxes(definition)) == 1 + 3
        assert {text.content for text in texts(definition)} >= {"Ja", "Nein", "Unklar"}

    def test_choice_without_options_is_an_error(self) -> None:
        with pytest.raises(ValidationError):
            FormConfig.model_validate(
                {"rows": [{"columns": [{"title": "x", "kind": "choice"}]}]}
            )

    def test_options_on_a_text_field_are_an_error(self) -> None:
        with pytest.raises(ValidationError):
            FormConfig.model_validate(
                {"rows": [{"columns": [{"title": "x", "options": ["a"]}]}]}
            )


class TestRulingIsAbsolute:
    def test_line_spacing_means_millimetres(self) -> None:
        # The most important point of the whole generator (§ 7.8): the raster
        # is relative, the writing lines are not.
        rules = [
            mark
            for mark in marks(
                {"rows": [{"columns": [{"title": "Notiz", "line_spacing": "8mm"}]}]}
            )
            if isinstance(mark, Segment)
        ]
        heights = sorted(rule.start.y for rule in rules)
        assert all(
            heights[index + 1] - heights[index] == 8_000
            for index in range(len(heights) - 1)
        )

    def test_the_number_of_lines_follows_from_the_field(self) -> None:
        tall = [
            mark
            for mark in marks(
                {"rows": [{"columns": [{"title": "Notiz", "line_spacing": "8mm"}]}]}
            )
            if isinstance(mark, Segment)
        ]
        short = [
            mark
            for mark in marks(
                {"rows": [{"columns": [{"title": "Notiz", "line_spacing": "8mm"}]}]},
                area=Area(width=100_000, height=40_000),
            )
            if isinstance(mark, Segment)
        ]
        assert len(tall) > len(short)

    def test_a_fixed_line_count_that_does_not_fit_is_an_error(self) -> None:
        config = FormConfig.model_validate(
            {
                "rows": [
                    {"columns": [{"title": "Notiz", "line_spacing": "8mm", "lines": 40}]}
                ]
            }
        )
        with pytest.raises(DefinitionError) as excinfo:
            FormGenerator().check(config, area=AREA, q=Q)
        assert "40" in str(excinfo.value)


class TestTitles:
    def test_a_title_too_wide_for_its_cell_is_an_error(self) -> None:
        # § 7.8: titles are measured beforehand, and `cut` (§ 8.9) does not
        # apply to generator labels.
        config = FormConfig.model_validate(
            {
                "rows": [
                    {
                        "columns": [
                            {"title": "Ansprechpartner für Rückfragen im Haus"},
                            {"title": "b"},
                            {"title": "c"},
                            {"title": "d"},
                            {"title": "e"},
                            {"title": "f"},
                        ]
                    }
                ],
                "title": {"font": {"size": "12pt"}},
            }
        )
        with pytest.raises(DefinitionError) as excinfo:
            FormGenerator().check(config, area=AREA, q=Q)
        assert "Ansprechpartner" in str(excinfo.value)

    def test_a_placeholder_in_a_title_is_resolved(self) -> None:
        # § 8.10: placeholders hold wherever the definition supplies free text,
        # and form titles are named there by name.
        drawn = texts({"rows": [{"columns": [{"title": "{name}"}]}]}, page=NAMED)
        assert drawn[0].content == "Ada"

    def test_a_form_with_a_placeholder_is_not_page_invariant(self) -> None:
        # § 7.8 says so outright, and § 10.1 depends on the answer.
        blade = FormGenerator()
        plain = FormConfig.model_validate(THREE)
        named = FormConfig.model_validate({"rows": [{"columns": [{"title": "{name}"}]}]})
        assert blade.is_page_invariant(plain) is True
        assert blade.is_page_invariant(named) is False

    def test_position_none_leaves_the_titles_out(self) -> None:
        assert texts({**THREE, "title": {"position": "none"}}) == []


class TestTheSeam:
    def test_snapping_is_refused(self) -> None:
        assert FormGenerator().supports_snap is False

    def test_describe_counts_the_rows_and_fields(self) -> None:
        described = "\n".join(FormGenerator().describe(FormConfig.model_validate(THREE)))
        assert "1" in described and "3" in described


class TestOnTheSheet:
    DEFINITION = (
        "version: 1\n"
        "page:\n  format: a5\n  margin: 12mm\n"
        "header:\n  height: 10mm\n  gap: 4mm\n  center: 'Telefonprotokoll'\n"
        "generator: form\n"
        "gap: 2mm\n"
        "rows:\n"
        "  - height: 20%\n"
        "    columns:\n"
        "      - {title: 'Datum'}\n"
        "      - {title: 'Uhrzeit'}\n"
        "      - {title: 'Anrufer'}\n"
        "  - height: 25%\n"
        "    columns:\n"
        "      - {title: 'Firma'}\n"
        "      - {title: 'Betreff', width: 50%}\n"
        "      - {title: 'Dringend', kind: choice, options: ['Ja', 'Nein']}\n"
        "  - height: rest\n"
        "    columns:\n"
        "      - {title: 'Notiz', line_spacing: 8mm}\n"
    )

    def test_it_reaches_the_pdf(self, tmp_path: Path) -> None:
        import pdfread

        path = tmp_path / "form.pdf"
        build(loads(self.DEFINITION, source="test"), PdfWriter(path))
        text = pdfread.text_on(path)
        assert "Telefonprotokoll" in text and "Anrufer" in text and "Ja" in text

    def test_two_runs_produce_identical_bytes(self, tmp_path: Path) -> None:
        first, second = tmp_path / "a.pdf", tmp_path / "b.pdf"
        for path in (first, second):
            build(loads(self.DEFINITION, source="test"), PdfWriter(path))
        assert first.read_bytes() == second.read_bytes()


class TestADegenerateRuling:
    """`line_spacing: 0mm` draws every writing line on top of the last.

    § 7.8's whole point is that the ruling is absolute and the line *count*
    follows from it — which is a division, in two places (`_line_count` and
    `_ruling`). Both assert the spacing is not `None`; neither asks whether it
    is zero, so the user gets a `ZeroDivisionError` traceback. The guard belongs
    on the field, where the loader can still name the line (§ 12).
    """

    DEFINITION = (
        "version: 1\n"
        "page:\n  format: a5\n  margin: 10mm\n"
        "generator: form\n"
        "rows:\n"
        "  - height: rest\n"
        "    columns:\n"
        "      - { title: 'Notiz', line_spacing: 8mm }\n"
    )

    def test_a_line_spacing_of_zero_is_refused_and_does_not_divide_by_it(self) -> None:
        with pytest.raises(DefinitionError) as excinfo:
            loads(self.DEFINITION.replace("line_spacing: 8mm", "line_spacing: 0mm"), source="test")
        assert "0mm" in str(excinfo.value)

    def test_a_negative_line_spacing_is_refused(self) -> None:
        with pytest.raises(DefinitionError) as excinfo:
            loads(self.DEFINITION.replace("line_spacing: 8mm", "line_spacing: -2mm"), source="test")
        assert "-2mm" in str(excinfo.value)
