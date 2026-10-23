"""Version-2 vehicle contract: four wheelsets, two bogies, one carbody.

The 35 generalized vehicle coordinates follow the hierarchy observed in the
user's SDITT MATLAB matrix builder. Connector equations are an independent,
energy-consistent small-rotation implementation, not decompiled Simpack code.
"""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .contact import ContactParameters
from .model import LinearSupport, RunSettings, TrackLayer, Wheel
from .paths import PathTrack, load_path
from .topology import topology_of
from .profiles import ProfileSeries, Station, load_profile
from .support_compliance import SupportCompliance
from .track_models import ModalTrack, load_modal_track


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
        # depends on the track kind.  With the legacy layout this is the historical 35.
        n = topology_of(self.topology, self.vehicle).body_dimension + (
            2 * len(self.rails) if self.track_kind == "local_compliant"
            else 4 * len(self.rails) if self.track_kind == "two_layer"
            else 2 * (1 + len(self.track_layers)) * len(self.rails)
            if self.track_kind == "layered"
            else self.modal_track.mode_count if self.modal_track else 0)
        if len(self.initial_q) != n or len(self.initial_v) != n:
            raise ValueError(f"initial q/v must each have {n} coordinates")
        if any(not math.isfinite(x) for x in (*self.initial_q, *self.initial_v)):
            raise ValueError("initial state must be finite")


def load_vehicle_case(path: str | Path) -> VehicleCase:
    target = Path(path).resolve(strict=True)
    raw_bytes = target.read_bytes()
    raw = json.loads(raw_bytes.decode("utf-8"))
    if raw.get("schema_version") != "velch-vehicle-v2":
        raise ValueError("unsupported vehicle case schema")
    base = target.parent
    assets: dict[str, str] = {}

    def profile(spec: dict[str, Any], surface: str):
        source = (base / spec["file"]).resolve(strict=True)
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
    vehicle = VehicleParameters(
        RigidBody(**v["carbody"]), RigidBody(**v["bogie"]), WheelsetBody(**v["wheelset"]),
        SuspensionStage(**v["primary"]), SuspensionStage(**v["secondary"]),
        **{key: v[key] for key in ("bogie_half_spacing_m", "wheelbase_m", "wheel_center_height_m",
                                "nominal_wheel_radius_m", "travel_speed_m_s", "gravity_m_s2",
                                "drive_torque_per_wheelset_nm")},
    )
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
    track_spec = raw.get("track_dynamics", {"kind": "local_compliant"})
    track_kind = track_spec["kind"]
    if track_kind not in {"rigid", "local_compliant", "two_layer", "layered", "modal"}:
        raise ValueError("track_dynamics.kind must be rigid, local_compliant, two_layer, layered or modal")
    layers = tuple(TrackLayer(**layer) for layer in track_spec.get("layers", []))
    modal_track = None
    if track_kind == "modal":
        modal_path = (base / track_spec["modal_file"]).resolve(strict=True)
        modal_track = load_modal_track(modal_path, [template["id"] for template in raw["rail_templates"]])
        assets[str(modal_path)] = hashlib.sha256(modal_path.read_bytes()).hexdigest()
    # The vehicle block size comes from the topology: the legacy 5-DOF layout gives the
    # frozen 35, a node table gives whatever its bodies declare.
    # A case may carry its own topology; otherwise it inherits the one its vehicle reference
    # declares, so "which bodies does this car have" lives with the car and not with each case.
    topology_block = raw.get("topology") or (
        None if "vehicle_ref" not in raw else (model.topology or None))
    topology = topology_of(topology_block, vehicle)
    n = topology.body_dimension + (2 * len(rails) if track_kind == "local_compliant"
              else 4 * len(rails) if track_kind == "two_layer"
              else 2 * (1 + len(layers)) * len(rails) if track_kind == "layered"
              else modal_track.mode_count if modal_track else 0)
    state = raw.get("initial_state", {})
    q = tuple(float(x) for x in state.get("q", [0.0] * n))
    default_v = [0.0] * n
    for axle in range(4):
        default_v[topology.require(f"wheelset{axle + 1}", "spin")] = (
            vehicle.travel_speed_m_s / vehicle.nominal_wheel_radius_m)
    velocity = tuple(float(x) for x in state.get("v", default_v))
    support_spec = raw.get("support_compliance")
    compliance = SupportCompliance(**support_spec) if support_spec else None
    return VehicleCase(raw["case_id"], raw["purpose"], raw["parameter_source"], vehicle,
                       wheels, tuple(rails), track_kind, modal_track, ContactParameters(**raw["contact"]),
                       RunSettings(**raw["run"]), q, velocity,
                       bool(raw.get("equilibrate_vertical", False)), target,
                       hashlib.sha256(raw_bytes).hexdigest(), assets, compliance,
                       layers, load_path(raw.get("path")),
                       dict(topology_block) if topology_block else None)
