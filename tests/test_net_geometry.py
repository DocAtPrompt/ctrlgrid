"""Panels in, cut and fold out (§ 7.14).

The whole cut/fold distinction of a net is one rule: an edge two panels share is
a crease, an edge only one panel has is a cut. It falls out of the geometry
rather than being maintained by hand, which is what lets a new box style be a
list of panels instead of a traced outline.

Exact, because positions are integer micrometres (§ 3.3): two panels either
share an edge or they do not, and there is no tolerance to tune.
"""

from __future__ import annotations

import pytest

from ctrlgrid.generators.net_geometry import Panel, edges
from ctrlgrid.marks import Point


def rect(x0: int, y0: int, x1: int, y1: int, name: str = "p") -> Panel:
    return Panel(
        points=(Point(x0, y0), Point(x1, y0), Point(x1, y1), Point(x0, y1)), name=name
    )


def test_a_lone_panel_is_all_cut() -> None:
    cuts, folds = edges([rect(0, 0, 10_000, 5000)])
    assert len(cuts) == 4
    assert folds == []


def test_two_panels_sharing_an_edge_crease_along_it() -> None:
    cuts, folds = edges([rect(0, 0, 10_000, 5000, "base"), rect(0, 5000, 10_000, 8000, "wall")])
    assert len(folds) == 1
    assert len(cuts) == 6
    (a, b) = folds[0]
    assert {(a.x, a.y), (b.x, b.y)} == {(0, 5000), (10_000, 5000)}


def test_the_direction_an_edge_is_given_in_does_not_matter() -> None:
    # One panel walks clockwise, the other counter-clockwise: the shared edge
    # arrives reversed, and it is still one crease.
    clockwise = Panel(
        points=(Point(0, 0), Point(0, 5000), Point(10_000, 5000), Point(10_000, 0)), name="a"
    )
    counter = rect(0, 5000, 10_000, 8000, "b")
    _cuts, folds = edges([clockwise, counter])
    assert len(folds) == 1


def test_three_panels_on_one_edge_is_a_programming_error() -> None:
    # A sheet cannot fold three ways along one line. Not user input — a style
    # that produced this would be wrong — so it fails loudly at the seam.
    with pytest.raises(AssertionError):
        edges(
            [
                rect(0, 0, 10_000, 5000, "a"),
                rect(0, 5000, 10_000, 8000, "b"),
                rect(0, 5000, 10_000, 2000, "c"),
            ]
        )


def test_the_order_is_the_order_the_panels_were_given() -> None:
    # § 10.1: same input, same bytes — so the edges come out in a fixed order,
    # not a set's.
    panels = [rect(0, 0, 10_000, 5000, "base"), rect(0, 5000, 10_000, 8000, "wall")]
    first = edges(panels)
    second = edges(panels)
    assert first == second
    # The base's own edges come before the wall's, in the order it walks them.
    assert first[0][0] == (Point(0, 0), Point(10_000, 0))
