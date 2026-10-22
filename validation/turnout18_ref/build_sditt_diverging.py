"""Assemble the diverging route of 07(009) from the SDITT profile catalog.

What this produces
------------------
``sditt_diverging_route.json``: per station, which rail bodies the diverging route has, and the
vehicle path offset implied by the data.  Two things make this more than a file copy:

* The switch panel (50.578..60.943 m) genuinely has **two** rails side by side -- the curved stock
  rail (``qjbg``) and the curved switch rail (``qjg_cgyg``) -- so the diverging route transfers its
  load between two bodies there, exactly like the frog's wing/point transfer on the through route.
* Each ``.prr`` lives in its **own part frame**, so the head centre of ``qjbg`` cannot be compared
  with that of ``zjg_zgyg``.  The path is therefore built per part and **tied at handover stations**:
  ``path(s) = path(tie) + centre_part(s) - centre_part(tie)``.  Every tie is printed so the
  assumption is auditable rather than buried in code.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

HERE = Path(__file__).parent
CATALOG = HERE / "sditt_turnout_catalog.json"
OUTPUT = HERE / "sditt_diverging_route.json"

# route order along the diverging route, with the station where each part takes over
CHAIN = (
    ("qjbg", 0.0),          # curved stock rail, present from the toe
    ("qjg_cgyg", 50.578),   # curved switch rail: shares the panel with qjbg, then runs alone
    ("cxg", 103.280),       # curved crossing (frog) part
)
RAIL_HALF_GAUGE_MM = 753.0


def head_centre_mm(record: dict) -> float:
    low, high = record["y_mm"]
    return 0.5 * (float(low) + float(high))


def main() -> int:
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    stations = catalog["stations"]
    keys = sorted((float(k), k) for k in stations)

    # per part: station -> centre
    part_series: dict[str, dict[float, float]] = {name: {} for name, _ in CHAIN}
    for station_m, key in keys:
        for name, record in stations[key].items():
            if name in part_series:
                part_series[name][station_m] = head_centre_mm(record)

    for name, _ in CHAIN:
        series = part_series[name]
        if not series:
            print(f"{name:<10} absent")
            continue
        values = np.array([series[s] for s in sorted(series)])
        print(f"{name:<10} {len(series):>3} stations {min(series):8.3f}..{max(series):8.3f} m  "
              f"centre {values.min():+7.2f}..{values.max():+7.2f} mm  drift {values[-1] - values[0]:+7.2f} mm")

    # -- the path, tied at handovers -----------------------------------------------------------
    path: dict[float, float] = {}
    tie_offset = 0.0
    for index, (name, start) in enumerate(CHAIN):
        series = part_series[name]
        if not series:
            continue
        inside = {s: c for s, c in series.items() if s >= start - 1e-9}
        if not inside:
            continue
        first = min(inside)
        reference = inside[first]
        if index > 0:
            # tie to the previous part at the handover station (or the closest station below it)
            previous = part_series[CHAIN[index - 1][0]]
            shared = [s for s in previous if abs(s - first) < 1e-9]
            if shared:
                tie_offset = path[shared[0]] - (inside[first] - reference)
            else:
                lower = [s for s in previous if s <= first]
                tie_station = max(lower) if lower else min(previous)
                tie_offset = path[tie_station] - (inside[tie_station] if tie_station in inside
                                                 else reference) + reference - reference
                tie_offset = path[tie_station]
                print(f"  tie {name} at {first:.3f} m uses qjbg station {tie_station:.3f} m")
        for station_m in sorted(inside):
            path[station_m] = tie_offset + (inside[station_m] - reference)
        print(f"  {name:<10} from {first:8.3f} m  tie offset {tie_offset:+7.3f} mm  "
              f"path {min(path[s] for s in inside):+7.2f}..{max(path[s] for s in inside):+7.2f} mm")

    for station_m in (50.578, 53.082, 55.0, 58.0, 60.943, 70.0, 80.0, 100.0, 103.28, 110.0, 116.59):
        nearest = min(path, key=lambda s: abs(s - station_m)) if path else None
        if nearest is not None and abs(nearest - station_m) < 1.0:
            print(f"  path({station_m:7.3f}) = {path[nearest]:+8.3f} mm   (station {nearest:.3f})")

    # -- bodies per station --------------------------------------------------------------------
    print("\nbodies per station (diverging route)")
    bodies: dict[float, list[str]] = {}
    for station_m in sorted(path):
        present = [name for name, start in CHAIN
                   if station_m in part_series[name] and station_m >= start - 1e-9]
        bodies[station_m] = present
    for station_m in (50.578, 53.082, 60.943, 70.0, 100.0, 103.28, 110.0):
        nearest = min(bodies, key=lambda s: abs(s - station_m))
        names = bodies[nearest]
        detail = ", ".join(f"{n}@{(part_series[n][nearest]):+.1f}mm" for n in names)
        print(f"  {nearest:8.3f}  {len(names)} body  {detail}")

    payload = {
        "turnout": catalog["turnout"],
        "rail_half_gauge_mm": RAIL_HALF_GAUGE_MM,
        "stations": [
            {
                "s_m": station_m,
                "path_mm": path[station_m],
                "bodies": [
                    {
                        "id": name,
                        "file": stations[_key_for(stations, station_m)][name]["file"],
                        "head_centre_mm": part_series[name][station_m],
                    }
                    for name in bodies[station_m]
                ],
            }
            for station_m in sorted(path)
        ],
        "note": ("path is the diverging route's centreline offset relative to the toe, chained per "
                 "part and tied at handovers; see the printed tie table for the assumption."),
    }
    OUTPUT.write_text(json.dumps(payload, indent=1), encoding="utf-8")
    print(f"\nwrote {OUTPUT.name}: {len(payload['stations'])} stations, "
          f"path {min(path.values()):+.2f}..{max(path.values()):+.2f} mm")
    return 0


_KEY_CACHE: dict[str, str] = {}


def _key_for(stations: dict, station_m: float) -> str:
    key = _KEY_CACHE.get(f"{station_m:.3f}")
    if key is None:
        key = f"{station_m:.3f}"
        if key not in stations:
            key = min(stations, key=lambda k: abs(float(k) - station_m))
        _KEY_CACHE[f"{station_m:.3f}"] = key
    return key


if __name__ == "__main__":
    raise SystemExit(main())
