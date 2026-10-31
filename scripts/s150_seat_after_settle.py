"""Where the corrected 60 km/h case dies: the re-seat after the modal settle.

`_integrate_vehicle` (src/velch/vehicle_solver.py:1894-1902) does

    seat -> (settle, seat) x2

and round 294 found that the corrected 60 km/h case never leaves that block:
`one_set_x46` at 60 km/h raises before the first output frame while the identical
geometry at 80 km/h runs.  This probe replicates the sequence without integrating and
reports which stage fails, how far the wheel sits afterwards, and which lateral seeds
(in micrometres on all four wheelsets) bring the second seat back.

Reported on purpose: the stage that fails, the wheel height and lateral offset of the
first seed that converges.  NOT reported: any amplitude, any speed-transfer claim.  A
convergent seed on an off-centre branch is a branch, not an answer.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import velch.vehicle_solver as vs  # noqa: E402
from velch.solver import SimulationFailure  # noqa: E402
from velch.vehicle import load_vehicle_case  # noqa: E402

CASE = Path(r"F:/ai道岔状态反演辨识/scratch/s146/one_set_x46.json")
SPEEDS = (60.0, 80.0)
SEEDS_UM = (0.0, 200.0, -200.0, 500.0, -500.0)
REPORT = ROOT / "reports" / "load_split_inversion_2026-10-31" / "seat_chain.json"


def seated(case, speed_kmh):
    dyn = vs.VehicleDynamics(case)
    q = np.asarray(case.initial_q, dtype=float)
    v = np.asarray(case.initial_v, dtype=float)
    for axle in (1, 2, 3, 4):
        v[dyn.topology.require(f"wheelset{axle}", "spin")] = speed_kmh / 3.6 / 0.43
    return dyn, q, v


def chain(case, speed_kmh):
    """Replicate seat -> (settle, seat) x2 exactly, stopping at the first failure."""
    dyn, q, v = seated(case, speed_kmh)
    record = {"speed_kmh": speed_kmh, "stages": [], "failed_at": None, "error": None}
    try:
        q, residual = vs._seat(case, dyn, q, v)
        record["stages"].append({"stage": "seat#1", "residual_n": float(residual)})
        z_row = dyn.topology.require("wheelset1", "z")
        y_row = dyn.topology.require("wheelset1", "y")
        record["stages"][-1]["wheel_z_um"] = float(q[z_row]) * 1e6
        for index in range(2):
            stage = f"settle#{index + 1}"
            q = vs._settle_modal_coordinates(dyn, q, v)
            record["stages"].append({"stage": stage, "wheel_z_um": float(q[z_row]) * 1e6})
            stage = f"seat#{index + 2}"
            q, residual = vs._seat(case, dyn, q, v)
            record["stages"].append(
                {
                    "stage": stage,
                    "residual_n": float(residual),
                    "wheel_z_um": float(q[z_row]) * 1e6,
                    "wheel_y_um": float(q[y_row]) * 1e6,
                }
            )
        record["ok"] = True
    except SimulationFailure as exc:
        record["ok"] = False
        record["failed_at"] = record["stages"][-1]["stage"] if record["stages"] else "seat#1"
        record["error"] = str(exc).splitlines()[0][:160]
    return record


def seed_sweep(case, speed_kmh, seeds_um=SEEDS_UM):
    """After the first settle, which lateral seeds re-seat successfully, and where?"""
    dyn, q, v = seated(case, speed_kmh)
    q, _ = vs._seat(case, dyn, q, v)
    q = vs._settle_modal_coordinates(dyn, q, v)
    y_rows = [dyn.topology.require(f"wheelset{axle}", "y") for axle in (1, 2, 3, 4)]
    z_row = dyn.topology.require("wheelset1", "z")
    rows = []
    for dy_um in seeds_um:
        seed = q.copy()
        for row in y_rows:
            seed[row] += dy_um * 1e-6
        try:
            out, residual = vs._seat(case, dyn, seed, v)
            rows.append(
                {
                    "dy_um": dy_um,
                    "ok": True,
                    "residual_n": float(residual),
                    "wheel_z_um": float(out[z_row]) * 1e6,
                    "wheel_y_um": float(out[y_rows[0]]) * 1e6,
                }
            )
        except SimulationFailure as exc:
            rows.append({"dy_um": dy_um, "ok": False, "error": str(exc).splitlines()[0][:120]})
    return rows


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--speeds", nargs="+", type=float, default=list(SPEEDS))
    parser.add_argument("--seeds", nargs="+", type=float, default=list(SEEDS_UM))
    parser.add_argument("--no-seeds", action="store_true", help="chain only")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args(argv)

    case = load_vehicle_case(CASE)
    chains = []
    for speed in args.speeds:
        record = chain(case, speed)
        chains.append(record)
        stages = " | ".join(
            f"{s['stage']}" + (f" r={s['residual_n']:.1e}" if "residual_n" in s else "")
            + (f" z={s['wheel_z_um']:.1f}" if "wheel_z_um" in s else "")
            for s in record["stages"]
        )
        print(f"== {speed:.0f} km/h -> {'ok' if record['ok'] else 'FAILED at ' + str(record['failed_at'])}")
        print(f"   {stages}")
        if not record["ok"]:
            print(f"   {record['error']}")

    sweep = []
    if not args.no_seeds:
        for speed in args.speeds:
            rows = seed_sweep(case, speed, tuple(args.seeds))
            sweep.append({"speed_kmh": speed, "rows": rows})
            print(f"-- lateral seed sweep at {speed:.0f} km/h")
            for row in rows:
                if row["ok"]:
                    print(f"   dy {row['dy_um']:+8.1f} um -> residual {row['residual_n']:.2e} N  "
                          f"z {row['wheel_z_um']:8.1f} um  y {row['wheel_y_um']:+8.1f} um")
                else:
                    print(f"   dy {row['dy_um']:+8.1f} um -> {row['error'][:70]}")

    failing = [c["speed_kmh"] for c in chains if not c["ok"]]
    off_centre = [
        (s["speed_kmh"], r["dy_um"], r["wheel_y_um"])
        for s in sweep
        for r in s["rows"]
        if r["ok"] and abs(r.get("wheel_y_um", 0.0)) > 100.0
    ]
    print()
    print(f"[CHAIN] speeds that fail before the first frame: {failing or 'none'}")
    print(f"[CHAIN] seeds that converge only off-centre (|y| > 100 um): {off_centre or 'none'}")
    print("[CHAIN] an off-centre convergent seed is a branch, not an answer")

    if args.write:
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_text(
            json.dumps(
                {"case": str(CASE), "chains": chains, "seed_sweep": sweep,
                 "failing_speeds": failing, "off_centre_seeds": off_centre},
                indent=2,
            ),
            encoding="utf-8",
        )
        print(f"report -> {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
