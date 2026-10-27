"""Round 34b: does a balanced cant finally seat and share the load evenly?"""

import json
import sys
from pathlib import Path

sys.path.insert(0, r"F:\ai道岔状态反演辨识\Velch\src")

from velch.vehicle import load_vehicle_case
from velch.vehicle_solver import simulate_vehicle

BASE = Path(r"F:\velch_tmp\curve_frames\case_r1100_geometry.json")  # R = 1100 m, geometry route
WORK = Path(r"F:\velch_tmp\curve34")

CASES = (
    ("R1100_cantM107_100", 1100.0, -0.107, 100.0),
    ("R1100_cantM107_80", 1100.0, -0.107, 80.0),
    ("R1100_cant0_100", 1100.0, 0.0, 100.0),
    ("R350_cantM100_80", 350.0, -0.100, 80.0),
)


def build(name: str, radius: float, cant: float, speed_kmh: float) -> Path:
    raw = json.loads(BASE.read_text(encoding="utf-8"))
    raw["case_id"] = f"probe_{name}"
    raw["run"].update({
        "curve_radius_m": radius,
        "curve_cant_m": cant,
        "curve_geometry": True,
        "align_to_track": True,
        "x_start_m": 60.0,
        "duration_s": 0.01,
        "output_step_s": 0.005,
    })
    raw.setdefault("vehicle", {})["travel_speed_m_s"] = speed_kmh / 3.6
    raw.pop("initial_state", None)
    WORK.mkdir(parents=True, exist_ok=True)
    path = WORK / f"case_{name}.json"
    path.write_text(json.dumps(raw, indent=1), encoding="utf-8")
    return path


def main() -> int:
    for name, radius, cant, speed in CASES:
        path = build(name, radius, cant, speed)
        theoretical = 1.5 * (speed / 3.6) ** 2 / (9.81 * radius)
        print(f"\n=== {name}: R={radius} cant={cant} v={speed} (h_th {theoretical:.3f} m)")
        try:
            result = simulate_vehicle(load_vehicle_case(path))
        except Exception as error:  # noqa: BLE001
            print(f"    -> {type(error).__name__}: {str(error)[:150]}")
            continue
        summary = getattr(result, "summary", None) or {}
        gates = summary.get("gates", {})
        failing = [key for key, value in gates.items() if not value]
        print(f"    -> {summary.get('result_status')}, gates "
              f"{len(gates) - len(failing)}/{len(gates)}, failing {failing}")
        peaks = summary.get("peak_normal_force_n", {})
        if peaks:
            shares = sorted(value / 59.66e3 for value in peaks.values())
            print(f"    shares {shares[0]:.3f}..{shares[-1]:.3f}  kN "
                  f"{ {k.split(':')[-1]: round(v / 1000, 1) for k, v in peaks.items()} }")
        print(f"    max penetration {summary.get('max_penetration_m', 0.0) * 1e6:.1f} um")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
