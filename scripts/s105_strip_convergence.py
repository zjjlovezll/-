"""Is the 45 kN/mm lateral impedance a property of the geometry, or of the strip discretisation?

Round 243 measured, on the canonical 234-coordinate case, that 1 mm of wheelset lateral shift moves
45 kN between the two sides (k = -2641 kN/mm for the pair split) while the contact point itself
barely moves.  The normal force is produced by ``normal_policy = strip_integral``: the contact band is
cut into strips of ``strip_dy_m`` and each strip contributes its own Hertz force, so the *sum* is what
the wheel feels.  A coarse band discretisation can smooth or exaggerate dN/dy, and this script decides
which it is, before anyone touches the physics.

Pre-registered gates (written before the numbers are seen):

    G1  dN/dy changes by <= 5 % between the finest strip (1e-4) and the coarsest (5e-4)
        -> the impedance is geometry, not discretisation; the next suspect is the search itself
    G2  dN/dy moves monotonically with strip_dy and by more than 5 %
        -> it is the band integration; fix that (never the contact stiffness, never a tolerance)
    G3  the seated penetration at dy = 0 stays within 1 % of 63.70 um across the three values
        -> the three runs are the same physical state, so G1/G2 compare like with like

Whatever the answer, ``freeze_baseline --check`` must stay UNCHANGED: this script replaces parameters
in memory only and writes nothing into the packaged cases.

    PYTHONPATH=src python -X utf8 scripts/s105_strip_convergence.py
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import pathlib
import time

import numpy as np

from velch.vehicle import load_vehicle_case
from velch.vehicle_solver import VehicleDynamics, _seat

ROOT = pathlib.Path(__file__).resolve().parents[1]
CASE = ROOT / "vehicles" / "turnouts" / "CN60-1100-1_18" / "cases" / "straight_one_set.json"
OUT = ROOT.parent / "scratch" / "s105"
STRIP_DY_M = (5.0e-4, 2.5e-4, 1.0e-4)
SPEED_M_S = 80.0 / 3.6
ROLL_RADIUS_M = 0.43
SHIFT_MM = (0.0, 1.0)
SEATED_PEN_UM = 63.70
G1_TOL = 0.05
G3_TOL = 0.01


def measure(strip_dy_m: float) -> dict:
    case = load_vehicle_case(CASE)
    case = dataclasses.replace(
        case, contact=dataclasses.replace(case.contact, strip_dy_m=float(strip_dy_m))
    )
    assert case.contact.strip_dy_m == float(strip_dy_m)
    start = time.perf_counter()

    dynamics = VehicleDynamics(case)
    state = np.asarray(case.initial_q, dtype=float)
    velocity = np.asarray(case.initial_v, dtype=float)
    velocity[dynamics.topology.require("wheelset1", "spin")] = SPEED_M_S / ROLL_RADIUS_M
    state, residual = _seat(case, dynamics, state, velocity)
    state = np.asarray(state, dtype=float)
    y_index = dynamics.topology.require("wheelset1", "y")

    rows = []
    for shift_mm in SHIFT_MM:
        q = state.copy()
        q[y_index] = state[y_index] + shift_mm * 1e-3
        _, merged = dynamics.evaluate(0.0, q, velocity)
        contacts = dynamics.body_contacts
        row = {"shift_mm": shift_mm}
        for rail_id in ("axle1_left", "axle1_right"):
            response = merged[rail_id]
            bodies = [r for r in (contacts.get(rail_id) or ()) if r.active and r.geometry is not None]
            deepest = max(bodies, key=lambda r: r.geometry.penetration_m) if bodies else None
            row[rail_id] = {
                "normal_n": float(response.normal_force_n),
                "lever_y": None if deepest is None else float(deepest.geometry.lever_y_m),
                "penetration_m": None if deepest is None else float(deepest.geometry.penetration_m),
                "tilt": None if deepest is None else float(deepest.geometry.normal_y / deepest.geometry.normal_z),
            }
        rows.append(row)

    seated, shifted = rows[0], rows[1]
    out = {"strip_dy_m": float(strip_dy_m), "residual_n": float(residual),
           "wall_s": time.perf_counter() - start, "rows": rows}
    for rail_id in ("axle1_left", "axle1_right"):
        out[f"dN_dy_{rail_id}_kn_per_mm"] = (
            (shifted[rail_id]["normal_n"] - seated[rail_id]["normal_n"]) / 1e3
        ) / (SHIFT_MM[1] - SHIFT_MM[0])
        out[f"penetration_um_{rail_id}"] = (
            None if seated[rail_id]["penetration_m"] is None else seated[rail_id]["penetration_m"] * 1e6
        )
    out["dN_dy_pair_kn_per_mm"] = (out["dN_dy_axle1_left_kn_per_mm"]
                                   - out["dN_dy_axle1_right_kn_per_mm"])
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    results = [measure(value) for value in STRIP_DY_M]
    print(f"{'strip_dy (m)':>13} {'seat r (N)':>11} {'pen L/R (um)':>17} "
          f"{'dN/dy L':>9} {'dN/dy R':>9} {'pair':>9} {'wall (s)':>9}")
    for item in results:
        pen_l, pen_r = item["penetration_um_axle1_left"], item["penetration_um_axle1_right"]
        print(f"{item['strip_dy_m']:>13.1e} {item['residual_n']:>11.2e} "
              f"{pen_l:>8.2f}/{pen_r:<8.2f} {item['dN_dy_axle1_left_kn_per_mm']:>9.2f} "
              f"{item['dN_dy_axle1_right_kn_per_mm']:>9.2f} {item['dN_dy_pair_kn_per_mm']:>9.2f} "
              f"{item['wall_s']:>9.2f}")

    pair = [item["dN_dy_pair_kn_per_mm"] for item in results]
    coarse, fine = pair[0], pair[-1]
    g1 = abs(coarse - fine) <= G1_TOL * abs(fine)
    steps = [b - a for a, b in zip(pair, pair[1:])]
    monotone = all(step >= -1e-12 for step in steps) or all(step <= 1e-12 for step in steps)
    g2 = (not g1) and monotone
    pens = [item["penetration_um_axle1_left"] for item in results]
    g3 = all(abs(value - SEATED_PEN_UM) <= G3_TOL * SEATED_PEN_UM for value in pens)

    print(f"[G3] seated penetration {min(pens):.3f}-{max(pens):.3f} um vs {SEATED_PEN_UM:.2f} "
          f"-> {'PASS' if g3 else 'FAIL'}")
    print(f"[G1] pair dN/dy {coarse:.2f} -> {fine:.2f} kN/mm "
          f"({abs(coarse - fine) / abs(fine) * 100:.2f} %) -> {'PASS' if g1 else 'FAIL'}")
    print(f"[G2] monotone with strip_dy and > {G1_TOL:.0%} -> {'PASS' if g2 else 'FAIL'}")
    if g1 and g3:
        verdict = "the impedance is geometry, not the strip width"
    elif g2 and g3:
        verdict = "the impedance is the band integration -- fix strip_dy_m, not the contact law"
    else:
        verdict = "inconclusive: G3 failed, the three runs are not the same physical state"
    print("VERDICT:", verdict)

    if args.write:
        OUT.mkdir(parents=True, exist_ok=True)
        payload = {"results": results, "gates": {"G1": g1, "G2": g2, "G3": g3},
                   "verdict": verdict, "seated_penetration_um": SEATED_PEN_UM}
        (OUT / "strip_convergence.json").write_text(
            json.dumps(payload, indent=1, ensure_ascii=False) + chr(10), encoding="utf-8"
        )
        print(f"report -> {OUT / 'strip_convergence.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
