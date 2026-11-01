"""Compute the reference station a load-split law predicts for a given blade share.

WHY THIS EXISTS
===============
Round 303 measured the physical engagement column: the blade's share of the axle load first passes 5 %
at 58.156 m (80 km/h) and 58.153 m (100 km/h), while the geometry crosses "within one static
penetration" at 57.733 m and reaches flush at 58.423 m.  That left the physical location gate
suspended, because the 0.42 m is *between* two calibrated geometric stations and nothing said where in
that interval a 5 % share ought to fall.  This script supplies that missing reference by an independent
route: the two-spring load split of the blade and stock, driven by the crown gap of the case's own
station table and by the frozen contact stiffness.

PRE-REGISTERED BEFORE MEASURING (do not edit after seeing the numbers)
=====================================================================
H4  : the 5 % engage station is what a parallel-Hertz split of the *crown gap* predicts.
      Falsifier: |s_law(5 %) - s_model(5 %)| >= 0.10 m (half of the 0.20 m physical gate).
Shape claim: the same law reproduces the measured share curve -> correlation >= 0.99 and rms share
      difference <= 0.05.
Diagnostic: the geometry must independently reproduce the calibrated touch station (57.733 m) to
      within 0.02 m, or the crown gap is not the quantity the solver sees and the whole comparison is
      void.

THE LAW
=======
One wheel, two surfaces, equal contact stiffness C from the frozen oracle:
    N_s = C d_s^1.5,  N_b = C max(d_s - g, 0)^1.5,  N_s + N_b = W
with g the crown gap (stock crown minus blade crown, positive when the blade is lower).  W is the
per-wheel weight of this case (481 078.5 N over eight contacts).  The share is N_b / W.  Nothing is
fitted here: C comes from 59 680.5769 N at 65.4661 um, W from the case's own mass.

WHAT IT ALREADY CANNOT DO (state it, do not paper over it)
========================================================
Equal stiffness is an idealisation.  The blade and stock crowns sit at different lateral positions, so
the wheel meets the blade at a different rolling-circle offset than it meets the stock; the effective
gap at the contact point is therefore *not* the crown gap.  If the law fails, that difference is the
measured residual, not an excuse.
"""

from __future__ import annotations

import json
import pathlib
import sys

import numpy as np

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))

CASE = ROOT.parent / "scratch" / "s146" / "one_set_x46.json"
REPORT = ROOT / "reports" / "load_split_inversion_2026-10-31" / "engage_reference.json"

FROZEN_FORCE_N = 59_680.57685863
FROZEN_DEPTH_M = 65.4661e-6
CASE_WEIGHT_N = 481_078.5
CONTACTS = 8

SHARE_TARGET = 0.05
TOLERANCE_M = 0.10
GEOMETRY_TOLERANCE_M = 0.02
CALIBRATED_TOUCH_M = 57.733
MODEL_SHARE_STATION_M = {80.0: 58.156, 100.0: 58.153}
SHAPE_STATIONS_M = (57.4, 59.2)

SPEED_KMH = 80.0


def stiffness_n_m_1p5() -> float:
    """Contact stiffness implied by the frozen oracle, unchanged from the archive."""
    return FROZEN_FORCE_N / FROZEN_DEPTH_M ** 1.5


def wheel_load_n() -> float:
    """Per-wheel weight of the case the runs were made from."""
    return CASE_WEIGHT_N / CONTACTS


def blade_penetration(gap_m: float, stiffness: float, load_n: float) -> tuple[float, float]:
    """Return (stock penetration, blade share) for a crown gap at one wheel."""
    low, high = max(0.0, gap_m), 1.0e-3
    for _ in range(200):
        mid = 0.5 * (low + high)
        total = stiffness * mid ** 1.5 + stiffness * max(mid - gap_m, 0.0) ** 1.5
        if total < load_n:
            low = mid
        else:
            high = mid
    depth = 0.5 * (low + high)
    blade = stiffness * max(depth - gap_m, 0.0) ** 1.5
    return depth, blade / load_n


def share_of(gap_m: float) -> float:
    return blade_penetration(gap_m, stiffness_n_m_1p5(), wheel_load_n())[1]


def gap_for_share(target: float) -> float:
    """Invert the law: the crown gap at which the blade carries ``target`` of the load."""
    low, high = 0.0, FROZEN_DEPTH_M * 4.0
    for _ in range(200):
        mid = 0.5 * (low + high)
        value = share_of(mid)
        if value > target:
            low = mid
        else:
            high = mid
    return 0.5 * (low + high)


def crown_gaps() -> dict:
    """Crown gap against mileage, read from the case's own station table."""
    from velch.vehicle import load_vehicle_case

    case = load_vehicle_case(CASE)
    rail = [r for r in case.rails if r.id == "axle1_right"][0]
    bodies = {b.id: b for b in rail.bodies}
    stock, blade = bodies["stock"], bodies["blade"]
    stations = np.arange(56.5, 60.0001, 0.05)
    gaps = []
    for station in stations:
        crown_stock = float(np.nanmax(np.asarray(stock.series.sample(float(station), 1.0).profile.z_m, float)))
        crown_blade = float(np.nanmax(np.asarray(blade.series.sample(float(station), 1.0).profile.z_m, float)))
        gaps.append(crown_stock - crown_blade)
    return {"stations": stations, "gaps": np.asarray(gaps)}


def station_where(table: dict, gap_m: float) -> float:
    stations, gaps = table["stations"], table["gaps"]
    order = np.argsort(gaps)
    return float(np.interp(gap_m, gaps[order], stations[order]))


def measured_share(speed_kmh: float) -> tuple[np.ndarray, np.ndarray]:
    """Blade share against station on the null route, the same series round 303 reported."""
    import s152_cross_speed as cross

    from s113_profile_inversion import _smooth, _split

    run = cross.load(cross.RUNS[speed_kmh][0], speed_kmh, cross.RUNS[speed_kmh][2])
    return run["station"], _smooth(_split(run), run["station"], 0.20)


def engage_station(stations: np.ndarray, share: np.ndarray, threshold: float) -> float | None:
    hit = np.nonzero(np.isfinite(share) & (share >= threshold))[0]
    return float(stations[hit[0]]) if hit.size else None


def shape_agreement(table: dict, speed_kmh: float) -> dict:
    stations, share = measured_share(speed_kmh)
    low, high = SHAPE_STATIONS_M
    keep = np.isfinite(share) & (stations > low) & (stations < high)
    predicted = np.array([share_of(gap) for gap in np.interp(stations[keep], table["stations"], table["gaps"])])
    observed = share[keep]
    return {
        "samples": int(keep.sum()),
        "correlation": float(np.corrcoef(predicted, observed)[0, 1]),
        "rms_share": float(np.sqrt(np.mean((predicted - observed) ** 2))),
    }


def measure() -> dict:
    table = crown_gaps()
    stiffness = stiffness_n_m_1p5()
    load = wheel_load_n()
    depth0, _ = blade_penetration(0.0, stiffness, load)

    gap_touch = FROZEN_DEPTH_M
    gap_target = gap_for_share(SHARE_TARGET)
    s_touch_geometry = station_where(table, gap_touch)
    s_law = station_where(table, gap_target)

    stations, share = measured_share(SPEED_KMH)
    s_model = engage_station(stations, share, SHARE_TARGET)
    crown_at_model = float(np.interp(s_model, table["stations"], table["gaps"])) if s_model else float("nan")

    offset = abs(s_law - s_model) if s_model else float("inf")
    excess = gap_target - crown_at_model
    shape = shape_agreement(table, SPEED_KMH)
    return {
        "stiffness_n_m_1p5": stiffness,
        "wheel_load_n": load,
        "seated_depth_um": depth0 * 1e6,
        "share_at_zero_gap": share_of(0.0),
        "gap_for_5pct_um": gap_target * 1e6,
        "touch_gap_um": FROZEN_DEPTH_M * 1e6,
        "touch_station_geometry_m": s_touch_geometry,
        "touch_station_calibrated_m": CALIBRATED_TOUCH_M,
        "touch_mismatch_m": abs(s_touch_geometry - CALIBRATED_TOUCH_M),
        "station_law_5pct_m": s_law,
        "station_model_5pct_m": s_model,
        "station_offset_m": offset,
        "crown_gap_at_model_um": crown_at_model * 1e6,
        "effective_gap_excess_um": excess * 1e6,
        "shape": shape,
        "tolerance_m": TOLERANCE_M,
        "geometry_tolerance_m": GEOMETRY_TOLERANCE_M,
    }


def verdict(row: dict) -> dict:
    """Apply the pre-registered readings; no threshold may move after this point."""
    geometry_ok = row["touch_mismatch_m"] <= GEOMETRY_TOLERANCE_M
    offset_ok = row["station_offset_m"] < TOLERANCE_M
    shape_ok = row["shape"]["correlation"] >= 0.99 and row["shape"]["rms_share"] <= 0.05
    if not geometry_ok:
        reason = (
            "the crown gap does not even reproduce the calibrated touch station, so it is not the "
            f"quantity the solver sees ({row['touch_mismatch_m']:.3f} m off)"
        )
    elif offset_ok and shape_ok:
        reason = "the parallel split of the crown gap reproduces both the level and the shape"
    else:
        parts = []
        if not offset_ok:
            parts.append(f"the law puts 5 % at {row['station_law_5pct_m']:.3f} m against the measured "
                         f"{row['station_model_5pct_m']:.3f} m ({row['station_offset_m']:.3f} m apart)")
        if not shape_ok:
            parts.append(f"the share curves differ by rms {row['shape']['rms_share']:.3f} at "
                         f"correlation {row['shape']['correlation']:.3f}")
        reason = "; ".join(parts) + (
            f"; the model needs an effective gap {row['effective_gap_excess_um']:.1f} um wider than the "
            "crown gap, so the reference station must come from the contact geometry, not the crowns"
        )
    return {
        "geometry_reproduces_touch": geometry_ok,
        "offset_within_tolerance": offset_ok,
        "shape_within_tolerance": shape_ok,
        "crown_gap_split_sufficient": bool(geometry_ok and offset_ok and shape_ok),
        "reason": reason,
    }


def main() -> int:
    row = measure()
    result = verdict(row)
    row["verdict"] = result
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(row, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(f"stiffness from the frozen oracle {row['stiffness_n_m_1p5']:.4e} N/m^1.5, "
          f"wheel load {row['wheel_load_n']:.1f} N -> seated depth {row['seated_depth_um']:.2f} um")
    print(f"share at zero gap {row['share_at_zero_gap']*100:.1f} % (the law is symmetric there)")
    print(f"touch   : crown gap {row['touch_gap_um']:.2f} um at {row['touch_station_geometry_m']:.3f} m "
          f"(calibrated {row['touch_station_calibrated_m']:.3f} m, off {row['touch_mismatch_m']:.3f} m)")
    print(f"5 %     : crown gap {row['gap_for_5pct_um']:.2f} um at {row['station_law_5pct_m']:.3f} m "
          f"(law) against {row['station_model_5pct_m']:.3f} m (model) -> {row['station_offset_m']:.3f} m")
    print(f"crown gap where the model engages: {row['crown_gap_at_model_um']:.2f} um "
          f"-> the model reports {row['effective_gap_excess_um']:.1f} um more gap than the crowns give")
    print(f"shape   : rms share difference {row['shape']['rms_share']:.3f} at correlation "
          f"{row['shape']['correlation']:.3f} over {row['shape']['samples']} samples")
    print(f"VERDICT : {'crown-gap split SUFFICIENT' if result['crown_gap_split_sufficient'] else 'CROWN-GAP SPLIT NOT SUFFICIENT'}")
    print(f"          {result['reason']}")
    print(f"report -> {REPORT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
