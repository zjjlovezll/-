"""S1-g: add the slab under the sleeper and see whether the low band fills in.

The single-layer stack (sleeper 79 kg on 12e6 N/m ballast) leaves 30-60 Hz at 5.68 kN rms
against Simpack's 14.84. A slab adds a second, slower body (300 kg on 50e6 N/m subgrade),
which puts another mode below 60 Hz. This runs the frog window on the current baseline
(strip integral, compliant fastener, c = 3e7 capped at 50 %) with and without the slab.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from velch.vehicle import load_vehicle_case
from velch.vehicle_solver import save_vehicle_result, simulate_vehicle

BASE = Path(__file__).resolve().parent
SOURCE = BASE / "case_full12_cap05.json"
OUT = BASE / "out_slab"

SLEEPER = {
    "mass_y_kg": 79.0,
    "mass_z_kg": 79.0,
    "k_y_n_m": 60.0e6,
    "c_y_n_s_m": 100.0e3,
    "k_z_n_m": 120.0e6,
    "c_z_n_s_m": 200.0e3,
}
SLAB = {
    "mass_y_kg": 300.0,
    "mass_z_kg": 300.0,
    "k_y_n_m": 25.0e6,
    "c_y_n_s_m": 200.0e3,
    "k_z_n_m": 50.0e6,
    "c_z_n_s_m": 400.0e3,
}


def band_rms(time_s: np.ndarray, values: np.ndarray, lo: float, hi: float) -> float:
    n = values.size
    spectrum = np.fft.rfft(values - values.mean())
    freqs = np.fft.rfftfreq(n, float(time_s[1] - time_s[0]))
    mask = (freqs >= lo) & (freqs < hi)
    return float(np.sqrt(2.0 * np.sum(np.abs(spectrum[mask]) ** 2) / (n * n)))


def run(layers: list[dict], tag: str) -> dict[str, float]:
    raw = json.loads(SOURCE.read_text(encoding="utf-8"))
    raw["case_id"] = f"slab_{tag}"
    raw["track_dynamics"] = {"kind": "layered", "layers": layers}
    raw["run"]["x_start_m"] = 69.0
    raw["run"]["duration_s"] = 0.05
    rails = (len(raw["initial_state"]["q"]) - 35) // 2
    dof = 35 + 2 * (1 + len(layers)) * rails
    raw["initial_state"]["q"] = (list(raw["initial_state"]["q"]) + [0.0] * dof)[:dof]
    if "v" in raw["initial_state"]:
        raw["initial_state"]["v"] = (list(raw["initial_state"]["v"]) + [0.0] * dof)[:dof]
    path = BASE / f"case_{raw['case_id']}.json"
    path.write_text(json.dumps(raw, indent=2, ensure_ascii=False), encoding="utf-8")

    case = load_vehicle_case(path)
    result = simulate_vehicle(case)
    out = OUT / raw["case_id"]
    save_vehicle_result(case, result, out)
    with (out / "history.csv").open(encoding="utf-8") as handle:
        header = handle.readline().strip().split(",")
    data = np.loadtxt(out / "history.csv", delimiter=",", skiprows=1)
    column = {name: index for index, name in enumerate(header)}
    time_s = data[:, column["time_s"]]
    force = data[:, column["axle1_right_normal_n"]]
    freqs = np.fft.rfftfreq(force.size, float(time_s[1] - time_s[0]))
    spectrum = np.abs(np.fft.rfft(force - force.mean()))
    return {
        "tag": tag,
        "dof": dof,
        "peak_kN": force.max() / 1e3,
        "min_kN": force.min() / 1e3,
        "lost": int(np.count_nonzero(force <= 0.0)),
        "rms_kN": float(np.sqrt(np.mean((force - force.mean()) ** 2)) / 1e3),
        "dom_Hz": float(freqs[np.argmax(spectrum)]),
        "b30_60": band_rms(time_s, force, 30.0, 60.0) / 1e3,
        "b150_250": band_rms(time_s, force, 150.0, 250.0) / 1e3,
        "b250_400": band_rms(time_s, force, 250.0, 400.0) / 1e3,
    }


def main() -> int:
    print(f"{'variant':>14}{'dof':>5}{'peak':>8}{'min':>8}{'lost':>6}{'rms':>8}"
          f"{'dom Hz':>9}{'30-60':>8}{'150-250':>9}{'250-400':>9}")
    rows = []
    for layers, tag in (( [SLEEPER], "one_layer"), ([SLEEPER, SLAB], "two_layer")):
        row = run(layers, tag)
        rows.append(row)
        print(f"{row['tag']:>14}{row['dof']:>5}{row['peak_kN']:>8.1f}{row['min_kN']:>8.2f}"
              f"{row['lost']:>6}{row['rms_kN']:>8.2f}{row['dom_Hz']:>9.1f}"
              f"{row['b30_60']:>8.2f}{row['b150_250']:>9.2f}{row['b250_400']:>9.2f}")
    (BASE / "slab_compare.json").write_text(
        json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
