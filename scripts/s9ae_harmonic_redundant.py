"""Harmonic-ladder inversion on the four runs already on disk, with redundancy.

Single channel gives two equations for two depth harmonics -- an exactly square system,
so the least-squares residual is identically zero and the sigma can only report the noise
floor, not the model error.  That is the "perfect fit, wrong answer" shape this project has
been bitten by before.

Four axle-box channels give eight equations for the same four unknowns.  Now the residual
is informative: it is the part of the response the two-harmonic model cannot explain, and
the honest uncertainty has to cover it (the coverage criterion of Xiao et al.).
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))

import s9ab_prr_corrugation as prr  # noqa: E402
from velch.inverse.harmonics import (  # noqa: E402
    HarmonicModel,
    calibrate_gains,
    coverage_across_orders,
    harmonic_amplitudes,
    invert_corrugation,
)
from velch.io.history import read_history  # noqa: E402

PERIOD_M = 0.050
DEPTH_M = 30.0e-6
SECOND_M = 9.0e-6
SECOND_PHASE = 0.9
SPEED_M_S = 80.0 / 3.6
X_START_M, PATCH_M = 30.0, (42.8, 44.8)
OUT = Path(r"F:\velch_tmp\harmonic")
CHANNELS = (
    "axle1_box_left_z_acc_m_per_s2",
    "axle1_box_right_z_acc_m_per_s2",
    "axle2_box_left_z_acc_m_per_s2",
    "axle2_box_right_z_acc_m_per_s2",
)
ORDERS = (1, 2)


def load(name: str) -> tuple[np.ndarray, np.ndarray]:
    history = read_history(prr.WORK / f"out_harm_{name}" / "history.csv")
    names = history.ordering
    time = np.asarray(history.data[names.index("time_s")], dtype=float)
    centre = ((PATCH_M[0] + PATCH_M[1]) / 2.0 - X_START_M - 10.0) / SPEED_M_S
    half = 0.75 * (PATCH_M[1] - PATCH_M[0]) / SPEED_M_S + 0.02
    keep = (time >= centre - half) & (time <= centre + half)
    rows = np.asarray([history.data[names.index(channel)] for channel in CHANNELS], dtype=float)
    return time[keep], rows[:, keep]


def main() -> int:
    runs = {name: load(name) for name in ("zero", "cal_1", "cal_2", "probe")}
    fundamental = SPEED_M_S / PERIOD_M

    floor = {}
    for name, (time, rows) in runs.items():
        floor[name] = [harmonic_amplitudes(time, row, fundamental, ORDERS) for row in rows]
    floor_amp = max(abs(value[order]) for value in floor["zero"] for order in ORDERS)

    gains: list[dict[int, complex]] = []
    for index in range(len(CHANNELS)):
        gain_1 = calibrate_gains(PERIOD_M, DEPTH_M, SPEED_M_S,
                                 runs["cal_1"][0], runs["cal_1"][1][index])
        gain_2 = calibrate_gains(PERIOD_M / 2.0, DEPTH_M, SPEED_M_S,
                                 runs["cal_2"][0], runs["cal_2"][1][index])
        gains.append({1: gain_1.gains[1], 2: gain_2.gains[1]})

    measured = [{order: harmonic_amplitudes(runs["probe"][0], runs["probe"][1][index],
                                           fundamental, ORDERS)[order] for order in ORDERS}
                for index in range(len(CHANNELS))]

    # Stack the four channels: one model, four independent looks at it.
    order_list = tuple(sorted(ORDERS))
    operator = np.zeros((2 * len(CHANNELS) * len(order_list), 2 * len(order_list)))
    rhs = np.zeros(2 * len(CHANNELS) * len(order_list))
    for channel_index in range(len(CHANNELS)):
        for order_position, order in enumerate(order_list):
            gain = gains[channel_index][order]
            row = (channel_index * len(order_list) + order_position) * 2
            column = 2 * order_position
            operator[row, column] = gain.real
            operator[row, column + 1] = -gain.imag
            rhs[row] = measured[channel_index][order].real
            operator[row + 1, column] = gain.imag
            operator[row + 1, column + 1] = gain.real
            rhs[row + 1] = measured[channel_index][order].imag

    from velch.uncertainty import weighted_least_squares

    posterior = weighted_least_squares(
        operator, rhs, measurement_sigma=floor_amp,
        prior_sigma=[200e-6] * (2 * len(order_list)), prior_mean=[0.0] * (2 * len(order_list)),
    )
    truth = {1: complex(DEPTH_M), 2: SECOND_M * complex(math.cos(SECOND_PHASE),
                                                        math.sin(SECOND_PHASE))}
    model = HarmonicModel(gains=gains[0], reference_depth_m=DEPTH_M)
    wrapper = type("W", (), {})()
    predicted = operator @ posterior.mean
    residual = rhs - predicted
    residual_rms = float(np.sqrt(np.mean(residual ** 2)))
    dof = rhs.size - posterior.mean.size
    chi2_sigma = residual_rms * math.sqrt(rhs.size / max(dof, 1))

    from velch.inverse.harmonics import HarmonicInversion  # noqa: E402

    inversion = HarmonicInversion(model=model, posterior=posterior, orders=order_list,
                                  fundamental_hz=fundamental, period_m=PERIOD_M)
    rows_report = coverage_across_orders(inversion, truth)

    print(f"channels {len(CHANNELS)}, orders {order_list}: {rhs.size} equations, "
          f"{posterior.mean.size} unknowns (dof {dof})")
    print(f"floor line {floor_amp:.5f} m/s^2; residual rms {residual_rms:.5f} m/s^2; "
          f"chi2 sigma {chi2_sigma:.5f}")
    print(f"|g| per channel order 1: "
          f"{', '.join(f'{abs(gains[i][1]):.0f}' for i in range(len(CHANNELS)))}"
          f"  order 2: {', '.join(f'{abs(gains[i][2]):.0f}' for i in range(len(CHANNELS)))}")
    print("\norder   true um   recovered um    sigma um   z    inside 1 sigma")
    for row in rows_report:
        print(f"{row['order']:5d} {row['true_m'] * 1e6:10.2f} {row['estimated_m'] * 1e6:14.2f}"
              f" {row['sigma_m'] * 1e6:10.2f} {row['z']:5.1f}   {row['inside']}")

    # Re-run with the model error folded in: the honest band must cover the mismatch.
    inflated = weighted_least_squares(
        operator, rhs, measurement_sigma=max(floor_amp, chi2_sigma),
        prior_sigma=[200e-6] * 4, prior_mean=[0.0] * 4,
    )
    covered = HarmonicInversion(model=model, posterior=inflated, orders=order_list,
                                fundamental_hz=fundamental, period_m=PERIOD_M)
    rows_inflated = coverage_across_orders(covered, truth)
    print("\nwith the model error in the sigma:")
    for row in rows_inflated:
        print(f"{row['order']:5d} {row['true_m'] * 1e6:10.2f} {row['estimated_m'] * 1e6:14.2f}"
              f" {row['sigma_m'] * 1e6:10.2f} {row['z']:5.1f}   {row['inside']}")

    payload = {
        "channels": list(CHANNELS), "orders": list(ORDER_NAMES := order_list),
        "fundamental_hz": fundamental, "period_m": PERIOD_M,
        "floor_m_s2": floor_amp, "residual_rms_m_s2": residual_rms,
        "chi2_sigma_m_s2": chi2_sigma, "dof": dof,
        "gains": [[gains[i][order].real, gains[i][order].imag] for i in range(len(CHANNELS))
                  for order in order_list],
        "truth": {str(k): [v.real, v.imag] for k, v in truth.items()},
        "recovered": {str(order): [float(posterior.mean[2 * i]),
                                   float(posterior.mean[2 * i + 1])]
                      for i, order in enumerate(order_list)},
        "sigma_floor_only": {str(k): float(v) for k, v in
                             HarmonicInversion(model=model, posterior=posterior,
                                               orders=order_list, fundamental_hz=fundamental,
                                               period_m=PERIOD_M).amplitude_sigma().items()},
        "coverage_floor_only": rows_report,
        "coverage_with_model_error": rows_inflated,
    }
    (OUT / "harmonic_redundant.json").write_text(json.dumps(payload, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
