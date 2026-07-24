"""The PDF writer — the only module in the package that may import reportlab.

That rule (§ 3.3, and acceptance criterion 6 of § 14) is guarded by a test that
predates this file. It is not tidiness: a generator that reaches for reportlab
kills the second writer before it is written.

Three duties beyond drawing:

* **Reproducibility** (§ 10.1). reportlab writes the creation time and a random
  document ID by default, so identical input would give different bytes and
  every golden comparison in CI would fail. `invariant=1` fixes both, and
  reportlab honours `SOURCE_DATE_EPOCH` on top of that.
* **File size** (§ 10.1). A dot is a zero-length stroke with a round cap, not a
  filled circle: 2500 dots per page as four Bézier curves each is the
  difference between a small file and a double-digit megabyte one.
* **Answering questions** (§ 10.2). Font metrics live here and nowhere else,
  and § 12 measures every page before writing the first one.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from reportlab.lib.colors import HexColor
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.pdfdoc import PDFArray, PDFDictionary, PDFName, PDFStream, PDFString
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from ctrlgrid import __version__, fonts
from ctrlgrid.errors import CtrlGridError
from ctrlgrid.marks import Arc, Dot, Image, Mark, Point, Polygon, Segment, Text, Um
from ctrlgrid.writers import Attachment, DocumentMeta

PT_PER_UM = 72 / 25400

# Stage 1 of § 10.3: the three logical families resolved to the standard PDF
# fonts. Their metrics are part of the PDF specification and fixed in
# reportlab, so the geometry is identical on every machine — which is the part
# a tool promising dimensional accuracy depends on. Nothing is embedded.
_FONTS = {
    "serif": "Times-Roman",
    "sans": "Helvetica",
    "mono": "Courier",
}

# What the standard fonts can encode (§ 10.3). `ä ö ü ß é à ñ ç …` yes,
# `ł ğ ő` no — the likeliest first stumbling block of the whole tool.
_STANDARD_ENCODING = "cp1252"


class PdfWriter:
    """Seam 3 for PDF (§ 3.6): marks in, metrics out."""

    def __init__(self, path: Path | str):
        self.path = Path(path)
        self._canvas: canvas.Canvas | None = None

    # ---------------------------------------------------------------- queries

    def capabilities(self) -> set[str]:
        """What this writer can render today (§ 10.2, § 14).

        The vocabulary is complete from M1; a writer grows into it, and the
        pre-flight check refuses anything missing instead of dropping it.
        """
        return {
            "vector", "color", "text", "opacity", "arc", "polygon", "image_png",
            "attachment",
        }

    def text_width(self, content: str, *, family: str, size: Um) -> Um:
        return _to_um(pdfmetrics.stringWidth(content, _font(family), _to_pt(size)))

    def text_metrics(self, *, family: str, size: Um) -> tuple[Um, Um]:
        """Ascent and descent in micrometres, both positive (§ 8.4)."""
        face = pdfmetrics.getFont(_font(family)).face
        return (
            round(size * face.ascent / 1000),
            round(size * abs(face.descent) / 1000),
        )

    def missing_glyphs(self, content: str, *, family: str) -> list[str]:
        """What this font cannot set (§ 10.2).

        For an embedded font the answer comes out of its own `cmap`, not out of
        an encoding table: stage 2 exists precisely so that `ł` stops being a
        missing glyph, and only the file can say whether it is.
        """
        if fonts.is_file_token(family):
            return fonts.load_token(family).missing(content)
        missing: list[str] = []
        for character in content:
            try:
                character.encode(_STANDARD_ENCODING)
            except UnicodeEncodeError:
                if character not in missing:
                    missing.append(character)
        return missing

    # ---------------------------------------------------------------- writing

    def begin_document(self, meta: DocumentMeta) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # invariant=1: fixed creation date and a document ID derived from the
        # content rather than from randomness (§ 10.1).
        self._canvas = canvas.Canvas(
            str(self.path),
            invariant=1,
            pageCompression=1,
            pdfVersion=(1, 4),
        )
        self._canvas.setTitle(meta.title)
        self._canvas.setAuthor(meta.author)
        self._canvas.setSubject(meta.subject)
        self._canvas.setCreator(f"ctrlgrid {__version__}")
        self._canvas.setProducer(f"ctrlgrid {__version__}")
        if meta.attachment is not None:
            self._embed(meta.attachment)

    def _embed(self, attachment: Attachment) -> None:
        """Carry a file inside the PDF as an EmbeddedFile (§ 8.8, § 15 point 5).

        reportlab has no filespec support ("skipping filespecs" in its own
        source), so the objects are built by hand: an EmbeddedFile stream, a
        Filespec that points at it, and the catalog's `/Names /EmbeddedFiles`
        name tree — the standard PDF 1.4+ mechanism, and exactly the version
        this writer targets, so every viewer lists it in its attachments panel.
        (`/AF`, the PDF 2.0 association array, is not added: reportlab's
        `PDFCatalog` only serialises a fixed set of keys and silently drops it,
        and the name tree is what viewers actually read.) Everything here is
        derived from the bytes and the name — no date, no random id — so § 10.1
        holds: identical input still gives identical bytes, and this is covered
        by a determinism test like every other addition to the writer.

        No `/Subtype`: reportlab's `PDFName` leaves the MIME slash raw
        (`/application/yaml`), which a strict parser reads as two name tokens and
        chokes on. Subtype is optional, so it is left off and the `.yaml`
        filename carries the type instead.
        """
        doc = self._pdf._doc
        data = attachment.data
        stream = PDFStream(
            dictionary=PDFDictionary({
                "Type": PDFName("EmbeddedFile"),
                "Params": PDFDictionary({"Size": len(data)}),
            }),
            content=data,
        )
        file_ref = doc.Reference(stream)
        spec: dict[str, object] = {
            "Type": PDFName("Filespec"),
            "F": PDFString(attachment.filename),
            "UF": PDFString(attachment.filename),
            "EF": PDFDictionary({"F": file_ref, "UF": file_ref}),
        }
        if attachment.description:
            spec["Desc"] = PDFString(attachment.description)
        spec_ref = doc.Reference(PDFDictionary(spec))
        doc.Catalog.Names = PDFDictionary({
            "EmbeddedFiles": PDFDictionary({
                "Names": PDFArray([PDFString(attachment.filename), spec_ref]),
            }),
        })

    def begin_page(self, width: Um, height: Um) -> None:
        # The exact MediaBox is the whole promise (§ 8.2): no rounding to a
        # named format, no "scale to fit".
        self._pdf.setPageSize((_to_pt(width), _to_pt(height)))

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
            case Text():
                self._text(mark)
            case Image():
                self._image(mark)

    def outline(self, title: str, *, index: int) -> None:
        """A bookmark on the current page (§ 10.1).

        The key comes from the page index, never from a counter or a random
        value, so two runs of the same command produce the same bytes.
        """
        pdf = self._pdf
        key = f"page{index}"
        pdf.bookmarkPage(key)
        pdf.addOutlineEntry(title, key)

    def end_page(self) -> None:
        self._pdf.showPage()

    def end_document(self) -> None:
        self._pdf.save()
        self._canvas = None

    # ------------------------------------------------------------- primitives

    @property
    def _pdf(self) -> canvas.Canvas:
        if self._canvas is None:
            raise CtrlGridError("begin_document must be called before writing")
        return self._canvas

    def _segment(self, mark: Segment) -> None:
        pdf = self._pdf
        pdf.saveState()
        pdf.setLineWidth(_mm_to_pt(mark.weight))
        pdf.setStrokeColor(HexColor(mark.color))
        pdf.setLineCap({"butt": 0, "round": 1, "square": 2}[mark.cap])
        _dash(pdf, mark.dash)
        if mark.opacity < 1.0:
            pdf.setStrokeAlpha(mark.opacity)
        pdf.line(*_pt(mark.start), *_pt(mark.end))
        pdf.restoreState()

    def _dot(self, mark: Dot) -> None:
        """A dot is a zero-length stroke with a round cap (§ 10.1)."""
        pdf = self._pdf
        pdf.saveState()
        pdf.setLineWidth(_mm_to_pt(mark.diameter))
        pdf.setStrokeColor(HexColor(mark.color))
        pdf.setLineCap(1)
        if mark.opacity < 1.0:
            pdf.setStrokeAlpha(mark.opacity)
        x, y = _pt(mark.pos)
        pdf.line(x, y, x, y)
        pdf.restoreState()

    def _arc(self, mark: Arc) -> None:
        pdf = self._pdf
        pdf.saveState()
        pdf.setLineWidth(_mm_to_pt(mark.weight))
        pdf.setStrokeColor(HexColor(mark.color))
        _dash(pdf, mark.dash)
        if mark.opacity < 1.0:
            pdf.setStrokeAlpha(mark.opacity)
        x, y = _pt(mark.center)
        radius = _to_pt(mark.radius)
        path = pdf.beginPath()
        path.arc(x - radius, y - radius, x + radius, y + radius, mark.start_angle, mark.sweep)
        pdf.drawPath(path, stroke=1, fill=0)
        pdf.restoreState()

    def _polygon(self, mark: Polygon) -> None:
        pdf = self._pdf
        pdf.saveState()
        pdf.setLineWidth(_mm_to_pt(mark.weight))
        pdf.setStrokeColor(HexColor(mark.color))
        if mark.fill_color is not None:
            pdf.setFillColor(HexColor(mark.fill_color))
        if mark.opacity < 1.0:
            pdf.setStrokeAlpha(mark.opacity)
            pdf.setFillAlpha(mark.opacity)
        path = pdf.beginPath()
        path.moveTo(*_pt(mark.points[0]))
        for point in mark.points[1:]:
            path.lineTo(*_pt(point))
        if mark.closed:
            path.close()
        pdf.drawPath(path, stroke=1, fill=1 if mark.fill_color is not None else 0)
        pdf.restoreState()

    def _image(self, mark: Image) -> None:
        """Place a PNG at exactly the box the layout measured (§ 5.2).

        `mask='auto'` so a logo with a transparent background stays one, and
        the box is never adjusted: the width came from the file's own
        proportions in `frame.py`, so drawing it as given is what keeps the
        picture unsquashed.
        """
        pdf = self._pdf
        pdf.saveState()
        if mark.opacity < 1.0:
            pdf.setFillAlpha(mark.opacity)
        x, y = _pt(mark.pos)
        pdf.drawImage(
            mark.source,
            x,
            y,
            width=_to_pt(mark.width),
            height=_to_pt(mark.height),
            mask="auto",
        )
        pdf.restoreState()

    def _text(self, mark: Text) -> None:
        pdf = self._pdf
        pdf.saveState()
        pdf.setFont(_font(mark.family), _to_pt(mark.size))
        pdf.setFillColor(HexColor(mark.color))
        if mark.opacity < 1.0:
            pdf.setFillAlpha(mark.opacity)
        x, y = _pt(mark.pos)
        if mark.angle:
            pdf.translate(x, y)
            pdf.rotate(mark.angle)
            x = y = 0
        draw = {
            "left": pdf.drawString,
            "center": pdf.drawCentredString,
            "right": pdf.drawRightString,
        }[mark.align]
        draw(x, y, mark.content)
        pdf.restoreState()


def _dash(pdf: canvas.Canvas, dash: tuple[float, ...]) -> None:
    """Set a dash pattern, or leave the line solid (§ 7.1).

    An empty tuple is left alone rather than written as `[] 0 d`: every stroke
    already runs inside its own `saveState`, so a solid line has nothing to
    reset, and not writing the operator keeps solid sheets byte-for-byte what
    they were before dashes existed (§ 10.1).
    """
    if dash:
        pdf.setDash([_mm_to_pt(value) for value in dash], 0)


def _font(family: str) -> str:
    """Resolve a font token to a name reportlab knows (§ 10.3).

    Stage 1 is a lookup. Stage 2 registers the file with reportlab the first
    time it is asked for, under the font's **own** PostScript name: a key
    derived from the path would put this machine's directory layout into the
    PDF and break § 10.1 across machines. Two different files claiming the same
    name are told apart by a short digest of the path — rare, and better than
    one silently standing in for the other.
    """
    if not fonts.is_file_token(family):
        return _FONTS[family]

    font = fonts.load_token(family)
    key = _registered.get(font.path)
    if key is None:
        key = font.name
        if key in _registered.values() or key in _FONTS.values():
            key = f"{font.name}-{hashlib.sha256(str(font.path).encode()).hexdigest()[:8]}"
        # reportlab subsets embedded TrueType fonts by itself, which is what
        # § 10.3 asks for: only the glyphs actually used travel with the file.
        pdfmetrics.registerFont(TTFont(key, str(font.path)))
        _registered[font.path] = key
    return key


#: Resolved path to the name it was registered under. Module level because
#: reportlab's font registry is module level too — registering the same file
#: twice under two names would embed it twice.
_registered: dict[Path, str] = {}


def _to_pt(um: Um) -> float:
    return um * PT_PER_UM


def _to_um(points: float) -> Um:
    return round(points / PT_PER_UM)


def _mm_to_pt(mm: float) -> float:
    return mm * 1000 * PT_PER_UM


def _pt(point: Point) -> tuple[float, float]:
    return _to_pt(point.x), _to_pt(point.y)
