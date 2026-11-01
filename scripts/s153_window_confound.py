"""Is the 16 % cross-speed gap a sampling-density artefact?  No -- measured, not argued.

Round 299 compared the same nine metres at 80 and 100 km/h and got

    80 km/h   A = 66.2 um   centre 58.514 m   p95 6.25 um
    100 km/h  A = 56.6 um   centre 58.919 m   p95 10.23 um      gap 16.11 %

with one confound left open: the two runs do not sample those nine metres equally densely.  At
5.0e-4 s output spacing the station step is 11.11 mm at 80 km/h and 13.89 mm at 100, and the
100 km/h run exists for only 0.33 s against 1.00 s, so it contributes fewer samples per metre.
A refit that prefers slightly different amplitudes depending on how coarsely the same run is
sampled would produce a difference that has nothing to do with speed.

PRE-REGISTERED BEFORE MEASURING
    H1  the 16.11 % gap is a sampling-density artefact
    falsifier   decimating the 80 km/h run to the 100 km/h density (stride 2, 13.9 mm step) or
                coarser (stride 3, 20.8 mm) moves the fitted amplitude by LESS THAN 3.0 um,
                i.e. under a fifth of the 9.6 um that has to be explained
    read        stride 1 / 2 / 3 on the 80 km/h row, same window, same law, same seeds
    verdict     H1 rejected if both strides stay inside 3.0 um; otherwise H1 is live and the
                cross-speed comparison must be redone at matched station steps

WHY 3.0 um: the gap between the two speeds is 9.6 um; sampling noise that stays under a third of
it cannot be the explanation, and 3.0 um is also under a fifth of the 22 um absolute gate, so a
sampling sensitivity of that size would be harmless to the gate anyway.

This script runs no simulation.  It is a sensitivity check on the estimator itself.
"""

from __future__ import annotations

import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

REPORT = ROOT / "reports" / "load_split_inversion_2026-10-31" / "window_confound.json"

SPEED_KMH = 80.0
STRIDES = (1, 2, 3)
STATION_STEP_MM = {1: 11.11, 2: 13.89, 3: 20.83}   # 5.0e-4 s at 80 km/h, decimated
TOLERANCE_UM = 3.0
NOTIONAL_GAP_UM = 66.2 - 56.6


def measure() -> dict:
    import s152_cross_speed as cross

    state = cross.null_state(SPEED_KMH)
    rows = {}
    for stride in STRIDES:
        run = cross.load(cross.RUNS[SPEED_KMH][0], SPEED_KMH, cross.RUNS[SPEED_KMH][2], stride=stride)
        row = cross.fit(SPEED_KMH, state, stride=stride)
        rows[stride] = {
            "samples": int(len(run["times"])),
            "station_step_mm": STATION_STEP_MM[stride],
            "amplitude_um": float(row["amplitude_um"]),
            "centre_m": float(row["centre_m"]),
            "p95_um": float(row["p95_um"]),
            "worst_bin_pct": float(row["worst_bin_pct"]),
            "usable_stations": int(row["usable_stations"]),
        }
    return rows


def verdict(rows: dict) -> dict:
    baseline = rows[1]["amplitude_um"]
    shifts = {stride: rows[stride]["amplitude_um"] - baseline for stride in STRIDES if stride != 1}
    worst = max(abs(value) for value in shifts.values())
    rejected = worst < TOLERANCE_UM
    return {
        "baseline_amplitude_um": baseline,
        "amplitude_shift_um": shifts,
        "worst_shift_um": worst,
        "tolerance_um": TOLERANCE_UM,
        "notional_gap_um": NOTIONAL_GAP_UM,
        "sampling_is_the_explanation": not rejected,
        "reason": ("decimation moves the amplitude by less than %g um, a fifth of the %.1f um gap"
                   % (TOLERANCE_UM, NOTIONAL_GAP_UM)
                   if rejected else
                   "decimation moves the amplitude by %g um or more, so the cross-speed gap may be sampling"
                   % TOLERANCE_UM),
    }


def main() -> int:
    rows = measure()
    result = verdict(rows)
    payload = {"speed_kmh": SPEED_KMH, "strides": list(STRIDES), "rows": rows, **result}

    print(f"speed {SPEED_KMH:g} km/h, same window 56-65 m, same law, same seeds")
    for stride, row in rows.items():
        print("  stride %d  samples %5d (%5.2f mm)  A %6.2f um  centre %.3f m  p95 %5.2f um  usable %d"
              % (stride, row["samples"], row["station_step_mm"], row["amplitude_um"],
                 row["centre_m"], row["p95_um"], row["usable_stations"]))
    print()
    print("amplitude shifts vs stride 1: " + ", ".join(
        "stride %d %+.2f um" % (stride, shift) for stride, shift in result["amplitude_shift_um"].items()))
    print("notional cross-speed gap %.1f um, tolerance %.1f um" % (NOTIONAL_GAP_UM, TOLERANCE_UM))
    print("VERDICT: %s -> %s" % (result["reason"],
                                 "H1 REJECTED (sampling is not the explanation)"
                                 if not result["sampling_is_the_explanation"] else "H1 LIVE"))

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"report -> {REPORT}")
    return 0 if not result["sampling_is_the_explanation"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
