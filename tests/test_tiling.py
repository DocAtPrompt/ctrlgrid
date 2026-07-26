"""The `tiling` blade (§ 7.7) — hexagons, triangles, rhombi, octagons.

The load-bearing sentence of the section is about *drawing*, not about shape:
**shared edges may only be drawn once**. A tiling emitted as closed polygons
paints every inner edge twice, which shows at low opacity and doubles the file
size — so the blade yields `Segment` marks for the edge net and `Polygon` marks
only for fills.

Cells are never cut: a tile that does not fit whole is left out and the block
of whole tiles is centred, because nothing here may be scaled or clipped
(§ 8.2, and the vocabulary of § 6 has no clip).
"""

from __future__ import annotations

import math
from pathlib import Path

import pytest
from pydantic import ValidationError

from ctrlgrid.errors import DefinitionError
from ctrlgrid.generators.tiling import TilingConfig, TilingGenerator
from ctrlgrid.loader import loads
from ctrlgrid.marks import Area, Polygon, Segment, Text
from ctrlgrid.pages import PageContext, build
from ctrlgrid.writers.pdf import PdfWriter

AREA = Area(width=100_000, height=80_000)
PAGE = PageContext(index=0, number=1, count=1, name=None, is_even=False, seed_material=b"")
Q = PdfWriter("unused.pdf")

SHAPES = ["hex", "tri", "square", "rhombus", "octagon_square"]


def marks(definition: dict, area: Area = AREA) -> list:
    config = TilingConfig.model_validate(definition)
    return list(TilingGenerator().generate(config, area=area, page=PAGE, q=Q))


def segments(definition: dict, area: Area = AREA) -> list[Segment]:
    return [mark for mark in marks(definition, area) if isinstance(mark, Segment)]


def length(segment: Segment) -> float:
    return math.dist(
        (segment.start.x, segment.start.y), (segment.end.x, segment.end.y)
    )


class TestEveryShape:
    @pytest.mark.parametrize("shape", SHAPES)
    def test_it_tiles_the_area(self, shape: str) -> None:
        assert segments({"shape": shape, "size": "10mm"})

    @pytest.mark.parametrize("shape", SHAPES)
    def test_every_edge_is_the_size_that_was_asked_for(self, shape: str) -> None:
        # § 8.2 applied to tiles: `size` is the edge length and nothing is
        # stretched to make the pattern come out even.
        drawn = segments({"shape": shape, "size": "10mm"})
        assert all(length(segment) == pytest.approx(10_000, abs=2) for segment in drawn)

    @pytest.mark.parametrize("shape", SHAPES)
    def test_no_edge_is_drawn_twice(self, shape: str) -> None:
        # The sentence the whole section turns on (§ 7.7).
        drawn = segments({"shape": shape, "size": "12mm"})
        edges = {
            tuple(sorted([(s.start.x, s.start.y), (s.end.x, s.end.y)])) for s in drawn
        }
        assert len(edges) == len(drawn)

    @pytest.mark.parametrize("shape", SHAPES)
    def test_nothing_is_drawn_outside_the_pattern_area(self, shape: str) -> None:
        # No clipping exists in the vocabulary (§ 6), so a tile that does not
        # fit whole is left out rather than cut.
        for segment in segments({"shape": shape, "size": "11mm"}):
            for point in (segment.start, segment.end):
                assert -2 <= point.x <= AREA.width + 2
                assert -2 <= point.y <= AREA.height + 2


class TestHexagons:
    def test_pointy_is_the_default(self) -> None:
        assert TilingConfig.model_validate({"shape": "hex", "size": "10mm"}).orientation == (
            "pointy"
        )

    def test_pointy_and_flat_differ(self) -> None:
        pointy = segments({"shape": "hex", "size": "10mm"})
        flat = segments({"shape": "hex", "size": "10mm", "orientation": "flat"})
        assert {(s.start.x, s.start.y) for s in pointy} != {
            (s.start.x, s.start.y) for s in flat
        }

    def test_a_pointy_hexagon_has_a_vertical_edge_and_a_flat_one_does_not(self) -> None:
        pointy = segments({"shape": "hex", "size": "10mm"})
        flat = segments({"shape": "hex", "size": "10mm", "orientation": "flat"})
        assert any(s.start.x == s.end.x for s in pointy)
        assert any(s.start.y == s.end.y for s in flat)

    def test_orientation_is_only_allowed_on_hexagons(self) -> None:
        # § 7.7 marks it "hex only", and § 5.1 refuses a key that cannot take
        # effect where it stands.
        with pytest.raises(ValidationError) as excinfo:
            TilingConfig.model_validate(
                {"shape": "square", "size": "10mm", "orientation": "flat"}
            )
        assert "hex" in str(excinfo.value)


class TestFills:
    def polygons(self, definition: dict) -> list[Polygon]:
        return [mark for mark in marks(definition) if isinstance(mark, Polygon)]

    def test_none_is_the_default(self) -> None:
        assert self.polygons({"shape": "hex", "size": "10mm"}) == []

    def test_a_cycle_colours_the_tiles(self) -> None:
        # The 2- and 3-colouring of hexagons is the colouring-in use case.
        filled = self.polygons(
            {
                "shape": "hex",
                "size": "10mm",
                "fill": "cycle",
                "fill_colors": ["#ffffff", "#eeeeee", "#dddddd"],
            }
        )
        assert filled
        assert {polygon.fill_color for polygon in filled} == {
            "#ffffff",
            "#eeeeee",
            "#dddddd",
        }

    def test_a_fill_is_a_closed_polygon(self) -> None:
        filled = self.polygons(
            {"shape": "hex", "size": "10mm", "fill": "cycle",
             "fill_colors": ["#ffffff", "#eeeeee"]}
        )
        assert all(polygon.closed for polygon in filled)
        assert len(filled[0].points) == 6

    def test_fills_come_before_the_edges(self) -> None:
        # § 3.6: the writer does not sort, so order is stacking.
        drawn = marks(
            {"shape": "hex", "size": "10mm", "fill": "cycle",
             "fill_colors": ["#ffffff", "#eeeeee"]}
        )
        assert isinstance(drawn[0], Polygon)
        assert isinstance(drawn[-1], Segment)

    def test_a_cycle_without_colours_is_an_error(self) -> None:
        with pytest.raises(ValidationError):
            TilingConfig.model_validate({"shape": "hex", "size": "10mm", "fill": "cycle"})


class TestLabels:
    def test_none_is_the_default(self) -> None:
        assert [mark for mark in marks({"shape": "hex", "size": "10mm"})
                if isinstance(mark, Text)] == []

    def test_coordinates_name_every_tile(self) -> None:
        drawn = [
            mark
            for mark in marks({"shape": "square", "size": "20mm", "labels": "coordinates"})
            if isinstance(mark, Text)
        ]
        assert "A1" in {text.content for text in drawn}

    def test_a_label_too_wide_for_its_tile_is_refused(self) -> None:
        config = TilingConfig.model_validate(
            {"shape": "square", "size": "4mm", "labels": "coordinates",
             "font": {"size": "12pt"}}
        )
        with pytest.raises(DefinitionError) as excinfo:
            TilingGenerator().check(config, area=AREA, q=Q)
        assert "tile" in str(excinfo.value)


class TestTheSeam:
    def test_snapping_is_refused(self) -> None:
        # § 8.3 lists `tiling` among the blades where snapping is an error.
        assert TilingGenerator().supports_snap is False

    def test_describe_names_the_shape_and_the_edge(self) -> None:
        described = "\n".join(
            TilingGenerator().describe(
                TilingConfig.model_validate({"shape": "hex", "size": "8mm"})
            )
        )
        assert "hex" in described and "8mm" in described

    def test_a_tile_larger_than_the_area_is_refused(self) -> None:
        config = TilingConfig.model_validate({"shape": "hex", "size": "200mm"})
        with pytest.raises(DefinitionError) as excinfo:
            TilingGenerator().check(config, area=AREA, q=Q)
        assert "200mm" in str(excinfo.value)


class TestOnTheSheet:
    DEFINITION = (
        "version: 1\n"
        "page:\n  format: a5\n  margin: 10mm\n"
        "generator: tiling\n"
        "shape: hex\n"
        "size: 8mm\n"
        "weight: 0.4pt\n"
        "color: '#334455'\n"
    )

    def test_it_reaches_the_pdf(self, tmp_path: Path) -> None:
        import pdfread

        path = tmp_path / "hex.pdf"
        build(loads(self.DEFINITION, source="test"), PdfWriter(path))
        assert pdfread.page_count(path) == 1
        assert len(pdfread.lines_um(path)) > 100

    def test_two_runs_produce_identical_bytes(self, tmp_path: Path) -> None:
        first, second = tmp_path / "a.pdf", tmp_path / "b.pdf"
        for path in (first, second):
            build(loads(self.DEFINITION, source="test"), PdfWriter(path))
        assert first.read_bytes() == second.read_bytes()


class TestADegenerateTile:
    """A tile with no edge is not a small tile — it is no tile (§ 12 point 6).

    `size` reaches `_cells` before `check` ever runs, so a zero divides and the
    user gets a `ZeroDivisionError` traceback instead of a message; a negative
    reaches `check` and is answered with advice written for a tile too *large*.
    One guard on the value closes both, and it belongs on the model so the
    loader can name the line (§ 12).
    """

    DEFINITION = (
        "version: 1\n"
        "page:\n  format: a5\n  margin: 10mm\n"
        "generator: tiling\n"
        "shape: hex\n"
        "size: 8mm\n"
    )

    def test_a_size_of_zero_is_refused_and_does_not_divide_by_it(self) -> None:
        with pytest.raises(DefinitionError) as excinfo:
            loads(self.DEFINITION.replace("size: 8mm", "size: 0mm"), source="test")
        assert "0mm" in str(excinfo.value)

    def test_a_negative_size_is_refused_as_such(self) -> None:
        # Not with "no tile fits, use a smaller size" — that advice is wrong.
        with pytest.raises(DefinitionError) as excinfo:
            loads(self.DEFINITION.replace("size: 8mm", "size: -5mm"), source="test")
        assert "-5mm" in str(excinfo.value)
