"""A2: quantify how far the dense grid's contact point/penetration is from the
analytic spline solution, on surrogates of the three real regimes.

The grid path in ``contact.py`` searches a *discrete* merged grid, so its answer is
quantised by the node spacing (the frog body sections are ~45 um apart). The spline
path solves ``g'(y) = 0`` with Brent, so its error is not tied to a grid at all.
This script measures that difference instead of asserting it.

Surrogate shapes (parameters taken from measurements made earlier on the real
profiles, not invented):
  straight : circular tread on a circular 60TY1 crown, r = 0.43 / 0.30 m.
  frog     : the same crown plus a 20 mm wide, 1.3 mm deep groove, which is the
             point-rail relief measured in the merge zone (crown -1.29 mm at
             y = 738 mm, `probe_gap_profile.py`).
  switch   : the same crown plus the 22.6 mm stock-rail shoulder cut that made the
             two-body seat fail (`DIVERGING_ROUTE_2026-10-21.md` section 10).

Outputs ``Velch\\docs\\CONTACT_GEOMETRY_ERROR_BOUND_<date>.md`` and a CSV beside it.
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

from velch.contact import _grid_curvature, _grid_slope  # noqa: E402
from velch.contact_geometry import fit_profile, swept_contact  # noqa: E402
from velch.contact_law import circular_equivalent_radius  # noqa: E402

GRID_STEP_M = 45.0e-6          # ~ the spacing of the real frog body sections
WHEEL_RADIUS_M = 0.43
LATERAL_SWEEP_M = 0.040
LATERAL_POINTS = 201
SINK_M = (0.0002, 0.0006)


def _wheel_tread(y: np.ndarray) -> np.ndarray:
    """Circular tread, z positive upward with the contact at y = 0, z = 0."""
    radius = WHEEL_RADIUS_M
    return radius - np.sqrt(np.maximum(radius * radius - y * y, 0.0))


def _rail_crown(y: np.ndarray) -> np.ndarray:
    # A crown flatter than the tread (0.50 m vs 0.43 m) so that a single wheel-rail
    # pair has an interior interference maximum; with a sharper crown the pair is
    # laterally unstable and the extremum sits on the overlap boundary, which the
    # production code reports as ``edge_limited`` and does not treat as a contact.
    radius = 0.50
    return radius - np.sqrt(np.maximum(radius * radius - y * y, 0.0)) + 0.0003


def _rail_frog(y: np.ndarray) -> np.ndarray:
    return _rail_crown(y) - 1.3e-3 * np.exp(-((y / 0.010) ** 2))


def _rail_switch(y: np.ndarray) -> np.ndarray:
    shoulder = -22.6e-3
    blend = 0.5 * (1.0 + np.tanh((y - 0.012) / 0.002))
    return _rail_crown(y) + shoulder * (1.0 - blend)


REGIMES = {
    "straight": (lambda y: _rail_crown(y)),
    "frog": _rail_frog,
    "switch": _rail_switch,
}


def _grid_contact(wheel_y, wheel_z, rail_y, rail_z, lower, upper):
    """Transcription of the production grid search in ``_contact_on_span``."""
    lo = max(float(lower), float(rail_y[0]), float(wheel_y[0]))
    hi = min(float(upper), float(rail_y[-1]), float(wheel_y[-1]))
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
    radius_y = max(1.0e-6, 0.0 - float(w_z[index]) + WHEEL_RADIUS_M)
    radius_star = circular_equivalent_radius(
        radius_y,
        float(_grid_curvature(w_z, grid)[index]),
        float(_grid_curvature(r_z, grid)[index]),
    )
    return {
        "y": float(grid[index]),
        "depth": float(depth[index]),
        "slope": float(slopes[index]),
        "radius_star": float(radius_star),
        "edge": index == 0 or index == grid.size - 1,
    }


def _percentiles(values):
    if not values:
        return (float("nan"),) * 3
    ordered = sorted(values)
    return (
        statistics.median(ordered),
        ordered[min(len(ordered) - 1, int(round(0.95 * (len(ordered) - 1))))],
        ordered[-1],
    )


def main() -> int:
    rows = []
    summary = {}
    for name, rail_fn in REGIMES.items():
        delta_y, delta_depth, delta_radius = [], [], []
        worst = None
        for sink in SINK_M:
            for offset in np.linspace(-LATERAL_SWEEP_M, LATERAL_SWEEP_M, LATERAL_POINTS):
                span = 0.120
                y = np.linspace(-span, span, 4001)
                rail_z = rail_fn(y)
                wheel_z_local = _wheel_tread(y - offset)
                wheel_z = wheel_z_local - sink

                grid = _grid_contact(y, wheel_z, y, rail_z, -0.06, 0.06)
                if grid is None or grid["edge"]:
                    continue
                wheel_spline = fit_profile(y, wheel_z)
                rail_spline = fit_profile(y, rail_z)
                spline = swept_contact(
                    wheel_spline, rail_spline,
                    wheel_origin_y_m=float(offset),
                    wheel_origin_z_m=WHEEL_RADIUS_M - sink,
                )
                if spline is None or spline.edge_limited:
                    continue

                d_y = (spline.y_m - grid["y"]) * 1e3
                d_depth = (spline.penetration_m - grid["depth"]) * 1e6
                d_radius = (spline.radius_star_m - grid["radius_star"]) * 100.0
                delta_y.append(abs(d_y))
                delta_depth.append(abs(d_depth))
                delta_radius.append(abs(d_radius))
                rows.append(
                    [name, sink * 1e3, offset * 1e3, d_y, d_depth, d_radius,
                     spline.extrema_count]
                )
                if worst is None or abs(d_depth) > worst[0]:
                    worst = (abs(d_depth), sink, offset, d_y, d_depth, d_radius,
                             spline.extrema_count)

        summary[name] = {
            "n": len(delta_y),
            "y": _percentiles(delta_y),
            "depth": _percentiles(delta_depth),
            "radius": _percentiles(delta_radius),
            "worst": worst,
            "multi_extremum": sum(1 for r in rows if r[0] == name and r[6] > 1),
        }

    stamp = _dt.date.today().isoformat()
    csv_path = BASE / "docs" / f"contact_geometry_error_bound_{stamp}.csv"
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            ["regime", "sink_mm", "offset_mm", "dy_mm", "d_depth_um",
             "d_radius_star_cm", "extrema"]
        )
        writer.writerows(rows)

    md = [
        f"# 接触几何误差界：样条解析 vs 密网格 {stamp}",
        "",
        f"网格步长 {GRID_STEP_M * 1e6:.0f} µm（≈ 真实辙叉 body 断面节点间距），"
        f"横向扫描 ±{LATERAL_SWEEP_M * 1e3:.0f} mm × {LATERAL_POINTS} 点，"
        f"下沉 {', '.join(f'{s * 1e3:.1f}' for s in SINK_M)} mm。",
        "",
        "| 工况 | 有效样本 | ‖Δy‖ mm (p50/p95/max) | ‖Δδ‖ µm (p50/p95/max) | ‖ΔR*‖ cm (p50/p95/max) | 多极值样本 |",
        "|---|---|---|---|---|---|",
    ]
    for name, item in summary.items():
        y50, y95, ymax = item["y"]
        d50, d95, dmax = item["depth"]
        r50, r95, rmax = item["radius"]
        md.append(
            f"| {name} | {item['n']} | {y50:.4f} / {y95:.4f} / {ymax:.4f} "
            f"| {d50:.3f} / {d95:.3f} / **{dmax:.3f}** "
            f"| {r50:.3f} / {r95:.3f} / {rmax:.3f} | {item['multi_extremum']} |"
        )
    md += ["", "## 最不利样本", ""]
    for name, item in summary.items():
        worst = item["worst"]
        if worst is None:
            md.append(f"- **{name}**：无有效样本")
            continue
        d_depth, sink, offset, d_y, d_depth_signed, d_radius, extrema = worst
        md.append(
            f"- **{name}**：下沉 {sink * 1e3:.1f} mm、横移 {offset * 1e3:.1f} mm → "
            f"Δy {d_y:+.4f} mm、Δδ {d_depth_signed:+.3f} µm、"
            f"ΔR* {d_radius:+.3f} cm、极值数 {extrema}"
        )
    md += [
        "",
        "## 读法",
        "",
        "- ‖Δδ‖ 是密网格自身的量化误差：真极值落在两个节点之间时，网格只能取端点值。"
        "样条在 `g'(y)=0` 上求根，因此这一项对它不成立。",
        "- Δy 与 ΔR* 同源：接触点位置一旦被量化，两型面在该点的曲率估计也随之偏离。",
        "- 多极值样本说明这些工况本身存在多个候选接触点，正是辙叉/尖轨区必须多点接触的理由。",
        "",
        f"CSV：`{csv_path.relative_to(BASE)}`",
    ]
    md_path = BASE / "docs" / f"CONTACT_GEOMETRY_ERROR_BOUND_{stamp}.md"
    md_path.write_text("\n".join(md) + "\n", encoding="utf-8")

    for name, item in summary.items():
        print(f"{name:>9}: n={item['n']:4d}  "
              f"max|dy|={item['y'][2]:.4f} mm  "
              f"max|dd|={item['depth'][2]:.3f} um  "
              f"max|dR*|={item['radius'][2]:.3f} cm  "
              f"multi={item['multi_extremum']}")
    print(f"\nwrote {md_path}")
    print(f"wrote {csv_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
