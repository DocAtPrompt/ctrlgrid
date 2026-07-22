"""Image sources for header and footer fields (§ 5.2, § 13).

Only two facts about an image ever leave this module: how many pixels wide and
how many tall. That is enough, because the *physical* height comes from the
definition (`height: 8mm`) and the width follows from the file's proportions —
a logo squeezed into a shape it does not have is the one outcome nobody wants.

**PNG only in v1** (§ 13). SVG is the most fragile dependency imaginable —
"SVG" runs from two paths to filters, gradients and clip paths — so a `.svg` is
refused by name rather than reported as a broken file.

Reading the header by hand rather than through an imaging library is not
frugality: `PIL` belongs to the PNG writer alone (§ 3.3, and
`tests/test_architecture.py` enforces it), and a PNG's size sits in the first
24 bytes of the file. Nothing here decodes pixels.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from ctrlgrid.errors import DefinitionError

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


@dataclass(frozen=True, slots=True)
class ImageFile:
    """What the band layout needs to know about an image before placing it."""

    path: Path
    width_px: int
    height_px: int

    @property
    def aspect(self) -> float:
        """Width over height. The one number that turns `height:` into a box."""
        return self.width_px / self.height_px


def load_image(raw: str, *, field: str | None = None) -> ImageFile:
    """Read a PNG's dimensions, refusing anything this version cannot use."""
    try:
        return _load(str(Path(raw).expanduser()))
    except DefinitionError as error:
        raise (error.at(field=field) if field else error) from None


@lru_cache(maxsize=64)
def _load(path_text: str) -> ImageFile:
    path = Path(path_text)
    if not path.is_file():
        raise DefinitionError(
            f"no image file at {path}. Paths are resolved against the definition file, "
            "so a logo travels with the definition that uses it (§ 5.2)"
        )

    data = path.read_bytes()[:24]
    if not data.startswith(PNG_SIGNATURE):
        if path.suffix.lower() == ".svg":
            raise DefinitionError(
                f"{path.name} is an SVG, and v1 takes PNG only (§ 13). 'SVG' ranges from "
                "two paths to filters, gradients and clip paths, and a renderer that "
                "handles some of it would produce sheets that are almost right. "
                "Export the logo as PNG at the size you need"
            )
        raise DefinitionError(
            f"{path.name} is not a PNG — its first bytes are not the PNG signature. "
            "v1 takes PNG only (§ 13); the file extension is not what decides"
        )

    # IHDR is required by the format to be the first chunk: eight bytes of
    # signature, four of length, four of type, then width and height.
    width = int.from_bytes(data[16:20], "big")
    height = int.from_bytes(data[20:24], "big")
    if width <= 0 or height <= 0:
        raise DefinitionError(f"{path.name} declares a size of {width}x{height} pixels")
    return ImageFile(path=path.resolve(), width_px=width, height_px=height)
