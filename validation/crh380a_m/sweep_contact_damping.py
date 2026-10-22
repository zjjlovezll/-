"""Sweep the contact damping of the compliant-fastener baseline.

The 571 Hz line in the full run is the rail's local mass bouncing on the contact spring.
Its damping ratio is c_eff / (2 sqrt(k m_rail)); with delta_half_velocity the effective
coefficient is c * sqrt(penetration) ~ 8 kN s/m, i.e. zeta ~ 1 %. This sweeps c upward and
measures whether the high bands fall without costing peak force or contact integrity.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from velch.vehicle import load_vehicle_case
from velch.vehicle_solver import save_vehicle_result, simulate_vehicle

BASE = Path(__file__).resolve().parent
SOURCE = BASE / "case_frog_strip_soft.json"
OUT = BASE / "out_damp_sweep"

LEVELS = (1.0e6, 1.0e7, 3.0e7, 6.0e7, 1.0e8)


def band_rms(time_s: np.ndarray, values: np.ndarray, lo: float, hi: float) -> float:
    n = values.size
    dt = float(time_s[1] - time_s[0])
    centred = values - values.mean()
    spectrum = np.fft.rfft(centred)
    freqs = np.fft.rfftfreq(n, dt)
    mask = (freqs >= lo) & (freqs < hi)
    power = np.sum(np.abs(spectrum[mask]) ** 2)
    return float(np.sqrt(2.0 * power / (n * n)))


def dominant(time_s: np.ndarray, values: np.ndarray) -> float:
    n = values.size
    dt = float(time_s[1] - time_s[0])
    spectrum = np.abs(np.fft.rfft(values - values.mean()))
    freqs = np.fft.rfftfreq(n, dt)
    return float(freqs[np.argmax(spectrum)])


def run(level: float) -> dict[str, float]:
    raw = json.loads(SOURCE.read_text(encoding="utf-8"))
    raw["case_id"] = f"damp_{level:.0e}"
    raw["contact"]["normal_damping_n_s_m_1p5"] = level
    path = BASE / f"case_damp_{level:.0e}.json"
    path.write_text(json.dumps(raw, indent=2, ensure_ascii=False), encoding="utf-8")
    case = load_vehicle_case(path)
    result = simulate_vehicle(case)
    out = OUT / f"damp_{level:.0e}"
    save_vehicle_result(case, result, out)

    with (out / "history.csv").open(encoding="utf-8") as handle:
        header = handle.readline().strip().split(",")
    data = np.loadtxt(out / "history.csv", delimiter=",", skiprows=1)
    columns = {name: index for index, name in enumerate(header)}
    time_s = data[:, columns["time_s"]]
    force = data[:, columns["axle1_right_normal_n"]]
    return {
        "c": level,
        "peak_kN": force.max() / 1e3,
        "min_kN": force.min() / 1e3,
        "lost": int(np.count_nonzero(force <= 0.0)),
        "rms_kN": float(np.sqrt(np.mean((force - force.mean()) ** 2)) / 1e3),
        "dom_Hz": dominant(time_s, force),
        "b30_60": band_rms(time_s, force, 30.0, 60.0) / 1e3,
        "b150_250": band_rms(time_s, force, 150.0, 250.0) / 1e3,
        "b250_400": band_rms(time_s, force, 250.0, 400.0) / 1e3,
    }


def main() -> int:
    print(f"{'c':>10}{'peak kN':>10}{'min kN':>9}{'lost':>6}{'rms kN':>9}"
          f"{'dom Hz':>9}{'30-60':>8}{'150-250':>9}{'250-400':>9}")
    rows = []
    for level in LEVELS:
        row = run(level)
        rows.append(row)
        print(f"{row['c']:>10.0e}{row['peak_kN']:>10.1f}{row['min_kN']:>9.2f}"
              f"{row['lost']:>6}{row['rms_kN']:>9.2f}{row['dom_Hz']:>9.1f}"
              f"{row['b30_60']:>8.2f}{row['b150_250']:>9.2f}{row['b250_400']:>9.2f}")
    (BASE / "damp_sweep.json").write_text(
        json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
