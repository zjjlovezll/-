"""Measure the gap the wheel actually sees: per-body penetrations at ten stations.

WHY THIS EXISTS
===============
Round 304 showed that the crown gap is the right abscissa for "do the blade and the wheel touch" -- it
reproduces the calibrated touch station to 0.000 m -- and the wrong one for "how much load": a two-spring
split of the crown gap puts 5 % at 57.853 m while the model reports 58.156 m, and at the model's station
the crowns are only 26.45 um apart where the law needs 54.66 um.  The stated mechanism was that the blade
crest sits inboard of the stock crest, so the wheel meets the blade below its crest and sees more
clearance.  That mechanism has not been measured.  This script measures it.

THE MEASUREMENT
===============
Seat the whole case at each station and read the individual bodies' contact geometry.  The depth a body
is indented is measured from the rigid wheel surface, so for two bodies under the same wheel

    d_eff = penetration(stock) - penetration(blade)

is exactly the height difference between the two surfaces **at their own contact points** -- which is the
quantity a load split needs.  The crown gap is the same difference at the two crests.  Everything else
(the lateral positions ``y`` of the two contacts, the forces, the share) is read from the same evaluate
call, so no series is re-interpolated.

PRE-REGISTERED BEFORE MEASURING (do not edit after seeing the numbers)
======================================================================
H5  crown-gap-is-effective-gap : |d_eff - g_crown| <= 10 um at every station.
H6  two-spring closure         : share(predicted from d_eff) within 2.0 percentage points of share(seated)
                                 at every station.
H7  reference station          : interpolating d_eff(s), the station where it equals the 5 % gap
                                 (54.66 um) matches the measured engage(5 %) within 0.10 m.

H5 is expected to FAIL -- that is the mechanism claim -- and H6/H7 are what decide whether the split law
survives with the correct abscissa.  A failure of H6 would mean the split is not a two-spring problem at
all; a failure of H7 would mean the seat's equilibrium gap does not order the stations the way the time
series does.

SCALE
=====
A seat costs 2-120 s depending on whether the blade is inside the search window, so the ten stations are
run in one go and cached in the report.  Spin is set to 80 km/h / 0.43 m to match the run the 5 % station
came from; the vertical seat itself is speed independent.
"""

from __future__ import annotations

import json
import pathlib
import sys

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

CASE = ROOT.parent / "scratch" / "s146" / "one_set_x46.json"
SCRATCH = ROOT.parent / "scratch" / "s158"
REPORT = ROOT / "reports" / "load_split_inversion_2026-10-31" / "effective_gap.json"

RAIL = "axle1_right"
AXLE_OFFSET_M = 10.0
SPEED_KMH = 80.0
ROLL_RADIUS_M = 0.43
STATIONS_M = tuple(57.4 + 0.2 * index for index in range(10))
# The crossing of the 5 % gap sits inside one 0.2 m cell, so the coarse sweep can only bracket it.
# The refinement below is pre-registered for exactly that reason: the reported station must be
# determined by two measured neighbours at 0.05 m, not by interpolating across 0.2 m.
REFINE_M = tuple(58.025 + 0.05 * index for index in range(4))

FROZEN_FORCE_N = 59_680.57685863
FROZEN_DEPTH_M = 65.4661e-6
CASE_WEIGHT_N = 481_078.5
CONTACTS = 8
SHARE_TARGET = 0.05

CROWN_TOLERANCE_M = 10e-6
CLOSURE_TOLERANCE = 0.02
STATION_TOLERANCE_M = 0.10
MEASURED_ENGAGE_5PCT_M = 58.156


def stiffness() -> float:
    return FROZEN_FORCE_N / FROZEN_DEPTH_M ** 1.5


def wheel_load() -> float:
    return CASE_WEIGHT_N / CONTACTS


def share_of_gap(gap_m: float) -> float:
    """Two-spring share for a given effective gap, same law as round 304."""
    stiff, load = stiffness(), wheel_load()
    low, high = max(0.0, gap_m), 1.0e-3
    for _ in range(200):
        mid = 0.5 * (low + high)
        total = stiff * mid ** 1.5 + stiff * max(mid - gap_m, 0.0) ** 1.5
        if total < load:
            low = mid
        else:
            high = mid
    depth = 0.5 * (low + high)
    return stiff * max(depth - gap_m, 0.0) ** 1.5 / load


def gap_for_share(target: float) -> float:
    low, high = 0.0, FROZEN_DEPTH_M * 4.0
    for _ in range(200):
        mid = 0.5 * (low + high)
        if share_of_gap(mid) > target:
            low = mid
        else:
            high = mid
    return 0.5 * (low + high)


def crown_gap(station_m: float) -> float:
    """Stock crest minus blade crest, from the case's own station table."""
    from velch.vehicle import load_vehicle_case

    if not hasattr(crown_gap, "_case"):
        crown_gap._case = load_vehicle_case(CASE)  # type: ignore[attr-defined]
    case = crown_gap._case  # type: ignore[attr-defined]
    rail = next(item for item in case.rails if item.id == RAIL)
    bodies = {str(body.id).split(":")[-1]: body for body in rail.bodies}
    stock = float(np.nanmax(np.asarray(bodies["stock"].series.sample(station_m, 1.0).profile.z_m, float)))
    blade = float(np.nanmax(np.asarray(bodies["blade"].series.sample(station_m, 1.0).profile.z_m, float)))
    return stock - blade


def seat_at(station_m: float) -> dict:
    """Seat the whole case with the front axle at ``station_m`` and read the two bodies under it."""
    from velch.vehicle import load_vehicle_case
    from velch.vehicle_solver import VehicleDynamics, _seat

    SCRATCH.mkdir(parents=True, exist_ok=True)
    base = json.loads(CASE.read_text(encoding="utf-8"))
    base["run"]["x_start_m"] = station_m - AXLE_OFFSET_M
    if "seat_x_start_m" in base["run"]:
        base["run"]["seat_x_start_m"] = station_m - AXLE_OFFSET_M
    variant = SCRATCH / f"seat_{station_m:06.2f}.json"
    variant.write_text(json.dumps(base), encoding="utf-8")

    case = load_vehicle_case(variant)
    dynamics = VehicleDynamics(case)
    q = np.asarray(case.initial_q, dtype=float)
    v = np.asarray(case.initial_v, dtype=float)
    v[dynamics.topology.require("wheelset1", "spin")] = SPEED_KMH / 3.6 / ROLL_RADIUS_M
    q, residual = _seat(case, dynamics, q, v)
    _, _contacts = dynamics.evaluate(0.0, q, v)

    rows = {}
    for body_id, response in zip(dynamics.body_ids[RAIL], dynamics.body_contacts[RAIL]):
        geometry = response.geometry
        rows[str(body_id).split(":")[-1]] = {
            "force_n": float(response.normal_force_n) if (response.active and geometry is not None) else 0.0,
            "penetration_m": float(geometry.penetration_m) if geometry is not None else 0.0,
            "hertz_penetration_m": float(response.hertz_penetration_m) if geometry is not None else 0.0,
            "y_m": float(geometry.y_m) if geometry is not None else float("nan"),
            "half_width_m": float(geometry.half_width_m) if geometry is not None else float("nan"),
            "active": bool(response.active and geometry is not None),
        }
    stock, blade = rows.get("stock", {}), rows.get("blade", {})
    total = stock.get("force_n", 0.0) + blade.get("force_n", 0.0)
    return {
        "residual_n": float(residual),
        "stock": stock,
        "blade": blade,
        "share_measured": blade.get("force_n", 0.0) / total if total > 0 else float("nan"),
        "total_n": total,
    }


def measure(stations: tuple = STATIONS_M) -> dict:
    rows = []
    for station in stations:
        seat = seat_at(station)
        gap_crown = crown_gap(station)
        depth_stock = seat["stock"].get("penetration_m", 0.0)
        depth_blade = seat["blade"].get("penetration_m", 0.0)
        effective = depth_stock - depth_blade
        rows.append({
            "station_m": station,
            "crown_gap_m": gap_crown,
            "effective_gap_m": effective,
            "difference_m": effective - gap_crown,
            "depth_stock_m": depth_stock,
            "depth_blade_m": depth_blade,
            "y_stock_m": seat["stock"].get("y_m"),
            "y_blade_m": seat["blade"].get("y_m"),
            "share_measured": seat["share_measured"],
            "share_law_effective": share_of_gap(effective),
            "share_law_crown": share_of_gap(gap_crown),
            "blade_force_n": seat["blade"].get("force_n", 0.0),
            "total_n": seat["total_n"],
            "residual_n": seat["residual_n"],
        })
    return {"stations": rows, "target_gap_m": gap_for_share(SHARE_TARGET)}


def crossings(rows: list, gap_m: float) -> list:
    """Stations where the effective gap passes ``gap_m``, walking the sweep in station order.

    Round 305 first version sorted the gaps before interpolating.  That is fine for a monotone series and
    silently wrong for this one: the effective gap is not monotone along the switch (the wheel's lateral
    registration moves with the station as well as the gap does), and sorting the abscissa produced a
    crossing at 57.987 m -- outside the station interval that actually contains it.  The walk below only
    ever interpolates between consecutive stations, and reports every crossing so an ambiguous abscissa
    cannot masquerade as a single answer.
    """
    stations = [row["station_m"] for row in rows]
    gaps = [row["effective_gap_m"] for row in rows]
    found = []
    for index in range(len(rows) - 1):
        low, high = gaps[index], gaps[index + 1]
        if low == high:
            continue
        if (low - gap_m) * (high - gap_m) <= 0.0:
            station = stations[index] + (stations[index + 1] - stations[index]) * (low - gap_m) / (low - high)
            found.append(float(station))
    return found


def non_monotone_pairs(rows: list) -> list:
    """Consecutive station pairs where the effective gap grows, i.e. where the abscissa loses its order."""
    gaps = [row["effective_gap_m"] for row in rows]
    return [
        {"from_m": rows[index]["station_m"], "to_m": rows[index + 1]["station_m"],
         "change_um": (gaps[index + 1] - gaps[index]) * 1e6}
        for index in range(len(rows) - 1)
        if gaps[index + 1] > gaps[index]
    ]


def verdict(data: dict) -> dict:
    rows = data["stations"]
    differences = np.array([row["difference_m"] for row in rows])
    worst_crown = float(np.max(np.abs(differences)))
    closure_effective = np.abs(np.array([row["share_measured"] - row["share_law_effective"] for row in rows]))
    closure_crown = np.abs(np.array([row["share_measured"] - row["share_law_crown"] for row in rows]))
    finite_eff = closure_effective[np.isfinite(closure_effective)]
    finite_crown = closure_crown[np.isfinite(closure_crown)]
    found = crossings(rows, data["target_gap_m"])
    station = found[0] if found else None
    station_error = None if station is None else abs(station - MEASURED_ENGAGE_5PCT_M)
    unique = len(found) == 1
    return {
        "worst_crown_minus_effective_um": worst_crown * 1e6,
        "H5_crown_is_effective": bool(worst_crown <= CROWN_TOLERANCE_M),
        "closure_effective_max_fraction": float(np.max(finite_eff)) if finite_eff.size else None,
        "closure_crown_max_fraction": float(np.max(finite_crown)) if finite_crown.size else None,
        "H6_two_spring_closure": bool(finite_eff.size and float(np.max(finite_eff)) <= CLOSURE_TOLERANCE),
        "crossings_m": found,
        "crossing_count": len(found),
        "non_monotone_pairs": non_monotone_pairs(rows),
        "station_from_effective_m": station,
        "station_error_m": station_error,
        "H7_reference_station": bool(unique and station_error is not None and station_error <= STATION_TOLERANCE_M),
        "measured_engage_5pct_m": MEASURED_ENGAGE_5PCT_M,
        "target_gap_um": data["target_gap_m"] * 1e6,
    }


def reports(stations: list, target_gap: float) -> dict:
    data = {"stations": stations, "target_gap_m": target_gap}
    return {"stations": stations, "verdict": verdict(data),
            "constants": {"stiffness": stiffness(), "wheel_load_n": wheel_load(),
                          "target_gap_m": target_gap}}


def main(argv: list | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if "--reuse" in argv:
        previous = json.loads(REPORT.read_text(encoding="utf-8"))
        payload = reports(previous["stations"], previous["constants"]["target_gap_m"])
    elif "--refine" in argv:
        previous = json.loads(REPORT.read_text(encoding="utf-8"))
        added = measure(REFINE_M)["stations"]
        merged = {round(row["station_m"], 4): row for row in previous["stations"]}
        merged.update({round(row["station_m"], 4): row for row in added})
        stations = [merged[key] for key in sorted(merged)]
        payload = reports(stations, previous["constants"]["target_gap_m"])
    else:
        measured = measure()
        payload = reports(measured["stations"], measured["target_gap_m"])
    result = payload["verdict"]
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(payload, indent=2, sort_keys=True) + chr(10), encoding="utf-8")

    print(f"{'station':>8} {'crown um':>9} {'eff um':>8} {'diff um':>8} {'y_s mm':>9} {'y_b mm':>9} "
          f"{'share':>7} {'law(eff)':>9} {'law(crown)':>11}")
    for row in payload["stations"]:
        yb = row["y_blade_m"]
        print(f"{row['station_m']:8.2f} {row['crown_gap_m']*1e6:9.2f} {row['effective_gap_m']*1e6:8.2f} "
              f"{row['difference_m']*1e6:+8.2f} {row['y_stock_m']*1e3:9.3f} "
              f"{'nan' if yb is None or yb != yb else format(yb*1e3, '9.3f')} "
              f"{row['share_measured']*100:6.2f}% {row['share_law_effective']*100:8.2f}% "
              f"{row['share_law_crown']*100:10.2f}%")
    print()
    print(f"target gap for 5 % share      {result['target_gap_um']:.2f} um")
    print(f"worst |crown - effective|    {result['worst_crown_minus_effective_um']:.2f} um "
          f"-> H5 {'PASS' if result['H5_crown_is_effective'] else 'FAIL'}")
    print(f"closure with effective gap   max {result['closure_effective_max_fraction']*100:.1f} pp "
          f"-> H6 {'PASS' if result['H6_two_spring_closure'] else 'FAIL'}")
    print(f"closure with crown gap       max {result['closure_crown_max_fraction']*100:.1f} pp")
    print(f"crossings of the 5 % gap     {[round(item, 3) for item in result['crossings_m']]} "
          f"(count {result['crossing_count']})")
    print(f"non-monotone consecutive pairs {len(result['non_monotone_pairs'])}")
    if result["station_from_effective_m"] is not None:
        print(f"station where effective gap = 5 % gap  {result['station_from_effective_m']:.3f} m "
              f"against measured {MEASURED_ENGAGE_5PCT_M:.3f} m "
              f"({result['station_error_m']:.3f} m) -> H7 "
              f"{'PASS' if result['H7_reference_station'] else 'FAIL'}")
    print(f"report -> {REPORT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
