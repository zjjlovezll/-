"""Read the design lowering profile out of a turnout case's own station table.

WHY THIS EXISTS
===============
P1 of the current objective does not need an irregularity we wrote ourselves:
the turnout already carries a *designed* vertical geometry -- the switch rail and
the long point rail are made lower than the stock rail, and that lowering is the
"truth" the inversion has to recover.  This script extracts it from the case the
solver actually integrates (not from a drawing table), so the truth and the
simulation can never drift apart.

WHERE THE LOWERING LIVES
========================
Each rail owns a station table: one entry every 5 mm, and each entry names a
profile file (``.prr``) plus a lateral offset.  As a wheel runs along the turnout
its support switches between stock rail, switch rail and point rail, and the
station table is exactly where that switch happens -- so the *crown height*
``max(z)`` of the profile sampled at each station IS the design elevation of the
running surface.  A switch rail that sits 23 mm low shows up as the crown being
23 mm lower wherever that rail carries the wheel.

The measured table is written as JSON (mileage, crown height, the profile file in
force) and a compact console table, so the inversion in the next step has a
number to be compared against.

Recompute::

    PYTHONPATH=src python -X utf8 scripts/s51_case_lowering.py \
        --case F:/velch_data/validation/crh380a_m/case_diverging_R1100.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from velch.vehicle import load_vehicle_case

HERE = Path(__file__).resolve().parents[1]
DEFAULT_CASE = Path(r"F:/velch_data/validation/crh380a_m/case_diverging_R1100.json")


def _stations(series):
    """Mileages a ``ProfileSeries`` carries, under whichever name it uses."""
    for name in ("stations_m", "mileages_m", "stations"):
        value = getattr(series, name, None)
        if value is not None:
            return np.asarray(value, dtype=float)
    raise SystemExit(f"{type(series).__name__} exposes no station mileages: {dir(series)[:20]}")


def crown_profile(case, rail_index: int, step_m: float):
    """Sample one rail's running-surface elevation against mileage.

    A rail owns one or more ``RailBody`` segments, each with its own station
    table, so the sweep walks the bodies in order rather than assuming a single
    one.
    """
    rail = case.rails[rail_index]
    rows = []
    for body in rail.bodies:
        stations = _stations(body.series)
        if stations.size == 0:
            continue
        first, last = float(stations.min()), float(stations.max())
        mileage = np.arange(first, last + 0.5 * step_m, step_m)
        for s in mileage:
            sample = body.series.sample(float(s), 1.0)
            profile = sample.profile
            z = np.asarray(profile.z_m, dtype=float)
            y = np.asarray(profile.y_m, dtype=float)
            if z.size == 0 or not np.isfinite(z).any():
                continue
            # The crown is the highest point of the running surface; for a
            # lowered blade the whole profile sits lower, so max(z) follows the
            # design elevation.
            k = int(np.nanargmax(z))
            rows.append(
                {
                    "s_m": float(s),
                    "body": body.id,
                    "crown_z_mm": float(z[k] * 1.0e3),
                    "crown_y_mm": float(y[k] * 1.0e3),
                    "profile": Path(str(profile.source)).name if getattr(profile, "source", None) else "",
                }
            )
    rows.sort(key=lambda r: r["s_m"])
    return rail, rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", type=Path, default=DEFAULT_CASE)
    parser.add_argument("--rail-index", type=int, default=0)
    parser.add_argument("--step", type=float, default=1.0, help="sampling step along the line, m")
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    case = load_vehicle_case(args.case)
    rail, rows = crown_profile(case, args.rail_index, args.step)
    print(f"case            {Path(str(args.case)).name}")
    print(f"rail            {rail.id}  (template {rail.template_id!r})")
    print(f"samples         {len(rows)}  step {args.step} m")
    if not rows:
        return 1
    z = np.array([r["crown_z_mm"] for r in rows])
    s = np.array([r["s_m"] for r in rows])
    print(f"crown height    min {z.min():+.3f} mm  max {z.max():+.3f} mm  span {z.max() - z.min():.3f} mm")
    dz = np.diff(z)
    print(f"largest step    {dz.max():+.3f} mm over {args.step} m  at s = {s[int(dz.argmax())]:.2f} m")
    print(f"largest drop    {dz.min():+.3f} mm over {args.step} m  at s = {s[int(dz.argmin())]:.2f} m")
    print()
    print("  mileage   crown_z(mm)   change(mm)   profile")
    previous = None
    for row in rows:
        change = "" if previous is None else f"{row['crown_z_mm'] - previous:+8.3f}"
        print(f"  {row['s_m']:8.2f}  {row['crown_z_mm']:10.3f}   {change:>8}   {row['profile']}")
        previous = row["crown_z_mm"]

    out = args.out
    if out is None:
        out = HERE.parent / "scratch" / "s51" / f"crown_{rail.id}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(
            {
                "case": str(args.case),
                "rail": rail.id,
                "template": rail.template_id,
                "step_m": args.step,
                "crown_z_mm_min": float(z.min()),
                "crown_z_mm_max": float(z.max()),
                "rows": rows,
            },
            indent=1,
        ),
        encoding="utf-8",
    )
    print(f"\nwritten {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
