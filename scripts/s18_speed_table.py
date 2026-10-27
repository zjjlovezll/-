"""Build the speed table for the short-wave gain, then use it section by section.

The record runs from 1.1 to 85 km/h while the operator was calibrated at one speed.  Above the axle-box
bounce frequency the response is nearly wavelength-blind, but not speed-blind: the earlier 80 vs 350 km/h
comparison moved the gain by 13.6 %, so a single number applied to a variable-speed record carries an
unknown error.  This measures the gain at the five speeds the record actually spends time at, then reports
each measured section's depth twice -- once with the single calibration speed and once with the operator
evaluated at that section's own mean speed -- so the size of the mistake is a number rather than a caveat.

Speeds are interpolated, never extrapolated: a section whose speed leaves the table reports the nearest
calibration and says so.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

import s16_operator as operator
import s17_order_tracking as tracker

SPEEDS_KMH = (40.0, 50.0, 60.0, 70.8, 80.0)
WAVELENGTH_M = 0.0275
PATCH_PERIODS = 240.0        # 6.6 m of corrugation: ~240 coherent cycles, plenty for one projection
FRONT_AXLE_M = 10.0          # axle 1 offset, so the patch starts under the leading axle
WORK = Path(r"F:\velch_tmp\speed_table")


def table() -> dict:
    """Measure the gain at each speed, caching what has already been run."""

    WORK.mkdir(parents=True, exist_ok=True)
    cache = WORK / "speed_table.json"
    rows = json.loads(cache.read_text(encoding="utf-8"))["rows"] if cache.exists() else []
    known = {float(row["speed_kmh"]) for row in rows}
    for speed in SPEEDS_KMH:
        if speed in known:
            print(f"  {speed:5.1f} km/h: cached")
            continue
        # The case starts at 30 m and the leading axle sits 10 m ahead of it, so the patch has to
        # start at 30 m and be long enough for that axle to reach and cross it: 10 m of approach
        # plus the patch itself.  Putting the patch under where I *thought* the axle was gave a
        # gain 76x too small, because no wheel ever crossed it.
        # The run starts at 30 m (the rail table's origin) and the leading axle is 10 m ahead of it,
        # so the patch begins exactly where that axle first touches rail.
        patch_start = 30.0 + FRONT_AXLE_M
        patch_length = PATCH_PERIODS * WAVELENGTH_M
        duration = (patch_length + 2.0) / (speed / 3.6)
        measurement = operator.model_gain(
            WORK / f"v{speed:05.1f}", duration_s=round(duration, 3), speed_kmh=speed,
            patch_start_m=patch_start, periods=PATCH_PERIODS,
        )
        rows.append(measurement)
        rows.sort(key=lambda row: float(row["speed_kmh"]))
        cache.write_text(json.dumps({"rows": rows}, indent=1), encoding="utf-8")
        print(f"  {speed:5.1f} km/h: gain {measurement['gain_per_m']:.4e} (m/s^2)/m, "
              f"{measurement['amplitude_m_per_s2']:.4f} m/s^2 at {measurement['frequency_hz']:.1f} Hz, "
              f"{measurement['status']}")
    return {"rows": rows}


def gain_at(speed_kmh: float, rows: list[dict]) -> tuple[float, bool, float]:
    """Interpolate the gain; return (gain, extrapolated, nearest_speed)."""

    speeds = np.array([float(row["speed_kmh"]) for row in rows])
    gains = np.array([float(row["gain_per_m"]) for row in rows])
    order = np.argsort(speeds)
    speeds, gains = speeds[order], gains[order]
    if speed_kmh <= speeds[0]:
        return float(gains[0]), bool(speed_kmh < speeds[0] - 1e-9), float(speeds[0])
    if speed_kmh >= speeds[-1]:
        return float(gains[-1]), bool(speed_kmh > speeds[-1] + 1e-9), float(speeds[-1])
    return float(np.interp(speed_kmh, speeds, gains)), False, float(speed_kmh)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=Path(r"F:\ai道岔状态反演辨识\75kmh数据"))
    parser.add_argument("--output", type=Path, default=Path(r"F:\velch_tmp\verdict\speed_table.json"))
    parser.add_argument("--single-gain", type=float, default=2.755e04)
    args = parser.parse_args(argv)

    print("measuring the operator at each speed:")
    measured = table()["rows"]
    speeds = [float(row["speed_kmh"]) for row in measured]
    gains = [float(row["gain_per_m"]) for row in measured]
    print(f"  gain spread {min(gains):.4e} .. {max(gains):.4e} "
          f"({max(gains) / min(gains) - 1.0:+.1%} across {min(speeds):.1f}-{max(speeds):.1f} km/h)")

    import s13_admission as gate
    import s10_measured_corrugation as detector

    files = sorted(args.data.glob("*.mat"))
    data = gate.load(files[0])
    position_m = gate._flat(data["Vi_pks"]) * 1000.0
    speeds_m_s = np.abs(gate._flat(data["Vi_Speed"]))
    channels = np.asarray(data["Vi_y"], dtype=float)

    sections = []
    for name, start_m, stop_m in detector.SECTIONS:
        mask = (position_m >= start_m) & (position_m <= stop_m)
        if np.count_nonzero(mask) < 1000:
            continue
        # Vi_Speed is already kilometres per hour: the record runs 1.1-85, and multiplying by 3.6
        # produced a "274 km/h" section that no railway has.
        mean_kmh = float(np.mean(speeds_m_s[mask]))
        gain, extrapolated, nearest = gain_at(mean_kmh, measured)
        section = {"section": name, "mean_speed_kmh": mean_kmh, "gain_per_m": gain,
                   "extrapolated": extrapolated, "nearest_speed_kmh": nearest, "depth_um": {}}
        for column in range(channels.shape[1]):
            grid, values = tracker.spatial_profile(position_m[mask], channels[mask, column], tracker.STEP_M)
            amplitude = tracker.coherent_at(grid, values, WAVELENGTH_M)
            section["depth_um"][f"column{column}"] = {
                "speed_matched": amplitude / gain * 1e6,
                "single_speed": amplitude / args.single_gain * 1e6,
                "amplitude_m_per_s2": amplitude,
            }
        sections.append(section)
        pair = section["depth_um"]
        print(f"  {name}: {mean_kmh:5.1f} km/h  gain {gain:.3e}  "
              + "  ".join(f"{key} {value['speed_matched']:6.1f} um (single {value['single_speed']:6.1f})"
                          for key, value in pair.items()))

    matched = [value["speed_matched"] for row in sections for value in row["depth_um"].values()]
    single = [value["single_speed"] for row in sections for value in row["depth_um"].values()]
    ratio = float(np.median(np.divide(matched, single))) if single else None
    verdict = {
        "speed_table": measured,
        "wavelength_mm": WAVELENGTH_M * 1000.0,
        "single_gain_per_m": args.single_gain,
        "sections": sections,
        "depth_speed_matched_median_um": float(np.median(matched)) if matched else None,
        "depth_single_speed_median_um": float(np.median(single)) if single else None,
        "median_ratio_matched_over_single": ratio,
        "any_extrapolated": any(row["extrapolated"] for row in sections),
        "citable": bool((not any(bool(row["extrapolated"]) for row in sections)) and bool(matched)),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(verdict, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"median depth {verdict['depth_speed_matched_median_um']:.1f} um speed-matched vs "
          f"{verdict['depth_single_speed_median_um']:.1f} um single-speed "
          f"(ratio {ratio:.2f})")
    print(f"verdict: SPEED TABLE -> {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
