"""Round 35: does _place_on_alignment's roll reach the seat's initial state?"""

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, r"F:\ai道岔状态反演辨识\Velch\src")

import velch.vehicle_solver as vs
from velch.vehicle import load_vehicle_case

BASE = Path(r"F:\velch_tmp\curve_frames\case_r1100_geometry.json")
WORK = Path(r"F:\velch_tmp\curve35")


def build(cant: float) -> Path:
    raw = json.loads(BASE.read_text(encoding="utf-8"))
    raw["case_id"] = f"probe_cant_{cant}"
    raw["run"].update({"curve_radius_m": 1100.0, "curve_cant_m": cant, "curve_geometry": True,
                       "align_to_track": True, "x_start_m": 60.0, "duration_s": 0.01,
                       "output_step_s": 0.005})
    raw.setdefault("vehicle", {})["travel_speed_m_s"] = 100.0 / 3.6
    raw.pop("initial_state", None)
    WORK.mkdir(parents=True, exist_ok=True)
    path = WORK / f"case_cant_{cant}.json"
    path.write_text(json.dumps(raw, indent=1), encoding="utf-8")
    return path


def main() -> int:
    case = load_vehicle_case(build(0.107))
    dynamics = vs.VehicleDynamics(case)
    topology = dynamics.topology
    q0 = np.zeros(dynamics.dimension)

    placed = vs._place_on_alignment(case, dynamics, q0)
    print("bodies with a roll coordinate and the placed value:")
    for body in topology.bodies:
        parts = []
        for axis in ("y", "roll", "yaw"):
            if axis in body.dof:
                parts.append(f"{axis}={placed[topology.require(body.id, axis)]:+.6f}")
        print(f"  {body.id:14s} " + "  ".join(parts))

    print("\nplace_on_alignment moved", int(np.count_nonzero(placed)), "entries")

    # Does simulate_vehicle actually use that placement before the seat?
    source = Path(vs.__file__).read_text(encoding="utf-8")
    for name in ("_place_on_alignment(", "_static_vertical_equilibrium("):
        lines = [f"{index + 1}: {line.strip()}"
                 for index, line in enumerate(source.splitlines()) if name in line]
        print(f"\ncalls to {name}")
        for line in lines:
            print("  " + line[:120])

    # What does the seat start from?
    original = vs._static_vertical_equilibrium
    seen = {}

    def spy(case_, dynamics_, q_, v_):  # noqa: ANN001
        seen["q"] = np.array(q_, dtype=float)
        return original(case_, dynamics_, q_, v_)

    vs._static_vertical_equilibrium = spy
    try:
        result = vs.simulate_vehicle(case)
        summary = getattr(result, "summary", None) or {}
        print("\nstatus:", summary.get("result_status"))
    except Exception as error:  # noqa: BLE001
        print(f"\nseat/run raised {type(error).__name__}: {str(error)[:120]}")
    finally:
        vs._static_vertical_equilibrium = original

    seat_start = seen.get("q")
    if seat_start is None:
        print("the seat was never called through the module name")
        return 0
    print("seat start: nonzero entries", int(np.count_nonzero(seat_start)),
          "| same as placed:", bool(np.allclose(seat_start, placed)))
    for body in topology.bodies:
        if "roll" in body.dof:
            index = topology.require(body.id, "roll")
            print(f"  seat-start roll {body.id:14s} = {seat_start[index]:+.6f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
