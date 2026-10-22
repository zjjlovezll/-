"""Derive policy A/B cases from the wing-body frog case.

Usage:
    python -X utf8 make_policy_cases.py

Each case differs from ``case_frog_I_wing_0p05s.json`` only in the ``contact``
block, so any change in the force history is attributable to the contact policy
and not to the geometry.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

BASE = Path(__file__).with_name("case_frog_I_wing_0p05s.json")

VARIANTS: dict[str, dict] = {
    "base": {},
    "soft": {"point_policy": "soft_argmax"},
    "soft_fixed_theta": {"point_policy": "soft_argmax", "point_theta_m": 2.0e-5},
    "local": {"stiffness_policy": "local_circular"},
    "local_hc": {"stiffness_policy": "local_circular",
                 "damping_policy": "hunt_crossley", "restitution_coefficient": 0.5},
    "combined": {"point_policy": "soft_argmax",
                 "stiffness_policy": "local_circular",
                 "damping_policy": "hunt_crossley",
                 "restitution_coefficient": 0.5},
}


def main() -> None:
    raw = json.loads(BASE.read_text(encoding="utf-8"))
    for name, overrides in VARIANTS.items():
        case = copy.deepcopy(raw)
        case["contact"].update(overrides)
        target = BASE.with_name(f"case_pol_{name}.json")
        target.write_text(json.dumps(case, indent=2), encoding="utf-8")
        print(f"{target.name}: {overrides or 'no policy change'}")


if __name__ == "__main__":
    main()
