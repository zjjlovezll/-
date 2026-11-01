"""One page: the four pre-registered gates per speed, plus the physical location column beside them.

The window is fixed in metres (56.0-65.0 m of front-axle travel) so every speed sees the same stations:
the ramp, the first touch near 57.7 m, and the flush region.  Only the clock differs, which is why the
durations differ too (60 km/h 0.54 s, 80 km/h 0.41 s, 100 km/h 0.33 s).

Two location quantities are reported and they are NOT interchangeable:

    synthetic G-LOC   |fitted centre - 58.5 m| <= 0.20 m     -- the reconstruction gate, against the
                                                                injected truth z = 60 um exp(-...)
    physical engage   first station where the blade carries 5 % of the load, against 57.733 m, the
                      station where the drawn sections put the blade within one static penetration
                      (65.4661 um) of the stock rail.  This is a measurement, not a fit, and its
                      reference comes from scripts/s110_lowering_readings.py (recomputed there, quoted
                      here so the two cannot drift apart silently).

Round 302 showed the synthetic centre is weakly identified at 100 km/h, so its G-LOC failure is expected
and explained; the physical column is what keeps the location claim honest, and the threshold scan below
says how much of the physical offset is the detection threshold rather than geometry.

Pre-registered gates, unchanged from s152 (no threshold is edited here):
    G-ABS  p95 |z_hat - z| <= 22 um            G-REL  worst 2 mm bin <= 2 % (truth >= 50 um)
    G-LOC  |centre - 58.5| <= 0.20 m           G-AMP  |A_hat - 60| / 60 <= 2 %
"""

from __future__ import annotations

import json
import pathlib

import numpy as np

SPEEDS_KMH = (60.0, 80.0, 100.0)
THRESHOLDS = (0.01, 0.02, 0.05, 0.10)
GEOMETRY_TOUCH_M = 57.733
GEOMETRY_SOURCE = "scripts/s110_lowering_readings.py (blade within one static penetration of the stock)"
LIMITS = {"G-ABS": 22.0, "G-REL": 2.0, "G-LOC": 0.20, "G-AMP": 2.0}
REPORT = pathlib.Path(__file__).resolve().parent.parent / "reports" / "load_split_inversion_2026-10-31" / "gate_page.json"


def _archived(speed_kmh: float) -> bool:
    import s152_cross_speed as cross

    import s113_profile_inversion as base

    route = cross.RUNS[speed_kmh][0]
    duration = cross.RUNS[speed_kmh][2]
    rows = [row for row in base._index_rows()
            if row.get("route") == route and abs(float(row.get("speed_kmh", -1)) - speed_kmh) < 1e-6
            and abs(float(row.get("duration_s", -1)) - duration) < 1e-9]
    return bool(rows)


def _route_archived(route: str, speed_kmh: float) -> bool:
    """Is there an archived run for exactly this route?  The bump route must exist for its own scan."""
    import s113_profile_inversion as base

    duration = _duration(speed_kmh)
    return any(
        row.get("route") == route
        and abs(float(row.get("speed_kmh", -1)) - speed_kmh) < 1e-6
        and abs(float(row.get("duration_s", -1)) - duration) < 1e-9
        for row in base._index_rows()
    )


def _duration(speed_kmh: float) -> float:
    import s152_cross_speed as cross

    return float(cross.RUNS[speed_kmh][2])


def engage_scan(speed_kmh: float, which: str = "null") -> dict:
    """First station where the blade carries more than each threshold share, on one of the two routes.

    ``which`` matters: the null route is the geometry the truth reference describes, the bump route adds
    the injected lowering and therefore moves the engagement earlier on its own.  Mixing the two would
    credit the model with a shift the bump caused, so both are reported and only the null one is compared
    with the geometry reference.
    """
    import s152_cross_speed as cross

    from s113_profile_inversion import _smooth, _split

    index = 0 if which == "null" else 1
    route = cross.RUNS[speed_kmh][index]
    if not _route_archived(route, speed_kmh):
        # A missing archive is not a measurement: report the cell as unavailable instead of raising,
        # so the other columns of that speed can still be read (round 304).
        return {
            "available": False,
            "reason": f"no archived run for route {route!r} at {speed_kmh:g} km/h",
            "by_threshold": {f"{threshold:.2f}": None for threshold in THRESHOLDS},
            "share_max": None,
            "samples": 0,
        }
    run = cross.load(route, speed_kmh, cross.RUNS[speed_kmh][2])
    share = _smooth(_split(run), run["station"], 0.20)
    stations = run["station"]
    scan = {}
    for threshold in THRESHOLDS:
        hit = np.nonzero(np.isfinite(share) & (share >= threshold))[0]
        scan[f"{threshold:.2f}"] = float(stations[hit[0]]) if hit.size else None
    return {"by_threshold": scan, "share_max": float(np.nanmax(share)), "samples": int(len(stations))}


def gates(speed_kmh: float) -> dict:
    import s152_cross_speed as cross

    state = cross.null_state(speed_kmh)
    fit = cross.fit(speed_kmh, state)
    values = {
        "G-ABS": float(fit["p95_um"]),
        "G-REL": float(fit["worst_bin_pct"]),
        "G-LOC": abs(float(fit["centre_m"]) - cross.CENTRE_M),
        "G-AMP": abs(float(fit["amplitude_um"]) - cross.TRUTH_AMPLITUDE_UM) / cross.TRUTH_AMPLITUDE_UM * 100.0,
    }
    passed = {key: bool(values[key] <= LIMITS[key]) for key in values}
    return {"values": values, "passed": passed, "all_passed": bool(all(passed.values())),
            "centre_m": float(fit["centre_m"]), "amplitude_um": float(fit["amplitude_um"]),
            "usable_stations": int(fit["usable_stations"])}


#: Round 310's stationarity read: a run whose rail load never settles has no quotable crossing, whatever its
#: gates say (the seven gates do not test stationarity).
STATIONARITY = (pathlib.Path(__file__).resolve().parent.parent
                / "reports" / "load_split_inversion_2026-10-31" / "engage_chatter.json")
MAX_STATIONARY_STD_KN = 5.0


def _stationary(speed_kmh: float) -> bool | None:
    """Whether the archived null run holds its load; ``None`` when round 310's report is absent."""

    if not STATIONARITY.is_file():
        return None
    report = json.loads(STATIONARITY.read_text(encoding="utf-8"))
    row = report.get("rows", {}).get(f"{speed_kmh:g}")
    if row is None:
        return None
    return bool(float(row["loaded_rail_std_kn"]) < MAX_STATIONARY_STD_KN)


def _runs(speed_kmh: float) -> tuple:
    import s152_cross_speed as cross

    return cross.RUNS[speed_kmh]


def measure() -> dict:
    """One row per speed: the four synthetic gates (bump route) and the physical engage (null route).

    The two columns live on different archived runs -- ``s152.fit`` loads route index 1, while the
    physical column must be read on route index 0 -- so a speed whose bump run is missing is reported as
    ``partial``: its physical engage is quotable, its four gates are not.  Treating that as ``measured``
    would put an absent gate in the pass column (round 304).
    """
    table = {}
    for speed in SPEEDS_KMH:
        null_route, bump_route, _ = _runs(speed)
        if not _route_archived(null_route, speed):
            table[f"{speed:g}"] = {"status": "pending", "reason": "no archive at this duration yet"}
            continue
        null_scan = engage_scan(speed, "null")
        stationary = _stationary(speed)
        physical = {key: (None if value is None else value - GEOMETRY_TOUCH_M)
                    for key, value in null_scan["by_threshold"].items()}
        if not _route_archived(bump_route, speed):
            note = ("null route archived; the bump route is missing, and the four synthetic gates "
                    "are measured on it (s152.fit loads route index 1)")
            if stationary is False:
                note += "; and round 310 found the rail load never settles, so its physical column is withdrawn"
            table[f"{speed:g}"] = {
                "status": "partial",
                "engage": null_scan,
                "physical_error_m": physical,
                "stationary": stationary,
                "reason": note,
            }
            continue
        bump_scan = engage_scan(speed, "bump")
        row = {"status": "measured", "gates": gates(speed), "engage": null_scan,
               "engage_bump": bump_scan, "bump_available": True, "stationary": stationary}
        row["physical_error_m"] = physical
        row["bump_shift_m"] = {
            key: (None if (null_scan["by_threshold"][key] is None or bump_scan["by_threshold"][key] is None)
                  else bump_scan["by_threshold"][key] - null_scan["by_threshold"][key])
            for key in null_scan["by_threshold"]}
        table[f"{speed:g}"] = row
    return table


def verdict(table: dict) -> dict:
    scored = {key: row for key, row in table.items() if row.get("status") == "measured"}
    readable = {key: row for key, row in table.items() if row.get("status") in ("measured", "partial")}
    all_gates = {key: row["gates"]["all_passed"] for key, row in scored.items()}
    # the physical column: does the 5 % engage stay within the 0.20 m location tolerance?
    physical = {}
    for key, row in readable.items():
        error = row["physical_error_m"].get("0.05")
        physical[key] = {"error_m": error, "within_gate": bool(error is not None and abs(error) <= LIMITS["G-LOC"])}
    return {
        "all_gates_by_speed": all_gates,
        "physical_by_speed": physical,
        "geometry_touch_m": GEOMETRY_TOUCH_M,
        "geometry_source": GEOMETRY_SOURCE,
        "pending": [key for key, row in table.items() if row.get("status") == "pending"],
        "partial": [key for key, row in table.items() if row.get("status") == "partial"],
        "not_stationary": [key for key, row in table.items() if row.get("stationary") is False],
    }


def main() -> int:
    table = measure()
    print(f"{'speed':>5} {'status':>9} {'G-ABS um':>9} {'G-REL %':>8} {'G-LOC m':>8} {'G-AMP %':>8} {'verdict':>8}")
    for key, row in table.items():
        if row.get("status") != "measured":
            print(f"{key:>5} {row.get('status', 'pending'):>9} {'-':>9} {'-':>8} {'-':>8} {'-':>8} {'-':>8}   {row['reason']}")
            continue
        values, passed = row["gates"]["values"], row["gates"]["passed"]
        verdict_text = "PASS" if row["gates"]["all_passed"] else "FAIL"
        print(f"{key:>5} {'measured':>9} {values['G-ABS']:9.2f} {values['G-REL']:8.2f} "
              f"{values['G-LOC']:8.3f} {values['G-AMP']:8.2f} {verdict_text:>8}")

    print()
    print("physical location column (engage = first station at a given blade share, NULL route):")
    print(f"  geometry reference {GEOMETRY_TOUCH_M:.3f} m  [{GEOMETRY_SOURCE}]")
    for key, row in table.items():
        if row.get("status") not in ("measured", "partial"):
            continue
        scan = row["engage"]["by_threshold"]
        cells = ", ".join(f"{threshold}: {scan[threshold]:.3f} m ({row['physical_error_m'][threshold]:+.3f})"
                          for threshold in scan if scan[threshold] is not None)
        print(f"  {key} km/h  {cells}")
        if "bump_shift_m" not in row:
            print("          bump moves it: pending (the bump route is not archived at this speed)")
            continue
        shift = row["bump_shift_m"]
        cells = ", ".join(f"{threshold}: {shift[threshold]:+.3f} m" for threshold in shift if shift[threshold] is not None)
        print("          bump moves it: " + (cells if cells else "pending (the bump route is not archived at this speed)"))

    result = verdict(table)
    print()
    for key, entry in result["physical_by_speed"].items():
        print(f"  {key} km/h physical error at 5 % share: {entry['error_m']:+.3f} m "
              f"-> {'within' if entry['within_gate'] else 'OUTSIDE'} the 0.20 m tolerance")
    if result["pending"]:
        print(f"pending: {', '.join(result['pending'])}")
    if result["partial"]:
        print(f"physical column only (gates need the bump route): {', '.join(result['partial'])}")

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps({"table": table, "verdict": result, "limits": LIMITS,
                                  "thresholds": list(THRESHOLDS)}, indent=2), encoding="utf-8")
    print(f"report -> {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
