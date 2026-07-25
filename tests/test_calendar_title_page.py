"""Calendar title-page beautifications — § 7.12.

A background PNG over the colour (transparency shows the colour), fit
cover|contain, and independent opt-in header/footer on the title page.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image as PILImage
from pydantic import ValidationError

from ctrlgrid.errors import DefinitionError
from ctrlgrid.generators.calendar import TitlePage
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


def _png(path: Path, w: int, h: int, *, transparent: bool = False) -> Path:
    mode, color = ("RGBA", (200, 60, 60, 128)) if transparent else ("RGB", (200, 60, 60))
    PILImage.new(mode, (w, h), color).save(path)
    return path


def _title(tmp_path, **kw):
    return TitlePage.model_validate(
        {"title": "2026", **kw}, context={"base_dir": tmp_path}
    )


def test_defaults_are_conservative(tmp_path):
    tp = _title(tmp_path)
    assert tp.background_image is None
    assert tp.background_fit == "cover"
    assert tp.header is False and tp.footer is False


def test_background_image_is_resolved_and_validated(tmp_path):
    _png(tmp_path / "bg.png", 200, 100)
    tp = _title(tmp_path, background_image="bg.png")
    assert tp.background_image == str(tmp_path / "bg.png")


def test_missing_background_image_is_refused_before_page_one(tmp_path):
    # A missing PNG is refused at validation, before page one (§ 12). Like the
    # existing `logo` test (test_calendar.py), the DefinitionError raised inside
    # the validator propagates raw — pydantic only wraps ValueError/AssertionError.
    with pytest.raises((DefinitionError, ValidationError), match="no image file"):
        _title(tmp_path, background_image="nope.png")


def test_bad_background_fit_is_refused(tmp_path):
    _png(tmp_path / "bg.png", 200, 100)
    with pytest.raises(ValidationError):
        _title(tmp_path, background_image="bg.png", background_fit="stretch")


def test_header_footer_flags_take_booleans(tmp_path):
    tp = _title(tmp_path, header=True, footer=True)
    assert tp.header is True and tp.footer is True
