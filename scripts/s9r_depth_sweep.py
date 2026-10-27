"""Vertical short-wave law: is the recovered depth linear in the true depth?

The single-point result (+9.7 % at 30 um, 80 km/h) cannot rule out a
depth-dependent bias.  This sweeps three depths at one wavelength, measures the
axle-box vertical line at the passing frequency, and divides by the constant
gain ``(2 pi f_n)^2`` the same way ``s9f_shortwave.py`` does.

Run:  python -X utf8 scripts/s9r_depth_sweep.py
"""

from __future__ import annotations

import json
import math
import pathlib
import sys
import time

import numpy as np

REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))

import s9k_random_spectrum as s9k  # noqa: E402
from velch.io.history import read_history  # noqa: E402
from velch.irregularity import IrregularityTrack  # noqa: E402
from velch.vehicle import load_vehicle_case  # noqa: E402
from velch.vehicle_solver import save_vehicle_result, simulate_vehicle  # noqa: E402

WORK = pathlib.Path(r"F:\velch_tmp\s9r")
SPEED_KMH = 80.0
WAVELENGTH_M = 0.050
DEPTHS_UM = (10.0, 30.0, 60.0)
OUTPUT_STEP_S = 5.0e-5
SOLVER_STEP_S = 1.0e-4
DURATION_S = 1.0
X_START_M = 20.0
TRE_STEP_M = 0.0025
TRE_LENGTH_M = 80.0
CHANNEL = "axle1_box_left_z_acc_m_per_s2"
PRIMARY_STIFFNESS_N_M = 1.176e6
BOX_MASS_KG = 48.2
# omega_n^2 = k / m; the law is a_box ~ omega_n^2 * A, and (2 pi f_n)^2 is omega_n^2,
# so this is k / m -- not 4 pi^2 k / m, which was the first (wrong) version.
CONSTANT = PRIMARY_STIFFNESS_N_M / BOX_MASS_KG


def tone(depth_m: float) -> IrregularityTrack:
    step = TRE_STEP_M
    count = int(TRE_LENGTH_M / step) + 1
    s = np.arange(count) * step
    vertical = depth_m * np.sin(2.0 * math.pi * s / WAVELENGTH_M)
    zeros = np.zeros_like(vertical)
    return IrregularityTrack(s_m=s, lateral_m=zeros, vertical_m=vertical,
                             roll_rad=zeros, gauge_m=zeros,
                             source=f"generated 50 mm tone, depth {depth_m * 1e6:.0f} um")


def measure(depth_m: float) -> dict[str, float]:
    label = f"d{depth_m * 1e6:04.0f}"
    tre = s9k.write_track(tone(depth_m), label)
    case = s9k.build_case(tre, label)
    doc = json.loads(case.read_text(encoding="utf-8"))
    doc["run"]["duration_s"] = DURATION_S
    doc["run"]["output_step_s"] = OUTPUT_STEP_S
    doc["run"]["max_solver_step_s"] = SOLVER_STEP_S
    doc["run"]["x_start_m"] = X_START_M
    case.write_text(json.dumps(doc, indent=2, ensure_ascii=False), encoding="utf-8")
    loaded = load_vehicle_case(case)
    started = time.perf_counter()
    result = simulate_vehicle(loaded)
    seconds = time.perf_counter() - started
    out = WORK / f"out_{label}"
    out.mkdir(parents=True, exist_ok=True)
    history_path, manifest = save_vehicle_result(loaded, result, out)
    status = json.loads(pathlib.Path(manifest).read_text(encoding="utf-8"))["summary"]["result_status"]
    history = read_history(pathlib.Path(history_path))
    names = list(history.ordering)
    values = np.asarray(history.data[names.index(CHANNEL)], dtype=float)
    times = np.asarray(history.data[names.index("time_s")], dtype=float)
    rate = 1.0 / float(np.mean(np.diff(times)))
    keep = times >= 0.4 * times[-1]
    values = values[keep] - float(np.mean(values[keep]))
    window = np.hanning(values.size)
    spectrum = np.fft.rfft(values * window)
    amplitude = 2.0 * np.abs(spectrum) / float(np.sum(window))
    frequencies = np.fft.rfftfreq(values.size, 1.0 / rate)
    target = (SPEED_KMH / 3.6) / WAVELENGTH_M
    index = int(np.argmin(np.abs(frequencies - target)))
    peak = float(amplitude[index])
    print(f"depth {depth_m * 1e6:5.1f} um: {seconds:5.0f} s -> {status}, "
          f"line {frequencies[index]:7.1f} Hz = {peak:.4f} m/s2", flush=True)
    return {"depth_um": depth_m * 1e6, "frequency_hz": float(frequencies[index]),
            "amplitude": peak, "recovered_um": peak / CONSTANT * 1e6,
            "seconds": seconds, "status": status}


def main() -> int:
    WORK.mkdir(parents=True, exist_ok=True)
    print(f"constant (2 pi f_n)^2 = {CONSTANT:.1f} (m/s^2)/m, target {SPEED_KMH / 3.6 / WAVELENGTH_M:.1f} Hz")
    rows = [measure(depth / 1e6) for depth in DEPTHS_UM]
    print(f"\n{'depth um':>9} {'recovered um':>13} {'ratio':>7} {'error':>8}")
    for row in rows:
        ratio = row["recovered_um"] / row["depth_um"]
        print(f"{row['depth_um']:9.1f} {row['recovered_um']:13.2f} {ratio:7.3f} "
              f"{(ratio - 1.0) * 100.0:7.1f}%")
    (WORK / "depth_sweep.json").write_text(json.dumps({"constant": CONSTANT, "rows": rows}, indent=2,
                                                      ensure_ascii=False), encoding="utf-8")
    print("wrote", WORK / "depth_sweep.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
