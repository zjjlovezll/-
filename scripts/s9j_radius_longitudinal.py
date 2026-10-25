"""How much longitudinal acceleration does a given out-of-roundness produce?

The axle-box longitudinal channel is the only acceleration channel that can see a change of
rolling radius: a polygon makes the wheel effectively smaller and larger as it turns, the
contact point moves along the tread, and the tangential creep force follows.  S9-8 showed the
channel lights up (71.4 rigid / 167.9 flexible per metre of depth) while a purely vertical
corrugation leaves it at 0.0 -- 1.5e-6 of the vertical channel.

What is still missing is the calibration: to invert a measured longitudinal spectrum into a
depth, the gain has to be a number with an uncertainty, and it has to be linear in depth.
This script sweeps the depth over an octave on both vehicles and prints, per run, the
longitudinal and vertical gains and their ratio.

Criteria fixed before the runs:

* the longitudinal gain must be proportional to depth within 10 % over 15-60 um, otherwise
  the contact nonlinearity is in play and a single constant is a lie;
* the ratio longitudinal/vertical must stay 2e-3..4e-3 (measured 0.25 % at 30 um), because
  both come from the same contact patch and a ratio that drifts by an order of magnitude
  would mean one of the two channels is not measuring what we think.

    python -X utf8 scripts/s9j_radius_longitudinal.py
"""

from __future__ import annotations

import json
import pathlib
import sys
import time

import numpy as np

REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

import s9f_shortwave as base  # noqa: E402  (path set above)

from velch.io.history import read_history  # noqa: E402
from velch.vehicle import load_vehicle_case  # noqa: E402
from velch.vehicle_solver import save_vehicle_result, simulate_vehicle  # noqa: E402

WORK = pathlib.Path(r"F:\velch_tmp\s9j")
VEHICLE = "CRH380A_M_axlebox_x"
ORDER = 10
DEPTHS_M = (15.0e-6, 30.0e-6, 60.0e-6)
SPEED_KMH = 350.0
OUTPUT_STEP_S = 5.0e-5
SOLVER_STEP_S = 1.0e-4
DURATION_S = 0.2
X_START_M = 100.0
RADIUS_M = 0.43
CHANNELS = ("axle1_box_left_x_acc_m_per_s2", "axle1_box_left_z_acc_m_per_s2")


def build(tmp: pathlib.Path, depth_m: float, label: str) -> pathlib.Path:
    doc = json.loads(base.BASE.read_text(encoding="utf-8"))
    base.absolute(doc, base.BASE.parent)
    doc.pop("initial_state", None)
    doc.pop("topology", None)
    doc.pop("vehicle", None)
    doc["vehicle_ref"] = VEHICLE
    doc["case_id"] = f"s9j_polygon_{label}"
    doc["run"].update({
        "method": "BDF", "jacobian": "analytic", "rtol": 1e-4, "atol": 1e-8,
        "x_start_m": X_START_M, "duration_s": DURATION_S,
        "output_step_s": OUTPUT_STEP_S, "max_solver_step_s": SOLVER_STEP_S,
        "longitudinal_force": True,
    })
    # pi/2 keeps the radius offset at zero when the clock starts; with 0 the static solve sees a
    # wheel that is small everywhere and falls into the symmetric hung branch.
    doc["wheel_polygon"] = {"order": ORDER, "depth_m": depth_m, "phase_rad": 0.5 * np.pi}
    doc.pop("irregularity", None)
    path = tmp / f"case_{label}.json"
    path.write_text(json.dumps(doc, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def main() -> int:
    WORK.mkdir(parents=True, exist_ok=True)
    report: dict[str, object] = {"order": ORDER, "depths_m": list(DEPTHS_M), "runs": {}}
    for depth in DEPTHS_M:
        label = f"{depth * 1e6:.0f}um"
        case = build(WORK, depth, label)
        loaded = load_vehicle_case(case)
        speed = loaded.vehicle.travel_speed_m_s
        passing = ORDER * speed / (2.0 * np.pi * RADIUS_M)
        print(f"{label}: {len(loaded.initial_q)} coordinates at {speed * 3.6:.0f} km/h, "
              f"passing {passing:.1f} Hz")
        started = time.perf_counter()
        result = simulate_vehicle(loaded)
        elapsed = time.perf_counter() - started
        out = WORK / f"out_{label}"
        out.mkdir(exist_ok=True)
        history_path, manifest = save_vehicle_result(loaded, result, out)
        status = json.loads(pathlib.Path(manifest).read_text(encoding="utf-8"))["summary"]["result_status"]
        print(f"  {elapsed:.1f} s -> {status}")
        history = read_history(pathlib.Path(history_path))
        names = list(history.ordering)
        time_s = np.asarray(history.data[names.index("time_s")], dtype=float)
        rate = 1.0 / float(np.mean(np.diff(time_s)))
        entry: dict[str, object] = {"seconds": elapsed, "status": status,
                                    "passing_hz": passing, "depth_m": depth, "channels": {}}
        for name in CHANNELS:
            if name not in names:
                continue
            values = np.asarray(history.data[names.index(name)], dtype=float)
            freqs, amplitude = base.spectrum(values, rate)
            centre = int(np.argmin(np.abs(freqs - passing)))
            peak = float(amplitude[centre])
            entry["channels"][name] = {"peak_at_polygon": peak, "gain_per_metre": peak / depth}
            print(f"  {name:32s} at {passing:.1f} Hz {peak:.3e}  gain {peak / depth:10.1f}")
        longitudinal = entry["channels"].get("axle1_box_left_x_acc_m_per_s2", {}).get("gain_per_metre")
        vertical = entry["channels"].get("axle1_box_left_z_acc_m_per_s2", {}).get("gain_per_metre")
        if longitudinal is not None and vertical:
            entry["ratio"] = longitudinal / vertical
            print(f"  longitudinal / vertical = {entry['ratio']:.5f}")
        report["runs"][label] = entry
    (WORK / "radius_longitudinal.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

    gains = [entry["channels"].get("axle1_box_left_x_acc_m_per_s2", {}).get("gain_per_metre")
             for entry in report["runs"].values()]
    gains = [g for g in gains if g]
    if len(gains) >= 2:
        spread = (max(gains) - min(gains)) / float(np.mean(gains))
        print(f"longitudinal gain across the octave: mean {np.mean(gains):.1f}, "
              f"spread {spread * 100:.1f} %")
        print("linear in depth" if spread < 0.10 else "NOT linear in depth over this range")
    print("wrote", WORK / "radius_longitudinal.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
