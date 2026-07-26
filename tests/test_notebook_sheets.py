"""A sheet plan inside a notebook section (§ 7.13, decision 55).

Decision 52 refused this and said why: § 7.13 did not settle what a per-section
sheet plan means. It does now — a section is a definition in miniature, so its
blade sees a page context of the section's own.
"""

from __future__ import annotations

from pathlib import Path

import pdfread

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
