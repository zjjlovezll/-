"""Synthetic inversion: recover two rail/contact parameters from a simulated measurement.

This is the first end-to-end inverse run of the solver, and it is deliberately
synthetic: the "measurement" is another run of the same model at a known parameter
set. That isolates the estimator from model error, which is the only way to tell a
convergence failure from a modelling failure. Real-data inversion has to come after.

Protocol, in the order the architecture requires:

  1. declare the unknowns as a ``CaseSpec`` (base value pulled from the case file);
  2. run the *nominal* model and a central-difference sensitivity at that point;
  3. ask :mod:`velch.inverse.identifiability` which unknowns the channels separate --
     this runs *before* any estimation, and a parameter it calls unidentifiable is
     dropped from the optimisation instead of being given an invented number;
  4. generate the synthetic truth by running the model at a known theta;
  5. Gauss-Newton with Levenberg damping on the surviving subset;
  6. report recovered vs truth, the required runs, and the cost history.

Two unknowns, both physically meaningful on the right rail:

  ``rail_k_z``    support stiffness under the rail  (nominal 50 MN/m)
  ``contact_c``   normal contact damping            (nominal 1e6 N s/m^1.5)

The truth is set to +30 % stiffness and -40 % damping, i.e. a soft/spongy track with
a lossy contact -- the direction a worn fastening plus a fouled contact would go.
"""

from __future__ import annotations

import json
import math
import time
from pathlib import Path

import numpy as np

from velch.case.spec import CaseSpec, ParameterSpec
from velch.inverse.identifiability import Sensitivity, analyse, finite_difference_jacobian
from velch.vehicle_solver import simulate_vehicle

BASE = Path(__file__).resolve().parent
SOURCE = BASE / "case_Z_local_rail.json"
WINDOW = BASE / "case_inverse_window.json"

DURATION_S = 0.02
OUTPUT_STEP_S = 0.0002
SIGMA_FORCE_N = 2.0e3      # 2 kN on a ~60 kN channel: 3 %
SIGMA_Z_M = 2.0e-5         # 20 um: an LVDT on the rail foot, deliberately tight
THETA_TRUTH = (0.30, -0.40)
STEPS = (0.02, 0.02)       # central-difference step in theta (2 %/2 %)

PARAMETERS = (
    ParameterSpec.of("rail_k_z", ("rail_templates", 0, "support", "k_z_n_m")),
    ParameterSpec.of("contact_c", ("contact", "normal_damping_n_s_m_1p5")),
)


def write_window_case() -> Path:
    raw = json.loads(SOURCE.read_text(encoding="utf-8"))
    raw["case_id"] = "crh380a_m_inverse_window"
    raw["run"]["duration_s"] = DURATION_S
    raw["run"]["output_step_s"] = OUTPUT_STEP_S
    WINDOW.write_text(json.dumps(raw, indent=2, ensure_ascii=False), encoding="utf-8")
    return WINDOW


def channel_series(result) -> tuple[np.ndarray, np.ndarray]:
    force = np.array([entry["axle1_right"].normal_force_n for entry in result.contacts])
    height = np.asarray(result.positions[:, 1], dtype=float)
    if force.shape != height.shape:
        raise RuntimeError(f"channel length mismatch: {force.shape} vs {height.shape}")
    return force, height


def main() -> int:
    write_window_case()
    spec = CaseSpec.from_path(WINDOW, PARAMETERS)
    print(f"parameters: {[(p.name, f'{p.base:.6g}') for p in spec.parameters]}")
    runs = 0

    def series(theta) -> tuple[np.ndarray, np.ndarray]:
        nonlocal runs
        case = spec.resolve(theta)
        result = simulate_vehicle(case)
        if result.summary.get("result_status") != "numerically_checked":
            raise RuntimeError(f"case not checked: {result.summary.get('result_status')}")
        runs += 1
        return channel_series(result)

    started = time.perf_counter()
    force_nominal, height_nominal = series(np.zeros(2))
    samples = force_nominal.size
    print(f"nominal run: {samples} samples, {time.perf_counter() - started:.1f} s, "
          f"peak {force_nominal.max() / 1e3:.2f} kN")

    def residual(theta) -> np.ndarray:
        force, height = series(theta)
        return np.concatenate(((force - truth_force) / SIGMA_FORCE_N,
                               (height - truth_height) / SIGMA_Z_M))

    # Synthetic measurement: same model, known parameters.
    truth_force, truth_height = series(np.asarray(THETA_TRUTH))
    print(f"truth run: peak {truth_force.max() / 1e3:.2f} kN, "
          f"rail drop {1e3 * (truth_height.max() - truth_height.min()):.3f} mm")

    # Identifiability first, on the nominal model.
    started = time.perf_counter()
    sensitivity = finite_difference_jacobian(residual, np.zeros(2), STEPS)
    sensitivity = Sensitivity(names=tuple(p.name for p in spec.parameters),
                              jacobian=sensitivity.jacobian,
                              scales=tuple([SIGMA_FORCE_N] * samples
                                           + [SIGMA_Z_M] * samples))
    verdict = analyse(sensitivity)
    print(f"\nidentifiability ({time.perf_counter() - started:.1f} s, {runs} runs):")
    print(verdict.summary())
    for note in verdict.notes:
        print("  note:", note)

    active = [index for index, spec_item in enumerate(spec.parameters)
              if verdict.identifiable[spec_item.name]]
    if not active:
        print("nothing identifiable: stop before estimating")
        return 1

    # Levenberg damped Gauss-Newton.
    theta = np.zeros(len(spec.parameters))
    lam = 1.0e-2
    history: list[dict[str, float]] = []
    for iteration in range(1, 7):
        started = time.perf_counter()
        jac = finite_difference_jacobian(residual, theta, STEPS).jacobian
        current = residual(theta)
        cost = float(current @ current)
        history.append({"iteration": iteration, "cost": cost,
                        **{name: float(theta[i]) for i, name in enumerate(verdict.names)}})
        print(f"\niter {iteration}: cost {cost:.4g} "
              f"theta {np.array2string(theta, precision=4)} "
              f"({time.perf_counter() - started:.1f} s)")
        free = jac[:, active]
        step = np.zeros_like(theta)
        matrix = free.T @ free
        vector = -free.T @ current
        try:
            step[active] = np.linalg.solve(matrix + lam * np.diag(np.diag(matrix)), vector)
        except np.linalg.LinAlgError:
            print("  singular system: increase damping")
            lam *= 10.0
            continue
        trial = theta + step
        if np.any(trial < -0.85) or np.any(trial > 8.0):
            print("  step left the bounds: increase damping")
            lam *= 10.0
            continue
        trial_cost = float(residual(trial) @ residual(trial))
        if trial_cost < cost:
            theta = trial
            lam = max(lam * 0.3, 1.0e-6)
            if np.max(np.abs(step)) < 1.0e-3:
                print("  converged: step below 1e-3")
                history.append({"iteration": iteration + 1,
                                "cost": trial_cost,
                                **{name: float(theta[i])
                                   for i, name in enumerate(verdict.names)}})
                break
        else:
            lam *= 10.0

    print("\nresult")
    for index, item in enumerate(spec.parameters):
        truth = item.value(THETA_TRUTH[index])
        recovered = item.value(theta[index])
        error = 100.0 * (recovered / truth - 1.0)
        print(f"  {item.name:<12} truth {truth:10.6g}  recovered {recovered:10.6g}  "
              f"error {error:+6.2f}%  theta {theta[index]:+.4f} (truth {THETA_TRUTH[index]:+.2f})")
    print(f"  forward runs used: {runs}")
    report = {
        "case": str(WINDOW.name),
        "samples": int(samples),
        "duration_s": DURATION_S,
        "theta_truth": list(THETA_TRUTH),
        "theta_recovered": [float(value) for value in theta],
        "parameters": [item.name for item in spec.parameters],
        "base": [item.base for item in spec.parameters],
        "identifiability": {
            "rank": verdict.rank,
            "condition_number": None if math.isinf(verdict.condition_number)
            else verdict.condition_number,
            "sensitivity": verdict.normalised_sensitivity,
            "identifiable": verdict.identifiable,
            "coverage": verdict.coverage,
            "singular_values": list(verdict.singular_values),
        },
        "history": history,
        "runs": runs,
        "sigma_force_n": SIGMA_FORCE_N,
        "sigma_z_m": SIGMA_Z_M,
    }
    out = BASE / "inversion_demo.json"
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"written {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
