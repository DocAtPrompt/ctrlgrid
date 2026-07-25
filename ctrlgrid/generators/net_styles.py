"""The box styles of `net` (§ 7.14) — each a list of panels, and nothing else.

A style says which faces and flaps exist and where they sit; `net_geometry`
turns that into cuts and creases by itself. So a style never traces an outline,
and adding one is a list rather than a rewrite.

Two conventions run through both styles, and both are **choices**, written here
and in § 7.14 so nobody has to reverse-engineer them from the arithmetic:

* **Dimensions are inner.** The number a user has is the thing that must go in
  the box, so that is the number they type.
* **Thickness has one rule.** A panel that closes *over* another layer is
  widened by `thickness`; a flap that slides *inside* one is shortened by it. At
  `thickness: 0` every allowance vanishes and the net is the ideal one.

Every flap spans its attachment edge completely and tapers only on its free
side — that is what lets the shared-edge rule be exact (§ 7.14), and it is how a
carton is cut in any case.
"""

from __future__ import annotations

from ctrlgrid.generators.net_geometry import Panel
from ctrlgrid.marks import Point, Um

#: How far a tab's free side is drawn in from its fold, so it slides rather than
#: catches. A fixed measure, like the cover sheet's figures (§ 8.8): a taper is
#: a property of tabs, not a setting.
TAPER: Um = 2000
TONGUE_TAPER: Um = 3000

#: The cap on an `auto` dust flap. Longer than this they collide over a long
#: box and buy nothing.
DUST_CAP: Um = 25_000


def _rect(x0: Um, y0: Um, x1: Um, y1: Um, name: str) -> Panel:
    return Panel(
        points=(Point(x0, y0), Point(x1, y0), Point(x1, y1), Point(x0, y1)), name=name
    )


def tray(
    *, length: Um, width: Um, height: Um, thickness: Um, glue_tab: Um, **_ignored
) -> list[Panel]:
    """An open box: a base, four walls, and a glue tab at each end of the two
    end walls. The tabs wrap around the wall they glue to and lose that much
    reach, which is the thickness rule's shortening half."""
    tab = max(glue_tab - thickness, TAPER + 1000)
    panels = [
        _rect(0, 0, length, width, "base"),
        _rect(0, -height, length, 0, "wall-south"),
        _rect(0, width, length, width + height, "wall-north"),
        _rect(-height, 0, 0, width, "wall-west"),
        _rect(length, 0, length + height, width, "wall-east"),
    ]
    # A corner tab spans its wall's full height (so its fold edge matches the
    # wall's edge exactly) and tapers on its free side.
    for name, x_fold, direction, y0, y1 in (
        ("tab-sw", 0, -1, -height, 0),
        ("tab-se", length, +1, -height, 0),
        ("tab-nw", 0, -1, width, width + height),
        ("tab-ne", length, +1, width, width + height),
    ):
        far = x_fold + direction * tab
        panels.append(
            Panel(
                points=(
                    Point(x_fold, y0),
                    Point(far, y0 + TAPER) if y0 < y1 else Point(far, y0 - TAPER),
                    Point(far, y1 - TAPER),
                    Point(x_fold, y1),
                ),
                name=name,
            )
        )
    return panels


def tuck_top(
    *,
    length: Um,
    width: Um,
    height: Um,
    thickness: Um,
    glue_tab: Um,
    tuck: Um,
    dust: Um | None,
    **_ignored,
) -> list[Panel]:
    """The classic carton: a strip of four walls with a glue tab, and a lid with
    a tongue at each end, supported by dust flaps.

    Each panel of the strip wraps one more layer of material than the one before
    it, so each is widened by `thickness` — that is the rule's widening half,
    and it is what makes the box close instead of bind.
    """
    t = thickness
    widths = [length, width + t, length + t, width + t]  # front, side, back, side
    tab = max(glue_tab - t, TAPER + 1000)
    lid_depth = width + t
    tongue = max(tuck - t, TONGUE_TAPER + 1000)
    dust_depth = max((dust if dust is not None else min(length // 3, DUST_CAP)) - t, 1000)

    panels: list[Panel] = []
    x = 0
    starts: list[tuple[int, int]] = []          # (x0, x1) of each wall panel
    for index, panel_width in enumerate(widths):
        panels.append(_rect(x, 0, x + panel_width, height, f"wall-{index}"))
        starts.append((x, x + panel_width))
        x += panel_width

    # The glue tab closes the tube, on the far end of the last wall.
    panels.append(
        Panel(
            points=(
                Point(x, 0),
                Point(x + tab, TAPER),
                Point(x + tab, height - TAPER),
                Point(x, height),
            ),
            name="tab-glue",
        )
    )

    # The closures. The lid hangs off the back wall (panel 2); the dust flaps
    # off the two side panels; the same again mirrored below the strip.
    for side, sign, base in (("top", +1, height), ("bottom", -1, 0)):
        x0, x1 = starts[2]
        lid_far = base + sign * lid_depth
        panels.append(
            Panel(
                points=(
                    Point(x0, base), Point(x1, base),
                    Point(x1, lid_far), Point(x0, lid_far),
                ),
                name=f"lid-{side}",
            )
        )
        tongue_far = lid_far + sign * tongue
        panels.append(
            Panel(
                points=(
                    Point(x0, lid_far),
                    Point(x1, lid_far),
                    Point(x1 - TONGUE_TAPER, tongue_far),
                    Point(x0 + TONGUE_TAPER, tongue_far),
                ),
                name=f"tongue-{side}",
            )
        )
        for number, index in enumerate((1, 3), start=1):
            dx0, dx1 = starts[index]
            far = base + sign * dust_depth
            panels.append(
                Panel(
                    points=(
                        Point(dx0, base),
                        Point(dx1, base),
                        Point(dx1 - TAPER, far),
                        Point(dx0 + TAPER, far),
                    ),
                    name=f"dust-{side}-{number}",
                )
            )
    return panels


STYLES = {"tray": tray, "tuck_top": tuck_top}


def net_panels(style: str, **spec) -> list[Panel]:
    """Every panel of one net, in a fixed order (§ 10.1)."""
    return STYLES[style](**spec)
