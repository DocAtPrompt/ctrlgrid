"""Reading generated PDFs back — the only honest way to check the promise.

§ 13.2: golden comparisons check *parsed geometry*, never bytes, so that a
reportlab update cannot break the suite. These helpers turn a page's content
stream back into micrometres so a test can assert against the numbers the
definition asked for.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from pypdf import PdfReader

PT_PER_UM = 72 / 25400


def um(points: float) -> float:
    """Points back to micrometres."""
    return points / PT_PER_UM


@dataclass(frozen=True)
class DrawnLine:
    """A stroked straight line, in micrometres and millimetres."""

    x1: float
    y1: float
    x2: float
    y2: float
    width_mm: float

    @property
    def is_horizontal(self) -> bool:
        return abs(self.y1 - self.y2) < 1.0

    @property
    def is_vertical(self) -> bool:
        return abs(self.x1 - self.x2) < 1.0


# reportlab writes ".15", not "0.15", so the leading digit is optional.
_NUMBER = r"(-?(?:\d+\.?\d*|\.\d+))"
_MOVE_LINE_STROKE = re.compile(
    rf"{_NUMBER} {_NUMBER} m\s+{_NUMBER} {_NUMBER} l\s+S".encode(),
)
_WIDTH = re.compile(rf"{_NUMBER} w".encode())


def media_box_um(path: Path, page: int = 0) -> tuple[float, float]:
    box = PdfReader(str(path)).pages[page].mediabox
    return um(float(box.width)), um(float(box.height))


def page_count(path: Path) -> int:
    return len(PdfReader(str(path)).pages)


def lines_um(path: Path, page: int = 0) -> list[DrawnLine]:
    """Every stroked line on a page, in micrometres, in drawing order."""
    stream = PdfReader(str(path)).pages[page].get_contents().get_data()
    lines: list[DrawnLine] = []
    width_mm = 0.0
    position = 0
    while True:
        stroke = _MOVE_LINE_STROKE.search(stream, position)
        if stroke is None:
            return lines
        for width in _WIDTH.finditer(stream, position, stroke.start()):
            width_mm = float(width.group(1)) / PT_PER_UM / 1000
        x1, y1, x2, y2 = (float(value) for value in stroke.groups())
        lines.append(DrawnLine(um(x1), um(y1), um(x2), um(y2), width_mm))
        position = stroke.end()


_DASH = re.compile(rb"\[([\d\.\s]*)\] *(-?[\d\.]+) d")


def dash_arrays(path: Path, page: int = 0) -> list[list[float]]:
    """Every non-empty dash array set on a page, in points, in drawing order.

    `[] 0 d` — the reset back to a solid line — is not one: reportlab writes it
    for every stroke, and counting it would say a solid family "has a dash".
    """
    stream = PdfReader(str(path)).pages[page].get_contents().get_data()
    arrays = [
        [float(value) for value in match.group(1).split()]
        for match in _DASH.finditer(stream)
    ]
    return [array for array in arrays if array]


def text_on(path: Path, page: int = 0) -> str:
    return PdfReader(str(path)).pages[page].extract_text()


_TOKEN = re.compile(rb"(-?(?:\d+\.?\d*|\.\d+))|([A-Za-z']+)")


def subpaths_um(path: Path, page: int = 0) -> list[list[tuple[float, float]]]:
    """Every subpath on a page as its **on-curve** points, in micrometres.

    A segment comes back as two points, a polygon as its vertices, and a circle
    as the five points reportlab's four Bézier quarters begin and end at. That is
    enough to measure what a definition declares — an edge length, a radius, a
    rotation — without the test knowing how the writer chose to draw it.

    Deliberately ignores the Bézier control points: they are the writer's
    business, and a test that asserted on them would be checking reportlab.
    """
    stream = PdfReader(str(path)).pages[page].get_contents().get_data()
    paths: list[list[tuple[float, float]]] = []
    current: list[tuple[float, float]] = []
    numbers: list[float] = []
    for match in _TOKEN.finditer(stream):
        number, operator = match.group(1), match.group(2)
        if number is not None:
            numbers.append(float(number))
            continue
        op = operator.decode()
        if op == "m":
            if len(current) > 1:
                paths.append(current)
            current = [(um(numbers[-2]), um(numbers[-1]))] if len(numbers) >= 2 else []
        elif (op == "l" and len(numbers) >= 2) or (op == "c" and len(numbers) >= 6):
            # A `c`'s last pair is its on-curve endpoint; the four before it are
            # control points and belong to the writer, not to the geometry.
            current.append((um(numbers[-2]), um(numbers[-1])))
        elif op in ("S", "f", "B", "b", "s", "n"):
            if len(current) > 1:
                paths.append(current)
            current = []
        numbers = []
    if len(current) > 1:
        paths.append(current)
    return paths


def length_um(a: tuple[float, float], b: tuple[float, float]) -> float:
    return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5


def circle_um(points: list[tuple[float, float]]) -> tuple[float, float, float]:
    """Centre and radius of a subpath that is a circle, from its on-curve points.

    Fitted from the extremes rather than from any one quarter, so a rounding in
    the writer's Bézier endpoints cannot decide the answer alone.
    """
    xs = [x for x, _ in points]
    ys = [y for _, y in points]
    cx = (min(xs) + max(xs)) / 2
    cy = (min(ys) + max(ys)) / 2
    radius = sum(length_um((cx, cy), point) for point in points) / len(points)
    return cx, cy, radius
