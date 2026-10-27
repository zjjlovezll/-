"""Compare the rail-grid axis frame with the absolute rail geometry.

Round 18 of the goal: on a curved rail the seat reports only left-rail patches (no right-rail patch
exists at all).  `_build_rail_grid` builds its axis from `rail_sample.profile.y_m` (relative) and
then interpolates with `np.interp(axis, rail_y, rail_z)` where `rail_y = rail_y_m + profile.y_m`
(absolute, contact_search.py:202).  If those two live in different frames, `np.interp` silently
clamps every axis sample to an endpoint -- which would look exactly like "no contact on that side".

This probe prints, for the first few grid builds of a straight case and of a curved case, the axis
bounds, the `rail_y` bounds, the difference, and whether the profile nodes are ascending.

Run: python -X utf8 scripts/s12b_grid_frame.py
"""

from __future__ import annotations

import json
import pathlib

import numpy as np

from velch import data_root
from velch import contact_grid
from velch import contact_search
from velch.vehicle import load_vehicle_case
from velch.vehicle_solver import simulate_vehicle

WORK = pathlib.Path(r"F:\velch_tmp\s12b")

records: list[dict] = []
original = contact_grid._build_rail_grid


def recording(rail_y, rail_z, rail_sample, grid_step_m):
    axis, axis_z, axis_slope, step = original(rail_y, rail_z, rail_sample, grid_step_m)
    node = np.asarray(rail_sample.profile.y_m, dtype=float)
    if len(records) < 6:
        records.append({
            "axis": (float(axis[0]), float(axis[-1])),
            "rail_y": (float(rail_y[0]), float(rail_y[-1])),
            "node": (float(node[0]), float(node[-1])),
            "ascending": bool(np.all(np.diff(node) > 0.0)),
            "offset_axis_rail": float(axis[0] - float(rail_y[0])),
            "z_span": (float(np.min(axis_z)), float(np.max(axis_z))),
        })
    return axis, axis_z, axis_slope, step


def build(label: str, *, curved: bool) -> pathlib.Path:
    raw = json.loads((data_root.case_dir() / "case_A_final_law.json").read_text(encoding="utf-8"))
    raw.pop("initial_state", None)
    raw["vehicle"]["travel_speed_m_s"] = 80.0 / 3.6
    raw["run"].update({"duration_s": 0.004, "output_step_s": 0.004, "x_start_m": 60.0})
    if curved:
        raw["run"].update({"curve_radius_m": 1100.0, "curve_cant_m": 0.0, "curve_geometry": True})
    WORK.mkdir(parents=True, exist_ok=True)
    path = WORK / f"case_{label}.json"
    path.write_text(json.dumps(raw, indent=1), encoding="utf-8")
    return path


def main() -> int:
    # contact_search imported the symbol by name, so patching the source module would not
    # be seen: the first attempt did exactly that and recorded zero calls.
    contact_search._build_rail_grid = recording  # type: ignore[assignment]
    contact_grid._build_rail_grid = recording  # type: ignore[assignment]
    for label, curved in (("straight", False), ("curved", True)):
        records.clear()
        case = load_vehicle_case(build(label, curved=curved))
        try:
            simulate_vehicle(case)
            status = "ran"
        except Exception as error:  # noqa: BLE001
            status = f"{type(error).__name__}: {str(error)[:80]}"
        print(f"\n{label}: {status}")
        for index, record in enumerate(records):
            print(f"  grid {index}: axis [{record['axis'][0]:+.4f}, {record['axis'][1]:+.4f}]  "
                  f"rail_y [{record['rail_y'][0]:+.4f}, {record['rail_y'][1]:+.4f}]  "
                  f"node [{record['node'][0]:+.4f}, {record['node'][1]:+.4f}]  "
                  f"ascending {record['ascending']}  axis-rail {record['offset_axis_rail']:+.4f}  "
                  f"z [{record['z_span'][0]:+.5f}, {record['z_span'][1]:+.5f}]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
