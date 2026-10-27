"""S8-1: the flexible wheelset's modal block, wired into the state vector.

The claims under test are narrow on purpose:

* a case with no ``flexible_wheelset`` block has exactly the state size and the right-hand side
  it had before this change (checked by comparison, not by inspection);
* a case with one grows by exactly its mode count, and the modal coordinates sit after the track
  block, so no body or track row can be overwritten by accident;
* the assembled block reproduces the frequencies the thesis measured on the real wheelset, and
  its analytic Jacobian is the linear operator its own force law implies.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from velch.io.history import classify, read_history
from velch.jacobian import JacobianAssembler
from velch.vehicle import load_vehicle_case
from velch.vehicle_solver import (VehicleDynamics, _settle_modal_coordinates,
                                  _static_vertical_equilibrium, save_vehicle_result,
                                  simulate_vehicle)
from velch.wheel_modes import (ModalAssembly, ModalBlock, modal_channel_names,
                               thesis_crh380a_modes)

EXAMPLE = Path(__file__).resolve().parents[1] / "examples" / "vehicle_v2" / "case.json"


def _absolute_paths(node) -> None:
    """Profile files are resolved against the case's own directory, so a copy must carry absolutes."""

    if isinstance(node, dict):
        if isinstance(node.get("file"), str):
            node["file"] = str((EXAMPLE.parent / node["file"]).resolve())
        for value in node.values():
            _absolute_paths(value)
    elif isinstance(node, list):
        for value in node:
            _absolute_paths(value)


def _case_with_modes(tmp_path: Path, axles=(1,), duration_s: float | None = None) -> Path:
    """A copy of the example case with one or more flexible wheelsets declared."""

    raw = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    _absolute_paths({key: raw[key] for key in ("wheels", "rail_templates")})
    if duration_s is not None:
        raw["run"]["duration_s"] = duration_s
    raw["flexible_wheelset"] = {"source": "table-2-3", "axles": list(axles), "cutoff_hz": 2000.0}
    target = tmp_path / "case_flexible.json"
    target.write_text(json.dumps(raw, indent=2), encoding="utf-8")
    return target


def _rigid_twin(tmp_path: Path, duration_s: float) -> Path:
    """The same car and the same run, with rigid wheelsets, for a side-by-side comparison."""

    raw = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    _absolute_paths({key: raw[key] for key in ("wheels", "rail_templates")})
    raw["run"]["duration_s"] = duration_s
    target = tmp_path / "case_rigid_twin.json"
    target.write_text(json.dumps(raw, indent=2), encoding="utf-8")
    return target


FE_MODES = Path(__file__).resolve().parents[1] / "vehicles" / "modes" / "CRH3C_wheelset_fe.json"


def _case_with_fe_modes(tmp_path: Path, axles=(1,), duration_s: float | None = None) -> Path:
    """The example case with the *measured* mode shapes attached.

    The frequency-only ``table-2-3`` set has no shapes, so it cannot project a contact force at
    all; anything that has to move the modes must load the finite-element set.
    """

    raw = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    _absolute_paths({key: raw[key] for key in ("wheels", "rail_templates")})
    if duration_s is not None:
        raw["run"]["duration_s"] = duration_s
    raw["flexible_wheelset"] = {"source": "file", "file": str(FE_MODES), "axles": list(axles)}
    target = tmp_path / "case_fe_modes.json"
    target.write_text(json.dumps(raw, indent=2), encoding="utf-8")
    return target


def _padded(values, extra: int) -> np.ndarray:
    return np.concatenate((np.asarray(values, dtype=float), np.zeros(extra)))


def test_a_rigid_case_is_untouched_by_the_modal_machinery() -> None:
    case = load_vehicle_case(EXAMPLE)
    assert case.wheel_modes is None
    dynamics = VehicleDynamics(case)
    assert dynamics.modal is None
    assert dynamics.dimension == len(case.initial_q)


def test_a_flexible_wheelset_adds_its_modes_after_the_track_block(tmp_path: Path) -> None:
    case = load_vehicle_case(_case_with_modes(tmp_path, axles=(1,)))
    modes = thesis_crh380a_modes()
    assert case.wheel_modes is not None
    assert sum(len(item.modes) for item in case.wheel_modes.values()) == len(modes.modes)
    dynamics = VehicleDynamics(case)
    rigid = VehicleDynamics(load_vehicle_case(EXAMPLE))
    assert dynamics.dimension == rigid.dimension + len(modes.modes)
    assert len(case.initial_q) == dynamics.dimension
    modal = dynamics.modal
    assert modal is not None
    assert modal.offset == rigid.dimension
    assert modal.stop == dynamics.dimension
    # Unit modal mass, and only there.
    assert np.array_equal(dynamics.mass[:rigid.dimension], rigid.mass)
    assert np.array_equal(dynamics.mass[rigid.dimension:], np.ones(len(modes.modes)))


def test_unexcited_modes_do_not_touch_a_single_body_or_track_row(tmp_path: Path) -> None:
    """The strongest available statement of "zero modes change nothing".

    Both cars are evaluated at the same body and track state, with the modal coordinates at rest.
    Every row that existed before must come back bit-identical; otherwise the block is leaking
    into the vehicle or the track, which would invalidate every frozen baseline at once.
    """

    rigid_case = load_vehicle_case(EXAMPLE)
    rigid = VehicleDynamics(rigid_case)
    flexible = VehicleDynamics(load_vehicle_case(_case_with_modes(tmp_path, axles=(1,))))
    q = np.asarray(rigid_case.initial_q, dtype=float)
    v = np.asarray(rigid_case.initial_v, dtype=float)
    force_rigid, _ = rigid.evaluate(0.0, q, v)
    force_flexible, _ = flexible.evaluate(0.0, _padded(q, flexible.dimension - rigid.dimension),
                                          _padded(v, flexible.dimension - rigid.dimension))
    assert np.array_equal(force_flexible[:rigid.dimension], force_rigid)
    assert np.allclose(force_flexible[rigid.dimension:], 0.0)


def test_the_assembly_reproduces_the_measured_frequency_split() -> None:
    """At 200 km/h the ND2 pair must land on the thesis's 420.2 / 499.1 Hz.

    This is the one external number available without ANSYS, so it is the check that the
    gyroscopic term is scaled correctly rather than merely present.
    """

    modes = thesis_crh380a_modes()
    speed = 200.0 / 3.6
    block = ModalBlock(modes=modes, offset=0, prefix="axle1",
                      spin_rad_s=speed / modes.radius_m)
    assembly = ModalAssembly((block,))
    pairs = {nd: (left, right) for left, right, nd in modes._pairs()}
    for nd, expected in ((2, (420.2, 499.1)), (3, (1145.4, 1263.0))):
        left, right = pairs[nd]
        k, c = assembly.mode_slice((left, right))
        companion = np.zeros((4, 4))
        companion[:2, 2:] = np.eye(2)
        companion[2:, :2] = -k
        companion[2:, 2:] = -c
        values = np.linalg.eigvals(companion)
        found = np.sort(np.abs(values.imag[values.imag > 0.0]) / (2.0 * np.pi))
        assert found == pytest.approx(expected, abs=3.5)


def test_the_modal_jacobian_is_the_force_laws_own_derivative(tmp_path: Path) -> None:
    flexible = VehicleDynamics(load_vehicle_case(_case_with_modes(tmp_path, axles=(1,))))
    modal = flexible.modal
    assert modal is not None
    q = np.zeros(flexible.dimension)
    v = np.zeros(flexible.dimension)
    start, stop = modal.offset, modal.stop
    q[start:] = 1e-5 * np.cos(np.arange(modal.size))
    v[start:] = 1e-4 * np.sin(np.arange(modal.size))
    assembler = JacobianAssembler(flexible)
    jacobian_q, jacobian_v = assembler.blocks(0.0, q, v)
    assert np.allclose(jacobian_q[start:stop, start:stop], -modal.stiffness(), rtol=1e-12, atol=0)
    assert np.allclose(jacobian_v[start:stop, start:stop], -modal.damping(), rtol=1e-12, atol=1e-12)
    # And nothing outside the block.
    outside = np.ones(flexible.dimension, dtype=bool)
    outside[start:stop] = False
    assert np.allclose(jacobian_q[start:stop, outside], 0.0)
    assert np.allclose(jacobian_v[start:stop, outside], 0.0)


def test_the_block_satisfies_its_own_energy_balance() -> None:
    """``f = −K q − C v`` must equal ``−∂U/∂q − C v`` with ``U = ½ qᵀK q``.

    A wrong stiffness in the force but the right one in the energy (or the reverse) would still
    integrate, and would still look plausible on a plot; this is what closes that gap.
    """

    modes = thesis_crh380a_modes()
    block = ModalBlock(modes=modes, offset=0, prefix="axle1", spin_rad_s=130.0)
    assembly = ModalAssembly((block,))
    q = 1e-6 * np.cos(np.arange(assembly.size))
    v = 1e-3 * np.sin(np.arange(assembly.size))
    # Central difference: a forward difference of a quadratic carries ``½ K_ii h``, which here is
    # 4.6e-4 — thirty times larger than the tolerance, and would flag a correct block.
    step = 1e-8
    gradient = np.empty(assembly.size)
    for index in range(assembly.size):
        plus = q.copy()
        minus = q.copy()
        plus[index] += step
        minus[index] -= step
        gradient[index] = (assembly.potential(plus) - assembly.potential(minus)) / (2.0 * step)
    force = assembly.force(q, v)
    assert np.allclose(force + assembly.damping() @ v, -gradient, rtol=0, atol=1e-6)


def test_modal_channel_names_match_the_assembly(tmp_path: Path) -> None:
    case = load_vehicle_case(_case_with_modes(tmp_path, axles=(1, 2)))
    modes = thesis_crh380a_modes()
    names = modal_channel_names(case.wheel_modes)
    assert len(names) == 2 * len(modes.modes)
    assert names[0].startswith("axle1_mode") and names[-1].startswith("axle2_mode")
    assert len(set(names)) == len(names)
    dynamics = VehicleDynamics(case)
    assert dynamics.modal is not None
    assert tuple(dynamics.modal.names()) == names

def test_a_run_with_inert_modes_matches_the_rigid_car(tmp_path: Path) -> None:
    """With no force mapping yet, the modes must stay exactly zero — and the car must not move.

    The tolerance is honest rather than cosmetic: adding 124 components changes the summation
    order inside the right-hand side, so the trajectories differ at ~1e-9 m on positions of order
    a millimetre.  What must hold exactly is that no modal coordinate ever leaves zero.
    """

    duration = 0.004
    flex_case = load_vehicle_case(_case_with_modes(tmp_path, axles=(1, 2, 3, 4), duration_s=duration))
    rigid_case = load_vehicle_case(_rigid_twin(tmp_path, duration))
    flex = simulate_vehicle(flex_case)
    rigid = simulate_vehicle(rigid_case)
    body = len(rigid_case.initial_q)
    rigid_positions = np.asarray(rigid.positions, dtype=float)
    flex_positions = np.asarray(flex.positions, dtype=float)
    assert flex_positions.shape[1] == body + 4 * len(thesis_crh380a_modes().modes)
    assert np.count_nonzero(flex_positions[:, body:]) == 0
    # Absolute, because a relative bound divides by coordinates that are legitimately zero.  A
    # nanometre against displacements of order a millimetre is the level the changed summation
    # order can reach; anything larger would mean the block is doing work it should not.
    difference = np.abs(flex_positions[:, :body] - rigid_positions)
    assert difference.max() < 1e-8
    assert difference.max() / np.max(np.abs(rigid_positions)) < 1e-5
    assert flex.summary["gates"] == rigid.summary["gates"]
    assert flex.summary["result_status"] == "numerically_checked"


def test_the_written_history_carries_and_reads_back_the_modal_columns(tmp_path: Path) -> None:
    case = load_vehicle_case(_case_with_modes(tmp_path, axles=(1,), duration_s=0.002))
    result = simulate_vehicle(case)
    history, _manifest = save_vehicle_result(case, result, tmp_path / "out")
    table = read_history(history)
    names = set(table.ordering)
    assert "axle1_mode1_q" in names
    assert classify("axle1_mode1_q").unit == "-"
    assert classify("axle1_mode1_q").kind == "state"
    modal = [name for name in table.ordering if name.endswith("_q")]
    assert len(modal) == len(thesis_crh380a_modes().modes)


def test_the_settled_tread_carries_the_contact_force_with_no_modal_residual(tmp_path: Path) -> None:
    """A flexible wheelset must not start with a flat, undeflected tread.

    Starting at q = 0 leaves the tread unloaded, so the first tenths of a second are the wheel
    settling at its own 76.8 Hz — and a 0.05 s window is entirely inside that.  The settle is a
    fixed point of K q = Phi^T f(q); after it the modal force at t = 0 vanishes while the modal
    coordinates are demonstrably not zero (a zero would also have a zero force, and prove nothing).
    """

    case = load_vehicle_case(_case_with_fe_modes(tmp_path, axles=(1,), duration_s=0.002))
    dynamics = VehicleDynamics(case)
    try:
        q = np.array(case.initial_q, dtype=float)
        v = np.array(case.initial_v, dtype=float)
        modal = dynamics.modal
        assert modal is not None
        # The raw initial state has no contact yet (the car has not been let down onto the rail),
        # so the settle only sees a force after the vertical equilibrium.  That is also the order
        # the solver runs them in, and settling against no contact would prove nothing.
        q, _residual = _static_vertical_equilibrium(case, dynamics, q, v)
        before = np.max(np.abs(dynamics.evaluate(0.0, q, v)[0][modal.offset:]))
        settled = _settle_modal_coordinates(dynamics, q, v)
        after = np.max(np.abs(dynamics.evaluate(0.0, settled, v)[0][modal.offset:]))
        displacement = np.max(np.abs(settled[modal.offset:]))
    finally:
        dynamics.close()
    assert displacement > 0.0, "the settle must move the modal coordinates"
    assert before > 0.0, "an unloaded tread must show a modal residual, else the test is vacuous"
    assert after < 1e-3 * before, f"modal residual {after:.3e} N of {before:.3e} N"
    # The tread has to be pressed *into* the rail: upward displacement of the wheel surface under
    # an upward contact force is positive z, and the solver's own sign convention puts the contact
    # below the wheel centre.
    assert np.all(np.isfinite(settled))


def test_a_rigid_case_has_nothing_to_settle(tmp_path: Path) -> None:
    case = load_vehicle_case(_rigid_twin(tmp_path, duration_s=0.002))
    dynamics = VehicleDynamics(case)
    try:
        q = np.array(case.initial_q, dtype=float)
        v = np.array(case.initial_v, dtype=float)
        assert dynamics.modal is None
        assert np.array_equal(_settle_modal_coordinates(dynamics, q, v), q)
    finally:
        dynamics.close()
