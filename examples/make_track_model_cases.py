"""Create rigid and synthetic-modal examples from the four-axle base case.

The modal data produced here are placeholders for software workflow examples;
they are not measured, FE-derived, or exported Simpack modes.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CASE_DIR = ROOT / "examples" / "vehicle_v2"
BASE_CASE = CASE_DIR / "case.json"
STATIONS_M = [-1.0, 0.0, 5.0, 10.0, 15.0, 20.0, 25.0]
SHAPE = [0.0, 0.1, 0.55, 0.9, 1.0, 0.65, 0.15]


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    base = json.loads(BASE_CASE.read_text(encoding="utf-8"))

    rigid = copy.deepcopy(base)
    rigid["case_id"] = "synthetic_four_axle_turnout_rigid_track"
    rigid["purpose"] = "synthetic"
    rigid["track_dynamics"] = {"kind": "rigid"}
    rigid.pop("initial_state", None)
    write_json(CASE_DIR / "case_rigid.json", rigid)

    modal = copy.deepcopy(base)
    modal["case_id"] = "synthetic_four_axle_turnout_modal_track_demo"
    modal["purpose"] = "synthetic"
    modal["track_dynamics"] = {"kind": "modal", "modal_file": "track_modes_synthetic.json"}
    modal.pop("initial_state", None)
    write_json(CASE_DIR / "case_modal_synthetic.json", modal)

    modes = [
        {"id": "left_stock_bending_demo", "modal_mass_kg": 400.0,
         "frequency_hz": 400.0, "damping_ratio": 0.03},
        {"id": "right_stock_bending_demo", "modal_mass_kg": 400.0,
         "frequency_hz": 520.0, "damping_ratio": 0.03},
        {"id": "right_switch_bending_demo", "modal_mass_kg": 250.0,
         "frequency_hz": 650.0, "damping_ratio": 0.04},
    ]
    shapes = {}
    for template_index, template_id in enumerate(("left_stock", "right_stock", "right_switch")):
        phi_z = [[0.0] * len(STATIONS_M) for _ in modes]
        phi_z[template_index] = SHAPE.copy()
        shapes[template_id] = {
            "station_m": STATIONS_M,
            "phi_y": [[0.0] * len(STATIONS_M) for _ in modes],
            "phi_z": phi_z,
        }
    write_json(CASE_DIR / "track_modes_synthetic.json", {
        "schema_version": "velch-modal-track-v1",
        "data_status": "synthetic_demo_only_not_simpack_or_fea_data",
        "normalization_note": "Shapes are dimensionless demonstrations; replace with exported and audited modes.",
        "modes": modes,
        "rail_shapes": shapes,
    })
    print("Wrote case_rigid.json, case_modal_synthetic.json and track_modes_synthetic.json")


if __name__ == "__main__":
    main()
