"""车辆数据库：把"一台车"作为数据文件管理，算例可以只引用它。

这一层只做三件事：找到文件、校验内容、把其中的 ``vehicle`` 块交给 ``load_vehicle_case``。
它不解析型面、不碰求解器——型面路径仍然写在算例的 ``wheels``/``rail_templates`` 里，
因为那属于"轨道几何"，不属于"这台车"。

为什么单独一层：算例里重复抄一份车辆参数，就会出现"同一台车在十个 case 里十个样子"。
让算例写 ``"vehicle_ref": "CRH380A_M"``，则这台车只有一个定义，改一处、全部生效，
并且校验规则只需要守一处。
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .vehicle import VehicleParameters

MODEL_SCHEMA = "velch-vehicle-model-v1"
INDEX_SCHEMA = "velch-vehicle-index-v1"
INDEX_NAME = "index.json"

#: v2 剖面下每个刚体的自由度；节点表的顺序就是这个顺序。
V2_LAYOUT = {"wheelset": ["y", "z", "roll", "spin", "yaw"],
             "bogie": ["y", "z", "roll", "pitch", "yaw"],
             "carbody": ["y", "z", "roll", "pitch", "yaw"]}

#: 车辆文件里 ``vehicle`` 块必须有的标量键（与 VehicleParameters 一一对应）。
SCALARS = ("bogie_half_spacing_m", "wheelbase_m", "wheel_center_height_m",
           "nominal_wheel_radius_m", "travel_speed_m_s", "gravity_m_s2",
           "drive_torque_per_wheelset_nm")

#: 悬挂阶段必须有的键（v2 剖面：只有 y / z / yaw）。
STAGE_KEYS = ("k_y_n_m", "c_y_n_s_m", "k_z_n_m", "c_z_n_s_m", "k_yaw_nm_rad",
              "c_yaw_nm_s_rad", "half_width_m", "upper_anchor_height_m", "lower_anchor_height_m")


class VehicleModelError(ValueError):
    """车辆文件不合法。消息要说清是哪一条、错在哪、怎么改。"""


@dataclass(frozen=True)
class VehicleModel:
    path: Path
    raw: dict[str, Any]

    @property
    def id(self) -> str:
        return str(self.raw.get("id") or "")

    @property
    def name(self) -> str:
        return str(self.raw.get("name") or self.id)

    @property
    def topology(self) -> dict | None:
        """Node table carried by this vehicle, if it has one."""

        block = self.raw.get("topology")
        return dict(block) if isinstance(block, dict) else None

    @property
    def block(self) -> dict[str, Any]:
        """交给 ``VehicleParameters`` 的那一块（逐字，不换算、不补默认值）。"""
        return dict(self.raw["vehicle"])

    @property
    def status(self) -> str:
        return str(self.raw.get("physics_validation_status") or "unknown")

    @property
    def axle_count(self) -> int:
        layout = self.raw.get("layout") or {}
        count = int(layout.get("bogies", 0)) * int(layout.get("axles_per_bogie", 0))
        if count:
            return count
        # A node table lists its axles as bodies, so the layout product is zero for it.
        return _axle_count(self.raw)

    def summary(self) -> dict[str, Any]:
        block = self.block
        body = block.get("carbody", {})
        bogie = block.get("bogie", {})
        wheelset = block.get("wheelset", {})
        return {
            "id": self.id,
            "name": self.name,
            "kind": self.raw.get("kind", ""),
            "axle_count": self.axle_count,
            "state_dimension": (self.raw.get("layout") or {}).get("state_dimension"),
            "mass_total_kg": round(float(body.get("mass_kg", 0.0))
                                    + float(bogie.get("mass_kg", 0.0))
                                    * (int((self.raw.get("layout") or {}).get("bogies", 0))
                                       or max(1, self.axle_count // 2))
                                    + float(wheelset.get("mass_kg", 0.0)) * self.axle_count,
                                    1),
            "travel_speed_m_s": block.get("travel_speed_m_s"),
            "status": self.status,
            "file": self.path.name,
        }


def _root() -> Path:
    """车辆库位置：``VELCH_VEHICLE_DIR`` → 仓库 ``vehicles/`` → 安装目录 ``vehicles/``。

    In a PyInstaller 6 onedir bundle the ``datas`` entries land inside ``_internal``, not
    next to the executable, so the install folder has to be asked twice.  Checking only
    ``<install>/vehicles`` made a packaged build report an empty library -- which reads as
    "the models are gone" rather than "they were packed one directory deeper".  The docs
    payload hit exactly this and ``velch.selfcheck.docs_roots()`` already tries both.
    """
    override = os.environ.get("VELCH_VEHICLE_DIR")
    if override:
        return Path(override).expanduser().resolve()
    # A wheel installs the library inside the package (``velch/_internal/vehicles``, filled by setup.py's
    # build_py).  Ask there first: in a source checkout that directory does not exist, so the repository
    # lookup below is unchanged, and in an installed copy the walk-up cannot find anything.
    packaged = Path(__file__).resolve().parent / "_internal" / "vehicles"
    if packaged.is_dir():
        return packaged
    from .data_root import repository_root  # 局部导入：避免 vehicle_db 成为 data_root 的依赖

    candidate = repository_root() / "vehicles"
    if candidate.is_dir():
        return candidate
    try:
        from .data_root import frozen_install_root, is_frozen

        if is_frozen():
            install = frozen_install_root()
            for frozen in (install / "vehicles", install / "_internal" / "vehicles"):
                if frozen.is_dir():
                    return frozen
    except Exception:  # pragma: no cover - 只在异常环境下走
        pass
    return candidate


def vehicle_dir() -> Path:
    return _root()


def list_models(*, root: Path | None = None) -> list[VehicleModel]:
    """目录里所有 ``*.json``（除 ``index.json``），按 id 排序；坏文件跳过并在返回值里不含它。"""
    folder = Path(root) if root is not None else _root()
    if not folder.is_dir():
        return []
    models: list[VehicleModel] = []
    for path in sorted(folder.glob("*.json")):
        if path.name == INDEX_NAME:
            continue
        try:
            models.append(load(path))
        except (VehicleModelError, json.JSONDecodeError, OSError):
            continue
    return sorted(models, key=lambda model: model.id)


def load(source: str | Path, *, root: Path | None = None) -> VehicleModel:
    """按 id 或路径加载并校验。``source`` 是裸 id 时在车辆库里找 ``<id>.json``。"""
    text = str(source)
    candidate = Path(text)
    if candidate.suffix.lower() == ".json" or candidate.is_absolute():
        path = candidate if candidate.is_absolute() else Path.cwd() / candidate
    else:
        folder = Path(root) if root is not None else _root()
        path = folder / f"{text}.json"
    if not path.is_file():
        raise VehicleModelError(f"vehicle model not found: {path}")
    raw = json.loads(path.read_text(encoding="utf-8"))
    model = VehicleModel(path=path, raw=raw)
    problems = validate(model)
    if problems:
        raise VehicleModelError("; ".join(problems))
    return model


def validate(model: VehicleModel) -> list[str]:
    """返回问题清单（空 = 合法）。逐条说清哪里错，便于按提示修文件。"""
    problems: list[str] = []
    raw = model.raw

    if raw.get("schema_version") != MODEL_SCHEMA:
        problems.append(f"schema_version must be {MODEL_SCHEMA!r}, got {raw.get('schema_version')!r}")
    if not model.id:
        problems.append("id is required")
    block = raw.get("vehicle")
    if not isinstance(block, dict):
        return problems + ["vehicle block is required"]

    for group, keys in (("carbody", ("mass_kg", "roll_inertia_kg_m2", "pitch_inertia_kg_m2",
                                     "yaw_inertia_kg_m2")),
                        ("bogie", ("mass_kg", "roll_inertia_kg_m2", "pitch_inertia_kg_m2",
                                   "yaw_inertia_kg_m2")),
                        ("wheelset", ("mass_kg", "roll_inertia_kg_m2", "spin_inertia_kg_m2",
                                      "yaw_inertia_kg_m2"))):
        spec = block.get(group)
        if not isinstance(spec, dict):
            problems.append(f"vehicle.{group} is required")
            continue
        for key in keys:
            value = spec.get(key)
            if not isinstance(value, (int, float)) or value <= 0:
                problems.append(f"vehicle.{group}.{key} must be a positive number, got {value!r}")

    for stage in ("primary", "secondary"):
        spec = block.get(stage)
        if not isinstance(spec, dict):
            problems.append(f"vehicle.{stage} is required")
            continue
        missing = [key for key in STAGE_KEYS if key not in spec]
        if missing:
            problems.append(f"vehicle.{stage} missing {missing}")
            continue
        for key in STAGE_KEYS:
            value = spec[key]
            if not isinstance(value, (int, float)):
                problems.append(f"vehicle.{stage}.{key} must be a number, got {value!r}")
            elif key.startswith(("k_", "c_")) and value < 0:
                problems.append(f"vehicle.{stage}.{key} must not be negative, got {value!r}")
        if float(spec["half_width_m"]) <= 0:
            problems.append(f"vehicle.{stage}.half_width_m must be positive")

    for key in SCALARS:
        value = block.get(key)
        if not isinstance(value, (int, float)):
            problems.append(f"vehicle.{key} must be a number, got {value!r}")
    for key in ("wheelbase_m", "wheel_center_height_m", "nominal_wheel_radius_m",
                "travel_speed_m_s", "gravity_m_s2"):
        value = block.get(key)
        if isinstance(value, (int, float)) and value <= 0:
            problems.append(f"vehicle.{key} must be positive, got {value!r}")

    layout = raw.get("layout") or {}
    model = layout.get("model")
    if model not in {"v2-5dof", "v2-node"}:
        problems.append("layout.model must be 'v2-5dof' or 'v2-node'")
    elif model == "v2-5dof":
        if layout.get("bogies") != 2 or layout.get("axles_per_bogie") != 2:
            problems.append("layout must be 2 bogies x 2 axles (the v2 builder hard-codes it)")
        if layout.get("state_dimension") != 35:
            problems.append("layout.state_dimension must be 35 for v2-5dof")
        if raw.get("topology"):
            problems.append("a v2-5dof model must not also carry a topology block")
    else:
        # v2-node: the state size and every element have to be checkable, so build the
        # topology here instead of trusting two places to agree.
        if not raw.get("topology"):
            problems.append("a v2-node model needs a 'topology' block with bodies and elements")
        else:
            try:
                from .topology import topology_of  # local: keeps the import graph a leaf
                topology = topology_of(raw["topology"], VehicleParameters(**block))
            except Exception as error:  # noqa: BLE001 - report, never crash the listing
                problems.append(f"topology is invalid: {error}")
            else:
                declared = layout.get("state_dimension")
                if declared != topology.body_dimension:
                    problems.append(
                        f"layout.state_dimension {declared!r} does not match the topology "
                        f"({topology.body_dimension} coordinates over {len(topology.bodies)} bodies)")
                for kind in ("wheelset", "bogie", "carbody"):
                    if not topology.of_kind(kind):
                        problems.append(f"topology has no body of kind {kind!r}")
                if len(topology.wheelsets()) != 4:
                    problems.append("topology must define four wheelsets")
                if len(topology.bogies()) != 2:
                    problems.append("topology must define two bogies")

    wheels = raw.get("wheels")
    if not isinstance(wheels, list) or len(wheels) != 2:
        problems.append("wheels must list the two wheels (L and R)")
    else:
        offsets = [float(item.get("lateral_offset_m", 0.0)) for item in wheels]
        if not (offsets[0] < 0 < offsets[1]):
            problems.append(f"wheels must sit either side of the centre line, got {offsets}")
        if abs(abs(offsets[0]) - abs(offsets[1])) > 1e-9:
            problems.append(f"wheels must be symmetric about the centre line, got {offsets}")

    status = raw.get("physics_validation_status")
    if not status:
        problems.append("physics_validation_status is required (say 'unvalidated...' if it is)")
    provenance = raw.get("provenance")
    if not isinstance(provenance, dict) or not provenance:
        problems.append("provenance is required: every physics number must name where it came from")

    problems.extend(_geometry_problems(raw))
    return problems


def _geometry_problems(raw: dict[str, Any]) -> list[str]:
    """The recorded geometry must agree with the numbers the solver actually uses.

    Every check below is an *identity* that follows from the frame convention: if the carbody CG is
    at -1.55 m and the air spring's upper surface at -1.0 m, then the solver's relative anchor has
    to be 0.55 m.  A geometry block that disagrees with ``vehicle`` would be worse than none at all,
    because it would look authoritative while describing a different car.
    """
    problems: list[str] = []
    geometry = raw.get("geometry")
    if geometry is None:
        return problems
    if not isinstance(geometry, dict):
        return ["geometry must be an object"]
    frame = geometry.get("frame")
    if not isinstance(frame, dict) or not all(frame.get(axis) for axis in ("x", "y", "z")):
        problems.append("geometry.frame must describe the x/y/z convention")

    block = raw.get("vehicle") or {}
    carbody = geometry.get("carbody") or {}
    used = block.get("carbody") or {}
    for recorded, mined in (("mass_kg", "mass_kg"), ("roll_inertia_kg_m2", "roll_inertia_kg_m2"),
                            ("pitch_inertia_kg_m2", "pitch_inertia_kg_m2"),
                            ("yaw_inertia_kg_m2", "yaw_inertia_kg_m2")):
        value = carbody.get(mined)
        if not isinstance(value, (int, float)):
            problems.append(f"geometry.carbody.{mined} must be a number, got {value!r}")
        elif not isinstance(used.get(recorded), (int, float)):
            continue
        elif abs(float(value) - float(used[recorded])) > 1e-6 * max(1.0, abs(float(used[recorded]))):
            problems.append(f"geometry.carbody.{mined}={value} disagrees with "
                            f"vehicle.carbody.{recorded}={used[recorded]}")
    cg = (carbody.get("cg_m") or {})
    if isinstance(cg.get("z"), (int, float)) and float(cg["z"]) >= 0:
        problems.append(f"geometry.carbody.cg_m.z must be below the rail top, got {cg['z']}")
    if not isinstance(carbody.get("reference_x_m"), (int, float)):
        problems.append("geometry.carbody.reference_x_m must be a number")

    bogies = geometry.get("bogies") or {}
    distance = bogies.get("distance_m")
    spacing = block.get("bogie_half_spacing_m")
    if isinstance(distance, (int, float)) and isinstance(spacing, (int, float)):
        if abs(float(distance) - 2.0 * float(spacing)) > 1e-6:
            problems.append(f"geometry.bogies.distance_m={distance} must be twice "
                            f"vehicle.bogie_half_spacing_m={spacing}")
    for key, mine in (("wheelbase_m", "wheelbase_m"),):
        if isinstance(bogies.get(mine), (int, float)) and isinstance(block.get(key), (int, float)):
            if abs(float(bogies[mine]) - float(block[key])) > 1e-6:
                problems.append(f"geometry.bogies.{mine}={bogies[mine]} disagrees with "
                                f"vehicle.{key}={block[key]}")

    secondary = geometry.get("secondary") or {}
    used_secondary = block.get("secondary") or {}
    half = secondary.get("half_width_m")
    if isinstance(half, (int, float)) and isinstance(used_secondary.get("half_width_m"), (int, float)):
        if abs(float(half) - float(used_secondary["half_width_m"])) > 1e-6:
            problems.append(f"geometry.secondary.half_width_m={half} disagrees with "
                            f"vehicle.secondary.half_width_m={used_secondary['half_width_m']}")
    cg_z = cg.get("z")
    for recorded, mined in (("upper_anchor_height_m", "air_spring_upper_z_m"),
                            ("lower_anchor_height_m", "air_spring_lower_z_m")):
        value = secondary.get(mined)
        expected = used_secondary.get(recorded)
        if not isinstance(value, (int, float)) or not isinstance(expected, (int, float)):
            continue
        reference = float(cg_z) if recorded.startswith("upper") else float(bogies.get("cg_z_m", 0.0))
        implied = float(value) - reference
        if abs(implied - float(expected)) > 1e-3:
            problems.append(f"geometry.secondary.{mined}={value} implies {implied:.4f} m against "
                            f"vehicle.secondary.{recorded}={expected}")

    primary = geometry.get("primary") or {}
    used_primary = block.get("primary") or {}
    for recorded, mined in (("upper_anchor_height_m", "damper_lower_z_m"),
                            ("lower_anchor_height_m", "spring_lower_z_m")):
        value = primary.get(mined)
        expected = used_primary.get(recorded)
        if not isinstance(value, (int, float)) or not isinstance(expected, (int, float)):
            continue
        if abs(float(value) - float(expected)) > 2e-3:
            problems.append(f"geometry.primary.{mined}={value} disagrees with "
                            f"vehicle.primary.{recorded}={expected}")
    return problems

def index(*, root: Path | None = None) -> dict[str, Any]:
    """``index.json`` 的内容；文件缺失时按目录现算，避免索引与文件脱节。"""
    folder = Path(root) if root is not None else _root()
    path = folder / INDEX_NAME
    if path.is_file():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            data = None
        if isinstance(data, dict) and data.get("schema_version") == INDEX_SCHEMA:
            return data
    return {"schema_version": INDEX_SCHEMA,
            "models": [model.summary() for model in list_models(root=folder)]}


def _axle_count(raw) -> int:
    """Count wheelsets.

    A node table states them as bodies, which is authoritative. The older model keeps a ``wheels``
    list holding the left/right *profile* definitions shared by every axle, so counting that list
    would report one axle for a four-axle vehicle.
    """

    topology = raw.get("topology") or {}
    bodies = topology.get("bodies") or ()
    from_bodies = sum(1 for body in bodies
                      if isinstance(body, dict) and str(body.get("kind")) == "wheelset")
    if from_bodies:
        return from_bodies
    wheels = raw.get("wheels") or ()
    return len(wheels) // 2 if len(wheels) % 2 == 0 else len(wheels)


def main_report(models: list[VehicleModel]) -> str:
    lines = [f"车辆库：{_root()}", ""]
    if not models:
        lines.append("（空）")
        return "\n".join(lines)
    for model in models:
        summary = model.summary()
        lines.append(f"{summary['id']:<14} {summary['name']}")
        lines.append(f"  {summary['axle_count']} 轴 · {summary['state_dimension']} 自由度 · "
                     f"总质量 {summary['mass_total_kg']} kg · "
                     f"{float(summary['travel_speed_m_s'] or 0) * 3.6:.1f} km/h")
        geometry = (model.raw.get("geometry") or {})
        carbody = geometry.get("carbody") or {}
        if carbody:
            cg = carbody.get("cg_m") or {}
            lines.append(f"  车体几何：质量 {carbody.get('mass_kg')} kg · "
                         f"Ixx/Iyy/Izz {carbody.get('roll_inertia_kg_m2')}/"
                         f"{carbody.get('pitch_inertia_kg_m2')}/"
                         f"{carbody.get('yaw_inertia_kg_m2')} kg·m² · "
                         f"质心 z {cg.get('z')} m")
            bogies = geometry.get("bogies") or {}
            lines.append(f"  车体位置：参考点 x {carbody.get('reference_x_m')} m · "
                         f"定距 {bogies.get('distance_m')} m（前 {bogies.get('front_x_m')} / "
                         f"后 {bogies.get('rear_x_m')}）· 轴距 {bogies.get('wheelbase_m')} m")
        from .elements import describe_inventory, inventory

        counts = inventory(model.raw)
        if counts:
            lines.append(f"  元件：{describe_inventory(counts)}")
        lines.append(f"  验证状态：{summary['status']}")
        lines.append(f"  文件：{summary['file']}")
    return "\n".join(lines)
