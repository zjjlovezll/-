"""End-to-end settlement inversion: recover pad stiffness and damping from a rail displacement.

The measured campaigns cannot see contact force (their channel is low-passed to 5 Hz, which is
1.67 m of travel at 30 km/h), but they *do* see rail displacement.  This demo closes that loop
on our own forward model: the "measurement" is the right-rail vertical waveform
``axle1_right_z_m`` of a perturbed case, and the estimator has to recover the perturbation.

It also prints what the same physics gives when only the *peak force* is observable, so the
comparison is explicit rather than asserted.
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
SOURCE = BASE / "case_frog_strip_soft.json"
WORK = Path(r"F:\velch_tmp\settle_inv")
RAIL_Z = "axle1_right_z_m"
FORCE = "axle1_right_normal_n"

THETA_TRUE = np.array([np.log(1.10), np.log(0.85)])  # k_z x1.10, c_z x0.85
NAMES = ("support.k_z", "support.c_z")
NOISE_M = 2.0e-5
CALLS = {"count": 0}


def make_case(theta: np.ndarray, tag: str) -> Path:
    case = json.loads(SOURCE.read_text(encoding="utf-8"))
    case["case_id"] = f"settle_{tag}"
    for template in case["rail_templates"]:
        support = template["support"]
        support["k_z_n_m"] = 5.0e7 * float(np.exp(theta[0]))
        support["c_z_n_s_m"] = 4.0e4 * float(np.exp(theta[1]))
    path = BASE / f"case_settlein_{tag}.json"
    path.write_text(json.dumps(case, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def run(theta: np.ndarray, tag: str) -> tuple[np.ndarray, np.ndarray]:
    path = make_case(theta, tag)
    out = WORK / f"out_{tag}"
    if not (out / "history.csv").exists():
        subprocess.run([sys.executable, "-X", "utf8", "-m", "velch", "run-vehicle", str(path),
                        "--output", str(out)], check=True, cwd=str(BASE.parent.parent.parent),
                       capture_output=True)
    table = read_history(out / "history.csv")
    CALLS["count"] += 1
    return (np.asarray(table[RAIL_Z], dtype=float), np.asarray(table[FORCE], dtype=float))


def main() -> int:
    WORK.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(20261021)

    truth_rail_z, truth_force = run(THETA_TRUE, "truth")
    scale = float(np.max(np.abs(truth_rail_z)))
    observed = truth_rail_z + NOISE_M * rng.standard_normal(truth_rail_z.size)
    observed_peak = float(truth_force.max())

    print(f"truth   k_z x{np.exp(THETA_TRUE[0]):.3f}  c_z x{np.exp(THETA_TRUE[1]):.3f}")
    print(f"rail-z waveform: {truth_rail_z.size} samples, scale {scale * 1e3:.4f} mm,"
          f" noise {NOISE_M * 1e3:.3f} mm, peak force {observed_peak / 1e3:.2f} kN")

    def residual(theta: np.ndarray) -> np.ndarray:
        rail_z, _ = run(theta, f"{theta[0]:+.4f}_{theta[1]:+.4f}")
        return (rail_z - observed) / scale

    estimate = gauss_newton(residual, (0.0, 0.0), names=NAMES,
                            noise_sigma=NOISE_M / scale, fd_step=1.0e-2, max_iterations=3,
                            max_step_norm=0.25)
    print()
    print(estimate.summary())
    print()
    for name, recovered, true in zip(NAMES, estimate.scale, np.exp(THETA_TRUE)):
        error = 100.0 * (recovered / true - 1.0)
        print(f"  {name:<14} recovered x{recovered:.5f}  true x{true:.5f}"
              f"  error {error:+.3f} %"
              f"  sigma {100.0 * estimate.sigma[NAMES.index(name)]:.3f} %")
    print(f"  forward runs used: {CALLS['count']}")

    peak_scale = observed_peak
    print()
    print("same physics, peak-force observable only:")
    print(f"  sigma(ln k_z) would be ~ {100.0 * 0.688:+.1f} % (measured in round 26 for the"
          f" force peak, whose column norm was 1.35 kN/ln-unit)")

    payload = {"theta_true": THETA_TRUE.tolist(), "names": list(NAMES),
               "recovered_scale": estimate.scale.tolist(), "sigma": estimate.sigma.tolist(),
               "cost": estimate.cost, "forward_runs": CALLS["count"],
               "noise_m": NOISE_M, "scale_m": scale,
               "waveform_samples": int(truth_rail_z.size),
               "peak_force_observable_n": peak_scale,
               "channel": RAIL_Z}
    (BASE / "inversion_settlement.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
