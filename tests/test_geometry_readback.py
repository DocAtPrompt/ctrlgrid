"""Every blade's geometry, read back out of a finished PDF (§ 13.2).

`test_dimensional.py` does this for `lines` and calls it the most important test
in the suite: build a PDF, parse it, and check the coordinates against the
numbers the definition asked for. This file extends that discipline to the other
blades, because a test written beside the code inherits the code's assumptions,
and reading the artefact back does not.

**The rule this file is written under.** Every expected number here is derived
from the *definition* — or from a property the specification states in words —
and never from the implementation. A hexagon's edges must be `size` long because
§ 7.7 says `size` is the edge length for every shape; ten cells across a block
must be ten equal cells because § 7.4 says so. Where a check could only compare
two quantities the code computed from the same input, it is not here: that
proves nothing, and `plot-a4` is the scar that says so.

Tolerances are one micrometre unless a number genuinely lands between two of
them (a hexagon's √3, a rotation's cosine), where the tolerance is stated with
its reason.
"""

from __future__ import annotations

import math
from collections import Counter
from pathlib import Path

import pdfread
import pytest

from ctrlgrid.loader import loads
from ctrlgrid.pages import build
from ctrlgrid.writers.pdf import PdfWriter

#: One micrometre. Positions are integer µm (§ 3.3), so anything that should be
#: exact is exact, and a tolerance of 1 covers only the µm→pt→µm round trip.
EXACT = 1.0


def sheet(tmp_path: Path, definition: str, name: str = "out.pdf") -> Path:
    path = tmp_path / name
    build(loads(definition, source="test"), PdfWriter(path))
    return path


def segments(path: Path, page: int = 0) -> list[list[tuple[float, float]]]:
    return [p for p in pdfread.subpaths_um(path, page) if len(p) == 2]


class TestDots:
    """§ 7.2: two crossed cycles, so the dots sit on an exact lattice."""

    DEFINITION = (
        "version: 1\n"
        "page: {format: a4, margin: 20mm}\n"
        "generator: dots\n"
        "grid:\n"
        "  x: {base_spacing: 5mm}\n"
        "  y: {base_spacing: 5mm}\n"
        "base_size: 0.4mm\n"
    )

    def test_every_dot_sits_on_the_declared_five_millimetre_lattice(
        self, tmp_path: Path
    ) -> None:
        # A dot is a zero-length stroke with a round cap (§ 10.1), so it reads
        # back as a segment whose two points coincide.
        dots = [p for p in segments(sheet(tmp_path, self.DEFINITION))
                if pdfread.length_um(p[0], p[1]) < EXACT]
        assert len(dots) > 500
        xs = sorted({round(p[0][0]) for p in dots})
        ys = sorted({round(p[0][1]) for p in dots})
        # The *declared* step is 5 mm. Every neighbouring gap must be that, and
        # the check is against 5000 µm, not against the mean of what was drawn.
        for axis in (xs, ys):
            gaps = {round(b - a) for a, b in zip(axis, axis[1:], strict=False)}
            assert gaps == {5_000}, gaps

    def test_the_lattice_fills_the_pattern_area_it_was_given(
        self, tmp_path: Path
    ) -> None:
        # A4 minus 20 mm margins is 170 x 257 mm; a 5 mm lattice from the origin
        # therefore has floor(170/5)+1 = 35 columns and floor(257/5)+1 = 52 rows.
        # Both numbers come from § 8.1's arithmetic, not from the blade.
        dots = [p for p in segments(sheet(tmp_path, self.DEFINITION))
                if pdfread.length_um(p[0], p[1]) < EXACT]
        assert len({round(p[0][0]) for p in dots}) == 35
        assert len({round(p[0][1]) for p in dots}) == 52


class TestGrid:
    """§ 7.4: count-driven, one centred block, square cells."""

    DEFINITION = (
        "version: 1\n"
        "page: {format: a4, margin: 15mm}\n"
        "generator: grid\n"
        "cells: {x: 10, y: 10}\n"
    )

    def test_ten_by_ten_cells_are_eleven_by_eleven_lines_all_equal(
        self, tmp_path: Path
    ) -> None:
        drawn = segments(sheet(tmp_path, self.DEFINITION))
        verticals = sorted({round(p[0][0]) for p in drawn if abs(p[0][0] - p[1][0]) < EXACT})
        horizontals = sorted({round(p[0][1]) for p in drawn if abs(p[0][1] - p[1][1]) < EXACT})
        assert len(verticals) == 11 and len(horizontals) == 11
        for axis in (verticals, horizontals):
            gaps = {round(b - a) for a, b in zip(axis, axis[1:], strict=False)}
            assert len(gaps) == 1, gaps

    def test_the_cells_are_square(self, tmp_path: Path) -> None:
        # § 7.4 says the cells are square, and A4 minus 15 mm margins is not.
        # So this is a real constraint on the block, not an accident of the page.
        drawn = segments(sheet(tmp_path, self.DEFINITION))
        verticals = sorted({round(p[0][0]) for p in drawn if abs(p[0][0] - p[1][0]) < EXACT})
        horizontals = sorted({round(p[0][1]) for p in drawn if abs(p[0][1] - p[1][1]) < EXACT})
        assert abs((verticals[1] - verticals[0]) - (horizontals[1] - horizontals[0])) <= EXACT


class TestPolar:
    """§ 7.6: the cycle model in polar coordinates — base times multiples."""

    DEFINITION = (
        "version: 1\n"
        "page: {format: a4, margin: 10mm}\n"
        "generator: polar\n"
        "rings:\n"
        "  base_radius: 12mm\n"
        "  radius: [1, 1, 2]\n"
        "spokes:\n"
        "  base_angle: 30deg\n"
    )

    def test_the_ring_radii_are_the_declared_cumulative_multiples(
        self, tmp_path: Path
    ) -> None:
        # base 12 mm with the cycle [1, 1, 2] steps 12, 24, 48, 60, 72, 96 …
        # That series is arithmetic anyone can do on the definition; it is not
        # asked of the code.
        circles = [p for p in pdfread.subpaths_um(sheet(tmp_path, self.DEFINITION))
                   if len(p) == 5]
        radii = sorted(round(pdfread.circle_um(c)[2]) for c in circles)
        expected, step = [], 0
        for multiple in [1, 1, 2] * 4:
            step += 12_000 * multiple
            expected.append(step)
        assert radii == [r for r in expected if r <= max(radii)]

    def test_thirty_degree_spokes_close_the_circle(self, tmp_path: Path) -> None:
        # Twelve spokes at exactly 30°, and the twelfth must land back on 0° —
        # § 3.3's reason for micro-degrees. Measured from the drawn endpoints
        # relative to the ring centre, which the circles give independently.
        page = pdfread.subpaths_um(sheet(tmp_path, self.DEFINITION))
        circles = [p for p in page if len(p) == 5]
        cx, cy, _ = pdfread.circle_um(circles[0])
        spokes = [p for p in page if len(p) == 2]
        angles = sorted(
            round(math.degrees(math.atan2(p[1][1] - cy, p[1][0] - cx)) % 360, 3)
            for p in spokes
        )
        assert len(angles) == 12
        for index, angle in enumerate(angles):
            assert abs(angle - index * 30) < 0.05, (index, angle)


class TestTiling:
    """§ 7.7: `size` is the **edge length**, for every shape."""

    def definition(self, shape: str, size: str = "10mm") -> str:
        return (
            "version: 1\n"
            "page: {format: a4, margin: 15mm}\n"
            f"generator: tiling\nshape: {shape}\nsize: {size}\n"
        )

    @pytest.mark.parametrize("shape", ["hex", "tri", "square", "rhombus"])
    def test_every_drawn_edge_is_exactly_the_declared_size(
        self, tmp_path: Path, shape: str
    ) -> None:
        # The strongest independent check in this file: the definition says
        # 10 mm, and every single stroke on the sheet must be 10 mm long. No
        # arithmetic of the blade's is consulted.
        drawn = segments(sheet(tmp_path, self.definition(shape), f"{shape}.pdf"))
        assert len(drawn) > 100
        lengths = Counter(round(pdfread.length_um(p[0], p[1])) for p in drawn)
        for length, count in lengths.items():
            # 2 µm: an edge at 60° lands on an irrational multiple of the step,
            # so its two ends each round to the nearest micrometre.
            assert abs(length - 10_000) <= 2, (shape, length, count)

    def test_an_octagon_edge_is_the_declared_size_too(self, tmp_path: Path) -> None:
        # `octagon_square` derives its circumradius from the edge; the edge is
        # what the user wrote, so that is what must come out.
        drawn = segments(sheet(tmp_path, self.definition("octagon_square"), "oct.pdf"))
        lengths = [round(pdfread.length_um(p[0], p[1])) for p in drawn]
        assert lengths and all(abs(length - 10_000) <= 2 for length in lengths)

    def test_no_inner_edge_is_drawn_twice(self, tmp_path: Path) -> None:
        # § 7.7's load-bearing sentence. Two tiles share an edge; if it were
        # emitted per closed cell it would be stroked twice.
        drawn = segments(sheet(tmp_path, self.definition("hex"), "dup.pdf"))
        keys = [tuple(sorted((round(p[0][0]), round(p[0][1]), round(p[1][0]), round(p[1][1]))))
                for p in drawn]
        assert len(keys) == len(set(keys))


class TestStaves:
    """§ 7.3: `stave_space` is the gap between neighbouring lines, `system_gap`
    the gap between systems — measured lowest line to highest, not axis to axis."""

    DEFINITION = (
        "version: 1\n"
        "page: {format: a4, margin: 20mm}\n"
        "generator: staves\n"
        "count: 6\n"
        "stave_space: 2mm\n"
        "system_gap: 5sp\n"
        "lines: 5\n"
        "clef: none\n"
    )

    def test_five_lines_two_millimetres_apart_six_times(self, tmp_path: Path) -> None:
        drawn = segments(sheet(tmp_path, self.DEFINITION))
        ys = sorted({round(p[0][1]) for p in drawn if abs(p[0][1] - p[1][1]) < EXACT})
        assert len(ys) == 30  # 6 systems x 5 lines
        for system in range(6):
            block = ys[system * 5:(system + 1) * 5]
            gaps = {round(b - a) for a, b in zip(block, block[1:], strict=False)}
            assert gaps == {2_000}, (system, gaps)

    def test_the_system_gap_is_the_gap_and_not_the_pitch(self, tmp_path: Path) -> None:
        # `system_gap: 5sp` with `stave_space: 2mm` is 10 mm from the lowest line
        # of one system to the highest of the next. If it were read as an axis
        # distance the measured gap would come out 10 mm minus a stave height.
        drawn = segments(sheet(tmp_path, self.DEFINITION))
        ys = sorted({round(p[0][1]) for p in drawn if abs(p[0][1] - p[1][1]) < EXACT})
        between = {round(ys[system * 5 + 5] - ys[system * 5 + 4]) for system in range(5)}
        assert between == {10_000}, between


class TestFormRulingIsAbsolute:
    """§ 7.8's central claim: the grid is relative, the writing lines are not."""

    def definition(self, page_format: str) -> str:
        return (
            "version: 1\n"
            f"page: {{format: {page_format}, margin: 10mm}}\n"
            "generator: form\n"
            "rows:\n"
            "  - height: rest\n"
            "    columns:\n"
            "      - {title: 'Notiz', line_spacing: 8mm}\n"
        )

    def test_the_same_definition_rules_eight_millimetres_on_a4_and_on_a5(
        self, tmp_path: Path
    ) -> None:
        spacings = {}
        for page_format in ("a4", "a5"):
            drawn = segments(sheet(tmp_path, self.definition(page_format), f"{page_format}.pdf"))
            ys = sorted({round(p[0][1]) for p in drawn if abs(p[0][1] - p[1][1]) < EXACT})
            gaps = Counter(round(b - a) for a, b in zip(ys, ys[1:], strict=False))
            spacings[page_format] = gaps.most_common(1)[0][0]
        assert spacings["a4"] == 8_000 and spacings["a5"] == 8_000, spacings

    def test_and_the_field_itself_does_change_with_the_format(
        self, tmp_path: Path
    ) -> None:
        # The other half of the claim: if the field were the same size too, the
        # test above would be measuring nothing.
        widths = {}
        for page_format in ("a4", "a5"):
            drawn = segments(sheet(tmp_path, self.definition(page_format), f"w{page_format}.pdf"))
            xs = [p[0][0] for p in drawn] + [p[1][0] for p in drawn]
            widths[page_format] = round(max(xs) - min(xs))
        assert widths["a4"] > widths["a5"] + 50_000, widths


class TestPerspective:
    """§ 7.11: rays converge on a vanishing point, and that is checkable
    without the blade — concurrent lines meet where they meet."""

    DEFINITION = (
        "version: 1\n"
        "page: {format: a4, margin: 10mm}\n"
        "generator: perspective\n"
        "horizon: 0.5\n"
        "vanishing_points:\n"
        "  - {at: [-0.6, 0.5], count: 9}\n"
        "  - {at: [1.6, 0.5], count: 9}\n"
    )

    def test_every_ray_of_a_fan_passes_through_one_point(self, tmp_path: Path) -> None:
        drawn = segments(sheet(tmp_path, self.DEFINITION))
        # The horizon is the one horizontal line; the rest are rays.
        rays = [p for p in drawn if abs(p[0][1] - p[1][1]) > EXACT]
        assert len(rays) > 10
        # Each ray, extended, must cross the horizon at one of the two vanishing
        # points. Solve for x at the horizon's y and count distinct crossings.
        horizontals = [p for p in drawn if abs(p[0][1] - p[1][1]) < EXACT]
        horizon_y = horizontals[0][0][1]
        crossings = []
        for (x1, y1), (x2, y2) in rays:
            if abs(y2 - y1) < EXACT:
                continue
            crossings.append((x1 + (x2 - x1) * (horizon_y - y1) / (y2 - y1)) / 1000)
        clusters: list[list[float]] = []
        for value in sorted(crossings):
            if clusters and abs(value - clusters[-1][-1]) < 1.0:
                clusters[-1].append(value)
            else:
                clusters.append([value])
        assert len(clusters) == 2, [round(c[0], 1) for c in clusters]
        for cluster in clusters:
            assert max(cluster) - min(cluster) < 1.0, cluster


class TestMandalaSymmetry:
    """§ 7.11: the motif is repeated about N sectors. Rotating the drawing by
    360/N must map it onto itself — a property of the *result*, which no part of
    the blade's arithmetic is consulted for."""

    DEFINITION = (
        "version: 1\n"
        "page: {format: a4, margin: 20mm}\n"
        "generator: mandala\n"
        "sectors: 12\n"
        "outer_radius: 60mm\n"
        "spokes: {}\n"
        "polygons: [{sides: 12, radius: 0.8}]\n"
    )

    def test_a_twelfth_of_a_turn_maps_the_drawing_onto_itself(
        self, tmp_path: Path
    ) -> None:
        page = pdfread.subpaths_um(sheet(tmp_path, self.DEFINITION))
        points = {(round(x), round(y)) for path in page for x, y in path}
        cx = (min(x for x, _ in points) + max(x for x, _ in points)) / 2
        cy = (min(y for _, y in points) + max(y for _, y in points)) / 2
        angle = 2 * math.pi / 12
        cos_a, sin_a = math.cos(angle), math.sin(angle)
        matched = 0
        for x, y in points:
            dx, dy = x - cx, y - cy
            rotated = (cx + dx * cos_a - dy * sin_a, cy + dx * sin_a + dy * cos_a)
            # 60 µm: a rotation is irrational, so a point lands between two
            # micrometres and its partner was itself rounded when drawn.
            if any(pdfread.length_um(rotated, other) < 60 for other in points):
                matched += 1
        assert matched / len(points) > 0.95, f"{matched}/{len(points)} points map onto a partner"


class TestNet:
    """§ 7.14: the flat size follows from the declared inner dimensions, and a
    fold is dashed where a cut is solid."""

    DEFINITION = (
        "version: 1\n"
        "page: {format: a4, margin: 10mm}\n"
        "generator: net\n"
        "style: tray\n"
        "length: 80mm\n"
        "width: 50mm\n"
        "height: 20mm\n"
        "thickness: 0mm\n"
        "glue_tab: 10mm\n"
    )

    def test_the_flat_size_is_the_arithmetic_of_the_declared_box(
        self, tmp_path: Path
    ) -> None:
        # A tray of 80 x 50 x 20 mm at zero thickness: the floor plus a wall of
        # 20 mm on each side. 80 + 2x20 = 120 mm long, 50 + 2x20 = 90 mm wide.
        # The glue tabs sit on the end walls and do not extend the outline
        # beyond them. All of that is § 7.14 read with a pencil.
        page = pdfread.subpaths_um(sheet(tmp_path, self.DEFINITION))
        xs = [x for path in page for x, _ in path]
        ys = [y for path in page for _, y in path]
        assert abs((max(xs) - min(xs)) - 120_000) <= EXACT, (max(xs) - min(xs)) / 1000
        assert abs((max(ys) - min(ys)) - 90_000) <= EXACT, (max(ys) - min(ys)) / 1000

    def test_creases_are_dashed_and_cuts_are_not(self, tmp_path: Path) -> None:
        # A tray has four walls, so four floor-to-wall creases; and § 7.14 puts
        # a glue tab at each end of the two end walls, so four more where a tab
        # meets its wall. Eight, counted off the panel list § 7.14 describes —
        # my first guess of four forgot the tabs, which is the sort of thing
        # this file exists to make explicit rather than to assume.
        path = sheet(tmp_path, self.DEFINITION, "dash.pdf")
        assert len(pdfread.dash_arrays(path)) == 8


class TestMaze:
    """§ 7.5: a rectangular grid maze, so every wall lies on the cell lattice."""

    DEFINITION = (
        "version: 1\n"
        "page: {format: a4, margin: 20mm}\n"
        "generator: maze\n"
        "cells: {x: 10, y: 14}\n"
        "seed: 4711\n"
    )

    def test_every_wall_is_one_cell_long_and_on_the_lattice(
        self, tmp_path: Path
    ) -> None:
        drawn = segments(sheet(tmp_path, self.DEFINITION))
        lengths = {round(pdfread.length_um(p[0], p[1])) for p in drawn}
        assert len(lengths) == 1, lengths
        cell = lengths.pop()
        origin_x = min(min(p[0][0], p[1][0]) for p in drawn)
        origin_y = min(min(p[0][1], p[1][1]) for p in drawn)
        for a, b in drawn:
            for x, y in (a, b):
                assert round(x - origin_x) % cell <= EXACT, (x - origin_x) / 1000
                assert round(y - origin_y) % cell <= EXACT, (y - origin_y) / 1000

    def test_the_grid_is_ten_by_fourteen_cells(self, tmp_path: Path) -> None:
        drawn = segments(sheet(tmp_path, self.DEFINITION))
        cell = round(pdfread.length_um(drawn[0][0], drawn[0][1]))
        xs = [min(p[0][0], p[1][0]) for p in drawn] + [max(p[0][0], p[1][0]) for p in drawn]
        ys = [min(p[0][1], p[1][1]) for p in drawn] + [max(p[0][1], p[1][1]) for p in drawn]
        assert round((max(xs) - min(xs)) / cell) == 10
        assert round((max(ys) - min(ys)) / cell) == 14


class TestLabelsNoneIsSpelledAsSpecified:
    """§ 7.10 ends with one sentence: "**`labels: none`** unterdrückt die
    Beschriftung ganz."

    `tiling` takes it, because its `labels` is a word. `grid` and `polar` refused
    it — their `labels` is a block, so the spelling the specification documents
    produced `Input should be a valid dictionary or instance of GridLabels`: an
    internal class name, in answer to a definition written straight out of § 7.10.
    Leaving the key out did work, so nothing was ever *unlabellable*; the
    documented way of saying it was simply not there.

    Found by writing these geometry definitions from the specification rather
    than from the presets — which is the whole reason to write them that way.
    """

    def blade(self, generator: str, body: str) -> str:
        return (
            "version: 1\n"
            "page: {format: a4, margin: 15mm}\n"
            f"generator: {generator}\n{body}"
            "labels: none\n"
        )

    def test_grid_takes_it(self, tmp_path: Path) -> None:
        path = sheet(tmp_path, self.blade("grid", "cells: {x: 4, y: 4}\n"), "g.pdf")
        assert pdfread.text_on(path).strip() == ""

    def test_polar_takes_it(self, tmp_path: Path) -> None:
        path = sheet(
            tmp_path,
            self.blade("polar", "rings: {base_radius: 20mm}\nspokes: {base_angle: 45deg}\n"),
            "p.pdf",
        )
        assert pdfread.text_on(path).strip() == ""

    def test_tiling_still_takes_it(self, tmp_path: Path) -> None:
        path = sheet(tmp_path, self.blade("tiling", "shape: hex\nsize: 10mm\n"), "t.pdf")
        assert pdfread.text_on(path).strip() == ""


class TestLogarithmicAxis:
    """§ 7.9: "Die Positionen berechnet das Werkzeug; niemand tippt 0.4771."

    Which makes it the one family whose positions a test cannot take from the
    definition — it has to compute log10 itself. That is not circular: the
    logarithm is mathematics, not this codebase's arithmetic, and `math.log10`
    is an independent second opinion on it.
    """

    DEFINITION = (
        "version: 1\n"
        "page: {format: a4, margin: 10mm}\n"
        "generator: lines\n"
        "families:\n"
        "  - direction: horizontal\n"
        "    law: log10\n"
        "    base_spacing: 40mm\n"
        "    decades: 3\n"
        "    base_weight: 0.2pt\n"
    )

    def test_the_lines_sit_where_the_logarithm_puts_them(self, tmp_path: Path) -> None:
        drawn = segments(sheet(tmp_path, self.DEFINITION))
        ys = sorted({round(p[0][1]) for p in drawn if abs(p[0][1] - p[1][1]) < EXACT})
        origin = ys[0]
        # Three decades of 40 mm: within each, 1…10 sits at log10(n) x 40 mm.
        expected = sorted(
            {round(decade * 40_000 + math.log10(n) * 40_000)
             for decade in range(3) for n in range(1, 11)}
        )
        assert len(ys) == len(expected), (len(ys), len(expected))
        for got, want in zip(ys, expected, strict=True):
            assert abs((got - origin) - want) <= EXACT, ((got - origin) / 1000, want / 1000)

    def test_the_block_is_exactly_decades_times_the_decade_length(
        self, tmp_path: Path
    ) -> None:
        # § 7.9: a log family has a fixed total length of decades x base_spacing
        # and does not repeat. 3 x 40 mm = 120 mm, on a 277 mm tall area.
        drawn = segments(sheet(tmp_path, self.DEFINITION))
        ys = sorted({round(p[0][1]) for p in drawn if abs(p[0][1] - p[1][1]) < EXACT})
        assert abs((ys[-1] - ys[0]) - 120_000) <= EXACT, (ys[-1] - ys[0]) / 1000
