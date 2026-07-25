"""`notebook` — a linked notebook of sections, each filled by a blade (§ 7.13).

The second document generator, and the first that composes blades. A section is
a small definition: the generator, then that generator's own keys, exactly as at
the top level of any file — so the blade validates its own section and a typo
inside one names the blade.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from ctrlgrid.errors import DefinitionError
from ctrlgrid.loader import loads
from ctrlgrid.marks import Area, Dot
from ctrlgrid.pages import build, document_page_marks, page_contexts
from ctrlgrid.writers.pdf import PdfWriter

Q = PdfWriter("unused.pdf")
AREA = Area(width=180_000, height=250_000)

DEF = (
    "version: 1\n"
    "page: {format: a4, margin: 12mm}\n"
    "generator: notebook\n"
    "sections:\n"
    "  - label: Journal\n"
    "    pages: 3\n"
    "    generator: dots\n"
    "    grid: {x: {base_spacing: 5mm}, y: {base_spacing: 5mm}}\n"
    "    base_size: 0.4mm\n"
    "  - label: Sums\n"
    "    pages: 2\n"
    "    divider: true\n"
    "    generator: lines\n"
    "    families:\n"
    "      - {direction: horizontal, base_spacing: 5mm}\n"
    "      - {direction: vertical, base_spacing: 5mm}\n"
)


def config(text: str = DEF):
    return loads(text, None, source="test").config


class TestTheSections:
    def test_a_section_carries_its_blades_validated_config(self) -> None:
        cfg = config()
        assert cfg.sections[0].generator == "dots"
        assert cfg.sections[0].config.base_size.raw == "0.4mm"
        assert cfg.sections[1].config.families[0].base_spacing.um == 5000

    def test_a_typo_inside_a_section_is_refused_by_that_blade(self) -> None:
        # § 5.1: an unknown key is an error, and here the error has to come
        # from the blade that owns the key, or it would read as a typo in the
        # notebook's own vocabulary.
        with pytest.raises((DefinitionError, ValidationError)) as excinfo:
            config(DEF + "  - {label: X, pages: 1, generator: dots, base_siz: 0.4mm}\n")
        assert "base_siz" in str(excinfo.value)

    def test_an_unknown_generator_lists_the_known_ones(self) -> None:
        with pytest.raises((DefinitionError, ValidationError)) as excinfo:
            config(DEF + "  - {label: X, pages: 1, generator: dotz}\n")
        message = str(excinfo.value)
        assert "dotz" in message and "dots" in message

    def test_a_document_generator_cannot_fill_a_section(self) -> None:
        # A section is pages; a document generator is what produces pages.
        with pytest.raises((DefinitionError, ValidationError)) as excinfo:
            config(DEF + "  - {label: X, pages: 1, generator: calendar, year: 2026}\n")
        assert "calendar" in str(excinfo.value)

    def test_a_section_needs_at_least_one_page(self) -> None:
        with pytest.raises((DefinitionError, ValidationError)):
            config(DEF + "  - {label: X, pages: 0, generator: dots}\n")

    def test_a_notebook_needs_at_least_one_section(self) -> None:
        with pytest.raises((DefinitionError, ValidationError)):
            loads(
                "version: 1\npage: {format: a4}\ngenerator: notebook\nsections: []\n",
                None,
                source="test",
            )

    def test_a_sections_blade_refuses_what_the_area_cannot_hold(self) -> None:
        # Each section's own `check` runs against the pattern area, so a
        # section that cannot fit is refused in that blade's own words (§ 12).
        text = (
            "version: 1\npage: {format: a6, margin: 5mm}\ngenerator: notebook\n"
            "sections:\n"
            "  - {label: Log, pages: 1, generator: lines, families: ["
            "{direction: horizontal, base_spacing: 20mm, law: log10, decades: 9}]}\n"
        )
        with pytest.raises(DefinitionError) as excinfo:
            build(loads(text, None, source="test"), PdfWriter("unused.pdf"))
        assert "decades" in str(excinfo.value)


class TestThePages:
    def _pages(self, text: str = DEF):
        from ctrlgrid import generators

        return list(generators.get("notebook").pages(config(text), area=AREA, q=Q))

    def test_the_order_is_contents_then_every_section(self) -> None:
        kinds = [page.kind for page in self._pages()]
        assert kinds == [
            "contents", "section", "section", "section", "divider", "section", "section",
        ]

    def test_page_count_agrees_with_the_pages_produced(self) -> None:
        from ctrlgrid import generators

        blade = generators.get("notebook")
        assert blade.page_count(config(), area=AREA) == len(self._pages())

    def test_a_dots_section_really_carries_dots(self) -> None:
        page = self._pages()[1]
        context = next(page_contexts(count=1, snap=()))
        marks = list(document_page_marks(page, area=AREA, context=context, q=Q))
        assert any(isinstance(mark, Dot) for mark in marks)

    def test_every_link_target_is_a_page_that_exists(self) -> None:
        pages = self._pages()
        destinations = {page.dest for page in pages}
        targets = {link.target for page in pages for link in page.links}
        assert targets and targets <= destinations

    def test_each_page_names_its_section_for_the_band(self) -> None:
        # `{section}` in a header: only the generator knows which section a
        # page belongs to (§ 8.10).
        pages = self._pages()
        assert dict(pages[1].placeholders)["section"] == "Journal"
        assert dict(pages[-1].placeholders)["section"] == "Sums"

    def test_a_title_page_is_opt_in(self) -> None:
        with_title = self._pages(
            DEF.replace(
                "sections:\n", "title_page: {title: 'Notebook'}\nsections:\n"
            )
        )
        assert with_title[0].kind == "title"

    def test_a_contents_that_cannot_fit_is_refused_with_the_height(self) -> None:
        from ctrlgrid import generators

        many = "".join(
            f"  - {{label: 'Section {i}', pages: 1, generator: dots}}\n" for i in range(200)
        )
        text = (
            "version: 1\npage: {format: a7, margin: 4mm}\ngenerator: notebook\n"
            "sections:\n" + many
        )
        with pytest.raises(DefinitionError) as excinfo:
            generators.get("notebook").check(
                config(text), area=Area(width=60_000, height=90_000), q=Q
            )
        assert "mm" in str(excinfo.value)


class TestOnTheSheet:
    def test_it_writes_the_pages_and_the_links(self, tmp_path: Path) -> None:
        from pypdf import PdfReader

        path = tmp_path / "nb.pdf"
        build(loads(DEF, None, source="test"), PdfWriter(path))
        reader = PdfReader(str(path))
        assert len(reader.pages) == 7
        annotations = reader.pages[0].get("/Annots")
        assert annotations and len(annotations) == 2   # one link per section

    def test_two_runs_produce_identical_bytes(self, tmp_path: Path) -> None:
        first, second = tmp_path / "a.pdf", tmp_path / "b.pdf"
        build(loads(DEF, None, source="test"), PdfWriter(first))
        build(loads(DEF, None, source="test"), PdfWriter(second))
        assert first.read_bytes() == second.read_bytes()

    def test_the_bands_number_the_pages_and_name_the_section(self, tmp_path: Path) -> None:
        from tests.pdfread import text_on

        text = DEF.replace(
            "generator: notebook\n",
            "header: {height: 8mm, gap: 3mm, left: '{section}'}\n"
            "footer: {height: 8mm, gap: 3mm, right: '{page} / {page_count}'}\n"
            "generator: notebook\n",
        )
        path = tmp_path / "nb.pdf"
        build(loads(text, None, source="test"), PdfWriter(path))
        assert "Journal" in text_on(path, 1)
        assert "2 / 7" in text_on(path, 1)
        assert "Sums" in text_on(path, 5)
