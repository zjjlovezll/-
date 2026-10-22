"""Enabling the contact partials must not move a single bit of the physics.

``JacobianAssembler`` flips ``VehicleDynamics.contact_partials`` on for the duration
of its own ``evaluate`` call, so the question this answers is: does assembling the
geometry partials change the contact force, the contact geometry, or the state
derivative?  If it does, the analytic Jacobian would be differentiating a different
model than the one the solver integrates.
"""
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from velch.vehicle import load_vehicle_case  # noqa: E402
from velch.vehicle_solver import VehicleDynamics, _static_vertical_equilibrium  # noqa: E402

FIELDS = ("y_m", "wheel_z_m", "rail_z_m", "penetration_m", "normal_y", "normal_z",
          "tangent_y", "tangent_z", "lever_y_m", "lever_z_m", "rail_dz_ds",
          "stiffness_n_m_1p5", "radius_star_m", "half_width_m")


def snapshot(dynamics):
    return {key: tuple(getattr(r.geometry, name) for name in FIELDS)
            for key, dyn_list in dynamics.body_contacts.items()
            for r in dyn_list if r.geometry is not None}


def partials_present(dynamics):
    return sum(1 for dyn_list in dynamics.body_contacts.values() for r in dyn_list
               if r.geometry is not None and r.geometry.partials is not None)


case = load_vehicle_case(ROOT / "validation" / "crh380a_m" / "case_full12_cap05.json")
dynamics = VehicleDynamics(case)
q = np.array(case.initial_q)
v = np.array(case.initial_v)
if case.equilibrate_vertical:
    q, _ = _static_vertical_equilibrium(case, dynamics, q, v)

# The contact search carries per-body memory, so both evaluations must start from
# the same memory, exactly the way JacobianAssembler does it.
state = dynamics.snapshot_contact_state()

dynamics.contact_partials = False
plain = dynamics.evaluate(0.45, q, v)[0].copy()
plain_geometry = snapshot(dynamics)
dynamics.restore_contact_state(state)

dynamics.contact_partials = True
rich = dynamics.evaluate(0.45, q, v)[0].copy()
rich_geometry = snapshot(dynamics)
present = partials_present(dynamics)
dynamics.restore_contact_state(state)

print("force bit-identical:", bool(np.array_equal(plain, rich)),
      " max |difference|:", float(np.max(np.abs(plain - rich))))
print("geometry bit-identical:", plain_geometry == rich_geometry)
print("contacts:", len(plain_geometry), " partials assembled:", present)
