"""Analytic Jacobian of the vehicle right-hand side.

The linear part of the model is exact: suspension connectors and the track stack
are springs and dampers, so their Jacobian is a constant matrix assembled once.
The contact part is where the difficulty lives, and this module makes one explicit
modelling choice about it:

    **the contact geometry is frozen** - the contact station along the rail, the
    surface normal, and the lever arms are taken from the current state and are
    not differentiated with respect to it.

That is the classical railway-vehicle linearisation: what makes the system stiff is
the elastic penetration, not the slow drift of the contact point across the
profile, so ``d(delta)/dq`` is taken along the current normal while the normal's
own rotation with the state is dropped. The consequence is honest and is stated in
the docstring rather than hidden: this is not the exact derivative of the
right-hand side, and its agreement with a finite difference is limited by how fast
the contact point travels across the profile. It *is* the exact derivative of the
linearised model, which is what an implicit solver needs to build a Newton step,
and it costs no extra right-hand-side evaluations - the whole point, because a
finite-difference Jacobian costs ``2 * dimension`` of them.

Both blocks are returned already divided by the mass vector, i.e. as the Jacobian
of ``f/m``::

    J = [[ 0 , I ], [ d(f/m)/dq , d(f/m)/dv ]]
"""

from __future__ import annotations

import math

import numpy as np

from .contact import ContactResponse
from .support_compliance import series_normal_force_slope


class JacobianAssembler:
    """Assemble ``d(f/m)/dq`` and ``d(f/m)/dv`` for a ``VehicleDynamics``."""

    def __init__(self, dynamics) -> None:
        self.dynamics = dynamics
        self.n = dynamics.dimension
        #: A node table may widen the vehicle block; the track block starts here.
        self.dof = dynamics.dof
        self.dynamics = dynamics
        self.mass = dynamics.mass
        self.law = dynamics.case.contact
        self.speed = dynamics.case.vehicle.travel_speed_m_s
        self.reference_speed = max(abs(self.speed), self.law.reference_speed_floor_m_s)
        self.support = dynamics.case.support_compliance
        self._stiffness_q, self._stiffness_v = self._connector_blocks()
        self._track_q, self._track_v = self._track_blocks()

    # -- exact linear blocks -------------------------------------------------

    def _connector_blocks(self) -> tuple[np.ndarray, np.ndarray]:
        stiffness = np.zeros((self.n, self.n))
        damping = np.zeros((self.n, self.n))
        for link in self.dynamics.connectors:
            outer = np.outer(link.jacobian, link.jacobian)
            stiffness -= link.stiffness * outer
            damping -= link.damping * outer
        return stiffness, damping

    def _track_blocks(self) -> tuple[np.ndarray, np.ndarray]:
        """Track stack Jacobian, recovered exactly by unit probing.

        ``TrackKernel.internal_force`` is linear in ``(q, v)`` for every track kind,
        so probing a unit coordinate yields the exact column rather than an
        approximation of it. This runs once, at construction, and touches no
        contact geometry.
        """
        track = self.dynamics.track
        if track.dimension == 0:
            return np.zeros((self.n, self.n)), np.zeros((self.n, self.n))
        zero_state = np.zeros(self.n)
        stiffness = np.zeros((self.n, self.n))
        damping = np.zeros((self.n, self.n))
        for index in range(self.dof, self.n):
            unit = np.zeros(self.n)
            unit[index] = 1.0
            # internal_force spans the rail dofs only; it lands on force[self.dof:] in the
            # right-hand side, so the column starts at 35 as well.
            stiffness[self.dof:, index] = track.internal_force(unit, zero_state)
            damping[self.dof:, index] = track.internal_force(zero_state, unit)
        return stiffness, damping

    # -- kinematic rows ------------------------------------------------------

    def _rail_rows(self, rail_index: int, x_m: float) -> tuple[np.ndarray, np.ndarray]:
        """``d(rail_y)/dq`` and ``d(rail_z)/dq`` as full-length rows."""
        track = self.dynamics.track
        y_row = np.zeros(self.n)
        z_row = np.zeros(self.n)
        kind = track.kind
        if kind == "local_compliant":
            y_row[self.dof + 2 * rail_index] = 1.0
            z_row[self.dof + 2 * rail_index + 1] = 1.0
        elif kind == "two_layer":
            y_row[self.dof + 4 * rail_index] = 1.0
            z_row[self.dof + 4 * rail_index + 1] = 1.0
        elif kind == "layered":
            stride = 2 * (1 + len(track.layers))
            y_row[self.dof + stride * rail_index] = 1.0
            z_row[self.dof + stride * rail_index + 1] = 1.0
        elif kind == "modal":
            rail = self.dynamics.case.rails[rail_index]
            py, pz, _dpy, _dpz = track.modal.shapes[rail.template_id].sample(x_m)
            y_row[self.dof:] = py
            z_row[self.dof:] = pz
        return y_row, z_row

    def _kinematic_row(self, rail_index: int, x_m: float, geometry) -> np.ndarray:
        """``d(delta)/dq``, equivalently ``d(approach)/dv``, with frozen geometry.

        One row serves both: the penetration rate is that row applied to the
        velocities, which is what makes the contact conservative. The wheel's roll
        enters through its lever arm, the rail through its own vertical dof.
        """
        rail = self.dynamics.case.rails[rail_index]
        wheel = self.dynamics.topology.offset(
            self.dynamics.topology.wheelset_id(rail.axle_index))
        ny, nz = geometry.normal_y, geometry.normal_z
        row = np.zeros(self.n)
        row[wheel] -= ny
        row[wheel + 1] -= nz
        row[wheel + 2] += ny * geometry.lever_z_m - nz * geometry.lever_y_m
        y_row, z_row = self._rail_rows(rail_index, x_m)
        row += ny * y_row + nz * z_row
        return row

    def _generalized_rows(self, rail_index: int, x_m: float,
                          geometry) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Generalized force per unit normal / lateral tangent / longitudinal force.

        These mirror the assembly in ``VehicleDynamics.evaluate`` exactly, but keep
        the three scalar force components symbolic so the chain rule can be applied.
        """
        track = self.dynamics.track
        wheel = self.dynamics.topology.offset(self.dynamics.topology.wheelset_id(
            self.dynamics.case.rails[rail_index].axle_index))
        ny, nz = geometry.normal_y, geometry.normal_z
        ty, tz = geometry.tangent_y, geometry.tangent_z
        ly, lz = geometry.lever_y_m, geometry.lever_z_m

        normal_row = np.zeros(self.n)
        normal_row[wheel] += ny
        normal_row[wheel + 1] += nz
        normal_row[wheel + 2] += ly * nz - lz * ny
        normal_row[self.dof:] += track.contact_reaction(rail_index, x_m, ny, nz)

        tangent_row = np.zeros(self.n)
        tangent_row[wheel] += ty
        tangent_row[wheel + 1] += tz
        tangent_row[wheel + 2] += ly * tz - lz * ty
        tangent_row[self.dof:] += track.contact_reaction(rail_index, x_m, ty, tz)

        longitudinal_row = np.zeros(self.n)
        longitudinal_row[wheel + 3] += lz
        longitudinal_row[wheel + 4] -= ly
        return normal_row, tangent_row, longitudinal_row

    # -- contact law derivatives --------------------------------------------

    def _normal_slopes(self, response: ContactResponse, geometry,
                       support_compliance) -> tuple[float, float, float]:
        """``dN/ddelta`` (elastic only), ``dN/ddelta`` (total), ``dN/d(approach)``.

        The elastic part is returned separately because the strip contact reports
        its gradient as ``dN_elastic/dq``: the damping branch is the same power of
        the same depth field, so the total force gradient is the total depth slope
        applied to ``dN_elastic/dq / elastic_slope``.
        """
        law = self.law
        depth = geometry.penetration_m
        stiffness = geometry.stiffness_n_m_1p5
        if stiffness is None:
            stiffness = law.normal_stiffness_n_m_1p5
        elastic_slope = series_normal_force_slope(depth, stiffness, support_compliance)
        approach = response.normal_approach_speed_m_s
        # The damping branch acts on the *geometric* depth: ``contact.evaluate_contact``
        # computes ``damping = c * sqrt(depth) * approach`` from ``g.penetration_m``, not
        # from the indentation that is left after the support has settled.  It therefore
        # picks up no chain factor through the compliance.  An earlier version scaled
        # both branches by ``elastic_slope / raw`` (the softened slope divided by the raw
        # Hertz one), which is 1/55 on a case with G ~ 1e-8 and left every velocity
        # column 55x too soft -- invisible on the compliance-free case the gate used.
        if law.damping_policy == "hunt_crossley":
            from .contact import hunt_crossley_coefficient
            coefficient = hunt_crossley_coefficient(stiffness, law.restitution_coefficient,
                                                    law.damping_reference_speed_m_s)
            depth_slope = 1.5 * coefficient * math.sqrt(depth) * approach
            rate_slope = coefficient * depth ** 1.5
        else:
            coefficient = law.normal_damping_n_s_m_1p5
            depth_slope = 0.5 * coefficient / math.sqrt(depth) * approach
            rate_slope = coefficient * math.sqrt(depth)
        if law.damping_force_cap_ratio is not None:
            cap = law.damping_force_cap_ratio * abs(response.normal_elastic_n)
            if abs(response.normal_damping_n) >= cap - 1.0e-12:
                # Cap active: damping tracks the elastic force and stops responding
                # to the approach speed, so only the depth slope survives.
                sign = 1.0 if response.normal_damping_n >= 0.0 else -1.0
                depth_slope = sign * law.damping_force_cap_ratio * elastic_slope
                rate_slope = 0.0
        if response.normal_force_n <= 0.0:
            return 0.0, 0.0, 0.0
        return elastic_slope, elastic_slope + depth_slope, rate_slope

    def _creep_slopes(self, response: ContactResponse, normal_force: float):
        """Slopes of the saturated creep law at the current slip.

        Returns ``(linear_x, linear_lateral, scale, d_scale_d_demand,
        d_scale_d_limit)`` where ``T = scale * linear``.
        """
        law = self.law
        limit = law.friction_coefficient * normal_force
        linear_x = -law.creep_stiffness_x_n * response.slip_x_m_s / self.reference_speed
        linear_lateral = (-law.creep_stiffness_lateral_n * response.slip_lateral_m_s
                          / self.reference_speed)
        demand = math.hypot(linear_x, linear_lateral)
        if demand <= 0.0:
            # Vanishing demand is the free-rolling limit: shape -> ratio, so
            # ``scale = limit * shape / demand -> 1``.  Returning zero here would
            # delete the whole creep stiffness exactly where the wheelset rolls
            # without slip, which turns the Newton matrix singular instead of
            # stiff (silent: the integrator only shrinks its step).
            return linear_x, linear_lateral, 1.0, 0.0, 0.0
        if limit <= 0.0:
            return linear_x, linear_lateral, 0.0, 0.0, 0.0
        if demand <= 3.0 * limit:
            ratio = demand / limit
            shape = ratio - ratio * ratio / 3.0 + ratio ** 3 / 27.0
            dshape = 1.0 - 2.0 * ratio / 3.0 + ratio * ratio / 9.0
        else:
            ratio = demand / limit
            shape = 1.0
            dshape = 0.0
        magnitude = limit * shape
        scale = magnitude / demand
        d_scale_d_demand = (dshape - scale) / demand
        # d(scale)/d(limit) with ratio = demand/limit and d(ratio)/d(limit) = -ratio/limit:
        #   d/dlimit [limit * shape(ratio) / demand]
        #     = (shape + limit * dshape * (-ratio/limit)) / demand
        #     = (shape - ratio * dshape) / demand
        # Dividing by ``limit`` instead of ``demand`` scales this term by
        # demand/limit = ratio, which happens to be 1 only on the saturation
        # boundary -- the finite-difference check in the tests caught it at
        # every other ratio.
        d_scale_d_limit = (shape - ratio * dshape) / demand
        return linear_x, linear_lateral, scale, d_scale_d_demand, d_scale_d_limit

    def _contact_modes(self, wheel: int, y_row: np.ndarray, z_row: np.ndarray,
                       geometry, elastic_slope: float) -> np.ndarray | None:
        """Rows that carry the five rigid contact modes into generalized coordinates.

        ``(5, n)`` with the modes in :data:`velch.contact.CONTACT_MODES` order, or
        ``None`` when this geometry carries no strip gradients (a point contact, or
        the cached-grid variant), in which case the frozen-angle form stands.
        """
        partials = getattr(geometry, "partials", None)
        if partials is None or not partials.normal_force_n or elastic_slope <= 0.0:
            return None
        modes = np.zeros((5, self.n))
        modes[0, wheel] = 1.0
        modes[1, wheel + 1] = 1.0
        modes[2, wheel + 2] = 1.0
        modes[3] = y_row
        modes[4] = z_row
        return modes

    # -- assembly ------------------------------------------------------------
    def blocks(self, t_s: float, q: np.ndarray, v: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Return ``d(f/m)/dq`` and ``d(f/m)/dv`` at one state.

        The contact search keeps memory (seeds, body attribution), so the probe is
        bracketed by a snapshot/restore: asking for a Jacobian must never change the
        trajectory the integrator sees.
        """
        snapshot = self.dynamics.snapshot_contact_state()
        had_partials = getattr(self.dynamics, "contact_partials", False)
        self.dynamics.contact_partials = True
        try:
            return self._blocks_at(t_s, q, v)
        finally:
            self.dynamics.contact_partials = had_partials
            self.dynamics.restore_contact_state(snapshot)

    def _blocks_at(self, t_s: float, q: np.ndarray,
                   v: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        dynamics = self.dynamics
        dynamics.evaluate(t_s, q, v)  # refreshes the per-body contact cache
        jacobian_q = self._stiffness_q + self._track_q
        jacobian_v = self._stiffness_v + self._track_v
        cfg = dynamics.case.vehicle
        law = self.law
        for rail_index, rail in enumerate(dynamics.case.rails):
            x_m = (dynamics.case.run.x_start_m + cfg.travel_speed_m_s * t_s
                   + cfg.axle_offsets_m[rail.axle_index])
            support_compliance = (self.support.at(x_m) if self.support is not None else None)
            wheel = self.dynamics.topology.offset(
            self.dynamics.topology.wheelset_id(rail.axle_index))
            y_row, z_row = self._rail_rows(rail_index, x_m)
            for response in dynamics.body_contacts.get(rail.id, ()):
                geometry = response.geometry
                if not response.active or geometry is None or geometry.penetration_m <= 0.0:
                    continue
                row = self._kinematic_row(rail_index, x_m, geometry)
                normal_row, tangent_row, longitudinal_row = self._generalized_rows(
                    rail_index, x_m, geometry)
                elastic_slope, depth_slope, rate_slope = self._normal_slopes(
                    response, geometry, support_compliance)
                normal_dq = depth_slope * row
                normal_dv = rate_slope * row
                mode_rows = self._contact_modes(wheel, y_row, z_row, geometry,
                                               elastic_slope)
                if mode_rows is not None:
                    # A strip contact publishes its real d(delta)/dq: the band
                    # average of the depth gradient, taken against the profile
                    # slopes, instead of the frozen-angle lever arm of a point.
                    #
                    # ``partials.normal_force_n`` is dN/dq of the strip's *own* Hertz
                    # functional, which knows nothing about the support compliance.
                    # Dividing it by the compliance-softened ``elastic_slope`` makes the
                    # two chain factors cancel and deletes the softening from the q block
                    # (55x too stiff at G ~ 1e-8, 12 columns over the gate).  Divide by
                    # the raw Hertz slope to recover d(delta)/dq, then re-apply the total
                    # slope to it.
                    depth_local = geometry.penetration_m
                    stiffness_local = geometry.stiffness_n_m_1p5
                    if stiffness_local is None:
                        stiffness_local = law.normal_stiffness_n_m_1p5
                    raw_slope = (1.5 * stiffness_local * math.sqrt(depth_local)
                                 if depth_local > 0.0 else 0.0)
                    if raw_slope <= 0.0:
                        raw_slope = elastic_slope
                    depth_gradient = ((np.asarray(geometry.partials.normal_force_n)
                                       / raw_slope) @ mode_rows)
                    normal_dq = depth_slope * depth_gradient
                    # The approach speed carries the prescribed grade term
                    # ``travel * rail_dz_ds * normal_z``, and the damping branch is
                    # proportional to it (rate_slope).  Both the grade reading and the
                    # normal's z component move with the contact point, so on a
                    # station with a non-zero longitudinal gradient this is the whole
                    # q-dependence of the damping channel -- 8e-5 on the rail rows at
                    # the worst gate station before it was added.
                    d_dz_ds = np.asarray(geometry.partials.rail_dz_ds)
                    d_normal_z = (geometry.normal_y * geometry.normal_z ** 2
                                  * np.asarray(geometry.partials.normal_slope))
                    d_approach = self.speed * (d_dz_ds * geometry.normal_z
                                               + geometry.rail_dz_ds * d_normal_z)
                    normal_dq = normal_dq + rate_slope * (d_approach @ mode_rows)

                (linear_x, linear_lateral, scale,
                 d_scale_d_demand, d_scale_d_limit) = self._creep_slopes(
                    response, response.normal_force_n)
                demand = math.hypot(linear_x, linear_lateral)
                friction = law.friction_coefficient
                # dT_i/d(linear_i) accounting for the saturation's own dependence
                gain_x = scale + (linear_x * linear_x * d_scale_d_demand / demand
                                  if demand > 0.0 else 0.0)
                gain_lat = scale + (linear_lateral * linear_lateral * d_scale_d_demand / demand
                                    if demand > 0.0 else 0.0)
                # dT_i/dN through limit = mu * N
                d_t_x_d_normal = linear_x * d_scale_d_limit * friction
                d_t_lat_d_normal = linear_lateral * d_scale_d_limit * friction

                slope_x = -law.creep_stiffness_x_n / self.reference_speed
                slope_lat = -law.creep_stiffness_lateral_n / self.reference_speed

                # slip_x = travel + spin * lever_z.  ``spin`` is the wheelset's spin
                # *rate*, i.e. a velocity coordinate, so this column belongs to the
                # d(f/m)/dv block -- putting it in the q block produced a spurious
                # stiffness entry and left the real velocity coupling at zero.
                longitudinal_v = np.zeros(self.n)
                longitudinal_v[wheel + 3] += gain_x * slope_x * geometry.lever_z_m
                # slip_lateral carries the yaw through the creep attack
                tangential_q = np.zeros(self.n)
                tangential_q[wheel + 4] += gain_lat * slope_lat * self.speed

                # slip_lateral velocities: wheel (y, z, roll) minus the rail's own
                ty, tz = geometry.tangent_y, geometry.tangent_z
                tangential_v = np.zeros(self.n)
                tangential_v[wheel] += gain_lat * slope_lat * ty
                tangential_v[wheel + 1] += gain_lat * slope_lat * tz
                tangential_v[wheel + 2] += (gain_lat * slope_lat
                                            * (-ty * geometry.lever_z_m
                                               + tz * geometry.lever_y_m))
                tangential_v -= gain_lat * slope_lat * (ty * y_row + tz * z_row)

                jacobian_q += np.outer(normal_row, normal_dq)
                jacobian_q += np.outer(tangent_row,
                                       tangential_q + d_t_lat_d_normal * normal_dq)
                jacobian_q += np.outer(longitudinal_row, d_t_x_d_normal * normal_dq)
                if mode_rows is not None:
                    # d(generalized row)/dq. A point contact's lever arm is frozen;
                    # a strip's centroid slides with the wheelset, and the lever
                    # multiplies the force directly (N * dlever_y is 3.5e-4 relative
                    # on the roll-moment row -- far above the 1e-5 gate). The normal
                    # and tangent *directions* are stationary: they are read off a
                    # discrete maximum, so their derivative vanishes almost
                    # everywhere and the finite difference agrees to 1e-16.
                    d_lever_y = np.asarray(geometry.partials.lever_y_m)
                    d_lever_z = np.asarray(geometry.partials.lever_z_m)
                    ny, nz = geometry.normal_y, geometry.normal_z
                    normal_force = response.normal_force_n
                    tangent_force = response.lateral_tangent_force_n
                    longitudinal_force = response.longitudinal_force_n
                    jacobian_q[wheel + 2] += (
                        (normal_force * (nz * d_lever_y - ny * d_lever_z)
                         + tangent_force * (tz * d_lever_y - ty * d_lever_z))
                        @ mode_rows)
                    jacobian_q[wheel + 3] += ((longitudinal_force * d_lever_z)
                                              @ mode_rows)
                    jacobian_q[wheel + 4] += ((-longitudinal_force * d_lever_y)
                                              @ mode_rows)
                    # slip_x = travel + spin * lever_z, so the lever drags the
                    # longitudinal creep force too; the velocity block above carries
                    # the spin-rate half of the same term.
                    jacobian_q += np.outer(
                        longitudinal_row,
                        (gain_x * slope_x * v[wheel + 3] * d_lever_z) @ mode_rows)
                    # The normal direction itself rotates when the contact walks
                    # along a curved stretch of the profile. With inv = normal_z and
                    # slope = -normal_y/normal_z,
                    #   d(normal)/ds = (-1, -s) inv^3,  d(tangent)/ds = (-s, 1) inv^3.
                    d_angle = np.asarray(geometry.partials.normal_slope)
                    if np.any(d_angle):
                        inv3 = nz ** 3
                        d_normal_y = -inv3 * d_angle
                        d_normal_z = ny * nz * nz * d_angle
                        d_tangent_y = d_normal_z
                        d_tangent_z = -d_normal_y
                        ly, lz = geometry.lever_y_m, geometry.lever_z_m
                        jacobian_q[wheel] += ((normal_force * d_normal_y
                                               + tangent_force * d_tangent_y)
                                              @ mode_rows)
                        jacobian_q[wheel + 1] += ((normal_force * d_normal_z
                                                   + tangent_force * d_tangent_z)
                                                  @ mode_rows)
                        jacobian_q[wheel + 2] += (
                            (normal_force * (ly * d_normal_z - lz * d_normal_y)
                             + tangent_force * (ly * d_tangent_z - lz * d_tangent_y))
                            @ mode_rows)
                        # The rail reaction turns with the same rotation; it is
                        # linear in the two normal components.
                        for k in range(5):
                            for force, dy_k, dz_k in (
                                    (normal_force, d_normal_y[k], d_normal_z[k]),
                                    (tangent_force, d_tangent_y[k], d_tangent_z[k])):
                                if force == 0.0:
                                    continue
                                turn = np.zeros(self.n)
                                turn[self.dof:] = dynamics.track.contact_reaction(
                                    rail_index, x_m, float(dy_k), float(dz_k))
                                jacobian_q += np.outer(turn, force * mode_rows[k])
                jacobian_v += np.outer(normal_row, normal_dv)
                jacobian_v += np.outer(tangent_row,
                                       tangential_v + d_t_lat_d_normal * normal_dv)
                jacobian_v += np.outer(longitudinal_row,
                                       longitudinal_v + d_t_x_d_normal * normal_dv)
        return jacobian_q / self.mass[:, None], jacobian_v / self.mass[:, None]

    def full(self, t_s: float, q: np.ndarray, v: np.ndarray) -> np.ndarray:
        """The complete ``(2n, 2n)`` Jacobian in ``(q, v)`` ordering."""
        jacobian_q, jacobian_v = self.blocks(t_s, q, v)
        block = np.zeros((2 * self.n, 2 * self.n))
        block[:self.n, self.n:] = np.eye(self.n)
        block[self.n:, :self.n] = jacobian_q
        block[self.n:, self.n:] = jacobian_v
        return block


def frozen_geometry_error(dynamics, t_s: float, q: np.ndarray, v: np.ndarray,
                          step: float = 1.0e-7) -> dict[str, float]:
    """Measure the assembled blocks against a central finite difference.

    Two normalisations are reported, because they answer different questions.

    ``dq`` / ``dv`` are ``max|J_a - J_fd| / max|J_fd|`` -- the block-max norm, which is
    the right *conservative* measure but a poor detector: a column that is wrong by
    100 % reads as a few percent whenever some other column is a thousand times larger
    (a spin column carrying ``lever_z`` squared next to a plain one).  Two defects
    slipped through exactly there.

    ``dq_worst_column`` / ``dv_worst_column`` are per-column:
    ``max_j max_i |J_a[i, j] - J_fd[i, j]| / max_i |J_fd[i, j]|`` over the columns whose
    magnitude is worth trusting, plus how many columns exceed 1e-3.  A wrong chain-rule
    factor or a term written into the wrong block shows up here as ~1.0 even when the
    block-max error is 0.04.
    """
    assembler = JacobianAssembler(dynamics)
    analytic_q, analytic_v = assembler.blocks(t_s, q, v)
    n = dynamics.dimension
    scale = np.maximum(1.0, np.abs(np.concatenate((q, v))))
    finite_q = np.empty((n, n))
    finite_v = np.empty((n, n))
    for index in range(n):
        for block, analytic in ((0, finite_q), (1, finite_v)):
            delta = step * scale[index + block * n]
            state = np.concatenate((q, v))
            plus = state.copy()
            plus[index + block * n] += delta
            minus = state.copy()
            minus[index + block * n] -= delta
            analytic[:, index] = ((dynamics.derivative_pure(t_s, plus)[n:]
                                   - dynamics.derivative_pure(t_s, minus)[n:])
                                  / (2.0 * delta))

    def _column_errors(analytic: np.ndarray, finite: np.ndarray) -> tuple[float, int]:
        """Worst per-column relative error and the number of columns above 1e-3."""
        column_scale = np.max(np.abs(finite), axis=0)
        # Columns whose finite-difference magnitude is at roundoff level carry no
        # information: the absolute difference there is noise, not a chain-rule error.
        floor = max(1.0e-9, 1.0e-6 * float(column_scale.max(initial=0.0)))
        usable = column_scale > floor
        if not usable.any():
            return 0.0, 0
        error = np.max(np.abs(analytic[:, usable] - finite[:, usable]), axis=0) \
            / column_scale[usable]
        return float(error.max()), int(np.count_nonzero(error > 1.0e-3))

    dq_worst, dq_bad = _column_errors(analytic_q, finite_q)
    dv_worst, dv_bad = _column_errors(analytic_v, finite_v)
    return {
        "dq": float(np.max(np.abs(analytic_q - finite_q)) / np.max(np.abs(finite_q))),
        "dv": float(np.max(np.abs(analytic_v - finite_v)) / np.max(np.abs(finite_v))),
        "dq_worst_column": dq_worst,
        "dv_worst_column": dv_worst,
        "dq_bad_columns": float(dq_bad),
        "dv_bad_columns": float(dv_bad),
    }
