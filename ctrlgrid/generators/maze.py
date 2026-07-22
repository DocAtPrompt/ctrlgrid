"""`maze` — rectangular grid mazes (§ 7.5).

The first blade that is not a pattern, and three things follow from that.

**It is procedural, so the seed rule of § 3.3 decides whether two runs agree.**
The effective seed is `blake2b(seed, page_index)` and never `seed + index`:
some generators correlate neighbouring pages seeded that way, and a class set
of twenty mazes that all look alike is a real failure, not a theoretical one.

**`min_path_factor` is not a luxury** (§ 7.5). A naive generator regularly
produces mazes whose solution is laughably short behind a complicated-looking
picture. The length is checked against `factor x cells_x x cells_y` and the
maze is generated again when it falls short — with a bound, because a factor
nobody can reach must be an error rather than a hang.

**Two solution modes reach into the page loop.** `separate_page` and
`back_mirrored` double the sheets: odd sheets are puzzles, even ones solutions,
`{page_count}` is twice the number of puzzles, and a name list gives each entry
both sheets. The blade says so through `sheets()`; the doubling, the numbering
and the mirroring stay with the handle, because they are properties of the
*page*, not of the pattern (§ 3).

Only rectangular grid mazes in v1, and no `complexity` dial: the three
algorithms have no common 0…1 parameter, and the character *is* the choice of
algorithm (§ 7.5).
"""

from __future__ import annotations

import hashlib
import random
from collections import deque
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from ctrlgrid.axes import AxisPeriod
from ctrlgrid.errors import DefinitionError
from ctrlgrid.marks import Area, Layer, Mark, Point, Polygon, Segment, Um
from ctrlgrid.model import ColorField, LengthField, Section
from ctrlgrid.pages import PageContext, SheetPlan
from ctrlgrid.units import Length
from ctrlgrid.writers import WriterQuery

#: How often a maze may be generated again before a `min_path_factor` counts as
#: unreachable. § 7.5 asks for regeneration; it does not ask for a hang, and a
#: factor of 0.99 on a 10x10 grid is simply not a thing that exists.
MAX_ATTEMPTS = 200

Corner = Literal["bottom-left", "bottom-right", "top-left", "top-right"]


class Cells(Section):
    x: int = Field(ge=2)
    y: int = Field(ge=2)


class MazeConfig(BaseModel):
    """The definition section belonging to this blade (§ 3.6, seam 2)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    cells: Cells
    algorithm: Literal["backtracker", "prim", "kruskal"] = "backtracker"
    start: Corner = "bottom-left"
    goal: Corner = "top-right"
    #: The guaranteed minimum length of the solution, as a share of the cells
    #: (§ 7.5). **Off by default, and that is a decision, not an oversight:**
    #: what is reachable depends on the algorithm — measured over 30 carvings,
    #: a backtracker reaches 0.35–0.45 of the cells, kruskal 0.15–0.25 and prim
    #: 0.10–0.20, and it falls further as the grid grows. A single built-in
    #: number would be toothless for one algorithm and unreachable for another,
    #: so the demand is the user's to make and § 5.1's rule holds: no invented
    #: numbers. The presets set one.
    min_path_factor: float = Field(default=0.0, ge=0.0, le=1.0)
    wall_weight: LengthField = Length(um=176, mm=0.17638888888888887, raw="0.5pt")
    color: ColorField = "#000000"
    solution_color: ColorField = "#cc3333"
    seed: int = 0
    solution: Literal["none", "overlay", "separate_page", "back_mirrored"] = "none"


@dataclass(frozen=True, slots=True)
class Maze:
    """A carved grid: which walls are gone, and the way through."""

    width: int
    height: int
    open_right: frozenset[tuple[int, int]]
    open_up: frozenset[tuple[int, int]]
    solution: tuple[tuple[int, int], ...]


class MazeGenerator:
    name = "maze"
    config_model = MazeConfig

    #: § 8.3 lists `maze` among the blades where snapping is an error.
    supports_snap = False

    def periodic_axes(self, cfg: MazeConfig) -> dict[str, list[AxisPeriod]]:
        return {}

    def is_page_invariant(self, cfg: MazeConfig) -> bool:
        """Never: every sheet is a different maze (§ 10.1)."""
        return False

    def sheets(self, cfg: MazeConfig) -> SheetPlan:
        """§ 7.5: two of the four solution modes need a sheet of their own.

        Odd sheets are puzzles and even ones solutions, so `--pages 10` gives
        ten puzzles on twenty sheets and a name list gives each entry both.
        """
        if cfg.solution in ("separate_page", "back_mirrored"):
            mirrored = frozenset({1}) if cfg.solution == "back_mirrored" else frozenset()
            return SheetPlan(per_item=2, mirrored=mirrored)
        return SheetPlan()

    def describe(self, cfg: MazeConfig) -> list[str]:
        return [
            f"maze: {cfg.cells.x} x {cfg.cells.y} cells, {cfg.algorithm}, seed "
            f"{cfg.seed}, minimum path {cfg.min_path_factor:g} x cells, solution "
            f"{cfg.solution}"
        ]

    def check(self, cfg: MazeConfig, *, area: Area, q: WriterQuery) -> None:
        """§ 12 point 10: the block has to fit, and is never squeezed."""
        cell = _cell_size(cfg, area)
        if cell < cfg.wall_weight.um * 3:
            raise DefinitionError(
                f"{cfg.cells.x} x {cfg.cells.y} cells in a pattern area of "
                f"{_mm(area.width)} x {_mm(area.height)} leave {_mm(cell)} per cell, which "
                f"is no wider than the walls around it ({cfg.wall_weight.raw}). Use fewer "
                "cells or a larger format (§ 7.5, § 12 point 10)",
                field="cells",
            )

    def generate(
        self,
        cfg: MazeConfig,
        *,
        area: Area,
        page: PageContext,
        q: WriterQuery,
    ) -> Iterator[Mark]:
        maze = self._maze(cfg, page)
        cell = _cell_size(cfg, area)
        left = (area.width - cell * cfg.cells.x) // 2
        bottom = (area.height - cell * cfg.cells.y) // 2

        def corner(column: int, row: int) -> Point:
            return Point(left + column * cell, bottom + row * cell)

        # The way in and the way out are gaps in the outer wall, at the two
        # corners `start` and `goal` name.
        openings = _openings(cfg)
        for row in range(cfg.cells.y + 1):
            for column in range(cfg.cells.x + 1):
                if (
                    column < cfg.cells.x
                    and ("h", column, row) not in openings
                    and not _open_horizontal(maze, column, row)
                ):
                    yield Segment(
                        start=corner(column, row),
                        end=corner(column + 1, row),
                        weight=cfg.wall_weight.mm,
                        color=cfg.color or "#000000",
                        layer=Layer.PATTERN,
                    )
                if (
                    row < cfg.cells.y
                    and ("v", column, row) not in openings
                    and not _open_vertical(maze, column, row)
                ):
                    yield Segment(
                        start=corner(column, row),
                        end=corner(column, row + 1),
                        weight=cfg.wall_weight.mm,
                        color=cfg.color or "#000000",
                        layer=Layer.PATTERN,
                    )

        if self._draws_solution(cfg, page):
            yield Polygon(
                points=tuple(
                    Point(
                        left + column * cell + cell // 2,
                        bottom + row * cell + cell // 2,
                    )
                    for column, row in maze.solution
                ),
                closed=False,
                weight=cfg.wall_weight.mm * 2,
                color=cfg.solution_color or "#cc3333",
                fill_color=None,
                layer=Layer.PATTERN,
            )

    def _draws_solution(self, cfg: MazeConfig, page: PageContext) -> bool:
        if cfg.solution == "none":
            return False
        if cfg.solution == "overlay":
            return True
        # § 7.5: odd sheets are puzzles, even ones solutions.
        return page.index % 2 == 1

    def _maze(self, cfg: MazeConfig, page: PageContext) -> Maze:
        """Carve until the solution is long enough (§ 7.5).

        The seed is stable and the *puzzle's* index seeds it, so the solution
        sheet shows the way through the maze on the sheet before it rather
        than a new maze of its own.
        """
        item = page.index // (2 if cfg.solution in ("separate_page", "back_mirrored") else 1)
        wanted = cfg.min_path_factor * cfg.cells.x * cfg.cells.y
        best = 0

        for attempt in range(MAX_ATTEMPTS):
            rng = random.Random(_seed(cfg.seed, item, attempt))
            maze = _carve(cfg, rng)
            best = max(best, len(maze.solution))
            if len(maze.solution) >= wanted:
                return maze

        raise DefinitionError(
            f"min_path_factor {cfg.min_path_factor:g} asks for a solution of at least "
            f"{wanted:.0f} cells and {MAX_ATTEMPTS} attempts on this "
            f"{cfg.cells.x} x {cfg.cells.y} grid reached {best} "
            f"({best / (cfg.cells.x * cfg.cells.y):.2f}). § 7.5 has the tool generate "
            "again rather than settle, but a factor nobody can reach has to be an error "
            "and not a hang. Measured over thirty carvings, `backtracker` reaches "
            "0.35-0.45 of the cells, `kruskal` 0.15-0.25 and `prim` 0.10-0.20, and all "
            "three fall as the grid grows — lower min_path_factor, or switch algorithm",
            field="min_path_factor",
        )


# ------------------------------------------------------------------- carving


def _carve(cfg: MazeConfig, rng: random.Random) -> Maze:
    """One perfect maze: a spanning tree over the cell grid (§ 7.5).

    Perfect means exactly one route between any two cells, which is what makes
    the wall count follow from the cell count and the solution unique.
    """
    width, height = cfg.cells.x, cfg.cells.y
    carver = {"backtracker": _backtracker, "prim": _prim, "kruskal": _kruskal}[
        cfg.algorithm
    ]
    passages = carver(width, height, rng)

    open_right = frozenset(
        (x, y) for (x, y), (nx, ny) in passages if nx == x + 1 and ny == y
    )
    open_up = frozenset(
        (x, y) for (x, y), (nx, ny) in passages if nx == x and ny == y + 1
    )
    maze = Maze(
        width=width,
        height=height,
        open_right=open_right,
        open_up=open_up,
        solution=(),
    )
    start, goal = _ends(cfg)
    return Maze(
        width=width,
        height=height,
        open_right=open_right,
        open_up=open_up,
        solution=_route(maze, start, goal),
    )


def _neighbours(x: int, y: int, width: int, height: int) -> list[tuple[int, int]]:
    return [
        (nx, ny)
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1))
        if 0 <= nx < width and 0 <= ny < height
    ]


def _normal(a: tuple[int, int], b: tuple[int, int]) -> tuple[tuple[int, int], ...]:
    """A passage as an ordered pair, so both directions are the same edge."""
    return tuple(sorted((a, b)))  # type: ignore[return-value]


def _backtracker(
    width: int, height: int, rng: random.Random
) -> set[tuple[tuple[int, int], tuple[int, int]]]:
    """Depth-first with backtracking: long corridors, few junctions."""
    start = (0, 0)
    seen = {start}
    stack = [start]
    passages: set[tuple[tuple[int, int], tuple[int, int]]] = set()
    while stack:
        x, y = stack[-1]
        options = [n for n in _neighbours(x, y, width, height) if n not in seen]
        if not options:
            stack.pop()
            continue
        chosen = options[rng.randrange(len(options))]
        passages.add(_normal((x, y), chosen))  # type: ignore[arg-type]
        seen.add(chosen)
        stack.append(chosen)
    return passages


def _prim(
    width: int, height: int, rng: random.Random
) -> set[tuple[tuple[int, int], tuple[int, int]]]:
    """Randomised Prim: many short branches, a bushy maze."""
    start = (0, 0)
    seen = {start}
    frontier = [(start, n) for n in _neighbours(*start, width, height)]
    passages: set[tuple[tuple[int, int], tuple[int, int]]] = set()
    while frontier:
        index = rng.randrange(len(frontier))
        inside, outside = frontier.pop(index)
        if outside in seen:
            continue
        passages.add(_normal(inside, outside))  # type: ignore[arg-type]
        seen.add(outside)
        frontier.extend(
            (outside, n) for n in _neighbours(*outside, width, height) if n not in seen
        )
    return passages


def _kruskal(
    width: int, height: int, rng: random.Random
) -> set[tuple[tuple[int, int], tuple[int, int]]]:
    """Randomised Kruskal: uniform texture, no bias towards the start."""
    edges = [
        ((x, y), (x + 1, y)) for y in range(height) for x in range(width - 1)
    ] + [((x, y), (x, y + 1)) for y in range(height - 1) for x in range(width)]
    # Fisher-Yates by hand: `rng.shuffle` is not promised to keep its exact
    # sequence across Python versions, and § 10.1 is a promise about bytes.
    for index in range(len(edges) - 1, 0, -1):
        other = rng.randrange(index + 1)
        edges[index], edges[other] = edges[other], edges[index]

    parent: dict[tuple[int, int], tuple[int, int]] = {}

    def root(cell: tuple[int, int]) -> tuple[int, int]:
        while parent.get(cell, cell) != cell:
            parent[cell] = parent.get(parent[cell], parent[cell])
            cell = parent[cell]
        return cell

    passages: set[tuple[tuple[int, int], tuple[int, int]]] = set()
    for a, b in edges:
        ra, rb = root(a), root(b)
        if ra == rb:
            continue
        parent[ra] = rb
        passages.add(_normal(a, b))  # type: ignore[arg-type]
    return passages


def _route(maze: Maze, start: tuple[int, int], goal: tuple[int, int]) -> tuple[
    tuple[int, int], ...
]:
    """The one way through — breadth-first, because a perfect maze has only one."""
    previous: dict[tuple[int, int], tuple[int, int]] = {start: start}
    queue = deque([start])
    while queue:
        cell = queue.popleft()
        if cell == goal:
            break
        for step in _open_neighbours(maze, cell):
            if step not in previous:
                previous[step] = cell
                queue.append(step)

    path = [goal]
    while path[-1] != start:
        path.append(previous[path[-1]])
    return tuple(reversed(path))


def _open_neighbours(maze: Maze, cell: tuple[int, int]) -> Iterator[tuple[int, int]]:
    x, y = cell
    if (x, y) in maze.open_right:
        yield (x + 1, y)
    if (x - 1, y) in maze.open_right:
        yield (x - 1, y)
    if (x, y) in maze.open_up:
        yield (x, y + 1)
    if (x, y - 1) in maze.open_up:
        yield (x, y - 1)


# ------------------------------------------------------------------- drawing


def _open_horizontal(maze: Maze, column: int, row: int) -> bool:
    """Whether the wall below cell (column, row) is gone."""
    if row == 0 or row == maze.height:
        return False
    return (column, row - 1) in maze.open_up


def _open_vertical(maze: Maze, column: int, row: int) -> bool:
    """Whether the wall left of cell (column, row) is gone."""
    if column == 0 or column == maze.width:
        return False
    return (column - 1, row) in maze.open_right


def _ends(cfg: MazeConfig) -> tuple[tuple[int, int], tuple[int, int]]:
    corners = {
        "bottom-left": (0, 0),
        "bottom-right": (cfg.cells.x - 1, 0),
        "top-left": (0, cfg.cells.y - 1),
        "top-right": (cfg.cells.x - 1, cfg.cells.y - 1),
    }
    return corners[cfg.start], corners[cfg.goal]


def _openings(cfg: MazeConfig) -> set[tuple[str, int, int]]:
    """Which outer wall segments are left out — the way in and the way out.

    A corner on the bottom row opens downwards, one on the top row upwards.
    Both are on the horizontal outer wall, which is where a hand naturally
    enters a maze printed portrait.
    """
    openings = set()
    for corner in (cfg.start, cfg.goal):
        column, row = {
            "bottom-left": (0, 0),
            "bottom-right": (cfg.cells.x - 1, 0),
            "top-left": (0, cfg.cells.y - 1),
            "top-right": (cfg.cells.x - 1, cfg.cells.y - 1),
        }[corner]
        openings.add(("h", column, 0 if row == 0 else cfg.cells.y))
    return openings


def _cell_size(cfg: MazeConfig, area: Area) -> Um:
    """Square cells, like `grid` (§ 7.4): the block is centred, never stretched."""
    return min(area.width // cfg.cells.x, area.height // cfg.cells.y)


def _seed(seed: int, item: int, attempt: int) -> int:
    """§ 3.3: a stable hash, never `seed + index`.

    Python's `hash()` is not stable across versions and is process-dependent
    for strings, and adding the index correlates neighbouring pages in some
    generators. blake2b is neither.
    """
    digest = hashlib.blake2b(
        f"{seed}:{item}:{attempt}".encode(), digest_size=8
    ).digest()
    return int.from_bytes(digest, "big")


def _mm(um: Um) -> str:
    return f"{um / 1000:.1f}mm"
