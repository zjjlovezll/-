"""M2: does the lateral registration come right if the rails are moved back under the wheels?

``scripts/s85_db_case.py:81`` holds ``CROWN_OFFSET_M = 13.0e-3``: every station cancels its own crown
y and then pushes the crown 13.0 mm *outward* from the wheel plane.  The comment records how that
number was found -- eight wheels at 1.000x share for any offset in 12.0-13.7 mm, shoulder contact
below 10 mm, separation above 14 mm -- but it was fitted against the 35-coordinate rigid-wheelset car,
while the canonical case is now the 86-coordinate car with flexible wheelsets.

This sweep re-fits that one number against the canonical car.  The variant cases are produced by
translating ``y_offset_m`` (the crown offset enters the profile as a pure lateral shift), so the
builder and the packaged case are untouched -- the sweep lives entirely in ``scratch/s104``.

Pre-registered gates (all four must hold, task book M2):

    1  seat: 8/8 contacts in [0.625, 1.6] x fair share, residual <= 1e-5 N
    2  contact on the crown: |lever_y - crown_y| <= 2 mm on both sides
    3  d(lever_y)/dy in [0.5, 1.0]           (the contact must follow the wheel)
    4  k_lat in [10, 100] kN/mm, monotone, and no contact lost over +-3 mm

If no offset satisfies all four, the conclusion is that the registration is not a constant to be
re-fitted and the contact search itself has to change -- that is the honest reading, and it is
written down before the numbers are seen.

    PYTHONPATH=src python -X utf8 scripts/s104_crown_offset_sweep.py
    PYTHONPATH=src python -X utf8 scripts/s104_crown_offset_sweep.py --write
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import pathlib

import numpy as np

from velch.vehicle import load_vehicle_case
from velch.vehicle_solver import SimulationFailure, VehicleDynamics, _seat

ROOT = pathlib.Path(__file__).resolve().parents[1]
CASE = ROOT / "vehicles" / "turnouts" / "CN60-1100-1_18" / "cases" / "straight_one_set.json"
OUT = ROOT.parent / "scratch" / "s104"
OFFSETS_MM = (13.0, 10.0, 8.0, 4.0, 0.0)
SPEED_M_S = 80.0 / 3.6
ROLL_RADIUS_M = 0.43
SHIFTS_MM = (-3.0, -2.0, -1.0, 0.0, 1.0, 2.0, 3.0)
SHARE_LO, SHARE_HI = 0.625, 1.6
ON_CROWN_TOL_M = 2.0e-3
SEAT_TOL_N = 1.0e-5
K_LO, K_HI = 10.0, 100.0


def _module(name: str, path: pathlib.Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


REG = _module("s103_lateral_registration", ROOT / "scripts" / "s103_lateral_registration.py")


def shift_the_crowns(case: dict, offset_mm: float, base_mm: float = 13.0) -> dict:
    """Move both rails in/out so the crown sits ``offset_mm`` outside the wheel plane."""
    delta = (offset_mm - base_mm) * 1e-3

    def move(stations: list[dict], side: int) -> None:
        for item in stations:
            profile = item["profile"]
            profile["y_offset_m"] = float(profile["y_offset_m"]) + side * delta

    for template in case["rail_templates"]:
        side = -1 if template["id"].endswith("left") else 1
        move(template["stations"], side)
        for body in template.get("bodies") or ():
            move(body["stations"], side)
    return case


def measure(case_path: pathlib.Path) -> dict:
    case = load_vehicle_case(case_path)
    dynamics = VehicleDynamics(case)
    state = np.asarray(case.initial_q, dtype=float)
    velocity = np.asarray(case.initial_v, dtype=float)
    velocity[dynamics.topology.require("wheelset1", "spin")] = SPEED_M_S / ROLL_RADIUS_M
    seated, residual = _seat(case, dynamics, state, velocity)
    state = np.asarray(seated, dtype=float)

    rail_ids = [rail.id for rail in case.rails]
    station = float(case.run.x_start_m) + float(case.vehicle.axle_offsets_m[0])
    rails = {rail.id: rail for rail in case.rails}
    crowns = {rail_id: REG.crown_y(rails[rail_id].contact_bodies[0].series, station)
              for rail_id in rail_ids}

    initial = dynamics.evaluate(0.0, state, velocity)
    _, frame = initial
    total = sum(float(frame[r].normal_force_n) if frame.get(r) is not None else 0.0 for r in rail_ids)
    shares = {r: (float(frame[r].normal_force_n) / (total / len(rail_ids))
                  if frame.get(r) is not None and total > 0 else 0.0) for r in rail_ids}
    seat_ok = bool(residual <= SEAT_TOL_N
                   and all(SHARE_LO <= value <= SHARE_HI for value in shares.values()))

    y_index = dynamics.topology.require("wheelset1", "y")
    pairs = ("axle1_left", "axle1_right")
    rows = []
    for shift_mm in SHIFTS_MM:
        q = state.copy()
        q[y_index] = state[y_index] + shift_mm * 1e-3
        _, merged = dynamics.evaluate(0.0, q, velocity)
        reading = REG.read(merged, dynamics, pairs)
        rows.append({"shift_mm": shift_mm, "contacts": reading,
                     "sum_lateral_n": sum(reading[r]["lateral_n"] for r in pairs)})

    out = {"residual_n": float(residual), "seat_ok": seat_ok, "shares": shares,
           "crown_y": crowns, "station_m": station, "rows": rows}
    for rail_id in pairs:
        levers = [(row["shift_mm"], row["contacts"][rail_id]["lever_y"]) for row in rows]
        pairs_ok = [(a[0] - b[0], a[1] - b[1]) for a, b in zip(levers, levers[1:])
                    if a[1] is not None and b[1] is not None and a[0] != b[0]]
        slope = None
        if pairs_ok:
            slope = (sum(ds * dl for ds, dl in pairs_ok) / sum(ds * ds for ds, _ in pairs_ok))
        base = next(row for row in rows if row["shift_mm"] == 0.0)["contacts"][rail_id]["lever_y"]
        out[f"d_lever_{rail_id}"] = slope
        out[f"lever_minus_crown_{rail_id}"] = None if base is None else (base - crowns[rail_id])
        out[f"lost_{rail_id}"] = [row["shift_mm"] for row in rows
                                  if not row["contacts"][rail_id]["active"]]
    lateral = [(row["shift_mm"], row["sum_lateral_n"]) for row in rows]
    num = sum((b[0] - a[0]) * 1e-3 * (b[1] - a[1]) for a, b in zip(lateral, lateral[1:]))
    den = sum(((b[0] - a[0]) * 1e-3) ** 2 for a, b in zip(lateral, lateral[1:]))
    out["k_lat_kn_per_mm"] = None if not den else num / den / 1e3
    monotone = all((b[1] - a[1]) * (1 if (b[0] - a[0]) > 0 else -1) <= 0
                   for a, b in zip(lateral, lateral[1:]))
    out["monotone"] = bool(monotone)
    out["gates"] = {
        "seat": seat_ok,
        "on_crown": all(out[f"lever_minus_crown_{r}"] is not None
                        and abs(out[f"lever_minus_crown_{r}"]) <= ON_CROWN_TOL_M for r in pairs),
        "follows_wheel": all(out[f"d_lever_{r}"] is not None
                             and 0.5 <= out[f"d_lever_{r}"] <= 1.0 for r in pairs),
        "stiffness": bool(out["k_lat_kn_per_mm"] is not None
                          and K_LO <= abs(out["k_lat_kn_per_mm"]) <= K_HI
                          and out["monotone"]
                          and not out[f"lost_{pairs[0]}"] and not out[f"lost_{pairs[1]}"]),
    }
    out["passes_all"] = all(out["gates"].values())
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    base = json.loads(CASE.read_text(encoding="utf-8"))
    results = {}
    print(f"{'offset':>7} {'seat r':>9} {'share':>13} {'lever-crown L/R':>19} "
          f"{'d lever/dy':>11} {'k_lat':>10} {'lost':>10}  gates")
    for offset in OFFSETS_MM:
        variant = shift_the_crowns(json.loads(json.dumps(base)), offset)
        OUT.mkdir(parents=True, exist_ok=True)
        path = OUT / f"one_set_off{offset:04.1f}.json"
        path.write_text(json.dumps(variant, ensure_ascii=False) + chr(10), encoding="utf-8")
        try:
            reading = measure(path)
        except SimulationFailure as failure:
            print(f"{offset:>7.1f} seat FAILED: {failure}")
            results[offset] = {"seat_failed": str(failure)}
            continue
        results[offset] = reading
        gates = reading["gates"]
        lost = reading["lost_axle1_left"] + reading["lost_axle1_right"]
        print(f"{offset:>7.1f} {reading['residual_n']:>9.2e} "
              f"{min(reading['shares'].values()):>5.2f}-{max(reading['shares'].values()):<7.2f} "
              f"{reading['lever_minus_crown_axle1_left'] * 1e3:>+8.2f}/{reading['lever_minus_crown_axle1_right'] * 1e3:>+8.2f} "
              f"{reading['d_lever_axle1_left']:>11.4f} {reading['k_lat_kn_per_mm']:>10.1f} "
              f"{str(lost):>10}  "
              + ",".join(f"{k}={'Y' if v else 'N'}" for k, v in gates.items())
              + ("  PASS" if reading["passes_all"] else ""))

    if args.write:
        OUT.mkdir(parents=True, exist_ok=True)
        payload = {f"{offset:g}": value for offset, value in results.items()}
        (OUT / "sweep.json").write_text(json.dumps(payload, indent=1, ensure_ascii=False) + chr(10),
                                        encoding="utf-8")
        print(f"report -> {OUT / 'sweep.json'}")
    any_pass = any(value.get("passes_all") for value in results.values())
    print("VERDICT:", "an offset satisfies all four gates" if any_pass
          else "no offset satisfies all four -- the registration is not a constant to re-fit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
