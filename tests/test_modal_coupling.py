"""The contact force must reach the mode shapes, and it must do so without losing work.

Two failure modes are what this file is really guarding:

* the projection maps a force to zero (or to the wrong wheel) — the modes then never move, which
  is the state the first flexible run was in before this module existed;
* the projection weights the force one way and reads the displacement another — then
  ``Q . q != f . d(x)``, energy does not close, and no peak force would ever reveal it.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pytest

from velch.modal_coupling import ModalContact, TreadRing
from velch.wheel_modes import load_modes

REPO = Path(__file__).resolve().parents[1]
MODES = REPO / "vehicles" / "modes" / "CRH3C_wheelset_fe.json"
EXAMPLE = REPO / "examples" / "vehicle_v2" / "case.json"


@pytest.fixture(scope="module")
def modes():
    return load_modes(MODES)


@pytest.fixture(scope="module")
def rings(modes):
    return {side: TreadRing.from_modes(modes, side) for side in (-1, 1)}


def test_each_side_gets_its_own_wheel(rings) -> None:
    assert rings[-1].plane_y_m < 0.0 < rings[1].plane_y_m
    assert abs(rings[-1].plane_y_m) == pytest.approx(0.7359, abs=0.01)
    assert rings[-1].n_modes == rings[1].n_modes == 33
    # each ring is one wheel: 772 nodes in the file, ~386 per side
    assert 300 < rings[1].nodes.shape[0] < 450


def test_the_contact_point_sits_under_the_wheel_centre(rings) -> None:
    ring = rings[1]
    point = ring.bottom_point(0.000_065)
    centre = ring.centre
    # the shapes live in the CAD assembly frame, whose origin is not the wheelset centre:
    # this wheel's ring is centred at x ~= -1.25 m, so the contact point has to follow it
    assert point[0] == pytest.approx(centre[0])
    assert point[0] == pytest.approx(-1.25, abs=0.05)
    assert point[1] == pytest.approx(ring.plane_y_m)
    assert point[2] == pytest.approx(centre[2] - 0.460 + 65e-6, abs=1e-9)


def test_the_weights_are_a_partition_of_unity(rings) -> None:
    ring = rings[1]
    w = ring.weights(ring.bottom_point())
    assert w.sum() == pytest.approx(1.0, rel=1e-12)
    assert np.all(w >= 0.0)
    # and the kernel really is local: the mass of the weights sits within a couple of sigmas
    centre = (w[:, None] * ring.nodes).sum(axis=0)
    assert np.linalg.norm(centre - ring.bottom_point()) < 2.0 * ring.sigma_m


def test_a_rigid_translation_passes_the_force_through(rings) -> None:
    """A shape set that translates every node equally must return the force unchanged."""

    ring = rings[1]
    # three rigid translations, one per axis: together they must reproduce the force exactly
    translations = np.zeros((3, ring.nodes.shape[0], 3))
    translations[0, :, 0] = 1.0
    translations[1, :, 1] = 1.0
    translations[2, :, 2] = 1.0
    rigid = TreadRing(side=ring.side, nodes=ring.nodes, shapes=translations,
                      radius_m=ring.radius_m, sigma_m=ring.sigma_m)
    force = np.array([1234.0, -567.0, 8901.0])
    assert rigid.generalised_force(rigid.bottom_point(), force) == pytest.approx(force, rel=1e-12)


def test_virtual_work_closes_for_any_modal_coordinate(rings) -> None:
    """``Q . q == f . d(x)`` — the single test that catches two disagreeing weightings."""

    ring = rings[1]
    rng = np.random.default_rng(20261024)
    point = ring.bottom_point()
    force = np.array([0.0, 321.0, -98_000.0])
    q = rng.normal(scale=1e-4, size=ring.n_modes)
    generalised = ring.generalised_force(point, force)
    assert float(generalised @ q) == pytest.approx(float(force @ ring.displacement(point, q)),
                                                   rel=1e-10, abs=1e-12)


def test_the_projection_is_linear_in_the_force(rings) -> None:
    ring = rings[-1]
    point = ring.bottom_point()
    a = np.array([0.0, 100.0, -1.0e5])
    b = np.array([0.0, -40.0, -2.5e5])
    qa = ring.generalised_force(point, a)
    qb = ring.generalised_force(point, b)
    qab = ring.generalised_force(point, a + b)
    assert qab == pytest.approx(qa + qb, rel=1e-12)
    assert ring.generalised_force(point, np.zeros(3)) == pytest.approx(np.zeros(ring.n_modes))


def test_a_missing_shape_set_is_refused_with_a_way_out() -> None:
    from velch.wheel_modes import ModeError, thesis_crh380a_modes

    with pytest.raises(ModeError, match="without mode shapes"):
        TreadRing.from_modes(thesis_crh380a_modes(), 1)


def test_the_block_slice_matches_the_offset(rings) -> None:
    coupling = ModalContact(rings=rings, offsets={0: 59, 1: 92})
    assert coupling.block(0) == slice(59, 92)
    assert coupling.block(1) == slice(92, 125)
    assert coupling.n_modes == 33
    with pytest.raises(Exception):
        coupling.block(7)


def test_the_shapes_are_scaled_for_metres_and_kilograms(modes) -> None:
    """Abaqus normalises mass in mm and tonnes; the solver works in m and kg.

    Skipping the 1/sqrt(1000) conversion leaves max |phi| at 3.56 instead of 0.113, which makes
    the modal force 31.6x too large and the implied tread displacement 1000x too large.  Nothing
    in a force check would notice, because the contact still runs on the undeformed tread.
    """

    peak = float(np.abs(modes.shapes).max())
    # a mode mass-normalised in kg/m moves the tread by about 1/sqrt(300 kg) per unit q
    assert 0.02 < peak < 0.5, f"max |phi| = {peak:.4g}: shapes look like mm/tonne normalisation"


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
    raw["case_id"] = "coupled_wheelset"
    raw["flexible_wheelset"] = {"source": "file", "file": str(MODES), "axles": [1, 2, 3, 4]}
    raw.setdefault("run", {})["duration_s"] = 0.002
    target = tmp_path / "case_coupled.json"
    target.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    return target


def test_the_contact_force_reaches_the_modal_coordinates(tmp_path: Path) -> None:
    """The wiring test: a loaded wheel must push on the modes, not only on the rigid body."""

    from velch.vehicle import load_vehicle_case
    from velch.vehicle_solver import VehicleDynamics

    case = load_vehicle_case(_coupled_case(tmp_path))
    dynamics = VehicleDynamics(case)
    assert dynamics.modal is not None and dynamics.contact_coupling is not None
    q = np.array(case.initial_q, dtype=float)
    v = np.zeros_like(q)
    force, _contacts = dynamics.evaluate(0.0, q, v)
    modal_force = force[dynamics.modal.offset:]
    assert modal_force.shape == (4 * 33,)
    assert np.any(modal_force != 0.0), "the modal block was driven by nothing"
    # and the rigid body still carries the load
    assert abs(force[dynamics.dof:]).max() > 0.0


def test_a_rigid_case_has_no_coupling(tmp_path: Path) -> None:
    from velch.vehicle import load_vehicle_case
    from velch.vehicle_solver import VehicleDynamics

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
    raw["case_id"] = "rigid_twin"
    target = tmp_path / "case_rigid.json"
    target.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    dynamics = VehicleDynamics(load_vehicle_case(target))
    assert dynamics.modal is None
    assert dynamics.contact_coupling is None
    assert dynamics.dimension == 59
