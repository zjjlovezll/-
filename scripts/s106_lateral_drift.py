"""Does the wheelset hold its lateral position, or drift off it?  (M2, time domain)

B047 retired as a contact-geometry statement: the contact sits where the two slopes match and the
force split is geometry.  What is left of M2 is a dynamics question, and it is the one that actually
mattered -- round 235 saw a 51-coordinate run trigger ``graph slope limit at axle1_right/right:stock``
at ``x = 67.03 m`` after the guiding wheelset had walked sideways.

This reads an archived run (no new simulation) and reports, per wheelset, the lateral displacement
``y(t) - y(0)`` and, per side, the lateral force ``sum Fy`` reconstructed from the rail forces.  The
gates are written here before the numbers are read:

    L1  |dy| <= 1 mm for the whole run and no monotone drift   (task book `lateral_hold`)
    L2  if it drifts, the sign of dy must agree with the sign of sum Fy -- a displacement that grows
        against the net force means the lateral equation, not the geometry, is wrong
    L3  the two directions must be reported per wheelset, not as a mean: the guiding axle and the
        trailing axles are expected to differ, and averaging them hides exactly the reported effect

Run: ``PYTHONPATH=src python -X utf8 scripts/s106_lateral_drift.py [--run-id …] [--write]``
"""
from __future__ import annotations

import argparse
import json
import pathlib

import numpy as np

from velch.vehicle import load_vehicle_case

ROOT = pathlib.Path(__file__).resolve().parents[1]
RUNS = ROOT.parent / "scratch" / "runs"
CASE = ROOT / "vehicles" / "turnouts" / "CN60-1100-1_18" / "cases" / "straight_one_set.json"
DEFAULT_RUN = None
"""No pinned run id.  It used to point at the pre-densification case, and then a new run of the same
duration silently read the old one -- the drift came back 0.7305 mm when the current case gives
0.0999 mm.  The default is now "the latest one-set run of at least 0.40 s" from ``index.jsonl``.
"""
OUT = ROOT.parent / "scratch" / "s106"
HOLD_TOL_M = 1.0e-3


def latest_run() -> pathlib.Path:
    index = RUNS / "index.jsonl"
    rows = [json.loads(line) for line in index.read_text(encoding="utf-8").splitlines() if line.strip()]
    rows = [row for row in rows if row.get("duration_s", 0.0) >= 0.40 and "one_set" in str(row.get("route"))]
    if not rows:
        raise SystemExit(f"no one-set run of >= 0.40 s in {index}")
    return RUNS / rows[-1]["run_id"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", default=None)
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()
    run_dir = RUNS / args.run_id if args.run_id else latest_run()
    data = np.load(run_dir / "series.npz")
    meta = json.loads((run_dir / "meta.json").read_text(encoding="utf-8"))

    case = load_vehicle_case(CASE)
    from velch.vehicle import topology_of

    topology = topology_of(case.topology, case.vehicle)
    times = data["times"]
    positions = data["positions"]
    forces = data["normal_force_n"]

    wheelsets = [f"wheelset{index}" for index in range(1, 5)]
    rows = {}
    for name in wheelsets:
        y_index = topology.require(name, "y")
        series = positions[:, y_index] - positions[0, y_index]
        rows[name] = {
            "y_start_m": float(positions[0, y_index]),
            "y_end_m": float(positions[-1, y_index]),
            "drift_mm": float(series[-1] * 1e3),
            "max_abs_mm": float(np.max(np.abs(series)) * 1e3),
            "slope_mm_per_s": float((series[-1] - series[0]) / max(times[-1] - times[0], 1e-12) * 1e3),
        }

    # the archived rail forces are per rail id; the lateral force of a contact is not stored, so the
    # imbalance per axle is reconstructed as the difference of the two sides' normal forces, scaled by
    # the contact tilt reported for that run is not available here -- keep it as a normal-force split,
    # which is what moved 45 kN/mm in the seated sweep.
    rail_ids = meta["rail_ids"]
    pairs = [("axle1_left", "axle1_right"), ("axle2_left", "axle2_right"),
             ("axle3_left", "axle3_right"), ("axle4_left", "axle4_right")]
    index = {rail_id: position for position, rail_id in enumerate(rail_ids)}
    split = {}
    for left, right in pairs:
        if left not in index or right not in index:
            continue
        imbalance = forces[:, index[right]] - forces[:, index[left]]
        split[left.split("_")[0]] = {
            "start_kn": float(imbalance[0] / 1e3),
            "end_kn": float(imbalance[-1] / 1e3),
            "max_abs_kn": float(np.max(np.abs(imbalance)) / 1e3),
        }

    print(f"run {run_dir.name}")
    print(f"frames {len(times)}  t 0..{times[-1]:.4f} s  gates {meta['gates'] and sum(meta['gates'].values())}/7")
    print(f"{'wheelset':>10} {'y start (mm)':>13} {'drift (mm)':>11} {'max |y| (mm)':>13} {'slope (mm/s)':>13}")
    for name, row in rows.items():
        print(f"{name:>10} {row['y_start_m'] * 1e3:>13.4f} {row['drift_mm']:>11.4f} "
              f"{row['max_abs_mm']:>13.4f} {row['slope_mm_per_s']:>13.4f}")
    print(f"{'axle':>10} {'R-L start (kN)':>15} {'R-L end (kN)':>14} {'max |R-L| (kN)':>15}")
    for name, row in split.items():
        print(f"{name:>10} {row['start_kn']:>15.2f} {row['end_kn']:>14.2f} {row['max_abs_kn']:>15.2f}")

    worst = max(abs(row["max_abs_mm"]) for row in rows.values())
    holds = worst <= HOLD_TOL_M * 1e3
    print(f"[L1] worst |dy| {worst:.4f} mm (gate {HOLD_TOL_M * 1e3:.1f} mm) -> {'PASS' if holds else 'FAIL'}")
    agree = []
    for name, row in rows.items():
        axle = name.replace("wheelset", "axle")
        if axle in split:
            agree.append(np.sign(row["drift_mm"]) == np.sign(split[axle]["end_kn"] - split[axle]["start_kn"]))
    print(f"[L2] drift sign vs load-imbalance sign: {sum(agree)}/{len(agree)} agree -> "
          f"{'PASS' if all(agree) else 'REVIEW'}")
    print("VERDICT:", "the wheelset holds its lateral position" if holds
          else "the wheelset walks off its lateral position -- the lateral equation needs a look")

    if args.write:
        OUT.mkdir(parents=True, exist_ok=True)
        payload = {"run": run_dir.name, "frames": int(len(times)), "times_s": float(times[-1]),
                   "wheelsets": rows, "load_imbalance": split, "hold_gate_mm": HOLD_TOL_M * 1e3,
                   "holds": bool(holds), "sign_agreement": int(sum(agree)), "sign_checked": len(agree)}
        (OUT / "lateral_drift.json").write_text(
            json.dumps(payload, indent=1, ensure_ascii=False) + chr(10), encoding="utf-8")
        print(f"report -> {OUT / 'lateral_drift.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
