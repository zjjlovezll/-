"""M0 verdict: the per-body sum identity, and where the blade may legitimately start carrying.

Two quantities live here, and they are deliberately computed in this order:

1. **the geometry's own prediction** -- sweep the drawn sections, take each body's crown (``max z``,
   which is the running surface because z is positive up after ``z_sign = -1``), and find the station
   where the blade crown comes within the static penetration (65.4661 um) of the stock crown.  That
   station is a property of the *sections*, not of the run, so it can be written down before any
   dynamics is integrated.
2. **what the run actually did** -- read ``../scratch/s97/attribution_<duration>s.json`` and compare
   each axle's first carrying station against (1).

The comparison is not a calibration.  On a 6.4 m ramp the blade force grows continuously from zero, so
a detector that counts "carrying" from 1 kN necessarily reports a station *after* first touch; the gap
between the two is reported, not hidden.

    python -X utf8 scripts/s98_m0_verdict.py [--duration 0.85] [--write]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib

import numpy as np

from velch.vehicle import load_vehicle_case

ROOT = pathlib.Path(__file__).resolve().parents[1]
CASE = ROOT / "vehicles" / "turnouts" / "CN60-1100-1_18" / "cases" / "straight.json"
SCRATCH = ROOT.parent / "scratch"
STATIC_PENETRATION_M = 65.4661e-6
RAIL = "axle1_right"
SWEEP_STEP_M = 0.005


def crown_m(series, station_m: float) -> float:
    """Highest z of that series at that station, in the model frame."""
    return float(np.max(np.asarray(series.sample(station_m, 1.0).profile.z_m, dtype=float)))


def geometry(case) -> dict:
    """Crown gap between the blade and the stock, and the stations it implies."""
    rail = next(item for item in case.rails if item.id == RAIL)
    bodies = {body.id: body for body in rail.contact_bodies}
    stock, blade = bodies["stock"], bodies["blade"]
    low = float(blade.series.lowest_m)
    high = min(float(blade.series.highest_m), low + 40.0)
    stations = np.arange(low, high, SWEEP_STEP_M)
    gaps = np.array([crown_m(blade.series, float(s)) - crown_m(stock.series, float(s))
                     for s in stations])
    flush = float(stations[int(np.argmin(np.abs(gaps)))])
    # The *first* crossing, not the station closest to zero anywhere: past the ramp the two crowns
    # wobble within a few tens of microns of each other, so a global argmin lands wherever the wobble
    # happens to vanish (it reported 71.003 m once, 12.6 m after the blade actually reaches the top).
    above = np.nonzero(gaps >= 0.0)[0]
    first_crossing = float(stations[int(above[0])]) if above.size else float("nan")
    touch = float(stations[int(np.argmin(np.abs(gaps + STATIC_PENETRATION_M)))])
    return {
        "rail": RAIL,
        "blade_lowest_m": low,
        "blade_highest_m": float(blade.series.highest_m),
        "tip_gap_mm": float(gaps[0]) * 1e3,
        "flush_station_m": first_crossing,
        "closest_to_zero_station_m": flush,
        "first_touch_station_m": touch,
        "max_above_stock_mm": float(gaps.max()) * 1e3,
        "max_above_stock_at_m": float(stations[int(np.argmax(gaps))]),
        "sweep_step_m": SWEEP_STEP_M,
    }


def read_run(duration_s: float) -> dict:
    path = SCRATCH / "s97" / f"attribution_{duration_s:g}s.json"
    if not path.exists():
        raise SystemExit(f"missing {path}; run scripts/s97_body_attribution.py --duration {duration_s:g}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["_path"] = str(path)
    payload["_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    return payload


def verdict(run: dict, geom: dict) -> dict:
    first = run["first_loaded"]
    rows = []
    for entry in first:
        if entry["body"] != "blade":
            continue
        carry = entry["first_carrying"]
        if carry is None:
            rows.append({"rail": entry["rail"], "first_carrying_m": None, "offset_m": None})
            continue
        rows.append({
            "rail": entry["rail"],
            "first_carrying_m": float(carry["station_m"]),
            "force_at_first_carrying_n": float(carry["force_n"]),
            "peak_n": float(entry["peak_n"]),
            "peak_station_m": float(entry["peak_station_m"]),
            "offset_m": float(carry["station_m"]) - geom["first_touch_station_m"],
        })
    # A blade body may not carry before the sections bring its crown within one static penetration.
    tolerance_m = 0.10
    early = [row for row in rows
             if row["first_carrying_m"] is not None
             and row["first_carrying_m"] < geom["first_touch_station_m"] - tolerance_m]
    return {
        "geometry": geom,
        "blade_rows": rows,
        "identity_max_relative": float(run["identity_max_relative"]),
        "identity_gate": float(run["identity_gate"]),
        "m0_1_identity_ok": bool(run["identity_ok"]),
        "m0_2_no_early_blade_ok": not early,
        "early_blade_rows": early,
        "early_tolerance_m": tolerance_m,
        "gates": run["gates"],
        "all_gates": bool(all(run["gates"].values())),
        "duration_s": float(run["duration_s"]),
        "speed_m_s": float(run["speed_m_s"]),
        "case": run["case"],
        "run_json": run["_path"],
        "run_json_sha256": run["_sha256"],
        "wall_s": float(run["wall_s"]),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--duration", type=float, default=0.85)
    ap.add_argument("--write", action="store_true", help="write scratch/s98/m0_verdict.json")
    args = ap.parse_args()

    case = load_vehicle_case(CASE)
    geom = geometry(case)
    run = read_run(args.duration)
    result = verdict(run, geom)

    print(f"geometry  tip gap {geom['tip_gap_mm']:+8.3f} mm   "
          f"flush at {geom['flush_station_m']:7.3f} m   "
          f"first touch (65.4661 um) at {geom['first_touch_station_m']:7.3f} m")
    print(f"          blade never more than {geom['max_above_stock_mm']:+.3f} mm above the stock "
          f"(at {geom['max_above_stock_at_m']:.2f} m)")
    print(f"[M0-1] max |sum(bodies) - merged| / merged = {result['identity_max_relative']:.3e} "
          f"(gate {result['identity_gate']:.0e})  -> {'PASS' if result['m0_1_identity_ok'] else 'FAIL'}")
    print(f"{'rail':<14}{'first carry (m)':>17}{'offset vs geometry':>20}{'peak (kN)':>11}{'peak at (m)':>13}")
    for row in result["blade_rows"]:
        if row["first_carrying_m"] is None:
            print(f"{row['rail']:<14}{'-':>17}{'-':>20}{'-':>11}{'-':>13}")
            continue
        print(f"{row['rail']:<14}{row['first_carrying_m']:>17.3f}{row['offset_m']:>+20.3f}"
              f"{row['peak_n']/1e3:>11.2f}{row['peak_station_m']:>13.3f}")
    print(f"[M0-2] no blade carries before first touch - {result['early_tolerance_m']:.2f} m -> "
          f"{'PASS' if result['m0_2_no_early_blade_ok'] else 'FAIL'}")
    for row in result["early_blade_rows"]:
        print(f"        !! {row['rail']} carries at {row['first_carrying_m']:.3f} m")
    print(f"[gates] {sum(bool(v) for v in result['gates'].values())}/{len(result['gates'])} "
          f"({result['duration_s']:g} s simulated in {result['wall_s']:.0f} s wall)")

    if args.write:
        out = SCRATCH / "s98" / "m0_verdict.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(result, ensure_ascii=False, indent=1) + chr(10), encoding="utf-8")
        print(f"wrote {out}")

    return 0 if result["m0_1_identity_ok"] and result["m0_2_no_early_blade_ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
