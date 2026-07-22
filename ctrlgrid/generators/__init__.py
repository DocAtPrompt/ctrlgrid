"""The blade registry — seam 2 of § 3.6.

A new blade is a registry entry and gets the frame, the page loop and the
output for free. Whether that stays true is the measure of whether the pocket
knife holds (§ 13.1).

No plugin system, no discovery (§ 2, § 10.5): contributions arrive as pull
requests, and the registry is a dict.
"""

from __future__ import annotations

import difflib
from collections.abc import Iterator
from typing import Protocol

from pydantic import BaseModel

from ctrlgrid.errors import DefinitionError
from ctrlgrid.generators.lines import LinesGenerator
from ctrlgrid.marks import Area, Mark
from ctrlgrid.pages import PageContext
from ctrlgrid.writers import WriterQuery


class Generator(Protocol):
    """A blade: marks in local coordinates, and nothing else (§ 3.6)."""

    name: str
    config_model: type[BaseModel]

    def is_page_invariant(self, cfg: BaseModel) -> bool:
        """True if the writer may store the pattern once and reference it (§ 10.1)."""
        ...

    def describe(self, cfg: BaseModel) -> list[str]:
        """Lines about the effective period, for the run report (§ 5.3, § 11.3).

        Part of the seam because only the blade knows its own cycles, and § 5.3
        requires both periods — in marks and in millimetres — to be reported.
        """
        ...

    def generate(
        self,
        cfg: BaseModel,
        *,
        area: Area,
        page: PageContext,
        q: WriterQuery,
    ) -> Iterator[Mark]: ...


REGISTRY: dict[str, Generator] = {
    generator.name: generator
    for generator in (LinesGenerator(),)
}


def get(name: str) -> Generator:
    """Look up a blade, suggesting a near miss rather than listing everything."""
    try:
        return REGISTRY[name]
    except KeyError:
        close = difflib.get_close_matches(name, REGISTRY, n=1)
        hint = f" — did you mean `{close[0]}`?" if close else ""
        known = ", ".join(sorted(REGISTRY))
        raise DefinitionError(
            f"unknown generator `{name}`{hint} (known: {known})",
            field="generator",
        ) from None


__all__ = ["REGISTRY", "Generator", "get"]
