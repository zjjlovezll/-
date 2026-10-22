"""Does Simpack's documented steep-slope removal close the frog gap?

``Profile Data and Preprocessing`` says points whose segment slope exceeds
40.9:1 are removed.  On ``Profile_Mileage_JBG.prr`` the number of steep
*segments* is 129, exactly the count Simpack reports in ``solver.log``, so one
point per steep segment is dropped.

This module measures what that does to the wheel/rail clearance at a station:
the wheel is placed at its static height (nominal radius minus the 0.4628 mm
static sink of the reference run) and ``d(y) = z_wheel(y) - z_rail(y)`` is
evaluated over the lateral overlap.  ``min d < 0`` means contact.

Usage::

    python gap_simpack_rules.py --station 79.96
    python gap_simpack_rules.py --scan 78.5 81.5 --step 0.05
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

from prep_simpack_rules import SLOPE_LIMIT, read_prr, steep_mask

CATALOG = Path(r"F:\ai道岔状态反演辨识\Velch\diagnostics\crh380a_m_track_catalog.json")
WHEEL = Path(
    r"G:\研究生\动力学\CRH380A_纯刚性模型\database\database\wheel_rail_profiles\LMA.prw"
)
STATIC_SINK_MM = 0.4628
RAIL_Y_OFFSET_MM = 753.0
WHEEL_Y_OFFSET_MM = 746.5


def drop_one_per_steep_segment(points: np.ndarray, limit: float = SLOPE_LIMIT) -> np.ndarray:
    """Remove the first point of every segment steeper than ``limit``."""
    dy = np.diff(points[:, 0])
    dz = np.diff(points[:, 1])
    with np.errstate(divide="ignore", invalid="ignore"):
        slope = np.where(np.abs(dy) > 1e-12, np.abs(dz / dy), np.inf)
    steep = np.abs(slope) > limit
    keep = np.ones(len(points), dtype=bool)
    keep[:-1] &= ~steep
    return points[keep]


def wheel_profile() -> np.ndarray:
    """LMA lower surface in absolute coordinates (mm, y across the track).

    ``.prw``/``.prr`` vertical values are metres (``units.len = m``), so both
    axes are scaled to millimetres before the nominal offsets are added.
    """
    _, points = read_prr(WHEEL)
    y = points[:, 0] * 1000.0 + WHEEL_Y_OFFSET_MM
    # ``z`` is the radius offset from the nominal rolling circle, so the
    # surface height is ``-z - sink`` (a positive offset means a smaller
    # radius, i.e. a higher point once the wheel is inverted through its centre).
    z = -points[:, 1] * 1000.0 - STATIC_SINK_MM
    order = np.argsort(y)
    return np.column_stack([y[order], z[order]])


def rail_profile(path: Path) -> np.ndarray:
    _, points = read_prr(path)
    y = points[:, 0] * 1000.0 + RAIL_Y_OFFSET_MM
    z = -points[:, 1] * 1000.0
    order = np.argsort(y)
    return np.column_stack([y[order], z[order]])


def clearance(rail: np.ndarray, wheel: np.ndarray) -> tuple[float, float]:
    lo = max(rail[:, 0].min(), wheel[:, 0].min())
    hi = min(rail[:, 0].max(), wheel[:, 0].max())
    if hi <= lo:
        return float("nan"), float("nan")
    grid = np.linspace(lo, hi, 4000)
    rz = np.interp(grid, rail[:, 0], rail[:, 1])
    wz = np.interp(grid, wheel[:, 0], wheel[:, 1])
    delta = wz - rz
    index = int(np.argmin(delta))
    return float(delta[index]), float(grid[index])


def station_files(station_m: float, tol: float = 2e-3) -> list[dict]:
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    refs = [
        ref for ref in catalog["profile_references"]
        if ref["side"] == "right" and abs(ref["station_m"] - station_m) <= tol
    ]
    return refs


def report(station_m: float) -> None:
    wheel = wheel_profile()
    for ref in station_files(station_m):
        path = Path(ref["path"])
        raw = rail_profile(path)
        kept = drop_one_per_steep_segment(raw)
        _, points = read_prr(path)
        mask = steep_mask(points)
        gap_raw, y_raw = clearance(raw, wheel)
        gap_new, y_new = clearance(kept, wheel)
        print(
            f"s={station_m:7.3f} {path.name:34s} pts {len(points):4d} "
            f"steep {int(mask.sum()):3d} | raw gap {gap_raw:+7.3f} mm @ {y_raw:7.2f} | "
            f"after removal {gap_new:+7.3f} mm @ {y_new:7.2f}"
        )


def scan(start: float, stop: float, step: float) -> None:
    wheel = wheel_profile()
    stations = np.round(np.arange(start, stop + 1e-9, step), 6)
    print(f"{'s':>8} {'file':>30} {'steep':>6} {'raw gap':>9} {'new gap':>9} {'y':>8}")
    for station_m in stations:
        for ref in station_files(float(station_m)):
            path = Path(ref["path"])
            _, points = read_prr(path)
            raw = rail_profile(path)
            kept = drop_one_per_steep_segment(raw)
            gap_raw, _ = clearance(raw, wheel)
            gap_new, y_new = clearance(kept, wheel)
            print(
                f"{station_m:8.4f} {path.name[:30]:>30} {int(steep_mask(points).sum()):6d} "
                f"{gap_raw:+9.3f} {gap_new:+9.3f} {y_new:8.2f}"
            )


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--station", type=float)
    ap.add_argument("--scan", nargs=2, type=float)
    ap.add_argument("--step", type=float, default=0.05)
    args = ap.parse_args(argv[1:])
    if args.scan:
        scan(args.scan[0], args.scan[1], args.step)
        return 0
    if args.station is not None:
        report(args.station)
        return 0
    print("give --station or --scan START STOP")
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
