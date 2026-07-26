"""Every generator's geometry, read back out of a finished PDF (§ 13.2).

`test_dimensional.py` does this for `lines` and calls it the most important test
in the suite: build a PDF, parse it, and check the coordinates against the
numbers the definition asked for. This file extends that discipline to the other
blades **and to the two document generators**, because a test written beside the
code inherits the code's assumptions, and reading the artefact back does not.

The documents were added last and for a stated reason: the suite exercises the
blade path, the document path is younger, and four of the five serious findings
of the release-readiness pass were on it. Until then, every number on a calendar
page came from the code that drew it.

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

import calendar
import math
from collections import Counter
from datetime import date, timedelta
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


# --------------------------------------------------------------------------
# The document generators (§ 7.12, § 7.13)
#
# A blade fills one pattern area, so page 0 shows everything it has. A document
# *owns* its pages, and what there is to read back is therefore different in
# kind: the page plan, the tables, the columns two views are required to share.
# The rule above does not change — every number below comes from the definition,
# from the calendar arithmetic of the year it names, or from a sentence of the
# specification. Where a claim could only be checked against a quantity the code
# also computed (the day page's block heights against "55 % of what"), it is
# left out and said so.
# --------------------------------------------------------------------------

#: § 7.12 fixes the page order: contents, full-year overview, half-year 1 and 2,
#: then the months. So January is the fifth page of a calendar with no title
#: page — an index derived from that sentence, and every test that uses it
#: asserts the page's own title as well, so a changed order fails here loudly.
CONTENTS_PAGE = 0
FULL_YEAR_PAGE = 1
HALF_YEAR_1_PAGE = 2
FIRST_MONTH_PAGE = 4

CALENDAR_YEAR = 2026
MONTH_NAMES = (
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
)
WEEKDAY_NAMES = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")

CALENDAR = (
    "version: 1\n"
    "page: {format: a4, margin: 12mm}\n"
    "generator: calendar\n"
    f"year: {CALENDAR_YEAR}\n"
    "week_start: monday\n"
    "font: {family: sans}\n"
)


def digits(placed: list[pdfread.PlacedText], length: int) -> list[pdfread.PlacedText]:
    return [t for t in placed if t.content.isdigit() and len(t.content) == length]


@pytest.fixture(scope="module")
def cal(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """The calendar above, built once — 381 pages is a second, and six tests
    read the same artefact. Nothing writes to it."""
    return sheet(tmp_path_factory.mktemp("cal"), CALENDAR, "calendar.pdf")


@pytest.fixture(scope="module")
def cal_with_weeks(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return sheet(tmp_path_factory.mktemp("weeks"), CALENDAR + "week_view: {}\n", "w.pdf")


class TestCalendarDocument:
    """§ 7.12: the pages a year makes, and the tables on them."""

    def test_one_page_per_view_and_the_count_follows_from_the_year(
        self, cal: Path
    ) -> None:
        # § 7.12: one page per view, never scrolled, never scaled. So the count
        # is arithmetic on the definition's `year` and nothing else: a contents
        # page, the full-year overview, two half-year tables, twelve months and
        # one page for every day the year has. 2026 is not a leap year.
        days = 366 if calendar.isleap(CALENDAR_YEAR) else 365
        assert pdfread.page_count(cal) == 1 + 1 + 2 + 12 + days

    def test_a_week_view_adds_the_weeks_that_touch_the_year(
        self, cal_with_weeks: Path
    ) -> None:
        # § 7.12: weeks are opt-in and aligned to `week_start`, not to ISO. The
        # number of them is therefore the count of Monday-started weeks that
        # touch 2026 — computed here with `datetime`, which knows nothing about
        # this codebase.
        first = date(CALENDAR_YEAR, 1, 1)
        monday = first - timedelta(days=first.weekday())
        weeks = (date(CALENDAR_YEAR, 12, 31) - monday).days // 7 + 1
        days = 366 if calendar.isleap(CALENDAR_YEAR) else 365
        assert pdfread.page_count(cal_with_weeks) == 1 + 1 + 2 + 12 + weeks + days

    def test_the_title_holds_the_left_edge_and_the_navigation_the_right(
        self, cal: Path
    ) -> None:
        # § 7.12: "Die Navigationsleiste sitzt am *rechten* Rand: links gehört
        # dem Seitentitel" — the two would otherwise fight over one corner.
        # Left edge and right edge are § 8.1's: 12 mm in from each side of A4.
        placed = pdfread.texts_um(cal, FIRST_MONTH_PAGE)
        title = next(t for t in placed if t.content == f"January {CALENDAR_YEAR}")
        assert abs(title.x - 12_000) <= EXACT, title.x / 1000
        nav = [t for t in placed if t.content in ("Index", "Year", "Month")]
        assert len(nav) == 3
        assert all(t.x > title.x for t in nav)
        # The strip ends flush with the pattern area's right edge, 210 - 12 mm.
        # Its underlines are the topmost thing drawn on the page.
        drawn = segments(cal, FIRST_MONTH_PAGE)
        top = max(round(p[0][1]) for p in drawn)
        edge = max(max(p[0][0], p[1][0]) for p in drawn if round(p[0][1]) == top)
        assert abs(edge - 198_000) <= EXACT, edge / 1000

    def test_the_full_year_is_twelve_mini_months_three_across(self, cal: Path) -> None:
        # § 7.12: "zwölf Mini-Monate, drei nebeneinander". Twelve names in three
        # columns is four rows, and both numbers are the sentence, not the code.
        placed = pdfread.texts_um(cal, FULL_YEAR_PAGE)
        names = [t for t in placed if t.content in MONTH_NAMES]
        assert len(names) == 12
        assert len({round(t.x) for t in names}) == 3
        assert len({round(t.y) for t in names}) == 4

    def test_a_mini_month_holds_its_days_right_of_the_name_and_its_weeks_left(
        self, cal: Path
    ) -> None:
        # § 7.12: the month name begins at the edge of the first day column and
        # not at the cell's, "sonst steht er über den Wochennummern, und eine
        # Zahl unter einem Monatsnamen wird als Tag gelesen". Both sides of that
        # are countable: January 2026 has 31 days, and it is spanned by five
        # Monday-weeks — so five numbers stand left of the name and thirty-one
        # at or right of it. Neither count is asked of the code.
        block = self.mini_month(cal, 0)
        name = next(t for t in block if t.content in MONTH_NAMES)
        numbers = [t for t in block if t.content.isdigit()]
        assert len([t for t in numbers if t.x < name.x]) == self.weeks_spanning(1)
        assert len([t for t in numbers if t.x >= name.x]) == calendar.monthrange(
            CALENDAR_YEAR, 1
        )[1]

    def test_the_week_number_column_stands_further_off_than_a_day_column(
        self, cal: Path
    ) -> None:
        # § 7.12: "der Abstand neben der Wochennummer bleibt deutlich größer als
        # der zwischen zwei Tagen". Measured left edge to left edge, and both
        # numbers come off the same page, so the comparison is between two
        # drawn distances rather than against a constant.
        block = self.mini_month(cal, 0)
        name = next(t for t in block if t.content in MONTH_NAMES)
        columns = sorted({round(t.x) for t in digits(block, 2) if t.x >= name.x})
        assert len(columns) == 7, columns
        pitch = {b - a for a, b in zip(columns, columns[1:], strict=False)}
        assert len(pitch) == 1, pitch
        week_numbers = sorted({round(t.x) for t in block if t.x < name.x})
        # The week numbers here are single digits and right-aligned like the
        # days, so their left edge overstates how close they sit — which makes
        # this assertion the conservative one.
        assert columns[0] - week_numbers[-1] > pitch.pop()

    def test_a_short_month_column_ends_and_leaves_no_empty_cells(
        self, cal: Path
    ) -> None:
        # § 7.12: "kurzer Monate Spalten enden — keine leeren Zellen". A cell is
        # a rectangle; a shaded weekend draws a second one at the same row, so
        # the rows are the distinct positions, and their number must be the
        # length of the month as the calendar has it.
        cells = [q for q in pdfread.subpaths_um(cal, HALF_YEAR_1_PAGE) if len(q) == 4]
        rows: dict[int, set[int]] = {}
        for quad in cells:
            left = round(min(x for x, _ in quad))
            rows.setdefault(left, set()).add(round(min(y for _, y in quad)))
        counted = [len(rows[left]) for left in sorted(rows)]
        assert counted == [calendar.monthrange(CALENDAR_YEAR, m)[1] for m in range(1, 7)]

    def test_and_a_leap_february_is_one_row_longer(self, tmp_path: Path) -> None:
        # The test above would also pass against a table of constants, so here
        # is the year moved and the drawing asked again: 2028 is a leap year,
        # and its February column has to grow by exactly the day the year gained.
        leap = sheet(tmp_path, CALENDAR.replace("year: 2026", "year: 2028"), "l.pdf")
        cells = [q for q in pdfread.subpaths_um(leap, HALF_YEAR_1_PAGE) if len(q) == 4]
        rows: dict[int, set[int]] = {}
        for quad in cells:
            left = round(min(x for x, _ in quad))
            rows.setdefault(left, set()).add(round(min(y for _, y in quad)))
        february = sorted(rows)[1]
        assert calendar.isleap(2028) and len(rows[february]) == 29

    def test_the_month_and_the_week_view_lay_out_the_same_columns(
        self, cal_with_weeks: Path
    ) -> None:
        # § 7.12: "beide Ansichten rechnen dieselben Spalten über `date_columns`".
        # A week page and a month page are built by different code paths on
        # different pages, so agreeing to the micrometre is a real constraint.
        first_week = FIRST_MONTH_PAGE + 12
        assert "Week 1" in pdfread.text_on(cal_with_weeks, first_week)
        month = self.columns(cal_with_weeks, FIRST_MONTH_PAGE)
        # Two empty tuples would also be equal, and an equality that can pass on
        # nothing is the probe that proves nothing. So the shape is asserted
        # first, and it is § 7.12's sentence: one weekday column holding the
        # left edge, and day numbers right-aligned into one column, which shows
        # as the two starting points a one- and a two-digit day have.
        assert (len(month[0]), len(month[1])) == (1, 2), month
        assert month == self.columns(cal_with_weeks, first_week)

    def test_the_weekday_holds_the_left_edge_and_the_day_numbers_are_right_aligned(
        self, cal: Path, tmp_path: Path
    ) -> None:
        # § 7.12: "der Wochentag hält die linke Kante, die Tageszahlen stehen
        # **rechtsbündig** in einer eigenen Spalte darunter". Right-aligned means
        # a two-digit day starts exactly one digit earlier than a one-digit one.
        # The width of that digit is font data, not this codebase's arithmetic
        # (§ 10.3), so it is asked of a metrics oracle — the same stand-in the
        # pre-flight measures with (decision 38) — at the size read off the page.
        placed = pdfread.texts_um(cal, FIRST_MONTH_PAGE)
        weekdays = [t for t in placed if t.content in WEEKDAY_NAMES]
        assert len({round(t.x) for t in weekdays}) == 1
        one, two = digits(placed, 1), digits(placed, 2)
        assert len({round(t.x) for t in one}) == 1
        assert len({round(t.x) for t in two}) == 1
        oracle = PdfWriter(tmp_path / "never-written.pdf")
        digit = oracle.text_width(
            "1", family="sans", size=round(one[0].size_pt * 25400 / 72)
        )
        # Two micrometres, and the reason is that two independently rounded
        # numbers meet here: the drawn position was rounded to µm when it was
        # written, and the oracle's width is rounded again on the way out.
        assert abs((one[0].x - two[0].x) - digit) <= 2 * EXACT

    # ------------------------------------------------------------- helpers

    def weeks_spanning(self, month: int) -> int:
        """How many `week_start`-aligned weeks a month touches — from `datetime`."""
        first = date(CALENDAR_YEAR, month, 1)
        last = date(CALENDAR_YEAR, month, calendar.monthrange(CALENDAR_YEAR, month)[1])
        monday = first - timedelta(days=first.weekday())
        return (last - monday).days // 7 + 1

    def mini_month(self, cal: Path, index: int) -> list[pdfread.PlacedText]:
        """Every text inside one cell of the full-year overview's 3 x 4 grid.

        The cell reaches *left* of the month name — that is the whole point of
        the two tests that use this, since the week numbers live there. So the
        cell cannot be bounded by the name, and it is found instead as a cluster:
        within one row, the air between two mini-months is the widest gap there
        is, wider even than the deliberate one that keeps the week numbers off
        the day grid. Two cuts at the two widest gaps give the three cells.
        """
        placed = pdfread.texts_um(cal, FULL_YEAR_PAGE)
        names = [t for t in placed if t.content in MONTH_NAMES]
        ys = sorted({round(t.y) for t in names}, reverse=True)
        column, row = index % 3, index // 3
        bottom = ys[row + 1] if row + 1 < len(ys) else -float("inf")
        band = [t for t in placed if bottom < t.y <= ys[row] + EXACT]
        xs = sorted({round(t.x) for t in band})
        widest = sorted((b - a, a) for a, b in zip(xs, xs[1:], strict=False))[-2:]
        edges = sorted(last for _, last in widest)
        lower = -float("inf") if column == 0 else edges[column - 1]
        upper = float("inf") if column == 2 else edges[column]
        return [t for t in band if lower < t.x <= upper + EXACT]

    def columns(self, path: Path, page: int) -> tuple[list[int], list[int]]:
        placed = pdfread.texts_um(path, page)
        return (
            sorted({round(t.x) for t in placed if t.content in WEEKDAY_NAMES}),
            sorted({round(t.x) for t in placed if t.content.isdigit()}),
        )


#: § 8.1's arithmetic on the notebook definition below: A4 is 297 mm tall, the
#: margin takes 15 off each end, and each band takes its 8 mm height plus its
#: 3 mm gap. So the pattern area runs from 26 mm to 271 mm — which is also how a
#: test tells a band's text from a page's own.
NOTEBOOK_PATTERN_TOP = 271_000
NOTEBOOK_PATTERN_BOTTOM = 26_000

NOTEBOOK = (
    "version: 1\n"
    "page: {format: a4, margin: 15mm}\n"
    'header: {height: 8mm, gap: 3mm, left: "{section}"}\n'
    'footer: {height: 8mm, gap: 3mm, right: "{page} / {page_count}"}\n'
    "generator: notebook\n"
    'title_page: {title: "Notebook"}\n'
    "sections:\n"
    '  - {label: "Dots", pages: 3, divider: true, generator: dots,\n'
    "     grid: {x: {base_spacing: 5mm}, y: {base_spacing: 5mm}}, base_size: 0.4mm}\n"
    '  - {label: "Squares", pages: 2, divider: true, generator: lines,\n'
    "     families: [{direction: horizontal, base_spacing: 5mm},\n"
    "                {direction: vertical, base_spacing: 5mm}]}\n"
    '  - {label: "Music", pages: 2, divider: true, generator: staves,\n'
    "     count: 10, stave_space: 1.8mm, system_gap: 4sp}\n"
)

#: Page indices that follow from § 7.13's page order — title, contents, then per
#: section its divider and its pages. Each test that uses one also asserts what
#: is on the page, so a changed order fails here rather than passing quietly.
FIRST_DOTS_PAGE = 3
FIRST_LINES_PAGE = 7
FIRST_STAVES_PAGE = 10


@pytest.fixture(scope="module")
def nb(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return sheet(tmp_path_factory.mktemp("nb"), NOTEBOOK, "notebook.pdf")


class TestNotebookDocument:
    """§ 7.13: sections filled by ordinary blades — so the thing to read back is
    whether composing a blade bends its measure. It must not: the handle calls
    the generator on the document path exactly as on the blade path (decision
    50), and the only proof of that is the drawing."""

    def test_the_page_plan_is_the_sections_plus_a_title_and_a_contents(
        self, nb: Path
    ) -> None:
        # § 7.13: "optionale Titelseite, Inhaltsverzeichnis, dann je Abschnitt
        # sein Trennblatt (falls verlangt) und seine Seiten." Every term of that
        # sum is written in the definition: 1 + 1 + (1+3) + (1+2) + (1+2).
        assert pdfread.page_count(nb) == 1 + 1 + (1 + 3) + (1 + 2) + (1 + 2)

    def test_the_contents_names_the_page_a_section_really_begins_on(
        self, nb: Path
    ) -> None:
        # § 7.13: "Das Verzeichnis nennt zu jedem Abschnitt die Seitenzahl, auf
        # der er beginnt." Two independently drawn facts have to agree: the
        # number printed on the contents page, and the page that first answers
        # `{section}` with that label in its own header. Neither is computed
        # from the other, and both come off the paper.
        listed = self.contents_entries(nb)
        assert set(listed) == {"Dots", "Squares", "Music"}
        for label, page in listed.items():
            begins = min(i for i, name in self.sections_by_page(nb).items()
                         if name == label)
            assert page == begins, (label, page, begins)

    def test_a_section_gets_the_pattern_area_section_8_1_computes(
        self, nb: Path
    ) -> None:
        # § 7.13: "ein Abschnitt nimmt den Musterbereich, wie er ist." A4 less
        # 15 mm margins is 180 mm wide; less both bands it is 245 mm tall. A
        # 5 mm lattice from the origin is therefore 37 columns by 50 rows, and
        # both numbers are § 8.1's arithmetic, not the notebook's.
        dots = [p for p in segments(nb, FIRST_DOTS_PAGE)
                if pdfread.length_um(p[0], p[1]) < EXACT]
        assert len({round(p[0][0]) for p in dots}) == 37
        assert len({round(p[0][1]) for p in dots}) == 50

    def test_two_sections_two_blades_one_declared_measure(self, nb: Path) -> None:
        # The composition claim itself. `dots` and `lines` are different blades
        # with different code, and both were told 5 mm in the same document. If
        # the handle really hands each the same pattern area (§ 7.13), the two
        # sections' lattices must fall on exactly the same lines — not merely
        # have the same pitch.
        dots = [p for p in segments(nb, FIRST_DOTS_PAGE)
                if pdfread.length_um(p[0], p[1]) < EXACT]
        ruled = segments(nb, FIRST_LINES_PAGE)
        columns = sorted({round(p[0][0]) for p in ruled
                          if abs(p[0][0] - p[1][0]) < EXACT})
        rows = sorted({round(p[0][1]) for p in ruled
                       if abs(p[0][1] - p[1][1]) < EXACT})
        assert columns == sorted({round(p[0][0]) for p in dots})
        assert rows == sorted({round(p[0][1]) for p in dots})
        # And the declared 5 mm is what the gaps are, on both.
        for axis in (columns, rows):
            assert {b - a for a, b in zip(axis, axis[1:], strict=False)} == {5_000}

    def test_the_music_section_keeps_its_declared_stave_space_and_system_gap(
        self, nb: Path
    ) -> None:
        # § 7.3: `stave_space` is the distance between neighbouring lines, and
        # `system_gap` is the **gap** — bottom line of one system to top line of
        # the next — not the pitch. The definition says 1.8 mm and 4 sp, so ten
        # five-line systems are 50 lines with 40 gaps of 1.8 mm and 9 of 7.2 mm.
        ys = sorted({round(p[0][1]) for p in segments(nb, FIRST_STAVES_PAGE)
                     if abs(p[0][1] - p[1][1]) < EXACT})
        assert len(ys) == 10 * 5
        gaps = Counter(b - a for a, b in zip(ys, ys[1:], strict=False))
        assert gaps == Counter({1_800: 40, 7_200: 9}), gaps

    def test_every_page_of_a_section_carries_the_same_paper(self, nb: Path) -> None:
        # A section is `pages: 3` of one paper, so the three have to be the same
        # drawing — the bands differ (`{page}` counts), the pattern must not.
        first = sorted(round(p[0][0]) for p in segments(nb, FIRST_DOTS_PAGE))
        for offset in (1, 2):
            assert sorted(
                round(p[0][0]) for p in segments(nb, FIRST_DOTS_PAGE + offset)
            ) == first

    # ------------------------------------------------------------- helpers

    def contents_entries(self, nb: Path) -> dict[str, int]:
        """Label to printed page, read off the contents page a line at a time."""
        placed = [t for t in pdfread.texts_um(nb, 1)
                  if NOTEBOOK_PATTERN_BOTTOM < t.y < NOTEBOOK_PATTERN_TOP]
        rows: dict[int, list[pdfread.PlacedText]] = {}
        for text in placed:
            rows.setdefault(round(text.y), []).append(text)
        entries = {}
        for line in rows.values():
            words = sorted(line, key=lambda t: t.x)
            if len(words) == 2 and words[1].content.isdigit():
                entries[words[0].content] = int(words[1].content)
        return entries

    def sections_by_page(self, nb: Path) -> dict[int, str]:
        """Printed page number to the section its header names (§ 7.13)."""
        found = {}
        for index in range(pdfread.page_count(nb)):
            placed = pdfread.texts_um(nb, index)
            header = [t for t in placed if t.y >= NOTEBOOK_PATTERN_TOP]
            footer = [t for t in placed if t.y <= NOTEBOOK_PATTERN_BOTTOM]
            if not header or not footer:
                continue        # the title page carries no bands
            found[int(footer[0].content.split("/")[0])] = header[0].content
        return found
