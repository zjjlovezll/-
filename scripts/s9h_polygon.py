"""S9h: a wheel polygon at 350 km/h — the rolling-radius excitation, and whether 345/378 Hz appears.

Order 10 at 350 km/h sits at 10 * 97.22 / (2*pi*0.43) = 359.9 Hz, i.e. inside the band the thesis
reports as the flexible-wheelset signature.  Two variants: rigid wheelset (longitudinal channel
answer) and the FE mode set (does the elastic band appear at its own frequency).
"""

from __future__ import annotations

import json
import pathlib
import sys
import time

import numpy as np

REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))

import s9f_shortwave as base

from velch.io.history import read_history
from velch.vehicle import load_vehicle_case
from velch.vehicle_solver import save_vehicle_result, simulate_vehicle

WORK = pathlib.Path(r"F:\velch_tmp\s9h")
VEHICLE = "CRH380A_M_axlebox_x"
ORDER = 10
DEPTH_M = 30.0e-6
OUTPUT_STEP_S = 5.0e-5
SOLVER_STEP_S = 1.0e-4
DURATION_S = 0.3
X_START_M = 100.0            # the straight case covers 0..150 m; the front axle sits +10 m ahead
RADIUS_M = 0.43
CHANNELS = (
    "axle1_box_left_x_acc_m_per_s2",
    "axle1_box_left_z_acc_m_per_s2",
    "axle1_box_left_y_acc_m_per_s2",
)


def build(tmp: pathlib.Path, flexible: bool, speed_m_s: float) -> pathlib.Path:
    doc = json.loads(base.BASE.read_text(encoding="utf-8"))
    base.absolute(doc, base.BASE.parent)
    doc.pop("initial_state", None)
    doc.pop("topology", None)
    doc.pop("vehicle", None)
    doc["vehicle_ref"] = VEHICLE
    doc["case_id"] = f"s9h_polygon{ORDER}_{'flex' if flexible else 'rigid'}"
    doc["run"].update({
        "method": "BDF", "jacobian": "analytic", "rtol": 1e-4, "atol": 1e-8,
        "x_start_m": X_START_M, "duration_s": DURATION_S,
        "output_step_s": OUTPUT_STEP_S, "max_solver_step_s": SOLVER_STEP_S,
        # The whole point of the x layout here: let the longitudinal tangential force reach the
        # state, so the axle-box x channel can see the rolling radius change.
        "longitudinal_force": True,
    })
    # Phase pi/2 puts the polygon at zero radius offset when the clock starts.  With phase 0 the
    # static equilibrium is solved against a wheel that is 30 um small everywhere, and it falls
    # into the symmetric hung branch (0 N against 120 kN) before the integrator ever runs.
    doc["wheel_polygon"] = {"order": ORDER, "depth_m": DEPTH_M, "phase_rad": 0.5 * np.pi}
    doc.pop("irregularity", None)          # a smooth track: the only excitation is the polygon
    if flexible:
        doc["flexible_wheelset"] = {
            "source": "file",
            "file": str(REPO / "vehicles" / "modes" / "CRH3C_wheelset_fe.json"),
            "axles": [1, 2, 3, 4],
        }
    path = tmp / f"case_{'flex' if flexible else 'rigid'}.json"
    path.write_text(json.dumps(doc, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def main() -> int:
    WORK.mkdir(parents=True, exist_ok=True)
    report = {"order": ORDER, "depth_m": DEPTH_M, "runs": {}}
    for flexible in (False, True):
        label = "flexible" if flexible else "rigid"
        case = build(WORK, flexible, 97.2222)
        loaded = load_vehicle_case(case)
        speed = loaded.vehicle.travel_speed_m_s
        passing = ORDER * speed / (2.0 * np.pi * RADIUS_M)
        print(f"{label}: {len(loaded.initial_q)} coordinates at {speed * 3.6:.0f} km/h, "
              f"polygon order {ORDER} -> {passing:.1f} Hz")
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
        entry = {"coordinates": len(loaded.initial_q), "seconds": elapsed, "status": status,
                 "passing_hz": passing, "channels": {}}
        for name in CHANNELS:
            if name not in names:
                continue
            values = np.asarray(history.data[names.index(name)], dtype=float)
            freqs, amplitude = base.spectrum(values, rate)
            centre = int(np.argmin(np.abs(freqs - passing)))
            peak = float(amplitude[centre])
            entry["channels"][name] = {"rms": float(np.sqrt(np.mean(values ** 2))),
                                       "peak_at_polygon": peak,
                                       "gain_per_metre": peak / DEPTH_M}
            print(f"  {name:32s} rms {np.sqrt(np.mean(values ** 2)):.3e}  "
                  f"at {passing:.1f} Hz {peak:.3e}  gain {peak / DEPTH_M:10.1f}")
        report["runs"][label] = entry
        # the 300-400 Hz band, which is where the thesis puts the elastic signature
        zname = "axle1_box_left_z_acc_m_per_s2"
        if zname in names:
            values = np.asarray(history.data[names.index(zname)], dtype=float)
            freqs, amplitude = base.spectrum(values, rate)
            band = (freqs >= 300.0) & (freqs <= 400.0)
            entry["band_300_400_rms"] = float(np.sqrt(np.sum(amplitude[band] ** 2) / 2.0))
            top = np.argsort(amplitude[1:])[-6:][::-1] + 1
            entry["top_lines"] = [[float(freqs[j]), float(amplitude[j])] for j in top]
            print(f"  300-400 Hz rms {entry['band_300_400_rms']:.3e}  "
                  f"top lines {[round(freqs[j], 1) for j in top]}")
    (WORK / "polygon.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("wrote", WORK / "polygon.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
