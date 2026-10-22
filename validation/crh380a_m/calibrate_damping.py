"""Calibrate contact damping against Simpack on the *same* station window.

Bands computed over different lengths or station ranges cannot be compared, so both
sides are cut to the same window (78.8..82.2 m of the leading axle) before the spectra
are taken. Then the damping coefficient is swept and the candidate whose band RMS sits
closest to Simpack's is reported.

Usage: python calibrate_damping.py [case.json] [channels...]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import h5py
import numpy as np

from velch.vehicle import load_vehicle_case
from velch.vehicle_solver import simulate_vehicle

BASE = Path(__file__).resolve().parent
MAT = Path(r"F:\ai道岔状态反演辨识\simpack-mcp-2021x\results"
           r"\case_a47bc7d9e48f40b08628147bfab5c3f4\model.output\350.mat")
GROUP = "timeInt/RS_result/SRS_S_R/SRS_S_WS_F/SRS_RWP_R"
LOW_M, HIGH_M = 78.8, 82.2
DT = 5.0e-4          # our output step; both series are interpolated onto this
BANDS = ((30.0, 60.0), (150.0, 250.0), (250.0, 400.0))


def simpack_window() -> tuple[np.ndarray, np.ndarray]:
    with h5py.File(MAT, "r") as handle:
        station = handle[f"{GROUP}/SRS_RWP_R_Pair/ch_008/values"][0]
        force = handle[f"{GROUP}/SRS_RWP_R_1/ch_010/values"][0]
        time = handle["timeInt/time/values"][0]
    station = np.asarray(station, dtype=float)
    keep = (station >= LOW_M) & (station <= HIGH_M)
    return np.asarray(time, dtype=float)[keep], np.asarray(force, dtype=float)[keep] / 1e3


def bands(time: np.ndarray, force: np.ndarray) -> dict[str, float]:
    step = float(np.median(np.diff(time)))
    grid = np.arange(time[0], time[-1], step)
    values = np.interp(grid, time, force)
    values = values - values.mean()
    spectrum = np.abs(np.fft.rfft(values)) * (2.0 / values.size)
    freq = np.fft.rfftfreq(values.size, step)
    out = {}
    for low, high in BANDS:
        mask = (freq >= low) & (freq < high)
        out[f"{low:g}-{high:g}"] = float(np.sqrt(np.sum(spectrum[mask] ** 2) / 2.0))
    peak = float(np.argmax(spectrum[1:]) + 1)
    out["dominant_Hz"] = float(freq[int(peak)])
    out["rms_kN"] = float(np.sqrt(np.mean(values ** 2)))
    return out


def our_window(source: Path, damping: float) -> dict:
    raw = json.loads(source.read_text(encoding="utf-8"))
    raw.setdefault("contact", {})["normal_damping_n_s_m_1p5"] = damping
    raw["case_id"] = f"damp_{damping:g}_{source.stem}"
    path = BASE / f"case_damp_{damping:g}.json"
    path.write_text(json.dumps(raw, indent=2, ensure_ascii=False), encoding="utf-8")
    case = load_vehicle_case(path)
    result = simulate_vehicle(case)
    time = np.asarray(result.times_s, dtype=float)
    force = np.array([entry["axle1_right"].normal_force_n for entry in result.contacts]) / 1e3
    station = (case.run.x_start_m + case.vehicle.axle_offsets_m[0]
               + case.vehicle.travel_speed_m_s * time)
    keep = (station >= LOW_M) & (station <= HIGH_M)
    row = bands(time[keep], force[keep])
    row["peak_kN"] = float(force.max())
    row["min_kN"] = float(force.min())
    row["lost"] = int(np.count_nonzero(force <= 0.0))
    return row


def main() -> int:
    source = Path(sys.argv[1]) if len(sys.argv) > 1 else BASE / "case_frog_N_strip05.json"
    values = [float(item) for item in sys.argv[2:]] or [2.0e4, 5.0e4, 1.0e5, 2.0e5]
    time, force = simpack_window()
    reference = bands(time, force)
    columns = ["rms_kN", "dominant_Hz", "30-60", "150-250", "250-400"]
    header = f"{'source':>18}" + "".join(f"{name:>12}" for name in columns) + f"{'peak':>9}{'lost':>6}"
    print(header)
    print(f"{'Simpack':>18}" + "".join(f"{reference[name]:>12.3f}" for name in columns)
          + "       -     -")
    rows = {"simpack": reference}
    for damping in values:
        row = our_window(source, damping)
        rows[f"{damping:g}"] = row
        print(f"{'damp '+format(damping, 'g'):>18}" + "".join(f"{row[name]:>12.3f}" for name in columns)
              + f"{row['peak_kN']:>9.1f}{row['lost']:>6}")
    (BASE / "damping_calibration.json").write_text(
        json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
