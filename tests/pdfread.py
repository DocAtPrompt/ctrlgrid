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
