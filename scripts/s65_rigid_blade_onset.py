"""Where does the straight blade first carry load on the RIGID straight route?

`scripts/s64_straight_rigid_blade.py` puts the drawn straight blade (`zjg`) beside the stock rail and
carries the design lowering; `evaluate` merges the two bodies into one response per rail, so the blade's
own share is only visible through `velch.vehicle_solver.BODY_CONTACT_HOOK`.

Pre-registered criterion: with the design lowering the blade can only touch once the lowering falls
below the 65.47 um static penetration, i.e. at **57.208 m** (this schedule: 0.50 mm at 56.569 m falling
to 0 at 57.304 m), inside +-0.20 m.  The output step is 5e-4 s = 11.1 mm at 80 km/h, so one sample is
worth 11.1 / 170 = 6.5 % of the lowering -- that is the amplitude resolution of this measurement.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parents[1]
LOWERING_JSON = HERE / "reports" / "turnout_lowering_2026-10-29" / "lowering.json"
STATIC_PENETRATION_MM = 0.06547
THRESHOLD_N = 50.0


def design_onset_m() -> float:
    data = json.loads(LOWERING_JSON.read_text(encoding="utf-8"))
    entry = next(e for e in data["schedules"]["07(009)"] if e["feature"] == "blade")
    miles = np.array([float(v) for v in entry["mileage_m"]])
    lower = np.array([float(v) for v in entry["lowering_mm"]])
    order = np.argsort(miles)
    return float(np.interp(-STATIC_PENETRATION_MM, -lower[order], miles[order]))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", type=Path, required=True)
    parser.add_argument("--duration", type=float, default=0.30)
    parser.add_argument("--speed-kmh", type=float, default=80.0)
    args = parser.parse_args()

    from velch import vehicle_solver as solver_module
    from velch.vehicle import load_vehicle_case

    case = load_vehicle_case(args.case)
    speed = args.speed_kmh / 3.6
    planned = design_onset_m()
    frames: list[tuple[float, float]] = []

    x_start = float(case.run.x_start_m)

    def record(t_s: float, rail_id: str, entries) -> None:
        # `evaluate` reports (t, rail, ((body_id, force_n), ...)); the mileage of axle 1 is the case's
        # run start plus its own longitudinal offset (+10 m) plus what the vehicle has travelled.
        if not str(rail_id).endswith("right"):
            return
        for body_id, force_n in entries:
            if str(body_id).endswith(":blade"):
                frames.append((x_start + 10.0 + float(t_s) * speed, float(force_n)))

    saved = solver_module.BODY_CONTACT_HOOK
    solver_module.BODY_CONTACT_HOOK = record
    try:
        result = solver_module.simulate_vehicle(case)
    finally:
        solver_module.BODY_CONTACT_HOOK = saved

    peaks = np.array([value for _, value in frames], dtype=float) if frames else np.zeros(1)
    print(f"case {args.case.name}   blade evaluations {len(frames)}   peak {peaks.max():.2f} kN")
    first = next(((s_m, value) for s_m, value in frames if value > THRESHOLD_N), None)
    if first is None:
        print(f"blade never carried load (threshold {THRESHOLD_N:.0f} N) -> the run stopped before "
              f"{planned:.2f} m")
        return 3
    onset, value = first
    error = onset - planned
    print(f"first blade load   {value / 1e3:.3f} kN at {onset:.3f} m   criterion {planned:.3f} m   "
          f"error {error:+.3f} m   {'PASS' if abs(error) <= 0.20 else 'FAIL'}")
    share = next((v for m, v in frames if m >= onset + 0.50), None)
    print(f"blade share at onset + 0.50 m: {share / 1e3:.3f} kN" if share else "no sample after onset")
    return 0 if abs(error) <= 0.20 else 4


if __name__ == "__main__":
    raise SystemExit(main())
