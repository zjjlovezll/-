"""S5f: measure the 2x2 matrix with BOTH bands excited at once (multi-tone BLMA).

Single-tone BLMA measured H's diagonal only and had to assume the off-diagonal entries were zero;
the 2.0 m band then came back 23 % low.  Here both bands are driven simultaneously with independent
random phases, so each realisation gives two equations and the full complex 2x2 -- coupling
included -- falls out of six realisations.
"""

import csv
import json
import shutil
import subprocess
import sys
from pathlib import Path

VELCH = Path(r"F:\ai道岔状态反演辨识\Velch")
DATA = Path(r"F:\velch_data\validation\crh380a_m")
WORK = Path(r"F:\velch_tmp\s5f")
sys.path.insert(0, str(VELCH / "src"))

import numpy as np  # noqa: E402

from velch.case.derive import absolutise_profile_paths  # noqa: E402
from velch.irregularity import IrregularityTrack, write_tre  # noqa: E402

BASE = Path(r"F:\velch_tmp\straight\case_straight_axlebox.json")
BANDS = (0.1, 2.0)
SPEED = 97.2222
STEP_M = 0.005
AMPLITUDE_M = 0.10e-3
REALISATIONS = 6
SHAPE = np.array([0.83, 1.03])
LAMBDA = 1e-2


def run(name: str, amplitudes: np.ndarray, phases: np.ndarray, base: dict,
        length_m: float) -> Path | None:
    WORK.mkdir(parents=True, exist_ok=True)
    s_m = np.arange(int(round(length_m / STEP_M)) + 1, dtype=float) * STEP_M
    vertical = np.zeros_like(s_m)
    for band, amplitude, phase in zip(BANDS, amplitudes, phases):
        vertical += amplitude * np.sin(2.0 * np.pi * s_m / band + phase)
    zeros = np.zeros_like(s_m)
    tre = WORK / f"{name}.tre"
    write_tre(tre, IrregularityTrack(s_m=s_m, lateral_m=zeros, vertical_m=vertical,
                                     roll_rad=zeros, gauge_m=zeros, source="s5f"))
    payload = json.loads(json.dumps(base))
    payload["case_id"] = f"s5f_{name}"
    payload["irregularity"] = {"tre": str(tre), "start_m": 0.0, "end_m": 1.0e6,
                              "fade_m": 10.0, "scale": 1.0, "channels": ["vertical"]}
    absolutise_profile_paths(payload, DATA)
    path = WORK / f"{name}.json"
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    out = WORK / f"out_{name}"
    if out.exists():
        shutil.rmtree(out)
    done = subprocess.run([sys.executable, "-X", "utf8", "-m", "velch", "run-vehicle", str(path),
                           "--output", str(out), "--fast"],
                          cwd=VELCH, capture_output=True, text=True, encoding="utf-8",
                          errors="replace")
    if done.returncode != 0 or not (out / "history.csv").exists():
        print(f"  {name}: run failed (exit {done.returncode})")
        return None
    return out


def measure(out: Path) -> np.ndarray:
    with (out / "history.csv").open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    times = np.array([float(row["time_s"]) for row in rows])
    values = np.array([float(row["axle1_box_left_z_acc_m_per_s2"]) for row in rows])
    span = times[-1] - times[0]
    mask = (times >= times[0] + 0.15 * span) & (times <= times[0] + 0.90 * span)
    times, values = times[mask], values[mask] - values[mask].mean()
    out_values = []
    for band in BANDS:
        design = np.column_stack([np.cos(2 * np.pi * times * SPEED / band),
                                  np.sin(2 * np.pi * times * SPEED / band)])
        a, b = np.linalg.lstsq(design, values, rcond=None)[0]
        out_values.append(complex(b, a))
    return np.array(out_values)


def invert(matrix: np.ndarray, measured: np.ndarray) -> np.ndarray:
    system = matrix.conj().T @ matrix + (LAMBDA ** 2) * np.eye(len(BANDS))
    return np.linalg.solve(system, matrix.conj().T @ measured)


def relative(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.linalg.norm(a - b) / np.linalg.norm(b))


def main() -> int:
    base = json.loads(BASE.read_text(encoding="utf-8"))
    base.pop("initial_state", None)
    length = float(base["run"]["duration_s"]) * SPEED + 30.0
    rng = np.random.default_rng(20261026)
    amplitudes = np.full(len(BANDS), AMPLITUDE_M)

    # Each realisation: two equations (response at each band) in four unknowns (H's entries).
    rows, targets = [], []
    for index in range(REALISATIONS):
        phases = rng.uniform(0.0, 2.0 * np.pi, size=len(BANDS))
        out = run(f"dual_{index}", amplitudes, phases, base, length)
        if out is None:
            continue
        measured = measure(out)
        inputs = amplitudes * np.exp(1j * phases)
        for band_index in range(len(BANDS)):
            row = np.zeros(len(BANDS) * len(BANDS), dtype=complex)
            for source_index in range(len(BANDS)):
                row[band_index * len(BANDS) + source_index] = inputs[source_index]
            rows.append(row)
            targets.append(measured[band_index])
    if len(rows) < len(BANDS) * len(BANDS):
        raise SystemExit(f"only {len(rows)} equations for {len(BANDS) ** 2} unknowns")

    solution = np.linalg.lstsq(np.array(rows), np.array(targets), rcond=None)[0]
    matrix = solution.reshape(len(BANDS), len(BANDS))
    print(f"H from {len(rows)} equations, condition {np.linalg.cond(matrix):.2f}")
    for row in matrix:
        print("   ", " ".join(f"|{abs(value):10.1f}|" for value in row))

    truth = SHAPE * AMPLITUDE_M
    phase = float(rng.uniform(0.0, 2.0 * np.pi))
    phases = np.full(len(BANDS), phase)
    measured = measure(run("target", truth, phases, base, length))
    recovered = invert(matrix, measured)
    error = relative(recovered, truth)
    print(f"calibration: error {error:.1%}  "
          + " ".join(f"{value * 1000:+.4f}" for value in recovered.real) + " mm")
    print("truth      :              "
          + " ".join(f"{value * 1000:+.4f}" for value in truth) + " mm")

    closure_out = run("closure", recovered.real, phases, base, length)
    if closure_out is None:
        print("closure: run failed")
    else:
        print(f"closure: response difference {relative(measure(closure_out), measured):.2%}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
