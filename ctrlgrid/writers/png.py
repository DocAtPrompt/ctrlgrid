"""The PNG writer — the only module that may import Pillow.

That confinement is the same rule reportlab lives under (§ 3.3), and
`tests/test_architecture.py` enforces it: the mark vocabulary is the contract,
and a second writer proves it by needing nothing from the first.

§ 10.4 asks for one thing — rasterise at the device's exact resolution — and
sends the thin-line and uneven-grid questions to the media check (§ 12.1),
which already answers them for both output paths. So this module is short: the
same marks in, pixels out, and the single vertical flip § 3.5 promised, because
PDF counts y upward and a raster counts it downward.

**One device pixel is one image pixel.** No supersampling: § 10.4 says *exact*
resolution, and a template synced to a pad has to land on its real pixels, not
on a smoothed average of them. Evenness is what `snap: pixel` (§ 8.3.1) is for.

**Text is not drawn here.** The standard PDF fonts have fixed metrics but no
file (§ 10.3), and Pillow needs a file to draw a glyph. Rather than substitute a
font nobody chose, the writer declares it cannot do text (§ 10.2) and the
pre-flight refuses a run that would put text on a PNG, naming the way out. The
pad templates this path exists for carry no text.
"""

from __future__ import annotations

import math
from pathlib import Path

from PIL import Image as PilImage
from PIL import ImageDraw

from ctrlgrid.errors import CtrlGridError
from ctrlgrid.marks import Arc, Dot, Image, Mark, Polygon, Segment, Text, Um
from ctrlgrid.writers import DocumentMeta

WHITE = (255, 255, 255)


class PngWriter:
    """Seam 3 for PNG (§ 3.6): marks in, pixels out, one file per page.

    `dpi` is the medium's resolution — a device's density or a format's
    `assumed_dpi` — and `sheets` how many physical pages the run will produce,
    so the files can be numbered from the first without buffering them all.
    """

    def __init__(self, path: Path | str, *, dpi: int = 600, sheets: int = 1):
        self.path = Path(path)
        self.dpi = dpi
        self.sheets = sheets
        self._image: PilImage.Image | None = None
        self._draw: ImageDraw.ImageDraw | None = None
        self._height_px = 0
        self._index = 0

    # ---------------------------------------------------------------- queries

    def capabilities(self) -> set[str]:
        """What a raster of vector marks can do (§ 10.2).

        Deliberately without `text`: see the module docstring. The pre-flight
        checks a run's marks against this set and refuses what is missing.
        """
        return {"vector", "color", "opacity", "arc", "polygon", "image_png"}

    def text_width(self, content: str, *, family: str, size: Um) -> Um:  # pragma: no cover
        raise CtrlGridError(_NO_TEXT)

    def text_metrics(self, *, family: str, size: Um) -> tuple[Um, Um]:  # pragma: no cover
        raise CtrlGridError(_NO_TEXT)

    def missing_glyphs(self, content: str, *, family: str) -> list[str]:  # pragma: no cover
        raise CtrlGridError(_NO_TEXT)

    # ---------------------------------------------------------------- writing

    def begin_document(self, meta: DocumentMeta) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def begin_page(self, width: Um, height: Um) -> None:
        self._height_px = self._px(height)
        self._image = PilImage.new("RGB", (self._px(width), self._height_px), WHITE)
        self._draw = ImageDraw.Draw(self._image, "RGBA")

    def draw(self, mark: Mark) -> None:
        match mark:
            case Segment():
                self._segment(mark)
            case Dot():
                self._dot(mark)
            case Arc():
                self._arc(mark)
            case Polygon():
                self._polygon(mark)
            case Image():
                self._image_mark(mark)
            case Text():
                # Refused in the pre-flight; a mark reaching here is a bug, not
                # user input, so it is a hard error rather than a definition one.
                raise CtrlGridError(_NO_TEXT)

    def outline(self, title: str, *, index: int) -> None:
        """PNG has no bookmarks; a data-driven run just gets numbered files."""

    def end_page(self) -> None:
        assert self._image is not None
        self._index += 1
        self._image.save(self._page_path(), optimize=True)
        self._image = self._draw = None

    def end_document(self) -> None:
        pass

    # ------------------------------------------------------------- primitives

    @property
    def _canvas(self) -> ImageDraw.ImageDraw:
        if self._draw is None:
            raise CtrlGridError("begin_page must be called before drawing")
        return self._draw

    def _segment(self, mark: Segment) -> None:
        width = max(1, self._px(_mm_um(mark.weight)))
        colour = _rgba(mark.color, mark.opacity)
        for start, end in _dash_runs(mark):
            self._canvas.line([self._pt(start), self._pt(end)], fill=colour, width=width)
        if mark.cap == "round" and width > 1:
            # A round cap on a raster is a disc at each end — this is also how a
            # `dotted` family draws its dots (§ 7.1).
            radius = width / 2
            for point in (mark.start, mark.end):
                x, y = self._pt(point)
                self._canvas.ellipse(
                    [x - radius, y - radius, x + radius, y + radius], fill=colour
                )

    def _dot(self, mark: Dot) -> None:
        radius = self._px(_mm_um(mark.diameter)) / 2
        x, y = self._pt(mark.pos)
        self._canvas.ellipse(
            [x - radius, y - radius, x + radius, y + radius],
            fill=_rgba(mark.color, mark.opacity),
        )

    def _arc(self, mark: Arc) -> None:
        x, y = self._pt(mark.center)
        radius = self._px(mark.radius)
        box = [x - radius, y - radius, x + radius, y + radius]
        width = max(1, self._px(_mm_um(mark.weight)))
        colour = _rgba(mark.color, mark.opacity)
        if mark.sweep >= 360.0:
            self._canvas.ellipse(box, outline=colour, width=width)
            return
        # y counts downward on a raster, so a mathematically positive angle runs
        # clockwise here — the sweep is measured from the negated start.
        start = -(mark.start_angle + mark.sweep)
        end = -mark.start_angle
        self._canvas.arc(box, start, end, fill=colour, width=width)

    def _polygon(self, mark: Polygon) -> None:
        points = [self._pt(point) for point in mark.points]
        fill = _rgba(mark.fill_color, mark.opacity) if mark.fill_color else None
        if fill is not None:
            self._canvas.polygon(points, fill=fill)
        outline = _rgba(mark.color, mark.opacity)
        width = max(1, self._px(_mm_um(mark.weight)))
        ring = points + [points[0]] if mark.closed else points
        if mark.weight > 0:
            self._canvas.line(ring, fill=outline, width=width)

    def _image_mark(self, mark: Image) -> None:
        assert self._image is not None
        with PilImage.open(mark.source) as source:
            box = source.convert("RGBA").resize(
                (max(1, self._px(mark.width)), max(1, self._px(mark.height)))
            )
        x, y = self._pt(mark.pos)
        # `pos` is the bottom-left of the image, and the raster origin is top,
        # so the paste corner is one image height up the screen.
        self._image.paste(box, (round(x), round(y) - box.height), box)

    # ------------------------------------------------------------- geometry

    def _px(self, um: Um) -> int:
        """Micrometres to whole image pixels, one per device pixel (§ 10.4)."""
        return round(um * self.dpi / 25400)

    def _pt(self, point) -> tuple[float, float]:
        """A sheet point (y-up, µm) to an image point (y-down, px) — the flip."""
        return (point.x * self.dpi / 25400, self._height_px - point.y * self.dpi / 25400)

    def _page_path(self) -> Path:
        if self.sheets <= 1:
            return self.path
        return self.path.with_name(f"{self.path.stem}-{self._index}{self.path.suffix}")


_NO_TEXT = (
    "the PNG writer cannot draw text: the standard PDF fonts have fixed metrics "
    "but no file, and a raster needs a file to draw a glyph (§ 10.3, § 10.4). Name a "
    "font file (`font: {file: ...}`) or leave the text off, or output PDF instead"
)


def _mm_um(mm: float) -> Um:
    return round(mm * 1000)


def _rgba(hex_colour: str, opacity: float) -> tuple[int, int, int, int]:
    r, g, b = (int(hex_colour[i : i + 2], 16) for i in (1, 3, 5))
    return (r, g, b, round(255 * opacity))


def _dash_runs(mark: Segment):
    """The visible pieces of a segment: the whole line, or its dash on-runs."""
    if not mark.dash or not any(mark.dash):
        yield mark.start, mark.end
        return

    length = math.dist((mark.start.x, mark.start.y), (mark.end.x, mark.end.y))
    if length == 0:
        yield mark.start, mark.end
        return
    ux = (mark.end.x - mark.start.x) / length
    uy = (mark.end.y - mark.start.y) / length
    pattern = [value * 1000 for value in mark.dash]  # mm to µm

    from ctrlgrid.marks import Point

    position = 0.0
    index = 0
    on = True
    while position < length:
        run = pattern[index % len(pattern)]
        end = min(position + run, length)
        if on and run > 0:
            yield (
                Point(round(mark.start.x + ux * position), round(mark.start.y + uy * position)),
                Point(round(mark.start.x + ux * end), round(mark.start.y + uy * end)),
            )
        position = end
        index += 1
        on = not on
