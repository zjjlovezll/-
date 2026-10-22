"""Does the sleeper/ballast layer supply the missing 30-60 Hz content?

Simpack's right-rail force carries 14.84 kN rms in 30-60 Hz where the single-degree
rail-on-fastener model gives only ~7. The SDITT layered track (sleeper 79 kg on 12e6 N/m
ballast under a 25e6 N/m pad) puts that band at sqrt(k_series/m_total)/2pi ~ 32 Hz, right
inside it. This runs the frog window with one extra layer added.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from velch.vehicle import load_vehicle_case
from velch.vehicle_solver import save_vehicle_result, simulate_vehicle

BASE = Path(__file__).resolve().parent
SOURCE = BASE / "case_frog_strip_soft.json"
OUT = BASE / "out_layered_frog"

LAYERS = {
    "two_layer": [
        {
            "mass_y_kg": 79.0,
            "mass_z_kg": 79.0,
            "k_y_n_m": 10.0e6,
            "c_y_n_s_m": 60.0e3,
            "k_z_n_m": 12.0e6,
            "c_z_n_s_m": 120.0e3,
        }
    ],
}


def band_rms(time_s: np.ndarray, values: np.ndarray, lo: float, hi: float) -> float:
    n = values.size
    spectrum = np.fft.rfft(values - values.mean())
    freqs = np.fft.rfftfreq(n, float(time_s[1] - time_s[0]))
    mask = (freqs >= lo) & (freqs < hi)
    return float(np.sqrt(2.0 * np.sum(np.abs(spectrum[mask]) ** 2) / (n * n)))


def run(kind: str, damping: float) -> dict[str, float]:
    raw = json.loads(SOURCE.read_text(encoding="utf-8"))
    raw["case_id"] = f"frog_{kind}_d{damping:.0e}"
    raw["contact"]["normal_damping_n_s_m_1p5"] = damping
    if kind in LAYERS:
        raw["track_dynamics"] = {"kind": "layered", "layers": LAYERS[kind]}
        dof = 35 + 2 * (1 + len(LAYERS[kind])) * len(raw["rail_templates"])
    else:
        raw["track_dynamics"] = {"kind": "local_compliant"}
        dof = 35 + 2 * len(raw["rail_templates"])
    q = list(raw["initial_state"]["q"])
    q = (q + [0.0] * dof)[:dof]
    raw["initial_state"]["q"] = q
    if "v" in raw["initial_state"]:
        velocity = list(raw["initial_state"]["v"])
        raw["initial_state"]["v"] = (velocity + [0.0] * dof)[:dof]
    path = BASE / f"case_{raw['case_id']}.json"
    path.write_text(json.dumps(raw, indent=2, ensure_ascii=False), encoding="utf-8")

    case = load_vehicle_case(path)
    result = simulate_vehicle(case)
    out = OUT / raw["case_id"]
    save_vehicle_result(case, result, out)
    with (out / "history.csv").open(encoding="utf-8") as handle:
        header = handle.readline().strip().split(",")
    data = np.loadtxt(out / "history.csv", delimiter=",", skiprows=1)
    columns = {name: index for index, name in enumerate(header)}
    time_s = data[:, columns["time_s"]]
    force = data[:, columns["axle1_right_normal_n"]]
    freqs = np.fft.rfftfreq(force.size, float(time_s[1] - time_s[0]))
    spectrum = np.abs(np.fft.rfft(force - force.mean()))
    return {
        "kind": kind,
        "damping": damping,
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
    print(f"{'variant':>26}{'peak':>9}{'min':>8}{'lost':>6}{'rms':>8}"
          f"{'dom Hz':>9}{'30-60':>8}{'150-250':>9}{'250-400':>9}")
    rows = []
    for kind, damping in (
        ("local_compliant", 3.0e7),
        ("two_layer", 3.0e7),
        ("two_layer", 1.0e7),
    ):
        row = run(kind, damping)
        rows.append(row)
        print(f"{row['kind'] + ' c=' + format(row['damping'], '.0e'):>26}"
              f"{row['peak_kN']:>9.1f}{row['min_kN']:>8.2f}{row['lost']:>6}"
              f"{row['rms_kN']:>8.2f}{row['dom_Hz']:>9.1f}"
              f"{row['b30_60']:>8.2f}{row['b150_250']:>9.2f}{row['b250_400']:>9.2f}")
    (BASE / "layered_frog.json").write_text(
        json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
