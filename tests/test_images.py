"""Images in header and footer (§ 5.2, § 8.9, § 12 point 13).

`left: { image: "logo.png", height: 8mm }`. The height comes from the
definition and the width from the file's own proportions — the one thing that
must never happen is a logo squeezed into a shape it does not have.

**A logo is never cropped**: § 8.9 gives text an explicit `cut: true` and
withholds it from images, so an image either fits or the run is refused. And
§ 12 point 13 measures the band's height against every image before page one,
because § 8.4 fixes band heights in the definition and refuses to derive them
from content.

PNG only in v1 (§ 13), with a message that names SVG rather than calling it an
unknown file type.
"""

from __future__ import annotations

import zlib
from pathlib import Path

import pdfread
import pytest

from ctrlgrid.errors import DefinitionError
from ctrlgrid.images import load_image
from ctrlgrid.loader import load
from ctrlgrid.marks import Image
from ctrlgrid.pages import build, preflight
from ctrlgrid.writers.pdf import PdfWriter

Q = PdfWriter("unused.pdf")


def png(path: Path, width: int = 40, height: int = 10) -> Path:
    """A valid PNG of a given pixel size, written without an image library."""

    def chunk(kind: bytes, payload: bytes) -> bytes:
        return (
            len(payload).to_bytes(4, "big")
            + kind
            + payload
            + zlib.crc32(kind + payload).to_bytes(4, "big")
        )

    header = width.to_bytes(4, "big") + height.to_bytes(4, "big") + bytes([8, 2, 0, 0, 0])
    rows = b"".join(b"\x00" + b"\x80\x80\x80" * width for _ in range(height))
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(rows))
        + chunk(b"IEND", b"")
    )
    return path


def document(tmp_path: Path, field: str, band: str = "header", height: str = "12mm"):
    text = (
        "version: 1\n"
        f"{band}:\n"
        f"  height: {height}\n"
        f"  left: {field}\n"
        "generator: lines\n"
        "families:\n"
        "  - {direction: horizontal, base_spacing: 10mm}\n"
    )
    (tmp_path / "def.yaml").write_text(text, encoding="utf-8")
    return load(tmp_path / "def.yaml")


class TestReadingThePng:
    def test_the_pixel_size_comes_out_of_the_header(self, tmp_path: Path) -> None:
        image = load_image(str(png(tmp_path / "logo.png", 40, 10)))
        assert (image.width_px, image.height_px) == (40, 10)

    def test_the_aspect_is_what_the_layout_needs(self, tmp_path: Path) -> None:
        assert load_image(str(png(tmp_path / "logo.png", 40, 10))).aspect == 4.0

    def test_a_missing_file_names_the_path(self, tmp_path: Path) -> None:
        with pytest.raises(DefinitionError) as excinfo:
            load_image(str(tmp_path / "nowhere.png"))
        assert "nowhere.png" in str(excinfo.value)

    def test_an_svg_is_refused_by_name(self, tmp_path: Path) -> None:
        # § 13: SVG is the most fragile dependency imaginable, so v1 says so
        # rather than pretending the file is broken.
        path = tmp_path / "logo.svg"
        path.write_text("<svg/>", encoding="utf-8")
        with pytest.raises(DefinitionError) as excinfo:
            load_image(str(path))
        assert "SVG" in str(excinfo.value).upper() and "PNG" in str(excinfo.value)

    def test_something_that_is_not_a_png_says_so(self, tmp_path: Path) -> None:
        path = tmp_path / "logo.png"
        path.write_bytes(b"GIF89a not really")
        with pytest.raises(DefinitionError) as excinfo:
            load_image(str(path))
        assert "PNG" in str(excinfo.value)


class TestInTheBand:
    def marks(self, tmp_path: Path, **kwargs) -> list:
        document_ = document(tmp_path, **kwargs)
        _, _, frames, _ = preflight(document_, Q)
        return frames[0]

    def test_the_width_follows_the_file_proportions(self, tmp_path: Path) -> None:
        png(tmp_path / "logo.png", 40, 10)
        marks = self.marks(tmp_path, field="{ image: logo.png, height: 8mm }")
        image = next(mark for mark in marks if isinstance(mark, Image))
        assert image.height == 8_000
        assert image.width == 32_000

    def test_the_path_is_relative_to_the_definition_file(self, tmp_path: Path) -> None:
        # Not to the working directory: a definition and its logo travel
        # together, and where the shell happens to stand is not part of that.
        png(tmp_path / "logo.png")
        marks = self.marks(tmp_path, field="{ image: logo.png, height: 4mm }")
        image = next(mark for mark in marks if isinstance(mark, Image))
        assert image.source == str((tmp_path / "logo.png").resolve())

    def test_it_sits_inside_its_band(self, tmp_path: Path) -> None:
        png(tmp_path / "logo.png")
        marks = self.marks(tmp_path, field="{ image: logo.png, height: 4mm }")
        image = next(mark for mark in marks if isinstance(mark, Image))
        assert image.pos.y > 0

    def test_text_beside_an_image_still_works(self, tmp_path: Path) -> None:
        png(tmp_path / "logo.png")
        text = (
            "version: 1\nheader:\n  height: 12mm\n"
            "  left: { image: logo.png, height: 6mm }\n"
            '  right: "Class 3B"\n'
            "generator: lines\nfamilies:\n"
            "  - {direction: horizontal, base_spacing: 10mm}\n"
        )
        (tmp_path / "def.yaml").write_text(text, encoding="utf-8")
        _, _, frames, _ = preflight(load(tmp_path / "def.yaml"), Q)
        assert any(isinstance(mark, Image) for mark in frames[0])
        assert any(getattr(mark, "content", None) == "Class 3B" for mark in frames[0])


class TestRefusals:
    """§ 8.9: a logo is never cropped — it fits or it is an error."""

    def test_an_image_taller_than_its_band_is_refused(self, tmp_path: Path) -> None:
        # § 8.4: the band height comes from the definition and is checked
        # against the content, never derived from it.
        png(tmp_path / "logo.png")
        with pytest.raises(DefinitionError) as excinfo:
            preflight(
                document(tmp_path, field="{ image: logo.png, height: 20mm }"), Q
            )
        message = str(excinfo.value)
        # The image height in the units the user wrote (§ 12), the band height
        # as it was computed.
        assert "20mm" in message and "12.0mm" in message

    def test_an_image_wider_than_its_field_is_refused(self, tmp_path: Path) -> None:
        png(tmp_path / "wide.png", 4000, 10)
        with pytest.raises(DefinitionError) as excinfo:
            preflight(document(tmp_path, field="{ image: wide.png, height: 8mm }"), Q)
        assert "wide.png" in str(excinfo.value)

    def test_cut_true_does_not_apply_to_images(self, tmp_path: Path) -> None:
        # § 8.9 withholds truncation from images on purpose.
        png(tmp_path / "wide.png", 4000, 10)
        text = (
            "version: 1\nheader:\n  height: 12mm\n  cut: true\n"
            "  left: { image: wide.png, height: 8mm }\n"
            "generator: lines\nfamilies:\n"
            "  - {direction: horizontal, base_spacing: 10mm}\n"
        )
        (tmp_path / "def.yaml").write_text(text, encoding="utf-8")
        with pytest.raises(DefinitionError):
            preflight(load(tmp_path / "def.yaml"), Q)

    def test_a_missing_height_is_an_error(self, tmp_path: Path) -> None:
        png(tmp_path / "logo.png")
        with pytest.raises(DefinitionError) as excinfo:
            document(tmp_path, field="{ image: logo.png }")
        assert "height" in str(excinfo.value)

    def test_nothing_is_written_when_an_image_does_not_fit(self, tmp_path: Path) -> None:
        png(tmp_path / "logo.png")
        out = tmp_path / "never.pdf"
        with pytest.raises(DefinitionError):
            build(document(tmp_path, field="{ image: logo.png, height: 20mm }"),
                  PdfWriter(out))
        assert not out.exists()


class TestOnTheSheet:
    def test_the_image_reaches_the_pdf(self, tmp_path: Path) -> None:
        png(tmp_path / "logo.png")
        out = tmp_path / "logo.pdf"
        build(document(tmp_path, field="{ image: logo.png, height: 6mm }"), PdfWriter(out))
        from pypdf import PdfReader

        resources = PdfReader(str(out)).pages[0]["/Resources"]
        assert "/XObject" in resources
        assert pdfread.page_count(out) == 1

    def test_two_runs_produce_identical_bytes(self, tmp_path: Path) -> None:
        png(tmp_path / "logo.png")
        first, second = tmp_path / "a.pdf", tmp_path / "b.pdf"
        for path in (first, second):
            build(document(tmp_path, field="{ image: logo.png, height: 6mm }"),
                  PdfWriter(path))
        assert first.read_bytes() == second.read_bytes()

    def test_the_writer_says_it_can_do_images_now(self) -> None:
        # § 10.2: capabilities are what the pre-flight checks against, so they
        # have to grow with the writer rather than after it.
        assert "image_png" in Q.capabilities()
