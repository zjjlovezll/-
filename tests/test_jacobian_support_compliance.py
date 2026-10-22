"""The analytic Jacobian on cases that DO carry a support compliance.

Why this file exists: every older gate used ``case_full12_cap05.json``, which is the
one production case whose ``support_compliance`` is ``None``. Two defects lived
entirely in the compliant branch and survived the whole 325-test suite:

* the strip gradient was normalised by the *softened* slope instead of the raw Hertz
  slope, which made every position column ~55x too stiff at G ~ 1e-8;
* the damping branch was scaled by ``elastic_slope / raw``, a factor the right-hand
  side does not contain (``evaluate_contact`` damps ``sqrt(depth)``), so every
  velocity column was ~55x too soft.

Both are pinned here, together with the two configuration/state leaks found in the
same review. The remaining error on the compliant cases is a separate, still-open
defect (the roll/lateral cross-coupling at deep penetration); it is bounded rather
than fixed, so a regression that makes it worse still fails.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from velch.jacobian import frozen_geometry_error
from velch.model import RunSettings
from velch.vehicle import load_vehicle_case
from velch.vehicle_solver import VehicleDynamics, _static_vertical_equilibrium
from velch.data_root import case_dir

pytestmark = pytest.mark.corpus


BASE = case_dir()
SETTINGS = {
    "method": "BDF",
    "x_start_m": 13.5,
    "duration_s": 0.01,
    "output_step_s": 5e-4,
    "max_solver_step_s": 1e-4,
    "rtol": 1e-6,
    "atol": 1e-8,
    "maximum_penetration_m": 3e-3,
    "maximum_abs_contact_slope": 1.0,
}


def _equilibrated(name: str):
    case = load_vehicle_case(BASE / name)
    dynamics = VehicleDynamics(case)
    q = np.array(case.initial_q, dtype=float)
    v = np.array(case.initial_v, dtype=float)
    if case.equilibrate_vertical:
        q, _residual = _static_vertical_equilibrium(case, dynamics, q, v)
    return case, dynamics, q, v


@pytest.mark.parametrize("name", ["case_X_support.json", "case_Y_full_support.json"])
def test_damping_branch_carries_no_compliance_factor(name: str) -> None:
    """dN/d(approach) must be c*sqrt(depth) even when the support settles.

    Before the fix these read 0.041 and 0.976; the factor was ``1/correction`` = 55x.
    """
    case, dynamics, q, v = _equilibrated(name)
    try:
        assert case.support_compliance is not None, "this regression needs a compliant case"
        error = frozen_geometry_error(dynamics, 0.0, q, v)
        assert error["dv"] < 1.0e-6, error
        assert error["dv_worst_column"] < 1.0e-6, error
        assert error["dv_bad_columns"] == 0.0, error
    finally:
        dynamics.close()


def test_strip_gradient_is_normalised_by_the_raw_slope() -> None:
    """The strip publishes dN/dq of the raw Hertz functional; divide by the raw slope.

    Before the fix this case read dq = 53.4 (worst column 88.0, 12 bad columns).
    """
    case, dynamics, q, v = _equilibrated("case_X_support.json")
    try:
        error = frozen_geometry_error(dynamics, 0.0, q, v)
        assert error["dq"] < 1.0e-2, error
        assert error["dq_worst_column"] < 2.0e-1, error
        assert error["dq_bad_columns"] <= 4.0, error
    finally:
        dynamics.close()


def test_deep_penetration_compliant_case_is_bounded_not_ignored() -> None:
    """Roll/lateral cross-coupling at 688 um penetration: known open defect (C1/D4).

    The q block is still ~2.4e-2 here. This is a bound, not an endorsement: it exists
    so that the *other* defects cannot hide inside a large number again.
    """
    case, dynamics, q, v = _equilibrated("case_Y_full_support.json")
    try:
        error = frozen_geometry_error(dynamics, 0.0, q, v)
        assert error["dq"] < 5.0e-2, error
    finally:
        dynamics.close()


def test_compliance_free_case_stays_exact() -> None:
    """The fix must not disturb the case the original gate was built on."""
    case, dynamics, q, v = _equilibrated("case_full12_cap05.json")
    try:
        assert case.support_compliance is None
        error = frozen_geometry_error(dynamics, 0.0, q, v)
        assert error["dq"] < 1.0e-8, error
        assert error["dv"] < 1.0e-8, error
    finally:
        dynamics.close()


def test_jacobian_is_rejected_for_explicit_methods() -> None:
    """solve_ivp only warns when jac is passed to DOP853, so the case must fail loudly."""
    with pytest.raises(ValueError):
        RunSettings(**{**SETTINGS, "method": "DOP853", "jacobian": "analytic"})
    with pytest.raises(ValueError):
        RunSettings(**{**SETTINGS, "method": "DOP853", "jacobian": "sparse_fd"})
    # The implicit methods still accept both, and None stays free everywhere.
    assert RunSettings(**SETTINGS, jacobian="analytic").jacobian == "analytic"
    assert RunSettings(**{**SETTINGS, "method": "Radau"}, jacobian="sparse_fd").jacobian == "sparse_fd"
    assert RunSettings(**{**SETTINGS, "method": "DOP853"}).jacobian is None


def test_body_contacts_is_a_snapshot_not_a_live_view() -> None:
    """A caller must not see the cache change under it when a pure probe unwinds."""
    case, dynamics, q, v = _equilibrated("case_frog_N_strip05.json")
    try:
        dynamics.evaluate(0.0, q, v)
        first = dynamics.body_contacts
        key = next(iter(first))
        before = first[key][0].geometry.penetration_m if first[key][0].geometry else None

        lifted = q.copy()
        for axle in range(4):
            lifted[5 * axle + 1] += 1.0e-3
        dynamics.derivative_pure(0.0, np.concatenate((lifted, v)))

        after = first[key][0].geometry.penetration_m if first[key][0].geometry else None
        assert before == after, "the dict handed out earlier was mutated behind the caller"
        assert dynamics.body_contacts is not first
    finally:
        dynamics.close()
