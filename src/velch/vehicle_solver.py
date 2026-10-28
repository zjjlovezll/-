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
from dataclasses import dataclass, replace
from pathlib import Path

import numpy as np
from scipy.integrate import solve_ivp
from scipy.optimize import least_squares, root

from . import __version__
from .contact import (ContactGeometry, ContactResponse, deduplicate_contacts, evaluate_contact,
                      find_graph_contact, merge_contact_responses)
from .contact_search import masked_sample_around
from .solver import SimulationFailure
from .topology import Topology, topology_for
from .track_models import TrackKernel
from .vehicle import VehicleCase
from .modal_coupling import ModalContact, TreadRing
from .speed import SpeedSchedule, SpeedScheduleError
from .wheel_modes import ModalAssembly, ModalBlock, modal_channel_names


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
    #: Row that senses the *rate*, when it is not the same row the force pushes on.  The
    #: gyroscopic term ``−2Ω G q̇`` couples one mode's force to another mode's velocity, and
    #: that is antisymmetric: no spring-damper row built from one vector can express it.
    #: ``None`` keeps the symmetric ``k``/``c`` behaviour every existing element relies on.
    speed_jacobian: np.ndarray | None = None

    @property
    def speed_row(self) -> np.ndarray:
        return self.jacobian if self.speed_jacobian is None else self.speed_jacobian

    def extension(self, q: np.ndarray) -> float:
        return float(self.jacobian @ q) - self.rest

    def speed(self, v: np.ndarray) -> float:
        return float(self.speed_row @ v)

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
    #: Analytic ``force/mass`` per emitted acceleration channel, one row per frame.  The channel
    #: list travels with the numbers: deriving the column names a second time in the writer is
    #: exactly how a table ends up with one more column than it has values.
    accelerations: np.ndarray | None = None
    acceleration_names: tuple[str, ...] = ()


#: Time constant of the wheel-spin servo, seconds.  Slow enough for DOP853 at
#: ``max_step=1e-4`` (20 steps per constant) and fast enough that the slip is gone long
#: before the creep law can saturate on it.
SPIN_TIME_CONSTANT_S = 2.0e-3
# Residual the seat returns when a least-squares trial point would trip a contact guard.
# The residual is `force / 1e5` and the acceptance test is `max |residual| * 1e5 <= 0.1` N,
# so 1.0 is a 1e8 N barrier: far above any real residual, and unmistakably rejected.
_SEAT_BARRIER_RESIDUAL = 1.0


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
        # One source for v(t) and x(t).  A constant profile returns exactly
        # ``cfg.travel_speed_m_s``, so every expression below stays bit-identical to the
        # literal it replaced; a varying profile is carried here and refused in
        # ``simulate_vehicle`` until the wheel spin tracks the speed (audit A4).
        self._schedule = getattr(case, "speed_schedule", None) or SpeedSchedule.constant(
            abs(float(cfg.travel_speed_m_s)), duration_s=float(case.run.duration_s))
        self._direction = 1.0 if float(cfg.travel_speed_m_s) >= 0.0 else -1.0
        # Spin tracking: a first-order servo on each wheelset's rotation.  With the inertia as
        # the gain the time constant is exactly SPIN_TIME_CONSTANT_S whatever the wheelset, and
        # the torque is bounded by I * (v / r) / tau, i.e. a few kN*m, well inside the creep
        # law.  It is off for a constant profile so that path stays bit-identical.
        self.spin_control = bool(getattr(case.run, "spin_control", False)
                                 or not self._schedule.is_constant)
        # How often the static search bounced off a contact guard.  Reported so a seat that
        # only converges at the barrier is visible instead of merely plausible.
        self.seat_barrier_hits = 0
        # 1/R of the equivalent-straight curve, signed the way the lateral force is: zero for
        # every straight case, so the curvature term in the creep slip is inert and the archived
        # numbers cannot move.  This is the term that lets a wheelset steer: the two contact
        # points of one axle then travel different arc lengths, exactly as they do in reality.
        radius = getattr(case.run, "curve_radius_m", None)
        # One object decides where the line is and which way it bends; the creep term and the
        # body force both read it, so they cannot disagree about handedness.  The curvature is
        # taken from the line when the case carries one -- for ``y = s^2/(2R)`` that is exactly
        # ``+1/R``, the same number the radius route used, so only the *force* sign moves.
        from .alignment import alignment_for
        self.alignment = alignment_for(case)
        self._curvature_1_per_m = float(self.alignment.curvature_1_per_m) if radius else 0.0

        # The topology decides the state vector: which bodies exist, what each carries, and
        # in which order.  With no node table it reproduces the frozen 35-slot layout.
        self.topology: Topology = topology_for(case)
        #: A curve is something a vehicle *enters*, not something it stands on.  At zero speed
        #: there is no lateral equilibrium on a curved track -- creep is what steers a wheelset
        #: round a curve (Elkins & Gostling, Vehicle System Dynamics 1977, quasi-static curving
        #: theory) -- so the seat is solved against the equivalent straight and the placement
        #: takes effect once time starts.  Measured at R = 1100 m: seating with the placement on
        #: stalled every seed (cond 3.76e12, all residuals 2.39 = 240 kN), while seating with it
        #: off converges to 1.07e-12 with all eight patches at 65.47 um.
        self.placement_enabled = True
        self.track = TrackKernel(case.track_kind, case.rails, case.modal_track,
                                 case.track_layers, offset=self.topology.body_dimension,
                                 placement=self._guarded_placement(self._curve_placement()))
        self.mass = self.topology.mass_array(self.track.mass)
        # Flexible-wheelset modal coordinates go *after* the track block, never among the
        # bodies: their mass of 1.0 is a normalisation, and ``total_weight`` adds up
        # ``body.mass_kg`` — 31 modes on four wheelsets would inject 124 kg of phantom mass
        # into the action-reaction gate.  With no ``flexible_wheelset`` block in the case this
        # is None and every line below behaves exactly as before.
        self.modal = self._build_modal_block()
        if self.modal is not None:
            self.mass = np.concatenate((self.mass, self.modal.mass()))
        # Projection of a contact force onto the mode shapes.  Without it the modal block only
        # pushes back on itself and every modal coordinate stays at zero, which is what the
        # first flexible run measured.  Built from the same mode sets the blocks were.
        self.contact_coupling: ModalContact | None = self._build_modal_contact()
        #: axle -> {coordinate: state index}.  Resolved by name, because a layout may put ``x``
        #: in front of ``y`` and every ``wh + k`` written by hand then reads the wrong number.
        self._wheel_axes = {
            body.axle: {axis: self.topology.require(body.id, axis) for axis in body.dof}
            for body in self.topology.wheelsets()
        }
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
    def speed_schedule(self) -> SpeedSchedule:
        """The travel speed as a function of time: the one source for ``v(t)`` and ``x(t)``."""

        return self._schedule

    def cant_sin_theta(self) -> float:
        """``sin(theta)`` of the cant plane: the raised rail is the outside one, at ``-y``."""
        cant = float(getattr(self.case.run, "curve_cant_m", 0.0) or 0.0)
        gauge = 2.0 * abs(float(self.case.wheels[0].lateral_offset_m)) if self.case.wheels else 1.5
        return cant / gauge if gauge else 0.0

    def curve_lateral_force_n(self, speed_m_s: float,
                              station_m: float = 0.0) -> float:
        """Total lateral body force at one station.

        A diagnostic: the *gate* reads ``curve_lateral_applied_n``, which ``evaluate`` records at
        each body's own station, because a single station cannot represent a line whose curvature
        starts part-way along the run (station zero is the straight approach, where this returns
        exactly zero).
        """
        sign = float(getattr(self.case.run, "curve_lateral_sign", 1.0))
        sin_theta = self.cant_sin_theta()
        gravity = float(self.case.vehicle.gravity_m_s2)
        return sign * sum(
            self.alignment.lateral_force_n(body.mass_kg, speed_m_s, gravity, sin_theta,
                                           station_m=station_m)
            for body in self.topology.bodies if "y" in body.dof)

    def speed_at(self, t_s: float) -> float:
        """Signed travel speed at ``t_s``, in m/s."""

        return self._direction * self._schedule.v_at(t_s)

    def x_at(self, t_s: float) -> float:
        """Mileage of the vehicle reference point at ``t_s``, in m."""

        return self.case.run.x_start_m + self._direction * self._schedule.x_at(t_s)

    def station_m(self, rail, t_s: float, q: np.ndarray) -> float:
        """Station of a wheel's contact patch at time ``t_s``.

        One implementation, because the patch evaluation and the action-reaction gate must agree
        on where the steel is: a layout that solves the wheelset's longitudinal coordinate moves
        the patch by that coordinate, and a second copy of this formula would silently compare a
        force at one station with a reaction at another.
        """

        cfg = self.case.vehicle
        x = self.x_at(t_s) + cfg.axle_offsets_m[rail.axle_index]
        axis = self._wheel_axes[rail.axle_index].get("x")
        if axis is not None:
            x = x + float(q[axis])
        return x

    @property
    def dimension(self) -> int:
        return len(self.mass)

    @property
    def dof(self) -> int:
        """Number of vehicle coordinates; the track block starts here."""

        return self.topology.body_dimension

    def _build_modal_block(self) -> ModalAssembly | None:
        """Lay out one modal block per wheelset after the track block."""

        modes = getattr(self.case, "wheel_modes", None)
        if not modes:
            return None
        speed = abs(float(self.case.vehicle.travel_speed_m_s))
        offset = self.topology.body_dimension + len(self.track.mass)
        blocks = []
        for axle in sorted(modes):
            mode_set = modes[axle]
            blocks.append(ModalBlock(modes=mode_set, offset=offset, prefix=f"axle{axle + 1}",
                                     spin_rad_s=speed / mode_set.radius_m))
            offset += len(mode_set.modes)
        return ModalAssembly(tuple(blocks))

    def _build_modal_contact(self) -> ModalContact | None:
        """One tread ring per wheel side, plus the axle → block offset map.

        Every axle shares the same mode set in practice, so the two rings are built once from
        the first axle's shapes.  The offsets are per axle because each axle owns its own block.
        """

        modal = self.modal
        if modal is None:
            return None
        blocks = list(modal.blocks)
        if not blocks:
            return None
        first = blocks[0].modes
        if not first.has_shapes:
            # A frequency-only set (thesis table 2-3) cannot route a force anywhere; the modal
            # block still runs, it simply has no excitation.  Say so instead of raising, so an
            # empty-shape run stays reproducible.
            return None
        rings = {side: TreadRing.from_modes(first, side) for side in (-1, 1)}
        offsets = {}
        for block in blocks:
            axle = int(str(block.prefix).replace("axle", "")) - 1
            offsets[axle] = block.offset
        return ModalContact(rings=rings, offsets=offsets)

    def _build_connectors(self) -> tuple[Connector, ...]:
        """Turn the topology's link specs into connectors, one row each."""

        return tuple(
            Connector(spec.name, spec.axis, spec.stiffness, spec.damping, spec.rest,
                      spec.jacobian(self.dimension), spec.law,
                      spec.speed_jacobian(self.dimension))
            for spec in self.topology.link_specs
        )

    def _guarded_placement(self, placement):
        """Wrap a placement so :attr:`placement_enabled` can switch it off for the seat."""
        if placement is None:
            return None

        def guarded(rail_index: int, x_m: float):
            if not self.placement_enabled:
                return (0.0, 0.0, 0.0)
            return placement(rail_index, x_m)

        return guarded

    def _curve_placement(self):
        """Where the design centreline sits, as a function of mileage, for a curved case.

        A constant-radius curve through ``x_start_m`` has ``y(s) = s^2 / (2R)`` with ``s`` measured
        from the start of the run, so ``dy/ds = s / R``.  Handing that to the track kernel is what
        lets the wheels yaw along the curve: at R = 350 m the footprint is 10 m long, so the far
        axle is 1.17 m to the side of the near one, and a model that keeps the rails straight has
        to drag it there through the flange.

        Cant adds a rail-to-rail height difference: the outer rail rises by half the gauge times
        ``sin(theta)``.  With the centre of the curve on the -y side, the outer rail is the right
        one.  Returns ``None`` unless ``run.curve_geometry`` is set, so every existing case keeps
        its design line at zero and its numbers bit for bit.
        """

        run = self.case.run
        radius = getattr(run, "curve_radius_m", None)
        if radius is None or not getattr(run, "curve_geometry", False):
            return None
        radius = float(radius)
        if radius == 0.0:
            raise SimulationFailure("curve_radius_m must not be zero")
        cant = float(getattr(run, "curve_cant_m", 0.0) or 0.0)
        # Cant belongs to the track plane, so on this route it is published as *both* things the
        # plane does: each rail surface is turned with it by ``roll_rails`` at load time, and the
        # outer rail centre rises by half the gauge times sin(phi).  The vehicle frame is rolled by
        # the same angle in ``_place_on_alignment``.  Publishing only one of the two was measured
        # to fail: the level difference without the rotation put the wheel on its flange root, and
        # the rotation alone could not seat at all (R = 1100 m, 107 mm cant, every seed).
        gauge = 2.0 * abs(float(self.case.wheels[0].lateral_offset_m)) if self.case.wheels else 1.5
        theta = math.asin(max(-1.0, min(1.0, cant / gauge))) if gauge else 0.0
        # Both halves of a cant must be published or neither is: the outer rail stands ``b sin(phi)``
        # higher *and* the section is rolled by ``phi`` (``roll_rails`` at load).  With the rise pinned
        # to zero the wheel met a rotated surface at the wrong height, which measured as a 103 mm
        # peak-to-peak gap in round 37.
        rise = abs(0.5 * gauge * math.sin(theta))
        rails = tuple(self.case.rails)

        def placement(rail_index: int, x_m: float) -> tuple[float, float, float]:
            s = _arc_parameter_m(run, x_m)
            # The centre of ``y(s) = s^2/(2R)`` is at +y, so the OUTER rail is the one on the -y
            # side -- the rail the solver labels ``left`` -- and it is that one that is raised.
            # Measured with the labels the other way round: the right (inner) rail came out at
            # +54.799 mm and the left (outer) at -53.721 mm, i.e. the track was canted *against*
            # the curve; a canted line then reads as "one side unloaded", which is how a wrong
            # side hides as a convergence failure rather than as a sign error.
            outer = "right" not in str(rails[rail_index].id).lower()
            return s * s / (2.0 * radius), (rise if outer else -rise), s / radius

        return placement

    def evaluate(self, t_s: float, q: np.ndarray, v: np.ndarray) -> tuple[np.ndarray, dict[str, ContactResponse]]:
        cfg = self.case.vehicle
        force = np.zeros(self.dimension)
        for body in self.topology.wheelsets():
            force[self.topology.require(body.id, "spin")] += cfg.drive_torque_per_wheelset_nm
        # Gravity for every body the topology knows about.  Naming the three legacy kinds dropped
        # the axle boxes' weight, which made the action/reaction gate read 3.8 kN short.
        for body in self.topology.bodies:
            if "z" in body.dof:
                force[self.topology.require(body.id, "z")] -= body.mass_kg * cfg.gravity_m_s2
        # Curve, as the equivalent straight track: a constant-radius curve is, in the
        # vehicle's own frame, a lateral body force ``m v^2 / R`` plus a gravity component
        # ``m g sin(theta)`` along the cant.  Without this term a curved station table just
        # drags the wheels onto the flange until the contact-slope guard fires (measured:
        # `graph slope limit at axle1_left/left:main, x=41.2461871 m`).
        curve = getattr(self.case.run, "curve_radius_m", None)
        # Two routes, one body force.  On the *force* route the track stays straight and the curve
        # enters here as an equivalent-straight body force ``m (v^2/R - g sin(theta))``.  On the
        # *geometry* route the track itself is curved and the plane is tilted (rise + roll +
        # surface rotation), so the rails supply the centripetal force and no body force is added:
        # adding it there double-counts both terms and the seat had no solution because of it.
        #: What the curving branch of this very evaluation added, so the action-reaction gate
        #: reads the applied number instead of restating the expression (a restated force can
        #: disagree with the applied one about the sign of the curve, and did).
        self.curve_lateral_applied_n = 0.0
        if curve and self.placement_enabled and not _placement_enabled(self.case.run):
            speed = abs(self.speed_at(t_s))
            cant = float(getattr(self.case.run, "curve_cant_m", 0.0) or 0.0)
            gauge = 2.0 * abs(float(self.case.wheels[0].lateral_offset_m)) if self.case.wheels else 1.5
            sin_theta = cant / gauge if gauge else 0.0
            for body in self.topology.bodies:
                if "y" not in body.dof:
                    continue
                # One expression, derived from the line itself (see ``alignment.py``): with
                # ``kappa > 0`` the centre sits at +y, so the inertia force points towards -y and
                # the raised outside rail (-y) adds +y.  ``curve_lateral_sign`` stays as a
                # diagnostic multiplier and defaults to the value every archived case used.
                sign = float(getattr(self.case.run, "curve_lateral_sign", 1.0))
                lateral = sign * self.alignment.lateral_force_n(
                    body.mass_kg, speed, cfg.gravity_m_s2, sin_theta,
                    station_m=(self.x_at(t_s) + _body_offset_m(self.case, self.topology, body, q))
                    if self.alignment.has_line else 0.0)
                force[self.topology.require(body.id, "y")] += lateral
                self.curve_lateral_applied_n += float(lateral)
        if self.spin_control:
            radius = float(cfg.nominal_wheel_radius_m)
            target = self.speed_at(t_s) / radius
            for axle in range(len(cfg.axle_offsets_m)):
                # The spin coordinate belongs to the topology, not to the contact-axis map
                # (which only carries x/y/z when the layout declares them).
                spin = self.topology.require(self.topology.wheelset_id(axle), "spin")
                # Inertia as the gain: the same time constant on every axle.
                force[spin] += self.mass[spin] * (target - float(v[spin])) / SPIN_TIME_CONSTANT_S
        for connector in self.connectors:
            force += connector.force(q, v)
        # The track block is no longer the tail of the vector once modal coordinates exist, so
        # add it by length rather than by open-ended slice.  Without modes the two are identical.
        track_force = self.track.internal_force(q, v)
        force[self.dof:self.dof + len(track_force)] += track_force
        if self.modal is not None:
            start = self.modal.offset
            force[start:] += self.modal.force(q[start:], v[start:])
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
            wheel_axes = self._wheel_axes[rail.axle_index]
            for _body_id, geometry, response in body_results:
                force[y_index] += response.wheel_force_y_n
                force[z_index] += response.wheel_force_z_n
                # The longitudinal tangential force used to be dropped on the floor: with x
                # prescribed there was nowhere to put it.  A layout that solves x has to carry
                # it, or the axle-box longitudinal channel can never be anything but zero.
                if "x" in wheel_axes and self.case.run.longitudinal_force:
                    force[wheel_axes["x"]] += response.longitudinal_force_n
                force[roll_index] += response.wheel_roll_moment_nm
                force[spin_index] += response.wheel_spin_moment_nm
                if geometry and yaw_index is not None:
                    force[yaw_index] -= geometry.lever_y_m * response.longitudinal_force_n
                # The same normal force, seen by the mode shapes: without this projection the
                # modal coordinates would be driven by nothing at all.
                coupling = self.contact_coupling
                if (coupling is not None and geometry is not None
                        and coupling.has(rail.axle_index)):
                    side = -1 if "left" in str(rail.template_id) else 1
                    ring = coupling.rings[side]
                    force[coupling.block(rail.axle_index)] += coupling.generalised(
                        rail.axle_index, side,
                        ring.bottom_point(geometry.penetration_m),
                        (response.longitudinal_force_n,
                         response.wheel_force_y_n, response.wheel_force_z_n),
                    )
                reaction = self.track.contact_reaction(rail_index, x,
                                                       response.wheel_force_y_n,
                                                       response.wheel_force_z_n)
                force[self.dof:self.dof + len(reaction)] += reaction
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

    def _deformed_profile(self, wheel, rail, q: np.ndarray):
        """Return the wheel profile with the tread displacement of the mode shapes added.

        This is the second half of the flexible contact: the steel *moves*, so the search has to
        run on the moved surface.  Gao & Dai (AMM 105-107, 2012, 1284) build a contact line from
        the deformed normal of every rolling circle and pick the point of least vertical
        distance; Chen Jiayin §2.2 and VSD 2017 write the same thing as ``x = x_rigid + Phi q``.
        Deforming the profile gets all three quantities from one search — position, slope and
        depth — instead of correcting the depth and the normal afterwards, where the three can
        disagree with each other.

        Two conventions matter and neither is guessable from the numbers:

        * the profile's own ``y_m`` is measured from the wheel plane and points *outboard* for
          both wheels, while the tread ring is in CAD (assembly) coordinates where +y points to
          the right.  The left wheel is therefore mirrored: its local +y is physical -y.  The
          flange settles it — both profiles peak in ``z`` at ``y = -0.045``, and the flange is
          inboard, so local -y is inboard on the right wheel and local +y is inboard on the left.
        * zero modal coordinate returns ``wheel.profile`` itself, so a rigid case keeps passing
          the same object to the search and its trajectory stays bit-identical.
        """

        coupling = self.contact_coupling
        if coupling is None or not coupling.has(rail.axle_index):
            return wheel.profile
        side = -1 if "left" in str(rail.template_id) else 1
        ring = coupling.rings[side]
        block_q = np.asarray(q, dtype=float)[coupling.block(rail.axle_index)]
        if not np.any(block_q):
            return wheel.profile
        shift = ring.tread_shift(block_q, side * np.asarray(wheel.profile.y_m, dtype=float))
        if not np.all(np.isfinite(shift)):
            raise SimulationFailure(
                f"non-finite tread deformation at {rail.id}: max|dz|={np.max(np.abs(shift))!r} m")
        return replace(wheel.profile, z_m=np.asarray(wheel.profile.z_m, dtype=float) + shift)

    def _out_of_round_shift(self, rail, q: np.ndarray) -> float:
        """Radial deviation of this wheel at its current rotation angle, in metres.

        The polygon is a property of the wheel, not of the track, so it survives a change of
        nominal rolling radius.  Returned as the *radius* offset; the caller flips the sign for a
        profile whose ``z`` points down.
        """

        polygon = getattr(self.case, "wheel_polygon", None)
        if polygon is None:
            return 0.0
        axis = self._wheel_axes[rail.axle_index].get("spin")
        if axis is None:
            return 0.0
        return float(polygon.radius_offset_m(float(q[axis])))

    def _tilted_geometry(self, geometry: ContactGeometry, rail, q: np.ndarray,
                         lateral_m: float) -> ContactGeometry:
        """Turn the contact normal by the slope of the deformed tread.

        The depth is already inside the geometry — the search ran on the deformed profile, so the
        point it picked *is* where the moved steel touches.  What the search cannot know is that
        the deformed surface is tilted: ``find_graph_contact`` takes its normal from the rail's own
        slope grid, so a wheel whose tread has a lateral slope would keep a normal that does not
        belong to it.  Rotating normal and tangent together keeps the pair orthonormal, and the
        rotation is by ``-atan(slope)`` because a tread ``z = f(y)`` has normal
        ``(-f', 1)/sqrt(1 + f'^2)``.
        """

        coupling = self.contact_coupling
        if coupling is None or not coupling.has(rail.axle_index):
            return geometry
        side = -1 if "left" in str(rail.template_id) else 1
        ring = coupling.rings[side]
        block_q = np.asarray(q, dtype=float)[coupling.block(rail.axle_index)]
        if not np.any(block_q):
            return geometry
        slope = ring.tread_slope(block_q, lateral_m)
        if not math.isfinite(slope):
            raise SimulationFailure(f"non-finite tread slope at {rail.id}: {slope!r} rad")
        angle = math.atan(slope)
        cosine, sine = math.cos(angle), math.sin(angle)
        normal_y = cosine * geometry.normal_y - sine * geometry.normal_z
        normal_z = sine * geometry.normal_y + cosine * geometry.normal_z
        tangent_y = cosine * geometry.tangent_y - sine * geometry.tangent_z
        tangent_z = sine * geometry.tangent_y + cosine * geometry.tangent_z
        return replace(geometry, normal_y=normal_y, normal_z=normal_z,
                       tangent_y=tangent_y, tangent_z=tangent_z)

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
        axes = self._wheel_axes[rail.axle_index]
        wheel = self.wheels[rail.wheel_id]
        x = self.station_m(rail, t_s, q)
        travel = self.speed_at(t_s) + (float(v[axes["x"]]) if "x" in axes else 0.0)
        path = self.case.path
        # B040: the route's offset belongs in the *position*, not in the velocity.  A vehicle that
        # follows the design line has dq[y]/dt = 0 against the rail, so its lateral creep is zero --
        # `v * dy/ds` is the rate at which the curve transports a point of the reference frame through
        # Cartesian space, not a material sliding velocity.  Feeding it as creep saturated the contact
        # at t = 0: measured on the 18-turnout diverging route at 80 km/h, slip_lateral came out
        # +0.5737 / +0.5232 / +0.2205 m/s with every state velocity except spin exactly zero, giving
        # sum(Fy) = -36 939 N against the +21 842 N the curve needs, and the run tripped the slope
        # guard 2.29 m after the start.  With the rate forced to zero the same frame reads slip_lateral
        # 0.0000 and sum(Fy) = +292 N.  The straight cases have dy/ds = 0, so they are unchanged.
        lateral_extra = path.at(x) if path is not None else 0.0
        rail_y, rail_z, rail_vy, rail_vz = self.track.local_state(q, v, rail_index, x,
                                                                  self.speed_at(t_s))
        body_results = []
        steep: list[tuple[str, str, float]] = []
        # S9-1: the steel moves, so the contact is searched on the deformed tread.  Computed once
        # per patch because the deformation depends on the axle and the side, not on the body.
        profile = self._deformed_profile(wheel, rail, q)
        out_of_round = self._out_of_round_shift(rail, q)
        if out_of_round:
            # R(theta) = R0 + delta, and the profile's z is measured downwards (R = -z), so a
            # larger radius is a lower column.
            profile = replace(profile, z_m=np.asarray(profile.z_m, float) - out_of_round)
        side_sign = -1 if "left" in str(rail.template_id) else 1
        for body in bodies:
            if not body.active_at(x):
                continue
            sample = body.series.sample(x, direction)
            law = self.case.contact
            seed_y = seeds.get(body.id) if seeds else None
            if seed_y is None and seeds:
                seed_y = seeds.get("__rail__")
            search = self._contact_search_kwargs(
                q, wh, axes, wheel, lateral_extra, rail_y, rail_z, law)
            geometry = find_graph_contact(
                profile, sample, search_half_width_m=half_width,
                previous_y_m=seed_y, surface_key=(rail.id, body.id), **search,
            )
            if geometry is not None and not body.accepts_contact_y(geometry.y_m):
                # Attribution gate: a head whose running surface is not under the
                # wheel tread cannot carry load, however deep its crown measures.
                geometry = None
            if geometry is not None and self.contact_coupling is not None:
                geometry = self._tilted_geometry(
                    geometry, rail, q,
                    side_sign * (float(geometry.y_m)
                                 - float(wheel.lateral_offset_m + lateral_extra)))
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
                # A steep normal is not an error by itself.  With two-point contact the flange root
                # really does carry a near-vertical normal -- measured on the curved route:
                # n_y/n_z = 0.7216/0.6923, slope 1.04 -- and refusing it is exactly what made the
                # model unable to run a curve.  What the gate is for is the *single* steep point, a
                # search that has slid onto the flange nose with nothing left on the tread.  The
                # decision therefore moved below the loop and now requires the absence of any
                # shallow contact on this patch.
                steep.append((rail.id, body.id, x))
            response = self._contact_response(geometry, rail, x, q, v, travel, rail_vy, rail_vz)
            body_results.append((body.id, geometry, response))
            if (self.case.run.contact_two_point and geometry is not None
                    and geometry.penetration_m > 0.0):
                second = self._second_contact(
                    profile, sample, body, rail, geometry, search, q, v,
                    x=x, travel=travel,
                    wheel_y_offset_m=wheel.lateral_offset_m + lateral_extra,
                    rail_y=rail_y, rail_vy=rail_vy, rail_vz=rail_vz)
                if second is not None:
                    body_results.append((body.id, second[0], second[1]))
        if steep:
            shallow = any(
                item_geometry is not None and item_geometry.penetration_m > 0.0
                and abs(item_geometry.normal_y / item_geometry.normal_z)
                <= self.case.run.maximum_abs_contact_slope
                for _body_id, item_geometry, _response in body_results)
            if not shallow:
                steep_rail, steep_body, steep_x = steep[0]
                raise SimulationFailure(
                    f"graph slope limit at {steep_rail}/{steep_body}, x={steep_x:.9g} m")
        return (rail_index, rail, x), body_results

    def _contact_search_kwargs(
        self,
        q: np.ndarray,
        wh: int,
        axes: dict[str, int],
        wheel,
        lateral_extra: float,
        rail_y: float,
        rail_z: float,
        law,
    ) -> dict[str, object]:
        """Everything the contact search needs except the two bounded-search arguments.

        Kept as one dict because the second contact has to be searched with *exactly* the same
        policy as the first: two argument lists that drift apart would give the two points of a
        two-point contact different normals, stiffnesses or strip rules, and nothing downstream
        could tell.
        """

        cfg = self.case.vehicle
        return dict(
            wheel_y_m=float(q[wh]),
            wheel_z_m=cfg.wheel_center_height_m + float(q[axes["z"]]),
            wheel_roll_rad=float(q[axes["roll"]]),
            wheel_lateral_offset_m=wheel.lateral_offset_m + lateral_extra,
            rail_y_m=rail_y,
            rail_z_m=rail_z,
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
            normal_policy=law.normal_policy,
            strip_dy_m=law.strip_dy_m,
            strip_min_depth_m=law.strip_min_depth_m,
            strip_half_width_m=law.strip_half_width_m,
            strip_center_policy=law.strip_center_policy,
            curvature_policy=law.curvature_policy,
            partials=self.contact_partials,
        )

    def _contact_response(
        self,
        geometry: ContactGeometry | None,
        rail,
        x: float,
        q: np.ndarray,
        v: np.ndarray,
        travel: float,
        rail_vy: float,
        rail_vz: float,
    ) -> ContactResponse:
        """Force law for one contact, shared by the first point and the second.

        Curvature belongs to the *track*, not to the route that carries it.  An axle on a curve
        runs its two contacts on different arc lengths (+-v kappa b), and that is a kinematic fact
        in the vehicle's own frame -- which is exactly where the force route lives, with straight
        rails and m v^2 / R as the body force.  The term used to be gated on the placement, i.e.
        only the geometry route carried it, and that left each route owning half of a co-rotating
        frame: the geometry route placed the vehicle on an arc and pushed it with nothing
        (measured: 8/8 seated at 0.988..1.013x and then graph slope limit after 1.04 m of travel,
        R = 1100 m at 80 km/h), while the force route had the centripetal force and no arc-length
        difference.

        Turning it on for the force route needs the *seat* to be able to absorb the yaw moment it
        produces.  Without a yaw unknown the vertical-only seat read 4 of 8 wheels and 128 901 N
        (2x the 59 662 N share); with the wheelsets' yaw free the same balance is well posed,
        because the attack velocity travel * yaw gives the yaw row real stiffness whenever the
        vehicle is rolling.  See the `curved` branch of _static_vertical_equilibrium.
        """

        axes = self._wheel_axes[rail.axle_index]
        support = self._support
        return evaluate_contact(
            geometry, self.case.contact,
            wheel_v_y_m_s=float(v[axes["y"]]),
            wheel_v_z_m_s=float(v[axes["z"]]),
            wheel_roll_rate_rad_s=float(v[axes["roll"]]),
            wheel_spin_rate_rad_s=float(v[axes["spin"]]),
            rail_v_y_m_s=rail_vy, rail_v_z_m_s=rail_vz,
            travel_speed_m_s=travel,
            creep_attack_velocity_m_s=float(travel * q[axes["yaw"]]),
            support_compliance_m_per_n=(support.at(x) if support is not None else None),
            curvature_1_per_m=self._curvature_1_per_m,
        )

    def _second_contact(
        self,
        profile,
        sample,
        body,
        rail,
        primary: ContactGeometry,
        search: dict[str, object],
        q: np.ndarray,
        v: np.ndarray,
        *,
        x: float,
        travel: float,
        wheel_y_offset_m: float,
        rail_y: float,
        rail_vy: float,
        rail_vz: float,
    ) -> tuple[ContactGeometry, ContactResponse] | None:
        """The next-deepest contact on this wheel-rail side, if the surface leaves one.

        L12's two-point algorithms find every local minimum of the clearance.  The primary patch
        is pushed into a well and the ordinary search is run again, so the second point is found,
        refined and given a normal by the same policy as the first; the only extra decision is the
        exclusion window, which is what keeps two extrema inside one Hertzian footprint from being
        counted twice (the same rule ``duplicate_patch_window_m`` applies across rail bodies).
        """

        exclusion = float(self.case.run.contact_two_point_exclusion_m)
        masked = masked_sample_around(
            sample, center_y_m=float(primary.y_m) - float(rail_y), exclusion_m=exclusion)
        if masked is sample:
            return None
        geometry = find_graph_contact(
            profile, masked, search_half_width_m=None, previous_y_m=None, surface_key=None,
            **search)
        if geometry is None or geometry.penetration_m <= 0.0:
            return None
        if abs(float(geometry.y_m) - float(primary.y_m)) < exclusion:
            return None
        if abs(float(geometry.normal_y) / float(geometry.normal_z)) < float(
                self.case.run.contact_two_point_min_slope):
            # A second *flat* extremum is another patch of the same tread (the profile polyline
            # carries more than one maximum across its own crown), not a second body.  Counting it
            # would halve every contact and move the frozen anchor; only a steep surface -- a flange
            # root -- is a genuine second point of contact.
            return None
        if not body.accepts_contact_y(geometry.y_m):
            return None
        if self.contact_coupling is not None:
            side_sign = -1.0 if "left" in str(rail.template_id) else 1.0
            geometry = self._tilted_geometry(
                geometry, rail, q,
                side_sign * (float(geometry.y_m) - float(wheel_y_offset_m)))
        response = self._contact_response(
            geometry, rail, x, q, v, travel, rail_vy, rail_vz)
        if not response.active or response.normal_force_n <= 0.0:
            return None
        return geometry, response

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
        # Same traversal as the force loop: every body that has a vertical coordinate is lifted by
        # gravity, axle boxes included.  Summing only carbody + bogies + wheelsets left the eight
        # boxes (8 x 48.2 kg) out of the energy check while they were in the force balance.
        energy += cfg.gravity_m_s2 * sum(
            body.mass_kg * q[topology.require(body.id, "z")]
            for body in topology.bodies if "z" in body.dof)
        energy += sum(link.potential(q) for link in self.connectors)
        energy += self.track.potential_j(q)
        if self.modal is not None:
            # Kinetic part already arrived through ``self.mass`` (unit modal mass); this is the
            # elastic energy the modal block stores, so an energy check still closes with modes on.
            start = self.modal.offset
            energy += self.modal.potential(q[start:])
        for responses in self._body_cache.values():
            for response in responses:
                if response.geometry and response.geometry.penetration_m > 0:
                    energy += 0.4 * self.case.contact.normal_stiffness_n_m_1p5 * response.geometry.penetration_m ** 2.5
        return float(energy)


def _placement_enabled(run) -> bool:
    """Whether the vehicle is moved onto the alignment.

    ``run.curve_placement`` wins when it is set; otherwise the placement follows
    ``run.curve_geometry``, which is what every case did before the two were separable.
    """

    explicit = getattr(run, "curve_placement", None)
    if explicit is not None:
        return bool(explicit)
    return bool(getattr(run, "curve_geometry", False))


def _gauge_centre(
    case: VehicleCase,
    s_m: float,
    dynamics: "VehicleDynamics | None" = None,
    speed_m_s: float = 0.0,
) -> tuple[float, float]:
    """The centre line of the track at ``s_m``, and its slope, read off the sampled rails.

    A turnout curves through its *station table*, not through ``curve_radius_m``: the diverging
    route of the 18 号道岔 has its tangent at 50.578 m and R = 1100 m afterwards, so by the run's
    start at 69 m the track has already moved 154 mm sideways and is rotated by 0.017 rad.  A
    vehicle that starts straight there meets the rail with its flange, which is what the seat
    reported as ``7 of 8 wheels carry load``.
    """

    def centre(x_m: float) -> float | None:
        # One value per *template*: a turnout template carries several surfaces at the same
        # mileage (stock rail, point rail, wing rail), and averaging two of those surfaces is not
        # the track centre.  Measured: taking the first two rails of the diverging case gave
        # -0.599 m at 69 m, where the gauge centre is -0.154 m.
        seen: dict[str, float] = {}
        for rail in case.rails:
            bodies = getattr(rail, "bodies", None) or getattr(rail, "contact_bodies", None) or ()
            if not bodies:
                continue
            key = str(getattr(rail, "template_id", id(rail)))
            if key in seen:
                continue
            sample = bodies[0].series.sample(float(x_m))
            local = float(np.mean(np.asarray(sample.profile.y_m, dtype=float)))
            if dynamics is not None:
                # Measured: on the geometry route ``profile.y_m`` is the *relative* section
                # coordinate, and the curve offset sits in the track kernel's placement.  Reading
                # only the profile returned exactly 0.000000 m at 60..80 m, which made this whole
                # function a no-op and left the vehicle straight while the rail moved 45.455 mm --
                # the 27 mm flange-root contact of round 27.
                index = next((i for i, item in enumerate(case.rails) if item is rail), None)
                if index is not None:
                    zero = np.zeros(dynamics.dimension)
                    local += float(
                        dynamics.track.local_state(zero, zero, index, float(x_m), float(speed_m_s))[0]
                    )
            seen[key] = local
        if not seen:
            return None
        return float(np.mean(list(seen.values())))

    here = centre(s_m)
    if here is None:
        return 0.0, 0.0
    ahead = centre(s_m + 1.0)
    if ahead is None:
        return here, 0.0
    return here, ahead - here


def _align_to_track_frame(case: VehicleCase, dynamics: VehicleDynamics,
                          q: np.ndarray) -> np.ndarray:
    """Rotate and shift the vehicle onto the track's own centre line at its own mileages."""

    topology = dynamics.topology
    start = float(getattr(case.run, "x_start_m", 0.0) or 0.0)
    # Opt-in only.  A turnout's *frog* also has rails that converge and diverge, so "the sampled
    # rails have a slope" is not evidence that the run is on a curve -- gating on the slope alone
    # moved the frog case's start state and its seat stopped converging.
    # The alignment complements the *geometry* route, where the rail has been placed on the arc and
    # the vehicle has to be placed with it.  On the force route the rails stay straight, so moving
    # the vehicle sideways puts it beside its own rails: measured, the force route that seats at
    # 59 652..59 708 N per wheel failed with `xtol` the moment align_to_track was switched on.
    if not _placement_enabled(case.run):
        # The gate used to be `curve_geometry` alone, so a turnout -- whose design line lives in
        # its station table, with `curve_radius_m` empty -- could never be aligned: the flag was
        # accepted and silently ignored (align_to_track measured as a no-op for three rounds).
        return q
    speed = abs(float(case.vehicle.travel_speed_m_s))
    here, tangent = _gauge_centre(case, start, dynamics, speed)
    if abs(tangent) <= 1.0e-4:
        return q
    offsets = list(getattr(case.vehicle, "axle_offsets_m", ()) or ())
    if not offsets:
        return q
    half = float(getattr(case.vehicle, "bogie_half_spacing_m", 0.0) or 0.0)
    stations = {topology.wheelset_id(index): start + float(offset)
                for index, offset in enumerate(offsets)}
    centres = {body.id: start for body in topology.bogies() if body.bogie == 0}
    centres.update({body.id: start for body in topology.bogies() if body.bogie == 1})
    for index, body in enumerate(topology.bogies()):
        centres[body.id] = start + (half if index == 0 else -half)
    for body in topology.bodies:
        if body.kind == "carbody":
            centres[body.id] = start
    have = {(body.id, axis) for body in topology.bodies for axis in body.dof}
    result = np.array(q, dtype=float, copy=True)
    for body_id, mileage in list(stations.items()) + list(centres.items()):
        lateral, slope = _gauge_centre(case, mileage, dynamics, speed)
        if (body_id, "y") in have:
            result[topology.require(body_id, "y")] = lateral
        if (body_id, "yaw") in have:
            # The state's ``yaw`` is read by the creep law as an *angle of attack*
            # (``creep_attack_velocity_m_s = travel * q[yaw]``, contact.py), not as an absolute
            # heading.  Writing the design line's own tangent here therefore injected
            # ``travel * arctan(slope)`` of spurious lateral creep -- 0.352 m/s at 30 m on
            # R = 1100 m, 0.6707 m/s at 81.6 m -- which saturates the patch.  The line's direction
            # is already carried by the wheel's lateral *placement* (``lateral_extra``), so a body
            # running along the line has zero angle of attack.
            result[topology.require(body_id, "yaw")] = 0.0
    return result


def _align_velocity_to_track(case: VehicleCase, dynamics: VehicleDynamics,
                             q: np.ndarray, v: np.ndarray) -> np.ndarray:
    """Give every body the design line's own lateral velocity, so it starts following the line.

    ``_align_to_track_frame`` puts the vehicle *on* the line but leaves it with zero lateral
    velocity, while the rail surface at the same mileage moves at ``v * dy/ds`` (``local_state``'s
    ``dy/dt``).  Measured on the geometry route at R = 1100 m, 80 km/h: the vehicle tracked the
    straight while the line ran away at 0.202 m/s, and ``graph slope limit at axle1_left/left:main,
    x=41.04259 m`` clipped the run after 1.04 m of travel -- 0.047 s of the 0.34 s the acceptance
    gate asks for.
    """

    if not _placement_enabled(case.run):
        return v
    topology = dynamics.topology
    signed = float(case.vehicle.travel_speed_m_s)
    speed = abs(signed)
    start = float(getattr(case.run, "x_start_m", 0.0) or 0.0)
    offsets = list(getattr(case.vehicle, "axle_offsets_m", ()) or ())
    if not offsets:
        return v
    half = float(getattr(case.vehicle, "bogie_half_spacing_m", 0.0) or 0.0)
    mileages = {topology.wheelset_id(index): start + float(offset)
                for index, offset in enumerate(offsets)}
    for index, body in enumerate(topology.bogies()):
        mileages[body.id] = start + (half if index == 0 else -half)
    for body in topology.bodies:
        if body.kind == "carbody":
            mileages[body.id] = start
    have = {(body.id, axis) for body in topology.bodies for axis in body.dof}
    result = np.array(v, dtype=float, copy=True)
    # Take the velocity from the *placement itself* (``local_state``'s third return value is
    # ``speed * dy_ds``), not from a differenced slope: ``_gauge_centre`` differences the centre
    # line over 1 m, which on a quadratic lags the true tangent by 0.5 m and gave 0.2121 m/s where
    # the rail moves at 0.2020 m/s -- a 5 % outward creep that the saturated patch then spent the
    # whole run removing.
    axle_of = {body.id: index for index, body in enumerate(topology.wheelsets())}
    zeros = np.zeros(len(q), dtype=float)
    for body_id, mileage in mileages.items():
        if (body_id, "y") not in have:
            continue
        index = axle_of.get(body_id, 0)
        _, _, rail_vy, _ = dynamics.track.local_state(zeros, zeros, index, float(mileage), signed)
        result[topology.require(body_id, "y")] = float(rail_vy)
    return result


def _arc_parameter_m(run, mileage_m: float) -> float:
    """Arc parameter of ``y = s^2/(2R)`` at an absolute mileage, clamped at the tangent point.

    A curve does not begin where the run begins.  ``s = x - x_start`` put the arc's apex at the run
    start, so a run that starts *before* the tangent sits on a mirror arc that does not exist: at
    R = 1100 m with the tangent at 50.578 m and ``x_start = 30 m`` the rear axle is 425 mm off the
    design line, and the front axle 381 mm, both to the wrong side.  Clamping at zero keeps the line
    straight before the tangent, which is what a real alignment does, and is first-order continuous
    (``dy/ds = 0`` on both sides of the joint).

    ``run.curve_origin_m`` says where the tangent is; ``None`` keeps the old meaning (the run start),
    so every existing case reproduces its numbers bit for bit.
    """

    radius = getattr(run, "curve_radius_m", None)
    if radius is None:
        return 0.0
    origin = getattr(run, "curve_origin_m", None)
    if origin is None:
        # No tangent was given, so the old meaning stands: the arc's apex is the run start and the
        # parameter is signed.  ``y = s^2/(2R)`` is symmetric, so a body behind the start sits on the
        # same arc with the opposite heading -- that is how every existing case was built, and every
        # one of them must stay bit-identical.
        return float(mileage_m) - float(run.x_start_m)
    return max(float(mileage_m) - float(origin), 0.0)


def _place_on_alignment(case: VehicleCase, dynamics: VehicleDynamics,
                        q: np.ndarray) -> np.ndarray:
    """Put the vehicle where the curved design line is, before the seat solves anything.

    ``_curve_placement`` moves the *track* onto ``y(s) = s^2/(2R)``; a vehicle that keeps
    ``y = yaw = 0`` then stands beside its own rails, and the seat has to drag every wheel into the
    flange to close the gap — the run dies on the contact-slope guard rather than on a force.  The
    vehicle therefore has to be placed on the same line: lateral offset ``s^2/(2R)`` and heading
    ``atan(s/R)`` for every body, each at its own mileage.

    Gated on ``run.curve_geometry``, which is exactly the flag that moves the track: with the rails
    left straight there is no line to sit on, and placing the vehicle would push it off a straight
    track by up to ``s^2/(2R)``.  Every case without that flag keeps its initial state unchanged.
    """

    radius = getattr(case.run, "curve_radius_m", None)
    if radius is None or not _placement_enabled(case.run):
        return q
    radius = float(radius)
    if radius == 0.0:
        raise SimulationFailure("curve_radius_m must not be zero")
    topology = dynamics.topology
    placed = q.copy()
    # The track plane is tilted by the cant, so the vehicle has to be tilted with it.  Without this
    # roll the wheel stays level while the rail rotates: the wheel then meets the high rail on the
    # flange root, where the profile slope is of order one, and the contact-slope guard stops the
    # run at the first step (measured: R = 1100 m, 107 mm cant, x = 70 m).
    #
    # The sign follows the same convention as ``_curve_placement``: with ``kappa > 0`` the raised
    # rail is the OUTER one at ``-y``, so the vehicle leans towards ``+y`` and the roll is
    # ``-theta``.  Positive roll raises the ``+y`` wheels (measured: +0.0717 rad moved the right
    # wheel up 53.5 mm), so ``+theta`` would lean the body *into* the curve while the track leans
    # out of it -- both halves of the same mirror error.
    cant = float(getattr(case.run, "curve_cant_m", 0.0) or 0.0)
    half_gauge = abs(float(case.wheels[0].lateral_offset_m)) if case.wheels else 0.75
    theta = 0.0 if half_gauge == 0.0 else math.asin(max(-1.0, min(1.0, cant / (2.0 * half_gauge))))
    for body in topology.bodies:
        mileage = float(case.run.x_start_m) + _body_offset_m(case, topology, body, placed)
        s = _arc_parameter_m(case.run, mileage)
        if "y" in body.dof:
            placed[topology.require(body.id, "y")] += s * s / (2.0 * radius)
        if "yaw" in body.dof:
            placed[topology.require(body.id, "yaw")] += math.atan(s / radius)
        if theta and "roll" in body.dof:
            placed[topology.require(body.id, "roll")] -= theta
    return placed


def _body_offset_m(case: VehicleCase, topology, body, q: np.ndarray) -> float:
    """Distance from the run's start to where this body meets the track.

    Only the ``_x`` layouts carry a longitudinal coordinate, so the legacy 35-coordinate layout has
    to take the mileage from the geometry it already declares: a wheelset sits at its axle offset, a
    bogie halfway between its two axles, and the carbody on the vehicle centre.
    """

    if "x" in body.dof:
        return float(q[topology.require(body.id, "x")]) - float(case.run.x_start_m)
    offsets = [float(value) for value in case.vehicle.axle_offsets_m]
    if getattr(body, "kind", None) == "wheelset" and getattr(body, "axle", None) is not None:
        return offsets[int(body.axle)]
    if getattr(body, "kind", None) == "bogie" and getattr(body, "bogie", None) is not None:
        axles = [int(item.axle) for item in topology.wheelsets()
                 if getattr(item, "bogie", None) == int(body.bogie)]
        if axles:
            return sum(offsets[axle] for axle in axles) / float(len(axles))
    return 0.0


def _seat(case: VehicleCase, dynamics: VehicleDynamics, q: np.ndarray,
          v: np.ndarray) -> tuple[np.ndarray, float]:
    """Solve the static seat against the equivalent straight track.

    At zero speed a curved track has no lateral equilibrium -- creep is what steers a wheelset
    round a curve (Elkins & Gostling, *A General Quasi-static Curving Theory for Railway
    Vehicles*, Vehicle System Dynamics 1977), so a curve can only be *entered* at speed, never
    stood on.  Measured at R = 1100 m: seating with the placement on stalled every seed
    (cond 3.76e12, every residual 2.39 = 240 kN), seating with it off converges to 1.07e-12 with
    all eight patches at 65.47 um.  The alignment takes effect as soon as time starts.
    """
    seat_mileage = getattr(case.run, "seat_x_start_m", None)
    run_mileage = case.run.x_start_m
    if seat_mileage is not None:
        # Stand the vehicle where the turnout is still straight; the run itself starts at
        # ``x_start_m`` and the alignment brings it onto the design line there.
        object.__setattr__(case.run, "x_start_m", float(seat_mileage))
    templates = getattr(case.run, "seat_templates", None)
    if templates:
        wanted = {str(name) for name in templates}
        keep = tuple(rail for rail in case.rails
                     if str(getattr(rail, "template_id", "")) in wanted)
        if not keep:
            raise SimulationFailure(
                f"seat_templates {sorted(wanted)} matches no rail; the case carries "
                f"{sorted({str(getattr(rail, 'template_id', '')) for rail in case.rails})}"
            )
        from dataclasses import replace as _replace

        seat_case = _replace(case, rails=keep)
        seat_dynamics = VehicleDynamics(seat_case)
        if seat_dynamics.dimension != dynamics.dimension:
            raise SimulationFailure(
                "seat_templates needs a rigid track: restricting the rails changes the elastic "
                f"state size ({seat_dynamics.dimension} vs {dynamics.dimension})"
            )
        seat_dynamics.placement_enabled = False
        seat_dynamics.track.placement = None
        return _static_vertical_equilibrium(seat_case, seat_dynamics, q, v)

    enabled = dynamics.placement_enabled
    placement = dynamics.track.placement
    dynamics.placement_enabled = False
    # Take the hook off the kernel as well as switching it off: the contact search caches
    # geometry per (rail, profile fingerprint), so a strip looked up while the placement was
    # active can be reused inside the seat and the rails stay curved there.
    dynamics.track.placement = None
    if bool(getattr(case.run, "align_to_track", False)):
        # The station table already carries the diverging route, so the vehicle has to be put on
        # that design line before the vertical seat solves: measured 4 of 8 wheels carrying load
        # when the seat starts from the coordinate origin instead.
        q = _align_to_track_frame(case, dynamics, q)
    try:
        return _static_vertical_equilibrium(case, dynamics, q, v)
    finally:
        dynamics.track.placement = placement
        dynamics.placement_enabled = enabled
        if seat_mileage is not None:
            object.__setattr__(case.run, "x_start_m", run_mileage)


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
    # Every body that owns a vertical coordinate is an unknown, not just the three kinds the
    # legacy layout has: an axle box carries a z coordinate and a mass, and freezing it turns the
    # primary spring into a rigid support (the car then rests on a motionless box while the
    # wheelsets sink on their bearings).
    # A curve puts a lateral force and a roll moment on every body, so freezing the lateral and
    # roll coordinates would make the seat answer a question the equations never asked: the run
    # would settle with every wheel on the same side of its clearance band and report a converged,
    # laterally meaningless set-down.  The unknowns are therefore widened only when the run really
    # has a curve, so every straight case keeps today's equations bit for bit.
    curved = bool(getattr(case.run, "curve_radius_m", None)) or bool(
        getattr(case.run, "curve_geometry", False)) or bool(getattr(case.run, "align_to_track", False))
    if getattr(dynamics, "placement_enabled", False) and getattr(dynamics.track, "placement", None) is not None:
        # A curve is entered, never stood on: with the placement on, the rails are rotated onto the arc
        # while the vehicle still sits on the straight line, and the seat settles on one side.  Measured:
        # 4 of 8 wheels carrying load, heaviest 127 821.9 N against a 59 662 N share (R = 1100 m,
        # 100 km/h).  ``_seat`` switches the placement off for exactly this reason.
        raise SimulationFailure(
            "the vertical seat cannot run with the curve placement on: the rails would be on the arc "
            "while the vehicle is on the straight line, and the seat settles on one side (measured 4 "
            "of 8 wheels, 127 821.9 N against a 59 662 N share). Call _seat(), which switches the "
            "placement off around the solve")
    indices = [topology.require(body.id, "z") for body in topology.bodies if "z" in body.dof]
    if curved:
        # yaw is not optional.  A wheelset steers on a curve only because its two contact points
        # run on different rolling radii, and that difference enters through the yaw moment: freezing
        # yaw leaves the wheelset parallel to the rails, so the equilibrium it can reach is flange
        # contact.  Measured on R = 1100 m at 80 km/h with y and roll free but yaw fixed: three left
        # patches only, 5.55-5.76 mm penetration, 13.6-13.8 MN per patch, no seed converged.
        # yaw only where the rails themselves are curved.  A force-route curve keeps a straight rail
        # and puts the curve in the force, so its balanced seat is already eight equal wheels
        # (measured 59 652-59 708 N against a 59 662 N share) and yaw adds an unknown nothing pulls
        # on.  A geometry-route curve needs yaw: a wheelset steers through the rolling-radius
        # difference between its two contacts, and that difference reaches the state as a yaw
        # moment.  Measured on R = 1100 m at 80 km/h, y and roll free but yaw fixed: three left
        # patches only, 5.5-5.8 mm penetration, 13.6-13.8 MN, no seed converged.  Adding yaw alone
        # did not seat it either (§21), so this is a necessary condition, not a sufficient one.
        arc = bool(getattr(case.run, "curve_geometry", False)) or bool(
            getattr(case.run, "align_to_track", False))
        # Lateral, yaw and roll stay *out* of the seat's unknowns.  At zero speed the creep forces
        # that would balance a curve are exactly zero and a crown contact carries no lateral
        # component, so those rows have no solution and their presence makes the system rank
        # deficient: measured on R = 1100 m, cond 3.76e12, smallest singular value 2.7e-11, and
        # every seed stopped at a stationary 240 kN.  Solving only the vertical coordinates from the
        # same aligned state converges to 1.07e-12 with all eight patches at 65.47 um and
        # 58.7..60.6 kN.  A curved vehicle's lateral state is a *running* equilibrium: the placement
        # sets it, the trajectory develops it, and the seat only decides how deep the wheels sit.
        del arc
        # The wheelsets' *yaw* is the one lateral-family coordinate that is not rank deficient on a
        # curve, because its row is stiffened by the creep law rather than by the contact geometry:
        # an attack angle `yaw` gives a lateral creep velocity `travel * yaw`, so the row has a real
        # tangent stiffness whenever the vehicle is rolling, while the vertical-only seat has nothing
        # to resist the `+-v kappa b` yaw moment the curvature term writes.  Measured with the
        # curvature term on and no yaw unknown: 4 of 8 wheels, 128 901 N = 2x the share.
        # y and roll stay out: at zero state velocity the crown contact carries no lateral component,
        # so those rows have no solution and make the system rank deficient (measured cond 3.76e12,
        # smallest singular value 2.7e-11, every seed stopped at a stationary 240 kN).
        for body in topology.wheelsets():
            if "yaw" in body.dof:
                indices.append(topology.require(body.id, "yaw"))
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

    box_rows = [topology.require(body.id, "z") for body in topology.bodies
                if body.kind == "axlebox"]
    seeds: list[np.ndarray] = [q[indices].copy()]
    # The seed grid has to span the bodies that actually exist.  An axle box sits between the
    # primary spring and the bearing, so its set-down is a fraction of the wheel's; without a box
    # dimension Newton settles on the symmetric branch where one side carries 2x and the other
    # side lifts off, which is exactly the failure the 1.2 s case showed (240.6 kN vs 59.7 kN).
    # Lateral seeds are gone with the lateral unknowns.  A seed written into a coordinate the solve
    # never touches is not a starting guess, it is a permanent offset: measured on R = 1100 m after
    # the unknowns became vertical-only, a +-2 mm seed left the vehicle standing on one side --
    # "4 of 8 wheels carry load, the heaviest 128901.3 N", exactly 2x the 59 662 N share -- because
    # nothing in the residual pulls the wheelset back to the middle of its clearance.
    for wheel_drop, bogie_drop, box_drop in (
            (2.0e-3, 2.0e-3, 2.0e-3), (5.0e-4, 5.0e-4, 5.0e-4), (2.0e-3, 0.0, 2.0e-3),
            (0.0, 2.0e-3, 2.0e-3), (1.0e-3, 1.0e-3, 5.0e-4), (3.0e-3, 3.0e-3, 3.0e-3)):
        seeded = q.copy()
        for row in wheel_rows:
            seeded[row] -= wheel_drop
        for row in bogie_rows:
            seeded[row] -= bogie_drop
        for row in box_rows:
            seeded[row] -= box_drop
        seeds.append(seeded[indices].copy())

    cfg = case.vehicle
    weight_n = cfg.gravity_m_s2 * sum(body.mass_kg for body in topology.bodies)
    # The even share belongs to a *wheel*, not to a declared rail.  A turnout case declares twelve
    # rails (stock and switch rails on each side) and a diverging one declares more still, while the
    # vehicle still has eight wheels — and a wheel sitting on two coincident rails splits its share
    # between them.  Dividing the weight by ``len(case.rails)`` therefore set the accept limit only
    # 2.8 % above the correct solution (B036); dividing it by the eight patches and then demanding
    # that *every* declared rail carry load is the opposite mistake, which made every multi-rail
    # case un-seatable (B038).  So: group the patches by wheel and judge the wheels.
    wheels = max(len({_wheel_of(rail) for rail in case.rails}), 2 * len(topology.wheelsets()), 1)
    expected_n = weight_n / wheels

    best: tuple[float, np.ndarray, float, list[float]] | None = None
    last_message = ""
    for seed in seeds:
        base = q.copy()
        base[indices] = seed

        def residual(values: np.ndarray, base: np.ndarray = base) -> np.ndarray:
            trial = base.copy()
            trial[indices] = values
            try:
                force, _ = dynamics.evaluate(0.0, trial, v)
            except SimulationFailure:
                # The contact guards (slope, penetration, edge) are diagnostics for a *run*: they
                # exist so a trajectory cannot continue off the rail.  A least-squares trial point
                # is not a trajectory — the search legitimately probes states that would be fatal
                # to integrate, and letting the guard escape kills the seat with a message that
                # describes the probe rather than the model.  Measured on a curved case: the seat
                # raised ``graph slope limit at axle1_left/left:main, x=70 m`` from inside this
                # loop while the reference state matched the rail to 5 um.  Turn the guard into a
                # barrier here: the step is rejected, the guard keeps its value for real time
                # stepping, and the hit count is reported so a seat that only converges by
                # bouncing off the barrier cannot pass unnoticed.
                dynamics.seat_barrier_hits += 1
                return np.full(len(indices), _SEAT_BARRIER_RESIDUAL)
            return force[indices] / 1e5

        # Least squares, not a square root(): seven vertical coordinates carry eight patches, so
        # the Jacobian has a near-null direction.  ``hybr`` requires a square system and its
        # pivoting decides the outcome — the same equations converge in one layout and report
        # "no progress" in another purely because the rows are numbered differently.
        solved = least_squares(residual, seed, method="trf", xtol=1e-12, ftol=1e-12,
                               gtol=1e-12, max_nfev=800)
        error_n = float(np.max(np.abs(residual(solved.x))) * 1e5)
        last_message = str(solved.message)
        if not np.all(np.isfinite(solved.x)) or error_n > 0.1:
            continue
        trial = base.copy()
        trial[indices] = solved.x
        _, contacts = dynamics.evaluate(0.0, trial, v)
        loads = [float(contacts[rail.id].normal_force_n) for rail in case.rails]
        per_wheel = _load_per_wheel(case.rails, loads)
        # Prefer the branch whose wheels sit closest to their even share: the hung-bogie branch
        # leaves one side carrying double, so it scores worst here.
        score = -max(abs(value - expected_n) for value in per_wheel.values())
        if best is None or score > best[0]:
            best = (score, solved.x.copy(), error_n, loads)
        if (max(per_wheel.values()) <= 1.6 * expected_n
                and min(per_wheel.values()) >= 0.625 * expected_n):
            break

    if best is None:
        raise SimulationFailure(
            f"vertical preload equilibrium failed: no seed converged; {last_message}")
    _, values, error_n, loads = best
    per_wheel = _load_per_wheel(case.rails, loads)
    starved = min(per_wheel.values()) < 0.625 * expected_n
    over_loaded = max(per_wheel.values()) > 1.6 * expected_n
    if starved and over_loaded:
        carrying = sum(1 for value in per_wheel.values() if value > 1.0e3)
        raise SimulationFailure(
            "vertical preload equilibrium failed: unbalanced branch - "
            f"{carrying} of {len(per_wheel)} wheels carry load, the lightest wheel carries "
            f"{min(per_wheel.values()):.1f} N while the heaviest carries "
            f"{max(per_wheel.values()):.1f} N (even share ~{expected_n:.0f} N per wheel; "
            f"heaviest single patch {max(loads):.1f} N over {len(loads)} rails); "
            "the vehicle is standing on one side, not failing to spread load over its wheels")
    q[indices] = values
    return q, error_n


def _wheel_of(rail: object) -> tuple[int, str]:
    """Which wheel a rail patch belongs to: same axle and side means the same wheel.

    A railway wheel can sit on two coincident rails (a stock and a switch rail at the same mileage
    in a turnout, or a stock and a branch rail at the point of divergence), so the patches are
    grouped by wheel before the load is compared with the even share.
    """

    axle = int(getattr(rail, "axle_index", 0))
    text = f"{getattr(rail, 'id', '')} {getattr(rail, 'template_id', '')}".lower()
    side = "right" if "right" in text else ("left" if "left" in text else str(getattr(rail, "template_id", "")))
    return axle, side


def _load_per_wheel(rails, loads) -> dict[tuple[int, str], float]:
    """Sum the patch loads of each wheel."""

    per_wheel: dict[tuple[int, str], float] = {}
    for rail, load in zip(rails, loads):
        key = _wheel_of(rail)
        per_wheel[key] = per_wheel.get(key, 0.0) + float(load)
    return per_wheel


def _settle_modal_coordinates(dynamics: VehicleDynamics, q: np.ndarray, v: np.ndarray,
                              rounds: int = 12) -> np.ndarray:
    """Put the modal coordinates where the static contact force holds them.

    A flexible wheelset started at ``q = 0`` is a wheel whose tread has not yet been pressed in
    by the load.  The first milliseconds are then the wheel settling onto the rail at its own
    lowest elastic frequency (76.8 Hz for the CRH3C set), and a 0.05 s window is *entirely*
    inside that transient: the forces read there belong to the initialisation, not to the
    turnout.  That is what made a rigid/flexible comparison report 87 %.

    The static state is the fixed point of ``K q = Phi^T f(q)``.  ``evaluate`` already returns
    ``force[modal] = Q(q) - K q`` at zero velocity, so ``K^-1 Q = q + K^-1 force[modal]`` and one
    pass is a fixed-point iteration whose contraction is the tread compliance times the contact
    stiffness (about 0.5 for this wheelset).  Twelve passes leave the residual near 2e-4, and the
    caller alternates them with the vertical equilibrium so wheel height and tread deflection are
    consistent with each other rather than each solved against the other's stale value.
    """
    modal = dynamics.modal
    if modal is None:
        return q
    settled = np.array(q, dtype=float)
    stiffness = modal.stiffness()
    for _round in range(rounds):
        force, _contacts = dynamics.evaluate(0.0, settled, v)
        step = np.linalg.solve(stiffness, force[modal.offset:])
        settled[modal.offset:] += step
        if float(np.max(np.abs(step))) < 1e-9:
            break
    return settled


def travel_mileage_m(case: VehicleCase, t_s: float) -> float:
    """Mileage of the vehicle reference point at ``t_s``, for anything written to disk.

    The history file's mileage columns and the force path must agree: if the solver samples the
    steel with ``x_at`` and the file reports ``v*t`` (the case's single speed), then a run with a
    varying speed produces a trail that does not belong to the geometry that was used.  A
    constant profile stays bit-identical, because the direction is ±1.0 and the product is the
    same one.
    """

    schedule = getattr(case, "speed_schedule", None)
    if schedule is None:
        return case.run.x_start_m + case.vehicle.travel_speed_m_s * t_s
    direction = 1.0 if case.vehicle.travel_speed_m_s >= 0.0 else -1.0
    return case.run.x_start_m + direction * schedule.x_at(t_s)


def simulate_vehicle(case: VehicleCase, contact_workers: int = 1) -> VehicleResult:
    # A varying speed is allowed now that the spin tracks it (``VehicleDynamics.spin_control``
    # is switched on automatically for a non-constant schedule) and the ``spin_tracking`` gate
    # reports how well it did.  A constant profile still takes the pass-through path.
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
    # A modal block is dense in itself and always coupled: its damping matrix carries the
    # antisymmetric gyroscopic term, which at rest is invisible to the probe whenever the pair is
    # momentarily at zero amplitude.  Marking the whole block costs nothing when there is none.
    modal = getattr(dynamics, "modal", None)
    if modal is not None:
        rows = np.arange(modal.offset, modal.stop)
        skeleton[np.ix_(rows, rows)] = True

    return mask | skeleton


#: Coordinates whose analytic acceleration is written out.  ``spin`` is deliberately absent: it is
#: an unsprung free rotation that no track input drives, so four near-zero channels would widen
#: every table without adding information.  ``x`` matters: on a node-table layout the longitudinal
#: coordinate is solved, and its acceleration is the only wheel-rail observation that is not
#: collinear with the vertical one (see docs/S7_OBSERVATION_DESIGN).
_ACCELERATED_AXES = frozenset({"x", "y", "z", "roll", "pitch", "yaw"})


def _acceleration_channels(dynamics: VehicleDynamics) -> list[tuple[int, object, str]]:
    """``(state_index, body, axis)`` for every emitted acceleration, in ``history.csv`` order.

    Iterating ``body.dof`` rather than a fixed axis tuple is what keeps the rows and their column
    names aligned: the writer builds the names by walking the same list.
    """

    topology = dynamics.topology
    ordered = sorted(topology.bodies, key=lambda item: topology.offset(item.id))
    return [(topology.require(body.id, axis), body, axis)
            for body in ordered for axis in body.dof if axis in _ACCELERATED_AXES]


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
        q, static_residual_n = _seat(case, dynamics, q, v)
        # A flexible wheelset has a second static unknown: how far the tread is pressed in.
        # Solving only the heights leaves the tread flat and the load unbalanced, and the
        # integrator then spends the first tenths of a second settling — inside every short
        # window.  Two outer rounds are enough: the inner fixed point converges to ~2e-4.
        for _round in range(2):
            q = _settle_modal_coordinates(dynamics, q, v)
            q, static_residual_n = _seat(case, dynamics, q, v)
    # The opt-in alignment is applied *after* the seat: the vehicle stands on the equivalent
    # straight first, then it is set on the design line it is about to run along.  Applying it
    # before the seat put the wheels 45 mm beside straight rails.
    # The opt-in alignment is applied *after* the seat, and the order is load bearing: the seat
    # solves against the equivalent straight (``placement_enabled`` off), so a vehicle placed on
    # the curve first stands 25-45 mm beside those straight rails -- 35-63 % of the 72.4 mm lateral
    # band -- and the least squares can only lift one side.  Measured with the alignment before the
    # seat: 4 of 8 wheels loaded, heaviest 127 783 N = 2.14x the 59 662 N share, identical at
    # x_start 30 / 50 / 69 m because ``_body_offset_m`` returns axle offsets, not mileage.
    if bool(getattr(case.run, "align_to_track", False)):
        q = _place_on_alignment(case, dynamics, q)
        q = _align_to_track_frame(case, dynamics, q)
        # Position alone is not enough: the line also *moves* under the vehicle.  Measured, the
        # geometry route without this reached only 1.04 m of travel before the slope guard.
        v = _align_velocity_to_track(case, dynamics, q, v)
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
    # Every body that has mass, not "four wheelsets + two bogies + car": with axle boxes the old
    # expression left 8 x 48.2 kg out and the action/reaction sum read permanently low by 3.8 kN.
    total_weight = sum(body.mass_kg for body in dynamics.topology.bodies) * cfg.gravity_m_s2
    # The curve enters the right-hand side as an external lateral force, so the lateral
    # action/reaction sum is short by exactly this much unless it is counted here too.
    #
    # ...but only on the route that actually applies it.  On the geometry route the vehicle is
    # placed on the arc and ``evaluate`` adds no lateral force, so adding m v^2/R to the balance
    # here made a curved run fail this gate by exactly 34.2 kN while every force was accounted for
    # (measured, R = 1100 m at 100 km/h: the only failing gate out of seven).
    #
    # The value is *recorded* by ``evaluate`` rather than recomputed here: a gate that restates
    # the force in its own words can disagree with the applied one about the sign of the curve,
    # and the first version of this fix did exactly that (it evaluated the curvature at station
    # zero, which on a line that starts at 30 m is the straight approach, and read 0 N).
    # The loop below already calls evaluate() on every accepted state for the gates; that call
    # *is* the right-hand side, so acceleration is force/mass with no finite difference.
    acceleration_channels = _acceleration_channels(dynamics)
    acceleration_names = tuple(
        _acceleration_name(f"{_column_prefix(body)}_{_state_suffix(body, axis)}")
        for _index, body, axis in acceleration_channels)
    acceleration_rows: list[list[float]] = []
    for t, position, velocity in zip(times, positions, velocities):
        force, contacts = dynamics.evaluate(float(t), position, velocity)
        # Inertia lives in mass[index] for the rotation coordinates; body.mass_kg is only right
        # for translations, so divide by the entry the equation of motion actually uses.
        acceleration_rows.append([float(force[index]) / float(dynamics.mass[index])
                                  for index, _body, _axis in acceleration_channels])
        contact_history.append(contacts)
        energies.append(dynamics.mechanical_energy_j(position, velocity, contacts))
        curve_lateral_n = float(getattr(dynamics, "curve_lateral_applied_n", 0.0))
        if case.track_kind in {"rigid", "local_compliant", "two_layer", "layered"}:
            # Every body's lateral and vertical coordinates, wherever the topology put them.
            topology = dynamics.topology
            bodies = tuple(body for body in topology.bodies if "y" in body.dof)
            y_indices = [topology.require(body.id, "y") for body in bodies]
            z_indices = [topology.require(body.id, "z") for body in topology.bodies
                         if "z" in body.dof]
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
                abs(sum(force[y_indices]) - curve_lateral_n + reaction[0]),
                abs(sum(force[z_indices]) + reaction[1] + total_weight))
        else:
            assert case.modal_track is not None
            for rail_index, rail in enumerate(case.rails):
                response = contacts[rail.id]
                x = dynamics.station_m(rail, float(t), position)
                py, pz, _, _ = case.modal_track.shapes[rail.template_id].sample(x)
                rail_force = dynamics.track.contact_reaction(rail_index, x,
                    response.wheel_force_y_n, response.wheel_force_z_n)
                # The track block is no longer the tail once modal wheelset coordinates exist.
                start = topology.body_dimension
                track_velocity = velocity[start:start + case.modal_track.mode_count]
                power_error = float(rail_force @ track_velocity +
                                    response.wheel_force_y_n * (py @ track_velocity) +
                                    response.wheel_force_z_n * (pz @ track_velocity))
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

    # Eighth gate, only when there is something to gate: with a varying speed the wheel spin is
    # driven towards ``v(t)/r``, and the metric is how far it actually sits from it.  A lag here
    # is not cosmetic -- it is booked as longitudinal creep, saturates, and takes lateral force
    # with it through ``hypot``.  A constant profile has no servo, so the gate is absent and the
    # seven-gate set is unchanged.
    spin_tracking_max_m = None
    spin_tracking_relative = None
    if dynamics.spin_control:
        radius = float(case.vehicle.nominal_wheel_radius_m)
        velocity_part = np.asarray(solution.y[dynamics.dimension:])
        spin_indices = [dynamics.topology.require(dynamics.topology.wheelset_id(axle), "spin")
                        for axle in range(len(case.vehicle.axle_offsets_m))]
        steps = np.asarray(solution.t, dtype=float)
        worst = 0.0
        for index, t_value in enumerate(steps):
            speed = abs(dynamics.speed_at(float(t_value)))
            for spin in spin_indices:
                worst = max(worst, abs(float(velocity_part[spin, index]) * radius - speed))
        spin_tracking_max_m = worst
        # The gate is measured where it means something.  A leg change is a step in the schedule
        # and no servo can follow a step: measured, the tread slip at the boundary is the whole
        # speed change (2.0 m/s at 2 -> 4 m/s), while it is back under 0.02 m/s within 5 ms.
        # So the gate reads each leg's *end*, where the creep reference and the spin must agree,
        # and reports the boundary peak separately rather than hiding it.
        settled = 0.0
        for end in dynamics.speed_schedule.leg_end_times_s:
            index = int(np.searchsorted(steps, end - 1.0e-12, side="right")) - 1
            index = min(max(index, 0), len(steps) - 1)
            speed = abs(dynamics.speed_at(float(steps[index])))
            for spin in spin_indices:
                slip = abs(float(velocity_part[spin, index]) * radius - speed)
                settled = max(settled, slip / max(speed, 1.0))
        spin_tracking_relative = settled

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
    if spin_tracking_relative is not None:
        gates["spin_tracking"] = bool(spin_tracking_relative <= 0.01)
    summary = {
        "case_id": case.case_id, "case_purpose": case.purpose,
        "result_status": "numerically_checked" if all(gates.values()) else "numerical_gate_failed",
        "physics_validation_status": "unvalidated_against_measurement_or_Simpack",
        # Written here as the no-claim default and nowhere else: only velch.inverse.verdict may
        # return anything stronger, because that is the layer that actually compares against a
        # measured record.  A run on its own can never say its numbers were validated.
        "measurement_validation_status": "not_evaluated",
        "vehicle_dof": topology.body_dimension, "total_dof": dynamics.dimension,
        "spin_tracking_max_m": spin_tracking_max_m,
        "spin_tracking_relative": spin_tracking_relative,
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
    accelerations = (np.asarray(acceleration_rows, dtype=float)
                     if acceleration_rows else None)
    return VehicleResult(times, positions, velocities, contact_history, summary,
                         accelerations=accelerations, acceleration_names=acceleration_names)


_COLUMN_SUFFIX = {"x": "x_m", "y": "y_m", "z": "z_m", "roll": "roll_rad",
                  "pitch": "pitch_rad", "yaw": "yaw_rad", "spin": "spin_rad"}


def _state_suffix(body, axis: str) -> str:
    """State column suffix, disambiguated where the schema already owns the name.

    The writer emits four leading ``axle<k>_x_m`` columns holding the *absolute* station of each
    axle.  A layout that also solves the wheelset's longitudinal coordinate would therefore label
    two different quantities with one name — a duplicate header, and every reader after the first
    collision silently pairs a displacement with a mileage.  The perturbation is ``dx`` instead.
    """

    if axis == "x" and body.kind == "wheelset":
        return "dx_m"
    return _COLUMN_SUFFIX[axis]


def _column_prefix(body) -> str:
    """History-column prefix for a body, numbered the way the rest of the schema numbers it.

    Rails are ``axle1_left`` … ``axle4_right`` (1-based, see :mod:`velch.vehicle`) and the archive
    every document quotes uses ``axle1_y_m``.  The topology stores wheelset/bogie indices 0-based,
    so they have to be shifted here: without it a run labels its first wheelset ``axle0`` while the
    contact on the same axle is ``axle1_left``, and any reader pairing the two is off by one.
    """

    if body.kind == "wheelset":
        return f"axle{body.axle + 1}"
    if body.kind == "axlebox":
        # Two boxes ride the same axle, so the side has to be in the name: duplicate headers make
        # every reader after the first collision pick the wrong column.  ``axle`` is 0-based like a
        # wheelset's, checked by the loader.
        side = "right" if str(body.id).endswith(("R", "r")) else "left"
        return f"axle{body.axle + 1}_box_{side}"
    if body.kind == "bogie":
        return f"bogie{body.bogie + 1}"
    return body.id


def _column_names(case: VehicleCase):
    """History column names in state order, taken from the topology offsets.

    The columns have to follow the order of the numbers in each row.  A hand-written list stops
    matching as soon as the layout gains a body or a coordinate: with an axle box, or with the
    longitudinal coordinate of a 6-DOF layout, every column after the first difference is mislabelled
    while the numbers themselves stay right.
    """

    topology = topology_for(case)
    for body in sorted(topology.bodies, key=lambda item: topology.offset(item.id)):
        prefix = _column_prefix(body)
        for axis in body.dof:
            yield f"{prefix}_{_state_suffix(body, axis)}"


#: Coordinate → acceleration column suffix.  ``x`` is here because node-table layouts solve the
#: longitudinal coordinate; leaving it out silently dropped every longitudinal acceleration, which
#: is the one channel a multi-level observation design cannot reconstruct from the vertical ones.
_ACCELERATION_SUFFIX_BY_AXIS = {"x": "x_acc_m_per_s2", "y": "y_acc_m_per_s2",
                                "z": "z_acc_m_per_s2", "roll": "roll_acc_rad_per_s2",
                                "pitch": "pitch_acc_rad_per_s2",
                                "yaw": "yaw_acc_rad_per_s2"}

_AXIS_BY_COLUMN_SUFFIX = {suffix: axis for axis, suffix in _COLUMN_SUFFIX.items()}
_AXIS_BY_COLUMN_SUFFIX["dx_m"] = "x"
#: state suffix -> acceleration suffix, kept as a pair of strings so ``dx_m`` keeps its ``d``:
#: deriving the acceleration name from the axis alone turns a perturbation into an absolute
#: quantity, and ``axle1_x_acc_m_per_s2`` would then read as the acceleration of the mileage.
_ACCELERATION_BY_COLUMN_SUFFIX = {suffix: _ACCELERATION_SUFFIX_BY_AXIS[axis]
                                  for suffix, axis in _AXIS_BY_COLUMN_SUFFIX.items()
                                  if axis in _ACCELERATED_AXES}   # spin has no channel
_ACCELERATION_BY_COLUMN_SUFFIX["dx_m"] = "dx_acc_m_per_s2"


def _acceleration_name(name: str) -> str | None:
    """Column name for the acceleration that belongs to a state column, or None."""
    for suffix, axis in _AXIS_BY_COLUMN_SUFFIX.items():
        if axis in _ACCELERATED_AXES and name.endswith("_" + suffix):
            return f"{name[: -len(suffix)]}{_ACCELERATION_BY_COLUMN_SUFFIX[suffix]}"
    return None


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
    body_names = list(_column_names(case))
    names = body_names + list(TrackKernel(case.track_kind, case.rails, case.modal_track,
                                         case.track_layers).state_names) \
        + list(modal_channel_names(case.wheel_modes))
    columns = ["time_s", *[f"axle{i + 1}_x_m" for i in range(4)], *names,
               *[name + "_per_s" for name in names]]
    acceleration_columns = list(result.acceleration_names)
    # Two walks produce the numbers and the header (the integrator, and _column_names).  If they
    # ever disagree the file would be silently mislabelled, so compare and refuse instead.  Only the
    # body columns are compared: a compliant rail's own states also end in ``_y_m``/``_z_m`` but
    # their acceleration is not emitted, and pretending otherwise would invent channels.
    derived = [column for column in (_acceleration_name(name) for name in body_names) if column]
    if result.accelerations is not None and acceleration_columns != derived:
        raise SimulationFailure(
            "acceleration header disagrees with the emitted channels: "
            f"{len(acceleration_columns)} names vs {len(derived)} derivable from the state columns")
    columns += acceleration_columns
    for rail in case.rails:
        columns += [f"{rail.id}_{field}" for field in ("normal_n", "fx_n", "fy_n", "fz_n",
                                                       "penetration_m", "active")]
    history = target / "history.csv"
    with history.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(columns)
        for index, (t, q, v, contacts) in enumerate(
                zip(result.times_s, result.positions, result.velocities, result.contacts)):
            reference = travel_mileage_m(case, float(t))
            row = [float(t), *[reference + offset for offset in case.vehicle.axle_offsets_m],
                   *map(float, q), *map(float, v)]
            if result.accelerations is not None:
                row += map(float, result.accelerations[index])
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
