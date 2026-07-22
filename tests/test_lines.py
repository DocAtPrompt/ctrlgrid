"""The `lines` blade (§ 7.1) — the one generator M1 carries.

A blade produces marks in local coordinates and knows nothing about margins
(§ 3.3). Everything it needs is the pattern area, the page context and the
writer query API; everything it emits is on the pattern layer.
"""

from __future__ import annotations

import inspect

import pytest
from pydantic import ValidationError

from ctrlgrid.generators.lines import LinesConfig, LinesGenerator
from ctrlgrid.marks import Area, Layer, Segment
from ctrlgrid.pages import PageContext

AREA = Area(width=100000, height=50000)
PAGE = PageContext(index=0, number=1, count=1, name=None, is_even=False, seed_material=b"")


def marks(definition: dict) -> list[Segment]:
    generator = LinesGenerator()
    config = LinesConfig.model_validate(definition)
    return list(generator.generate(config, area=AREA, page=PAGE, q=None))


class TestHorizontalFamilies:
    def test_lines_are_stacked_along_y_from_the_origin(self) -> None:
        # The origin is bottom left (§ 3.5), so mark 0 sits on it.
        segments = marks(
            {
                "families": [
                    {"direction": "horizontal", "base_spacing": "10mm", "spacing": [1]},
                ]
            }
        )
        assert [s.start.y for s in segments] == [0, 10000, 20000, 30000, 40000, 50000]

    def test_a_horizontal_line_spans_the_whole_pattern_area(self) -> None:
        segments = marks(
            {"families": [{"direction": "horizontal", "base_spacing": "10mm", "spacing": [1]}]}
        )
        first = segments[0]
        assert (first.start.x, first.end.x) == (0, AREA.width)
        assert first.start.y == first.end.y

    def test_a_millimetre_grid_puts_a_line_every_thousand_micrometres(self) -> None:
        segments = marks(
            {"families": [{"direction": "horizontal", "base_spacing": "1mm", "spacing": [1]}]}
        )
        assert len(segments) == 51
        assert [s.start.y for s in segments[:4]] == [0, 1000, 2000, 3000]


class TestVerticalFamilies:
    def test_lines_are_stacked_along_x(self) -> None:
        segments = marks(
            {"families": [{"direction": "vertical", "base_spacing": "10mm", "spacing": [1]}]}
        )
        assert [s.start.x for s in segments] == [0, 10000, 20000, 30000, 40000, 50000, 60000,
                                                 70000, 80000, 90000, 100000]

    def test_a_vertical_line_spans_the_whole_height(self) -> None:
        segments = marks(
            {"families": [{"direction": "vertical", "base_spacing": "10mm", "spacing": [1]}]}
        )
        first = segments[0]
        assert (first.start.y, first.end.y) == (0, AREA.height)


class TestCyclesReachTheMarks:
    def test_every_fifth_line_is_heavier(self) -> None:
        # The most implemented feature of every comparable tool, as the
        # two-entry case of the general mechanism (§ 1.1, § 5.3).
        segments = marks(
            {
                "families": [
                    {
                        "direction": "horizontal",
                        "base_spacing": "1mm",
                        "spacing": [1],
                        "base_weight": "0.15pt",
                        "weight": [1, 1, 1, 1, 2.7],
                    }
                ]
            }
        )
        thin = 0.15 * 25.4 / 72
        assert [s.weight for s in segments[:6]] == pytest.approx(
            [thin, thin, thin, thin, thin * 2.7, thin]
        )

    def test_colours_cycle_independently_of_weights(self) -> None:
        segments = marks(
            {
                "families": [
                    {
                        "direction": "horizontal",
                        "base_spacing": "10mm",
                        "spacing": [1],
                        "color": ["#7799bb", "#4466aa"],
                    }
                ]
            }
        )
        assert [s.color for s in segments[:4]] == ["#7799bb", "#4466aa", "#7799bb", "#4466aa"]

    def test_a_single_colour_applies_to_every_line(self) -> None:
        segments = marks(
            {
                "families": [
                    {
                        "direction": "horizontal",
                        "base_spacing": "10mm",
                        "spacing": [1],
                        "color": "#123456",
                    }
                ]
            }
        )
        assert {s.color for s in segments} == {"#123456"}

    def test_an_offset_moves_the_start_of_the_cycle(self) -> None:
        segments = marks(
            {
                "families": [
                    {
                        "direction": "horizontal",
                        "base_spacing": "10mm",
                        "spacing": [1],
                        "offset": "5mm",
                    }
                ]
            }
        )
        assert [s.start.y for s in segments] == [5000, 15000, 25000, 35000, 45000]


class TestSeamTwo:
    def test_several_families_make_a_grid(self) -> None:
        segments = marks(
            {
                "families": [
                    {"direction": "horizontal", "base_spacing": "10mm", "spacing": [1]},
                    {"direction": "vertical", "base_spacing": "10mm", "spacing": [1]},
                ]
            }
        )
        assert len(segments) == 6 + 11

    def test_everything_a_blade_yields_is_on_the_pattern_layer(self) -> None:
        segments = marks(
            {"families": [{"direction": "horizontal", "base_spacing": "10mm", "spacing": [1]}]}
        )
        assert {s.layer for s in segments} == {Layer.PATTERN}

    def test_generate_streams_rather_than_collecting(self) -> None:
        # § 3.3: 200 pages of dot grid would otherwise hold hundreds of
        # thousands of objects in memory at once.
        config = LinesConfig.model_validate(
            {"families": [{"direction": "horizontal", "base_spacing": "10mm", "spacing": [1]}]}
        )
        assert inspect.isgenerator(LinesGenerator().generate(config, area=AREA, page=PAGE, q=None))

    def test_lines_are_the_same_on_every_page(self) -> None:
        config = LinesConfig.model_validate(
            {"families": [{"direction": "horizontal", "base_spacing": "10mm", "spacing": [1]}]}
        )
        assert LinesGenerator().is_page_invariant(config) is True


class TestValidation:
    def test_at_least_one_family_is_required(self) -> None:
        with pytest.raises(ValidationError):
            LinesConfig.model_validate({"families": []})

    def test_a_colour_must_be_six_hex_digits(self) -> None:
        for bad in ("#abc", "red", "#12345678", "7799bb"):
            with pytest.raises(ValidationError):
                LinesConfig.model_validate(
                    {
                        "families": [
                            {"direction": "horizontal", "base_spacing": "1mm", "color": bad}
                        ]
                    }
                )

    def test_a_stroke_wider_than_its_spacing_is_an_error(self) -> None:
        # § 12 point 6: the commonest user error is mm for pt. At 0.15 mm
        # against 0.15 mm spacing the grid closes into a solid area.
        with pytest.raises(ValidationError) as excinfo:
            LinesConfig.model_validate(
                {
                    "families": [
                        {
                            "direction": "horizontal",
                            "base_spacing": "0.2mm",
                            "base_weight": "0.3mm",
                        }
                    ]
                }
            )
        message = str(excinfo.value)
        assert "0.3mm" in message and "0.2mm" in message

    def test_a_slanted_direction_says_it_is_not_implemented_yet(self) -> None:
        with pytest.raises(ValidationError) as excinfo:
            LinesConfig.model_validate(
                {"families": [{"direction": "30deg", "base_spacing": "5mm"}]}
            )
        assert "horizontal" in str(excinfo.value)

    @pytest.mark.parametrize(
        "key,value",
        [
            ("law", "log10"),
            ("count", 1),
            ("extent", {"start": "0mm", "end": "100mm"}),
            ("governing", True),
        ],
    )
    def test_a_key_from_a_later_milestone_names_it(self, key: str, value: object) -> None:
        with pytest.raises(ValidationError) as excinfo:
            LinesConfig.model_validate(
                {"families": [{"direction": "horizontal", "base_spacing": "5mm", key: value}]}
            )
        message = str(excinfo.value)
        assert key in message and "M" in message

    def test_an_unknown_key_is_an_error(self) -> None:
        with pytest.raises(ValidationError) as excinfo:
            LinesConfig.model_validate(
                {"families": [{"direction": "horizontal", "base_spacng": "5mm"}]}
            )
        assert "base_spacng" in str(excinfo.value)
