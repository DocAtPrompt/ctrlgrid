"""Seam 1 — definition file to validated model (§ 3.6), plus formats and presets.

`ruamel.yaml` rather than `PyYAML` for one reason (§ 13): § 12 demands
actionable error messages, and that includes the **line** of the definition
file. PyYAML throws the position away at load time, and pydantic afterwards
knows only the key path. On an eighty-line preset copy `families.2.base_spacing`
is markedly worse than `line 47`.

Three refusals happen here before anything else looks at the data:

* **merge keys** (`<<`) — inheritance, and inheritance is a non-goal (§ 2, § 5.4)
* **runaway alias expansion** — safe loading does not prevent it, and defs get
  copied out of other people's repositories (§ 5.4)
* **unknown keys**, with a suggestion for a near miss (§ 5.1, § 12 point 4)
"""

from __future__ import annotations

import codecs
import difflib
import hashlib
import re
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ValidationError
from ruamel.yaml import YAML, YAMLError
from ruamel.yaml.comments import CommentedMap, CommentedSeq
from ruamel.yaml.nodes import MappingNode, SequenceNode

from ctrlgrid import fonts, generators
from ctrlgrid.axes import AxisPeriod
from ctrlgrid.errors import DefinitionError
from ctrlgrid.model import (
    Band,
    BorderSpec,
    Margin,
    PageSpec,
    PagesSpec,
    PatternSpec,
    StampSpec,
)
from ctrlgrid.pages import Sheet
from ctrlgrid.units import Length, parse_length

DATA = Path(__file__).parent / "data"
PRESETS = DATA / "presets"

SUPPORTED_VERSION = 1

#: Top-level keys owned by the handle (§ 3). Everything else on the top level
#: belongs to the blade and is validated by its own config model.
HANDLE_KEYS = {
    "version", "defs", "generator",
    "page", "header", "footer", "border", "stamp", "pattern", "pages",
}

#: Keys the specification defines on the top level and this milestone does not
#: implement. Named, so they cannot be mistaken for typos.
DEFERRED_KEYS: dict[str, str] = {}

#: Walking the loaded structure is where a YAML bomb detonates, because
#: `ruamel` shares aliased objects rather than copying them. So the walk itself
#: is the guard (§ 5.4).
EXPANSION_LIMIT = 100_000


@dataclass(frozen=True, slots=True)
class PaperFormat:
    """An entry of the built-in format table (§ 9.1)."""

    id: str
    name: str
    width: Length
    height: Length
    margin: Length
    assumed_dpi: int


@dataclass(frozen=True, slots=True)
class Document:
    """A definition file, validated, with units normalised and the sheet resolved."""

    version: int
    page: PageSpec
    header: Band | None
    footer: Band | None
    border: BorderSpec | None
    stamp: StampSpec | None
    pattern: PatternSpec
    pages: PagesSpec
    generator: str
    config: Any
    """The blade's own section, validated by its `config_model` (§ 3.6)."""

    names: list[str] | None
    """One entry per page, already resolved to the final page count (§ 9.4).
    None when the run is not data-driven."""

    notices: tuple[str, ...]
    """Things said once per run rather than refused over — see § 9.4 on
    reporting that a list was cut rather than cutting it quietly."""

    sheet: Sheet
    axes: dict[str, list[AxisPeriod]]
    """The blade's periodic axes, asked once so the handle can place the
    leftover and snap without ever reaching into the blade (§ 8.3, § 8.5)."""

    source: str
    """Where this came from — a preset name or a file path, for messages."""

    digest: str
    """A short SHA-256 over the definition text, for the cover sheet (§ 8.8).

    § 8.8 asks for the name *or* the checksum of the definition underneath; it
    gets both, because a preset copied and bent carries the same name as the
    preset it came from and a name alone would not tell the two apart. Short
    rather than full: this is an identity check for a human comparing two
    sheets, not a signature."""


def load(source: Path | str, overrides: Mapping[str, Any] | None = None) -> Document:
    """Definition file to model (§ 3.6, seam 1).

    `overrides` are the command-line values, and they beat the definition
    without exception (§ 11).
    """
    path = Path(source)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as error:
        raise DefinitionError(f"cannot read {path}: {error.strerror}") from None
    return loads(text, overrides, source=str(path))


def loads(text: str, overrides: Mapping[str, Any] | None = None, *, source: str) -> Document:
    """The same, from text already in hand — presets take this path too."""
    _guard_expansion(text, source)
    raw = _parse(text, source)
    _reject_merge_keys(raw)

    _check_version(raw)
    data = {key: value for key, value in raw.items() if key != "defs"}
    data.pop("version")

    overrides = {key: value for key, value in (overrides or {}).items() if value is not None}

    generator_name = _pop_generator(data, raw, overrides)
    blade = generators.get(generator_name)

    handle = {key: data.pop(key) for key in list(data) if key in HANDLE_KEYS}
    _check_unknown_keys(data, blade.config_model, raw)
    _apply_overrides(handle, overrides)

    page = _section(PageSpec, handle.get("page") or {}, raw, "page")
    header = _section(Band, handle["header"], raw, "header") if handle.get("header") else None
    footer = _section(Band, handle["footer"], raw, "footer") if handle.get("footer") else None
    border = _section(BorderSpec, handle["border"], raw, "border") if handle.get("border") else None
    stamp = _section(StampSpec, handle["stamp"], raw, "stamp") if handle.get("stamp") else None
    pattern = _section(PatternSpec, handle.get("pattern") or {}, raw, "pattern")
    pages = _section(PagesSpec, handle.get("pages") or {}, raw, "pages")
    config = _section(blade.config_model, data, raw, None)
    pages, names, notices = _resolve_names(pages, overrides)
    notices += _hole_mark_notices(page)
    _check_fonts({"header": header, "footer": footer}, raw)

    return Document(
        version=SUPPORTED_VERSION,
        page=page,
        header=header,
        footer=footer,
        border=border,
        stamp=stamp,
        pattern=pattern,
        pages=pages,
        generator=generator_name,
        config=config,
        names=names,
        notices=notices,
        sheet=resolve_sheet(page),
        axes=blade.periodic_axes(config),
        source=source,
        digest=hashlib.sha256(text.encode("utf-8")).hexdigest()[:12],
    )


def _resolve_names(
    pages: PagesSpec, overrides: Mapping[str, Any]
) -> tuple[PagesSpec, list[str] | None, tuple[str, ...]]:
    """Settle the two modes of § 9.4 and lay one name out per page.

    | mode         | led by     | behaviour                                  |
    |--------------|------------|--------------------------------------------|
    | data-driven  | the list   | one sheet per entry — the default with a list |
    | fixed count  | the count  | entries repeated cyclically, or cut         |

    Which applies turns on whether a count was written down at all, so a bare
    `ctrlgrid millimeter-a4 --names class3b.txt` gives a sheet per child rather
    than the single page the default count would suggest.
    """
    source = overrides.get("names") or pages.names
    if not source:
        return pages, None, ()

    names = list(source)
    if not pages.count_was_given:
        # The data leads (§ 9.4).
        return pages.model_copy(update={"count": len(names)}), names, ()

    count = pages.count
    notices: tuple[str, ...] = ()
    if count < len(names):
        # The legitimate "let me look at three sheets first" case. Cutting is
        # fine as long as the number is said out loud (§ 9.4).
        notices = (f"using {count} of {len(names)} names",)
    # Short lists repeat cyclically; long ones are cut by the same expression.
    laid_out = [names[index % len(names)] for index in range(count)]
    return pages, laid_out, notices


def _check_fonts(bands: dict[str, Band | None], raw: CommentedMap) -> None:
    """Open every named font file here, where the line number is still known.

    § 10.3 refuses a font whose licence forbids embedding, and § 12 wants that
    refusal to point at the line that named it — which the writer, three seams
    away, could no longer do. Doing it here also means `check` catches it and
    the pre-flight rule of § 12 point 13 holds without any further work: the
    file is opened before any page exists.
    """
    for section, band in bands.items():
        if band is None or band.font.file is None:
            continue
        try:
            fonts.load_font(band.font.file, field=f"{section}.font.file")
        except DefinitionError as error:
            raise error.at(line=_line(raw, (section, "font", "file"))) from None


def _hole_mark_notices(page: PageSpec) -> tuple[str, ...]:
    """§ 8.7: warn when the punch marks will land on the pattern.

    A warning and not an error, and no space is reserved: hole centres at 12 mm
    against a 5 mm margin is simply what an ordinary sheet of paper looks like.
    Whoever wants them clear of the grid sets a wider `margin.inner`, and that
    is a design decision that stays with the user.
    """
    if not page.hole_marks or page.margin is None:
        return ()
    if page.margin.inner.um >= 12_000:
        return ()
    return (
        f"hole marks sit 12mm from the binding edge, inside a margin.inner of "
        f"{page.margin.inner.raw} — they will fall on the pattern. Set "
        "margin.inner to 15mm or more to keep them clear (§ 8.7)",
    )


def resolve_sheet(page: PageSpec) -> Sheet:
    """Turn a page section into physical geometry (§ 8.1, § 9.1).

    Sizes are stored portrait throughout — one convention for the format table
    and the device profiles alike — and `orientation` swaps them here.
    """
    table = formats()
    if page.format in table:
        paper = table[page.format]
        width, height = paper.width.um, paper.height.um
        default_margin = paper.margin
    elif _FREE_SIZE.match(page.format.strip()):
        width, height = _free_size(page.format)
        default_margin = FREE_MARGIN
    else:
        known = ", ".join(sorted(table))
        raise DefinitionError(
            f"unknown page format `{page.format}` (known: {known}). A free size is "
            "written as two measures, width first: 210x99mm, 8.5x11in (§ 9.1)",
            field="page.format",
        )

    if page.orientation == "landscape":
        width, height = height, width
    # The margin default is a property of the medium, not of the code (§ 8.1).
    margin = page.margin or Margin.uniform(default_margin)
    return Sheet(width=width, height=height, margin=margin)


#: What a free size gets where a format table entry would have carried its own
#: (§ 9.1: "then the general defaults apply"). 5 mm is the non-printable border
#: of most consumer printers (§ 8.1).
FREE_MARGIN = Length(um=5000, mm=5.0, raw="5mm")

#: Two measures with an `x` between them, width first. The unit may stand once
#: at the end or on each side; § 9.1 writes it once, and `210mmx99mm` is what
#: people type anyway.
_FREE_SIZE = re.compile(
    r"^(?P<x>[\d.,]+\s*[a-z%]*)\s*[xX×]\s*(?P<y>[\d.,]+\s*[a-z%]+)$", re.IGNORECASE
)


def _free_size(text: str) -> tuple[int, int]:
    """`210x99mm` to a pair of micrometre measures, taken exactly as written.

    **Not normalised to portrait**, unlike the format table and the device
    profiles. Those are data files with one convention; this is the user
    writing down a sheet, and § 9.1's own example — 210x99mm — is a wide strip.
    Standing it upright would hand back a sheet nobody asked for. `orientation`
    still swaps the two, whatever their source.
    """
    match = _FREE_SIZE.match(text.strip())
    assert match is not None  # only called after the same match succeeded
    x_text, y_text = match.group("x").strip(), match.group("y").strip()
    # A unit written once at the end governs both sides — the form § 9.1 uses.
    if not any(character.isalpha() or character == "%" for character in x_text):
        x_text += "".join(character for character in y_text if not character.isdigit()
                          and character not in ".,").strip()

    width = parse_length(x_text, field="page.format")
    height = parse_length(y_text, field="page.format")
    for side, value in (("width", width), ("height", height)):
        if value.um <= 0:
            raise DefinitionError(
                f"a page {side} of {value.raw} is not a sheet of paper — both measures of "
                "a free size must be positive (§ 9.1)",
                field="page.format",
            )
    return width.um, height.um


# --------------------------------------------------------------- data files


@lru_cache(maxsize=1)
def formats() -> dict[str, PaperFormat]:
    """The built-in format table (§ 9.1). A4 is world knowledge, not definition."""
    raw = _parse((DATA / "formats.yaml").read_text(encoding="utf-8"), "formats.yaml")
    table = {}
    for entry in raw["formats"]:
        table[entry["id"]] = PaperFormat(
            id=entry["id"],
            name=entry["name"],
            width=parse_length(entry["size"]["x"], field=f"formats.{entry['id']}.size.x"),
            height=parse_length(entry["size"]["y"], field=f"formats.{entry['id']}.size.y"),
            margin=parse_length(entry["margin"], field=f"formats.{entry['id']}.margin"),
            assumed_dpi=int(entry["assumed_dpi"]),
        )
    return table


@lru_cache(maxsize=1)
def devices() -> list[dict[str, Any]]:
    """The shipped device profiles (§ 9.2).

    Read raw for now: M1 has no px/mm conversion, and `ctrlgrid devices` shows
    `source` and `verified` precisely because device figures are the kind of
    data that spreads quietly and becomes quietly wrong.
    """
    raw = _parse((DATA / "devices.yaml").read_text(encoding="utf-8"), "devices.yaml")
    return list(raw["devices"])


def read_names(path: Path | str) -> list[str]:
    """Read a name list — one entry per line (§ 9.4).

    Encoding gets its own care because it is where this feature actually
    breaks: lists come out of spreadsheets, and those export CP1252 far more
    often than anyone expects. "invalid start byte" is useless then, so the
    message names the line and the byte and says what the likely cause is.
    """
    path = Path(path)
    try:
        data = path.read_bytes()
    except OSError as error:
        raise DefinitionError(f"cannot read the name list {path}: {error.strerror}") from None

    data = data.removeprefix(codecs.BOM_UTF8)
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as error:
        line = data.count(b"\n", 0, error.start) + 1
        column = error.start - (data.rfind(b"\n", 0, error.start) + 1) + 1
        raise DefinitionError(
            f"{path} is not valid UTF-8: line {line}, byte {error.start} "
            f"(character {column} of that line) is 0x{data[error.start]:02x}. "
            "Lists exported from a spreadsheet are often CP1252 — "
            "re-save the file as UTF-8 (§ 9.4)"
        ) from None

    # A trailing newline is not an empty name, and neither is a blank line
    # someone left in the middle. A nameless sheet is not a thing anyone means.
    names = [line.strip() for line in text.splitlines()]
    names = [name for name in names if name]
    if not names:
        raise DefinitionError(f"the name list {path} holds no entries")
    return names


def preset_names() -> list[str]:
    return sorted(path.stem for path in PRESETS.glob("*.yaml"))


def preset_text(name: str) -> str:
    path = PRESETS / f"{name}.yaml"
    if not path.is_file():
        known = ", ".join(preset_names())
        close = difflib.get_close_matches(name, preset_names(), n=1)
        hint = f" — did you mean `{close[0]}`?" if close else ""
        raise DefinitionError(f"unknown preset `{name}`{hint} (available: {known})")
    return path.read_text(encoding="utf-8")


def load_preset(name: str, overrides: Mapping[str, Any] | None = None) -> Document:
    """A preset is an ordinary definition file, never a special path (§ 9.3)."""
    return loads(preset_text(name), overrides, source=name)


# ------------------------------------------------------------------ parsing


def _parse(text: str, source: str) -> CommentedMap:
    yaml = YAML(typ="rt")
    try:
        raw = yaml.load(text)
    except YAMLError as error:
        raise DefinitionError(f"{source} is not valid YAML: {_yaml_message(error)}") from None
    if raw is None:
        raise DefinitionError(f"{source} is empty")
    if not isinstance(raw, CommentedMap):
        raise DefinitionError(f"{source} must be a mapping of keys at the top level")
    return raw


def _yaml_message(error: YAMLError) -> str:
    mark = getattr(error, "problem_mark", None)
    problem = getattr(error, "problem", str(error))
    return f"{problem} (line {mark.line + 1}, column {mark.column + 1})" if mark else problem


def _reject_merge_keys(node: Any, path: str = "") -> None:
    """§ 5.4: merge keys are inheritance the parser happens to bring along."""
    if isinstance(node, CommentedMap):
        if getattr(node, "merge", None):
            raise DefinitionError(
                "merge keys (`<<`) are not supported — copy the block instead (§ 5.4)",
                field=path or None,
                line=node.lc.line + 1 if node.lc.line is not None else None,
            )
        for key, value in node.items():
            _reject_merge_keys(value, f"{path}.{key}" if path else str(key))
    elif isinstance(node, CommentedSeq):
        for index, value in enumerate(node):
            _reject_merge_keys(value, f"{path}.{index}")


def _guard_expansion(text: str, source: str) -> None:
    """Refuse a definition that expands beyond all reason (§ 5.4).

    Nested aliases stack into a YAML bomb, and the safe loading mode does not
    protect against it — it prevents arbitrary objects being constructed, not
    the expansion. Since defs get copied out of other people's repositories, an
    upper bound is required, with a clear refusal instead of a memory error.

    The measurement happens on the **composed node graph**, before anything is
    constructed. There each anchor is one node and an alias is a reference to
    it, so the expanded size can be computed by memoised addition: linear work
    for a number that would take exponential time to reach by expanding.
    """
    import io

    try:
        root = YAML(typ="rt").compose(io.StringIO(text))
    except YAMLError:
        return  # not valid YAML; _parse reports that properly in a moment
    if root is None:
        return

    sizes: dict[int, int] = {}

    def size(node: Any) -> int:
        cached = sizes.get(id(node))
        if cached is not None:
            return cached
        total = 1
        if isinstance(node, MappingNode):
            total += sum(size(key) + size(value) for key, value in node.value)
        elif isinstance(node, SequenceNode):
            total += sum(size(value) for value in node.value)
        sizes[id(node)] = total
        return total

    if size(root) > EXPANSION_LIMIT:
        raise DefinitionError(
            f"{source}: alias expansion exceeds {EXPANSION_LIMIT:,} nodes. Nested aliases "
            "multiply, and a definition that large cannot be meant seriously (§ 5.4)"
        )


def _check_version(raw: CommentedMap) -> None:
    if "version" not in raw:
        raise DefinitionError(
            f"the version line is mandatory — add `version: {SUPPORTED_VERSION}` "
            "at the top of the file (§ 5.1)"
        )
    if raw["version"] != SUPPORTED_VERSION:
        raise DefinitionError(
            f"version {raw['version']} is not supported; this tool understands "
            f"version {SUPPORTED_VERSION}",
            line=_line(raw, ("version",)),
        )


def _pop_generator(
    data: dict[str, Any], raw: CommentedMap, overrides: Mapping[str, Any]
) -> str:
    name = overrides.get("generator") or data.pop("generator", None)
    if not name:
        known = ", ".join(sorted(generators.REGISTRY))
        raise DefinitionError(f"no `generator` given — one of: {known} (§ 5.2)")
    data.pop("generator", None)
    try:
        generators.get(name)
    except DefinitionError as error:
        raise error.at(line=_line(raw, ("generator",))) from None
    return str(name)


def _check_unknown_keys(
    rest: dict[str, Any], config_model: type[BaseModel], raw: CommentedMap
) -> None:
    """§ 12 point 4: an unknown key is an error, with a suggestion if one is close."""
    known = HANDLE_KEYS | set(config_model.model_fields)
    for key in rest:
        if key in DEFERRED_KEYS:
            raise DefinitionError(
                f"`{key}` {DEFERRED_KEYS[key]}", line=_line(raw, (key,))
            )
        if key not in known:
            raise DefinitionError(
                _unknown(key, known), field=None, line=_line(raw, (key,))
            )


def _unknown(key: str, known: set[str]) -> str:
    close = difflib.get_close_matches(key, sorted(known), n=1)
    hint = f" — did you mean `{close[0]}`?" if close else ""
    return f"unknown key `{key}`{hint}"


def _apply_overrides(handle: dict[str, Any], overrides: Mapping[str, Any]) -> None:
    """The command line beats the definition, always and without exception (§ 11)."""
    if "pages" in overrides:
        handle["pages"] = {**(handle.get("pages") or {}), "count": overrides["pages"]}
    if overrides.get("cover"):
        # § 8.8: `--cover` switches it on. Only on — the flag is a wish for
        # this one run, and there is no flag that unwishes what the definition
        # asked for, because `--no-cover` would be a fifth spelling of nothing.
        handle["pages"] = {**(handle.get("pages") or {}), "cover": True}
    for key in ("format", "orientation"):
        if key in overrides:
            handle["page"] = {**(handle.get("page") or {}), key: overrides[key]}
    if "stamp" in overrides:
        # § 8.6: the flag is the intended route, so it replaces the section
        # outright rather than merging into it.
        handle["stamp"] = {**(handle.get("stamp") or {}), "text": overrides["stamp"]}


def _section(
    model: type[BaseModel], data: Any, raw: CommentedMap, prefix: str | None
) -> Any:
    try:
        return model.model_validate(data)
    except ValidationError as error:
        raise _translate(error, model, raw, prefix) from None


def _translate(
    error: ValidationError, model: type[BaseModel], raw: CommentedMap, prefix: str | None
) -> DefinitionError:
    """Turn a pydantic error into one a user can act on (§ 12)."""
    # A misspelled key raises twice: the key is unknown *and* the real one is
    # missing. Only the first explains the second, so it goes first.
    errors = error.errors()
    first = next((e for e in errors if e["type"] == "extra_forbidden"), errors[0])
    loc = tuple(str(part) for part in first["loc"])
    full = (prefix, *loc) if prefix else loc
    field = ".".join(full)

    if first["type"] == "extra_forbidden":
        known = _fields_at(model, loc[:-1]) or set(model.model_fields)
        message = _unknown(loc[-1], known)
        field = ".".join(full[:-1]) or None
    else:
        message = first["msg"].removeprefix("Value error, ")

    return DefinitionError(message, field=field, line=_line(raw, full))


def _fields_at(model: type[BaseModel], loc: tuple[str, ...]) -> set[str] | None:
    """The field names of the model reached by walking `loc` — for suggestions."""
    current: Any = model
    for part in loc:
        if not (isinstance(current, type) and issubclass(current, BaseModel)):
            return None
        if part.isdigit():
            continue
        field = current.model_fields.get(part)
        if field is None:
            return None
        current = _model_inside(field.annotation)
        if current is None:
            return None
    if isinstance(current, type) and issubclass(current, BaseModel):
        return set(current.model_fields)
    return None


def _model_inside(annotation: Any) -> Any:
    """The model class inside `list[Family]`, `Family | None` and friends."""
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        return annotation
    for argument in getattr(annotation, "__args__", ()):
        found = _model_inside(argument)
        if found is not None:
            return found
    return None


def _line(raw: Any, loc: tuple[str, ...]) -> int | None:
    """The 1-based line of the deepest key of `loc` that can still be found.

    Falling back to the parent is deliberate: pointing at the enclosing block
    is still far better than pointing nowhere.
    """
    line = None
    node: Any = raw
    for part in loc:
        try:
            if isinstance(node, CommentedMap) and part in node:
                line = node.lc.key(part)[0] + 1
                node = node[part]
            elif isinstance(node, CommentedSeq) and part.isdigit():
                index = int(part)
                line = node.lc.item(index)[0] + 1
                node = node[index]
            else:
                break
        except (KeyError, IndexError, TypeError):
            break
    return line


def iter_presets() -> Iterator[tuple[str, str]]:
    for name in preset_names():
        yield name, preset_text(name)
