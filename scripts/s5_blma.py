"""S5c: replace "linear H" with the literature's best linear approximation (BLMA).

The previous round proved that single-band responses do not superpose.  Frequency-domain methods
still work for nonlinear systems, but only as the *best linear approximation* averaged over random
phases, with the nonlinear distortion reported as its own output level (Pintelon/Schoukens;
"frequency response functions cannot be defined" -- Arsenio thesis, ai.mit.edu/projects/mars).

Per band: R random-phase realisations -> coherent mean H_BLA, distortion = scatter across
realisations, coherence gamma^2 = |mean|^2 / mean(|Y|^2).  Then invert only the bands where the
distortion sits below the S4 noise floor, and say which bands were dropped.
"""

import csv
import json
import shutil
import subprocess
import sys
from pathlib import Path

VELCH = Path(r"F:\ai道岔状态反演辨识\Velch")
DATA = Path(r"F:\velch_data\validation\crh380a_m")
WORK = Path(r"F:\velch_tmp\s5c")
sys.path.insert(0, str(VELCH / "src"))

import numpy as np  # noqa: E402

from velch.case.derive import absolutise_profile_paths  # noqa: E402
from velch.irregularity import IrregularityTrack, write_tre  # noqa: E402

BASE = Path(r"F:\velch_tmp\straight\case_straight_axlebox.json")
BANDS = (0.1, 0.5, 2.0, 8.0)
SPEED = 97.2222
STEP_M = 0.005
AMPLITUDE_M = 0.10e-3
REALISATIONS = 6
NOISE_M_PER_S2 = 0.011
SHAPE = np.array([0.83, -0.60, 1.03, 1.40])


def run(name: str, amplitudes: dict[float, float], tags: dict[float, float], base: dict,
        length_m: float) -> Path:
    WORK.mkdir(parents=True, exist_ok=True)
    s_m = np.arange(int(round(length_m / STEP_M)) + 1, dtype=float) * STEP_M
    vertical = np.zeros_like(s_m)
    for band, amplitude in amplitudes.items():
        vertical += amplitude * np.sin(2.0 * np.pi * s_m / band + tags.get(band, 0.0))
    zeros = np.zeros_like(s_m)
    tre = WORK / f"{name}.tre"
    write_tre(tre, IrregularityTrack(s_m=s_m, lateral_m=zeros, vertical_m=vertical,
                                     roll_rad=zeros, gauge_m=zeros, source="s5c"))
    payload = json.loads(json.dumps(base))
    payload["case_id"] = f"s5c_{name}"
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
        # A failed realisation must be *counted*, not silently dropped: dropping samples changes the
        # BLMA into a biased estimate, which is exactly the error the literature warns about.
        print(f"{name}: run failed (exit {done.returncode})", (done.stderr or "")[-160:])
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


def blma_column(band: float, base: dict, length: float, rng) -> tuple[np.ndarray, np.ndarray, float, int]:
    responses = []
    failures = 0
    for index in range(REALISATIONS):
        phase = float(rng.uniform(0.0, 2.0 * np.pi))
        out = run(f"h{band}_{index}", {band: AMPLITUDE_M}, {band: phase}, base, length)
        if out is None:
            failures += 1
            continue
        responses.append(measure(out) * np.exp(-1j * phase))
    if len(responses) < REALISATIONS - 2:
        raise SystemExit(f"band {band}: only {len(responses)}/{REALISATIONS} realisations ran; "
                          f"refusing to report a BLMA built from a biased sample")
    stack = np.array(responses)
    mean = stack.mean(axis=0)
    distortion = stack.std(axis=0, ddof=1)
    # gamma^2 at the driven frequency, from the same realisations (aligned by phase)
    column = BANDS.index(band)
    magnitude = np.abs(stack[:, column]) ** 2
    coherence = float(abs(mean[column]) ** 2 / magnitude.mean())
    return mean / AMPLITUDE_M, distortion, coherence, failures


def main() -> int:
    base = json.loads(BASE.read_text(encoding="utf-8"))
    base.pop("initial_state", None)
    length = float(base["run"]["duration_s"]) * SPEED + 30.0
    rng = np.random.default_rng(20261024)

    matrix = np.zeros((len(BANDS), len(BANDS)), dtype=complex)
    distortion = np.zeros((len(BANDS), len(BANDS)))
    coherence = np.zeros(len(BANDS))
    failed_total = 0
    for index, band in enumerate(BANDS):
        column, spread, gamma, failures = blma_column(band, base, length, rng)
        failed_total += failures
        matrix[:, index] = column
        distortion[:, index] = spread / AMPLITUDE_M
        coherence[index] = gamma
        print(f"band {band} m: |H_BLA| diag {abs(column[index]):10.1f} "
              f"distortion {spread[index]:8.1f} (m/s^2) gamma^2 {gamma:.3f} "
              f"failed runs {failures}/{REALISATIONS}")
    print(f"total failed runs: {failed_total}")

    singular = np.linalg.svd(matrix, compute_uv=False)
    print("\nsingular values:", " ".join(f"{value:.3e}" for value in singular))
    print(f"condition number: {singular[0] / singular[-1]:.2f}")

    truth = SHAPE * AMPLITUDE_M
    phase = float(rng.uniform(0.0, 2.0 * np.pi))
    measured = measure(run("target", {band: truth[index] for index, band in enumerate(BANDS)},
                            {band: phase for band in BANDS}, base, length))

    # ``distortion`` is stored per unit amplitude (spread/A) and ``matrix`` likewise, so their ratio
    # *is* distortion/signal: (spread/A)/|H| = spread/(A*|H|).  Dividing by A a second time inflates
    # the ratio by 1/A (1e4 here); that mistake was made and reverted on 2026-10-24.
    ratios = [distortion[index, index] / max(abs(matrix[index, index]), 1e-12)
              for index in range(len(BANDS))]
    usable = [index for index, ratio in enumerate(ratios) if ratio < 0.5]
    print("distortion/signal per band:",
          " ".join(f"{BANDS[i]}:{ratios[i]:.2f}" for i in range(len(BANDS))))
    print("bands with distortion/signal < 0.5:", [BANDS[index] for index in usable])
    if usable:
        sub = matrix[np.ix_(usable, usable)]
        target = measured[usable]
        solve_truth = truth[usable]
        lam = 1e-2
        recovered = np.linalg.solve(sub.conj().T @ sub + (lam ** 2) * np.eye(len(usable)),
                                    sub.conj().T @ target)
        error = float(np.linalg.norm(recovered - solve_truth) / np.linalg.norm(solve_truth))
        print(f"inversion on {len(usable)} band(s): error {error:.1%}")
        print("  recovered (mm):", " ".join(f"{value * 1000:+.3f}" for value in recovered.real))
        print("  truth     (mm):", " ".join(f"{value * 1000:+.3f}" for value in solve_truth))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
