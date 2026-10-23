"""S5e: the two remaining criteria -- closure and blind test -- on the two usable bands.

Closure: rebuild the track from the *recovered* amplitudes, run it, and compare the response with the
measurement the inversion was fitted to.  If the recovered set is physically the same track, the two
measurements must agree; if H is only a curve fit, they will not.

Blind: a different amplitude pattern (signs flipped where they were positive), fitted with the same
H, compared against a *tolerance relative to the calibration error* (<=1.5x) rather than against zero.
"""

import csv
import json
import shutil
import subprocess
import sys
from pathlib import Path

VELCH = Path(r"F:\ai道岔状态反演辨识\Velch")
DATA = Path(r"F:\velch_data\validation\crh380a_m")
WORK = Path(r"F:\velch_tmp\s5e")
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
BLIND_SHAPE = np.array([-0.62, 0.88])
LAMBDA = 1e-2


def run(name: str, amplitudes: dict[float, float], tags: dict[float, float], base: dict,
        length_m: float) -> Path | None:
    WORK.mkdir(parents=True, exist_ok=True)
    s_m = np.arange(int(round(length_m / STEP_M)) + 1, dtype=float) * STEP_M
    vertical = np.zeros_like(s_m)
    for band, amplitude in amplitudes.items():
        vertical += amplitude * np.sin(2.0 * np.pi * s_m / band + tags.get(band, 0.0))
    zeros = np.zeros_like(s_m)
    tre = WORK / f"{name}.tre"
    write_tre(tre, IrregularityTrack(s_m=s_m, lateral_m=zeros, vertical_m=vertical,
                                     roll_rad=zeros, gauge_m=zeros, source="s5e"))
    payload = json.loads(json.dumps(base))
    payload["case_id"] = f"s5e_{name}"
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
        print(f"{name}: run failed (exit {done.returncode})", (done.stderr or "")[-140:])
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


def column(band: float, base: dict, length: float, rng) -> np.ndarray:
    stack = []
    for index in range(REALISATIONS):
        phase = float(rng.uniform(0.0, 2.0 * np.pi))
        out = run(f"h{band}_{index}", {band: AMPLITUDE_M}, {band: phase}, base, length)
        if out is None:
            continue
        stack.append(measure(out) * np.exp(-1j * phase))
    if len(stack) < REALISATIONS - 1:
        raise SystemExit(f"band {band}: only {len(stack)} realisations ran")
    return np.array(stack).mean(axis=0) / AMPLITUDE_M


def invert(matrix: np.ndarray, measured: np.ndarray) -> np.ndarray:
    system = matrix.conj().T @ matrix + (LAMBDA ** 2) * np.eye(len(BANDS))
    return np.linalg.solve(system, matrix.conj().T @ measured)


def relative(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.linalg.norm(a - b) / np.linalg.norm(b))


def main() -> int:
    base = json.loads(BASE.read_text(encoding="utf-8"))
    base.pop("initial_state", None)
    length = float(base["run"]["duration_s"]) * SPEED + 30.0
    rng = np.random.default_rng(20261025)

    matrix = np.zeros((len(BANDS), len(BANDS)), dtype=complex)
    for index, band in enumerate(BANDS):
        matrix[:, index] = column(band, base, length, rng)
    condition = np.linalg.cond(matrix)
    print(f"H (2x2) condition {condition:.2f}")

    truth = SHAPE * AMPLITUDE_M
    phase = float(rng.uniform(0.0, 2.0 * np.pi))
    tags = {band: phase for band in BANDS}
    measured = measure(run("target", dict(zip(BANDS, truth)), tags, base, length))
    recovered = invert(matrix, measured)
    calibration = relative(recovered, truth)
    print(f"calibration: error {calibration:.1%}  "
          + " ".join(f"{value * 1000:+.4f}" for value in recovered.real) + " mm")
    print("truth      :              "
          + " ".join(f"{value * 1000:+.4f}" for value in truth) + " mm")

    closure_out = run("closure", dict(zip(BANDS, recovered.real)), tags, base, length)
    if closure_out is None:
        print("closure: run failed")
    else:
        closure = relative(measure(closure_out), measured)
        print(f"closure: response difference {closure:.2%} (criterion <10 %)")

    blind = BLIND_SHAPE * AMPLITUDE_M
    blind_phase = float(rng.uniform(0.0, 2.0 * np.pi))
    blind_measured = measure(run("blind", dict(zip(BANDS, blind)),
                                 {band: blind_phase for band in BANDS}, base, length))
    blind_recovered = invert(matrix, blind_measured)
    blind_error = relative(blind_recovered, blind)
    print(f"blind: error {blind_error:.1%} "
          f"(criterion <= 1.5x calibration = {1.5 * calibration:.1%}) -> "
          f"{'PASS' if blind_error <= 1.5 * calibration else 'FAIL'}")
    print("blind truth:", " ".join(f"{value * 1000:+.4f}" for value in blind) + " mm")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
