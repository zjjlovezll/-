"""Coupled wheelset/rail equations, adaptive stepping, and auditable outputs."""
from __future__ import annotations

import csv
import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from scipy.integrate import solve_ivp

from .contact import ContactResponse, evaluate_contact, find_graph_contact
from .model import Case


class SimulationFailure(RuntimeError):
    """A run failed its numerical execution contract."""


@dataclass
class SimulationResult:
    times_s: np.ndarray
    positions: np.ndarray
    velocities: np.ndarray
    contact_history: list[dict[str, ContactResponse]]
    solver_evaluations: int
    summary: dict[str, object]


class Dynamics:
    """One wheelset with 4 DOF and 2 translation DOF per rail patch.

    q=[wheel y,z,roll,spin, rail_1 y,z,...]; v has the same ordering.
    Longitudinal wheelset x(t) is prescribed, and its drive reaction is not
    solved. This model is suitable for controlled contact experiments, not a
    complete vehicle or gear-rack simulation.
    """

    def __init__(self, case: Case):
        self.case = case
        self.wheels = {item.id: item for item in case.wheels}
        self.mass = np.array([
            case.wheelset.mass_kg, case.wheelset.mass_kg,
            case.wheelset.roll_inertia_kg_m2, case.wheelset.spin_inertia_kg_m2,
            *(value for rail in case.rails for value in (rail.mass_y_kg, rail.mass_z_kg)),
        ], dtype=float)

    @property
    def dimension(self) -> int:
        return len(self.mass)

    def evaluate(self, t_s: float, q: np.ndarray, v: np.ndarray) -> tuple[np.ndarray, dict[str, ContactResponse]]:
        case = self.case
        force = np.zeros(self.dimension, dtype=float)
        support = case.suspension.support
        wheel = case.wheelset
        force[0] = -support.k_y_n_m * (q[0] - case.suspension.y_reference_m) - support.c_y_n_s_m * v[0]
        force[1] = (-wheel.mass_kg * wheel.gravity_m_s2
                    - support.k_z_n_m * (q[1] - case.suspension.z_reference_m)
                    - support.c_z_n_s_m * v[1])
        force[2] = (-case.suspension.k_roll_nm_rad * (q[2] - case.suspension.roll_reference_rad)
                    - case.suspension.c_roll_nm_s_rad * v[2])
        force[3] = wheel.drive_torque_nm
        x_m = case.run.x_start_m + wheel.travel_speed_m_s * t_s
        direction = 1 if wheel.travel_speed_m_s >= 0 else -1
        contacts: dict[str, ContactResponse] = {}
        for index, rail in enumerate(case.rails):
            pos = 4 + 2 * index
            force[pos] = -rail.support.k_y_n_m * q[pos] - rail.support.c_y_n_s_m * v[pos]
            force[pos + 1] = -rail.support.k_z_n_m * q[pos + 1] - rail.support.c_z_n_s_m * v[pos + 1]
            # Sample the surface the same way the v2 solver does: the running surface of
            # the body that carries it, not ``rail.profiles``.  ``shift_rails`` wraps
            # ``rail.bodies[*].series`` with the .tre offset, so going through the bare
            # ``profiles`` here made every irregularity silently inert on this path.
            bodies = getattr(rail, "contact_bodies", None) or getattr(rail, "bodies", None)
            series = bodies[0] if bodies else rail.profiles
            sample = series.sample(x_m, direction)
            geometry = find_graph_contact(
                self.wheels[rail.wheel_id].profile, sample,
                wheel_y_m=float(q[0]), wheel_z_m=float(q[1]), wheel_roll_rad=float(q[2]),
                wheel_lateral_offset_m=self.wheels[rail.wheel_id].lateral_offset_m,
                rail_y_m=float(q[pos]), rail_z_m=float(q[pos + 1]),
            )
            if (geometry is not None and geometry.penetration_m > 0
                    and abs(geometry.normal_y / geometry.normal_z) > case.run.maximum_abs_contact_slope):
                raise SimulationFailure(
                    f"contact on {rail.id} exceeds graph slope limit at x={x_m:.9g} m"
                )
            response = evaluate_contact(
                geometry, case.contact,
                wheel_v_y_m_s=float(v[0]), wheel_v_z_m_s=float(v[1]),
                wheel_roll_rate_rad_s=float(v[2]), wheel_spin_rate_rad_s=float(v[3]),
                rail_v_y_m_s=float(v[pos]), rail_v_z_m_s=float(v[pos + 1]),
                travel_speed_m_s=wheel.travel_speed_m_s,
            )
            contacts[rail.id] = response
            force[0] += response.wheel_force_y_n
            force[1] += response.wheel_force_z_n
            force[2] += response.wheel_roll_moment_nm
            force[3] += response.wheel_spin_moment_nm
            force[pos] -= response.wheel_force_y_n
            force[pos + 1] -= response.wheel_force_z_n
        if not np.all(np.isfinite(force)):
            raise SimulationFailure(f"non-finite generalized force at t={t_s:.9g} s, x={x_m:.9g} m")
        return force, contacts

    def derivative(self, t_s: float, state: np.ndarray) -> np.ndarray:
        dimension = self.dimension
        q, v = state[:dimension], state[dimension:]
        force, _ = self.evaluate(t_s, q, v)
        return np.concatenate((v, force / self.mass))

    def mechanical_energy_j(self, q: np.ndarray, v: np.ndarray,
                            contacts: dict[str, ContactResponse]) -> float:
        case = self.case
        support = case.suspension.support
        elastic = 0.5 * float(np.dot(self.mass, v * v))
        elastic += case.wheelset.mass_kg * case.wheelset.gravity_m_s2 * q[1]
        elastic += 0.5 * support.k_y_n_m * (q[0] - case.suspension.y_reference_m) ** 2
        elastic += 0.5 * support.k_z_n_m * (q[1] - case.suspension.z_reference_m) ** 2
        elastic += 0.5 * case.suspension.k_roll_nm_rad * (q[2] - case.suspension.roll_reference_rad) ** 2
        for index, rail in enumerate(case.rails):
            pos = 4 + 2 * index
            elastic += 0.5 * rail.support.k_y_n_m * q[pos] ** 2
            elastic += 0.5 * rail.support.k_z_n_m * q[pos + 1] ** 2
            response = contacts[rail.id]
            if response.geometry and response.geometry.penetration_m > 0:
                elastic += (2.0 / 5.0 * case.contact.normal_stiffness_n_m_1p5
                            * response.geometry.penetration_m ** 2.5)
        return elastic


def simulate(case: Case) -> SimulationResult:
    dynamics = Dynamics(case)
    run = case.run
    duration = run.duration_s
    # Preflight start and end; a profile event in between is checked by every RHS.
    direction = 1 if case.wheelset.travel_speed_m_s >= 0 else -1
    for rail in case.rails:
        rail.profiles.sample(run.x_start_m, direction)
        rail.profiles.sample(run.x_start_m + case.wheelset.travel_speed_m_s * duration, direction)
    intervals = int(math.ceil(duration / run.output_step_s))
    times = np.linspace(0.0, duration, intervals + 1)
    initial = np.array((*case.initial_q, *case.initial_v), dtype=float)
    solution = solve_ivp(
        dynamics.derivative, (0.0, duration), initial, method=run.method, t_eval=times,
        rtol=run.rtol, atol=run.atol, max_step=run.max_solver_step_s,
    )
    if not solution.success or solution.y.shape[1] != len(times):
        raise SimulationFailure(f"{run.method} failed: {solution.message}")
    if not np.all(np.isfinite(solution.y)):
        raise SimulationFailure("non-finite solution state")
    n = dynamics.dimension
    positions = solution.y[:n, :].T
    velocities = solution.y[n:, :].T
    contact_history = []
    energies = []
    max_depth = 0.0
    max_friction_excess = 0.0
    min_dissipation = float("inf")
    edge_limited_active_samples = 0
    peak_normal = {rail.id: 0.0 for rail in case.rails}
    active_samples = {rail.id: 0 for rail in case.rails}
    for time, q, v in zip(times, positions, velocities):
        _, contacts = dynamics.evaluate(float(time), q, v)
        contact_history.append(contacts)
        energies.append(dynamics.mechanical_energy_j(q, v, contacts))
        for rail in case.rails:
            response = contacts[rail.id]
            if response.geometry:
                max_depth = max(max_depth, response.geometry.penetration_m)
                edge_limited_active_samples += int(response.active and response.geometry.edge_limited)
            peak_normal[rail.id] = max(peak_normal[rail.id], response.normal_force_n)
            active_samples[rail.id] += int(response.active)
            friction = math.hypot(response.longitudinal_force_n, response.lateral_tangent_force_n)
            max_friction_excess = max(max_friction_excess,
                                      friction - case.contact.friction_coefficient * response.normal_force_n)
            min_dissipation = min(min_dissipation, response.friction_dissipation_w,
                                  response.damping_dissipation_w)
    gates = {
        "solver_completed": True,
        "finite_states_and_forces": True,
        "penetration_within_case_limit": max_depth <= run.maximum_penetration_m,
        "friction_bound": max_friction_excess <= 1e-7,
        "nonnegative_reported_dissipation": min_dissipation >= -1e-10,
        "no_edge_limited_active_contact": edge_limited_active_samples == 0,
    }
    summary = {
        "case_id": case.case_id,
        "case_purpose": case.purpose,
        "result_status": "numerically_checked" if all(gates.values()) else "numerical_gate_failed",
        "physics_validation_status": "unvalidated_against_measurement_or_Simpack",
        "gates": gates,
        "solver": {"method": run.method, "nfev": int(solution.nfev),
                   "njev": int(solution.njev), "nlu": int(solution.nlu),
                   "rtol": run.rtol, "atol": run.atol},
        "max_penetration_m": max_depth,
        "max_friction_excess_n": max_friction_excess,
        "peak_normal_force_n": peak_normal,
        "active_output_samples": active_samples,
        "edge_limited_active_output_samples": edge_limited_active_samples,
        "initial_mechanical_energy_j": float(energies[0]),
        "final_mechanical_energy_j": float(energies[-1]),
        "energy_change_j": float(energies[-1] - energies[0]),
        "note": "Energy changes include prescribed longitudinal drive/profile work and damping; change alone is not a conservation verdict.",
    }
    return SimulationResult(times, positions, velocities, contact_history, int(solution.nfev), summary)


def save_result(case: Case, result: SimulationResult, output_dir: str | Path) -> tuple[Path, Path]:
    directory = Path(output_dir).resolve()
    directory.mkdir(parents=True, exist_ok=True)
    csv_path = directory / "history.csv"
    json_path = directory / "manifest.json"
    case_snapshot = directory / "case_snapshot.json"
    current_case = case.source_path.read_bytes()
    if hashlib.sha256(current_case).hexdigest() != case.case_sha256:
        raise SimulationFailure("case JSON changed during the run")
    for asset_path, expected_sha256 in case.asset_hashes.items():
        if hashlib.sha256(Path(asset_path).read_bytes()).hexdigest() != expected_sha256:
            raise SimulationFailure(f"profile asset changed during the run: {asset_path}")
    case_snapshot.write_bytes(current_case)
    names = ["wheel_y_m", "wheel_z_m", "wheel_roll_rad", "wheel_spin_rad"]
    for rail in case.rails:
        names.extend((f"{rail.id}_y_m", f"{rail.id}_z_m"))
    columns = ["time_s", "x_m"] + names + [name + "_per_s" for name in names]
    for rail in case.rails:
        columns.extend((f"{rail.id}_normal_n", f"{rail.id}_fx_n", f"{rail.id}_fy_n",
                        f"{rail.id}_fz_n", f"{rail.id}_penetration_m", f"{rail.id}_active"))
    with csv_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(columns)
        for time, q, v, contacts in zip(result.times_s, result.positions, result.velocities, result.contact_history):
            row = [float(time), case.run.x_start_m + case.wheelset.travel_speed_m_s * float(time)]
            row.extend(float(x) for x in q)
            row.extend(float(x) for x in v)
            for rail in case.rails:
                contact = contacts[rail.id]
                row.extend((contact.normal_force_n, contact.longitudinal_force_n,
                            contact.wheel_force_y_n, contact.wheel_force_z_n,
                            contact.geometry.penetration_m if contact.geometry else 0.0,
                            int(contact.active)))
            writer.writerow(row)
    manifest = {
        "software": "Velch 0.2.0 (legacy single-wheelset solver)",
        "case_sha256": case.case_sha256,
        "case_snapshot": str(case_snapshot),
        "profile_asset_sha256": case.asset_hashes,
        "state_order": names,
        "units": {"time": "s", "x": "m", "positions": "m except roll/spin in rad",
                  "velocities": "m/s except roll/spin in rad/s", "forces": "N", "penetration": "m"},
        "summary": result.summary,
    }
    json_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return csv_path, json_path
