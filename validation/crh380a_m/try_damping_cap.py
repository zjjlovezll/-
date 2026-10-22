"""Cap the contact damping at a fraction of the elastic force.

Sweeping c alone forces a bad trade: c = 3e7 removes the 571 Hz ringing but turns the
switch panel's 0.17 mm step into 406 kN, because the damping term scales with approach
velocity and has no upper bound. Simpack's `fn.dref` transition does the same job without
that consequence. This caps the damping at a fraction of the elastic force and checks both
windows at once.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from velch.vehicle import load_vehicle_case
from velch.vehicle_solver import save_vehicle_result, simulate_vehicle

BASE = Path(__file__).resolve().parent
SOURCE = BASE / "case_frog_strip_soft.json"
OUT = BASE / "out_damp_cap"

WINDOWS = {"switch": 42.5, "frog": 69.0}
CAPS = (None, 0.5, 0.25)


def band_rms(time_s: np.ndarray, values: np.ndarray, lo: float, hi: float) -> float:
    n = values.size
    spectrum = np.fft.rfft(values - values.mean())
    freqs = np.fft.rfftfreq(n, float(time_s[1] - time_s[0]))
    mask = (freqs >= lo) & (freqs < hi)
    return float(np.sqrt(2.0 * np.sum(np.abs(spectrum[mask]) ** 2) / (n * n)))


def run(window: str, cap: float | None) -> dict[str, float]:
    raw = json.loads(SOURCE.read_text(encoding="utf-8"))
    tag = "none" if cap is None else f"{cap:g}".replace(".", "p")
    raw["case_id"] = f"{window}_cap{tag}"
    raw["contact"]["normal_damping_n_s_m_1p5"] = 3.0e7
    if cap is None:
        raw["contact"].pop("damping_force_cap_ratio", None)
    else:
        raw["contact"]["damping_force_cap_ratio"] = cap
    raw["run"]["x_start_m"] = WINDOWS[window]
    raw["run"]["duration_s"] = 0.05
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
        "window": window,
        "cap": cap,
        "peak_kN": force.max() / 1e3,
        "min_kN": force.min() / 1e3,
        "lost": int(np.count_nonzero(force <= 0.0)),
        "rms_kN": float(np.sqrt(np.mean((force - force.mean()) ** 2)) / 1e3),
        "dom_Hz": float(freqs[np.argmax(spectrum)]),
        "b250_400": band_rms(time_s, force, 250.0, 400.0) / 1e3,
    }


def main() -> int:
    print(f"{'window':>8}{'cap':>7}{'peak kN':>10}{'min kN':>9}{'lost':>6}"
          f"{'rms kN':>9}{'dom Hz':>9}{'250-400':>9}")
    rows = []
    for window in WINDOWS:
        for cap in CAPS:
            row = run(window, cap)
            rows.append(row)
            label = "off" if row["cap"] is None else f"{row['cap']:g}"
            print(f"{row['window']:>8}{label:>7}{row['peak_kN']:>10.1f}"
                  f"{row['min_kN']:>9.2f}{row['lost']:>6}{row['rms_kN']:>9.2f}"
                  f"{row['dom_Hz']:>9.1f}{row['b250_400']:>9.2f}")
    (BASE / "damp_cap.json").write_text(
        json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
