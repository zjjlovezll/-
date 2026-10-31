"""Is the rail support compliance a real gap error, or common mode?

Round 253 named "the two bodies' support compliance" as the physics the model was missing.  That claim
deserves a measurement before it earns a paragraph in any report: in a ``local_compliant`` track there is
**one node pair per rail**, and the stock and blade bodies of the right rail are two bodies on the *same*
node.  If so, both surfaces descend together, the gap ``d(s)`` is a difference, and the sink cancels --
which would make the round 253 explanation wrong.

This script measures it: seat the canonical case, read the rail node's vertical coordinate and the total
normal force on that rail, and check the sink against ``k_z`` (5.0e7 N/m per rail in the case) and against
force balance.  It also prints the per-body split at the same frame, so the "shared node" claim is visible
rather than asserted.
"""
from __future__ import annotations

import json
import pathlib
import sys

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from velch.vehicle import load_vehicle_case  # noqa: E402
from velch.vehicle_solver import VehicleDynamics, _seat  # noqa: E402

CASE = ROOT / "vehicles" / "turnouts" / "CN60-1100-1_18" / "cases" / "straight_one_set.json"
OUT = ROOT.parent / "scratch" / "s116"
K_Z_N_M = 5.0e7


def main() -> int:
    case = load_vehicle_case(CASE)
    dynamics = VehicleDynamics(case)
    q = np.asarray(case.initial_q, dtype=float)
    v = np.asarray(case.initial_v, dtype=float)
    v[dynamics.topology.require("wheelset1", "spin")] = 80.0 / 3.6 / 0.43
    q, residual = _seat(case, dynamics, q, v)
    _, contacts = dynamics.evaluate(0.0, q, v)

    names = list(dynamics.track.state_names)
    offset = int(dynamics.track.offset)
    print(f"seat residual {residual:.3e} N   track kind {dynamics.track.kind}   "
          f"track coords {len(names)}   offset {offset}")
    print()
    print(f"{'rail':16s} {'sink (um)':>11s} {'force (kN)':>11s} {'k from F/sink (N/m)':>20s} "
          f"{'F/k_z (um)':>11s}")

    rows = []
    for index, name in enumerate(names):
        if not name.endswith("_z_m"):
            continue
        rail_id = name[: -len("_z_m")]
        sink = float(q[offset + index])
        rail = next(item for item in case.rails if item.id == rail_id)
        merged = contacts.get(rail_id)
        force = float(merged.normal_force_n) if merged is not None else 0.0
        implied = force / sink if sink else float("nan")
        rows.append({"rail": rail_id, "sink_m": sink, "force_n": force,
                     "implied_stiffness_n_m": implied, "force_over_k_m": force / K_Z_N_M})
        print(f"{rail_id:16s} {sink * 1e6:11.4f} {force / 1e3:11.2f} {implied:20.4g} "
              f"{force / K_Z_N_M * 1e6:11.4f}")

    # Do the two bodies of the right rail sit on the same node?  Their contact drop must be identical,
    # because there is only one vertical coordinate for that rail.
    print()
    axes = sorted({row["rail"] for row in rows})
    print(f"rails with a vertical node: {axes}")
    body_rows = []
    body_contacts = dynamics.body_contacts
    for rail_id in axes:
        for body_id, response in zip(dynamics.body_ids[rail_id], body_contacts[rail_id]):
            if response.active and response.geometry is not None:
                body_rows.append((rail_id, body_id, float(response.normal_force_n)))
    print()
    print("per-body share on the same rail node (a shared sink cannot split them):")
    for rail_id, body_id, force in body_rows:
        print(f"  {rail_id:8s} {body_id:10s} {force / 1e3:10.2f} kN")

    total = sum(row["force_n"] for row in rows)
    print()
    print(f"total normal force on the rails {total / 1e3:.2f} kN")
    sink_span = max(row["sink_m"] for row in rows) - min(row["sink_m"] for row in rows)
    print(f"sink span across rails {sink_span * 1e6:.2f} um")
    print(f"monotone-with-load check: max|F/k_z - sink| = "
          f"{max(abs(row['force_over_k_m'] - row['sink_m']) for row in rows) * 1e6:.3f} um")
    print()
    print("VERDICT: " + ("the two bodies share one rail node, so their sink is common mode and cancels "
                         "from the gap -- round 253's explanation does not hold"
                         if abs(sink_span) < 1e-6 else
                         "rails sink differently, so sink can enter the gap"))
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "support_sink.json").write_text(json.dumps(
        {"seat_residual_n": residual, "track_kind": dynamics.track.kind,
         "k_z_n_m": K_Z_N_M, "rows": rows,
         "body_share": [{"rail": r, "body": b, "force_n": f} for r, b, f in body_rows],
         "sink_span_m": sink_span}, indent=1) + chr(10), encoding="utf-8")
    print(f"report -> {OUT / 'support_sink.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
