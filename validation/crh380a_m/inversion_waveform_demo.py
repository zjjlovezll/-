"""Recover BOTH fastener parameters from the waveform, on the real dynamics.

The identifiability gate says the 20 ms force waveform separates ``rail_k_z`` from
``rail_c_z`` (rank 2, condition 1.44) while the peak alone cannot (rank 1, condition inf).
This script closes that loop: perturb both parameters, run the real solver for the
"measurement", add a stated noise level, and let Levenberg-Marquardt find them back.

Cost: one forward run is ~12 s, and each LM step needs ~4, so keep the iteration count low.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import numpy as np

from velch.inverse.estimator import gauss_newton
from velch.io.history import read_history

BASE = Path(__file__).resolve().parent
SOURCE = BASE / "case_inverse_window.json"
WORK = Path(r"F:\velch_tmp\obs_lm")
CHANNEL = "axle1_right_normal_n"
NOISE_N = 1.0e3
TRUE_SCALE = np.array([1.10, 0.90])       # rail_k_z, rail_c_z
START_SCALE = np.array([1.00, 1.00])
NAMES = ("rail_k_z", "rail_c_z")
CALLS = {"n": 0}


def run(scale: np.ndarray) -> np.ndarray:
    CALLS["n"] += 1
    case = json.loads(SOURCE.read_text(encoding="utf-8"))
    case["case_id"] = "lmdemo"
    for template in case["rail_templates"]:
        template["support"]["k_z_n_m"] *= float(scale[0])
        template["support"]["c_z_n_s_m"] *= float(scale[1])
    path = BASE / "obsdiff_lmdemo.json"
    path.write_text(json.dumps(case, indent=2, ensure_ascii=False), encoding="utf-8")
    out = WORK / "run"
    subprocess.run([sys.executable, "-X", "utf8", "-m", "velch", "run-vehicle", str(path),
                    "--output", str(out)], check=True, cwd=str(BASE.parent.parent.parent),
                   capture_output=True)
    table = read_history(out / "history.csv")
    return np.asarray(table[CHANNEL], dtype=float)


def main() -> int:
    WORK.mkdir(parents=True, exist_ok=True)
    observed = run(TRUE_SCALE)
    rng = np.random.default_rng(11)
    observed = observed + rng.normal(0.0, NOISE_N, observed.size)
    print(f"observed peak {observed.max() / 1e3:.2f} kN over {observed.size} samples, "
          f"noise {NOISE_N / 1e3:.2f} kN")

    cache: dict[tuple[float, float], np.ndarray] = {}

    def residual(theta: np.ndarray) -> np.ndarray:
        scale = START_SCALE * np.exp(theta)
        key = (round(float(scale[0]), 12), round(float(scale[1]), 12))
        if key not in cache:
            cache[key] = run(scale)
        return (cache[key] - observed) / NOISE_N

    estimate = gauss_newton(residual, np.zeros(2), names=NAMES, noise_sigma=1.0,
                            fd_step=2.0e-3, max_iterations=6, initial_damping=1.0e-2,
                            max_step_norm=0.15, tolerance=1.0e-4)
    print(f"\nforward runs {CALLS['n']}")
    print(estimate.summary())
    recovered = START_SCALE * estimate.scale
    for i, name in enumerate(NAMES):
        error = 100.0 * (recovered[i] / TRUE_SCALE[i] - 1.0)
        print(f"  {name:<10} true {TRUE_SCALE[i]:.4f}  recovered {recovered[i]:.4f}"
              f"  error {error:+.3f} %")
    payload = {
        "true_scale": TRUE_SCALE.tolist(),
        "start_scale": START_SCALE.tolist(),
        "recovered_scale": recovered.tolist(),
        "estimate": estimate.report(),
        "forward_runs": CALLS["n"],
        "noise_n": NOISE_N,
        "samples": int(observed.size),
    }
    (BASE / "inversion_waveform_demo.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
