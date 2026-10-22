"""A3 measurement: how many engaged contact patches does one wheel pose produce on a
real turnout cross-section, and how wrong is the single-deepest-point moment arm?

No solver change.  This only measures, so that "split the patches" can be adopted or
rejected on numbers instead of on Simpack's ``N_ConPatch``.

Run:  python -X utf8 validation/crh380a_m/probe_multipatch.py
Writes probe_multipatch.json next to itself.
"""

from __future__ import annotations

import json
import math
import pathlib
import statistics
import sys

import numpy as np

BASE = pathlib.Path(__file__).resolve().parent
VELCH = BASE.parents[1]
sys.path.insert(0, str(VELCH / "src"))

from velch.profiles import load_profile  # noqa: E402

WHEEL_FILE = pathlib.Path(
    r"G:\研究生\动力学\CRH380A_纯刚性模型\database\database\wheel_rail_profiles\LMA.prw"
)
WHEEL_ORIGIN_M = 0.430
WHEEL_LATERAL_M = 0.7465
EFFECTIVE_MODULUS_PA = 1.1393e11
GRID_STEP_M = 4.0e-5
Y_REFERENCE_M = 0.753


def load_rail(path: pathlib.Path):
    data = np.loadtxt(path, delimiter=",")
    return data[:, 0] * 1.0e-3, data[:, 1] * 1.0e-3


def load_wheel():
    profile = load_profile(
        WHEEL_FILE,
        file_format="prr",
        surface="wheel_lower",
        y_sign=-1,
        z_sign=-1,
        z_offset_m=-0.43,
    )
    y = np.asarray(profile.y_m, dtype=float)
    z = np.asarray(profile.z_m, dtype=float) + WHEEL_ORIGIN_M
    order = np.argsort(y)
    return y[order], z[order]


def depth_field(wheel_y, wheel_z, rail_y, rail_z):
    lower = max(float(wheel_y[0]), float(rail_y[0]))
    upper = min(float(wheel_y[-1]), float(rail_y[-1]))
    if not upper > lower:
        return None
    points = int(min(20001, max(64, math.ceil((upper - lower) / GRID_STEP_M) + 1)))
    grid = np.linspace(lower, upper, points)
    rz = np.interp(grid, rail_y, rail_z)
    wz = np.interp(grid, wheel_y, wheel_z)
    slope = np.gradient(rz, grid)
    inv = 1.0 / np.sqrt(1.0 + slope * slope)
    depth = (rz - wz) * inv
    if not np.any(depth > 0.0):
        return None
    return grid, depth, float(grid[1] - grid[0])


def patches(grid, depth, step):
    """Connected engaged runs with their own force, centroid and moment arm."""
    active = depth > 0.0
    edges = np.diff(active.astype(np.int8))
    starts = list(np.flatnonzero(edges == 1) + 1)
    stops = list(np.flatnonzero(edges == -1) + 1)
    if active[0]:
        starts.insert(0, 0)
    if active[-1]:
        stops.append(active.size)

    out = []
    for start, stop in zip(starts, stops):
        segment_depth = depth[start:stop]
        segment_y = grid[start:stop]
        weights = segment_depth ** 1.5
        total = float(np.sum(weights))
        if total <= 0.0:
            continue
        force = 0.25 * math.pi * EFFECTIVE_MODULUS_PA * total * step
        centroid = float(np.sum(weights * segment_y) / total)
        out.append(
            {
                "y_lo_mm": (segment_y[0] - Y_REFERENCE_M) * 1.0e3,
                "y_hi_mm": (segment_y[-1] - Y_REFERENCE_M) * 1.0e3,
                "width_mm": (segment_y[-1] - segment_y[0]) * 1.0e3,
                "force_n": force,
                "centroid_mm": (centroid - Y_REFERENCE_M) * 1.0e3,
                "depth_max_um": float(segment_depth.max()) * 1.0e6,
            }
        )
    return out


def main() -> int:
    wheel_y, wheel_z = load_wheel()
    files = sorted(BASE.joinpath("bodies").glob("main_r*.csv"))
    picks = [files[int(round(i * (len(files) - 1) / 5))] for i in range(6)]
    rng = np.random.default_rng(20261023)

    rows = []
    for path in picks:
        rail_y, rail_z = load_rail(path)
        counts: dict[int, int] = {}
        moment_errors = []
        arm_errors = []
        force_smallest = []
        trials = 0
        for _ in range(120):
            lateral = WHEEL_LATERAL_M + rng.uniform(-2.0e-3, 2.0e-3)
            sink = rng.uniform(0.0, 6.0e-4)
            field = depth_field(wheel_y + lateral, wheel_z - sink, rail_y, rail_z)
            if field is None:
                continue
            grid, depth, step = field
            found = patches(grid, depth, step)
            if not found:
                continue
            trials += 1
            counts[len(found)] = counts.get(len(found), 0) + 1

            total_force = sum(p["force_n"] for p in found)
            true_arm = (
                sum(p["force_n"] * (p["centroid_mm"] + Y_REFERENCE_M * 1.0e3) for p in found)
                / total_force
                if total_force
                else 0.0
            ) - Y_REFERENCE_M * 1.0e3
            deepest_arm = (float(grid[int(np.argmax(depth))]) - Y_REFERENCE_M) * 1.0e3
            arm_errors.append(true_arm - deepest_arm)
            moment_errors.append(abs(true_arm - deepest_arm) / max(1.0, abs(true_arm)))
            if len(found) > 1:
                force_smallest.append(min(p["force_n"] for p in found) / total_force)

        rows.append(
            {
                "station": path.stem,
                "trials": trials,
                "patch_counts": {str(k): v for k, v in sorted(counts.items())},
                "multi_patch_fraction": (
                    sum(v for k, v in counts.items() if k > 1) / trials if trials else 0.0
                ),
                "arm_error_mean_mm": (
                    statistics.mean(arm_errors) * 1.0e0 if arm_errors else float("nan")
                ),
                "arm_error_max_mm": (
                    max(abs(v) for v in arm_errors) if arm_errors else float("nan")
                ),
                "smallest_force_share": (
                    statistics.mean(force_smallest) if force_smallest else float("nan")
                ),
            }
        )
        r = rows[-1]
        shares = ", ".join(f"{k}:{v}" for k, v in r["patch_counts"].items())
        print(
            f"{path.stem}  trials {trials:>3}  patches {{{shares}}}"
            f"  multi {r['multi_patch_fraction'] * 100:5.1f}%"
            f"  arm err mean {r['arm_error_mean_mm']:7.3f} max {r['arm_error_max_mm']:7.3f} mm"
            f"  small share {r['smallest_force_share'] * 100:6.2f}%"
        )

    summary = {
        "stations": len(rows),
        "multi_patch_fraction": statistics.mean(r["multi_patch_fraction"] for r in rows),
        "worst_arm_error_mm": max(r["arm_error_max_mm"] for r in rows),
        "rows": rows,
    }
    out = BASE / "probe_multipatch.json"
    out.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(
        f"\nmean multi-patch fraction {summary['multi_patch_fraction'] * 100:.1f}%  "
        f"worst single-point moment-arm error {summary['worst_arm_error_mm']:.3f} mm"
    )
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
