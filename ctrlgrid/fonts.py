"""Stage 2 of § 10.3 — a named font file, checked before it is embedded.

**A path, never a name.** Name lookup works differently on every platform
(fontconfig, CoreText, the registry), finds different fonts depending on what
happens to be installed, and is exactly the unreliability this tool exists to
avoid. A path is unambiguous, checkable, and can be named in an error message.

**Embedding rights are checked, not assumed.** TrueType and OpenType fonts
carry an `fsType` field in their `OS/2` table which can forbid embedding.
Ignoring it produces PDFs that violate the font licence, so a font that forbids
it aborts the run and is named — there is no quiet substitution, because a
sheet set in a font nobody asked for is the "almost right" failure of § 5.1.

This module reads the file; `writers/pdf.py` embeds it. The split is not
tidiness: § 3.3 keeps reportlab in one module, and the licence question is not
a rendering question. Reportlab cannot answer it either — it parses `OS/2` for
metrics and never looks at `fsType`.

Nothing here caches a font's *pixels*, only its facts: the parse is memoised by
resolved path, so thirty pages with the same header do not re-read the file
thirty times.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from ctrlgrid.errors import DefinitionError

#: The `fsType` bits that matter, from the OpenType OS/2 table.
RESTRICTED = 0x0002
"""No embedding at all."""
BITMAP_ONLY = 0x0200
"""Only bitmaps may be embedded — we embed outlines, so this is a refusal too."""
NO_SUBSETTING = 0x0100
"""Embedding without subsetting only. We always subset (§ 10.3)."""

#: How a font file is spelled inside a mark's `family` field. The mark
#: vocabulary does not grow for this (§ 6): `family` was always a string the
#: writer resolves, and stage 1's three logical names are the other spellings.
PREFIX = "file:"


@dataclass(frozen=True, slots=True)
class FontFile:
    """What the tool needs to know about a font before it uses it."""

    path: Path
    name: str
    """The PostScript name, as the font itself gives it."""

    version: str
    """The font's own version string — § 10.3 puts it on the cover sheet,
    because two releases of the same font are two different sheets."""

    fs_type: int
    characters: frozenset[int]
    """Every code point the font can set, from its best `cmap` subtable."""

    def missing(self, text: str) -> list[str]:
        """Which characters of `text` this font cannot set, in order, once each."""
        missing: list[str] = []
        for character in text:
            if ord(character) not in self.characters and character not in missing:
                missing.append(character)
        return missing


def token_for(raw: str) -> str:
    """The font token for a path, without touching the disk.

    Kept separate from `load_font` so the model can carry a token through
    validation while the file itself is opened once, later, by whoever needs
    its metrics.
    """
    return f"{PREFIX}{Path(raw).expanduser()}"


def is_file_token(token: str) -> bool:
    return token.startswith(PREFIX)


def load_token(token: str) -> FontFile:
    return load_font(token[len(PREFIX):])


def load_font(raw: str, *, field: str | None = None) -> FontFile:
    """Read a font file, refuse it if its licence forbids what we would do.

    `field` is the definition key it came from, so § 12's rule holds: the
    message names the place in the file, not just the file on disk.
    """
    try:
        return _load(str(Path(raw).expanduser()))
    except DefinitionError as error:
        raise (error.at(field=field) if field else error) from None


@lru_cache(maxsize=32)
def _load(path_text: str) -> FontFile:
    # Imported here rather than at module level: fontTools is a heavy import,
    # and a run that names no font file should not pay for it. `tests/
    # test_architecture.py` keeps it to this module either way.
    from fontTools.ttLib import TTFont, TTLibError

    path = Path(path_text)
    if not path.is_file():
        raise DefinitionError(
            f"no font file at {path} — stage 2 of § 10.3 takes a path to a file, "
            "not a font name, because name lookup finds different fonts on "
            "different machines"
        )

    try:
        font = TTFont(str(path), lazy=True, fontNumber=0)
        os2 = font.get("OS/2")
        cmap = font.getBestCmap()
        names = font["name"]
        version = names.getDebugName(5) or ""
        name = names.getDebugName(6) or names.getDebugName(4) or path.stem
    except (TTLibError, KeyError, OSError, AssertionError) as error:
        raise DefinitionError(
            f"{path} is not a font file this tool can read ({type(error).__name__}: "
            f"{error}). TrueType (.ttf) and OpenType (.otf) are what § 10.3 means"
        ) from None

    # No `OS/2` table means no statement about embedding. That is not the same
    # as permission, but refusing every font from before the table existed
    # would be absurd — it is treated as the installable default, the way every
    # other PDF producer treats it.
    fs_type = int(getattr(os2, "fsType", 0) or 0)
    _check_licence(fs_type, path=path, name=name)

    return FontFile(
        path=path.resolve(),
        name=name,
        version=version.strip(),
        fs_type=fs_type,
        characters=frozenset(cmap),
    )


def _check_licence(fs_type: int, *, path: Path, name: str) -> None:
    """§ 10.3: refuse rather than substitute, and say which bit said so."""
    if fs_type & RESTRICTED:
        raise DefinitionError(
            f"{name} ({path.name}) may not be embedded: its fsType field says "
            "'restricted licence' (bit 0x0002). Embedding it anyway would break the "
            "font licence, and swapping in another font quietly would change every "
            "measurement on the sheet — pick a font whose licence allows embedding "
            "(§ 10.3)"
        )
    if fs_type & BITMAP_ONLY:
        raise DefinitionError(
            f"{name} ({path.name}) may only be embedded as bitmaps (fsType bit 0x0200), "
            "and this tool embeds outlines — a bitmap font would not be dimensionally "
            "accurate at print resolution (§ 8.2, § 10.3)"
        )
    if fs_type & NO_SUBSETTING:
        raise DefinitionError(
            f"{name} ({path.name}) forbids subsetting (fsType bit 0x0100), and this tool "
            "always subsets: a template embeds a handful of characters, and shipping a "
            "whole font in every sheet is not a trade this tool makes (§ 10.1, § 10.3)"
        )
