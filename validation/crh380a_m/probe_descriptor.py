"""B4 measurement: does an upper-hull per-station descriptor reproduce the grid
contact point, and how fast is it?

Run:  python -X utf8 validation/crh380a_m/probe_descriptor.py
Writes a JSON summary next to itself and prints the table.
"""

from __future__ import annotations

import json
import pathlib
import statistics
import sys
import time

import numpy as np

BASE = pathlib.Path(__file__).resolve().parent
VELCH = BASE.parents[1]
sys.path.insert(0, str(VELCH / "src"))

from velch.contact_descriptor import ContactDescriptor  # noqa: E402
from velch.profiles import load_profile  # noqa: E402

WHEEL_FILE = pathlib.Path(
    r"G:\研究生\动力学\CRH380A_纯刚性模型\database\database\wheel_rail_profiles\LMA.prw"
)
WHEEL_ORIGIN_M = 0.430
WHEEL_LATERAL_M = 0.7465


def load_rail(path: pathlib.Path) -> tuple[np.ndarray, np.ndarray]:
    data = np.loadtxt(path, delimiter=",")
    return data[:, 0] * 1.0e-3, data[:, 1] * 1.0e-3


def load_wheel() -> tuple[np.ndarray, np.ndarray]:
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


def grid_truth(
    wheel_y: np.ndarray,
    wheel_z: np.ndarray,
    rail_y: np.ndarray,
    rail_z: np.ndarray,
    *,
    step_m: float = 4.0e-5,
):
    lower = max(float(wheel_y[0]), float(rail_y[0]))
    upper = min(float(wheel_y[-1]), float(rail_y[-1]))
    if not upper > lower:
        return 0.0, float("nan"), 0.0
    points = int(min(20001, max(64, np.ceil((upper - lower) / step_m) + 1)))
    grid = np.linspace(lower, upper, points)
    rz = np.interp(grid, rail_y, rail_z)
    wz = np.interp(grid, wheel_y, wheel_z)
    slope = np.gradient(rz, grid)
    inv = 1.0 / np.sqrt(1.0 + slope * slope)
    depth = (rz - wz) * inv
    best = int(np.argmax(depth))
    if not depth[best] > 0.0:
        return 0.0, float("nan"), 0.0
    return float(depth[best]), float(grid[best]), points


def main() -> int:
    wheel_y, wheel_z = load_wheel()
    print(f"wheel nodes {wheel_y.size}  y {wheel_y[0]:.5f}..{wheel_y[-1]:.5f} m  "
          f"z {wheel_z.min():.5f}..{wheel_z.max():.5f} m")

    files = sorted(BASE.joinpath("bodies").glob("main_r*.csv"))
    if not files:
        print("no station files found")
        return 1
    picks = [files[int(round(i * (len(files) - 1) / 5))] for i in range(6)]

    rng = np.random.default_rng(20261022)
    rows = []
    for path in picks:
        rail_y, rail_z = load_rail(path)
        descriptor = ContactDescriptor.build(rail_y, rail_z)
        info = descriptor.describe()

        # Time the descriptor's deepest() against the grid body, both with the
        # wheel actually placed over the rail (otherwise both return early).
        pose_y = wheel_y + WHEEL_LATERAL_M
        pose_z = wheel_z - 4.0e-4
        descriptor.deepest(pose_y, pose_z)
        grid_truth(pose_y, pose_z, rail_y, rail_z)

        starts = time.perf_counter()
        for _ in range(200):
            descriptor.deepest(pose_y, pose_z)
        descriptor_us = (time.perf_counter() - starts) / 200.0 * 1.0e6

        starts = time.perf_counter()
        for _ in range(200):
            grid_truth(pose_y, pose_z, rail_y, rail_z)
        grid_us = (time.perf_counter() - starts) / 200.0 * 1.0e6

        dy = []
        dd = []
        agree = 0
        trials = 120
        for _ in range(trials):
            lateral = WHEEL_LATERAL_M + rng.uniform(-2.0e-3, 2.0e-3)
            sink = rng.uniform(0.0, 6.0e-4)
            wy = wheel_y + lateral
            wz = wheel_z - sink
            truth_depth, truth_y, _ = grid_truth(wy, wz, rail_y, rail_z)
            depth, y, *_ = descriptor.deepest(wy, wz)
            if truth_depth <= 0.0 and depth <= 0.0:
                agree += 1
                continue
            if (truth_depth <= 0.0) != (depth <= 0.0):
                dy.append(float("inf"))
                dd.append(float("inf"))
                continue
            agree += 1
            dy.append(abs(y - truth_y))
            dd.append(abs(depth - truth_depth))

        finite_dy = [v for v in dy if np.isfinite(v)]
        finite_dd = [v for v in dd if np.isfinite(v)]
        rows.append(
            {
                "station": path.stem,
                **info,
                "descriptor_us": descriptor_us,
                "grid_us": grid_us,
                "speedup": grid_us / descriptor_us if descriptor_us else float("nan"),
                "trials": trials,
                "agree": agree,
                "delta_y_p50_mm": (
                    statistics.median(finite_dy) * 1.0e3 if finite_dy else float("nan")
                ),
                "delta_y_max_mm": (
                    max(finite_dy) * 1.0e3 if finite_dy else float("nan")
                ),
                "delta_depth_p50_um": (
                    statistics.median(finite_dd) * 1.0e6 if finite_dd else float("nan")
                ),
                "delta_depth_max_um": (
                    max(finite_dd) * 1.0e6 if finite_dd else float("nan")
                ),
            }
        )
        print(
            f"{path.stem}  nodes {info['source_nodes']:>4} -> hull {info['hull_nodes']:>3}"
            f"  bridge {info['bridge_depth_um']:7.2f} um"
            f"  desc {descriptor_us:6.2f} us  grid {grid_us:7.2f} us"
            f"  speedup {grid_us / descriptor_us:5.2f}x"
            f"  dy p50 {rows[-1]['delta_y_p50_mm']:.4f} max {rows[-1]['delta_y_max_mm']:.4f} mm"
            f"  dd p50 {rows[-1]['delta_depth_p50_um']:.2f} max {rows[-1]['delta_depth_max_um']:.1f} um"
            f"  agree {agree}/{trials}"
        )

    summary = {
        "wheel": str(WHEEL_FILE),
        "stations": len(rows),
        "mean_speedup": statistics.mean(r["speedup"] for r in rows),
        "mean_descriptor_us": statistics.mean(r["descriptor_us"] for r in rows),
        "mean_grid_us": statistics.mean(r["grid_us"] for r in rows),
        "worst_delta_y_mm": max(
            (r["delta_y_max_mm"] for r in rows if np.isfinite(r["delta_y_max_mm"])),
            default=float("nan"),
        ),
        "worst_delta_depth_um": max(
            (
                r["delta_depth_max_um"]
                for r in rows
                if np.isfinite(r["delta_depth_max_um"])
            ),
            default=float("nan"),
        ),
        "rows": rows,
    }
    out = BASE / "probe_descriptor.json"
    out.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(
        f"\nmean speedup {summary['mean_speedup']:.2f}x  "
        f"desc {summary['mean_descriptor_us']:.2f} us  grid {summary['mean_grid_us']:.2f} us"
    )
    print(
        f"worst delta_y {summary['worst_delta_y_mm']:.4f} mm  "
        f"worst delta_depth {summary['worst_delta_depth_um']:.1f} um"
    )
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
