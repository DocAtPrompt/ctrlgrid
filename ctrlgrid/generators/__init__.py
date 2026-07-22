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

from ctrlgrid.axes import AxisPeriod
from ctrlgrid.errors import DefinitionError
from ctrlgrid.generators.dots import DotsGenerator
from ctrlgrid.generators.grid import GridGenerator
from ctrlgrid.generators.lines import LinesGenerator
from ctrlgrid.generators.maze import MazeGenerator
from ctrlgrid.generators.polar import PolarGenerator
from ctrlgrid.generators.staves import StavesGenerator
from ctrlgrid.generators.tiling import TilingGenerator
from ctrlgrid.marks import Area, Mark
from ctrlgrid.pages import PageContext
from ctrlgrid.writers import WriterQuery


class Generator(Protocol):
    """A blade: marks in local coordinates, and nothing else (§ 3.6)."""

    name: str
    config_model: type[BaseModel]

    supports_snap: bool
    """Whether `pattern.snap` means anything here (§ 8.3).

    § 8.3 lists the blades for which snapping is an **error** rather than a
    setting — `polar` among them — so the answer belongs to the blade and the
    handle refuses before it computes any geometry. Not derivable from
    `periodic_axes`: an empty result means "nothing to snap to here", which is
    a different sentence from "snapping does not apply to this pattern".
    """

    def is_page_invariant(self, cfg: BaseModel) -> bool:
        """True if the writer may store the pattern once and reference it (§ 10.1)."""
        ...

    def periodic_axes(self, cfg: BaseModel) -> dict[str, list[AxisPeriod]]:
        """The periodic families this blade has, keyed by axis (`x`, `y`).

        The handle needs them for snapping (§ 8.3) and remainder handling
        (§ 8.5). An empty result means the blade has no period to work with,
        and both settings are then an error rather than quietly ineffective.
        """
        ...

    def describe(self, cfg: BaseModel) -> list[str]:
        """Lines about the effective period, for the run report (§ 5.3, § 11.3).

        Part of the seam because only the blade knows its own cycles, and § 5.3
        requires both periods — in marks and in millimetres — to be reported.
        """
        ...

    def check(self, cfg: BaseModel, *, area: Area, q: WriterQuery) -> None:
        """Refuse anything that can only be judged against the pattern area.

        Called once by the pre-flight, before a single page is written (§ 12
        point 13). `polar` needs it for two questions nothing else can answer:
        does the circle fit the area it was handed, and do the segment labels
        fit their segments (§ 7.6, § 10.2). A blade with nothing to add leaves
        it empty — `generate` is unchanged either way, which is the point.
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
    for generator in (
        DotsGenerator(),
        GridGenerator(),
        LinesGenerator(),
        MazeGenerator(),
        PolarGenerator(),
        StavesGenerator(),
        TilingGenerator(),
    )
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


__all__ = ["REGISTRY", "AxisPeriod", "Generator", "get"]
