"""Version-2 vehicle contract: four wheelsets, two bogies, one carbody.

The 35 generalized vehicle coordinates follow the hierarchy observed in the
user's SDITT MATLAB matrix builder. Connector equations are an independent,
energy-consistent small-rotation implementation, not decompiled Simpack code.
"""
from __future__ import annotations

import hashlib
import json
import math
import warnings
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import numpy as np

from .contact import ContactParameters
from .model import LinearSupport, RunSettings, TrackLayer, Wheel
from .paths import PathTrack, load_path
from .topology import legacy_topology, migrate_initial_state, topology_of
from .assets import resolve_asset
from .profiles import ProfileSeries, Station, load_profile
from .support_compliance import SupportCompliance
from .track_models import ModalTrack, load_modal_track
from .speed import SpeedSchedule
from .wheel_modes import ModeSet, load_modes, thesis_crh380a_modes


def finite(name: str, value: Any, *, positive: bool = False, nonnegative: bool = False) -> float:
    result = float(value)
    if not math.isfinite(result) or positive and result <= 0 or nonnegative and result < 0:
        raise ValueError(f"{name} must be finite with the required SI sign")
    return result


@dataclass(frozen=True)
class RigidBody:
    mass_kg: float
    roll_inertia_kg_m2: float
    pitch_inertia_kg_m2: float
    yaw_inertia_kg_m2: float

    def __post_init__(self) -> None:
        for name, value in vars(self).items():
            finite(name, value, positive=True)


@dataclass(frozen=True)
class WheelsetBody:
    mass_kg: float
    roll_inertia_kg_m2: float
    spin_inertia_kg_m2: float
    yaw_inertia_kg_m2: float

    def __post_init__(self) -> None:
        for name, value in vars(self).items():
            finite(name, value, positive=True)


@dataclass(frozen=True)
class SuspensionStage:
    k_y_n_m: float
    c_y_n_s_m: float
    k_z_n_m: float
    c_z_n_s_m: float
    k_yaw_nm_rad: float
    c_yaw_nm_s_rad: float
    half_width_m: float
    upper_anchor_height_m: float
    lower_anchor_height_m: float

    def __post_init__(self) -> None:
        for name, value in vars(self).items():
            finite(name, value, positive=name == "half_width_m", nonnegative=name.startswith(("k_", "c_")))
        if self.k_z_n_m <= 0:
            raise ValueError("vertical suspension stiffness must be positive for preload equilibrium")


@dataclass(frozen=True)
class VehicleParameters:
    carbody: RigidBody
    bogie: RigidBody
    wheelset: WheelsetBody
    primary: SuspensionStage
    secondary: SuspensionStage
    bogie_half_spacing_m: float
    wheelbase_m: float
    wheel_center_height_m: float
    nominal_wheel_radius_m: float
    travel_speed_m_s: float
    gravity_m_s2: float
    drive_torque_per_wheelset_nm: float

    def __post_init__(self) -> None:
        for name in ("bogie_half_spacing_m", "wheelbase_m", "nominal_wheel_radius_m"):
            finite(name, getattr(self, name), positive=True)
        for name in ("wheel_center_height_m", "travel_speed_m_s", "drive_torque_per_wheelset_nm"):
            finite(name, getattr(self, name))
        finite("gravity_m_s2", self.gravity_m_s2, positive=True)

    @property
    def axle_offsets_m(self) -> tuple[float, float, float, float]:
        a, b = self.bogie_half_spacing_m, self.wheelbase_m / 2
        return (a + b, a - b, -a + b, -a - b)


@dataclass(frozen=True)
class RailBody:
    """One physical rail body of a single track side.

    A turnout cross-section carries several independent rail heads on the same
    side of the gauge (stock rail / switch rail, wing rail / point rail). The
    solver resolves one contact per body; merging them into a single profile
    deletes the body identity and lets the contact point jump between heads.
    """

    id: str
    series: ProfileSeries
    s_lo_m: float = float("-inf")
    s_hi_m: float = float("inf")
    y_window_m: tuple[float, float] | None = None

    def active_at(self, s_m: float) -> bool:
        if not (self.s_lo_m <= s_m <= self.s_hi_m):
            return False
        return self.series.covers(s_m)

    def accepts_contact_y(self, y_m: float) -> bool:
        """Lateral gate for body attribution.

        A body whose running surface is not under the wheel tread cannot carry
        load however deep its crown is measured to be. The window is in
        absolute rail coordinates (metres) and is part of the case definition,
        so every run states the attribution rule it used.
        """
        if self.y_window_m is None:
            return True
        lo, hi = self.y_window_m
        return lo <= y_m <= hi


@dataclass(frozen=True)
class VehicleRail:
    id: str
    template_id: str
    axle_index: int
    wheel_id: str
    mass_y_kg: float
    mass_z_kg: float
    support: LinearSupport
    profiles: ProfileSeries
    bodies: tuple[RailBody, ...] = ()

    @property
    def contact_bodies(self) -> tuple[RailBody, ...]:
        return self.bodies or (RailBody(self.id, self.profiles),)


def _irregularity_reach(vehicle, run_raw: dict, track) -> dict:
    """Does any axle actually pass over the stretch this record excites?

    The offset is applied to the sampled surface, so a case whose profiles carry it
    correctly still produces a run identical to no-irregularity if the wheels never reach
    the band.  That failure is completely silent -- it cost a full debugging round -- and
    the whole check is one interval intersection.
    """

    speed = float(vehicle.travel_speed_m_s)
    start = float(run_raw.get("x_start_m", 0.0))
    duration = float(run_raw.get("duration_s", 0.0))
    direction = 1.0 if speed >= 0.0 else -1.0
    mileages = np.asarray(track.s_m, dtype=float)
    active = ((np.abs(np.asarray(track.vertical_m)) > 0.0)
              | (np.abs(np.asarray(track.lateral_m)) > 0.0)
              | (np.abs(np.asarray(track.roll_rad)) > 0.0)
              | (np.abs(np.asarray(track.gauge_m)) > 0.0))
    spans = []
    for offset in vehicle.axle_offsets_m:
        lo = start + offset
        hi = lo + direction * abs(speed) * duration
        spans.append([min(lo, hi), max(lo, hi)])
    if not active.any():
        return {"axles_m": [[round(lo, 3), round(hi, 3)] for lo, hi in spans], "overlaps": False}
    band = (float(mileages[active].min()), float(mileages[active].max()))
    overlaps = any(lo <= band[1] and band[0] <= hi for lo, hi in spans)
    return {"axles_m": [[round(lo, 3), round(hi, 3)] for lo, hi in spans],
            "band_m": [round(band[0], 3), round(band[1], 3)],
            "overlaps": overlaps}


def _track_size(track_kind: str, rails, layers, modal_track: "ModalTrack | None") -> int:
    """Coordinates the track block contributes. One implementation, both call sites."""

    if track_kind == "local_compliant":
        return 2 * len(rails)
    if track_kind == "two_layer":
        return 4 * len(rails)
    if track_kind == "layered":
        return 2 * (1 + len(layers)) * len(rails)
    return modal_track.mode_count if modal_track else 0


def vehicle_parameters(block: dict[str, Any]) -> VehicleParameters:
    """Build the parameter object from a ``vehicle`` block (inline or from a vehicle file).

    One implementation, because two callers (a case that inlines the block and a case that points at
    a vehicle file) must not be able to interpret the same fields differently.
    """

    return VehicleParameters(
        RigidBody(**block["carbody"]), RigidBody(**block["bogie"]),
        WheelsetBody(**block["wheelset"]),
        SuspensionStage(**block["primary"]), SuspensionStage(**block["secondary"]),
        **{key: block[key] for key in ("bogie_half_spacing_m", "wheelbase_m",
                                       "wheel_center_height_m", "nominal_wheel_radius_m",
                                       "travel_speed_m_s", "gravity_m_s2",
                                       "drive_torque_per_wheelset_nm")},
    )


def _modal_size(modes: "dict[int, ModeSet] | None") -> int:
    """Coordinates the flexible-wheelset blocks contribute (they sit after the track block)."""

    return sum(len(item.modes) for item in modes.values()) if modes else 0


def _load_wheel_modes(spec: "dict | None", vehicle, case_path: Path,
                      assets: dict[str, str]) -> "dict[int, ModeSet] | None":
    """Parse the ``flexible_wheelset`` block: which wheelsets, and where their modes come from.

    ``source`` is either ``"table-2-3"`` (the thesis's free-free modal table, shipable now) or
    ``"file"`` (a ``velch-wheel-modes/1`` document exported from ANSYS).  Both produce the same
    object, so swapping the numbers later changes nothing downstream.
    """

    if not spec:
        return None
    source = str(spec.get("source", "table-2-3"))
    radius = float(spec.get("radius_m", vehicle.nominal_wheel_radius_m))
    if source in ("table-2-3", "thesis"):
        modes = thesis_crh380a_modes(radius_m=radius, cutoff_hz=float(spec.get("cutoff_hz", 2000.0)))
    elif source == "file":
        if "file" not in spec:
            raise ValueError("flexible_wheelset with source 'file' needs a 'file' entry")
        # ``lib:`` reaches the mode set that ships inside the package; a plain name is still
        # relative to the case file, so existing documents keep working unchanged.
        resolved = resolve_asset(spec["file"], case_path=case_path, kind="wheel mode set")
        path = resolved.path
        modes = load_modes(path)
        assets[str(path)] = resolved.sha256
    else:
        raise ValueError(f"unknown flexible_wheelset source {source!r}: use 'table-2-3' or 'file'")
    axles = spec.get("axles", [1, 2, 3, 4])
    result: dict[int, ModeSet] = {}
    for axle in axles:
        number = int(axle)
        if number not in (1, 2, 3, 4):
            raise ValueError("flexible_wheelset axles are 1-based wheelset numbers 1..4")
        result[number - 1] = modes
    if not result:
        raise ValueError("flexible_wheelset selects no axles")
    return result


@dataclass(frozen=True)
class WheelPolygon:
    """Out-of-round wheel: a radial deviation that repeats every ``1/order`` of a revolution.

    Written as ``R(theta) = R0 + depth * cos(order * theta + phase)``.  A polygon is the cleanest
    way to excite two things at once: the tread radius changes (so the longitudinal creepage
    changes, which is what the wheelset's longitudinal coordinate is for) and the contact surface
    moves vertically (so the axle-box vertical channel sees it exactly like a corrugation of
    wavelength ``2 pi R / order``).

    The profile's ``z`` is measured downwards from the wheel centre (``R = -z``), so a larger
    radius is a *lower* ``z``; the solver subtracts this shift for that reason.
    """

    order: int
    depth_m: float
    phase_rad: float = 0.0

    def __post_init__(self) -> None:
        if int(self.order) != self.order or self.order < 1:
            raise ValueError(f"wheel polygon order must be a positive integer, got {self.order!r}")
        if not self.depth_m > 0.0:
            raise ValueError(f"wheel polygon depth must be positive, got {self.depth_m!r}")

    def radius_offset_m(self, spin_rad: float) -> float:
        """Radial deviation at a wheel rotation angle."""

        return self.depth_m * math.cos(self.order * float(spin_rad) + self.phase_rad)

    def wavelength_m(self, radius_m: float) -> float:
        return 2.0 * math.pi * float(radius_m) / self.order

    def frequency_hz(self, speed_m_s: float, radius_m: float) -> float:
        """Passing frequency at a running speed: ``order * v / (2 pi R)``."""

        return self.order * abs(float(speed_m_s)) / (2.0 * math.pi * float(radius_m))


@dataclass(frozen=True)
class VehicleCase:
    case_id: str
    purpose: str
    parameter_source: str
    vehicle: VehicleParameters
    wheels: tuple[Wheel, ...]
    rails: tuple[VehicleRail, ...]
    track_kind: str
    modal_track: ModalTrack | None
    contact: ContactParameters
    run: RunSettings
    initial_q: tuple[float, ...]
    initial_v: tuple[float, ...]
    equilibrate_vertical: bool
    source_path: Path
    case_sha256: str
    asset_hashes: dict[str, str]
    support_compliance: SupportCompliance | None = None
    track_layers: tuple[TrackLayer, ...] = ()
    path: "PathTrack | None" = None
    topology: "dict | None" = None
    #: What irregularity was applied (``.tre`` path, window, channels), or ``None``.
    irregularity: "dict | None" = None
    #: Flexible wheelsets, zero-based axle number → its modal set, or ``None`` for rigid wheels.
    wheel_modes: "dict[int, ModeSet] | None" = None
    wheel_polygon: WheelPolygon | None = None
    #: Parsed `run.speed_profile`; a constant profile also sets `vehicle.travel_speed_m_s`.
    speed_schedule: "SpeedSchedule | None" = None

    def __post_init__(self) -> None:
        if not self.case_id or self.purpose not in {"synthetic", "engineering"} or not self.parameter_source:
            raise ValueError("case ID, purpose, and parameter source required")
        wheel_ids = {item.id for item in self.wheels}
        if len(wheel_ids) != len(self.wheels) or len(wheel_ids) != 2:
            raise ValueError("v2 requires two uniquely identified wheel sides")
        rail_ids = {item.id for item in self.rails}
        if not self.rails or len(rail_ids) != len(self.rails):
            raise ValueError("rail patch IDs must be unique")
        if any(item.axle_index not in range(4) or item.wheel_id not in wheel_ids for item in self.rails):
            raise ValueError("rail patch must name one of four axles and a defined wheel side")
        if any(not any(item.axle_index == i for item in self.rails) for i in range(4)):
            raise ValueError("each axle requires at least one rail patch")
        if self.track_kind not in {"rigid", "local_compliant", "two_layer", "layered", "modal"}:
            raise ValueError("unknown track dynamics kind")
        if (self.track_kind == "modal") != (self.modal_track is not None):
            raise ValueError("modal track kind requires a modal exchange file")
        # The vehicle block is whatever the topology declared; only the track block below it
        # depends on the track kind.  With the legacy layout this is the historical 35, and a
        # flexible wheelset appends its modal coordinates after the track block.
        n = (topology_of(self.topology, self.vehicle).body_dimension
             + _track_size(self.track_kind, self.rails, self.track_layers, self.modal_track)
             + _modal_size(self.wheel_modes))
        if len(self.initial_q) != n or len(self.initial_v) != n:
            raise ValueError(f"initial q/v must each have {n} coordinates")
        if any(not math.isfinite(x) for x in (*self.initial_q, *self.initial_v)):
            raise ValueError("initial state must be finite")


def load_vehicle_case(path: str | Path) -> VehicleCase:
    target = Path(path).resolve(strict=True)
    raw_bytes = target.read_bytes()
    raw = json.loads(raw_bytes.decode("utf-8"))
    # The speed profile has to be applied *before* anything reads the speed: the initial
    # wheelset spin is derived from ``travel_speed_m_s`` further down, so a constant profile
    # applied at the end of this function would leave the spin at the replaced value and the
    # run would differ in the last bits despite claiming the same speed.
    speed_schedule = None
    if isinstance(raw.get("run"), dict) and raw["run"].get("speed_profile") is not None:
        speed_schedule = SpeedSchedule.from_spec(raw["run"]["speed_profile"])
        if speed_schedule.is_constant:
            raw["vehicle"]["travel_speed_m_s"] = speed_schedule.constant_speed_m_s
    # ``case_sha256`` must stay the hash of the file on disk, not of the view built above.
    case_digest = hashlib.sha256(raw_bytes).hexdigest()
    if raw.get("schema_version") != "velch-vehicle-v2":
        raise ValueError("unsupported vehicle case schema")
    base = target.parent
    assets: dict[str, str] = {}

    def profile(spec: dict[str, Any], surface: str):
        source = resolve_asset(spec["file"], case_path=target, kind="profile").path
        units = spec.get("units")
        if units not in {"m", "mm"} or spec["format"] == "prr" and units != "m":
            raise ValueError("profile units must be m or mm; PRR must be m")
        scale = 1.0 if units == "m" else 0.001
        parsed = load_profile(source, file_format=spec["format"], surface=surface,
                              y_scale_m=scale, z_scale_m=scale,
                              y_sign=int(spec.get("y_sign", 1)), z_sign=int(spec.get("z_sign", 1)),
                              y_offset_m=float(spec.get("y_offset_m", 0)),
                              z_offset_m=float(spec.get("z_offset_m", 0)),
                              roll_rad=float(spec.get("roll_rad", 0.0)),
                              roll_pivot_y_m=float(spec.get("roll_pivot_y_m", 0.0)),
                              roll_pivot_z_m=float(spec.get("roll_pivot_z_m", 0.0)))
        if spec.get("sha256") and parsed.source_sha256 != spec["sha256"]:
            raise ValueError(f"profile hash mismatch: {source}")
        assets[str(source)] = parsed.source_sha256
        return parsed

    def support(spec: dict[str, Any]) -> LinearSupport:
        return LinearSupport(**spec)

    def _y_window(raw_window: Any, body_id: str) -> tuple[float, float] | None:
        if raw_window is None:
            return None
        lo, hi = raw_window
        lo, hi = float(lo), float(hi)
        if not (lo < hi):
            raise ValueError(f"body {body_id}: y_window_m must be increasing, got {raw_window}")
        return lo, hi

    v = raw.get("vehicle")
    reference = raw.get("vehicle_ref")
    if v is not None and reference is not None:
        # 两个来源同时存在就必然漂移：哪个才是真的？拒绝，让人删掉一个。
        raise ValueError("case carries both 'vehicle' and 'vehicle_ref': keep exactly one")
    if v is None:
        if reference is None:
            raise ValueError("case must carry either 'vehicle' or 'vehicle_ref'")
        from .vehicle_db import load as load_vehicle_model

        model = load_vehicle_model(str(reference))
        v = model.block
        # 把车辆文件也记进 assets：它是这台车唯一的定义，改了就必须让 manifest 校验失败。
        assets[str(model.path)] = hashlib.sha256(model.path.read_bytes()).hexdigest()
    vehicle = vehicle_parameters(v)
    wheels = tuple(Wheel(item["id"], float(item["lateral_offset_m"]),
                         profile(item["profile"], "wheel_lower")) for item in raw["wheels"])
    rails = []
    for template in raw["rail_templates"]:
        if template.get("bodies"):
            bodies = tuple(
                RailBody(
                    str(item["id"]),
                    ProfileSeries(
                        [Station(float(entry["s_m"]), profile(entry["profile"], "rail_top"), entry["id"])
                         for entry in item["stations"]],
                        item.get("event_branches") or template.get("event_branches"),
                    ),
                    float(item.get("s_lo_m", "-inf")),
                    float(item.get("s_hi_m", "inf")),
                    _y_window(item.get("y_window_m"), str(item["id"])),
                )
                for item in template["bodies"]
            )
            series = bodies[0].series
        else:
            stations = [Station(float(item["s_m"]), profile(item["profile"], "rail_top"), item["id"])
                        for item in template["stations"]]
            series = ProfileSeries(stations, template.get("event_branches"))
            bodies = (RailBody(f"{template['id']}:main", series),)
        for axle in range(4):
            rails.append(VehicleRail(f"axle{axle + 1}_{template['id']}", template["id"], axle, template["wheel_id"],
                                     finite("mass_y_kg", template["mass_y_kg"], positive=True),
                                     finite("mass_z_kg", template["mass_z_kg"], positive=True),
                                     support(template["support"]), series, bodies))
    # Track irregularity is a mileage-dependent offset of the running surface, so it is applied
    # where the surface is sampled (see velch.irregularity.ShiftedSeries) rather than baked into
    # the station profiles: the stations are metres apart and the samples are 0.25 m apart.
    irregularity_record = None
    irregularity_spec = raw.get("irregularity")
    if irregularity_spec:
        from .irregularity import describe_application, read_tre, scaled_track, shift_rails

        tre_asset = resolve_asset(irregularity_spec["tre"], case_path=target,
                                  kind="irregularity record")
        tre_path = tre_asset.path
        assets[str(tre_path)] = tre_asset.sha256
        raw_track = read_tre(tre_path)
        channels = tuple(irregularity_spec.get("channels") or
                         ("lateral", "vertical", "roll", "gauge"))
        start_m = float(irregularity_spec.get("start_m", raw_track.span_m[0]))
        end_m = float(irregularity_spec.get("end_m", raw_track.span_m[1]))
        fade_m = float(irregularity_spec.get("fade_m", 0.0))
        scale = float(irregularity_spec.get("scale", 1.0))
        windowed = scaled_track(raw_track, scale=scale, channels=channels,
                                start_m=start_m, end_m=end_m, fade_m=fade_m)
        half_gauge_m = abs(wheels[0].lateral_offset_m)
        rails = shift_rails(rails, windowed, half_gauge_m=half_gauge_m)
        irregularity_record = describe_application(
            raw_track, start_m=start_m, end_m=end_m, fade_m=fade_m, scale=scale, channels=channels)
        irregularity_record["sha256"] = assets[str(tre_path)]
        reach = _irregularity_reach(vehicle, raw.get("run", {}), windowed)
        irregularity_record["reach"] = reach
        if not reach["overlaps"]:
            warnings.warn(
                f"irregularity {Path(tre_path).name} is applied but no axle passes over it: "
                f"axle spans {reach['axles_m']} m, excited band {reach.get('band_m')} m. "
                f"This run is identical to one with no irregularity.",
                RuntimeWarning, stacklevel=2)
    # Cant turns the whole track plane, so the rail surfaces are rotated and not merely raised.
    # The angle comes from the cant and the gauge the vehicle declares; on the geometry route the
    # level difference is published by ``_curve_placement`` and the rotation here, and the force
    # route keeps using the equivalent-straight lateral force plus its gravity component.
    run_block = raw.get("run", {})
    cant_m = float(run_block.get("curve_cant_m") or 0.0)
    if cant_m != 0.0 and bool(run_block.get("curve_geometry", False)):
        gauge_m = 2.0 * abs(float(wheels[0].lateral_offset_m))
        if gauge_m <= 0.0:
            raise ValueError("curve_cant_m needs a vehicle with a non-zero lateral wheel offset")
        import math as _math
        from .irregularity import roll_rails
        angle = _math.asin(max(-1.0, min(1.0, cant_m / gauge_m)))
        rails = roll_rails(rails, angle)
    radius = run_block.get("curve_radius_m")
    # OFF BY DEFAULT, because it is measurably wrong today.  Shifting the sampled rail surface by
    # s^2/(2R) while the vehicle keeps its own lateral frame gives 78 786 kN on the left rail with
    # the car straight, and 150 690 kN once the car is shifted by the same 45.5 mm -- two equal
    # shifts in one frame would cancel, so profile.y_m and the vehicle position are not in the same
    # frame (docs/CURVE_SEAT_AND_CREEP_2026-10-27.md §23).  A turnout does not need this path at all:
    # its station table is already curved, and `align_to_track` places the vehicle on it.
    # ``curve_geometry`` moves the track through TrackKernel's own placement hook: ``local_state``
    # returns ``rail_y_m = s^2/(2R)`` for every rail, and the profile keeps carrying the rail's side
    # offset (+/- 0.753).  Round 25 measured that adding a second shift on the sampled surface
    # double-counts it: crown = rail_y_m + (profile.y_m + 45.455 mm) read -0.669296 m where the
    # straight crown is -0.753337, and the wheel sat 32-79 mm beside it.  With the surface untouched
    # and only the vehicle aligned, wheel minus crown is the straight case's 6.8 mm.  So the rail
    # side lives in exactly one place: the kernel.
    track_spec = raw.get("track_dynamics", {"kind": "local_compliant"})
    track_kind = track_spec["kind"]
    if track_kind not in {"rigid", "local_compliant", "two_layer", "layered", "modal"}:
        raise ValueError("track_dynamics.kind must be rigid, local_compliant, two_layer, layered or modal")
    layers = tuple(TrackLayer(**layer) for layer in track_spec.get("layers", []))
    modal_track = None
    if track_kind == "modal":
        modal_asset = resolve_asset(track_spec["modal_file"], case_path=target,
                                    kind="modal track file")
        modal_path = modal_asset.path
        modal_track = load_modal_track(modal_path, [template["id"] for template in raw["rail_templates"]])
        assets[str(modal_path)] = modal_asset.sha256
    # The vehicle block size comes from the topology: the legacy 5-DOF layout gives the
    # frozen 35, a node table gives whatever its bodies declare.
    # A case may carry its own topology; otherwise it inherits the one its vehicle reference
    # declares, so "which bodies does this car have" lives with the car and not with each case.
    topology_block = raw.get("topology") or (
        None if "vehicle_ref" not in raw else (model.topology or None))
    topology = topology_of(topology_block, vehicle)
    # A flexible wheelset adds modal coordinates *after* the track block; a rigid one adds none,
    # which is why every existing case keeps its exact state size and results.
    wheel_modes = _load_wheel_modes(raw.get("flexible_wheelset"), vehicle, target, assets)
    modal_size = _modal_size(wheel_modes)
    tracks = _track_size(track_kind, rails, layers, modal_track)
    n = topology.body_dimension + tracks + modal_size
    state = raw.get("initial_state", {})
    # A balanced starting state is worth keeping: the compliant-track static solve cannot start from
    # zeros (stiff rail rows make every seed look like "no progress").  A 35-coordinate state written
    # for the legacy layout still describes the same car, so carry it over body by body.
    supplied = state.get("q")
    if supplied is not None and len(supplied) != n:
        legacy = legacy_topology(vehicle)
        track_extra = len(supplied) - legacy.body_dimension
        if track_extra == tracks:
            supplied = migrate_initial_state(supplied, legacy, topology,
                                             tracks=tracks, modal_size=modal_size)
        else:
            raise ValueError(f"initial_state.q has {len(supplied)} values; the layout needs {n} "
                             f"({topology.body_dimension} body + {tracks} track "
                             f"+ {modal_size} modal) and the legacy "
                             f"layout takes {legacy.body_dimension} + {track_extra} track")
    q = tuple(float(x) for x in (supplied or [0.0] * n))
    default_v = [0.0] * n
    for axle in range(4):
        default_v[topology.require(f"wheelset{axle + 1}", "spin")] = (
            vehicle.travel_speed_m_s / vehicle.nominal_wheel_radius_m)
    velocity = tuple(float(x) for x in state.get("v", default_v))
    support_spec = raw.get("support_compliance")
    compliance = SupportCompliance(**support_spec) if support_spec else None
    polygon = None
    if raw.get("wheel_polygon") is not None:
        spec = raw["wheel_polygon"]
        if not isinstance(spec, dict):
            raise ValueError("'wheel_polygon' must be an object with order and depth_m")
        polygon = WheelPolygon(int(spec["order"]), float(spec["depth_m"]),
                               float(spec.get("phase_rad", 0.0)))
    return VehicleCase(raw["case_id"], raw["purpose"], raw["parameter_source"], vehicle,
                       wheels, tuple(rails), track_kind, modal_track, ContactParameters(**raw["contact"]),
                       RunSettings(**raw["run"]), q, velocity,
                       bool(raw.get("equilibrate_vertical", False)), target,
                       hashlib.sha256(raw_bytes).hexdigest(), assets, compliance,
                       layers, load_path(raw.get("path")),
                       dict(topology_block) if topology_block else None,
                       irregularity=irregularity_record, wheel_modes=wheel_modes,
                       wheel_polygon=polygon, speed_schedule=speed_schedule)
