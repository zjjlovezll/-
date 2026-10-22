"""Compare the analytic spline contact path with the grid path (roadmap S1-b).

Both paths are fed the same surfaces through
:func:`velch.contact_geometry.absolute_surfaces`, so any difference is the
discretisation of the grid path and nothing else.

Run:  python -X utf8 validation\\crh380a_m\\cmp_spline_contact.py
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from velch.contact import find_graph_contact  # noqa: E402
from velch.contact_geometry import (absolute_surfaces, fit_profile,  # noqa: E402
                                    swept_contact)
from velch.vehicle import load_vehicle_case  # noqa: E402

CASE = ROOT / "validation" / "crh380a_m" / "case_frog_S_local_rise0.4_0p05s.json"
STATIONS = [40.0, 60.0, 79.86, 79.92, 79.97, 80.004, 80.06, 80.12, 80.22, 80.34,
            80.50, 80.72, 80.91, 82.0, 90.0, 120.0]
SINK_M = 0.4628e-3
WHEEL_BAND = (0.700, 0.830)
RAIL_BAND = (0.700, 0.860)


def main() -> int:
    case = load_vehicle_case(CASE)
    rail = next(r for r in case.rails if r.axle_index == 0 and r.id.endswith("right"))
    wheel = next(w for w in case.wheels if w.id == rail.wheel_id)
    law = case.contact
    rows = []
    for s in STATIONS:
        body = max((b for b in rail.contact_bodies if b.active_at(s)),
                   key=lambda b: b.series.covers(s), default=None)
        if body is None:
            continue
        sample = body.series.sample(s, 1)
        wheel_z_m = case.vehicle.wheel_center_height_m - SINK_M
        args = dict(wheel_y_m=0.0, wheel_z_m=wheel_z_m, wheel_roll_rad=0.0,
                    wheel_lateral_offset_m=wheel.lateral_offset_m,
                    rail_y_m=0.0, rail_z_m=0.0)
        grid = find_graph_contact(
            wheel.profile, sample, **args,
            stiffness_policy="local_circular",
            effective_modulus_pa=law.effective_modulus_pa,
        )
        wy, wz, ry, rz = absolute_surfaces(wheel.profile, sample, **args)
        mask_w = (wy >= WHEEL_BAND[0]) & (wy <= WHEEL_BAND[1])
        mask_r = (ry >= RAIL_BAND[0]) & (ry <= RAIL_BAND[1])
        try:
            wp = fit_profile(wy[mask_w], wz[mask_w], max_residual_m=2.0e-4,
                             name=f"wheel@{s:.3f}")
            rp = fit_profile(ry[mask_r], rz[mask_r], max_residual_m=2.0e-4,
                             name=f"rail@{s:.3f}")
        except ValueError as exc:
            rows.append({"s_m": s, "status": f"fit failed: {exc}"})
            continue
        sweep = swept_contact(wp, rp, wheel_origin_y_m=0.0, wheel_origin_z_m=wheel_z_m,
                              effective_modulus_pa=law.effective_modulus_pa)
        if sweep is None or grid is None:
            rows.append({"s_m": s, "status": "no contact"})
            continue
        rows.append({
            "s_m": s,
            "body": body.id,
            "residual_um": round(max(wp.max_residual_m, rp.max_residual_m) * 1e6, 3),
            "grid": {"y_mm": grid.y_m * 1e3, "pen_um": grid.penetration_m * 1e6,
                     "slope": grid.normal_y / grid.normal_z,
                     "R_star_m": grid.radius_star_m, "edge": grid.edge_limited},
            "spline": {"y_mm": sweep.y_m * 1e3, "pen_um": sweep.penetration_m * 1e6,
                       "slope": sweep.slope, "R_star_m": sweep.radius_star_m,
                       "edge": sweep.edge_limited,
                       "kappa_w": sweep.curvature_wheel_1_m,
                       "kappa_r": sweep.curvature_rail_1_m,
                       "extrema": sweep.extrema_count},
            "diff": {"y_mm": (sweep.y_m - grid.y_m) * 1e3,
                     "pen_um": (sweep.penetration_m - grid.penetration_m) * 1e6,
                     "R_star_rel": (sweep.radius_star_m - grid.radius_star_m)
                     / max(grid.radius_star_m, 1e-9)},
        })
    out = ROOT / "validation" / "crh380a_m" / "cmp_spline_contact.json"
    out.write_text(json.dumps(rows, indent=1, ensure_ascii=False), encoding="utf-8")

    print(f"{'s(m)':>8} {'body':>5} {'y_mm':>9} {'dy_mm':>7} {'pen_um':>8} "
          f"{'dpen':>7} {'R*_mm':>8} {'dR*%':>7} {'ext':>4}")
    live_y = live_pen = live_r = 0.0
    live_n = 0
    for row in rows:
        if "grid" not in row:
            print(f"{row['s_m']:8.3f}  {row.get('status', '')}")
            continue
        g, sp, d = row["grid"], row["spline"], row["diff"]
        loaded = g["pen_um"] > 1e-6 and sp["pen_um"] > 1e-6
        if loaded:
            live_n += 1
            live_y = max(live_y, abs(d["y_mm"]))
            live_pen = max(live_pen, abs(d["pen_um"]))
            live_r = max(live_r, abs(d["R_star_rel"]))
        print(f"{row['s_m']:8.3f} {row['body']:>5} {sp['y_mm']:9.3f} "
              f"{d['y_mm']:7.3f} {sp['pen_um']:8.2f} {d['pen_um']:7.2f} "
              f"{sp['R_star_m'] * 1e3:8.3f} {d['R_star_rel'] * 100:7.2f} "
              f"{sp['extrema']:4d}{'' if loaded else '  (no contact: tie)'}")
    print(f"\nstations with penetration on both paths: {live_n}")
    print(f"  worst |dy|   = {live_y:.4f} mm")
    print(f"  worst |dpen| = {live_pen:.3f} um")
    print(f"  worst |dR*|  = {live_r * 100:.2f} %")
    print(f"written to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
