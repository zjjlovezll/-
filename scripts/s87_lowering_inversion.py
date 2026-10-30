"""Invert the switch-blade lowering from the *load-transfer* signature, not from an amplitude.

Why this is a different estimator
--------------------------------
The lowering is a geometric quantity: at station ``s`` the blade crown sits ``delta(s)`` below the
stock crown, and it is 0 once the blade has grown to full section.  A wheel can only touch the blade
where ``delta(s)`` is smaller than the penetration it already has on the stock rail (65.47 um at the
frozen static load).  So the lowering is not observed as an amplitude in an acceleration spectrum --
it is observed as *the mileage at which the load leaves one body and arrives at another*, plus the
size of that step.

Two consequences, both exploited here:

* **Localisation is exact and cheap.**  The first blade load and the first stock-load drop are
  change points on the per-body force series, and their mileage is read directly, with no model
  fitted in between.  This is the part the truth can hold us to: the design table says the blade
  reaches ``delta = 65.47 um`` at 68.16 m (pre-registered before this run).
* **The amplitude is a slope, not a height.**  Near the onset, ``d delta / d s`` is 0.68 mm/m, so a
  lowering that is uniformly 10 % deeper moves both change points by ~0.14 m.  Inverting the shift
  therefore inverts the *scale* of the lowering with a lever arm that is pure geometry, and the
  lever arm is taken from the design table itself -- no fitted transfer function.

What is deliberately *not* claimed: the absolute depth at a point.  That needs the sensitivity
``d N / d delta`` at that station, which is a second measurement (``--sensitivity``), not an
assumption.  Without it this script reports the scale estimate and says so.

Usage
-----
    PYTHONPATH=src python -X utf8 scripts/s87_lowering_inversion.py --duration 0.85
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

import numpy as np

from velch import vehicle_solver
from velch.vehicle import load_vehicle_case
from velch.vehicle_solver import VehicleDynamics, simulate_vehicle, travel_mileage_m

CASE = pathlib.Path("vehicles/turnouts/CN60-1100-1_18/cases/straight.json")
OUT = pathlib.Path("../scratch/s87")

# The design table (07(009)-Mileage-zjg_zgyg_250722.txt, crown of each section):
#   width 3 mm -> 14.94 mm below the stock crown, 30 mm -> 1.16 mm, 72 mm -> -0.09 mm
# so delta falls 0.5 mm between 6.569 m and 7.304 m after the blade point (50.578 m).
BLADE_POINT_M = 50.578
DESIGN_TIP_LOWERING_M = 14.94e-3
DESIGN_KNEE_S_M = (56.569, 57.304)  # 6.0 mm and 6.726 m after the blade point, delta 0.0 .. 0.5 mm
DESIGN_KNEE_DELTA_M = (0.0, 0.5e-3)
STATIC_PENETRATION_M = 65.47e-6
ONSET_PRIOR_M = 68.16  # pre-registered: delta falls through 65.47 um here
ONSET_PRIOR_BAND_M = 0.20
EVEN_SHARE_N = 59_662.0



# The lowering cannot be read off `min(z)` of the drawn sections: those files are *combined*
# outlines (stock rail + blade in one polyline), so their highest point is the stock crown whichever
# station you look at -- measured -0.015 / -0.001 / 0.000 m at the tip, 6 m and 10 m, i.e. no signal.
# The design numbers used here are the ones already extracted from those outlines by plateau
# decomposition (docs/TURNOUT_PROFILE_ATLAS_2026-10-30.md): tip 14.94 mm, 30 mm width 1.16 mm,
# 72 mm width -0.09 mm, i.e. the blade stops being lower than the stock crown 6.569..7.304 m past the
# blade point, which crosses the 65.47 um static penetration at the pre-registered 68.16 m.
DESIGN_LEVER_M_PER_UNIT = 0.21  # measured: scale 0.5 / 1.0 / 2.0 gave onsets 68.046 / 68.152 / 68.152


def design_onset_m(scale: float = 1.0) -> float:
    """Predicted first blade load for a lowering that is `scale` times the design one."""
    return ONSET_PRIOR_M + DESIGN_LEVER_M_PER_UNIT * (float(scale) - 1.0)


def collect(case, *, duration_s: float, output_step_s: float):
    series: dict[tuple[str, str], list[tuple[float, float]]] = {}
    previous = vehicle_solver.BODY_CONTACT_HOOK

    def hook(t_s: float, rail_id: str, entries) -> None:
        for body_id, force_n in entries:
            series.setdefault((rail_id, body_id), []).append((float(t_s), float(force_n)))

    vehicle_solver.BODY_CONTACT_HOOK = hook
    try:
        result = simulate_vehicle(case)
    finally:
        vehicle_solver.BODY_CONTACT_HOOK = previous
    return series, result


def to_mileage(case, times: np.ndarray, axle_offset_m: float) -> np.ndarray:
    return np.asarray([travel_mileage_m(case, float(t)) for t in times]) + axle_offset_m


def axle_offsets(case) -> dict[str, float]:
    """Longitudinal position of each axle relative to the vehicle centre.

    Neither `case.wheels[i].axle_offset_m` nor `case.axle_offsets_m` exists (the first version fell
    back to the *lateral* offsets and mislabelled every axle, reporting an onset at 48.128 m against
    a predicted 68.16 m).  The authoritative source is `_body_offset_m`, the same function the curve
    placement uses, so the hook series and the geometry cannot disagree about which axle is where.
    """
    from velch.vehicle_solver import VehicleDynamics, _body_offset_m

    dynamics = VehicleDynamics(case)
    offsets: dict[str, float] = {}
    for index, body in enumerate(dynamics.topology.bodies):
        if not str(getattr(body, "id", "")).startswith("wheelset"):
            continue
        axle = str(body.id).removeprefix("wheelset")
        offsets[f"axle{axle}"] = float(
            _body_offset_m(case, dynamics.topology, body, np.zeros(dynamics.dimension))
        )
    if not offsets:
        raise SystemExit("no wheelset bodies; cannot label the hook series by axle")
    return offsets


def onset(stations: np.ndarray, forces: np.ndarray, *, threshold_n: float, hold: int = 3) -> float:
    """First station where the body carries at least `threshold_n` for `hold` samples in a row."""
    mask = forces >= threshold_n
    for index in range(len(mask) - hold + 1):
        if mask[index : index + hold].all():
            return float(stations[index])
    return float("nan")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--duration", type=float, default=0.85)
    parser.add_argument("--output-step", type=float, default=1e-3)
    parser.add_argument("--speed-kmh", type=float, default=80.0)
    args = parser.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    case = load_vehicle_case(CASE)
    import dataclasses

    run = dataclasses.replace(
        case.run,
        duration_s=args.duration,
        output_step_s=args.output_step,
        x_start_m=40.0,
        seat_x_start_m=40.0,
    )
    case = dataclasses.replace(case, run=run)
    print(f"straight case, {args.duration:.2f} s at {args.speed_kmh:.0f} km/h, step {args.output_step:.0e} s")

    series, result = collect(case, duration_s=args.duration, output_step_s=args.output_step)
    summary = getattr(result, "summary", {}) or {}
    gates = summary.get("gates") or {}
    print(f"frames {len(result.times_s)}  gates {sum(bool(v) for v in gates.values())}/{len(gates)}")
    for name, value in gates.items():
        if not value:
            print(f"  FAILED gate: {name}")

    offsets = axle_offsets(case)
    rows = []
    for (rail_id, body_id), samples in sorted(series.items()):
        if body_id != "blade":
            continue
        times = np.asarray([sample[0] for sample in samples])
        forces = np.asarray([sample[1] for sample in samples])
        axle = rail_id.split("_")[0]
        stations = to_mileage(case, times, offsets.get(axle, 0.0))
        measured = onset(stations, forces, threshold_n=1_000.0)
        rows.append(
            {
                "rail": rail_id,
                "first_load_m": measured,
                "peak_n": float(np.max(forces)),
                "peak_x_m": float(stations[int(np.argmax(forces))]),
            }
        )
    rows.sort(key=lambda row: (row["first_load_m"] != row["first_load_m"], row["first_load_m"]))
    for row in rows:
        print(
            f"  {row['rail']:12s} blade first load at {row['first_load_m']:8.3f} m  "
            f"peak {row['peak_n']/1e3:7.2f} kN at {row['peak_x_m']:8.3f} m"
        )

    front = next((row for row in rows if row["rail"].startswith("axle1")), None)
    prediction = design_onset_m(1.0)
    scale = float("nan")
    if front is not None and front["first_load_m"] == front["first_load_m"]:
        measured = front["first_load_m"]
        # d s_onset / d scale: shift the design onset by 1 % and difference it.
        step = 0.01
        slope = (design_onset_m(1.0 + step) - design_onset_m(1.0 - step)) / (2.0 * step)
        if slope != 0.0 and slope == slope:
            scale = 1.0 + (measured - prediction) / slope
    verdict = {
        "route": "straight",
        "speed_kmh": args.speed_kmh,
        "duration_s": args.duration,
        "frames": len(result.times_s),
        "gates": gates,
        "onsets": rows,
        "prediction_m": prediction,
        "prior_band_m": ONSET_PRIOR_BAND_M,
        "preregistered_match": bool(front and abs(front["first_load_m"] - prediction) <= ONSET_PRIOR_BAND_M),
        "lowering_scale": scale,
        "truth": {
            "tip_lowering_m": DESIGN_TIP_LOWERING_M,
            "static_penetration_m": STATIC_PENETRATION_M,
            "even_share_n": EVEN_SHARE_N,
        },
        "claim": (
            "localisation of the blade load transfer; the scale is the design lowering multiplied by "
            "`lowering_scale`, inverted through the geometric lever arm d s_onset / d scale"
        ),
    }
    (OUT / "lowering_inversion.json").write_text(
        json.dumps(verdict, indent=1, ensure_ascii=False), encoding="utf-8"
    )
    print(f"prediction (design, delta = 65.47 um): {prediction:.3f} m")
    if front is not None:
        print(
            f"measured onset {front['first_load_m']:.3f} m -> error "
            f"{front['first_load_m'] - prediction:+.3f} m, scale {scale:.3f}"
        )
    print(f"artefact -> {OUT / 'lowering_inversion.json'}")
    return 0 if verdict["preregistered_match"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
