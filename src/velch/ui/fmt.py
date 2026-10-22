"""One numeric formatter for the whole interface.

Before this module the same 1/3-octave band could read ``39.3725`` on the axis, ``39.4`` in the
table and ``39 Hz`` on the card, and a limit of 49 790 N was printed as ``4.979e+04`` — which, when
the layout clipped it to ``4.97``, read as 4.97 N.  Numbers in an engineering tool are conclusions,
so they get one exit.

Rules, in order:

* non-finite → ``—`` (missing data is not zero)
* exact zero → ``0``
* ``1e-3 <= |v| < 1e4`` → four significant digits, plain decimal (``3089``, ``0.4738``)
* otherwise, when a unit is known and the scale is an SI prefix of 3 → prefix form
  (``49.79 kN``, ``44.4 µm``); without a unit, ``3.09e+04`` is still better than 30500.7
"""
from __future__ import annotations

import math

SI_PREFIXES: tuple[tuple[int, str], ...] = (
    (9, "G"), (6, "M"), (3, "k"), (0, ""), (-3, "m"), (-6, "µ"), (-9, "n"), (-12, "p"),
)

#: Units that may take an SI prefix.  ``°``, ``%``, ``/`` ratios and counts must not: "4.7 k%"
#: is not a thing, and a prefixed count would be a lie about a discrete quantity.
PREFIXABLE = frozenset({"N", "m", "s", "m/s", "m/s²", "Hz", "rad", "rad/s", "N·m", "N·s/m",
                        "Pa", "kg", "W", "V", "A", "m⁻¹", "N/m"})


def fmt_number(value: float, unit: str = "", *, digits: int = 4, prefix: bool = True) -> str:
    """Format one measurement for display, appending ``unit`` when it is given."""

    try:
        number = float(value)
    except (TypeError, ValueError):
        return "—"
    if not math.isfinite(number):
        return "—"
    if number == 0.0:
        return "0" if not unit else f"0 {unit}"
    magnitude = abs(number)

    if 1e-3 <= magnitude < 1e4:
        text = f"{number:.{digits}g}"
    elif prefix and unit in PREFIXABLE:
        exponent = int(math.floor(math.log10(magnitude) / 3.0) * 3)
        exponent = max(-12, min(9, exponent))
        scaled = number / (10.0 ** exponent)
        name = dict(SI_PREFIXES).get(exponent)
        if name is None:
            text = f"{number:.{digits - 1}e}"
            return text if not unit else f"{text} {unit}"
        if 1e-3 <= abs(scaled) < 1e4:
            return f"{scaled:.{digits}g} {name}{unit}"
        text = f"{scaled:.{digits}g}"
        return f"{text} {name}{unit}"
    else:
        text = f"{number:.{digits - 1}e}"

    return text if not unit else f"{text} {unit}"


def fmt_percent(ratio: float, *, digits: int = 4) -> str:
    """A ratio as a percentage; used for "how far to the limit" readings."""

    if not math.isfinite(float(ratio)):
        return "—"
    return f"{float(ratio) * 100.0:.{digits}g} %"


def fmt_pair(value: float, limit: float, unit: str = "") -> str:
    """``value / limit`` where both sides share one scale so the comparison stays readable."""

    if not math.isfinite(float(value)) or not math.isfinite(float(limit)):
        return "—"
    # Choose the scale from the limit (the stable side), then print the value on the same scale,
    # so "3896 / 49.79 kN" never degenerates into two different exponents.
    def scaled(number: float) -> tuple[float, str]:
        if limit == 0.0:
            return number, unit
        magnitude = abs(float(limit))
        if 1e-3 <= magnitude < 1e4 or unit not in PREFIXABLE:
            return number, unit
        exponent = max(-12, min(9, int(math.floor(math.log10(magnitude) / 3.0) * 3)))
        name = dict(SI_PREFIXES).get(exponent, "")
        return number / (10.0 ** exponent), f"{name}{unit}"

    value_scaled, unit_scaled = scaled(float(value))
    limit_scaled, _ = scaled(float(limit))
    return f"{fmt_number(value_scaled, '', prefix=False)} / {fmt_number(limit_scaled, unit_scaled)}"
