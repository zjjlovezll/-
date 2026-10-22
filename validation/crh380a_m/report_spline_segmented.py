"""A2 round 2: segmented spline vs dense grid on real turnout sections.

Round 1 proved a single cubic cannot represent LMA (flange-root kink, 396.8 um
overshoot). This version splits both bands at curvature discontinuities, fits a
cubic on each segment, searches every overlapping (wheel, rail) segment pair and
keeps the deepest interference -- which is also the only way the frog's 20 mm wide
point-rail relief can be represented at all.

It reports two tables:
  1. where both methods answer: |dy|, |ddelta|, |dR*|, |dC| percentiles;
  2. where the *grid* declares "no interior contact" (edge_limited) while the
     segmented spline still finds a candidate. That disagreement is the interesting
     one and is the reason stage C (third-party arbitration) follows.
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
from velch.contact_geometry import fit_profile, fit_segmented, swept_contact  # noqa: E402
from velch.contact_law import (  # noqa: E402
    circular_equivalent_radius,
    hertz_stiffness_n_m_1p5,
)

CASE = BASE / "validation" / "crh380a_m" / (
    sys.argv[1] if len(sys.argv) > 1 else "case_B_turnout.json"
)
GRID_STEP_M = (float(sys.argv[2]) * 1e-6 if len(sys.argv) > 2 else 45.0e-6)
OFFSETS_MM = (-8.0, -4.0, 0.0, 4.0, 8.0)
SINKS_MM = (0.2, 0.6)
WINDOWS = {
    "straight": (40.0, 50.0),
    "switch": (54.0, 60.5),
    "frog": (79.3, 80.9),
}
STATIONS = 240
E_STAR_PA = 1.1393e11
KINK_SLOPE_JUMP = 0.15          # ~8.6 deg between adjacent nodes
MIN_SEGMENT_NODES = 6
SEGMENT_MIN_NODES = 6        # fit_profile's own floor; resolution comes from depth
SEGMENT_MAX_DEPTH = 16
# Any penetration far beyond the swept sinks is not a contact: the two profiles are
# placed on a shared lateral grid with no body-interference test, so deep inside a
# flangeway groove or beyond the rail's field edge the search can "find" 20+ mm of
# interference between surfaces that are not touching at all. The sweep intends at
# most ``max(SINKS_MM)`` = 0.6 mm, and the artefacts measured here are 20-25 mm, so a
# 2 mm cut separates them with a wide margin on both sides. Such samples are counted
# and excluded instead of being averaged into the error statistics -- otherwise the
# tail reports the difference between two physically impossible numbers.
IMPOSSIBLE_DEPTH_UM = 2000.0
RAIL_REFERENCE_Y_M = 0.753    # right rail reference plane (gauge face + 36 mm)
HEAD_HALF_BAND_M = 0.030      # running band half width around that plane


def _segmented_contact(wheel_y, wheel_z, rail_y, rail_z, wheel_origin_y, wheel_origin_z):
    """One contact solve on the whole band, with segmentation used only for the fit.

    Solving each piece pair separately and keeping the deepest candidate lets a
    spurious pair (the flange tip against a filled flangeway floor) beat the true
    tread contact. ``fit_segmented`` returns a chain that the search walks as a single
    continuous surface, which is what the merged-grid path does by construction.
    """
    wheel = fit_segmented(wheel_y, wheel_z, min_nodes=SEGMENT_MIN_NODES,
                          max_depth=SEGMENT_MAX_DEPTH)
    rail = fit_segmented(rail_y, rail_z, min_nodes=SEGMENT_MIN_NODES,
                         max_depth=SEGMENT_MAX_DEPTH)
    quality = max(wheel.max_residual_m, rail.max_residual_m)
    candidate = swept_contact(
        wheel, rail,
        wheel_origin_y_m=wheel_origin_y,
        wheel_origin_z_m=wheel_origin_z,
        effective_modulus_pa=E_STAR_PA,
    )
    if candidate is None:
        return None, 0, quality
    return candidate, max(1, candidate.extrema_count), quality


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
    radius_star = circular_equivalent_radius(
        max(1.0e-6, 0.43 - float(w_z[index])),
        float(_grid_curvature(w_z, grid)[index]),
        float(_grid_curvature(r_z, grid)[index]),
    )
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
    from velch.vehicle import load_vehicle_case  # noqa: E402

    case = load_vehicle_case(CASE)
    wheel = None
    for name in ("profile", "graph", "surface"):
        candidate = getattr(case.wheels[0], name, None)
        if candidate is not None and hasattr(candidate, "y_m"):
            wheel = candidate
            break
    if wheel is None:
        raise SystemExit("wheel profile not found on the case")
    rail = next(r for r in case.rails if "right" in r.id)
    series = rail.profiles if rail.bodies == () else rail.bodies[0].series
    body_series = [body.series for body in rail.bodies] or [rail.profiles]

    rows = []
    summary = {}
    for regime, (lo, hi) in WINDOWS.items():
        dy, dd, dr, dc = [], [], [], []
        qualities: list[float] = []
        grid_edge = 0
        spline_none = 0
        edge_depth = []
        edge_y = []
        pairs = 0
        impossible: list[float] = []
        for s in np.linspace(lo, hi, STATIONS):
            candidates = [item.sample(float(s)) for item in body_series
                          if item.covers(float(s))]
            if not candidates:
                continue
            # Datum by *first contact*, per body. Place the wheel with its lowest point at
            # zero; the height it must drop before it touches body b is
            # h_b = max(rail_z - wheel_z) over that body's merged grid. The wheel lands on
            # the body with the largest h_b, and sinking `sink` below it makes the deepest
            # penetration exactly `sink` - by construction, not by a crown heuristic.
            # This is what the ±30 mm band and the per-body global crown both failed to do:
            # the band excluded the stock-rail crown in the switch panel, the per-body
            # maximum let a node 24 mm above the running surface win at the frog.
            for sink_mm in SINKS_MM:
                sink_m = sink_mm * 1e-3
                for offset_mm in OFFSETS_MM:
                    offset_m = offset_mm * 1e-3
                    pick = None
                    for candidate in candidates:
                        wy, wz, ry, rz = _absolute_arrays(
                            wheel, candidate,
                            wheel_y_m=RAIL_REFERENCE_Y_M,
                            wheel_z_m=0.0,
                            wheel_roll_rad=0.0,
                            wheel_lateral_offset_m=offset_m,
                            rail_y_m=0.0,
                            rail_z_m=0.0,
                        )
                        probe = _grid_solution(wy, wz, ry, rz)
                        if probe is None:
                            continue
                        if pick is None or probe["depth"] > pick[0]:
                            pick = (probe["depth"], candidate)
                    if pick is None:
                        continue
                    drop_m, sample = pick
                    wheel_y_m = RAIL_REFERENCE_Y_M
                    crown_y = wheel_y_m
                    wheel_z_m = drop_m - sink_m
                    wheel_y, wheel_z, rail_y, rail_z = _absolute_arrays(
                        wheel, sample,
                        wheel_y_m=crown_y,
                        wheel_z_m=wheel_z_m,
                        wheel_roll_rad=0.0,
                        wheel_lateral_offset_m=offset_mm * 1e-3,
                        rail_y_m=0.0,
                        rail_z_m=0.0,
                    )
                    grid = _grid_solution(wheel_y, wheel_z, rail_y, rail_z)
                    spline, extrema, quality = _segmented_contact(
                        wheel_y, wheel_z, rail_y, rail_z,
                        crown_y, wheel_z_m,
                    )
                    qualities.append(quality)
                    if spline is None:
                        spline_none += 1
                        continue
                    if grid is None:
                        grid_edge += 1
                        edge_depth.append(spline.penetration_m * 1e6)
                        edge_y.append(spline.y_m * 1e3)
                        continue
                    if (spline.penetration_m * 1e6 > IMPOSSIBLE_DEPTH_UM
                            or grid["depth"] * 1e6 > IMPOSSIBLE_DEPTH_UM):
                        impossible.append(max(spline.penetration_m,
                                              grid["depth"]) * 1e6)
                        continue
                    pairs += 1
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
                                 d_radius, d_stiff, extrema])
        summary[regime] = {
            "pairs": pairs, "grid_edge": grid_edge, "spline_none": spline_none,
            "y": _pct(dy), "d": _pct(dd), "r": _pct(dr), "c": _pct(dc),
            "edge_depth": _pct(edge_depth), "edge_y": _pct([abs(v) for v in edge_y]),
            "quality": max(qualities) if qualities else float("nan"),
            "impossible": len(impossible),
            "impossible_depth": _pct(impossible),
        }

    stamp = _dt.date.today().isoformat()
    csv_path = BASE / "docs" / f"contact_geometry_segmented_{stamp}.csv"
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["regime", "s_m", "sink_mm", "offset_mm", "dy_mm",
                         "d_depth_um", "d_radius_star_cm", "d_stiffness_pct", "extrema"])
        writer.writerows(rows)

    lines = [
        f"# 分段样条 vs 密网格（真实断面）{stamp}",
        "",
        f"`{CASE.name}` 右股，每档 {STATIONS} 站 × {len(OFFSETS_MM)} 横移 × "
        f"{len(SINKS_MM)} 下沉；网格 {GRID_STEP_M * 1e6:.0f} µm；"
        f"分段阈值 |Δslope| > {KINK_SLOPE_JUMP}（≈"
        f"{math.degrees(math.atan(KINK_SLOPE_JUMP)):.1f}°），最少 {MIN_SEGMENT_NODES} 节点。",
        "",
        "## 1 两法都给答案的样本",
        "",
        "| 区段 | 可比样本 | ‖Δy‖ mm (p50/p95/max) | ‖Δδ‖ µm (p50/p95/max) "
        "| ‖ΔR*‖ cm (p50/p95/max) | ‖ΔC‖ % (p50/p95/max) |",
        "|---|---|---|---|---|---|",
    ]
    for regime, item in summary.items():
        y50, y95, ymax = item["y"]
        d50, d95, dmax = item["d"]
        r50, r95, rmax = item["r"]
        c50, c95, cmax = item["c"]
        lines.append(
            f"| {regime} | {item['pairs']} | {y50:.4f} / {y95:.4f} / {ymax:.4f} "
            f"| {d50:.3f} / {d95:.3f} / **{dmax:.3f}** "
            f"| {r50:.3f} / {r95:.3f} / {rmax:.3f} "
            f"| {c50:.3f} / {c95:.3f} / {cmax:.3f} |"
        )
    lines += [
        "",
        "## 2 网格判“无内部接触”而分段样条仍找到候选的样本",
        "",
        "| 区段 | 网格 edge_limited 样本 | 样条仍找到 | 样条侵入 µm (p50/p95/max) "
        "| ‖y‖ mm (p50/p95/max) | 样条完全无解 |",
        "|---|---|---|---|---|",
    ]
    for regime, item in summary.items():
        d50, d95, dmax = item["edge_depth"]
        y50, y95, ymax = item["edge_y"]
        lines.append(
            f"| {regime} | {item['grid_edge']} | {item['grid_edge']} "
            f"| {d50:.3f} / {d95:.3f} / {dmax:.3f} "
            f"| {y50:.3f} / {y95:.3f} / {ymax:.3f} | {item['spline_none']} |"
        )
    lines += ["", f"CSV：`{csv_path.relative_to(BASE)}`"]
    md_path = BASE / "docs" / f"CONTACT_GEOMETRY_SEGMENTED_{stamp}.md"
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    for regime, item in summary.items():
        print(f"{regime:>9}: pairs={item['pairs']:5d} grid_edge={item['grid_edge']:4d} "
              f"none={item['spline_none']:4d}  imposs={item['impossible']:4d}  "
              f"max|dd|={item['d'][2]:7.3f} um  fit_overshoot={item['quality'] * 1e6:8.3f} um")
    print(f"\nwrote {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
