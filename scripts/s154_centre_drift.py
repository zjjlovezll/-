"""Is the 0.42 m centre drift between 80 and 100 km/h a sampling-density artefact?

Round 299 compared the same nine metres (56-65 m) at two real speeds.  The engage station agreed to
3 mm (58.156 against 58.153 m) but the fitted patch centre did not: 58.514 m at 80 km/h against a value
that put the gap at 0.42 m.  Round 300 rejected sampling density for the AMPLITUDE gap; the centre was
not covered by that test, and the 100 km/h archive is short (0.33 s) with a coarser station step
(13.89 mm against 11.11 mm).

Pre-registered before measuring
    H2        the 0.42 m centre difference is sampling density (same mechanism as the amplitude gap)
    falsifier decimating either speed to a coarser step moves its own fitted centre by >= 0.10 m
              (half of the 0.20 m G-LOC gate), OR the 80-vs-100 gap collapses below 0.10 m once both
              speeds are decimated to their second step
    verdict   sampling is the explanation only if a decimation moves a centre by >= 0.10 m

Second question, same script
    H3        the centre is weakly identified at 100 km/h: the residual valley runs flat along the
              A-centre ridge, so the fit can slide the centre without paying for it
    falsifier the residual rms along centre (holding A at its optimum) rises by >= 10 % within +-0.60 m
              -- i.e. the valley is NOT flat, and the centre is identified but wrong for another reason

Nothing is re-simulated: every input is an archived run under scratch/runs/.
"""

from __future__ import annotations

import json
import pathlib

import numpy as np

SPEEDS_KMH = (80.0, 100.0)
STRIDES = (1, 2, 3)
TOLERANCE_M = 0.10
GATE_M = 0.20
RIDGE_HALF_M = 0.60
RIDGE_POINTS = 13
FLAT_RISE = 0.10
REPORT = pathlib.Path(__file__).resolve().parent.parent / "reports" / "load_split_inversion_2026-10-31" / "centre_drift.json"


def measure() -> dict:
    import s152_cross_speed as cross

    rows = {}
    for speed in SPEEDS_KMH:
        state = cross.null_state(speed)
        for stride in STRIDES:
            fit = cross.fit(speed, state, stride=stride)
            rows[f"{speed:g}@{stride}"] = {
                "speed_kmh": speed,
                "stride": stride,
                "samples": int(len(cross.load(cross.RUNS[speed][0], speed, cross.RUNS[speed][2], stride=stride)["times"])),
                "station_step_mm": 11.11 * speed / 80.0 * stride,
                "amplitude_um": float(fit["amplitude_um"]),
                "centre_m": float(fit["centre_m"]),
                "p95_um": float(fit["p95_um"]),
                "usable_stations": int(fit["usable_stations"]),
                "worst_bin_pct": float(fit["worst_bin_pct"]),
            }
    return rows


def ridge(speed_kmh: float, stride: int) -> dict:
    """Residual rms along centre, with the amplitude held at its fitted optimum."""
    import s152_cross_speed as cross

    from s113_profile_inversion import _smooth, _split

    import s123_m7_assembly as assembly
    import s124_joint_inversion as joint

    import s119_width_aware_inversion as law

    state = cross.null_state(speed_kmh)
    fit = cross.fit(speed_kmh, state, stride=stride)
    route = cross.RUNS[speed_kmh][1]
    run = cross.load(route, speed_kmh, cross.RUNS[speed_kmh][2], stride)
    stations = run["station"]
    observed = _smooth(_split(run), stations, 0.20)
    u0 = np.interp(stations, state["station"], state["u0"], left=np.nan, right=np.nan)
    sigma_of = joint.share_law(assembly.build_law())
    widths = law._width_at(stations, *law._width_table())
    usable = ((stations >= cross.FIT_LO_M) & (stations <= cross.FIT_HI_M)
              & np.isfinite(observed) & np.isfinite(u0)
              & (observed >= cross.SHARE_LO) & (observed <= 1.0))
    amplitude = float(fit["amplitude_um"])
    centre = float(fit["centre_m"])

    profile = []
    for shift in np.linspace(-RIDGE_HALF_M, RIDGE_HALF_M, RIDGE_POINTS):
        truth = amplitude * np.exp(-0.5 * ((stations[usable] - (centre + shift)) / cross.WIDTH_M) ** 2)
        residual = sigma_of(u0[usable] + truth, widths[usable]) - observed[usable]
        profile.append({"shift_m": float(shift), "rms_um": float(np.sqrt(np.mean(residual ** 2)))})

    base = next(point["rms_um"] for point in profile if abs(point["shift_m"]) < 1e-9)
    rise = max(point["rms_um"] for point in profile) / base - 1.0
    return {
        "speed_kmh": speed_kmh,
        "stride": stride,
        "centre_m": centre,
        "amplitude_um": amplitude,
        "profile": profile,
        "peak_rise": float(rise),
        "valley_is_flat": bool(rise < FLAT_RISE),
    }


def verdict(rows: dict) -> dict:
    per_speed = {}
    for speed in SPEEDS_KMH:
        centres = {stride: rows[f"{speed:g}@{stride}"]["centre_m"] for stride in STRIDES}
        moves = {stride: centres[stride] - centres[1] for stride in STRIDES if stride != 1}
        per_speed[f"{speed:g}"] = {
            "centre_m": centres,
            "move_m": moves,
            "worst_move_m": float(max(abs(value) for value in moves.values())),
        }
    gap_s1 = rows["100@1"]["centre_m"] - rows["80@1"]["centre_m"]
    gaps = {stride: rows[f"100@{stride}"]["centre_m"] - rows[f"80@{stride}"]["centre_m"] for stride in STRIDES}
    worst_move = max(entry["worst_move_m"] for entry in per_speed.values())
    sampling_is_the_explanation = bool(worst_move >= TOLERANCE_M or abs(min(gaps.values(), key=abs)) < TOLERANCE_M)
    return {
        "per_speed": per_speed,
        "gap_at_stride_1_m": float(gap_s1),
        "gap_by_stride_m": {str(stride): float(value) for stride, value in gaps.items()},
        "worst_decimation_move_m": float(worst_move),
        "tolerance_m": TOLERANCE_M,
        "sampling_is_the_explanation": sampling_is_the_explanation,
        "gate_m": GATE_M,
        "gap_exceeds_gate": bool(abs(gap_s1) > GATE_M),
    }


def main() -> int:
    rows = measure()
    print(f"{'key':>8} {'step mm':>8} {'n':>5} {'A um':>7} {'centre m':>9} {'p95 um':>7} {'usable':>7} {'bin %':>7}")
    for key, row in rows.items():
        print(f"{key:>8} {row['station_step_mm']:8.2f} {row['samples']:5d} "
              f"{row['amplitude_um']:7.2f} {row['centre_m']:9.3f} {row['p95_um']:7.2f} "
              f"{row['usable_stations']:7d} {row['worst_bin_pct']:7.2f}")

    result = verdict(rows)
    print()
    for speed, entry in result["per_speed"].items():
        moves = ", ".join(f"stride {stride}: {value:+.3f} m" for stride, value in entry["move_m"].items())
        print(f"{speed} km/h centre moves: {moves}   worst {entry['worst_move_m']:.3f} m")
    print(f"80-vs-100 centre gap: {result['gap_at_stride_1_m']:+.3f} m   by stride: "
          + ", ".join(f"{stride}: {value:+.3f}" for stride, value in result["gap_by_stride_m"].items()))
    print(f"tolerance {TOLERANCE_M:.2f} m (half the {GATE_M:.2f} m gate), gate exceeded: {result['gap_exceeds_gate']}")

    ridges = {}
    for speed in SPEEDS_KMH:
        for stride in (1, 2):
            entry = ridge(speed, stride)
            ridges[f"{speed:g}@{stride}"] = entry
            print(f"ridge {speed:g} km/h stride {stride}: peak rise {entry['peak_rise'] * 100:5.1f} % "
                  f"-> valley {'FLAT' if entry['valley_is_flat'] else 'SHARP'}")

    if not result["sampling_is_the_explanation"]:
        print("\nVERDICT: decimation does not move a centre by 0.10 m and the gap survives matched sampling")
        print("         -> H2 REJECTED (sampling is not the explanation for the centre drift)")
    else:
        print("\nVERDICT: sampling explains the centre drift")
        print("         -> H2 STANDS (the cross-speed centre comparison needs matched sampling)")

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps({"rows": rows, "verdict": result, "ridges": ridges,
                                  "tolerance_m": TOLERANCE_M, "flat_rise": FLAT_RISE}, indent=2),
                      encoding="utf-8")
    print(f"report -> {REPORT}")
    return 0 if not result["sampling_is_the_explanation"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
