"""Bit-level snapshot of the sampled geometry, used to prove a cache is exact.

For a spread of longitudinal positions across the switch, records a SHA-256 of
the interpolated rail profile (y and z arrays), its longitudinal derivative,
and the resulting contact geometry. Any refactor of ProfileSeries.sample or
find_graph_contact must reproduce this file byte for byte.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np

from velch.contact import find_graph_contact
from velch.vehicle import load_vehicle_case

BASE = Path("validation/crh380a_m")
CASE = BASE / "case_B_turnout.json"
OUT = BASE / "geometry_snapshot.json"

POSITIONS_M = (
    3.5, 13.5, 20.0, 23.5, 31.0, 40.0, 45.55, 50.578, 50.579, 52.889, 55.0,
    57.304, 60.0, 60.3424, 60.68, 60.963, 65.0, 69.479, 72.5, 78.538, 79.131,
    79.44, 80.278, 80.911, 84.0, 90.0, 100.0, 110.0, 120.0, 130.0, 140.17, 150.0,
)
SINK_M = 0.000463


def digest(array: np.ndarray) -> str:
    return hashlib.sha256(np.ascontiguousarray(array, dtype=np.float64).tobytes()).hexdigest()


def main() -> None:
    case = load_vehicle_case(CASE)
    wheels = {item.id: item for item in case.wheels}
    records = {}

    for rail in (case.rails[0], case.rails[4]):
        wheel = wheels[rail.wheel_id]
        per_rail = {}
        for x_m in POSITIONS_M:
            sample = rail.profiles.sample(x_m, 1)
            geometry = find_graph_contact(
                wheel.profile,
                sample,
                wheel_y_m=0.0,
                wheel_z_m=0.43 - SINK_M,
                wheel_roll_rad=0.0,
                wheel_lateral_offset_m=wheel.lateral_offset_m,
                rail_y_m=0.0,
                rail_z_m=0.0,
            )
            per_rail[f"{x_m:.4f}"] = {
                "source": sample.profile.source,
                "source_sha256": sample.profile.source_sha256,
                "y_sha256": digest(sample.profile.y_m),
                "z_sha256": digest(sample.profile.z_m),
                "dz_ds_sha256": digest(sample.dz_ds),
                "y_points": int(sample.profile.y_m.size),
                "contact": None if geometry is None else {
                    "y_m": repr(geometry.y_m),
                    "penetration_m": repr(geometry.penetration_m),
                    "normal_y": repr(geometry.normal_y),
                    "normal_z": repr(geometry.normal_z),
                    "rail_dz_ds": repr(geometry.rail_dz_ds),
                    "edge_limited": geometry.edge_limited,
                },
            }
        records[rail.id] = per_rail

    OUT.write_text(json.dumps(records, indent=1, ensure_ascii=False), encoding="utf-8")
    total = sum(len(v) for v in records.values())
    print(f"wrote {OUT} : {len(records)} rails x {len(POSITIONS_M)} positions = {total} records")
    for rail_id, per_rail in records.items():
        unique_ids = {item["source"] for item in per_rail.values()}
        print(f"  {rail_id:14s} distinct interpolated profiles: {len(unique_ids)}")


if __name__ == "__main__":
    main()
