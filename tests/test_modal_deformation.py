"""The deformed tread has to change the depth the force law sees, and nothing else.

S8-3 is easy to get wrong in a way no peak force reveals.  Two mistakes matter:

* the tread displacement is applied to the *force* rather than to the *depth* — then the
  ``delta**1.5`` law never sees it, and a 20 um tread movement produces a linear-looking
  effect instead of the asymmetric one a one-sided contact must produce;
* the displacement is applied with the wrong sign or without the left/right mirror — the
  mode shapes live in the CAD assembly frame, where the two wheels sit at opposite ``y``
  and their z components are mirrored.

The quantitative handle used here is the force law itself: with the velocities zero there is
no damping term, so the normal force is exactly ``C * depth**1.5`` and moving the tread by
``d`` must scale it by ``((depth - d) / depth)**1.5``.
"""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from velch.contact_models import ContactGeometry

REPO = Path(__file__).resolve().parents[1]
MODES = REPO / "vehicles" / "modes" / "CRH3C_wheelset_fe.json"
EXAMPLE = REPO / "examples" / "vehicle_v2" / "case.json"


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
    raw["case_id"] = "deformed_wheelset"
    raw["flexible_wheelset"] = {"source": "file", "file": str(MODES), "axles": [1, 2, 3, 4]}
    raw.setdefault("run", {})["duration_s"] = 0.002
    target = tmp_path / "case_deformed.json"
    target.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    return target


@pytest.fixture(scope="module")
def dynamics(tmp_path_factory):
    from velch.vehicle import load_vehicle_case
    from velch.vehicle_solver import VehicleDynamics

    case = load_vehicle_case(_coupled_case(tmp_path_factory.mktemp("deformed")))
    return VehicleDynamics(case), case


def _rail(side: str, axle: int = 0):
    return SimpleNamespace(id=f"axle{axle + 1}_{side}_stock",
                           template_id=f"{side}_stock", axle_index=axle)


def _geometry(depth_m: float = 227e-6) -> ContactGeometry:
    return ContactGeometry(y_m=0.753, wheel_z_m=0.0, rail_z_m=0.0, penetration_m=depth_m,
                           normal_y=0.0, normal_z=1.0, tangent_y=1.0, tangent_z=0.0,
                           lever_y_m=0.0, lever_z_m=-0.46, rail_dz_ds=0.0,
                           stiffness_n_m_1p5=1.37e9)


def _modal_q(case, dynamics, ring_side: int, target_z_m: float,
             lateral_m: float = 0.0, penetration_m: float = 227e-6) -> np.ndarray:
    """Fill every axle's modal block so the tread moves ``target_z_m`` in z at the contact."""

    q = np.array(case.initial_q, dtype=float)
    ring = dynamics.contact_coupling.rings[ring_side]
    point = ring.contact_point(lateral_m, penetration_m)
    unit = ring.displacement(point, np.ones(ring.n_modes))[2]
    assert unit != 0.0
    fill = target_z_m / unit
    start = dynamics.modal.offset
    per = ring.n_modes
    for axle in range(4):
        q[start + axle * per: start + (axle + 1) * per] += fill
    return q


def test_zero_modal_coordinates_leave_the_contact_untouched(dynamics) -> None:
    dyn, case = dynamics
    geometry = _geometry()
    q = np.array(case.initial_q, dtype=float)
    assert np.all(np.asarray(q)[dyn.modal.offset:] == 0.0)
    assert dyn._deform_geometry(geometry, _rail("right"), q) is geometry


def test_the_tread_moves_the_depth_by_its_own_displacement(dynamics) -> None:
    dyn, case = dynamics
    geometry = _geometry()
    for target in (2.0e-5, -2.0e-5):
        q = _modal_q(case, dyn, 1, target)
        moved = dyn._deform_geometry(geometry, _rail("right"), q)
        # penetration is measured down into the rail, so raising the steel by d removes d
        assert moved.penetration_m == pytest.approx(geometry.penetration_m - target, abs=1e-15)
        # and the height the search reported has to travel with it, or the two disagree
        assert moved.wheel_z_m == pytest.approx(geometry.wheel_z_m + target, abs=1e-15)


def test_the_two_wheels_are_mirrors(dynamics) -> None:
    """One set of mode shapes serves both wheels through a mirror; the z signs must oppose."""

    dyn, case = dynamics
    q = _modal_q(case, dyn, 1, 2.0e-5)
    right = dyn._deform_geometry(_geometry(), _rail("right"), q)
    left = dyn._deform_geometry(_geometry(), _rail("left"), q)
    moved_right = right.penetration_m - _geometry().penetration_m
    moved_left = left.penetration_m - _geometry().penetration_m
    assert moved_right < 0.0 < moved_left
    assert abs(moved_left) == pytest.approx(abs(moved_right), rel=0.08)


def test_the_elastic_force_follows_the_new_depth(dynamics) -> None:
    """The end-to-end statement: the *elastic* force is C*delta**1.5 with delta moved by the tread."""

    dyn, case = dynamics
    q0 = np.array(case.initial_q, dtype=float)
    v = np.zeros_like(q0)
    _, base = dyn.evaluate(0.0, q0, v)
    rail_id = "axle1_right_stock"
    depth = base[rail_id].geometry.penetration_m
    elastic = base[rail_id].normal_elastic_n
    assert depth > 2.0e-4 and elastic > 0.0

    lateral = base[rail_id].geometry.y_m - 0.75  # contact offset from the wheel centre
    for target in (2.0e-5, -2.0e-5):
        q = _modal_q(case, dyn, 1, target, lateral_m=lateral, penetration_m=depth)
        _, moved = dyn.evaluate(0.0, q, v)
        expected = ((depth - target) / depth) ** 1.5
        assert moved[rail_id].normal_elastic_n / elastic == pytest.approx(expected, rel=1e-6)
        # the depth the law saw equals the shifted one
        assert moved[rail_id].geometry.penetration_m == pytest.approx(depth - target, rel=1e-9)


def test_the_normal_turns_with_the_tread_slope(dynamics) -> None:
    """Gao & Dai take the normal *after* deformation; a tread ring can supply its slope."""

    dyn, case = dynamics
    geometry = _geometry()
    lateral = geometry.y_m - 0.75
    q = _modal_q(case, dyn, 1, 2.0e-5, lateral_m=lateral,
                 penetration_m=geometry.penetration_m)
    moved = dyn._deform_geometry(geometry, _rail("right"), q, lateral_m=lateral)
    ring = dyn.contact_coupling.rings[1]
    first = dyn.modal.blocks[0]
    block = slice(first.offset, first.stop)
    _, slope = ring.deformation(np.asarray(q)[block], lateral, geometry.penetration_m)
    assert abs(slope) > 1e-6
    # a tread whose surface is z = f(y) has normal (-f'', 1)/sqrt(1+f''^2), so a slope of s turns
    # the normal by -atan(s): the measured angle must be the negative of the applied one
    angle = np.degrees(np.arctan2(moved.normal_y, moved.normal_z)
                       - np.arctan2(geometry.normal_y, geometry.normal_z))
    assert angle == pytest.approx(-np.degrees(np.arctan(slope)), rel=1e-6)
    assert moved.normal_y / moved.normal_z == pytest.approx(-slope, rel=1e-6)
    # rotating both keeps the creep basis orthonormal, so the pair cannot shear apart
    for y, z in ((moved.normal_y, moved.normal_z), (moved.tangent_y, moved.tangent_z)):
        assert np.hypot(y, z) == pytest.approx(1.0, rel=1e-12)
    assert moved.normal_y * moved.tangent_y + moved.normal_z * moved.tangent_z == pytest.approx(0.0, abs=1e-12)


def test_the_vertical_force_is_the_normal_projected_on_the_tilted_normal(dynamics) -> None:
    dyn, case = dynamics
    q0 = np.array(case.initial_q, dtype=float)
    v = np.zeros_like(q0)
    _, base = dyn.evaluate(0.0, q0, v)
    rail_id = "axle1_right_stock"
    assert base[rail_id].wheel_force_z_n / base[rail_id].normal_force_n == pytest.approx(
        base[rail_id].geometry.normal_z, rel=1e-12)
    q = _modal_q(case, dyn, 1, 2.0e-5, lateral_m=0.004, penetration_m=base[rail_id].geometry.penetration_m)
    _, moved = dyn.evaluate(0.0, q, v)
    assert moved[rail_id].wheel_force_z_n / moved[rail_id].normal_force_n == pytest.approx(
        moved[rail_id].geometry.normal_z, rel=1e-12)
    # and the tilt is not a rounding effect: the vertical share of the normal moved
    assert moved[rail_id].geometry.normal_z != base[rail_id].geometry.normal_z


def test_a_rigid_case_never_deforms(dynamics) -> None:
    from velch.vehicle import load_vehicle_case
    from velch.vehicle_solver import VehicleDynamics

    case = load_vehicle_case(EXAMPLE)
    dyn = VehicleDynamics(case)
    assert dyn.contact_coupling is None
    geometry = _geometry()
    q = np.array(case.initial_q, dtype=float)
    q[-1] = 1.0  # even a nonsense tail cannot reach a coupling that does not exist
    assert dyn._deform_geometry(geometry, _rail("right"), q) is geometry
