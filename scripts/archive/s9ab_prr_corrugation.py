"""Put the corrugation into the rail profile point set, then invert its depth.

Two questions, one script:

1. Can a corrugation that lives *only* in the rail profile files — a dense
   station table whose every section is lifted by ``A sin(2 pi s / lambda)`` —
   be run at all, and does it produce the same acceleration as the same
   corrugation written into a ``.tre`` track-excitation file?
2. Fed only the axle-box acceleration, how much of the depth comes back?

The equivalence half is the part worth having: the two paths reach the contact
geometry through different code (``ProfileSeries.sample`` versus
``ShiftedSeries``), so agreement is evidence that neither is mis-wired.  The
calibration is taken from the ``.tre`` run, not from the analytic
``k / m = 24398 (m/s^2)/m`` constant, because that constant was measured before
the axle-box rotational restraint existed and is now known to be vehicle
specific (see docs/AXLEBOX_RESTRAINT_2026-10-26.md).

Run:  python -X utf8 scripts/s9ab_prr_corrugation.py
"""

from __future__ import annotations

import json
import math
import sys
import time
from pathlib import Path

import numpy as np

WORK = Path(r"F:\velch_tmp\prr")
BASE_CASE = Path(r"F:\velch_tmp\straight\case_straight_axlebox.json")

WAVELENGTH_M = 0.050
DEPTH_M = 30.0e-6
SAMPLES_PER_PERIOD = 20
PATCH_START_M = 40.0
PATCH_PERIODS = 20
SPEED_KMH = 80.0
X_START_M = 38.0
DURATION_S = 0.25
OUTPUT_STEP_S = 2.0e-4
SOLVER_STEP_S = 1.0e-4
CHANNEL = "axle1_box_left_z_acc_m_per_s2"
WINDOW_START = 0.30

PATCH_END_M = PATCH_START_M + PATCH_PERIODS * WAVELENGTH_M


def speed_m_s() -> float:
    return SPEED_KMH / 3.6


def excitation_hz() -> float:
    return speed_m_s() / WAVELENGTH_M


def lift_at(s_m: float) -> float:
    """Physical lift of the rail top at this mileage; zero outside the patch."""
    if s_m < PATCH_START_M or s_m > PATCH_END_M:
        return 0.0
    phase = 2.0 * math.pi * (s_m - PATCH_START_M) / WAVELENGTH_M
    return DEPTH_M * math.sin(phase)


def shifted_prr(text: str, drop: float) -> str:
    """Return the profile text with every point's z reduced by ``drop``.

    The PRR carries ``z_sign = -1`` in this case, so the physical height is
    ``-z``; raising the rail therefore means *subtracting* from the file value.
    Only the two numeric columns of the point block are touched, and only when
    a line has at least two floats, so comments, units and the spline header
    survive byte for byte.
    """
    lines = text.splitlines(keepends=True)
    try:
        start = next(index for index, line in enumerate(lines) if "point.begin" in line)
        end = next(index for index, line in enumerate(lines) if "point.end" in line)
    except StopIteration as exc:  # pragma: no cover - malformed file
        raise ValueError("PRR point block is missing") from exc
    for index in range(start + 1, end):
        row = lines[index]
        stripped = row.strip()
        if not stripped or stripped.startswith("!"):
            continue
        fields = stripped.split()
        if len(fields) < 2:
            continue
        try:
            y_value = float(fields[0])
            z_value = float(fields[1])
        except ValueError:
            continue
        lines[index] = f" {y_value:12.8f} {z_value - drop:12.8f}\n"
    return "".join(lines)


def build_stations(base_text: str, directory: Path) -> list[tuple[float, Path]]:
    """Sparse outside the patch, one profile per sample inside it."""
    directory.mkdir(parents=True, exist_ok=True)
    step = WAVELENGTH_M / SAMPLES_PER_PERIOD
    # The table must start at the origin and cover the front axle for the whole
    # run.  A shorter table seats the vehicle on the hung branch even when the
    # surface is identical everywhere (reproduced: first station 33 m -> FAILED,
    # 0 m -> OK); that is the same near-singular eight-patch seat as O010 and it
    # is why the corpus templates always span 0..150 m.
    mileages = [0.0, PATCH_START_M]
    count = int(round(PATCH_PERIODS * SAMPLES_PER_PERIOD))
    mileages.extend(PATCH_START_M + index * step for index in range(1, count))
    mileages.append(PATCH_END_M)
    mileages.append(X_START_M + speed_m_s() * DURATION_S + 5.0)
    stations: list[tuple[float, Path]] = []
    for index, s_m in enumerate(sorted(set(mileages))):
        lift = lift_at(s_m)
        path = directory / f"profile_{index:04d}.prr"
        path.write_text(shifted_prr(base_text, lift), encoding="utf-8")
        stations.append((s_m, path))
    return stations


def build_case(stations: list[tuple[float, Path]], tre: Path | None, target: Path,
               warm_start: list[float] | None = None) -> Path:
    raw = json.loads(BASE_CASE.read_text(encoding="utf-8"))
    raw.pop("initial_state", None)
    if warm_start is not None:
        raw["initial_state"] = {"q": list(warm_start), "v": [0.0] * len(warm_start)}
    for body in raw.get("topology", {}).get("bodies", []):
        if body.get("kind") == "axlebox" and isinstance(body.get("axle"), int):
            body["axle"] = body["axle"] - 1
    raw["vehicle"]["travel_speed_m_s"] = speed_m_s()
    for template in raw["rail_templates"]:
        template["stations"] = [
            {
                "s_m": s_m,
                "id": f"{template['id']}{index}",
                "profile": {
                    **template["stations"][0]["profile"],
                    "file": str(path),
                    "format": "prr",
                },
            }
            for index, (s_m, path) in enumerate(stations)
        ]
    if tre is None:
        raw.pop("irregularity", None)
    else:
        raw["irregularity"] = {
            "tre": str(tre),
            "start_m": 0.0,
            "end_m": 1.0e7,
            "fade_m": 0.0,
            "scale": 1.0,
            "channels": ["vertical"],
        }
    run = raw.setdefault("run", {})
    run.update(
        {
            "method": "BDF",
            "jacobian": "analytic",
            "rtol": 1.0e-4,
            "atol": 1.0e-8,
            "x_start_m": X_START_M,
            "duration_s": DURATION_S,
            "output_step_s": OUTPUT_STEP_S,
            "max_solver_step_s": SOLVER_STEP_S,
            "maximum_penetration_m": 0.003,
        }
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")
    return target


def build_tre(target: Path) -> Path:
    """The same corrugation as a track excitation file, for the equivalence run."""
    from velch.irregularity import IrregularityTrack, write_tre

    step = WAVELENGTH_M / SAMPLES_PER_PERIOD
    s_m = np.arange(0.0, X_START_M + speed_m_s() * DURATION_S + 6.0, step)
    lift = np.array([lift_at(float(value)) for value in s_m])
    track = IrregularityTrack(
        s_m=s_m,
        lateral_m=np.zeros_like(s_m),
        vertical_m=lift,
        roll_rad=np.zeros_like(s_m),
        gauge_m=np.zeros_like(s_m),
        source="prr corrugation equivalence run",
    )
    return write_tre(target, track)


def warm_start(flat_profile: Path) -> list[float]:
    """Solve the static seat on the untouched two-station table, then reuse it.

    A dense station table moves the static solve onto the hung branch even
    though the surface is identical everywhere: the eight-patch seat has a
    near-zero singular direction, so the interpolation's last-bit arithmetic
    decides which branch the solver lands on.  That fragility is real (it is the
    same family as O010) and is not what this experiment is about, so the seat
    is solved once on the trivial table and carried in as ``initial_state``.
    """
    from velch.vehicle import load_vehicle_case
    from velch.vehicle_solver import VehicleDynamics, _static_vertical_equilibrium

    two = [(0.0, flat_profile), (150.0, flat_profile)]
    path = build_case(two, None, WORK / "case_warm.json")
    case = load_vehicle_case(path)
    dynamics = VehicleDynamics(case)
    q, residual = _static_vertical_equilibrium(
        case, dynamics, np.asarray(case.initial_q, dtype=float),
        np.asarray(case.initial_v, dtype=float),
    )
    print(f"warm start   : residual {residual:.3g} N on the two-station table")
    return [float(value) for value in q]


def run(case: Path, label: str) -> tuple[Path, float]:
    from velch.vehicle import load_vehicle_case
    from velch.vehicle_solver import save_vehicle_result, simulate_vehicle

    loaded = load_vehicle_case(case)
    started = time.perf_counter()
    result = simulate_vehicle(loaded)
    elapsed = time.perf_counter() - started
    out = WORK / f"out_{label}"
    save_vehicle_result(loaded, result, out)
    print(f"  {label}: {elapsed:.1f} s, status {result.summary.get('result_status')}")
    return out, elapsed


def amplitude_at_line(out: Path, *, start_m: float, end_m: float) -> tuple[float, int]:
    """Least-squares amplitude of the excitation line inside a mileage window."""
    from velch.io.history import read_history

    history = read_history(out / "history.csv")
    times = np.asarray(history.data[history.ordering.index("time_s")], dtype=float)
    values = np.asarray(history.data[history.ordering.index(CHANNEL)], dtype=float)
    mileage = start_m + speed_m_s() * times
    keep = (mileage >= start_m + WINDOW_START * (end_m - start_m)) & (mileage <= end_m)
    omega = 2.0 * math.pi * excitation_hz()
    basis = np.column_stack((np.cos(omega * times[keep]), np.sin(omega * times[keep])))
    coefficients, *_ = np.linalg.lstsq(basis, values[keep], rcond=None)
    amplitude = float(math.hypot(coefficients[0], coefficients[1]))
    return amplitude, int(np.count_nonzero(keep))


def main() -> int:
    if not BASE_CASE.exists():
        raise SystemExit(f"base case is missing: {BASE_CASE}")
    raw = json.loads(BASE_CASE.read_text(encoding="utf-8"))
    base_profile = Path(raw["rail_templates"][0]["stations"][0]["profile"]["file"])
    if not base_profile.exists():
        raise SystemExit(f"base rail profile is missing: {base_profile}")
    print(f"base profile : {base_profile}")
    print(f"wavelength   : {WAVELENGTH_M * 1e3:.1f} mm  ->  {excitation_hz():.1f} Hz at {SPEED_KMH:.0f} km/h")
    print(f"depth        : {DEPTH_M * 1e6:.1f} um peak, patch {PATCH_START_M:.1f}..{PATCH_END_M:.1f} m")

    stations = build_stations(base_profile.read_text(encoding="utf-8"), WORK / "profiles")
    print(f"stations     : {len(stations)} profile files")

    tre = build_tre(WORK / "corrugation_50mm.tre")
    flat_profile = stations[0][1]  # lift_at(first station) == 0, i.e. the untouched section
    reach = X_START_M + speed_m_s() * DURATION_S + 15.0
    plain = [(0.0, flat_profile), (PATCH_START_M, flat_profile),
             (PATCH_END_M, flat_profile), (reach, flat_profile)]
    warm = warm_start(flat_profile)
    cases = {
        "zero": build_case(plain, None, WORK / "case_zero.json", warm),
        "tre": build_case(plain, tre, WORK / "case_tre.json", warm),
        "prr": build_case(stations, None, WORK / "case_prr.json", warm),
    }

    out: dict[str, float] = {}
    for label in ("zero", "tre", "prr"):
        directory, elapsed = run(cases[label], label)
        amplitude, frames = amplitude_at_line(directory, start_m=X_START_M,
                                              end_m=X_START_M + speed_m_s() * DURATION_S)
        out[label] = amplitude
        print(f"  {label}: |a| at {excitation_hz():.0f} Hz = {amplitude:.5f} m/s^2 over {frames} frames")

    gain_prr = out["prr"] / DEPTH_M
    gain_tre = out["tre"] / DEPTH_M
    recovered_from_prr = out["prr"] / gain_tre
    payload = {
        "wavelength_m": WAVELENGTH_M,
        "depth_m": DEPTH_M,
        "excitation_hz": excitation_hz(),
        "amplitude_zero": out["zero"],
        "amplitude_tre": out["tre"],
        "amplitude_prr": out["prr"],
        "gain_prr": gain_prr,
        "gain_tre": gain_tre,
        "prr_over_tre": gain_prr / gain_tre if gain_tre else float("nan"),
        "recovered_depth_m": recovered_from_prr,
        "recovered_error_percent": 100.0 * (recovered_from_prr / DEPTH_M - 1.0),
        "analytic_constant": 24398.0,
    }
    (WORK / "prr_corrugation.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print()
    print(f"gain through the profile path : {gain_prr:,.0f} (m/s^2)/m")
    print(f"gain through the .tre path    : {gain_tre:,.0f} (m/s^2)/m")
    print(f"profile / tre                 : {payload['prr_over_tre']:.4f}")
    print(f"recovered depth               : {recovered_from_prr * 1e6:.2f} um "
          f"vs {DEPTH_M * 1e6:.2f} um truth ({payload['recovered_error_percent']:+.1f} %)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
