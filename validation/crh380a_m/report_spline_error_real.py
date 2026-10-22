"""A2 (real sections): spline vs dense grid on actual turnout sections.

Samples >=200 real stations per regime from the validated turnout case, places the
real LMA wheel on each section at nine lateral offsets and two sink depths, and
reports |dy|, |ddelta|, |dR*|, |dC| percentiles. No synthetic profiles.

Frame note: both surfaces are placed in one common lateral frame by shifting the
rail so that its crown sits under the wheel reference plane. A geometry-error study
depends only on the *relative* placement, so this is equivalent to the solver frame
and avoids reproducing the case's per-body offsets here.
"""

from __future__ import annotations

import csv
import datetime as _dt
import math
import statistics
import sys
from pathlib import Path

import numpy as np

BASE = Path(r"F:\ai道岔状态反演辨识\Velch")
sys.path.insert(0, str(BASE / "src"))

from velch.contact import _absolute_arrays, _grid_curvature, _grid_slope  # noqa: E402
from velch.contact_geometry import fit_profile, swept_contact  # noqa: E402
from velch.contact_law import (  # noqa: E402
    circular_equivalent_radius,
    hertz_stiffness_n_m_1p5,
)

CASE = BASE / "validation" / "crh380a_m" / "case_B_turnout.json"
GRID_STEP_M = 45.0e-6
OFFSETS_MM = (-8.0, -6.0, -4.0, -2.0, 0.0, 2.0, 4.0, 6.0, 8.0)
SINKS_MM = (0.2, 0.6)
WINDOWS = {
    "straight": (40.0, 50.0),
    "switch": (54.0, 60.5),
    "frog": (79.3, 80.9),
}
STATIONS_PER_REGIME = 240
E_STAR_PA = 1.1393e11


def _wheel_profile(case):
    wheel = case.wheels[0]
    for name in ("profile", "graph", "surface"):
        prof = getattr(wheel, name, None)
        if prof is not None and hasattr(prof, "y_m"):
            return prof
    raise SystemExit(f"cannot find the wheel profile on {type(wheel).__name__}")


def _local_fit(y, z, y0, half_spans_mm=(2.0, 1.0, 0.5, 0.25, 0.125)):
    """Fit a cubic spline on the smallest window around ``y0`` that stays inside
    the 2 um overshoot tolerance.

    A global fit cannot represent LMA: the flange root and the field-side chamfer
    are curvature discontinuities, and a single cubic overshoots them by ~400 um,
    which ``fit_profile`` correctly rejects. Restricting the fit is also what the
    production path wants: a contact search only needs the surface around the
    candidate, and a spline segment that spans a kink is not a valid surface.
    """
    for half in half_spans_mm:
        lo = y0 - half * 1e-3
        hi = y0 + half * 1e-3
        if lo <= float(y[0]) or hi >= float(y[-1]):
            continue
        try:
            return fit_profile(y, z, y_lo_m=lo, y_hi_m=hi)
        except ValueError:
            continue
    return None


def _grid_solution(wheel_y, wheel_z, rail_y, rail_z):
    lo = max(float(wheel_y[0]), float(rail_y[0]))
    hi = min(float(wheel_y[-1]), float(rail_y[-1]))
    if not hi > lo:
        return None
    count = max(2, int(math.floor((hi - lo) / GRID_STEP_M)) + 1)
    grid = lo + (hi - lo) / (count - 1) * np.arange(count, dtype=float)
    r_z = np.interp(grid, rail_y, rail_z)
    w_z = np.interp(grid, wheel_y, wheel_z)
    slopes = _grid_slope(r_z, grid)
    inv = 1.0 / np.sqrt(1.0 + slopes * slopes)
    depth = (r_z - w_z) * inv
    index = int(np.argmax(depth))
    if index == 0 or index == grid.size - 1:
        return None
    kw = float(_grid_curvature(w_z, grid)[index])
    kr = float(_grid_curvature(r_z, grid)[index])
    radius_y = max(1.0e-6, 0.43 - float(w_z[index]))
    radius_star = circular_equivalent_radius(radius_y, kw, kr)
    return {
        "y": float(grid[index]),
        "depth": float(depth[index]),
        "radius_star": float(radius_star),
        "stiffness": hertz_stiffness_n_m_1p5(E_STAR_PA, float(radius_star)),
    }


def _pct(values):
    if not values:
        return (float("nan"),) * 3
    ordered = sorted(values)
    return (
        statistics.median(ordered),
        ordered[min(len(ordered) - 1, int(round(0.95 * (len(ordered) - 1))))],
        ordered[-1],
    )


def main() -> int:
    sys.path.insert(0, str(BASE / "src"))
    from velch.vehicle import load_vehicle_case  # noqa: E402

    case = load_vehicle_case(CASE)
    wheel = _wheel_profile(case)
    rail = next(r for r in case.rails if r.id.endswith("right") or "right" in r.id)
    series = rail.profiles if rail.bodies == () else rail.bodies[0].series

    rows = []
    per_regime = {}
    for regime, (lo, hi) in WINDOWS.items():
        dy, dd, dr, dc = [], [], [], []
        for s in np.linspace(lo, hi, STATIONS_PER_REGIME):
            if not series.covers(float(s)):
                continue
            sample = series.sample(float(s))
            crown = int(np.argmin(sample.profile.z_m))
            crown_y = float(sample.profile.y_m[crown])
            crown_z = float(sample.profile.z_m[crown])
            for sink_mm in SINKS_MM:
                for offset_mm in OFFSETS_MM:
                    wheel_y, wheel_z, rail_y, rail_z = _absolute_arrays(
                        wheel, sample,
                        wheel_y_m=crown_y,
                        wheel_z_m=crown_z + 0.43 - sink_mm * 1e-3,
                        wheel_roll_rad=0.0,
                        wheel_lateral_offset_m=offset_mm * 1e-3,
                        rail_y_m=0.0,
                        rail_z_m=0.0,
                    )
                    grid = _grid_solution(wheel_y, wheel_z, rail_y, rail_z)
                    if grid is None:
                        continue
                    wheel_spline = _local_fit(wheel_y, wheel_z, grid["y"])
                    rail_spline = _local_fit(rail_y, rail_z, grid["y"])
                    if wheel_spline is None or rail_spline is None:
                        continue
                    spline = swept_contact(
                        wheel_spline, rail_spline,
                        wheel_origin_y_m=crown_y,
                        wheel_origin_z_m=crown_z + 0.43 - sink_mm * 1e-3,
                        effective_modulus_pa=E_STAR_PA,
                    )
                    if spline is None or spline.edge_limited:
                        continue
                    d_y = (spline.y_m - grid["y"]) * 1e3
                    d_depth = (spline.penetration_m - grid["depth"]) * 1e6
                    d_radius = (spline.radius_star_m - grid["radius_star"]) * 100.0
                    d_stiff = (
                        (spline.stiffness_n_m_1p5 - grid["stiffness"])
                        / grid["stiffness"] * 100.0
                        if spline.stiffness_n_m_1p5 else float("nan")
                    )
                    dy.append(abs(d_y))
                    dd.append(abs(d_depth))
                    dr.append(abs(d_radius))
                    if math.isfinite(d_stiff):
                        dc.append(abs(d_stiff))
                    rows.append([regime, float(s), sink_mm, offset_mm, d_y, d_depth,
                                 d_radius, d_stiff, spline.extrema_count])
        per_regime[regime] = {
            "n": len(dy), "y": _pct(dy), "d": _pct(dd), "r": _pct(dr), "c": _pct(dc),
        }

    stamp = _dt.date.today().isoformat()
    csv_path = BASE / "docs" / f"contact_geometry_error_bound_real_{stamp}.csv"
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["regime", "s_m", "sink_mm", "offset_mm", "dy_mm",
                         "d_depth_um", "d_radius_star_cm", "d_stiffness_pct", "extrema"])
        writer.writerows(rows)

    lines = [
        f"# 接触几何误差界（真实断面）{stamp}",
        "",
        f"算例 `{CASE.name}`，右股，每档 {STATIONS_PER_REGIME} 个真实站位 × "
        f"{len(OFFSETS_MM)} 个横移 × {len(SINKS_MM)} 个下沉；网格步长 "
        f"{GRID_STEP_M * 1e6:.0f} µm。",
        "",
        "| 区段 | 有效样本 | ‖Δy‖ mm (p50/p95/max) | ‖Δδ‖ µm (p50/p95/max) "
        "| ‖ΔR*‖ cm (p50/p95/max) | ‖ΔC‖ % (p50/p95/max) |",
        "|---|---|---|---|---|---|",
    ]
    for regime, item in per_regime.items():
        y50, y95, ym = item["y"]
        d50, d95, dm = item["d"]
        r50, r95, rm = item["r"]
        c50, c95, cm = item["c"]
        lines.append(
            f"| {regime} | {item['n']} | {y50:.4f} / {y95:.4f} / {ym:.4f} "
            f"| {d50:.3f} / {d95:.3f} / **{dm:.3f}** "
            f"| {r50:.3f} / {r95:.3f} / {rm:.3f} "
            f"| {c50:.3f} / {c95:.3f} / {cm:.3f} |"
        )
    lines += ["", f"CSV：`{csv_path.relative_to(BASE)}`"]
    md_path = BASE / "docs" / f"CONTACT_GEOMETRY_ERROR_BOUND_REAL_{stamp}.md"
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    for regime, item in per_regime.items():
        print(f"{regime:>9}: n={item['n']:5d} "
              f"max|dy|={item['y'][2]:.4f} mm  max|dd|={item['d'][2]:.3f} um  "
              f"max|dR*|={item['r'][2]:.3f} cm  max|dC|={item['c'][2]:.3f} %")
    print(f"\nwrote {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
