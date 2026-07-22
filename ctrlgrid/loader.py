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

import difflib
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ValidationError
from ruamel.yaml import YAML, YAMLError
from ruamel.yaml.comments import CommentedMap, CommentedSeq
from ruamel.yaml.nodes import MappingNode, SequenceNode

from ctrlgrid import generators
from ctrlgrid.errors import DefinitionError
from ctrlgrid.model import Band, Margin, PageSpec, PagesSpec, PatternSpec
from ctrlgrid.pages import Sheet
from ctrlgrid.units import Length, parse_length

DATA = Path(__file__).parent / "data"
PRESETS = DATA / "presets"

SUPPORTED_VERSION = 1

#: Top-level keys owned by the handle (§ 3). Everything else on the top level
#: belongs to the blade and is validated by its own config model.
HANDLE_KEYS = {"version", "defs", "generator", "page", "header", "footer", "pattern", "pages"}

#: Keys the specification defines on the top level and this milestone does not
#: implement. Named, so they cannot be mistaken for typos.
DEFERRED_KEYS = {
    "border": "arrives with milestone M2 (§ 5.2)",
    "stamp": "arrives with milestone M2 (§ 8.6)",
}

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
    pattern: PatternSpec
    pages: PagesSpec
    generator: str
    config: Any
    """The blade's own section, validated by its `config_model` (§ 3.6)."""

    sheet: Sheet
    source: str
    """Where this came from — a preset name or a file path, for messages."""


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
    pattern = _section(PatternSpec, handle.get("pattern") or {}, raw, "pattern")
    pages = _section(PagesSpec, handle.get("pages") or {}, raw, "pages")
    config = _section(blade.config_model, data, raw, None)

    return Document(
        version=SUPPORTED_VERSION,
        page=page,
        header=header,
        footer=footer,
        pattern=pattern,
        pages=pages,
        generator=generator_name,
        config=config,
        sheet=resolve_sheet(page),
        source=source,
    )


def resolve_sheet(page: PageSpec) -> Sheet:
    """Turn a page section into physical geometry (§ 8.1, § 9.1).

    Sizes are stored portrait throughout — one convention for the format table
    and the device profiles alike — and `orientation` swaps them here.
    """
    table = formats()
    if page.format not in table:
        known = ", ".join(sorted(table))
        raise DefinitionError(
            f"unknown page format `{page.format}` (known: {known}). "
            "Free sizes such as 210x99mm arrive with milestone M2 (§ 9.1)",
            field="page.format",
        )
    paper = table[page.format]
    width, height = paper.width.um, paper.height.um
    if page.orientation == "landscape":
        width, height = height, width
    # The margin default is a property of the medium, not of the code (§ 8.1).
    margin = page.margin or Margin.uniform(paper.margin)
    return Sheet(width=width, height=height, margin=margin)


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
    for key in ("format", "orientation"):
        if key in overrides:
            handle["page"] = {**(handle.get("page") or {}), key: overrides[key]}


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
