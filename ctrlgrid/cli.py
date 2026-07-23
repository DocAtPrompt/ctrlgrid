"""The command line (§ 11).

**The command line beats the definition — always and without exception.** A
ranking with exceptions would not be memorable; this one is. The definition
supplies the default, the call supplies the deviation for this one run.

Two rules about output, both from § 11.3:

* the process writes the file itself, into Downloads unless `-o` says otherwise
* an existing file is never overwritten silently — comparable tools are
  criticised by name for exactly that

And one from § 8.2: every successful run names the print setting concretely
("Actual size" / 100 %), because the commonest complaint about every tool in
this space is a print driver quietly scaling the sheet to 96 %.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Annotated

import typer
from typer.core import TyperGroup

from ctrlgrid import generators
from ctrlgrid.errors import CtrlGridError
from ctrlgrid.loader import (
    Document,
    devices,
    load,
    load_preset,
    preset_names,
    preset_text,
    read_names,
)
from ctrlgrid.pages import Geometry, build, preflight, sheet_plan
from ctrlgrid.writers.pdf import PdfWriter


class PresetAsCommand(TyperGroup):
    """`ctrlgrid millimeter-a4` is the ordinary call, not a subcommand.

    Generating is what the tool is for, so it needs no command word: anything
    that is not one of the four listed commands is handed to `generate`. That
    covers both `ctrlgrid millimeter-a4` and `ctrlgrid -d my-def.yaml`, the two
    forms § 11 shows first.
    """

    def parse_args(self, ctx, args: list[str]) -> list[str]:
        if args and args[0] not in self.commands and args[0] not in ("-h", "--help"):
            args = ["generate", *args]
        return super().parse_args(ctx, args)


app = typer.Typer(
    cls=PresetAsCommand,
    add_completion=False,
    no_args_is_help=True,
    help="Dimensionally accurate PDF templates. What says 5 mm measures 5 mm.",
)


@app.command()
def generate(
    target: Annotated[
        str | None, typer.Argument(help="Preset name; see `ctrlgrid presets`.")
    ] = None,
    definition: Annotated[
        Path | None, typer.Option("-d", "--def", help="Own definition file instead of a preset.")
    ] = None,
    out: Annotated[
        Path | None, typer.Option("-o", "--out", help="Output path; default is Downloads.")
    ] = None,
    pages: Annotated[int | None, typer.Option(help="Page count; overrides pages.count.")] = None,
    names: Annotated[
        Path | None,
        typer.Option(help="Name list, one entry per line — a sheet per entry (§ 9.4)."),
    ] = None,
    format: Annotated[str | None, typer.Option(help="Paper format, e.g. a4, letter.")] = None,
    device: Annotated[
        str | None,
        typer.Option(help="Device profile instead of a format; see `ctrlgrid devices` (§ 9.2)."),
    ] = None,
    orientation: Annotated[str | None, typer.Option(help="portrait | landscape")] = None,
    stamp: Annotated[
        str | None,
        typer.Option(help='Full-page diagonal overprint, e.g. --stamp "DRAFT" (§ 8.6).'),
    ] = None,
    seed: Annotated[
        int | None,
        typer.Option(help="Seed for procedural blades, e.g. `maze` (§ 7.5)."),
    ] = None,
    nup: Annotated[
        str | None,
        typer.Option(help="Impose pages CxR on a sheet, never scaled, e.g. 2x2 (§ 14)."),
    ] = None,
    nup_sheet: Annotated[
        str | None,
        typer.Option(help="Sheet format for --nup (default a4)."),
    ] = None,
    crop_marks: Annotated[
        bool,
        typer.Option("--crop-marks", help="Draw cut guides in the imposition margin (§ 14)."),
    ] = False,
    strict: Annotated[
        bool,
        typer.Option("--strict", help="Turn media warnings into errors (§ 12.1)."),
    ] = False,
    cover: Annotated[
        bool,
        typer.Option("--cover", help="Extra first sheet: calibration and settings (§ 8.8)."),
    ] = False,
    force: Annotated[bool, typer.Option("--force", help="Overwrite an existing file.")] = False,
    quiet: Annotated[bool, typer.Option("--quiet", help="Report only the output path.")] = False,
) -> None:
    """Build a PDF from a preset or a definition file."""
    with _reporting():
        document = _open(
            target,
            definition,
            _overrides(
                pages, format, device, orientation, names, stamp, cover, seed, strict,
                nup, nup_sheet, crop_marks,
            ),
        )
        destination = _destination(out, target, definition, force)
        geometry = build(document, _writer_for(destination, document))
        _report(document, destination, geometry, quiet=quiet)


@app.command()
def check(
    file: Annotated[Path, typer.Argument(help="Definition file to validate.")],
    strict: Annotated[
        bool,
        typer.Option("--strict", help="Turn media warnings into errors (§ 12.1)."),
    ] = False,
) -> None:
    """Validate a definition and write nothing (§ 11).

    Runs the same pre-flight as a real run: units, keys, geometry, and every
    page measured for text that does not fit (§ 12). With `--strict`, a media
    warning (§ 12.1) fails the check — what a CI run needs to guard a preset set.
    """
    with _reporting():
        document = load(file, {"strict": True} if strict else None)
        # The writer is used for its metrics only; it touches no file until
        # `begin_document`, and check never gets that far (§ 10.2).
        geometry, _, _, _ = preflight(document, PdfWriter(file))
        typer.echo(
            f"{file}: valid — {document.pages.count} page(s), "
            f"generator `{document.generator}`"
        )
        for notice in (*document.notices, *geometry.notices):
            typer.echo(f"  note: {notice}")


@app.command()
def presets() -> None:
    """List the shipped presets. They are the documentation too (§ 9.3)."""
    for name in preset_names():
        typer.echo(name)


@app.command()
def show(name: Annotated[str, typer.Argument(help="Preset to print.")]) -> None:
    """Print a preset's definition, ready to copy and bend."""
    with _reporting():
        typer.echo(preset_text(name), nl=False)


@app.command("devices")
def devices_command() -> None:
    """List the device profiles, with where their figures come from (§ 9.2)."""
    for device in devices():
        typer.echo(
            f"{device['id']:<24} {device['pixels']['x']}x{device['pixels']['y']} px  "
            f"{device['density']}  verified {device['verified']}  — {device['source']}"
        )


# ----------------------------------------------------------------- internals


class _reporting:
    """Turn any deliberate error into a message and a non-zero exit (§ 12)."""

    def __enter__(self) -> None:
        return None

    def __exit__(self, kind, error, traceback) -> bool:
        if isinstance(error, CtrlGridError):
            typer.secho(f"error: {error}", fg=typer.colors.RED, err=True)
            raise typer.Exit(1) from None
        return False


def _overrides(
    pages: int | None,
    format: str | None,
    device: str | None,
    orientation: str | None,
    names: Path | None = None,
    stamp: str | None = None,
    cover: bool = False,
    seed: int | None = None,
    strict: bool = False,
    nup: str | None = None,
    nup_sheet: str | None = None,
    crop_marks: bool = False,
) -> dict:
    if format is not None and device is not None:
        # § 9.2: two answers to "what medium". The loader would refuse them in a
        # definition; refuse them on the command line for the same reason.
        raise CtrlGridError("--format and --device name the medium two ways — give one (§ 9.2)")
    if nup is None and (nup_sheet is not None or crop_marks):
        raise CtrlGridError("--nup-sheet and --crop-marks only mean something with --nup (§ 14)")
    return {
        "pages": pages,
        "format": format,
        "device": device,
        "orientation": orientation,
        "names": read_names(names) if names is not None else None,
        "stamp": stamp,
        # § 8.8: a flag that only ever switches the cover on. `False` is not
        # "no cover", it is "the definition decides", which is why it is
        # dropped here rather than sent as an override.
        "cover": True if cover else None,
        # § 7.5: a blade key rather than a handle one, and the only one the
        # command line reaches into — a run's seed is a property of the run.
        "seed": seed,
        # § 12.1: only ever switches strictness on, like --cover.
        "strict": True if strict else None,
        # § 14: imposition is a property of the print, so it is command-line
        # only. `nup` present is what turns it on; the loader resolves the rest.
        "nup": nup,
        "nup_sheet": nup_sheet,
        "crop_marks": True if crop_marks else None,
    }


def _open(target: str | None, definition: Path | None, overrides: dict) -> Document:
    if definition is not None:
        return load(definition, overrides)
    if target is not None:
        return load_preset(target, overrides)
    raise CtrlGridError(
        "give a preset name or a definition file with -d. "
        "`ctrlgrid presets` lists what is available"
    )


def _writer_for(destination: Path, document: Document):
    """Pick the writer by the output extension (§ 10.4).

    `.png` rasters at the medium's resolution; anything else is PDF, the v1
    default. The PNG writer needs the dpi and the physical sheet count up front
    so it can number its files without buffering them all.
    """
    if destination.suffix.lower() != ".png":
        return PdfWriter(destination)
    from ctrlgrid.media import _dpi
    from ctrlgrid.pages import sheet_plan
    from ctrlgrid.writers.png import PngWriter

    pages = document.pages.count * sheet_plan(document).per_item
    sheets = pages if document.nup is None else -(-pages // document.nup.per_sheet)
    return PngWriter(destination, dpi=_dpi(document), sheets=sheets)


def _destination(
    out: Path | None, target: str | None, definition: Path | None, force: bool
) -> Path:
    if out is None:
        stem = target or (definition.stem if definition else "ctrlgrid")
        downloads = Path.home() / "Downloads"
        out = (downloads if downloads.is_dir() else Path.cwd()) / f"{stem}.pdf"
    if out.exists() and not force:
        raise CtrlGridError(f"{out} exists — pass --force to overwrite it (§ 11.3)")
    return out


def _report(document: Document, path: Path, geometry: Geometry, *, quiet: bool) -> None:
    if quiet:
        typer.echo(str(path))
        return
    typer.echo(str(path))
    pages = document.pages.count * sheet_plan(document).per_item
    typer.echo(f"  {pages} page(s), {document.sheet.width / 1000:.0f} x "
               f"{document.sheet.height / 1000:.0f} mm")
    if document.nup is not None:
        nup = document.nup
        sheets = -(-pages // nup.per_sheet)  # ceil
        typer.echo(
            f"  imposed {nup.cols}x{nup.rows} on {nup.sheet_name} "
            f"({nup.sheet_width / 1000:.0f} x {nup.sheet_height / 1000:.0f} mm) — "
            f"{sheets} sheet(s), at 100 %, cut to size"
        )
    blade = generators.get(document.generator)
    for line in blade.describe(document.config):
        typer.echo(f"  {line}")
    # Said once per run, never per page: a list that was cut (§ 9.4) or a
    # setting that cannot take effect where it stands (§ 8.3).
    for notice in (*document.notices, *geometry.notices):
        typer.echo(f"  note: {notice}")
    # § 8.2: we cannot stop a print driver scaling, so we name the setting.
    typer.echo("  print at 'Actual size' / 100 % — not 'Fit to page', or it is not to scale")


def main() -> int:
    try:
        app()
    except SystemExit as exit_code:
        return int(exit_code.code or 0)
    return 0


if __name__ == "__main__":
    sys.exit(main())
