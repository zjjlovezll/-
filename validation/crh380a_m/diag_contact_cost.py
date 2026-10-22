"""Cost of one contact evaluation with the case's own law and a real state.

Prints, per wheel/rail patch: the engaged lateral overlap, the strip count the
current policy would use, and the measured cost of one ``find_graph_contact`` call.
This is what tells geometry cost apart from profile-sampling cost; the two are
different optimisations.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from velch.contact import find_graph_contact          # noqa: E402
from velch.vehicle import load_vehicle_case           # noqa: E402


def main() -> int:
    case = load_vehicle_case(Path(sys.argv[1]))
    law = case.contact
    repeats = int(sys.argv[2]) if len(sys.argv) > 2 else 30
    q = np.asarray(case.initial_q, float)
    v = np.asarray(case.initial_v, float)
    sink_mm = float(sys.argv[3]) if len(sys.argv) > 3 else 0.0
    if sink_mm:
        for axle in range(4):
            q[5 * axle + 1] -= sink_mm * 1e-3
    print(f"case   : {case.case_id}   sink={sink_mm:.4g} mm")
    print(f"law    : normal={law.normal_policy} stiffness={law.stiffness_policy} "
          f"geometry={law.geometry_policy} strip_dy={law.strip_dy_m * 1e3:.4g} mm")
    print(f"E*     : {law.effective_modulus_pa:.4g} Pa   R*={law.effective_radius_m:.4g} m")
    print(f"patch  : enabled={law.patch_enabled} half_width={law.patch_half_width_m * 1e3:.4g} mm "
          f"slices={law.patch_slices}  dup_window={law.duplicate_patch_window_m * 1e3:.4g} mm")
    print(f"search : half_width={case.run.contact_search_half_width_m} arm={getattr(case.run, 'arm_at_boundary', None)} "
          f"seed_scope={case.run.contact_seed_scope}")
    print()
    print(f"{'rail':<12}{'body':<7}{'span mm':>9}{'pts':>6}{'us/call':>10}{'pen um':>9}")
    total = 0.0
    for rail in case.rails:
        wheel = next(w for w in case.wheels if w.id == rail.wheel_id)
        wh = 5 * rail.axle_index
        x = case.run.x_start_m + case.vehicle.axle_offsets_m[rail.axle_index]
        for body in rail.contact_bodies:
            if not body.active_at(x):
                continue
            sample = body.series.sample(x, 1)
            args = dict(
                wheel_y_m=float(q[wh]),
                wheel_z_m=case.vehicle.wheel_center_height_m + float(q[wh + 1]),
                wheel_roll_rad=float(q[wh + 2]),
                wheel_lateral_offset_m=wheel.lateral_offset_m,
                rail_y_m=0.753 if rail.id.endswith("right") else -0.753,
                rail_z_m=0.0,
                patch_half_width_m=law.patch_half_width_m,
                patch_slices=law.patch_slices,
                point_policy=law.point_policy,
                point_theta_m=law.point_theta_m,
                stiffness_policy=law.stiffness_policy,
                effective_modulus_pa=law.effective_modulus_pa,
                effective_radius_m=law.effective_radius_m,
                ellipticity_correction=law.ellipticity_correction,
                geometry_policy=law.geometry_policy,
                patch_window_m=law.patch_window_m,
                grid_step_m=law.grid_step_m,
                normal_policy=law.normal_policy,
                strip_dy_m=law.strip_dy_m,
                strip_min_depth_m=law.strip_min_depth_m,
            )
            start = time.perf_counter()
            geometry = None
            for _ in range(repeats):
                geometry = find_graph_contact(wheel.profile, sample, **args)
            per_call = (time.perf_counter() - start) / repeats * 1e6
            total += per_call
            lower = max(wheel.profile.y_m[0] + 0.0, sample.profile.y_m[0])
            span = float(sample.profile.y_m[-1] - sample.profile.y_m[0])
            points = int(min(20001, max(64, np.ceil(span / law.strip_dy_m) + 1)))
            pen = geometry.penetration_m * 1e6 if geometry else float("nan")
            print(f"{rail.id:<12}{body.id:<7}{span * 1e3:>9.1f}{points:>6d}"
                  f"{per_call:>10.1f}{pen:>9.2f}")
    print()
    print(f"sum of one pass over all active bodies: {total:8.1f} us")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
