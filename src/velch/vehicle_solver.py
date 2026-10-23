"""Independent vehicle and multi-patch turnout integration.

The vehicle has 35 coordinates. Track coordinates depend on the selected
rigid, local-compliant or reduced-modal track kernel.
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from scipy.integrate import solve_ivp
from scipy.optimize import root

from . import __version__
from .contact import (ContactGeometry, ContactResponse, deduplicate_contacts, evaluate_contact,
                      find_graph_contact, merge_contact_responses)
from .solver import SimulationFailure
from .topology import Topology, topology_for
from .track_models import TrackKernel
from .vehicle import VehicleCase


@dataclass(frozen=True)
class Connector:
    name: str
    axis: str
    stiffness: float
    damping: float
    rest: float
    jacobian: np.ndarray
    #: Optional nonlinear force law; ``None`` keeps the linear row this solver always used.
    law: object | None = None

    def extension(self, q: np.ndarray) -> float:
        return float(self.jacobian @ q) - self.rest

    def speed(self, v: np.ndarray) -> float:
        return float(self.jacobian @ v)

    def force(self, q: np.ndarray, v: np.ndarray) -> np.ndarray:
        if self.law is not None:
            return -float(self.law.force(self.extension(q), self.speed(v))) * self.jacobian
        return -(self.stiffness * self.extension(q) + self.damping * self.speed(v)) * self.jacobian

    def stiffness_at(self, q: np.ndarray) -> float:
        """Local dF/dextension: the number the analytic Jacobian must use at this state."""

        if self.law is not None:
            return float(self.law.stiffness(self.extension(q)))
        return self.stiffness

    def damping_at(self, v: np.ndarray) -> float:
        if self.law is not None:
            return float(self.law.damping(self.speed(v)))
        return self.damping

    def potential(self, q: np.ndarray) -> float:
        if self.law is not None:
            return float(self.law.potential(self.extension(q)))
        return 0.5 * self.stiffness * self.extension(q) ** 2


@dataclass
class VehicleResult:
    times_s: np.ndarray
    positions: np.ndarray
    velocities: np.ndarray
    contacts: list[dict[str, ContactResponse]]
    summary: dict[str, object]


class VehicleDynamics:
    """Small-rotation body/bogie/wheelset connector assembly.

    Coordinates: wheelsets 1..4 [y,z,roll,spin,yaw]; bogies F/R
    [y,z,roll,pitch,yaw]; carbody [y,z,roll,pitch,yaw]; then each
    axle/rail patch [y,z]. Longitudinal x is prescribed for all axles.
    """

    def __init__(self, case: VehicleCase, contact_workers: int = 1):
        self.case = case
        self.contact_workers = max(1, int(contact_workers))
        self._pool = (ThreadPoolExecutor(max_workers=self.contact_workers,
                                         thread_name_prefix="velch-contact")
                      if self.contact_workers > 1 else None)
        cfg = case.vehicle
        # The topology decides the state vector: which bodies exist, what each carries, and
        # in which order.  With no node table it reproduces the frozen 35-slot layout.
        self.topology: Topology = topology_for(case)
        self.track = TrackKernel(case.track_kind, case.rails, case.modal_track,
                                 case.track_layers, offset=self.topology.body_dimension)
        self.mass = self.topology.mass_array(self.track.mass)
        self.wheels = {wheel.id: wheel for wheel in case.wheels}
        self.connectors = self._build_connectors()
        # Assemble the strip-contact gradients (dN/dq, d(lever)/dq) only while the
        # analytic Jacobian is being assembled. They cost a handful of vectorised
        # passes per contact, which the solver's own right-hand side does not need;
        # leaving this False keeps the default integration path bit-identical.
        self.contact_partials: bool = False
        # Last accepted lateral contact position per rail patch. It seeds the
        # bounded contact search window; it is only maintained on the single
        # threaded path so that pooled evaluations stay order independent.
        self._contact_seed: dict[tuple[int, str], float] = {}
        self._body_cache: dict[str, tuple[ContactResponse, ...]] = {}
        # Consecutive evaluations in which a held rail seed found no contact.
        self._seed_misses: dict[int, int] = {}
        # Evaluation age per rail patch, used to schedule the exhaustive re-check.
        self._contact_age: dict[int, int] = {}
        self.CONTACT_RESEARCH_INTERVAL: int = 40
        # Body attribution: which rail body currently carries the load. Kept across
        # evaluations so a switch needs a margin and the old body must first unload.
        self._active_body: dict[int, str] = {}
        self._support = case.support_compliance
        self.BODY_SWITCH_MARGIN_M: float = 2.0e-5
        self.BODY_SWITCH_RELEASE_M: float = 5.0e-5

    @property
    def dimension(self) -> int:
        return len(self.mass)

    @property
    def dof(self) -> int:
        """Number of vehicle coordinates; the track block starts here."""

        return self.topology.body_dimension

    def _build_connectors(self) -> tuple[Connector, ...]:
        """Turn the topology's link specs into connectors, one row each."""

        return tuple(
            Connector(spec.name, spec.axis, spec.stiffness, spec.damping, spec.rest,
                      spec.jacobian(self.dimension), spec.law)
            for spec in self.topology.link_specs
        )

    def evaluate(self, t_s: float, q: np.ndarray, v: np.ndarray) -> tuple[np.ndarray, dict[str, ContactResponse]]:
        cfg = self.case.vehicle
        force = np.zeros(self.dimension)
        for body in self.topology.wheelsets():
            force[self.topology.require(body.id, "z")] -= body.mass_kg * cfg.gravity_m_s2
            force[self.topology.require(body.id, "spin")] += cfg.drive_torque_per_wheelset_nm
        for body in self.topology.bogies():
            force[self.topology.require(body.id, "z")] -= body.mass_kg * cfg.gravity_m_s2
        carbody = self.topology.carbody()
        force[self.topology.require(carbody.id, "z")] -= carbody.mass_kg * cfg.gravity_m_s2
        for connector in self.connectors:
            force += connector.force(q, v)
        force[self.dof:] += self.track.internal_force(q, v)
        contacts: dict[str, ContactResponse] = {}
        direction = 1 if cfg.travel_speed_m_s >= 0 else -1
        half_width = self.case.run.contact_search_half_width_m
        warm = half_width is not None and self._pool is None
        seeds: dict[int, dict[str, float]] = {}
        if warm:
            scope = self.case.run.contact_seed_scope
            for rail_index, rail in enumerate(self.case.rails):
                age = self._contact_age.get(rail_index, 0) + 1
                if age >= self.CONTACT_RESEARCH_INTERVAL:
                    # Periodic exhaustive re-check so a bounded search can never
                    # stay parked on a secondary lobe for the whole run.
                    self._contact_age[rail_index] = 0
                    seeds[rail_index] = {}
                else:
                    self._contact_age[rail_index] = age
                    if scope in ("rail", "rail_hold"):
                        # One wheel has one contact position: every body of this
                        # side searches around the same seed, so a bounded search
                        # cannot hand the wheel to a head 40 mm away in one step.
                        rail_seed = self._contact_seed.get((rail_index, "__rail__"))
                        seeds[rail_index] = ({"__rail__": rail_seed}
                                             if rail_seed is not None else {})
                    else:
                        seeds[rail_index] = {body.id: self._contact_seed[(rail_index, body.id)]
                                             for body in rail.contact_bodies
                                             if (rail_index, body.id) in self._contact_seed}
        jobs = [(rail_index, rail, rail.contact_bodies, t_s, q, v, direction,
                 seeds.get(rail_index) or {}, half_width if warm else None)
                for rail_index, rail in enumerate(self.case.rails)]
        if self._pool is None:
            results = [self._evaluate_patch(job) for job in jobs]
        else:
            results = list(self._pool.map(self._evaluate_patch, jobs))
        for (rail_index, rail, x), body_results in results:
            wh = self.topology.offset(self.topology.wheelset_id(rail.axle_index))
            body_results = self._attribute_bodies(rail_index, body_results)
            overlap = self.case.contact.duplicate_patch_window_m
            if overlap > 0.0 and len(body_results) > 1:
                body_results = deduplicate_contacts(body_results, overlap)
            self._body_cache[rail.id] = tuple(item[2] for item in body_results)
            contacts[rail.id] = merge_contact_responses(self._body_cache[rail.id])
            if self.case.run.contact_seed_scope == "rail_hold" and self._pool is None:
                loaded = any(geometry is not None and response.active
                             and geometry.penetration_m > 0.0
                             for _body_id, geometry, response in body_results)
                misses = 0 if loaded else self._seed_misses.get(rail_index, 0) + 1
                self._seed_misses[rail_index] = misses
                if misses >= self.CONTACT_RESEARCH_INTERVAL:
                    self._contact_seed.pop((rail_index, "__rail__"), None)
                    self._seed_misses[rail_index] = 0
            wheel_id = self.topology.wheelset_id(rail.axle_index)
            y_index = self.topology.require(wheel_id, "y")
            z_index = self.topology.require(wheel_id, "z")
            roll_index = self.topology.require(wheel_id, "roll")
            spin_index = self.topology.require(wheel_id, "spin")
            yaw_index = self.topology.index(wheel_id, "yaw")
            for _body_id, geometry, response in body_results:
                force[y_index] += response.wheel_force_y_n
                force[z_index] += response.wheel_force_z_n
                force[roll_index] += response.wheel_roll_moment_nm
                force[spin_index] += response.wheel_spin_moment_nm
                if geometry and yaw_index is not None:
                    force[yaw_index] -= geometry.lever_y_m * response.longitudinal_force_n
                force[self.dof:] += self.track.contact_reaction(rail_index, x,
                                                          response.wheel_force_y_n,
                                                          response.wheel_force_z_n)
        if not np.all(np.isfinite(force)):
            raise SimulationFailure(f"non-finite v2 force at t={t_s:.9g} s")
        return force, contacts

    def _attribute_bodies(self, rail_index: int,
                          body_results: list[tuple[str, ContactGeometry | None, ContactResponse]]
                          ) -> list[tuple[str, ContactGeometry | None, ContactResponse]]:
        """Decide which rail body of one side actually carries the wheel.

        Without ``run.body_hysteresis`` every body keeps its own contact, i.e.
        the sides are independent and multiple heads may load at once. With it,
        exactly one body per side carries load and the choice is sticky: the
        incumbent keeps the wheel until it has unloaded below
        ``BODY_SWITCH_RELEASE_M`` *and* a challenger is deeper by
        ``BODY_SWITCH_MARGIN_M``. That is what stops the contact point from
        jumping between heads at a fused nose.
        """
        active = [(body_id, geometry, response) for body_id, geometry, response in body_results
                  if geometry is not None and response.active]
        if not self.case.run.body_hysteresis or len(body_results) < 2:
            if active:
                deepest = max(active, key=lambda item: item[1].penetration_m)
                self._active_body[rail_index] = deepest[0]
            else:
                self._active_body.pop(rail_index, None)
            return body_results
        if not active:
            self._active_body.pop(rail_index, None)
            return body_results
        previous = self._active_body.get(rail_index)
        if previous is None:
            deepest = max(active, key=lambda item: item[1].penetration_m)
            self._active_body[rail_index] = deepest[0]
            return [deepest]
        incumbent = [item for item in active if item[0] == previous]
        challengers = [item for item in active if item[0] != previous]
        if not incumbent:
            # The incumbent lost contact completely: hand over unconditionally.
            deepest = max(active, key=lambda item: item[1].penetration_m)
            self._active_body[rail_index] = deepest[0]
            return [deepest]
        current = max(incumbent, key=lambda item: item[1].penetration_m)
        if challengers:
            challenger = max(challengers, key=lambda item: item[1].penetration_m)
            if (current[1].penetration_m < self.BODY_SWITCH_RELEASE_M
                    and challenger[1].penetration_m > current[1].penetration_m + self.BODY_SWITCH_MARGIN_M):
                self._active_body[rail_index] = challenger[0]
                return [challenger]
        return [current]

    def _evaluate_patch(self, job):
        """Evaluate every rail body of one wheel/rail patch.

        Safe to run in a worker thread. Each body is searched on its own profile,
        so the contact of the wing rail and of the point rail are resolved
        independently instead of competing for one argmax on a merged profile.
        """
        (rail_index, rail, bodies, t_s, q, v, direction,
         seeds, half_width) = job
        cfg = self.case.vehicle
        wh = self.topology.offset(self.topology.wheelset_id(rail.axle_index))
        wheel = self.wheels[rail.wheel_id]
        x = self.case.run.x_start_m + cfg.travel_speed_m_s * t_s + cfg.axle_offsets_m[rail.axle_index]
        path = self.case.path
        # The case's path is expressed in the rail reference frame, so its *offset* is absorbed by the
        # rail placement and only its slope matters here: the route's curvature turns the wheel against
        # the rail, which is a lateral creepage.  Feed it as extra lateral surface velocity.
        lateral_extra = path.at(x) if path is not None else 0.0
        lateral_rate = path.lateral_velocity_m_s(x, cfg.travel_speed_m_s) if path is not None else 0.0
        rail_y, rail_z, rail_vy, rail_vz = self.track.local_state(q, v, rail_index, x,
                                                                  cfg.travel_speed_m_s)
        body_results = []
        for body in bodies:
            if not body.active_at(x):
                continue
            sample = body.series.sample(x, direction)
            law = self.case.contact
            seed_y = seeds.get(body.id) if seeds else None
            if seed_y is None and seeds:
                seed_y = seeds.get("__rail__")
            geometry = find_graph_contact(
                wheel.profile, sample, wheel_y_m=float(q[wh]),
                wheel_z_m=cfg.wheel_center_height_m + float(q[wh + 1]),
                wheel_roll_rad=float(q[wh + 2]),
                wheel_lateral_offset_m=wheel.lateral_offset_m + lateral_extra,
                rail_y_m=rail_y, rail_z_m=rail_z,
                search_half_width_m=half_width,
                previous_y_m=seed_y,
                patch_half_width_m=law.patch_half_width_m,
                patch_slices=law.patch_slices,
                point_policy=law.point_policy,
                point_theta_m=law.point_theta_m,
                stiffness_policy=law.stiffness_policy,
                effective_modulus_pa=law.effective_modulus_pa,
                effective_radius_m=law.effective_radius_m,
                ellipticity_correction=law.ellipticity_correction,
                geometry_policy=law.geometry_policy,
                patch_window_m=law.patch_window_m,
                grid_step_m=law.grid_step_m,
                surface_key=(rail.id, body.id),
                normal_policy=law.normal_policy,
                strip_dy_m=law.strip_dy_m,
                strip_min_depth_m=law.strip_min_depth_m,
                strip_half_width_m=law.strip_half_width_m,
                strip_center_policy=law.strip_center_policy,
                curvature_policy=law.curvature_policy,
                partials=self.contact_partials,
            )
            if geometry is not None and not body.accepts_contact_y(geometry.y_m):
                # Attribution gate: a head whose running surface is not under the
                # wheel tread cannot carry load, however deep its crown measures.
                geometry = None
            if half_width is not None and self._pool is None:
                # A lost contact leaves no point worth tracking: drop the seed so
                # the next evaluation re-acquires it with the exhaustive span.
                # Under 'rail_hold' the seed is deliberately kept: the wheel stays
                # aimed where the contact last was, so the bounded search cannot
                hold = self.case.run.contact_seed_scope == "rail_hold"
                key = (rail_index, body.id)
                rail_key = (rail_index, "__rail__")
                if geometry is not None and geometry.penetration_m > 0.0:
                    self._contact_seed[key] = geometry.y_m
                    self._contact_seed[rail_key] = geometry.y_m
                else:
                    self._contact_seed.pop(key, None)
                    if not hold:
                        self._contact_seed.pop(rail_key, None)
            if (geometry and geometry.penetration_m > 0
                    and abs(geometry.normal_y / geometry.normal_z) > self.case.run.maximum_abs_contact_slope):
                raise SimulationFailure(f"graph slope limit at {rail.id}/{body.id}, x={x:.9g} m")
            support = self._support
            response = evaluate_contact(
                geometry, self.case.contact,
                wheel_v_y_m_s=float(v[wh]) + lateral_rate,
                wheel_v_z_m_s=float(v[wh + 1]),
                wheel_roll_rate_rad_s=float(v[wh + 2]),
                wheel_spin_rate_rad_s=float(v[wh + 3]),
                rail_v_y_m_s=rail_vy, rail_v_z_m_s=rail_vz,
                travel_speed_m_s=cfg.travel_speed_m_s,
                creep_attack_velocity_m_s=float(cfg.travel_speed_m_s * q[wh + 4]),
                support_compliance_m_per_n=(support.at(x) if support is not None else None),
            )
            body_results.append((body.id, geometry, response))
        return (rail_index, rail, x), body_results

    @property
    def body_contacts(self) -> dict[str, tuple[ContactResponse, ...]]:
        """Per-body contact responses of the most recent evaluation.

        ``evaluate`` returns one merged response per rail so that callers see the
        wheel's total force; the individual bodies stay here because their own
        geometry is what an analytic Jacobian has to linearise.

        The mapping is copied. ``restore_contact_state`` rebinds ``_body_cache`` when a
        pure evaluation unwinds, so handing out the live dict lets the content change
        under a caller that is still holding a reference from one step ago.
        """
        return dict(self._body_cache)

    def close(self) -> None:
        if self._pool is not None:
            self._pool.shutdown(wait=True)
            self._pool = None

    def derivative(self, t_s: float, state: np.ndarray) -> np.ndarray:
        n = self.dimension
        q, v = state[:n], state[n:]
        force, _ = self.evaluate(t_s, q, v)
        return np.concatenate((v, force / self.mass))

    def snapshot_contact_state(self) -> dict[str, object]:
        """Copy *every* piece of cross-call contact memory so a step can be replayed.

        The first version only stored the seed/age/active maps, which was enough
        for the cases on hand (`contact_search_half_width_m=None`,
        `body_hysteresis=False` never write them) but not in general:
        `_body_cache` is overwritten on every evaluation and `_seed_misses`
        counts consecutive misses and clears the seed at
        `CONTACT_RESEARCH_INTERVAL`. Both change later evaluations, so both have
        to travel with the snapshot or `derivative_pure` is only accidentally
        pure. The dicts hold references to frozen responses, so this is a
        shallow copy of a handful of entries.
        """
        return {
            "seed": dict(self._contact_seed),
            "age": dict(self._contact_age),
            "active": dict(self._active_body),
            "body": dict(self._body_cache),
            "misses": dict(self._seed_misses),
        }

    def restore_contact_state(self, snapshot: dict[str, object]) -> None:
        self._contact_seed = dict(snapshot["seed"])  # type: ignore[arg-type]
        self._contact_age = dict(snapshot["age"])  # type: ignore[arg-type]
        self._active_body = dict(snapshot["active"])  # type: ignore[arg-type]
        self._body_cache = dict(snapshot["body"])  # type: ignore[arg-type]
        self._seed_misses = dict(snapshot["misses"])  # type: ignore[arg-type]

    def derivative_pure(self, t_s: float, state: np.ndarray) -> np.ndarray:
        """Right-hand side with the contact memory discarded after the call.

        Explicit integrators evaluate the right-hand side once per step, so the
        seed and hysteresis memory is a one-way recursion along the trajectory.
        Implicit integrators evaluate it many times at neighbouring states of the
        same step; keeping the memory in place makes those evaluations overwrite
        each other and the map stops being a function of the state. Restoring the
        memory after each call makes it a pure function without changing the
        single-call physics.
        """
        snapshot = self.snapshot_contact_state()
        try:
            return self.derivative(t_s, state)
        finally:
            self.restore_contact_state(snapshot)

    def mechanical_energy_j(self, q: np.ndarray, v: np.ndarray,
                            contacts: dict[str, ContactResponse]) -> float:
        cfg = self.case.vehicle
        energy = 0.5 * float(np.dot(self.mass, v * v))
        topology = self.topology
        energy += cfg.gravity_m_s2 * (
            cfg.carbody.mass_kg * q[topology.require(topology.carbody().id, "z")] +
            sum(cfg.bogie.mass_kg * q[topology.require(body.id, "z")]
                for body in topology.bogies()) +
            sum(body.mass_kg * q[topology.require(body.id, "z")]
                for body in topology.wheelsets()))
        energy += sum(link.potential(q) for link in self.connectors)
        energy += self.track.potential_j(q)
        for responses in self._body_cache.values():
            for response in responses:
                if response.geometry and response.geometry.penetration_m > 0:
                    energy += 0.4 * self.case.contact.normal_stiffness_n_m_1p5 * response.geometry.penetration_m ** 2.5
        return float(energy)


def _static_vertical_equilibrium(case: VehicleCase, dynamics: VehicleDynamics,
                                 q: np.ndarray, v: np.ndarray) -> tuple[np.ndarray, float]:
    """Solve the vertical preload equilibrium, rejecting the hung-bogie branch.

    Seven vertical degrees of freedom have to carry eight contact patches, so the
    problem is over-determined and Newton iteration can settle on a branch with
    one bogie hanging: the front four patches then read ~2x the static load and
    the rear four read zero while the resultant still equals the weight. That
    branch reproduces a doubled flat-section force and a non-physical set-down,
    so every seed is solved and the branch with the *least starved* rail is kept.
    """
    topology = dynamics.topology
    # The seven vertical coordinates: four wheelsets, two bogies, one carbody, wherever the
    # topology put them.  With the legacy layout these are the historical 1/6/11/16/21/26/31.
    indices = ([topology.require(body.id, "z") for body in topology.wheelsets()] +
               [topology.require(body.id, "z") for body in topology.bogies()] +
               [topology.require(topology.carbody().id, "z")])
    if case.track_kind == "local_compliant":
        indices += [topology.body_dimension + 2 * i + 1 for i in range(len(case.rails))]
    elif case.track_kind == "two_layer":
        for i in range(len(case.rails)):
            indices += [topology.body_dimension + 4 * i + 1,
                        topology.body_dimension + 4 * i + 3]
    elif case.track_kind == "layered":
        stride = 2 * (1 + len(case.track_layers))
        for i in range(len(case.rails)):
            indices += [topology.body_dimension + stride * i + 2 * j + 1
                        for j in range(1 + len(case.track_layers))]
    elif case.track_kind == "modal":
        indices += list(range(topology.body_dimension, dynamics.dimension))
    wheel_rows = [topology.require(body.id, "z") for body in topology.wheelsets()]
    bogie_rows = [topology.require(body.id, "z") for body in topology.bogies()]

    seeds: list[np.ndarray] = [q[indices].copy()]
    for wheel_drop, bogie_drop in ((2.0e-3, 2.0e-3), (5.0e-4, 5.0e-4), (2.0e-3, 0.0), (0.0, 2.0e-3)):
        seed = q[indices].copy()
        seeded = q.copy()
        for row in wheel_rows:
            seeded[row] -= wheel_drop
        for row in bogie_rows:
            seeded[row] -= bogie_drop
        seed = seeded[indices].copy()
        seeds.append(seed)

    cfg = case.vehicle
    weight_n = cfg.gravity_m_s2 * (cfg.carbody.mass_kg + 2.0 * cfg.bogie.mass_kg
                                   + 4.0 * cfg.wheelset.mass_kg)
    expected_n = weight_n / max(len(case.rails), 1)

    best: tuple[float, np.ndarray, float, list[float]] | None = None
    last_message = ""
    for seed in seeds:
        base = q.copy()
        base[indices] = seed

        def residual(values: np.ndarray, base: np.ndarray = base) -> np.ndarray:
            trial = base.copy()
            trial[indices] = values
            force, _ = dynamics.evaluate(0.0, trial, v)
            return force[indices] / 1e5

        solved = root(residual, seed, method="hybr", options={"xtol": 1e-10})
        error_n = float(np.max(np.abs(residual(solved.x))) * 1e5)
        last_message = str(solved.message)
        if not np.all(np.isfinite(solved.x)) or error_n > 0.1:
            continue
        trial = base.copy()
        trial[indices] = solved.x
        _, contacts = dynamics.evaluate(0.0, trial, v)
        loads = [float(contacts[rail.id].normal_force_n) for rail in case.rails]
        # Prefer the branch whose heaviest patch is closest to its even share: the
        # hung-bogie branch doubles the front patches, so it scores worst here.
        score = -max(loads)
        if best is None or score > best[0]:
            best = (score, solved.x.copy(), error_n, loads)
        if max(loads) <= 1.6 * expected_n and min(loads) >= 1.0e3:
            break

    if best is None:
        raise SimulationFailure(
            f"vertical preload equilibrium failed: no seed converged; {last_message}")
    _, values, error_n, loads = best
    starved = min(loads) < 1.0e3
    over_loaded = max(loads) > 1.6 * expected_n
    if starved and over_loaded:
        raise SimulationFailure(
            "vertical preload equilibrium failed: hung-bogie branch - the lightest "
            f"contact patch carries only {min(loads):.1f} N while the heaviest carries "
            f"{max(loads):.1f} N (even share ~{expected_n:.0f} N); the seven vertical "
            "degrees of freedom cannot seat eight patches evenly")
    q[indices] = values
    return q, error_n


def simulate_vehicle(case: VehicleCase, contact_workers: int = 1) -> VehicleResult:
    dynamics = VehicleDynamics(case, contact_workers=contact_workers)
    try:
        return _integrate_vehicle(case, dynamics)
    finally:
        dynamics.close()


def _rhs_sparsity(dynamics: VehicleDynamics, state: np.ndarray, t_s: float) -> "object":
    """Structural sparsity of d(state)/dt: FD probe ∪ physically guaranteed entries.

    The mass matrix is diagonal and every spring/damper couples only a handful of
    coordinates, so the true Jacobian is sparse. BDF/LSODA can exploit that with a
    sparsity template: one dense probe (2n right-hand sides) buys a much cheaper
    Jacobian for the whole run.

    Three corrections over the first version, all of which matter for correctness
    rather than speed:

    1. The probe calls `derivative_pure`, not `derivative`. With the raw right-hand
       side the 2n probes overwrite the contact memory 2n times before the solve
       has even started.
    2. `t_s` is a argument (it used to be hard-coded to 0.0 inside). It happens to
       be 0.0 at the call site today, but a template probed at the wrong time is
       silently wrong once the profile lookup starts depending on it.
    3. The probe is unioned with a skeleton that holds regardless of contact state:
       `q' = v` is exact so the (q, q) block is structurally zero, and every
       `Connector` couples `support(jac) × support(jac)` in both the stiffness and
       the damping block. The probe can legitimately miss the latter when a link is
       momentarily unloaded (`stiffness * extension == 0` by cancellation) even
       though damping still couples it.

    Residual risk, deliberately left for the analytic Jacobian: columns that only
    light up through contact (which rail body, which track DOF) are still inferred
    from the probe state alone. At t=0 all patches are active in the production
    cases, so the probe sees them; a case that starts on a gap would not.
    """
    size = state.size
    dof = dynamics.dimension
    base = dynamics.derivative_pure(t_s, state)
    probe = np.empty((size, size))
    step = 1e-7 * np.maximum(1.0, np.abs(state))
    for index in range(size):
        trial = state.copy()
        trial[index] += step[index]
        probe[:, index] = (dynamics.derivative_pure(t_s, trial) - base) / step[index]
    mask = np.abs(probe) > 1e-12 * max(1.0, float(np.max(np.abs(probe))))

    skeleton = np.zeros((size, size), dtype=bool)
    skeleton[:dof, dof:] = np.eye(dof, dtype=bool)
    for link in dynamics.connectors:
        coupled = dof + np.flatnonzero(np.abs(link.jacobian) > 0.0)
        if coupled.size:
            skeleton[np.ix_(coupled, coupled - dof)] = True
            skeleton[np.ix_(coupled, coupled)] = True

    return mask | skeleton


def _integrate_vehicle(case: VehicleCase, dynamics: VehicleDynamics) -> VehicleResult:
    cfg, run = case.vehicle, case.run
    direction = 1 if cfg.travel_speed_m_s >= 0 else -1
    for rail in case.rails:
        for body in rail.contact_bodies:
            for t in (0.0, run.duration_s):
                x = run.x_start_m + cfg.axle_offsets_m[rail.axle_index] + cfg.travel_speed_m_s * t
                if body.active_at(x):
                    body.series.sample(x, direction)
    q = np.array(case.initial_q, dtype=float)
    v = np.array(case.initial_v, dtype=float)
    static_residual_n = None
    if case.equilibrate_vertical:
        q, static_residual_n = _static_vertical_equilibrium(case, dynamics, q, v)
    initial = np.concatenate((q, v))
    count = int(math.ceil(run.duration_s / run.output_step_s))
    times = np.linspace(0, run.duration_s, count + 1)
    rhs = dynamics.derivative_pure if run.method in {"BDF", "Radau"} else dynamics.derivative
    solver_options: dict[str, object] = {}
    if run.jacobian == "sparse_fd":
        solver_options["jac_sparsity"] = _rhs_sparsity(dynamics, initial, 0.0)
    elif run.jacobian == "analytic":
        from .jacobian import JacobianAssembler
        assembler = JacobianAssembler(dynamics)
        solver_options["jac"] = lambda t, y: assembler.full(
            float(t), y[:dynamics.dimension], y[dynamics.dimension:])
    if run.refine_peak:
        solver_options["dense_output"] = True
    solution = solve_ivp(rhs, (0, run.duration_s), initial,
                         method=run.method, t_eval=times, rtol=run.rtol, atol=run.atol,
                         max_step=run.max_solver_step_s, **solver_options)
    if not solution.success or solution.y.shape[1] != len(times) or not np.all(np.isfinite(solution.y)):
        raise SimulationFailure(f"v2 {run.method} integration failed: {solution.message}")
    n = dynamics.dimension
    positions, velocities = solution.y[:n, :].T, solution.y[n:, :].T
    contact_history = []
    peak_normal = {rail.id: 0.0 for rail in case.rails}
    active = {rail.id: 0 for rail in case.rails}
    max_depth = max_friction_excess = 0.0
    max_hertz_depth = max_settlement = 0.0
    edge_active = 0
    energies = []
    max_translation_balance_error_n = 0.0
    max_modal_projection_error_w = 0.0
    total_weight = (4 * cfg.wheelset.mass_kg + 2 * cfg.bogie.mass_kg + cfg.carbody.mass_kg) * cfg.gravity_m_s2
    for t, position, velocity in zip(times, positions, velocities):
        force, contacts = dynamics.evaluate(float(t), position, velocity)
        contact_history.append(contacts)
        energies.append(dynamics.mechanical_energy_j(position, velocity, contacts))
        if case.track_kind in {"rigid", "local_compliant", "two_layer", "layered"}:
            # Every body's lateral and vertical coordinates, wherever the topology put them.
            topology = dynamics.topology
            bodies = (*topology.wheelsets(), *topology.bogies(), topology.carbody())
            y_indices = [topology.require(body.id, "y") for body in bodies]
            z_indices = [topology.require(body.id, "z") for body in bodies]
            if case.track_kind == "local_compliant":
                y_indices += [topology.body_dimension + 2 * i for i in range(len(case.rails))]
                z_indices += [topology.body_dimension + 2 * i + 1 for i in range(len(case.rails))]
            elif case.track_kind == "two_layer":
                for i in range(len(case.rails)):
                    y_indices += [topology.body_dimension + 4 * i, topology.body_dimension + 4 * i + 2]
                    z_indices += [topology.body_dimension + 4 * i + 1, topology.body_dimension + 4 * i + 3]
            elif case.track_kind == "layered":
                stride = 2 * (1 + len(case.track_layers))
                for i in range(len(case.rails)):
                    for j in range(1 + len(case.track_layers)):
                        y_indices.append(topology.body_dimension + stride * i + 2 * j)
                        z_indices.append(topology.body_dimension + stride * i + 2 * j + 1)
            reaction = dynamics.track.support_reaction(position, velocity,
                [(contacts[rail.id].wheel_force_y_n, contacts[rail.id].wheel_force_z_n)
                 for rail in case.rails])
            assert reaction is not None
            max_translation_balance_error_n = max(max_translation_balance_error_n,
                abs(sum(force[y_indices]) + reaction[0]),
                abs(sum(force[z_indices]) + reaction[1] + total_weight))
        else:
            assert case.modal_track is not None
            for rail_index, rail in enumerate(case.rails):
                response = contacts[rail.id]
                x = run.x_start_m + cfg.travel_speed_m_s * float(t) + cfg.axle_offsets_m[rail.axle_index]
                py, pz, _, _ = case.modal_track.shapes[rail.template_id].sample(x)
                rail_force = dynamics.track.contact_reaction(rail_index, x,
                    response.wheel_force_y_n, response.wheel_force_z_n)
                power_error = float(rail_force @ velocity[topology.body_dimension:] +
                                    response.wheel_force_y_n * (py @ velocity[topology.body_dimension:]) +
                                    response.wheel_force_z_n * (pz @ velocity[topology.body_dimension:]))
                max_modal_projection_error_w = max(max_modal_projection_error_w, abs(power_error))
        for rail in case.rails:
            response = contacts[rail.id]
            peak_normal[rail.id] = max(peak_normal[rail.id], response.normal_force_n)
            active[rail.id] += int(response.active)
            if response.geometry:
                max_depth = max(max_depth, response.geometry.penetration_m)
                max_hertz_depth = max(max_hertz_depth, response.hertz_penetration_m)
                max_settlement = max(max_settlement, response.support_settlement_m)
                edge_active += int(response.active and response.geometry.edge_limited)
            max_friction_excess = max(max_friction_excess,
                                      math.hypot(response.longitudinal_force_n,
                                                 response.lateral_tangent_force_n) -
                                      case.contact.friction_coefficient * response.normal_force_n)
    # B2: the recorded peak is a sampling artefact of output_step_s, not an
    # integration error -- a 4x finer integration step at the same output spacing
    # moves the frog peak by +0.005 %, while a 10x finer *output* grid moves it by
    # +2.571 % (docs/B2_EVENT_INTEGRATION_2026-10-22.md).  Re-evaluating the dense
    # interpolant at the accepted steps recovers that peak with no extra RHS.
    peak_step = {rail.id: 0.0 for rail in case.rails}
    dense = getattr(solution, "sol", None)
    if run.refine_peak and callable(dense):
        try:
            step_times = np.asarray(getattr(dense, "ts", solution.t), dtype=float)
            step_states = dense(step_times)
        except (ValueError, AttributeError):
            step_states = None
        if step_states is not None and np.all(np.isfinite(step_states)):
            for column, step_time in zip(step_states.T, step_times):
                step_position = column[:n]
                step_velocity = column[n:]
                _force, step_contacts = dynamics.evaluate(
                    float(step_time), step_position, step_velocity
                )
                for rail in case.rails:
                    peak_step[rail.id] = max(
                        peak_step[rail.id], step_contacts[rail.id].normal_force_n
                    )

    gates = {
        "solver_completed": True,
        "finite_states_and_forces": True,
        "vertical_preload_residual": bool(static_residual_n is None or static_residual_n <= 0.1),
        "penetration_within_case_limit": bool(max_depth <= run.maximum_penetration_m),
        "friction_bound": bool(max_friction_excess <= 1e-7),
        "no_edge_limited_active_contact": bool(edge_active == 0),
    }
    if case.track_kind == "modal":
        gates["modal_generalized_contact_power"] = bool(max_modal_projection_error_w <= 1e-6)
    else:
        gates["translational_action_reaction"] = bool(max_translation_balance_error_n <= 1e-6)
    summary = {
        "case_id": case.case_id, "case_purpose": case.purpose,
        "result_status": "numerically_checked" if all(gates.values()) else "numerical_gate_failed",
        "physics_validation_status": "unvalidated_against_measurement_or_Simpack",
        "vehicle_dof": topology.body_dimension, "total_dof": dynamics.dimension,
        "track_kind": case.track_kind, "track_dof": dynamics.track.dimension,
        "rail_patch_count": len(case.rails), "connector_count": len(dynamics.connectors),
        "gates": gates, "solver": {"method": run.method, "nfev": int(solution.nfev),
                                      "rtol": run.rtol, "atol": run.atol},
        "vertical_preload_max_residual_n": static_residual_n,
        "max_translation_balance_error_n": (None if case.track_kind == "modal" else float(max_translation_balance_error_n)),
        "max_modal_contact_power_error_w": (float(max_modal_projection_error_w) if case.track_kind == "modal" else None),
        "max_penetration_m": max_depth, "max_friction_excess_n": max_friction_excess,
        "max_hertz_penetration_m": max_hertz_depth,
        "max_support_settlement_m": max_settlement,
        "edge_limited_active_output_samples": edge_active,
        "peak_normal_force_n": peak_normal, "active_output_samples": active,
        "peak_normal_force_step_resolved_n": peak_step,
        "initial_mechanical_energy_j": energies[0], "final_mechanical_energy_j": energies[-1],
        "energy_change_j": energies[-1] - energies[0],
        "note": "Prescribed longitudinal motion and profile variation can do external work; energy difference alone is not a conservation test.",
    }
    return VehicleResult(times, positions, velocities, contact_history, summary)


def save_vehicle_result(case: VehicleCase, result: VehicleResult,
                        output_dir: str | Path) -> tuple[Path, Path]:
    target = Path(output_dir).resolve()
    target.mkdir(parents=True, exist_ok=True)
    snapshot = target / "case_snapshot.json"
    data = case.source_path.read_bytes()
    if hashlib.sha256(data).hexdigest() != case.case_sha256:
        raise SimulationFailure("v2 case changed during simulation")
    for path, digest in case.asset_hashes.items():
        if hashlib.sha256(Path(path).read_bytes()).hexdigest() != digest:
            raise SimulationFailure(f"v2 profile changed during simulation: {path}")
    snapshot.write_bytes(data)
    names = [f"axle{i + 1}_{name}" for i in range(4) for name in ("y_m", "z_m", "roll_rad", "spin_rad", "yaw_rad")]
    names += [f"bogie{i + 1}_{name}" for i in range(2) for name in ("y_m", "z_m", "roll_rad", "pitch_rad", "yaw_rad")]
    names += [f"carbody_{name}" for name in ("y_m", "z_m", "roll_rad", "pitch_rad", "yaw_rad")]
    names += TrackKernel(case.track_kind, case.rails, case.modal_track,
                         case.track_layers).state_names
    columns = ["time_s", *[f"axle{i + 1}_x_m" for i in range(4)], *names,
               *[name + "_per_s" for name in names]]
    for rail in case.rails:
        columns += [f"{rail.id}_{field}" for field in ("normal_n", "fx_n", "fy_n", "fz_n",
                                                       "penetration_m", "active")]
    history = target / "history.csv"
    with history.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(columns)
        for t, q, v, contacts in zip(result.times_s, result.positions, result.velocities, result.contacts):
            row = [float(t), *[case.run.x_start_m + case.vehicle.travel_speed_m_s * float(t) + offset
                               for offset in case.vehicle.axle_offsets_m], *map(float, q), *map(float, v)]
            for rail in case.rails:
                response = contacts[rail.id]
                row += [response.normal_force_n, response.longitudinal_force_n,
                        response.wheel_force_y_n, response.wheel_force_z_n,
                        response.geometry.penetration_m if response.geometry else 0.0,
                        int(response.active)]
            writer.writerow(row)
    manifest = {
        "software": f"Velch {__version__}", "case_sha256": case.case_sha256,
        "case_snapshot": str(snapshot), "input_asset_sha256": case.asset_hashes,
        "track_model": {"kind": case.track_kind, "track_dof": TrackKernel(
            case.track_kind, case.rails, case.modal_track, case.track_layers).dimension,
            "modal_count": case.modal_track.mode_count if case.modal_track else 0,
            "modal_exchange_schema": "velch-modal-track-v1" if case.modal_track else None},
        "state_order": names, "units": {"time": "s", "x": "m", "translation": "m",
                                          "rotation": "rad", "force": "N", "penetration": "m"},
        "summary": result.summary,
    }
    manifest_path = target / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return history, manifest_path
