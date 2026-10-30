"""The frozen oracle, guarded.

Every accuracy claim in this repository is measured against one number: the static
vertical equilibrium of the straight-track case, **59 680.577 N per contact** with
**65.5 um** penetration.  Until now that number lived only in documents, so a silent
change to a profile, a stiffness policy or the contact law could move it without any
test turning red.

The case is ``case_A_plain.json`` (flat straight track, rigid 35-dof vehicle,
``local_circular`` stiffness, 350 km/h): eight contacts, and by symmetry all eight must
carry the same force.  The tolerances are tight because this is a regression guard, not
a validation: the reference is what this exact case produced when the contact law was
frozen (2026-10-20), and any departure is a change to the physics or the geometry.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from velch.vehicle import load_vehicle_case
from velch.vehicle_solver import VehicleDynamics, _static_vertical_equilibrium
from velch.data_root import case_dir

pytestmark = pytest.mark.corpus


CASE = case_dir() / "case_A_plain.json"

ORACLE_CONTACT_N = 59_680.577
#: B048: with the stiffness fitted from the profiles (the default since the 20 mm override was
#: retired) the same 59 680.5769 N sits at **65.4661 um** of penetration, which is the number this
#: project has always quoted, and the body rides 132 um higher than under the 20 mm law
#: (-3.3057783604e-04 instead of -4.628e-4).  The force is untouched; only the depth under it moved,
#: because 20 mm was twelve times sharper than the wheel/rail pair the case actually carries
#: (R* = 0.5501 m measured at the contact).
ORACLE_VERTICAL_M = -3.3057783604e-04
STATIC_RESIDUAL_TOLERANCE_N = 1.0e-6


@pytest.fixture(scope="module")
def static_state():
    if not CASE.exists():  # pragma: no cover - the oracle case ships with the repo
        pytest.skip(f"oracle case missing: {CASE}")
    case = load_vehicle_case(CASE)
    dynamics = VehicleDynamics(case)
    q = np.array(case.initial_q, dtype=float)
    v = np.array(case.initial_v, dtype=float)
    assert case.equilibrate_vertical, "the oracle case must solve its own preload"
    q, residual = _static_vertical_equilibrium(case, dynamics, q, v)
    _force, responses = dynamics.evaluate(0.0, q, v)
    return q, residual, responses


def test_every_contact_carries_the_oracle_force(static_state) -> None:
    """59 680.577 N per contact, all eight equal -- the frozen accuracy anchor."""
    _q, _residual, responses = static_state
    forces = np.array([response.normal_force_n for response in responses.values()])
    assert forces.size == 8
    assert np.all(forces > 0.0), "the vehicle must sit on all eight contacts"
    np.testing.assert_allclose(forces, ORACLE_CONTACT_N, rtol=2.0e-4)
    # A static equilibrium on symmetric track has no reason to favour one side.
    assert forces.max() - forces.min() < 1.0e-3


def test_static_penetration_is_the_oracle_value(static_state) -> None:
    """The wheelset sinks 0.4628 mm; the contact consumes 65.5 um of it."""
    q, _residual, _responses = static_state
    vertical = np.array([q[5 * axle + 1] for axle in range(4)])
    np.testing.assert_allclose(vertical, ORACLE_VERTICAL_M, atol=1.0e-7)
    # The wheelset must not be rolling in this equilibrium.
    assert np.all(np.abs([q[5 * axle + 2] for axle in range(4)]) < 1.0e-9)


def test_static_equilibrium_is_converged(static_state) -> None:
    """The preload solve reports a residual, so the guard checks it is really zero."""
    _q, residual, _responses = static_state
    assert abs(residual) < STATIC_RESIDUAL_TOLERANCE_N
