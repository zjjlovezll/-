"""The search has to run on the *deformed* tread, not on a corrected copy of its output.

S9-1 moved the deformation from a fix-up applied after :func:`find_graph_contact` to the wheel
profile that goes *into* it.  That single change is what makes position, slope and depth agree:
the search picks the deepest point of the moved surface, so the depth it reports already contains
the tread displacement and the point it reports is where the moved steel is.

The tests pin the four things that can go wrong, in the order they would bite:

* a rigid case must pass the **same profile object** — anything else perturbs trajectories that
  are supposed to be frozen;
* the profile must move by exactly the shift field, not by a resampled or smoothed version of it;
* the force must follow ``((depth - dz) / depth) ** 1.5`` — the ``delta**1.5`` law has to see the
  moved depth, otherwise a 11 um tread movement produces a linear-looking effect;
* the contact point must **move** with a strong slope, and the normal must turn by ``-atan(slope)``
  because ``contact_search`` takes its normal from the rail's slope grid and cannot know the
  wheel moved.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[1]
MODES = REPO / "vehicles" / "modes" / "CRH3C_wheelset_fe.json"
EXAMPLE = REPO / "examples" / "vehicle_v2" / "case.json"
RIGHT = "axle1_right_stock"
LEFT = "axle1_left_stock"


def _coupled_case(tmp_path: Path) -> Path:
    raw = json.loads(EXAMPLE.read_text(encoding="utf-8"))

    def absolute(node) -> None:
        if isinstance(node, dict):
            if isinstance(node.get("file"), str):
                node["file"] = str((EXAMPLE.parent / node["file"]).resolve())
            for value in node.values():
                absolute(value)
        elif isinstance(node, list):
            for value in node:
                absolute(value)

    absolute(raw)
    raw["case_id"] = "deformed_wheelset_profile"
    raw["flexible_wheelset"] = {"source": "file", "file": str(MODES), "axles": [1, 2, 3, 4]}
    raw.setdefault("run", {})["duration_s"] = 0.002
    target = tmp_path / "case_deformed_profile.json"
    target.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    return target


@pytest.fixture(scope="module")
def dynamics(tmp_path_factory):
    from velch.vehicle import load_vehicle_case
    from velch.vehicle_solver import VehicleDynamics

    case = load_vehicle_case(_coupled_case(tmp_path_factory.mktemp("deformed_profile")))
    return VehicleDynamics(case), case


def _rail(dynamics, rail_id: str):
    return next(rail for rail in dynamics.case.rails if rail.id == rail_id)


def _q_for_shift(dynamics, case, target_z_m: float, axle: int = 0) -> np.ndarray:
    """Modal vector whose vertical tread shift at the wheel centre is ``target_z_m``.

    The first mode is used alone because its shift across the running surface is nearly constant,
    which keeps the arithmetic of the force-law test readable.
    """

    ring = dynamics.contact_coupling.rings[1]
    probe = np.zeros(ring.n_modes)
    probe[0] = 1.0
    unit = float(ring.tread_shift(probe, np.array([0.0]))[0])
    assert abs(unit) > 0.0
    q = np.array(case.initial_q, dtype=float)
    q[dynamics.contact_coupling.block(axle)] = probe * (target_z_m / unit)
    return q


def _contact(dynamics, case, q: np.ndarray, rail_id: str = RIGHT):
    force, contacts = dynamics.evaluate(0.0, q, np.zeros(dynamics.dimension))
    return force, contacts[rail_id]


def test_zero_modal_coordinate_returns_the_original_profile(dynamics):
    dyn, case = dynamics
    q = np.array(case.initial_q, dtype=float)
    assert dyn._deformed_profile(dyn.wheels["R"], _rail(dyn, RIGHT), q) is dyn.wheels["R"].profile


def test_a_rigid_case_has_no_deformation(dynamics):
    from velch.vehicle import load_vehicle_case
    from velch.vehicle_solver import VehicleDynamics

    rigid = VehicleDynamics(load_vehicle_case(EXAMPLE))
    q = np.zeros(rigid.dimension)
    wheel = rigid.wheels["R"]
    assert rigid.contact_coupling is None
    assert rigid._deformed_profile(wheel, _rail(rigid, RIGHT), q) is wheel.profile


def test_the_profile_moves_by_exactly_the_shift_field(dynamics):
    dyn, case = dynamics
    q = _q_for_shift(dyn, case, 20e-6)
    wheel = dyn.wheels["R"]
    deformed = dyn._deformed_profile(wheel, _rail(dyn, RIGHT), q)
    shift = dyn.contact_coupling.rings[1].tread_shift(
        q[dyn.contact_coupling.block(0)], np.asarray(wheel.profile.y_m))
    assert np.array_equal(np.asarray(deformed.z_m),
                          np.asarray(wheel.profile.z_m, dtype=float) + shift)
    assert np.max(np.abs(shift)) > 1e-5


def test_the_force_follows_the_deformed_depth(dynamics):
    """The force is the Hertz law of the depth the search reports, at the stiffness it reports.

    Before B048 this was written as ``F_deformed / F_base == ((delta - dz)/delta)**1.5`` and it held
    to 2e-3, because the case pinned ``effective_radius_m = 0.02`` and therefore a *constant*
    stiffness.  With the stiffness fitted from the profiles (the default now) the stiffness is a
    property of where the contact sits, so a deformation that also slides the contact changes ``C``
    as well as ``delta`` -- measured 1.00618 where the constant-C arithmetic predicted 1.01827, a
    1.2 % gap that is the change of ``C``, not an error.  The exact statement is the one below: the
    elastic force equals ``C(y) * delta**1.5`` with both numbers read off the deformed contact, and
    the reported depth equals ``delta_base - dz`` so nothing is counted twice.
    """
    dyn, case = dynamics
    q = np.array(case.initial_q, dtype=float)
    _force, base = _contact(dyn, case, q)
    moved = _q_for_shift(dyn, case, 5e-6)
    _force, deformed = _contact(dyn, case, moved)
    depth = base.geometry.penetration_m
    # What the tread actually moved by, read at the lateral offset the contact sits at -- not at
    # the wheel centre.  This is the mistake that made an earlier round report 1.13 where the
    # arithmetic said 1.49: the contact is 4 mm away from the point that was calibrated.
    wheel = dyn.wheels["R"]
    lateral = float(base.geometry.y_m) - float(wheel.lateral_offset_m)
    dz = float(dyn.contact_coupling.rings[1].tread_shift(
        moved[dyn.contact_coupling.block(0)], np.array([lateral]))[0])
    deformed_depth = float(deformed.geometry.penetration_m)
    # The search runs on the moved surface, so the depth it reports *is* depth minus the shift.
    assert deformed_depth - (depth - dz) == pytest.approx(0.0, abs=1e-9)
    # The law at the deformed state: same modulus, the stiffness of the contact it actually found.
    predicted = float(deformed.geometry.stiffness_n_m_1p5) * deformed_depth ** 1.5
    assert deformed.normal_elastic_n == pytest.approx(predicted, rel=2e-3)
    # Under B048's fitted stiffness the force is the product of two moving quantities, and both
    # move measurably on this profile: measured at a 5 um tread shift, C falls 1.19 % (the contact
    # slid toward a blunter part of the rail) while the depth rises 1.21 %, so the net force rises
    # 0.62 % -- where the constant-C arithmetic would have predicted a 1.8 % fall.  The decomposition
    # is the exact statement, and the two effects are asserted to be large enough to matter.
    ratio = deformed.normal_elastic_n / base.normal_elastic_n
    c_ratio = deformed.geometry.stiffness_n_m_1p5 / base.geometry.stiffness_n_m_1p5
    d_ratio = deformed_depth / depth
    assert ratio == pytest.approx(c_ratio * d_ratio ** 1.5, rel=1e-3)
    assert abs(c_ratio - 1.0) > 5e-3, f"the stiffness must move with the contact, got {c_ratio:.6f}"
    assert abs(d_ratio - 1.0) > 5e-3, f"the depth must move with the tread, got {d_ratio:.6f}"


def test_the_contact_point_responds_to_a_steep_deformation(dynamics):
    """A shallow shift only moves the depth; a steep one also moves where the wheel touches.

    Both have to be true of a search that runs on the moved surface.  At 20 um the lateral
    position is unchanged to six decimals — the tread's own shift varies by only 1.6 um over the
    20 mm contact window, far less than the rail curvature — so the movement is demonstrated where
    it is measurable rather than asserted where it is not.
    """

    dyn, case = dynamics
    q = np.array(case.initial_q, dtype=float)
    _force, base = _contact(dyn, case, q)
    ring = dyn.contact_coupling.rings[1]
    probe = np.zeros(ring.n_modes)
    probe[1] = 1.0
    unit = float(ring.tread_shift(probe, np.array([0.0]))[0])
    strong = np.array(case.initial_q, dtype=float)
    strong[dyn.contact_coupling.block(0)] = probe * (-120e-6 / unit)
    _force, deformed = _contact(dyn, case, strong)
    assert abs(deformed.geometry.y_m - base.geometry.y_m) > 1e-3


def test_the_normal_turns_with_the_tread_slope(dynamics):
    dyn, case = dynamics
    q = np.array(case.initial_q, dtype=float)
    _force, base = _contact(dyn, case, q)
    moved = _q_for_shift(dyn, case, 20e-6)
    _force, deformed = _contact(dyn, case, moved)
    wheel = dyn.wheels["R"]
    lateral = float(base.geometry.y_m) - float(wheel.lateral_offset_m)
    slope = float(dyn.contact_coupling.rings[1].tread_slope(
        moved[dyn.contact_coupling.block(0)], lateral))
    # n = (-f', 1)/sqrt(1+f'^2): the tilt added to the base normal is -atan(slope).
    assert deformed.geometry.normal_y - base.geometry.normal_y == pytest.approx(-slope, rel=5e-2)
    norm = np.hypot(deformed.geometry.normal_y, deformed.geometry.normal_z)
    assert norm == pytest.approx(1.0, abs=1e-12)
    assert (deformed.geometry.normal_y * deformed.geometry.tangent_y
            + deformed.geometry.normal_z * deformed.geometry.tangent_z) == pytest.approx(0.0, abs=1e-12)


def test_the_left_wheel_reads_the_mirrored_lateral_coordinate(dynamics):
    """The profile's own lateral axis points outboard on both wheels; the CAD frame does not.

    Both wheel profiles peak in z at y = -0.045 (the flange), and the flange is inboard, so the
    left wheel's local +y is physical -y.  A test on the sign of the vertical shift would not see
    this — the symmetric first mode lifts both wheels together.  What pins it is that the left
    profile is shifted by the field evaluated at -y, and the right at +y.
    """

    dyn, case = dynamics
    q = _q_for_shift(dyn, case, 20e-6)
    block = q[dyn.contact_coupling.block(0)]
    wheel = dyn.wheels["L"]
    left_profile = dyn._deformed_profile(wheel, _rail(dyn, LEFT), q)
    expected = dyn.contact_coupling.rings[-1].tread_shift(
        block, -np.asarray(wheel.profile.y_m, dtype=float))
    assert np.array_equal(np.asarray(left_profile.z_m),
                          np.asarray(wheel.profile.z_m, dtype=float) + expected)
    # And it is not the same array the right wheel uses: the mirror has to change something.
    right_shift = dyn.contact_coupling.rings[1].tread_shift(
        block, np.asarray(wheel.profile.y_m, dtype=float))
    assert not np.allclose(expected, right_shift, atol=1e-9)
