"""S6a: does lifting the input features (Koopman-style) explain the amplitude-dependent gain?

The linear model says response_i = sum_j H_ij a_j.  It failed: measuring H with one band present
changed the other band's gain by 14 %, and inversion came out 65 % off.  A lifted model keeps the
least-squares problem linear in the COEFFICIENTS but makes it nonlinear in the amplitude:

    response_i = sum_j (c_ij * a_j + d_ij * a_j * |a_j| / a_ref)

If the cross-validated prediction error drops from the linear model's level to a few percent, the
lifting works and the next step is to invert it.  If it does not drop, the honest conclusion is that
this system is not describable by these features either, and the line should stop here.
"""

import csv
import json
import shutil
import subprocess
import sys
from pathlib import Path

VELCH = Path(r"F:\ai道岔状态反演辨识\Velch")
DATA = Path(r"F:\velch_data\validation\crh380a_m")
WORK = Path(r"F:\velch_tmp\s6a")
sys.path.insert(0, str(VELCH / "src"))

import numpy as np  # noqa: E402
from scipy.optimize import least_squares  # noqa: E402

from velch.case.derive import absolutise_profile_paths  # noqa: E402
from velch.irregularity import IrregularityTrack, write_tre  # noqa: E402

BASE = Path(r"F:\velch_tmp\straight\case_straight_axlebox.json")
BANDS = (0.1, 2.0)
SPEED = 97.2222
STEP_M = 0.005
A_REF = 0.10e-3
LEVELS_MM = ((0.05, 0.10, 0.20, 0.35), (0.05, 0.10, 0.20, 0.30))
REALISATIONS = 12
SHAPE = np.array([0.83, 1.03])
HOLDOUT = 3


def run(name, amplitudes, phases, base, length_m):
    WORK.mkdir(parents=True, exist_ok=True)
    s_m = np.arange(int(round(length_m / STEP_M)) + 1, dtype=float) * STEP_M
    vertical = np.zeros_like(s_m)
    for band, amplitude, phase in zip(BANDS, amplitudes, phases):
        vertical += amplitude * np.sin(2.0 * np.pi * s_m / band + phase)
    zeros = np.zeros_like(s_m)
    tre = WORK / f"{name}.tre"
    write_tre(tre, IrregularityTrack(s_m=s_m, lateral_m=zeros, vertical_m=vertical,
                                     roll_rad=zeros, gauge_m=zeros, source="s6a"))
    payload = json.loads(json.dumps(base))
    payload["case_id"] = f"s6a_{name}"
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
        return None
    return out


def measure(out):
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


def design(amplitudes, lifted):
    """One row per realisation per output band; columns are complex coefficients."""
    n = len(BANDS)
    width = 2 * n if lifted else n
    rows = []
    for output in range(n):
        row = np.zeros(n * width, dtype=complex)
        start = output * width
        for source in range(n):
            amplitude = amplitudes[source]
            row[start + source] = amplitude
            if lifted:
                row[start + n + source] = amplitude * abs(amplitude) / A_REF
        rows.append(row)
    return rows


def fit(samples, lifted):
    matrix, targets = [], []
    for amplitudes, response in samples:
        for row, value in zip(design(amplitudes, lifted), response):
            matrix.append(row)
            targets.append(value)
    return np.linalg.lstsq(np.array(matrix), np.array(targets), rcond=None)[0]


def predict(coefficients, amplitudes, lifted):
    return np.array([np.dot(row, coefficients) for row in design(amplitudes, lifted)])


def relative(a, b):
    return float(np.linalg.norm(a - b) / np.linalg.norm(b))


def main():
    base = json.loads(BASE.read_text(encoding="utf-8"))
    base.pop("initial_state", None)
    length = float(base["run"]["duration_s"]) * SPEED + 30.0
    rng = np.random.default_rng(20261025)

    samples = []
    for index in range(REALISATIONS):
        amplitudes = np.array([rng.choice(LEVELS_MM[band]) for band in range(len(BANDS))]) * 1e-3
        phases = rng.uniform(0.0, 2.0 * np.pi, size=len(BANDS))
        out = run(f"mix_{index}", amplitudes, phases, base, length)
        if out is None:
            print(f"  mix_{index}: run failed, dropped")
            continue
        samples.append((amplitudes, measure(out)))
    if len(samples) < 8:
        raise SystemExit(f"only {len(samples)} usable realisations")

    train, test = samples[:-HOLDOUT], samples[-HOLDOUT:]
    print(f"realisations: {len(samples)} usable, {len(train)} train / {len(test)} held out")
    report = {}
    for lifted in (False, True):
        coefficients = fit(train, lifted)
        error = np.mean([relative(predict(coefficients, amplitudes, lifted), response)
                         for amplitudes, response in test])
        report["lifted" if lifted else "linear"] = error
        print(f"{'lifted' if lifted else 'linear'}: held-out relative error {error:.1%}")
    print(json.dumps(report))

    if report["lifted"] >= report["linear"]:
        print("VERDICT: no gain from lifting -- stop here")
        return 0

    coefficients = fit(samples, True)
    truth = SHAPE * 1e-3
    phase = float(rng.uniform(0.0, 2.0 * np.pi))
    target = measure(run("target", truth, np.full(len(BANDS), phase), base, length))
    start = truth.copy()

    def residual(amplitudes):
        difference = predict(coefficients, np.abs(amplitudes), True) - target
        return np.concatenate([difference.real, difference.imag]) / np.linalg.norm(target)

    solution = least_squares(residual, start, bounds=(0.0, 0.6e-3), xtol=1e-12, ftol=1e-12)
    recovered = np.abs(solution.x)
    print(f"lifted inverse: error {relative(recovered, truth):.1%}  "
          + " ".join(f"{value * 1000:+.4f}" for value in recovered) + " mm")
    print("truth         :              "
          + " ".join(f"{value * 1000:+.4f}" for value in truth) + " mm")

    closure = run("closure", recovered, np.full(len(BANDS), phase), base, length)
    if closure is not None:
        print(f"closure: {relative(measure(closure), target):.2%}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
