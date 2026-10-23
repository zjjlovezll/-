"""S5b: is there a linear amplitude range at all?

Per amplitude: rebuild H from single-band runs *at that amplitude*, run the mixed target at the same
amplitude, and report three numbers -- condition number, **superposition error** ||H·truth - y||/||y||
(the number the previous round was missing), and the inversion error.  If superposition holds only at
amplitudes where the signal is below the S4 noise floor, that is the honest end of S5.
"""

import csv
import json
import shutil
import subprocess
import sys
from pathlib import Path

VELCH = Path(r"F:\ai道岔状态反演辨识\Velch")
DATA = Path(r"F:\velch_data\validation\crh380a_m")
WORK = Path(r"F:\velch_tmp\s5b")
sys.path.insert(0, str(VELCH / "src"))

import numpy as np  # noqa: E402

from velch.case.derive import absolutise_profile_paths  # noqa: E402
from velch.irregularity import IrregularityTrack, write_tre  # noqa: E402

BASE = Path(r"F:\velch_tmp\straight\case_straight_axlebox.json")
BANDS = (0.1, 0.5, 2.0, 8.0)
SHAPE = np.array([0.83, -0.60, 1.03, 1.40])       # target shape, scaled by the amplitude
SPEED = 97.2222
STEP_M = 0.005
AMPLITUDES_MM = (0.30, 0.10, 0.05)


def run(name: str, amplitudes: dict[float, float], base: dict, length_m: float) -> Path:
    WORK.mkdir(parents=True, exist_ok=True)
    s_m = np.arange(int(round(length_m / STEP_M)) + 1, dtype=float) * STEP_M
    vertical = np.zeros_like(s_m)
    for band, amplitude in amplitudes.items():
        vertical += amplitude * np.sin(2.0 * np.pi * s_m / band)
    zeros = np.zeros_like(s_m)
    tre = WORK / f"{name}.tre"
    write_tre(tre, IrregularityTrack(s_m=s_m, lateral_m=zeros, vertical_m=vertical,
                                     roll_rad=zeros, gauge_m=zeros, source="s5b"),
              comment=json.dumps(amplitudes))
    payload = json.loads(json.dumps(base))
    payload["case_id"] = f"s5b_{name}"
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
    if done.returncode != 0:
        print(f"{name}: failed", (done.stderr or "")[-200:])
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


def main() -> int:
    base = json.loads(BASE.read_text(encoding="utf-8"))
    base.pop("initial_state", None)
    length = float(base["run"]["duration_s"]) * SPEED + 30.0

    print(f"{'amp mm':>7} {'cond':>9} {'superpos':>10} {'|err| rel':>10}  recovered / truth (mm)")
    for amplitude_mm in AMPLITUDES_MM:
        amplitude = amplitude_mm * 1e-3
        matrix = np.zeros((len(BANDS), len(BANDS)), dtype=complex)
        for index, band in enumerate(BANDS):
            out = run(f"a{amplitude_mm:.2f}_h{index}", {band: amplitude}, base, length)
            matrix[:, index] = measure(out) / amplitude
        truth = SHAPE * amplitude
        measured = measure(run(f"a{amplitude_mm:.2f}_target",
                               dict(zip(BANDS, truth)), base, length))

        singular = np.linalg.svd(matrix, compute_uv=False)
        condition = singular[0] / singular[-1] if singular[-1] else float("inf")
        superposition = float(np.linalg.norm(matrix @ truth - measured)
                              / np.linalg.norm(measured))
        lam = 1e-2
        recovered = np.linalg.solve(matrix.conj().T @ matrix + (lam ** 2) * np.eye(len(BANDS)),
                                    matrix.conj().T @ measured)
        error = float(np.linalg.norm(recovered - truth) / np.linalg.norm(truth))
        pairs = " ".join(f"{rec * 1000:+.2f}/{truth_value * 1000:+.2f}"
                         for rec, truth_value in zip(recovered.real, truth))
        print(f"{amplitude_mm:7.2f} {condition:9.2f} {superposition:10.1%} {error:10.1%}  {pairs}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
