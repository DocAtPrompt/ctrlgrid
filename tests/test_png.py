"""The PNG writer (§ 10.4) — rasterising at exact device resolution.

§ 10.4 is one paragraph: rasterise at the device's resolution, and let the
media check (§ 12.1) — not the writer — worry about thin lines and uneven
grids, because that check applies to the PDF path just the same. So the PNG
writer is a second implementation of seam 3 (§ 3.6): the same marks in, pixels
out instead of vector operators, and the vertical flip § 3.5 promised, done
once.

Its one real limit is text. The standard PDF fonts have fixed *metrics* but no
*file* (§ 10.3), and Pillow needs a file to draw a glyph. So the PNG writer
declares it cannot render text, and the pre-flight refuses a run that would put
text on a PNG — naming the way out, a font file — exactly as § 10.2's
capability model prescribes. The pad templates § 10.4 exists for — dot grids,
line grids — carry no text, so this is a limit at the edge, not the centre.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ctrlgrid.errors import CtrlGridError, DefinitionError
from ctrlgrid.loader import loads

DOTS = (
    "version: 1\n"
    "page:\n  device: remarkable-paper-pro\n"
    "generator: dots\n"
    "grid:\n  x: {base_spacing: 5mm}\n  y: {base_spacing: 5mm}\n"
    "base_size: 0.5mm\n"
    "color: '#000000'\n"
)


def render(tmp_path: Path, definition: str, name: str = "out.png", **overrides):
    from ctrlgrid.cli import _writer_for

    document = loads(definition, overrides or None, source="test")
    path = tmp_path / name
    from ctrlgrid.pages import build

    build(document, _writer_for(path, document))
    return path


class TestTheImage:
    def test_it_is_the_devices_exact_pixel_size(self, tmp_path: Path) -> None:
        from PIL import Image

        # § 9.2: the Paper Pro is 1620 x 2160 px. A PNG for it is exactly that.
        path = render(tmp_path, DOTS)
        with Image.open(path) as image:
            assert image.size == (1620, 2160)

    def test_the_dots_actually_reach_the_pixels(self, tmp_path: Path) -> None:
        from PIL import Image

        path = render(tmp_path, DOTS)
        with Image.open(path) as image:
            colours = image.convert("RGB").getcolors(maxcolors=1_000_000)
        # White background and black dots at least.
        present = {colour for _, colour in colours}
        assert (255, 255, 255) in present
        assert any(sum(colour) < 60 for colour in present)

    def test_the_origin_is_flipped_once(self, tmp_path: Path) -> None:
        from PIL import Image

        # § 3.5: PDF is y-up, PNG is y-down. A family that only draws near the
        # bottom of the sheet must appear near the bottom rows of the image.
        definition = (
            "version: 1\npage:\n  device: remarkable-paper-pro\n"
            "generator: lines\nfamilies:\n"
            "  - {direction: horizontal, base_spacing: 5mm, base_weight: 0.6pt, "
            "count: 3, extent: {end: 15mm}}\n"
        )
        path = render(tmp_path, definition)
        with Image.open(path) as image:
            pixels = image.convert("L").load()
            width, height = image.size
            top_dark = sum(pixels[x, y] < 128 for x in range(0, width, 20)
                           for y in range(0, height // 4))
            bottom_dark = sum(pixels[x, y] < 128 for x in range(0, width, 20)
                              for y in range(3 * height // 4, height))
        # The three lines sit in the bottom 15 mm, so the bottom quarter is
        # darker than the top quarter.
        assert bottom_dark > top_dark


class TestPagesAreSeparateFiles:
    def test_one_page_keeps_the_plain_name(self, tmp_path: Path) -> None:
        path = render(tmp_path, DOTS)
        assert path.exists()

    def test_several_pages_are_numbered(self, tmp_path: Path) -> None:
        render(tmp_path, DOTS, name="sheet.png", pages=3)
        names = sorted(p.name for p in tmp_path.glob("sheet*.png"))
        assert names == ["sheet-1.png", "sheet-2.png", "sheet-3.png"]


class TestTextIsRefused:
    def test_a_header_on_png_is_refused_with_the_way_out(self, tmp_path: Path) -> None:
        # § 10.2, § 10.3: the standard fonts have no file, so the PNG writer
        # cannot draw them — and it says so before rendering, not mid-file.
        definition = (
            "version: 1\npage:\n  device: remarkable-paper-pro\n"
            "header:\n  height: 10mm\n  center: 'Notes'\n"
            "generator: dots\n"
            "grid:\n  x: {base_spacing: 5mm}\n  y: {base_spacing: 5mm}\n"
            "base_size: 0.5mm\n"
        )
        with pytest.raises((DefinitionError, CtrlGridError)) as excinfo:
            render(tmp_path, definition)
        message = str(excinfo.value)
        assert "text" in message.lower() and "png" in message.lower()

    def test_grid_labels_on_png_are_refused(self, tmp_path: Path) -> None:
        definition = (
            "version: 1\npage:\n  device: remarkable-paper-pro\n"
            "generator: grid\ncells: {x: 8, y: 8}\n"
            "labels:\n  columns: 'A'\n"
        )
        with pytest.raises((DefinitionError, CtrlGridError)):
            render(tmp_path, definition)

    def test_nothing_is_written_when_text_is_refused(self, tmp_path: Path) -> None:
        definition = (
            "version: 1\npage:\n  device: remarkable-paper-pro\n"
            "header:\n  height: 10mm\n  center: 'Notes'\n"
            "generator: dots\n"
            "grid:\n  x: {base_spacing: 5mm}\n  y: {base_spacing: 5mm}\n"
            "base_size: 0.5mm\n"
        )
        with pytest.raises((DefinitionError, CtrlGridError)):
            render(tmp_path, definition, name="never.png")
        assert not (tmp_path / "never.png").exists()

    def test_a_pattern_without_text_is_fine(self, tmp_path: Path) -> None:
        assert render(tmp_path, DOTS).exists()


class TestReproducibility:
    def test_two_runs_produce_identical_bytes(self, tmp_path: Path) -> None:
        # § 10.1's promise holds for the raster too: no timestamps.
        first = render(tmp_path, DOTS, name="a.png")
        second = render(tmp_path, DOTS, name="b.png")
        assert first.read_bytes() == second.read_bytes()


class TestPaperUsesAssumedDpi:
    def test_a_paper_png_rasters_at_assumed_dpi(self, tmp_path: Path) -> None:
        from PIL import Image

        # A6 at 600 dpi: 105/25.4*600 = 2480 px wide.
        definition = (
            "version: 1\npage:\n  format: a6\n  margin: 0mm\n"
            "generator: lines\nfamilies:\n"
            "  - {direction: horizontal, base_spacing: 5mm, base_weight: 0.6pt}\n"
        )
        path = render(tmp_path, definition)
        with Image.open(path) as image:
            assert image.size[0] == pytest.approx(2480, abs=2)


class TestSkipUnsupported:
    """§ 10.2: leaving a feature out and carrying on — but only as the user's
    explicit decision, and never silently.

    The name is the spec's own: `--anyway` beside § 11.3's `--force` would be
    two flags that both read "do it regardless" and do different things.
    """

    HEADER = (
        "version: 1\npage:\n  device: remarkable-paper-pro\n"
        "header:\n  height: 10mm\n  center: 'Notes'\n"
        "generator: dots\n"
        "grid:\n  x: {base_spacing: 5mm}\n  y: {base_spacing: 5mm}\n"
        "base_size: 0.5mm\n"
    )

    def test_without_the_flag_the_run_is_still_refused(self, tmp_path: Path) -> None:
        with pytest.raises((DefinitionError, CtrlGridError)):
            render(tmp_path, self.HEADER)

    def test_with_the_flag_the_png_is_written_without_the_text(self, tmp_path: Path) -> None:
        path = render(tmp_path, self.HEADER, skip_unsupported=True)
        assert path.exists()

    def test_it_says_what_it_left_out(self, tmp_path: Path) -> None:
        from ctrlgrid.pages import preflight
        from ctrlgrid.writers.png import PngWriter

        document = loads(self.HEADER, {"skip_unsupported": True}, source="test")
        geometry, _contexts, _bands, _cover = preflight(
            document, PngWriter(tmp_path / "out.png")
        )
        notices = list(document.notices) + list(geometry.notices)
        assert any("text" in note and "skip" in note.lower() for note in notices)

    def test_the_pattern_itself_still_comes_out(self, tmp_path: Path) -> None:
        from PIL import Image

        path = render(tmp_path, self.HEADER, skip_unsupported=True)
        with Image.open(path) as image:
            assert image.size == (1620, 2160)
            assert image.convert("L").getextrema()[0] < 200   # the dots are there

    def test_on_pdf_the_flag_changes_nothing(self, tmp_path: Path) -> None:
        # Everything is supported there, so there is nothing to leave out — and
        # a flag that quietly changed a supported run would be the worst of both.
        definition = (
            "version: 1\npage: {format: a4}\n"
            "header:\n  height: 10mm\n  center: 'Notes'\n"
            "generator: dots\ngrid:\n  x: {base_spacing: 5mm}\n  y: {base_spacing: 5mm}\n"
            "base_size: 0.5mm\n"
        )
        plain = render(tmp_path, definition, name="a.pdf")
        skipped = render(tmp_path, definition, name="b.pdf", skip_unsupported=True)
        assert plain.read_bytes() == skipped.read_bytes()

    def test_a_document_on_png_leaves_out_its_links(self, tmp_path: Path) -> None:
        # A calendar needs `link` and `text`; with the flag it becomes a set of
        # plain pages rather than a refusal.
        definition = (
            "version: 1\npage:\n  device: remarkable-2\n  orientation: landscape\n"
            "  margin: 0mm\n"
            "generator: calendar\nyear: 2026\n"
        )
        path = render(tmp_path, definition, name="cal.png", skip_unsupported=True)
        assert path.exists() or (tmp_path / "cal-1.png").exists()
