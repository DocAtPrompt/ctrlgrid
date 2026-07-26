"""A sheet plan inside a notebook section (§ 7.13, decision 55).

Decision 52 refused this and said why: § 7.13 did not settle what a per-section
sheet plan means. It does now — a section is a definition in miniature, so its
blade sees a page context of the section's own.
"""

from __future__ import annotations

from pathlib import Path

import pdfread
import pytest

from ctrlgrid.errors import DefinitionError
from ctrlgrid.loader import loads
from ctrlgrid.pages import build
from ctrlgrid.writers.pdf import PdfWriter


def notebook(sections: str, *, title: bool = False) -> str:
    return (
        "version: 1\n"
        "page: {format: a5, margin: 10mm}\n"
        "generator: notebook\n"
        + ('title_page: {title: "N"}\n' if title else "")
        + "sections:\n" + sections
    )


def maze_section(pages: int, solution: str, label: str = "Mazes") -> str:
    return (
        f'  - {{label: "{label}", pages: {pages}, generator: maze,\n'
        f"     cells: {{x: 8, y: 10}}, seed: 4711, solution: {solution}}}\n"
    )


def sheet(tmp_path: Path, definition: str, name: str = "n.pdf") -> Path:
    path = tmp_path / name
    build(loads(definition, source="test"), PdfWriter(path))
    return path


class TestASectionIsARunOfItsOwn:
    """§ 7.13: "Ein Abschnitt ist eine Definition im Kleinen." So what precedes
    a section must not reach into it — the bug decision 52 recorded was a title
    page silently redrawing every maze."""

    def test_a_title_page_before_it_does_not_change_the_mazes(
        self, tmp_path: Path
    ) -> None:
        plain = sheet(tmp_path, notebook(maze_section(2, "none")), "plain.pdf")
        titled = sheet(
            tmp_path, notebook(maze_section(2, "none"), title=True), "titled.pdf"
        )
        # The maze pages are the last two of each document. Their walls must be
        # identical drawings, not merely the same count.
        for offset in (2, 1):
            a = pdfread.subpaths_um(plain, pdfread.page_count(plain) - offset)
            b = pdfread.subpaths_um(titled, pdfread.page_count(titled) - offset)
            assert a == b

    def test_two_sections_of_the_same_maze_draw_the_same_pages(
        self, tmp_path: Path
    ) -> None:
        # Two identical sections are two identical runs, so page 1 of each is
        # the same maze. Before this, the second section's index carried on
        # from the first and every maze differed.
        path = sheet(
            tmp_path,
            notebook(maze_section(1, "none", "A") + maze_section(1, "none", "B")),
        )
        pages = pdfread.page_count(path)
        assert pdfread.subpaths_um(path, pages - 2) == pdfread.subpaths_um(path, pages - 1)


DOTS = (
    '  - {label: "Dots", pages: 2, generator: dots,\n'
    "     grid: {x: {base_spacing: 5mm}, y: {base_spacing: 5mm}}}\n"
)


class TestTheSheetPlanIsCarriedOut:
    """§ 7.5 on the blade path: "`--pages 10` ergibt zehn Rätsel auf zwanzig
    Blättern." One rule for both paths, so `pages:` counts items here too."""

    def test_ten_puzzles_take_twenty_pages(self, tmp_path: Path) -> None:
        path = sheet(tmp_path, notebook(maze_section(10, "separate_page")))
        # contents + 20 maze pages, no title page and no divider asked for.
        assert pdfread.page_count(path) == 1 + 20

    def test_the_solution_belongs_to_the_puzzle_before_it(
        self, tmp_path: Path
    ) -> None:
        # § 7.5: odd sheets are puzzles, even ones their solutions. What makes
        # a solution *that* puzzle's is geometric: the maze walls are the same
        # drawing, and the solution page adds a path on top. So the puzzle's
        # walls must all appear on the solution page.
        path = sheet(tmp_path, notebook(maze_section(2, "separate_page")))
        first = pdfread.page_count(path) - 4
        puzzle = {tuple(p) for p in pdfread.subpaths_um(path, first)}
        solution = {tuple(p) for p in pdfread.subpaths_um(path, first + 1)}
        assert puzzle and puzzle <= solution
        assert len(solution) > len(puzzle)

    def test_a_second_puzzle_is_a_different_maze(self, tmp_path: Path) -> None:
        path = sheet(tmp_path, notebook(maze_section(2, "separate_page")))
        first = pdfread.page_count(path) - 4
        assert pdfread.subpaths_um(path, first) != pdfread.subpaths_um(path, first + 2)

    def test_the_contents_still_names_the_page_the_next_section_starts_on(
        self, tmp_path: Path
    ) -> None:
        # `page_count` and `_section_starts` share one arithmetic, and doubling
        # a section must move both. The contents page prints the number, and the
        # section's own header answers `{section}` — two independent facts.
        definition = (
            "version: 1\n"
            "page: {format: a5, margin: 10mm}\n"
            'header: {height: 8mm, gap: 2mm, left: "{section}"}\n'
            'footer: {height: 8mm, gap: 2mm, right: "{page}"}\n'
            "generator: notebook\n"
            "sections:\n" + maze_section(2, "separate_page") + DOTS
        )
        path = sheet(tmp_path, definition)
        rows: dict[int, list] = {}
        for text in pdfread.texts_um(path, 0):
            rows.setdefault(round(text.y), []).append(text)
        entries = {}
        for line in rows.values():
            words = sorted(line, key=lambda t: t.x)
            if len(words) == 2 and words[1].content.isdigit():
                entries[words[0].content] = int(words[1].content)
        assert entries["Mazes"] == 2          # straight after the contents
        assert entries["Dots"] == 2 + 4       # four maze pages, then Dots


class TestBackMirrored:
    """§ 7.5: the solution goes on the back of the same sheet, mirrored about
    the **sheet's** vertical centre, so it shows through against the light."""

    def test_the_solution_page_is_the_mirror_of_the_puzzle(
        self, tmp_path: Path
    ) -> None:
        path = sheet(tmp_path, notebook(maze_section(1, "back_mirrored")))
        pages = pdfread.page_count(path)
        puzzle = pdfread.subpaths_um(path, pages - 2)
        solution = pdfread.subpaths_um(path, pages - 1)
        # A5 is 148 mm wide. Mirroring about the sheet's centre sends x to
        # 148000 - x, and the reference is the sheet, not the pattern area
        # (§ 7.5) — that is the physical turning edge.
        flipped = {
            tuple(sorted((round(148_000 - x), round(y)) for x, y in drawn))
            for drawn in solution
        }
        for wall in puzzle:
            assert tuple(sorted((round(x), round(y)) for x, y in wall)) in flipped

    def test_duplex_with_unequal_margins_is_refused_on_the_document_path_too(
        self, tmp_path: Path
    ) -> None:
        # § 7.5: the alternating gutter moves the pattern area between front
        # and back, and the solution would miss the maze by exactly that. The
        # blade path has refused this since M2; the document path must too.
        definition = (
            "version: 1\n"
            "page: {format: a5, margin: {top: 10mm, bottom: 10mm, "
            "inner: 20mm, outer: 8mm}, duplex: true}\n"
            "generator: notebook\n"
            "sections:\n" + maze_section(1, "back_mirrored")
        )
        with pytest.raises(DefinitionError) as excinfo:
            build(loads(definition, source="t"), PdfWriter(tmp_path / "never.pdf"))
        assert "back_mirrored" in str(excinfo.value)
