"""S4, second attempt: coherent averaging over phase realisations.

A single run cannot separate the sinusoid from the crossing transient — measured last round, the
"no excitation" run had *larger* peaks than the excited one at 2 m and 8 m.  Coherent averaging
fixes exactly that: every realisation carries the same four components with a common phase offset,
so multiplying the response coefficient by exp(-i*phi) aligns them and they add linearly while the
incoherent transient grows as sqrt(R).  The report therefore prints both the coherent gain and the
per-realisation scatter, so the confidence is visible instead of assumed.
"""

import csv
import json
import shutil
import subprocess
import sys
from pathlib import Path

VELCH = Path(r"F:\ai道岔状态反演辨识\Velch")
DATA = Path(r"F:\velch_data\validation\crh380a_m")
WORK = Path(r"F:\velch_tmp\s4")
sys.path.insert(0, str(VELCH / "src"))

import numpy as np  # noqa: E402

from velch.case.derive import absolutise_profile_paths  # noqa: E402
from velch.irregularity import IrregularityTrack, write_tre  # noqa: E402

BASE = DATA / "case_long_axlebox.json"
WAVELENGTHS = (0.1, 0.5, 2.0, 8.0)
AMPLITUDE_M = 0.3e-3
SPEED = 97.2222
REALISATIONS = 6
WINDOW_S = (0.40, 0.80)


def build_profile(length_m: float, step_m: float, phase: float) -> IrregularityTrack:
    s_m = np.arange(int(round(length_m / step_m)) + 1, dtype=float) * step_m
    vertical = np.zeros_like(s_m)
    for wavelength in WAVELENGTHS:
        vertical += AMPLITUDE_M * np.sin(2.0 * np.pi * s_m / wavelength + phase)
    zeros = np.zeros_like(s_m)
    return IrregularityTrack(s_m=s_m, lateral_m=zeros, vertical_m=vertical,
                             roll_rad=zeros, gauge_m=zeros, source="s4-multisine")


def run_case(name: str, case: dict) -> Path:
    WORK.mkdir(parents=True, exist_ok=True)
    case_path = WORK / f"{name}.json"
    out = WORK / f"out_{name}"
    if out.exists():
        shutil.rmtree(out)
    payload = json.loads(json.dumps(case))
    absolutise_profile_paths(payload, DATA)
    case_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    done = subprocess.run(
        [sys.executable, "-X", "utf8", "-m", "velch", "run-vehicle", str(case_path),
         "--output", str(out), "--fast"],
        cwd=VELCH, capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    if done.returncode != 0:
        print("run failed:", done.stderr[-300:])
    return out


def coefficient(out: Path, frequency_hz: float, window: tuple[float, float]) -> complex:
    with (out / "history.csv").open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    times = np.array([float(row["time_s"]) for row in rows])
    values = np.array([float(row["axle1_box_left_z_acc_m_per_s2"]) for row in rows])
    mask = (times >= window[0]) & (times <= window[1])
    times, values = times[mask], values[mask]
    values = values - values.mean()
    # Least-squares fit of A*cos + B*sin at the exact frequency: exact for a known frequency, and it
    # does not care about the record length being an integer number of periods.
    design = np.column_stack([np.cos(2 * np.pi * frequency_hz * times),
                              np.sin(2 * np.pi * frequency_hz * times)])
    a, b = np.linalg.lstsq(design, values, rcond=None)[0]
    return complex(b, a)


def main() -> int:
    base = json.loads(BASE.read_text(encoding="utf-8"))
    run_length = float(base["run"]["duration_s"]) * SPEED
    steps = {0.005, 0.01, 0.02}
    tracks = {}
    rng = np.random.default_rng(20261024)
    phases = rng.uniform(0.0, 2.0 * np.pi, size=REALISATIONS)
    for index, phase in enumerate(phases):
        step = 0.005  # 0.1 m needs 0.05 m; 0.005 m keeps the 0.1 m component honest
        track = build_profile(run_length + 30.0, step, phase)
        tre = WORK / f"s4_r{index}.tre"
        WORK.mkdir(parents=True, exist_ok=True)
        write_tre(tre, track, comment=f"S4 phase {phase:.4f}")
        tracks[index] = tre

    case = json.loads(BASE.read_text(encoding="utf-8"))
    case.pop("initial_state", None)

    gathered: dict[float, list[complex]] = {wavelength: [] for wavelength in WAVELENGTHS}
    magnitudes: dict[float, list[float]] = {wavelength: [] for wavelength in WAVELENGTHS}
    for index, phase in enumerate(phases):
        payload = json.loads(json.dumps(case))
        payload["case_id"] = f"s4_r{index}"
        payload["irregularity"] = {"tre": str(tracks[index]), "start_m": 0.0, "end_m": 1.0e6,
                                   "fade_m": 10.0, "scale": 1.0, "channels": ["vertical"]}
        out = run_case(f"s4_r{index}", payload)
        for wavelength in WAVELENGTHS:
            frequency = SPEED / wavelength
            value = coefficient(out, frequency, WINDOW_S)
            gathered[wavelength].append(value * np.exp(-1j * phase))
            magnitudes[wavelength].append(abs(value))
        print(f"realisation {index}: done")

    print(f"\nwindow {WINDOW_S[0]}–{WINDOW_S[1]} s, amplitude {AMPLITUDE_M * 1000:.2f} mm, "
          f"{REALISATIONS} realisations")
    print(f"{'wavelength':>10} {'freq Hz':>8} {'coherent':>10} {'per-run mean':>13} "
          f"{'scatter':>8} {'SNR':>6} {'gain 1/s^2 per m':>17}")
    for wavelength in WAVELENGTHS:
        values = np.array(gathered[wavelength])
        coherent = abs(values.mean())
        per_run = float(np.mean(magnitudes[wavelength]))
        scatter = float(np.std(magnitudes[wavelength]))
        noise = scatter / np.sqrt(REALISATIONS)
        print(f"{wavelength:10.3f} {SPEED / wavelength:8.1f} {coherent:10.4f} {per_run:13.4f} "
              f"{scatter:8.4f} {coherent / noise if noise else float('inf'):6.1f} "
              f"{coherent / AMPLITUDE_M:17.1f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
