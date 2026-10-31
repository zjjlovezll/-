"""SI-only case contract for one prescribed-speed wheelset and flexible rails."""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .contact import ContactParameters
from .profiles import GraphProfile, ProfileSeries, Station, load_profile


def _finite(name: str, value: Any, *, positive: bool = False, nonnegative: bool = False) -> float:
    number = float(value)
    if not math.isfinite(number) or positive and number <= 0 or nonnegative and number < 0:
        raise ValueError(f"{name} must be a finite SI value with the required sign")
    return number


@dataclass(frozen=True)
class Wheelset:
    mass_kg: float
    roll_inertia_kg_m2: float
    spin_inertia_kg_m2: float
    gravity_m_s2: float
    travel_speed_m_s: float
    drive_torque_nm: float

    def __post_init__(self) -> None:
        for name in ("mass_kg", "roll_inertia_kg_m2", "spin_inertia_kg_m2"):
            _finite(name, getattr(self, name), positive=True)
        _finite("gravity_m_s2", self.gravity_m_s2, nonnegative=True)
        _finite("travel_speed_m_s", self.travel_speed_m_s)
        _finite("drive_torque_nm", self.drive_torque_nm)


@dataclass(frozen=True)
class Wheel:
    id: str
    lateral_offset_m: float
    profile: GraphProfile

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("wheel ID required")
        _finite("lateral_offset_m", self.lateral_offset_m)


@dataclass(frozen=True)
class LinearSupport:
    k_y_n_m: float
    c_y_n_s_m: float
    k_z_n_m: float
    c_z_n_s_m: float
    # Second track layer (two_layer track kind only). The rail sits on this
    # support; the sleeper mass and the ballast below it are what give the
    # track its low-frequency (30-60 Hz) content -- see
    # validation/turnout18_ref/S1F_TRACK_LAYERS_2026-10-20.md.
    sleeper_mass_y_kg: float = 0.0
    sleeper_mass_z_kg: float = 0.0
    ballast_k_y_n_m: float = 0.0
    ballast_c_y_n_s_m: float = 0.0
    ballast_k_z_n_m: float = 0.0
    ballast_c_z_n_s_m: float = 0.0

    def __post_init__(self) -> None:
        for name in ("k_y_n_m", "c_y_n_s_m", "k_z_n_m", "c_z_n_s_m",
                     "sleeper_mass_y_kg", "sleeper_mass_z_kg",
                     "ballast_k_y_n_m", "ballast_c_y_n_s_m",
                     "ballast_k_z_n_m", "ballast_c_z_n_s_m"):
            _finite(name, getattr(self, name), nonnegative=True)


@dataclass(frozen=True)
class TrackLayer:
    """One layer of the track stack below the steel rail.

    `k_*`/`c_*` describe the spring and damper *below* this layer, so a sleeper
    layer carries the ballast stiffness, a slab layer carries the subgrade
    stiffness. The rail itself is not a layer: it is part of the vehicle rail
    patch and sits on the fastening/pad stiffness.
    """

    mass_y_kg: float
    mass_z_kg: float
    k_y_n_m: float
    c_y_n_s_m: float
    k_z_n_m: float
    c_z_n_s_m: float

    def __post_init__(self) -> None:
        for name in ("mass_y_kg", "mass_z_kg"):
            _finite(name, getattr(self, name), positive=True)
        for name in ("k_y_n_m", "c_y_n_s_m", "k_z_n_m", "c_z_n_s_m"):
            _finite(name, getattr(self, name), nonnegative=True)


@dataclass(frozen=True)
class WheelSuspension:
    support: LinearSupport
    k_roll_nm_rad: float
    c_roll_nm_s_rad: float
    y_reference_m: float
    z_reference_m: float
    roll_reference_rad: float

    def __post_init__(self) -> None:
        for name in ("k_roll_nm_rad", "c_roll_nm_s_rad"):
            _finite(name, getattr(self, name), nonnegative=True)
        for name in ("y_reference_m", "z_reference_m", "roll_reference_rad"):
            _finite(name, getattr(self, name))


@dataclass(frozen=True)
class RailPatch:
    id: str
    wheel_id: str
    mass_y_kg: float
    mass_z_kg: float
    support: LinearSupport
    profiles: ProfileSeries

    def __post_init__(self) -> None:
        if not self.id or not self.wheel_id:
            raise ValueError("rail and wheel IDs required")
        _finite("mass_y_kg", self.mass_y_kg, positive=True)
        _finite("mass_z_kg", self.mass_z_kg, positive=True)


@dataclass(frozen=True)
class RunSettings:
    method: str
    x_start_m: float
    duration_s: float
    output_step_s: float
    max_solver_step_s: float
    rtol: float
    atol: float
    maximum_penetration_m: float
    maximum_abs_contact_slope: float
    contact_search_half_width_m: float | None = None
    body_hysteresis: bool = False
    contact_seed_scope: str = "body"
    jacobian: str | None = None
    refine_peak: bool = False
    #: Apply the longitudinal tangential force to a wheelset that solves ``x``.  Off by default:
    #: with x free the vehicle is a free body, and the unbalanced longitudinal force also enters
    #: the yaw row through its lever arm, which walks the contact across the profile until
    #: ``maximum_abs_contact_slope`` trips.  Turn it on only for a case whose longitudinal
    #: behaviour is the thing being measured (the wheel-polygon runs).
    longitudinal_force: bool = False
    #: Drive each wheelset's spin towards ``v(t) / r`` with a first-order servo.  Needed as
    #: soon as the speed varies: the spin is integrated from the contact force, and if it lags
    #: the schedule the mismatch is booked as longitudinal creep, saturates, and eats lateral
    #: force through ``hypot``.  A constant profile leaves this off, so its results stay
    #: bit-identical; a multi-leg profile turns it on automatically.
    spin_control: bool = False
    #: How fast the vehicle is going, as a value rather than a single number.  Either
    #: ``{"constant": {"speed_kmh": 80}}`` or ``{"legs": [{"speed_kmh": 80, "duration_s": 2}]}``.
    #: A constant profile becomes ``vehicle.travel_speed_m_s`` and changes nothing; a
    #: multi-leg profile is parsed and carried on the case, but the solver refuses it until
    #: the wheelset spin tracks ``v/r`` -- without that, a varying ``v`` turns the creep
    #: reference into a fake longitudinal demand.
    speed_profile: dict | None = None
    #: Radius of a constant-radius curve, in metres, or ``None`` for a straight track.  The
    #: solver keeps the track straight and adds the curve as a lateral body force
    #: ``m v^2 / R`` (equivalent straight track).  Cant beyond ``curve_cant_m`` is not
    #: modelled, and the static seat solves vertical coordinates only, so a canted case
    #: seats on one side — keep ``curve_cant_m`` small or zero.
    curve_radius_m: float | None = None
    #: Cant (superelevation) in metres across the gauge; enters as ``m g sin(theta)`` inward.
    curve_origin_m: float | None = None
    """Mileage where the design line's tangent is.  ``None`` means the run start.

    Only meaningful with ``curve_radius_m``; before the tangent the line is straight (see
    ``_arc_parameter_m``).  Refused together with a cant, because the canted geometry route is
    itself refused (docs/CURVE_CANT_DECISION_2026-10-27.md).
    """
    curve_cant_m: float = 0.0
    #: Give the alignment to the contact geometry as well, not only to the body force: the rail's
    #: absolute position then follows ``y(s) = (s - s0)^2 / (2R)`` and its transverse velocity picks
    #: up ``v * dy/ds``.  Off by default so every existing (equivalent-straight) case keeps its
    #: numbers bit for bit; turning it on for a curved case is what lets the wheelset yaw along the
    #: curve instead of being dragged flange-first (measured: 1.17 m of missing yaw over the
    #: footprint at R = 350 m).
    #: Mileage at which to solve the static seat.  A turnout's diverging route is *entered*:
    #: the vehicle stands on the straight lead (where both rails are level and parallel) and the
    #: curve arrives with mileage.  Seating at the diverging mileage instead asks for a static
    #: equilibrium on rails that are already rotated and offset, which has no solution -- measured
    #: on case_diverging_R1100 at 80 km/h: 7 of 8 wheels loaded from 69 m, 4 of 8 from 30 m.
    seat_x_start_m: float | None = None
    seat_templates: tuple[str, ...] | None = None
    """Rail template ids the static seat may touch; None means every rail.

    A turnout carries the through and the diverging route at the same mileage, so a
    vehicle placed once cannot seat on both: measured 4 of 8 wheels carrying load at
    30 m until the seat is restricted to the through group.
    """
    seat_modal_scales: tuple[float, ...] | None = None
    """Tread-deflection scales the seat retries from, before it declares no solution.

    The seat is an initialisation, not physics, and it already tries several vertical seeds.  The
    modal coordinates it is handed are one more starting coordinate: on the one-set turnout case at
    60 km/h the adaptively-damped settle lands on a legal 1.06 mm tread (round 296) and the plain
    start then has no vertical solution, while 80 km/h closes from the same first seat.  Each scale
    multiplies the modal block before a retry; ``1.0`` is always tried first, so cases that already
    seat never take a second pass.  ``None`` means ``(1.0, 0.8, 0.95, 1.05, 0.5)``.
    """
    seat_lateral: bool = False
    """Also put each wheelset where its own net lateral force vanishes.

    The vertical seat solves ``z`` only.  On a *flexible* wheelset the tread deflects
    asymmetrically -- measured on the one-set turnout case at 80 km/h: left contact tilt
    ``+0.024782`` against right ``-0.021744``, so the seated state carries a net ``+736.5 N``
    (per axle ``+184 N``) and the whole vehicle walks ``+0.73 mm`` in 0.40 s with zero initial
    lateral velocity.  The equilibrium is a scalar problem *per wheelset* (find ``y`` with
    ``F_y = 0``), which this flag solves after the vertical/modal seat.  Off by default so every
    frozen baseline keeps its numbers bit for bit.
    """
    curve_geometry: bool = False
    # Place the vehicle on the sampled track's own centreline and tangent.  A turnout's diverging
    # route is curved through its station table, not through curve_radius_m, so without this the
    # vehicle starts straight at 69 m where the design line has already moved 0.154 m and turned
    # 0.017 rad (7 of 8 wheels then carry load, one side at twice the share).
    align_to_track: bool = False

    #: Whether the vehicle is moved onto the alignment (per-body ``y`` from its own mileage, yaw
    #: from ``s / R``).  ``None`` follows :attr:`curve_geometry`, so nothing that exists changes;
    #: ``True`` with ``curve_geometry`` off puts the wheelset at an angle of attack on a straight
    #: rail table — the steering half of a curve without the geometry half.
    curve_placement: bool | None = None

    #: Direction of the frame's fictitious lateral force, ``m v^2 / R``, on the route that keeps the
    #: rails straight and injects the curving load as a body force.  ``1.0`` is the sign every
    #: existing case was measured with and stays the default; ``-1.0`` exists because the sign is
    #: *not* a free parameter on a station-table curve -- the line ``y = s^2 / (2R)`` turns towards
    #: +y, so its centre sits at +y and the inertia force on the vehicle points towards -y.  A
    #: diagnostic run with the opposite sign is what decides between the two, and the emitted case
    #: records it so no result can be quoted without it.
    curve_lateral_sign: float = 1.0

    #: Look for a *second* local extremum of the clearance on the same wheel-rail side instead of
    #: keeping only the deepest one.  Two-point contact is what a wheelset actually does once the
    #: tread and the flange root both touch, and the algorithms that do it (L12: contact-line and
    #: conformal two-point methods) find every local minimum of the clearance, not just the global
    #: one.
    #:
    #: On by default, and that is a measurement rather than optimism.  The frozen static anchor
    #: (59 680.5769 N per contact, -0.4628 mm) was calibrated with one point per rail, so the
    #: multi-point search has to return exactly that when there is only one body in contact --
    #: measured with the flag on: eight rails, one active contact each, 59 680.5769 N, vertical
    #: -0.4628 mm, residual 1.88e-08 N, i.e. bit-identical to the flag off.  Getting there needed
    #: two criteria, both measured on ``case_A_plain``: without them the search splits every contact
    #: in two -- 41 400.5 N at y = -0.75277 (154.86 um) plus 18 298.0 N at y = -0.74471 (89.85 um),
    #: two extrema **8.06 mm apart on the same rail head**, which is one Hertzian footprint seen
    #: through the profile's own double curvature, not a tread/flange pair (those sit ~55 mm apart).
    contact_two_point: bool = True

    #: Lateral window, in metres, around the deepest contact that the second search excludes.
    #: Two extrema closer than this are one patch: the deeper one already accounts for the shared
    #: Hertzian area, so summing both would double count -- the same reason
    #: ``duplicate_patch_window_m`` exists for two rail bodies in a turnout cross-section.
    #: 12 mm sits above the measured same-head pair (8.06 mm) and far below a tread/flange pair
    #: (~55 mm), so a genuine second body survives and a double-curvature artefact does not.
    contact_two_point_exclusion_m: float = 0.012

    #: Minimum |n_y / n_z| for the second contact to count as a second *body* rather than
    #: another patch of the same tread.  This is the criterion that makes the search a
    #: two-point contact model instead of a multi-lobe tread sampler: the tread is nearly
    #: flat (measured |n_y/n_z| = 0.025 at the crown) while a flange root is steep by nature,
    #: and it is the flange -- not a second flat lobe -- that lets a wheelset carry a curving
    #: load.  Measured on ``case_A_plain`` with the flag on and no slope criterion: a second
    #: flat lobe splits every contact and moves the frozen anchor to 59 698.5 N at 52 um,
    #: which is why the criterion is not optional.
    contact_two_point_min_slope: float = 0.25

    def __post_init__(self) -> None:
        if self.method not in {"DOP853", "Radau", "BDF"}:
            raise ValueError("supported methods are DOP853, Radau and BDF")
        if self.jacobian not in {None, "sparse_fd", "analytic"}:
            raise ValueError("jacobian must be None, 'sparse_fd' or 'analytic'")
        if self.jacobian is not None and self.method == "DOP853":
            # solve_ivp silently ignores jac/jac_sparsity for explicit solvers and only
            # emits a UserWarning, so a case could claim an analytic Jacobian and quietly
            # integrate without one.  Fail loudly instead: A/B comparisons made on top of
            # that warning are wrong in a way nothing else catches.
            raise ValueError("jacobian is only used by the implicit methods (Radau/BDF)")
        _finite("x_start_m", self.x_start_m)
        for name in ("duration_s", "output_step_s", "max_solver_step_s", "rtol", "atol",
                     "maximum_penetration_m", "maximum_abs_contact_slope"):
            _finite(name, getattr(self, name), positive=True)
        if self.contact_search_half_width_m is not None:
            _finite("contact_search_half_width_m", self.contact_search_half_width_m, positive=True)
        if self.curve_radius_m is not None:
            _finite("curve_radius_m", self.curve_radius_m, positive=True)
        if self.curve_lateral_sign not in (1.0, -1.0):
            raise ValueError("curve_lateral_sign must be +1.0 or -1.0")
        _finite("curve_cant_m", self.curve_cant_m)
        if abs(self.curve_cant_m) > 0.20:
            raise ValueError("curve_cant_m looks like a cant in millimetres; pass metres (0.06 for 60 mm)")
        if not isinstance(self.body_hysteresis, bool):
            raise ValueError("body_hysteresis must be a boolean")
        if self.contact_seed_scope not in ("body", "rail", "rail_hold"):
            raise ValueError("contact_seed_scope must be 'body', 'rail', or 'rail_hold'")
        if self.output_step_s > self.duration_s:
            raise ValueError("output step exceeds duration")
        if not isinstance(self.refine_peak, bool):
            raise ValueError("refine_peak must be a boolean")
        if not isinstance(self.contact_two_point, bool):
            raise ValueError("contact_two_point must be a boolean")
        _finite("contact_two_point_exclusion_m", self.contact_two_point_exclusion_m, positive=True)
        _finite("contact_two_point_min_slope", self.contact_two_point_min_slope, positive=True)


@dataclass(frozen=True)
class Case:
    case_id: str
    purpose: str
    parameter_source: str
    wheelset: Wheelset
    suspension: WheelSuspension
    wheels: tuple[Wheel, ...]
    rails: tuple[RailPatch, ...]
    contact: ContactParameters
    run: RunSettings
    initial_q: tuple[float, ...]
    initial_v: tuple[float, ...]
    case_sha256: str
    source_path: Path
    asset_hashes: dict[str, str]

    def __post_init__(self) -> None:
        if not self.case_id or self.purpose not in {"synthetic", "engineering"} or not self.parameter_source:
            raise ValueError("case identity, purpose, and parameter source are required")
        wheel_ids = {wheel.id for wheel in self.wheels}
        if not wheel_ids or len(wheel_ids) != len(self.wheels):
            raise ValueError("wheel IDs must be unique")
        if not self.rails or len({rail.id for rail in self.rails}) != len(self.rails):
            raise ValueError("rail IDs must be unique")
        if any(rail.wheel_id not in wheel_ids for rail in self.rails):
            raise ValueError("every rail must name a defined wheel")
        dimension = 4 + 2 * len(self.rails)
        if len(self.initial_q) != dimension or len(self.initial_v) != dimension:
            raise ValueError(f"initial q/v must each have {dimension} ordered entries")
        if not all(math.isfinite(value) for value in (*self.initial_q, *self.initial_v)):
            raise ValueError("initial state must be finite")


def _support(raw: dict[str, Any]) -> LinearSupport:
    return LinearSupport(**{key: _finite(key, raw[key], nonnegative=True) for key in
                            ("k_y_n_m", "c_y_n_s_m", "k_z_n_m", "c_z_n_s_m")})


def load_case(path: str | Path) -> Case:
    """Load a declarative JSON case; every external profile is hash recorded."""
    target = Path(path).resolve(strict=True)
    data = target.read_bytes()
    raw = json.loads(data.decode("utf-8"))
    if raw.get("schema_version") != "velch-case-v1":
        raise ValueError("unsupported case schema")
    base = target.parent
    assets: dict[str, str] = {}

    def profile(spec: dict[str, Any], surface: str) -> GraphProfile:
        filename = Path(spec["file"])
        source = (base / filename).resolve(strict=True) if not filename.is_absolute() else filename.resolve(strict=True)
        if spec.get("units") not in {"m", "mm"}:
            raise ValueError("profile source units must explicitly be m or mm")
        if spec["format"] == "prr" and spec["units"] != "m":
            raise ValueError("PRR source unit must agree with its m header")
        unit_scale = 1.0 if spec["units"] == "m" else 1e-3
        parsed = load_profile(source, file_format=spec["format"], surface=surface,
                              y_scale_m=unit_scale,
                              z_scale_m=unit_scale,
                              y_sign=int(spec.get("y_sign", 1)), z_sign=int(spec.get("z_sign", 1)),
                              y_offset_m=float(spec.get("y_offset_m", 0.0)),
                              z_offset_m=float(spec.get("z_offset_m", 0.0)))
        if spec.get("sha256") and spec["sha256"] != parsed.source_sha256:
            raise ValueError(f"profile checksum mismatch: {source}")
        assets[str(source)] = parsed.source_sha256
        return parsed

    wheels = tuple(Wheel(id=item["id"], lateral_offset_m=float(item["lateral_offset_m"]),
                         profile=profile(item["profile"], "wheel_lower")) for item in raw["wheels"])
    rails = []
    for item in raw["rails"]:
        stations = [Station(float(station["s_m"]), profile(station["profile"], "rail_top"),
                            station["id"]) for station in item["stations"]]
        rails.append(RailPatch(item["id"], item["wheel_id"],
                               float(item["mass_y_kg"]), float(item["mass_z_kg"]),
                               _support(item["support"]),
                               ProfileSeries(stations, item.get("event_branches"))))
    suspension_raw = raw["suspension"]
    suspension = WheelSuspension(_support(suspension_raw),
                                  float(suspension_raw["k_roll_nm_rad"]),
                                  float(suspension_raw["c_roll_nm_s_rad"]),
                                  float(suspension_raw["y_reference_m"]),
                                  float(suspension_raw["z_reference_m"]),
                                  float(suspension_raw["roll_reference_rad"]))
    initial = raw["initial_state"]
    wheel_q = initial["wheel_q"]
    wheel_v = initial["wheel_v"]
    q = [float(wheel_q[k]) for k in ("y_m", "z_m", "roll_rad", "spin_rad")]
    v = [float(wheel_v[k]) for k in ("y_m_s", "z_m_s", "roll_rad_s", "spin_rad_s")]
    for rail in rails:
        rail_q = initial["rail_q"][rail.id]
        rail_v = initial["rail_v"][rail.id]
        q.extend((float(rail_q["y_m"]), float(rail_q["z_m"])))
        v.extend((float(rail_v["y_m_s"]), float(rail_v["z_m_s"])))
    return Case(
        case_id=raw["case_id"], purpose=raw["purpose"], parameter_source=raw["parameter_source"],
        wheelset=Wheelset(**raw["wheelset"]), suspension=suspension, wheels=wheels,
        rails=tuple(rails), contact=ContactParameters(**raw["contact"]),
        run=RunSettings(**raw["run"]), initial_q=tuple(q), initial_v=tuple(v),
        case_sha256=hashlib.sha256(data).hexdigest(), asset_hashes=assets,
        source_path=target,
    )
