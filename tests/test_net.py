"""`net` — parametric box nets (§ 7.14).

Measurements in, a law computes the net. Two conventions carry it, and both are
choices rather than derivations, so both are tested in both directions:

* dimensions are **inner** — the space inside the box;
* a panel that closes *over* a layer is widened by the material thickness, a
  flap that slides *inside* one is shortened by it. At `thickness: 0` every
  allowance vanishes and the net is the ideal one.
"""

from __future__ import annotations

import pytest

from ctrlgrid.generators.net_geometry import Panel, edges
from ctrlgrid.generators.net_styles import net_panels
from ctrlgrid.marks import Point

L, W, H = 80_000, 50_000, 30_000
TAB = 12_000
TUCK = 15_000


def spec(**kwargs):
    """The style arguments, defaulting to an ideal (thickness-free) box."""
    return {
        "length": L, "width": W, "height": H, "thickness": 0,
        "glue_tab": TAB, "tuck": TUCK, "dust": None, **kwargs,
    }


def bounds(panels: list[Panel]) -> tuple[int, int, int, int]:
    xs = [point.x for panel in panels for point in panel.points]
    ys = [point.y for panel in panels for point in panel.points]
    return min(xs), min(ys), max(xs), max(ys)


def named(panels: list[Panel], name: str) -> Panel:
    return next(panel for panel in panels if panel.name == name)


def size(panel: Panel) -> tuple[int, int]:
    xs = [point.x for point in panel.points]
    ys = [point.y for point in panel.points]
    return max(xs) - min(xs), max(ys) - min(ys)


class TestTheTray:
    def test_the_base_is_exactly_the_inner_size(self) -> None:
        panels = net_panels("tray", **spec())
        assert size(named(panels, "base")) == (L, W)

    def test_it_has_a_base_four_walls_and_four_tabs(self) -> None:
        names = [panel.name for panel in net_panels("tray", **spec())]
        assert names.count("base") == 1
        assert sum(1 for name in names if name.startswith("wall")) == 4
        assert sum(1 for name in names if name.startswith("tab")) == 4

    def test_the_flat_size_is_the_base_plus_a_wall_on_each_side(self) -> None:
        x0, y0, x1, y1 = bounds(net_panels("tray", **spec()))
        assert (x1 - x0, y1 - y0) == (L + 2 * max(H, TAB), W + 2 * H)

    def test_eight_creases_the_four_base_edges_and_the_four_tabs(self) -> None:
        _cuts, folds = edges(net_panels("tray", **spec()))
        assert len(folds) == 8

    def test_a_tab_is_shortened_by_the_material(self) -> None:
        # It wraps around the wall it glues to, and loses that much reach.
        ideal = size(named(net_panels("tray", **spec()), "tab-sw"))
        thick = size(named(net_panels("tray", **spec(thickness=300)), "tab-sw"))
        assert ideal[0] - thick[0] == 300


class TestTheTuckTop:
    def test_the_wall_strip_is_the_circumference_plus_the_glue_tab(self) -> None:
        x0, _y0, x1, _y1 = bounds(net_panels("tuck_top", **spec()))
        assert x1 - x0 == 2 * (L + W) + TAB

    def test_the_lid_covers_the_opening_and_the_tongue_is_the_tuck(self) -> None:
        panels = net_panels("tuck_top", **spec())
        assert size(named(panels, "lid-top"))[1] == W
        assert size(named(panels, "tongue-top"))[1] == TUCK

    def test_it_closes_at_both_ends(self) -> None:
        names = [panel.name for panel in net_panels("tuck_top", **spec())]
        assert {"lid-top", "tongue-top", "lid-bottom", "tongue-bottom"} <= set(names)
        assert sum(1 for name in names if name.startswith("dust")) == 4

    def test_every_panel_of_the_strip_is_creased_to_its_neighbour(self) -> None:
        _cuts, folds = edges(net_panels("tuck_top", **spec()))
        # four wall-to-wall creases + glue tab + 2 lids + 2 tongues + 4 dust flaps
        assert len(folds) == 12


class TestTheThicknessRule:
    """Both directions of the one rule, and the ideal net at zero."""

    def test_at_zero_the_net_is_the_ideal_one(self) -> None:
        for style in ("tray", "tuck_top"):
            ideal = net_panels(style, **spec(thickness=0))
            assert all(
                all(isinstance(point, Point) for point in panel.points) for panel in ideal
            )
        panels = net_panels("tuck_top", **spec(thickness=0))
        assert size(named(panels, "wall-1"))[0] == W   # no wrap allowance anywhere

    def test_a_panel_that_closes_over_a_layer_is_widened(self) -> None:
        thick = net_panels("tuck_top", **spec(thickness=300))
        assert size(named(thick, "lid-top"))[1] == W + 300
        assert size(named(thick, "wall-1"))[0] == W + 300

    def test_a_flap_that_slides_inside_is_shortened(self) -> None:
        thick = net_panels("tuck_top", **spec(thickness=300))
        assert size(named(thick, "tongue-top"))[1] == TUCK - 300

    def test_the_strip_grows_by_one_thickness_per_wrapped_panel(self) -> None:
        # The three panels after the first each wrap one more layer. Measured on
        # the walls themselves: the whole net's width also carries the glue tab,
        # which *shrinks* by a thickness, and the two would cancel out to a
        # number that says nothing.
        def strip(thickness: int) -> int:
            panels = net_panels("tuck_top", **spec(thickness=thickness))
            return sum(size(named(panels, f"wall-{i}"))[0] for i in range(4))

        assert strip(300) - strip(0) == 3 * 300

    def test_dust_flaps_default_to_a_third_of_the_length_capped(self) -> None:
        panels = net_panels("tuck_top", **spec())
        assert size(named(panels, "dust-top-1"))[1] == min(L // 3, 25_000)


def test_an_unknown_style_is_a_programming_error_here() -> None:
    # The user's message comes from the config (§ 7.14); by this depth the
    # style has been validated.
    with pytest.raises(KeyError):
        net_panels("origami_crane", **spec())


class TestTheBlade:
    """The config's refusals, and the marks (§ 7.14)."""

    DEF = (
        "version: 1\npage: {format: a4, margin: 10mm}\n"
        "generator: net\nstyle: tray\n"
        "length: 80mm\nwidth: 50mm\nheight: 30mm\n"
    )

    def load(self, text: str = DEF):
        from ctrlgrid.loader import loads

        return loads(text, None, source="test")

    def test_it_loads_and_describes_its_flat_size(self) -> None:
        from ctrlgrid import generators

        document = self.load()
        described = generators.get("net").describe(document.config)
        assert "tray" in described[0]
        assert "flat 140.0 x 110.0 mm" in described[1]

    def test_a_dimension_of_zero_is_refused(self) -> None:
        from ctrlgrid.errors import DefinitionError

        with pytest.raises(DefinitionError):
            self.load(self.DEF.replace("height: 30mm", "height: 0mm"))

    def test_a_thickness_that_eats_the_box_is_refused(self) -> None:
        from ctrlgrid.errors import DefinitionError

        with pytest.raises(DefinitionError) as excinfo:
            self.load(self.DEF + "thickness: 20mm\n")
        assert "half the smallest dimension" in str(excinfo.value)

    def test_a_key_that_does_nothing_for_this_style_is_refused(self) -> None:
        from ctrlgrid.errors import DefinitionError

        with pytest.raises(DefinitionError) as excinfo:
            self.load(self.DEF + "tuck: 15mm\n")
        message = str(excinfo.value)
        assert "tuck" in message and "tuck_top" in message

    def test_an_unknown_style_names_the_ones_there_are(self) -> None:
        from ctrlgrid.errors import DefinitionError

        with pytest.raises(DefinitionError) as excinfo:
            self.load(self.DEF.replace("style: tray", "style: origami_crane"))
        message = str(excinfo.value)
        assert "tray" in message and "tuck_top" in message

    def test_a_net_too_large_for_the_sheet_is_refused_with_both_sizes(self) -> None:
        from ctrlgrid.errors import DefinitionError
        from ctrlgrid.pages import build
        from ctrlgrid.writers.pdf import PdfWriter

        document = self.load(self.DEF.replace("length: 80mm", "length: 300mm"))
        with pytest.raises(DefinitionError) as excinfo:
            build(document, PdfWriter("unused.pdf"))
        message = str(excinfo.value)
        assert "never scaled" in message and "mm" in message

    def test_the_marks_are_cut_and_fold_lines_and_stay_in_the_area(self) -> None:
        from ctrlgrid import generators
        from ctrlgrid.marks import Segment
        from ctrlgrid.pages import Geometry, page_contexts
        from ctrlgrid.writers.pdf import PdfWriter

        document = self.load()
        geometry = Geometry.of(document.sheet, header=None, footer=None)
        page = next(page_contexts(count=1, snap=()))
        marks = list(
            generators.get("net").generate(
                document.config, area=geometry.area, page=page, q=PdfWriter("unused.pdf")
            )
        )
        assert marks and all(isinstance(mark, Segment) for mark in marks)
        assert all(mark.dash for mark in marks[:8])        # the creases, dashed
        assert not any(mark.dash for mark in marks[8:])    # the cuts, solid
        for mark in marks:
            for point in (mark.start, mark.end):
                assert 0 <= point.x <= geometry.area.width
                assert 0 <= point.y <= geometry.area.height
