"""Invert a non-sinusoidal corrugation from the harmonic ladder it excites.

Protocol, all on the same 80 km/h window so nothing is extrapolated:

1. ``zero``  -- flat profile: the channel's floor, which sets the measurement sigma.
2. ``cal_1`` -- pure sine of period L, depth A -> complex gain of order 1 of L.
3. ``cal_2`` -- pure sine of period L/2, depth A -> gain of order 2 of L
                (a sine of half the period *is* the second harmonic of L).
4. ``probe`` -- two-harmonic profile ``A1 cos(theta) + A2 cos(2 theta + phi)``.

The two gains are the operator; ``velch.inverse.harmonics`` inverts (4) and the
recovered ``A1``/``A2`` are compared with what was written into the PRR files.
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

import s9ab_prr_corrugation as prr  # noqa: E402  (PRR rewriting + case building)
from velch.inverse.harmonics import (  # noqa: E402
    HarmonicModel,
    calibrate_gains,
    coverage_across_orders,
    harmonic_amplitudes,
    invert_corrugation,
)
from velch.io.history import read_history  # noqa: E402

WORK = Path(r"F:\velch_tmp\harmonic")
BASE_CASE = Path(r"F:\velch_tmp\straight\case_straight_axlebox.json")
PERIOD_M = 0.050
DEPTH_M = 30.0e-6
SECOND_M = 9.0e-6
SECOND_PHASE = 0.9
SPEED_KMH = 80.0
X_START_M = 30.0
# An axle passes here: with x_start 30 m the axle offsets are (-10, -7.5, +7.5, +10),
# so during the run the front axles sweep 37.5...45.6 m -- a patch at 30-34 m is never
# touched by a wheel, which is exactly the "applied but unreachable" case the loader warns
# about.
PATCH_M = (X_START_M + 12.8, X_START_M + 14.8)
DURATION_S = 0.25
OUTPUT_STEP_S = 5.0e-5
SOLVER_STEP_S = 1.0e-4
TAIL_M = X_START_M + 24.0
CHANNEL = "axle1_box_left_z_acc_m_per_s2"
FALLBACK = "axle1_z_acc_m_per_s2"


def shape_of(name: str, s_m) -> np.ndarray:
    s = np.asarray(s_m, dtype=float)
    if name == "zero":
        return np.zeros_like(s)
    if name == "cal_1":
        return DEPTH_M * np.cos(2.0 * math.pi * s / PERIOD_M)
    if name == "cal_2":
        return DEPTH_M * np.cos(4.0 * math.pi * s / PERIOD_M)
    if name == "probe":
        theta = 2.0 * math.pi * s / PERIOD_M
        return DEPTH_M * np.cos(theta) + SECOND_M * np.cos(2.0 * theta + SECOND_PHASE)
    raise SystemExit(f"unknown run {name!r}")


def base_profile_text() -> str:
    """The PRR text of the case's own first station (the flat running surface)."""

    raw = json.loads(BASE_CASE.read_text(encoding="utf-8"))
    station = raw["rail_templates"][0]["stations"][0]
    path = Path(station["profile"]["file"])
    return path.read_text(encoding="utf-8", errors="replace")


def stations_for(name: str, directory: Path) -> list[tuple[float, Path]]:
    text = base_profile_text()
    span = np.arange(PATCH_M[0], PATCH_M[1], PERIOD_M / 20.0)
    stations: list[tuple[float, Path]] = [(0.0, directory / f"{name}_start.prr"),
                                          (PATCH_M[0] - 1.0, directory / f"{name}_before.prr")]
    for path in (stations[0][1], stations[1][1]):
        path.write_text(text, encoding="utf-8")
    for index, s_m in enumerate(span):
        target = directory / f"{name}_{index:04d}.prr"
        target.write_text(prr.shifted_prr(text, float(shape_of(name, s_m))), encoding="utf-8")
        stations.append((float(s_m), target))
    # The rail coverage has to reach past the *front* axle for the whole run, otherwise
    # the static seat lands on the hung branch (every patch on one side, ~120 kN each):
    # x_start 30 m + axle offset 10 m + 5.6 m of travel + margin.
    flat_after = directory / f"{name}_after.prr"
    flat_after.write_text(text, encoding="utf-8")
    stations.append((PATCH_M[1], flat_after))
    tail = directory / f"{name}_tail.prr"
    tail.write_text(text, encoding="utf-8")
    stations.append((TAIL_M, tail))
    return stations


def apply_to_every_template(case_path: Path, stations: list[tuple[float, Path]]) -> None:
    """Put the corrugation on *both* rails.

    ``build_case`` writes the station list it is handed, which is the list of one
    template; the axle-box channel measured here is the left one, so a right-only patch
    reads as almost nothing -- which is exactly how a 30 um sag produced 0.003 m/s^2
    instead of 0.8 m/s^2 and a gain two orders of magnitude too small.
    """

    payload = json.loads(case_path.read_text(encoding="utf-8"))
    for rail in payload["rail_templates"]:
        # Each template's *own* station dict carries its y_sign / y_offset / surface, and
        # those differ between the left and right rail.  Reusing the first template's dict
        # for both put the right rail on a mirrored surface: the seat then landed on the
        # hung branch (one side carrying 120 kN per patch).
        base = rail["stations"][0]
        rail["stations"] = [
            {**base, "s_m": float(s_m),
             "profile": {**base["profile"], "file": str(path)}}
            for s_m, path in stations
        ]
    case_path.write_text(json.dumps(payload, indent=1), encoding="utf-8")


def main() -> int:
    WORK.mkdir(parents=True, exist_ok=True)
    speed = SPEED_KMH / 3.6
    captured: dict[str, dict] = {}
    for name in ("zero", "cal_1", "cal_2", "probe"):
        directory = WORK / name
        directory.mkdir(parents=True, exist_ok=True)
        stations_cache = stations_for(name, directory)
        case = prr.build_case(stations_cache, None, WORK / f"case_{name}.json", None)
        apply_to_every_template(Path(case), stations_cache)
        payload = json.loads(Path(case).read_text(encoding="utf-8"))
        payload["run"].update({"x_start_m": X_START_M, "duration_s": DURATION_S,
                               "output_step_s": OUTPUT_STEP_S,
                               "max_solver_step_s": SOLVER_STEP_S})
        Path(case).write_text(json.dumps(payload, indent=1), encoding="utf-8")
        out, elapsed = prr.run(Path(case), f"harm_{name}")
        history = read_history(out / "history.csv")
        names = history.ordering
        column = CHANNEL if CHANNEL in names else FALLBACK
        signal = np.asarray(history.data[names.index(column)], dtype=float)
        time = np.asarray(history.data[names.index("time_s")], dtype=float)
        # Analyse only the crossing, not the whole record: the front axle sweeps
        # x_start + 10 ... x_start + 10 + v*T, so a patch placed anywhere else is either
        # crossed in the first milliseconds (still inside the start-up transient) or not
        # at all -- which is why an earlier version read 0.003 m/s^2 against a floor of
        # 0.005 m/s^2 and called it a depth.
        front_offset = max(abs(value) for value in payload["run"]["axle_offset_m"]) \
            if False else 10.0
        centre_s = ((PATCH_M[0] + PATCH_M[1]) / 2.0 - X_START_M - front_offset) / speed
        half_s = 0.75 * (PATCH_M[1] - PATCH_M[0]) / speed + 0.02
        keep = (time >= centre_s - half_s) & (time <= centre_s + half_s)
        captured[name] = {"time": time[keep], "signal": signal[keep]}
        print(f"  {name}: {int(keep.sum())} samples, rms {float(np.std(signal[keep])):.4f} m/s^2,"
              f" column {column!r}, {elapsed:.1f} s")

    fundamental = speed / PERIOD_M
    orders = (1, 2)
    floor = harmonic_amplitudes(captured["zero"]["time"], captured["zero"]["signal"],
                                fundamental, orders)
    floor_amp = max(abs(floor[1]), abs(floor[2]), 1e-9)

    gain_1 = calibrate_gains(PERIOD_M, DEPTH_M, speed,
                             captured["cal_1"]["time"], captured["cal_1"]["signal"])
    gain_2 = calibrate_gains(PERIOD_M / 2.0, DEPTH_M, speed,
                             captured["cal_2"]["time"], captured["cal_2"]["signal"])
    model = HarmonicModel(gains={1: gain_1.gains[1], 2: gain_2.gains[1]},
                          reference_depth_m=DEPTH_M,
                          name="per-order calibration from two pure sines")

    measured = harmonic_amplitudes(captured["probe"]["time"], captured["probe"]["signal"],
                                   fundamental, orders)
    truth = {1: complex(DEPTH_M),
             2: SECOND_M * complex(math.cos(SECOND_PHASE), math.sin(SECOND_PHASE))}
    inverted = invert_corrugation(
        model, measured, measurement_sigma=floor_amp, prior_sigma=200e-6,
        fundamental_hz=fundamental, period_m=PERIOD_M,
        floor_gain=0.02 * abs(model.gains[1]),
    )
    rows = coverage_across_orders(inverted, truth)
    record = {
        "period_m": PERIOD_M, "speed_kmh": SPEED_KMH, "x_start_m": X_START_M,
        "floor_amplitudes": {str(k): [v.real, v.imag] for k, v in floor.items()},
        "gains": {str(k): [v.real, v.imag] for k, v in model.gains.items()},
        "measured": {str(k): [v.real, v.imag] for k, v in measured.items()},
        "truth": {str(k): [v.real, v.imag] for k, v in truth.items()},
        "recovered": {str(order): [float(inverted.posterior.mean[2 * i]),
                                   float(inverted.posterior.mean[2 * i + 1])]
                      for i, order in enumerate(inverted.orders)},
        "sigma": {str(k): float(v) for k, v in inverted.amplitude_sigma().items()},
        "coverage": rows,
        "peak_to_peak_m": inverted.peak_to_peak_m(),
    }
    (WORK / "harmonic.json").write_text(json.dumps(record, indent=1), encoding="utf-8")

    print("\norder   true um   recovered um    sigma um   inside 1 sigma")
    for row in rows:
        print(f"{row['order']:5d} {row['true_m'] * 1e6:10.2f} {row['estimated_m'] * 1e6:14.2f} "
              f"{row['sigma_m'] * 1e6:11.2f}  {row['inside']}")
    inside = sum(1 for row in rows if row["inside"])
    print(f"\n{inside}/{len(rows)} orders inside one sigma; "
          f"peak-to-peak {inverted.peak_to_peak_m() * 1e6:.1f} um "
          f"(truth {(DEPTH_M + SECOND_M) * 2e6:.1f} um)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
