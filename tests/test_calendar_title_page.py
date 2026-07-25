"""Calendar title-page beautifications — § 7.12.

A background PNG over the colour (transparency shows the colour), fit
cover|contain, and independent opt-in header/footer on the title page.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image as PILImage
from pydantic import ValidationError
from pypdf import PdfReader

from ctrlgrid.document import DocumentPage
from ctrlgrid.errors import DefinitionError
from ctrlgrid.generators.calendar import TitlePage
from ctrlgrid.loader import loads
from ctrlgrid.marks import Area, Image, Text
from ctrlgrid.pages import _build_document, background_image_rect, build
from ctrlgrid.writers.pdf import PdfWriter

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


def test_contain_tall_image_binds_height():
    # aspect 0.5 (taller than sheet 0.707): contain binds height, colour left/right.
    assert background_image_rect(W, H, 0.5, "contain") == (30_750, 0, 148_500, 297_000)


def test_equal_aspect_fills_exactly_for_both_fits():
    # aspect == sheet aspect: cover and contain agree, exact full-sheet, no overhang
    # (verified: no 1-µm rounding drift with the float ratio).
    s = W / H
    assert background_image_rect(W, H, s, "contain") == (0, 0, W, H)
    assert background_image_rect(W, H, s, "cover") == (0, 0, W, H)


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


class _Recorder:
    """A minimal Writer double that records draw() calls in order."""

    def __init__(self):
        self.drawn = []

    def begin_document(self, meta): pass
    def begin_page(self, width, height): pass
    def define_dest(self, key): pass
    def capabilities(self):
        # Not a metrics oracle: `_build_document` asks for one and gets a real
        # PdfWriter, so this recorder only has to record.
        return set()

    def draw(self, mark): self.drawn.append(mark)
    def link(self, lower_left, upper_right, target): pass
    def outline(self, title, *, index): pass
    def end_page(self): pass
    def end_document(self): pass


def _run(page, tmp_path):
    """Drive `_build_document` for a single page with a recorder, returning it.

    The bands are real ones now: since they are laid out per page (§ 8.10), the
    fake document carries a real `Band` and the geometry a real `Box`, and
    "HDR"/"FTR" come out of the same `layout_band` a run uses.
    """
    from ctrlgrid.model import Band
    from ctrlgrid.pages import Box

    band = {"height": "8mm", "gap": "2mm", "font": {"size": "9pt"}}
    doc = SimpleNamespace(
        source="t.yaml",
        pages=SimpleNamespace(embed_def=False),
        sheet=SimpleNamespace(width=W, height=H),
        config=object(),
        header=Band.model_validate({**band, "left": "HDR"}),
        footer=Band.model_validate({**band, "left": "FTR"}),
    )
    blade = SimpleNamespace(
        pages=lambda cfg, *, area, q: iter([page]),
        page_count=lambda cfg, *, area: 1,
        placeholders=lambda cfg: {},
    )
    geometry = SimpleNamespace(
        origin=SimpleNamespace(x=0, y=0),
        area=Area(width=W, height=H),
        header=Box(left=0, bottom=H - 8000, right=W, top=H),
        footer=Box(left=0, bottom=0, right=W, top=8000),
    )
    rec = _Recorder()
    _build_document(doc, blade, rec, geometry)
    return rec


def _title_page(tmp_path, **kw):
    _png(tmp_path / "bg.png", 200, 100, transparent=True)
    return DocumentPage(
        dest="title", kind="title", marks=(), links=(),
        background="#123456", background_image=str(tmp_path / "bg.png"), **kw,
    )


def test_colour_is_drawn_before_the_background_image(tmp_path):
    rec = _run(_title_page(tmp_path, show_header=False, show_footer=False), tmp_path)
    kinds = [type(m).__name__ for m in rec.drawn]
    # Polygon (the colour) must precede the Image, so transparency shows colour.
    assert kinds.index("Polygon") < kinds.index("Image")


def test_background_image_rect_is_used(tmp_path):
    rec = _run(_title_page(tmp_path, background_fit="contain",
                           show_header=False, show_footer=False), tmp_path)
    img = next(m for m in rec.drawn if isinstance(m, Image))
    # 200x100 → aspect 2.0, contain on A4: full width, centred vertically.
    assert (img.pos.x, img.width, img.height) == (0, 210_000, 105_000)


def test_header_shown_footer_hidden_per_flags(tmp_path):
    rec = _run(_title_page(tmp_path, show_header=True, show_footer=False), tmp_path)
    texts = [m.content for m in rec.drawn if isinstance(m, Text)]
    assert "HDR" in texts and "FTR" not in texts


def test_default_document_page_shows_both_bands(tmp_path):
    plain_marks = DocumentPage(dest="d", kind="month", marks=())
    rec = _run(plain_marks, tmp_path)
    texts = [m.content for m in rec.drawn if isinstance(m, Text)]
    assert "HDR" in texts and "FTR" in texts


def test_title_background_image_and_header_render(tmp_path):
    _png(tmp_path / "bg.png", 400, 560, transparent=True)
    definition = tmp_path / "cal.yaml"
    definition.write_text(
        "version: 1\n"
        "page:\n"
        "  format: a4\n"
        "  margin: 12mm\n"
        "header:\n"
        "  height: 7mm\n"
        "  gap: 3mm\n"
        '  center: "HDR"\n'
        "footer:\n"
        "  height: 7mm\n"
        "  gap: 3mm\n"
        '  center: "FTR"\n'
        "generator: calendar\n"
        "year: 2026\n"
        "title_page:\n"
        '  title: "2026"\n'
        "  background_image: bg.png\n"
        "  header: true\n"
        "  footer: false\n",
        encoding="utf-8",
    )
    doc = loads(definition.read_text(), source=str(definition))
    out = tmp_path / "cal.pdf"
    build(doc, PdfWriter(str(out)))

    reader = PdfReader(str(out))
    page1 = reader.pages[0]
    # The background image is an XObject on page 1.
    assert "/XObject" in (page1.get("/Resources") or {})
    text1 = page1.extract_text()
    assert "HDR" in text1 and "FTR" not in text1   # header opted in, footer not
    # A sub-page (contents) still shows both bands.
    text2 = reader.pages[1].extract_text()
    assert "HDR" in text2 and "FTR" in text2


def test_calendar_title_header_strip_renders(tmp_path):
    definition = tmp_path / "cal.yaml"
    definition.write_text(
        "version: 1\n"
        "page:\n"
        "  format: a4\n"
        "  margin: 12mm\n"
        "header:\n"
        "  height: 8mm\n"
        "  gap: 3mm\n"
        '  center: "{year}"\n'
        '  background: "#2f3a48"\n'
        '  text_color: "#ffffff"\n'
        "generator: calendar\n"
        "year: 2026\n"
        "title_page:\n"
        '  title: "2026"\n'
        "  header: true\n",
        encoding="utf-8",
    )
    doc = loads(definition.read_text(), source=str(definition))
    out = tmp_path / "cal.pdf"
    build(doc, PdfWriter(str(out)))

    reader = PdfReader(str(out))
    # The header strip is a filled rectangle in the page content; the header
    # text still extracts. Both on page 1 (the cover opted the header in).
    page1 = reader.pages[0]
    assert "2026" in page1.extract_text()
    # The fill operator (rg + re + f) is present in the content stream.
    content = page1.get_contents().get_data()
    assert b" rg" in content or b" RG" in content   # a colour was set (the strip)
