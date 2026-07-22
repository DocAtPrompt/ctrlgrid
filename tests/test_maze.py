"""The `maze` blade (§ 7.5) — the first blade that is not a pattern.

Three things make it unlike every other one. It is **procedural**, so § 3.3's
seed rule decides whether two runs agree. It has a **quality criterion**
(`min_path_factor`), because a naive generator regularly produces mazes whose
solution is laughably short behind a complicated-looking picture. And two of
its `solution` modes reach into the page loop: § 7.5 doubles the sheet count
and makes odd sheets puzzles and even ones solutions.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from ctrlgrid.errors import DefinitionError
from ctrlgrid.generators.maze import MazeConfig, MazeGenerator
from ctrlgrid.loader import loads
from ctrlgrid.marks import Area, Polygon, Segment
from ctrlgrid.pages import PageContext, build, preflight, seed_material
from ctrlgrid.writers.pdf import PdfWriter

AREA = Area(width=100_000, height=100_000)
Q = PdfWriter("unused.pdf")

CELLS = {"cells": {"x": 10, "y": 10}}


def page(index: int = 0, count: int = 1) -> PageContext:
    return PageContext(
        index=index,
        number=index + 1,
        count=count,
        name=None,
        is_even=(index + 1) % 2 == 0,
        seed_material=seed_material(0, index),
    )


def marks(definition: dict, index: int = 0, area: Area = AREA) -> list:
    config = MazeConfig.model_validate(definition)
    return list(MazeGenerator().generate(config, area=area, page=page(index), q=Q))


def walls(definition: dict, index: int = 0) -> list[Segment]:
    return [mark for mark in marks(definition, index) if isinstance(mark, Segment)]


class TestTheMaze:
    def test_it_draws_walls(self) -> None:
        assert walls(CELLS)

    def test_the_cells_are_square(self) -> None:
        # Count-driven like `grid` (§ 7.4): the block is centred and nothing
        # is stretched to fill (§ 8.2).
        drawn = walls({"cells": {"x": 10, "y": 5}})
        lengths = {
            round(abs(w.end.x - w.start.x) + abs(w.end.y - w.start.y)) for w in drawn
        }
        assert lengths == {10_000}

    def test_every_maze_is_a_spanning_tree(self) -> None:
        # A grid maze is perfect: exactly one route between any two cells, so
        # the wall count is fixed by the cell count alone.
        for algorithm in ("backtracker", "prim", "kruskal"):
            drawn = walls({**CELLS, "algorithm": algorithm})
            # 2*n*(n+1) grid edges minus the n*n-1 carved ones, minus the two
            # openings at start and goal.
            assert len(drawn) == 2 * 10 * 11 - (10 * 10 - 1) - 2

    def test_the_three_algorithms_differ(self) -> None:
        shapes = {
            algorithm: tuple(
                sorted((w.start.x, w.start.y, w.end.x, w.end.y) for w in
                       walls({**CELLS, "algorithm": algorithm, "seed": 4711}))
            )
            for algorithm in ("backtracker", "prim", "kruskal")
        }
        assert len(set(shapes.values())) == 3

    def test_start_and_goal_are_open(self) -> None:
        # The way in and the way out are gaps in the outer wall.
        drawn = walls(CELLS)
        bottom = [w for w in drawn if w.start.y == w.end.y == 0]
        assert len(bottom) == 9


class TestReproducibility:
    def test_the_same_seed_gives_the_same_maze(self) -> None:
        first = walls({**CELLS, "seed": 4711})
        second = walls({**CELLS, "seed": 4711})
        assert [(w.start, w.end) for w in first] == [(w.start, w.end) for w in second]

    def test_a_different_seed_gives_a_different_maze(self) -> None:
        first = walls({**CELLS, "seed": 4711})
        second = walls({**CELLS, "seed": 4712})
        assert [(w.start, w.end) for w in first] != [(w.start, w.end) for w in second]

    def test_every_page_gets_its_own_maze(self) -> None:
        # § 7.5: the seed is stable per page, so page 2 is a different maze —
        # and blake2b, not `seed + index`, because some PRNGs correlate
        # neighbouring pages seeded that way (§ 3.3).
        first = walls({**CELLS, "seed": 4711}, index=0)
        second = walls({**CELLS, "seed": 4711}, index=1)
        assert [(w.start, w.end) for w in first] != [(w.start, w.end) for w in second]


class TestMinimumPathLength:
    def test_a_short_solution_is_regenerated(self) -> None:
        # § 7.5: not a luxury — the picture looks complicated either way.
        config = MazeConfig.model_validate(
            {**CELLS, "algorithm": "kruskal", "seed": 1, "min_path_factor": 0.25}
        )
        maze = MazeGenerator()._maze(config, page(0))
        assert len(maze.solution) >= 0.25 * 100

    def test_an_impossible_factor_is_refused_rather_than_looped(self) -> None:
        config = MazeConfig.model_validate({**CELLS, "min_path_factor": 0.99})
        with pytest.raises(DefinitionError) as excinfo:
            MazeGenerator()._maze(config, page(0))
        message = str(excinfo.value)
        assert "0.99" in message and "attempt" in message.lower()

    def test_it_is_off_by_default(self) -> None:
        # What is reachable depends on the algorithm — measured, a backtracker
        # gets 0.35-0.45 of the cells and prim 0.10-0.20 — so a built-in
        # number would be toothless for one and unreachable for another. § 5.1:
        # no invented numbers.
        assert MazeConfig.model_validate(CELLS).min_path_factor == 0.0

    def test_the_factor_has_a_range(self) -> None:
        with pytest.raises(ValidationError):
            MazeConfig.model_validate({**CELLS, "min_path_factor": 2})


class TestSolutions:
    def solution_of(self, definition: dict, index: int = 0) -> list[Polygon]:
        return [mark for mark in marks(definition, index) if isinstance(mark, Polygon)]

    def test_none_draws_no_solution(self) -> None:
        assert self.solution_of(CELLS) == []

    def test_overlay_draws_it_on_the_same_sheet(self) -> None:
        drawn = self.solution_of({**CELLS, "solution": "overlay"})
        assert len(drawn) == 1
        assert drawn[0].closed is False

    def test_the_solution_runs_from_start_to_goal(self) -> None:
        path = self.solution_of({**CELLS, "solution": "overlay"})[0]
        assert path.points[0].x < path.points[-1].x
        assert path.points[0].y < path.points[-1].y

    def test_separate_page_leaves_the_first_sheet_a_puzzle(self) -> None:
        assert self.solution_of({**CELLS, "solution": "separate_page"}, index=0) == []

    def test_separate_page_puts_the_solution_on_the_second(self) -> None:
        assert self.solution_of({**CELLS, "solution": "separate_page"}, index=1)

    def test_the_solution_sheet_shows_the_same_maze(self) -> None:
        # § 7.5: page 2 solves page 1 rather than being a new maze.
        puzzle = walls({**CELLS, "solution": "separate_page", "seed": 7}, index=0)
        answer = walls({**CELLS, "solution": "separate_page", "seed": 7}, index=1)
        assert [(w.start, w.end) for w in puzzle] == [(w.start, w.end) for w in answer]


class TestThePageLoop:
    def definition(self, solution: str, pages: int = 3) -> str:
        return (
            "version: 1\n"
            "page:\n  format: a6\n  margin: 8mm\n"
            f"pages:\n  count: {pages}\n"
            "generator: maze\n"
            "cells: {x: 8, y: 8}\n"
            f"solution: {solution}\n"
        )

    def test_separate_page_doubles_the_sheet_count(self, tmp_path: Path) -> None:
        # § 7.5: `--pages 10` gives ten puzzles on twenty sheets.
        import pdfread

        path = tmp_path / "maze.pdf"
        build(loads(self.definition("separate_page"), source="test"), PdfWriter(path))
        assert pdfread.page_count(path) == 6

    def test_none_does_not(self, tmp_path: Path) -> None:
        import pdfread

        path = tmp_path / "maze.pdf"
        build(loads(self.definition("none"), source="test"), PdfWriter(path))
        assert pdfread.page_count(path) == 3

    def test_the_numbering_counts_every_sheet(self, tmp_path: Path) -> None:
        import pdfread

        path = tmp_path / "maze.pdf"
        text = self.definition("separate_page", pages=2).replace(
            "generator: maze",
            "footer:\n  height: 8mm\n  center: '{page} / {page_count}'\ngenerator: maze",
        )
        build(loads(text, source="test"), PdfWriter(path))
        assert "1 / 4" in pdfread.text_on(path, 0)
        assert "4 / 4" in pdfread.text_on(path, 3)

    def test_a_name_list_gives_each_entry_both_sheets(self, tmp_path: Path) -> None:
        import pdfread

        path = tmp_path / "maze.pdf"
        text = self.definition("separate_page", pages=2).replace(
            "generator: maze",
            "header:\n  height: 8mm\n  center: '{name}'\ngenerator: maze",
        )
        document = loads(text, {"names": ["Ada", "Grace"]}, source="test")
        build(document, PdfWriter(path))
        assert "Ada" in pdfread.text_on(path, 0)
        assert "Ada" in pdfread.text_on(path, 1)
        assert "Grace" in pdfread.text_on(path, 2)


class TestBackMirrored:
    def test_the_solution_sheet_is_mirrored(self, tmp_path: Path) -> None:
        import pdfread

        path = tmp_path / "mirrored.pdf"
        build(
            loads(
                "version: 1\npage: {format: a6, margin: 8mm}\npages: {count: 1}\n"
                "generator: maze\ncells: {x: 8, y: 8}\nsolution: back_mirrored\n",
                source="test",
            ),
            PdfWriter(path),
        )
        sheet_width = 105_000

        def walls_on(index: int) -> set[tuple[int, int, int, int]]:
            return {
                tuple(round(value) for value in (line.x1, line.y1, line.x2, line.y2))
                for line in pdfread.lines_um(path, index)
            }

        def mirrored(walls: set[tuple[int, int, int, int]]) -> set[tuple[int, int, int, int]]:
            return {
                (sheet_width - x1, y1, sheet_width - x2, y2) for x1, y1, x2, y2 in walls
            }

        front, back = walls_on(0), walls_on(1)
        # The same maze, reflected in the sheet's vertical centre line — so it
        # covers the puzzle when the sheet is held against the light (§ 7.5).
        assert back == mirrored(front)
        assert back != front

    def test_duplex_with_unequal_margins_is_refused(self) -> None:
        # § 7.5: the shifting gutter would move the pattern area between the
        # sides, and the solution would land exactly that far off.
        definition = (
            "version: 1\n"
            "page: {format: a6, duplex: true, margin: {top: 8mm, bottom: 8mm, "
            "inner: 15mm, outer: 8mm}}\n"
            "generator: maze\ncells: {x: 8, y: 8}\nsolution: back_mirrored\n"
        )
        with pytest.raises(DefinitionError) as excinfo:
            preflight(loads(definition, source="test"), Q)
        message = str(excinfo.value)
        assert "duplex" in message and "back_mirrored" in message

    def test_duplex_with_equal_margins_is_fine(self) -> None:
        definition = (
            "version: 1\npage: {format: a6, duplex: true, margin: 8mm}\n"
            "generator: maze\ncells: {x: 8, y: 8}\nsolution: back_mirrored\n"
        )
        preflight(loads(definition, source="test"), Q)


class TestTheSeam:
    def test_snapping_is_refused(self) -> None:
        assert MazeGenerator().supports_snap is False

    def test_a_maze_is_not_page_invariant(self) -> None:
        # § 10.1: every sheet is a different maze, so the writer may not store
        # the pattern once and reference it.
        assert MazeGenerator().is_page_invariant(MazeConfig.model_validate(CELLS)) is False

    def test_describe_names_the_algorithm_and_the_grid(self) -> None:
        described = "\n".join(
            MazeGenerator().describe(MazeConfig.model_validate({**CELLS, "seed": 4711}))
        )
        assert "backtracker" in described and "10" in described and "4711" in described

    def test_too_many_cells_are_refused_with_the_arithmetic(self) -> None:
        config = MazeConfig.model_validate({"cells": {"x": 400, "y": 400}})
        with pytest.raises(DefinitionError) as excinfo:
            MazeGenerator().check(config, area=AREA, q=Q)
        assert "400" in str(excinfo.value)


class TestOnTheSheet:
    def test_two_runs_produce_identical_bytes(self, tmp_path: Path) -> None:
        # § 3.3: the seed rule exists for exactly this.
        first, second = tmp_path / "a.pdf", tmp_path / "b.pdf"
        definition = (
            "version: 1\npage: {format: a6, margin: 8mm}\npages: {count: 2}\n"
            "generator: maze\ncells: {x: 12, y: 12}\nseed: 4711\nsolution: overlay\n"
        )
        for path in (first, second):
            build(loads(definition, source="test"), PdfWriter(path))
        assert first.read_bytes() == second.read_bytes()

    def test_the_seed_flag_beats_the_definition(self, tmp_path: Path) -> None:
        # § 11: the command line wins, always.
        definition = (
            "version: 1\ngenerator: maze\ncells: {x: 8, y: 8}\nseed: 1\n"
        )
        document = loads(definition, {"seed": 99}, source="test")
        assert document.config.seed == 99
