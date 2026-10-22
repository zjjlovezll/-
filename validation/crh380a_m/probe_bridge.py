"""Does a coarse contact-geometry table bridge the frog groove?

Hypothesis: Simpack builds its contact geometry table from the same .prr files
but samples it on a grid (`rail.r.prof.disc`, `cont_disc_delta`).  A grid wider
than the groove would replace the 1.3 mm-deep, ~20 mm-wide valley by the
surrounding crown, which is exactly the difference we measured (our wheel needs
a 0.66 mm drop, Simpack's sits 0.18 mm *into* the same station).

This probe answers it quantitatively: put the wheel at the static stance, merge
the rail bodies into one surface, dilate it laterally by a half-width ``w``
(rolling max = the highest point a patch of width 2w can touch) and report the
worst clearance over the frog stations for several ``w``.

    clearance(s, w) = -max_y [ z_rail(y) **dilated by w** - z_wheel(y) ]

Positive = the wheel still has to drop this far; <=0 = contact exists.

Usage: python probe_bridge.py <case.json> [s_lo s_hi ds_mm] [sink_mm]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE.parents[1] / "src"))

from velch.profiles import load_profile  # noqa: E402

HALF_WIDTHS_MM = (0.0, 2.0, 5.0, 8.0, 10.0, 15.0, 20.0, 30.0)


def to_graph(spec: dict, surface: str, base: Path | None = None):
    scale = 1e-3 if spec.get("units", "m") == "mm" else 1.0
    path = Path(spec["file"])
    if not path.is_absolute() and base is not None:
        # Body CSVs are stored next to the case file, not next to the CWD.
        path = base / path
    return load_profile(
        path, file_format=spec.get("format", "csv"), surface=surface,
        y_scale_m=scale, z_scale_m=scale,
        y_sign=int(spec.get("y_sign", 1)), z_sign=int(spec.get("z_sign", 1)),
        y_offset_m=float(spec.get("y_offset_m", 0.0)),
        z_offset_m=float(spec.get("z_offset_m", 0.0)),
    )


def build(case_path: Path):
    case = json.loads(case_path.read_text(encoding="utf-8"))
    # The right-hand rail sits at +y.  The gauge offset lives in each station's
    # profile spec, not on the template, so score the template by the offsets of
    # its stations and fall back to the body count.
    def _score(t: dict) -> tuple[float, int]:
        specs = list(t.get("stations", []))
        for body in t.get("bodies") or ():
            specs.extend(body.get("stations", []))
        offsets = [float(s["profile"].get("y_offset_m", 0.0)) for s in specs]
        return (max(offsets) if offsets else 0.0, len(t.get("bodies") or ()))

    template = max(case["rail_templates"], key=_score)
    raw_bodies = template.get("bodies") or [
        {"id": template.get("id", "rail"), "stations": template["stations"]}
    ]
    wheel_spec = next(w for w in case["wheels"] if float(w.get("lateral_offset_m", 0)) > 0)
    wheel = to_graph(wheel_spec["profile"], "wheel_lower", case_path.parent)
    lat = float(wheel_spec["lateral_offset_m"])
    bodies = []
    for body in raw_bodies:
        stations = sorted(body["stations"], key=lambda st: st["s_m"])
        bodies.append(
            (
                body["id"],
                [st["s_m"] for st in stations],
                [to_graph(st["profile"], "rail_top", case_path.parent) for st in stations],
            )
        )
    return case, bodies, wheel, lat


def merged_surface(bodies, s: float, grid: np.ndarray) -> np.ndarray:
    """Highest rail surface over all bodies that cover ``s`` (NaN free)."""
    best = np.full(grid.shape, -np.inf)
    for _name, s_list, graphs in bodies:
        if not (s_list[0] - 1e-9 <= s <= s_list[-1] + 1e-9):
            continue
        idx = int(np.searchsorted(s_list, s))
        idx = min(max(idx, 1), len(s_list) - 1)
        w = 0.0 if s_list[idx] == s_list[idx - 1] else (s - s_list[idx - 1]) / (s_list[idx] - s_list[idx - 1])
        ga, gb = graphs[idx - 1], graphs[idx]
        z = np.interp(grid, ga.y_m, ga.z_m) * (1.0 - w) + np.interp(grid, gb.y_m, gb.z_m) * w
        inside = (grid >= min(ga.y_m.min(), gb.y_m.min())) & (grid <= max(ga.y_m.max(), gb.y_m.max()))
        z = np.where(inside, z, -np.inf)
        best = np.maximum(best, z)
    return best


def dilate(z: np.ndarray, grid: np.ndarray, half_width: float) -> np.ndarray:
    if half_width <= 0.0:
        return z
    dy = grid[1] - grid[0]
    n = max(int(round(half_width / dy)), 0)
    if n == 0:
        return z
    padded = np.pad(z, n, mode="edge")
    return np.max(np.lib.stride_tricks.sliding_window_view(padded, 2 * n + 1), axis=-1)


def main(argv: list[str]) -> int:
    case_path = Path(argv[1]) if len(argv) > 1 else BASE / "case_I_wing.json"
    lo = float(argv[2]) if len(argv) > 2 else 79.60
    hi = float(argv[3]) if len(argv) > 3 else 80.60
    ds = (float(argv[4]) if len(argv) > 4 else 10.0) / 1e3
    sink = (float(argv[5]) if len(argv) > 5 else 0.4628) / 1e3
    _case, bodies, wheel, lat = build(case_path)

    grid = np.arange(
        max(min(g.y_m.min() for _n, _s, gs in bodies for g in gs), wheel.y_m.min() + lat),
        min(max(g.y_m.max() for _n, _s, gs in bodies for g in gs), wheel.y_m.max() + lat),
        2.0e-4,
    )
    stations = np.arange(lo, hi + 1e-9, ds)
    print(f"case {case_path.name}  sink {sink * 1e3:.3f} mm  grid {grid[0] * 1e3:.1f}..{grid[-1] * 1e3:.1f} mm"
          f"  {len(stations)} stations")
    header = "  ".join(f"w={int(w):>2d}mm" for w in HALF_WIDTHS_MM)
    print(f"  {'s_m':>7s}  {header}")
    table = np.full((len(stations), len(HALF_WIDTHS_MM)), np.nan)
    for i, s in enumerate(stations):
        rail = merged_surface(bodies, s, grid)
        wz = np.interp(grid - lat, wheel.y_m, wheel.z_m) + 0.430 - sink
        cells = []
        for j, w_mm in enumerate(HALF_WIDTHS_MM):
            zz = dilate(rail, grid, w_mm / 1e3)
            pen = np.where(np.isfinite(zz), zz - wz, -np.inf)
            k = int(np.argmax(pen))
            gap = -pen[k] * 1e3
            table[i, j] = gap
            cells.append(f"{gap:8.3f}")
        print(f"  {s:7.3f}  " + "  ".join(cells))

    print()
    for j, w_mm in enumerate(HALF_WIDTHS_MM):
        col = table[:, j]
        print(f"  w={int(w_mm):>2d} mm : max gap {np.nanmax(col):7.3f} mm | "
              f"stations with contact {(col <= 0).sum():3d}/{len(col)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
