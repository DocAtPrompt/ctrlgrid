"""Calendar title-page beautifications — § 7.12.

A background PNG over the colour (transparency shows the colour), fit
cover|contain, and independent opt-in header/footer on the title page.
"""

from __future__ import annotations

import pytest

from ctrlgrid.pages import background_image_rect

# A4 portrait in µm.
W, H = 210_000, 297_000


def test_contain_square_fits_inside_and_centres():
    # aspect 1.0 >= sheet aspect (0.707): contain binds width.
    assert background_image_rect(W, H, 1.0, "contain") == (0, 43_500, 210_000, 210_000)


def test_cover_square_fills_and_overhangs():
    # aspect 1.0: cover binds height, overhangs left/right (negative x).
    assert background_image_rect(W, H, 1.0, "cover") == (-43_500, 0, 297_000, 297_000)


def test_contain_wide_image_binds_width():
    # aspect 2.0 (wider than sheet): contain → full width, short height.
    assert background_image_rect(W, H, 2.0, "contain") == (0, 96_000, 210_000, 105_000)


def test_cover_tall_image_binds_width():
    # aspect 0.5 (taller than sheet 0.707): cover binds width, overhangs top/bottom.
    x, y, w, h = background_image_rect(W, H, 0.5, "cover")
    assert (x, w) == (0, 210_000)
    assert h == 420_000 and y == round((H - 420_000) / 2)
