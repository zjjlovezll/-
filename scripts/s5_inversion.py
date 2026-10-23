"""S5: build the response matrix H column by column and invert it.

H is measured, not derived from the Jacobian yet: one run per band with only that band excited gives
column i, and the same four analysis frequencies are read out of every run.  That is the matrix the
inverse problem actually has — whatever the Jacobian says, this is what the measurement responds to,
including the crossing transient leaking between bins.

The inversion is Tikhonov with a fixed λ list and a **discrepancy principle** choice (λ where the
residual matches the noise we measured in S4), so nothing is tuned against the truth vector.
"""

import csv
import json
import shutil
import subprocess
import sys
from pathlib import Path

VELCH = Path(r"F:\ai道岔状态反演辨识\Velch")
DATA = Path(r"F:\velch_data\validation\crh380a_m")
WORK = Path(r"F:\velch_tmp\s5")
sys.path.insert(0, str(VELCH / "src"))

import numpy as np  # noqa: E402

from velch.case.derive import absolutise_profile_paths  # noqa: E402
from velch.irregularity import IrregularityTrack, write_tre  # noqa: E402

BASE = Path(sys.argv[1]) if len(sys.argv) > 1 else DATA / "case_long_axlebox.json"
BANDS = (0.1, 0.5, 2.0, 8.0)
SPEED = 97.2222
WINDOW_S = (0.40, 0.80)
STEP_M = 0.005
AMPLITUDE_M = 0.3e-3
NOISE = 0.011          # sqrt-mean per-run scatter from S4 (0.037/0.206/1.021/36.65 over 6 runs)
LAMBDAS = (1e-4, 1e-3, 1e-2, 0.1, 1.0, 10.0)


def make_track(amplitudes: dict[float, float], length_m: float) -> IrregularityTrack:
    s_m = np.arange(int(round(length_m / STEP_M)) + 1, dtype=float) * STEP_M
    vertical = np.zeros_like(s_m)
    for band, amplitude in amplitudes.items():
        vertical += amplitude * np.sin(2.0 * np.pi * s_m / band)
    zeros = np.zeros_like(s_m)
    return IrregularityTrack(s_m=s_m, lateral_m=zeros, vertical_m=vertical,
                             roll_rad=zeros, gauge_m=zeros, source="s5")


def run(name: str, amplitudes: dict[float, float], base: dict, length_m: float) -> Path:
    WORK.mkdir(parents=True, exist_ok=True)
    tre = WORK / f"{name}.tre"
    write_tre(tre, make_track(amplitudes, length_m), comment=json.dumps(amplitudes))
    payload = json.loads(json.dumps(base))
    payload["case_id"] = f"s5_{name}"
    payload["irregularity"] = {"tre": str(tre), "start_m": 0.0, "end_m": 1.0e6,
                              "fade_m": 10.0, "scale": 1.0, "channels": ["vertical"]}
    absolutise_profile_paths(payload, DATA)
    case_path = WORK / f"{name}.json"
    case_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    out = WORK / f"out_{name}"
    if out.exists():
        shutil.rmtree(out)
    done = subprocess.run(
        [sys.executable, "-X", "utf8", "-m", "velch", "run-vehicle", str(case_path),
         "--output", str(out), "--fast"],
        cwd=VELCH, capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    if done.returncode != 0:
        print(f"{name}: run failed", done.stderr[-300:])
    return out


def measure(out: Path) -> np.ndarray:
    with (out / "history.csv").open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    times = np.array([float(row["time_s"]) for row in rows])
    values = np.array([float(row["axle1_box_left_z_acc_m_per_s2"]) for row in rows])
    span = times[-1] - times[0]
    lo, hi = times[0] + 0.15 * span, times[0] + 0.90 * span
    mask = (times >= lo) & (times <= hi)
    times, values = times[mask], values[mask]
    values = values - values.mean()
    out_values = []
    for band in BANDS:
        design = np.column_stack([np.cos(2 * np.pi * times * SPEED / band),
                                  np.sin(2 * np.pi * times * SPEED / band)])
        a, b = np.linalg.lstsq(design, values, rcond=None)[0]
        out_values.append(complex(b, a))
    return np.array(out_values)


def main() -> int:
    base = json.loads(BASE.read_text(encoding="utf-8"))
    base.pop("initial_state", None)
    length = float(base["run"]["duration_s"]) * SPEED + 30.0

    matrix = np.zeros((len(BANDS), len(BANDS)), dtype=complex)
    for index, band in enumerate(BANDS):
        out = run(f"h{index}", {band: AMPLITUDE_M}, base, length)
        matrix[:, index] = measure(out) / AMPLITUDE_M
        print(f"column {index} ({band} m): done")

    singular = np.linalg.svd(matrix, compute_uv=False)
    print("\nH (one band at a time), |H| matrix:")
    for row in range(len(BANDS)):
        print("  " + " ".join(f"{abs(matrix[row, col]):10.2f}" for col in range(len(BANDS))))
    print("singular values:", " ".join(f"{value:.3e}" for value in singular))
    print(f"condition number: {singular[0] / singular[-1]:.3e}")

    truth = np.array([0.25e-3, -0.18e-3, 0.31e-3, 0.42e-3])   # m, mixed signs on purpose
    measured = measure(run("target", dict(zip(BANDS, truth)), base, length))

    print(f"\n{'lambda':>9} {'residual':>10} {'|error| rel':>11}  recovered (mm)")
    best = None
    for lam in LAMBDAS:
        system = matrix.conj().T @ matrix + (lam ** 2) * np.eye(len(BANDS))
        recovered = np.linalg.solve(system, matrix.conj().T @ measured)
        residual = float(np.linalg.norm(matrix @ recovered - measured))
        error = float(np.linalg.norm(recovered - truth) / np.linalg.norm(truth))
        print(f"{lam:9.1e} {residual:10.3e} {error:11.1%}  "
              + " ".join(f"{value * 1000:+6.2f}" for value in recovered.real))
        if best is None and residual <= NOISE * np.sqrt(len(BANDS)):
            best = (lam, recovered, error)
    if best is None:
        print("\nno lambda met the discrepancy principle at the S4 noise level")
    else:
        lam, recovered, error = best
        print(f"\ndiscrepancy choice: lambda={lam:.1e}, |error| {error:.1%}")
        print("truth  (mm):", " ".join(f"{value * 1000:+6.2f}" for value in truth))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
