"""Parameter registry: the single source of truth for what a Chinese UI may edit.

The UI must never grow a hand-written control per number: every editable quantity is declared once
here with its Chinese label, unit, group and physical range, and the panels are generated from this
table.  That gives three properties the project needs as it grows a vehicle library and a turnout
library:

* one place decides the Chinese wording, so two screens cannot name the same quantity differently;
* the range check lives with the declaration, so a slider and the JSON validator cannot disagree;
* an AI assistant can be handed this table as its tool schema instead of guessing field names.

``apply_patch`` is the only writer: it copies, coerces, range-checks and raises.  Nothing here knows
about the solver -- it is pure data and validation.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Iterable, Mapping, MutableMapping

__all__ = [
    "ParameterError",
    "ParameterSpec",
    "REGISTRY",
    "apply_patch",
    "coverage",
    "editable",
    "registry_by_path",
    "to_chinese",
]


class ParameterError(ValueError):
    """Raised for an unknown, non-numeric or out-of-range parameter edit."""


@dataclass(frozen=True)
class ParameterSpec:
    path: str
    label_zh: str
    unit: str
    group: str
    note: str = ""
    minimum: float | None = None
    maximum: float | None = None
    step: float | None = None

    def __post_init__(self) -> None:
        if not self.path or "." not in self.path:
            raise ParameterError(f"parameter path must be dotted, got {self.path!r}")
        if not self.label_zh:
            raise ParameterError(f"{self.path}: label_zh is required")
        if self.minimum is not None and self.maximum is not None and self.minimum > self.maximum:
            raise ParameterError(f"{self.path}: minimum exceeds maximum")


VEHICLE = "车辆"
SUSPENSION = "悬挂"
CONTACT = "轮轨接触"
RUN = "求解设置"
TRACK = "轨道"

#: Case sections the UI is allowed to edit.  Everything else is provenance or geometry records.
EDITABLE_SECTIONS: tuple[str, ...] = (
    "vehicle",
    "contact",
    "run",
    "track_dynamics",
    "rail_templates",
    "support_compliance",
)

#: Geometry tables inside editable sections that are data, not knobs (thousands of numbers each).
IGNORED_LEAF_PREFIXES: tuple[str, ...] = (
    "rail_templates[].stations",
    "rail_templates[].bodies[].stations",
    "rail_templates[].bodies[].id",
    "contact.wheel_profile",
    "contact.rail_profile",
)

REGISTRY: tuple[ParameterSpec, ...] = (
    # ---- 车辆: masses and inertias -------------------------------------------------------------
    ParameterSpec("vehicle.carbody.mass_kg", "车体质量", "kg", VEHICLE, minimum=1.0, maximum=2.0e5),
    ParameterSpec("vehicle.carbody.roll_inertia_kg_m2", "车体侧滚惯量", "kg·m²", VEHICLE, minimum=1.0),
    ParameterSpec("vehicle.carbody.pitch_inertia_kg_m2", "车体点头惯量", "kg·m²", VEHICLE, minimum=1.0),
    ParameterSpec("vehicle.carbody.yaw_inertia_kg_m2", "车体摇头惯量", "kg·m²", VEHICLE, minimum=1.0),
    ParameterSpec("vehicle.bogie.mass_kg", "构架质量", "kg", VEHICLE, minimum=1.0, maximum=5.0e4),
    ParameterSpec("vehicle.bogie.roll_inertia_kg_m2", "构架侧滚惯量", "kg·m²", VEHICLE, minimum=1.0),
    ParameterSpec("vehicle.bogie.pitch_inertia_kg_m2", "构架点头惯量", "kg·m²", VEHICLE, minimum=1.0),
    ParameterSpec("vehicle.bogie.yaw_inertia_kg_m2", "构架摇头惯量", "kg·m²", VEHICLE, minimum=1.0),
    ParameterSpec("vehicle.wheelset.mass_kg", "轮对质量", "kg", VEHICLE, minimum=1.0, maximum=1.0e4),
    ParameterSpec("vehicle.wheelset.roll_inertia_kg_m2", "轮对侧滚惯量", "kg·m²", VEHICLE, minimum=1.0),
    ParameterSpec("vehicle.wheelset.spin_inertia_kg_m2", "轮对自旋惯量", "kg·m²", VEHICLE, minimum=1.0),
    ParameterSpec("vehicle.wheelset.yaw_inertia_kg_m2", "轮对摇头惯量", "kg·m²", VEHICLE, minimum=1.0),
    # ---- 悬挂 ---------------------------------------------------------------------------------
    ParameterSpec("vehicle.primary.k_y_n_m", "一系横向刚度", "N/m", SUSPENSION, minimum=1.0),
    ParameterSpec("vehicle.primary.k_z_n_m", "一系垂向刚度", "N/m", SUSPENSION, minimum=1.0),
    ParameterSpec("vehicle.primary.c_y_n_s_m", "一系横向阻尼", "N·s/m", SUSPENSION, minimum=0.0),
    ParameterSpec("vehicle.primary.c_z_n_s_m", "一系垂向阻尼", "N·s/m", SUSPENSION, minimum=0.0),
    ParameterSpec("vehicle.secondary.k_y_n_m", "二系横向刚度", "N/m", SUSPENSION, minimum=1.0),
    ParameterSpec("vehicle.secondary.k_z_n_m", "二系垂向刚度", "N/m", SUSPENSION, minimum=1.0),
    ParameterSpec("vehicle.secondary.c_y_n_s_m", "二系横向阻尼", "N·s/m", SUSPENSION, minimum=0.0),
    ParameterSpec("vehicle.secondary.c_z_n_s_m", "二系垂向阻尼", "N·s/m", SUSPENSION, minimum=0.0),
    ParameterSpec("vehicle.secondary.k_yaw_nm_rad", "二系抗摇头刚度", "N·m/rad", SUSPENSION, minimum=0.0),
    ParameterSpec("vehicle.secondary.c_yaw_nm_s_rad", "二系抗摇头阻尼", "N·m·s/rad", SUSPENSION,
                  minimum=0.0),
    ParameterSpec("vehicle.primary.k_yaw_nm_rad", "一系抗摇头刚度", "N·m/rad", SUSPENSION, minimum=0.0),
    ParameterSpec("vehicle.primary.c_yaw_nm_s_rad", "一系抗摇头阻尼", "N·m·s/rad", SUSPENSION,
                  minimum=0.0),
    ParameterSpec("vehicle.primary.half_width_m", "一系弹簧横向半间距", "m", SUSPENSION,
                  minimum=0.0, maximum=1.5),
    ParameterSpec("vehicle.secondary.half_width_m", "二系弹簧横向半间距", "m", SUSPENSION,
                  minimum=0.0, maximum=2.0),
    ParameterSpec("vehicle.primary.upper_anchor_height_m", "一系上锚点高度", "m", SUSPENSION),
    ParameterSpec("vehicle.primary.lower_anchor_height_m", "一系下锚点高度", "m", SUSPENSION),
    ParameterSpec("vehicle.secondary.upper_anchor_height_m", "二系上锚点高度", "m", SUSPENSION),
    ParameterSpec("vehicle.secondary.lower_anchor_height_m", "二系下锚点高度", "m", SUSPENSION),
    # ---- 车辆几何与工况 -----------------------------------------------------------------------
    ParameterSpec("vehicle.wheelbase_m", "轴距", "m", VEHICLE, minimum=0.5, maximum=5.0),
    ParameterSpec("vehicle.bogie_half_spacing_m", "转向架半间距", "m", VEHICLE, minimum=1.0, maximum=20.0),
    ParameterSpec("vehicle.wheel_center_height_m", "轮心名义高度", "m", VEHICLE, minimum=0.2, maximum=1.2),
    ParameterSpec("vehicle.nominal_wheel_radius_m", "名义滚动圆半径", "m", VEHICLE,
                  minimum=0.2, maximum=1.2),
    ParameterSpec("vehicle.travel_speed_m_s", "行车速度", "m/s", VEHICLE,
                  minimum=0.1, maximum=200.0, step=0.5),
    ParameterSpec("vehicle.gravity_m_s2", "重力加速度", "m/s²", VEHICLE,
                  minimum=9.0, maximum=10.0),
    ParameterSpec("vehicle.drive_torque_per_wheelset_nm", "单轮对牵引力矩", "N·m", VEHICLE,
                  minimum=0.0),
    # ---- 轮轨接触 -----------------------------------------------------------------------------
    ParameterSpec("contact.effective_modulus_pa", "等效弹性模量", "Pa", CONTACT, minimum=1.0e9),
    ParameterSpec("contact.effective_radius_m", "固定等效曲率半径", "m", CONTACT,
                  note="仅 fixed_effective_radius 策略使用；local_circular 时由型面曲率导出",
                  minimum=1.0e-3, maximum=10.0),
    ParameterSpec("contact.normal_damping_n_s_m_1p5", "法向接触阻尼", "N·s/m^1.5", CONTACT,
                  minimum=0.0),
    ParameterSpec("contact.friction_coefficient", "轮轨摩擦系数", "-", CONTACT,
                  minimum=0.0, maximum=1.5, step=0.01),
    ParameterSpec("contact.creep_stiffness_x_n", "纵向蠕滑刚度", "N", CONTACT, minimum=1.0),
    ParameterSpec("contact.creep_stiffness_lateral_n", "横向蠕滑刚度", "N", CONTACT, minimum=1.0),
    ParameterSpec("contact.reference_speed_floor_m_s", "蠕滑参考速度下限", "m/s", CONTACT,
                  minimum=1.0e-4, maximum=10.0),
    ParameterSpec("contact.strip_dy_m", "条带积分片宽", "m", CONTACT, minimum=1.0e-5, maximum=0.01),
    ParameterSpec("contact.damping_force_cap_ratio", "阻尼力上限系数", "-", CONTACT,
                  note="留空表示不设上限；建议 0.5", minimum=0.0, maximum=10.0, step=0.05),
    ParameterSpec("contact.ellipticity_correction", "椭圆度修正", "-", CONTACT,
                  minimum=0.1, maximum=10.0),
    ParameterSpec("contact.wheel_rolling_radius_m", "轮滚动半径", "m", CONTACT,
                  minimum=0.1, maximum=1.0),
    ParameterSpec("contact.restitution_coefficient", "恢复系数", "-", CONTACT,
                  minimum=0.0, maximum=1.0, step=0.05),
    ParameterSpec("contact.damping_reference_speed_m_s", "阻尼参考速度", "m/s", CONTACT,
                  minimum=1.0e-3, maximum=10.0),
    # ---- 求解设置 -----------------------------------------------------------------------------
    ParameterSpec("run.x_start_m", "起始里程", "m", RUN, minimum=-1.0e4, maximum=1.0e5),
    ParameterSpec("run.duration_s", "仿真时长", "s", RUN, minimum=1.0e-4, maximum=60.0),
    ParameterSpec("run.output_step_s", "输出步长", "s", RUN, minimum=1.0e-6, maximum=0.1),
    ParameterSpec("run.max_solver_step_s", "最大积分步长", "s", RUN, minimum=1.0e-8, maximum=0.1),
    ParameterSpec("run.rtol", "相对容差", "-", RUN, minimum=1.0e-14, maximum=1.0e-2),
    ParameterSpec("run.atol", "绝对容差", "-", RUN, minimum=1.0e-16, maximum=1.0e-2),
    ParameterSpec("run.maximum_penetration_m", "侵入量上限（门）", "m", RUN, minimum=1.0e-6),
    ParameterSpec("run.maximum_abs_contact_slope", "接触面坡度上限（门）", "-", RUN, minimum=0.0),
    # ---- 轨道 ---------------------------------------------------------------------------------
    ParameterSpec("track_dynamics.layers[].k_z_n_m", "道床垂向刚度", "N/m", TRACK, minimum=1.0),
    ParameterSpec("track_dynamics.layers[].c_z_n_s_m", "道床垂向阻尼", "N·s/m", TRACK, minimum=0.0),
    ParameterSpec("track_dynamics.layers[].mass_z_kg", "层质量（垂向）", "kg", TRACK, minimum=0.0),
    ParameterSpec("rail_templates[].support.k_z_n_m", "扣件垂向刚度", "N/m", TRACK, minimum=1.0),
    ParameterSpec("rail_templates[].support.c_z_n_s_m", "扣件垂向阻尼", "N·s/m", TRACK, minimum=0.0),
    ParameterSpec("rail_templates[].support.k_y_n_m", "扣件横向刚度", "N/m", TRACK, minimum=1.0),
    ParameterSpec("rail_templates[].support.c_y_n_s_m", "扣件横向阻尼", "N·s/m", TRACK, minimum=0.0),
    ParameterSpec("rail_templates[].mass_y_kg", "钢轨分布质量（横向）", "kg", TRACK, minimum=0.0),
    ParameterSpec("rail_templates[].mass_z_kg", "钢轨分布质量（垂向）", "kg", TRACK, minimum=0.0),
    ParameterSpec("rail_templates[].bodies[].s_lo_m", "轨体起点里程", "m", TRACK),
    ParameterSpec("rail_templates[].bodies[].s_hi_m", "轨体终点里程", "m", TRACK),
    ParameterSpec("support_compliance.spacing_m", "轨枕间距", "m", TRACK,
                  minimum=0.3, maximum=1.5),
    ParameterSpec("support_compliance.pad_stiffness_n_m", "支撑刚度（静力柔度）", "N/m", TRACK,
                  minimum=1.0e6),
    ParameterSpec("support_compliance.rail_ei_n_m2", "钢轨抗弯刚度 EI", "N·m²", TRACK,
                  minimum=1.0e4),
)


def registry_by_path() -> dict[str, ParameterSpec]:
    table: dict[str, ParameterSpec] = {}
    for spec in REGISTRY:
        if spec.path in table:
            raise ParameterError(f"duplicate parameter path {spec.path!r}")
        table[spec.path] = spec
    return table


def _split(path: str) -> list[str]:
    """Split a dotted / indexed path into tokens, keeping ``[]`` segments as wildcards."""
    return [token for token in path.replace("].", "].|").replace(".", "|").split("|") if token]


def _walk(mapping: Any, tokens: Iterable[str]) -> list[Any]:
    """Resolve a path against a nested mapping; ``[]`` collects every list element."""
    current = [mapping]
    for token in tokens:
        nxt: list[Any] = []
        for node in current:
            if token.endswith("[]"):
                key = token[:-2]
                value = node.get(key) if isinstance(node, Mapping) else None
                if isinstance(value, list):
                    nxt.extend(value)
            elif isinstance(node, Mapping) and token in node:
                nxt.append(node[token])
        current = nxt
        if not current:
            return []
    return current


def editable(case: Mapping[str, Any]) -> list[tuple[ParameterSpec, Any]]:
    """Every registry parameter that actually resolves in this case, with its current value."""
    found: list[tuple[ParameterSpec, Any]] = []
    for spec in REGISTRY:
        values = _walk(case, _split(spec.path))
        numeric = [value for value in values if isinstance(value, (int, float))]
        if numeric:
            found.append((spec, numeric if len(numeric) > 1 else numeric[0]))
    return found


def coverage(
    case: Mapping[str, Any], sections: Iterable[str] = EDITABLE_SECTIONS
) -> tuple[int, list[str]]:
    """How many numeric leaves of the editable sections the registry can name, and which it cannot.

    Provenance blocks (``source_evidence``, ``asset_hashes``, ``initial_state``, profile geometry)
    are deliberately excluded: they are records, not knobs, and counting them would make coverage
    look catastrophic while saying nothing about the editing surface.
    """
    leaves: list[str] = []

    def visit(node: Any, prefix: str) -> None:
        if any(prefix.startswith(ignored) for ignored in IGNORED_LEAF_PREFIXES):
            return
        if isinstance(node, Mapping):
            for key, value in node.items():
                visit(value, f"{prefix}.{key}" if prefix else str(key))
        elif isinstance(node, list):
            for value in node:
                visit(value, f"{prefix}[]")
        elif isinstance(node, (int, float)) and not isinstance(node, bool):
            leaves.append(prefix)

    scope = {name: case[name] for name in sections if name in case}
    visit(scope, "")
    table = registry_by_path()
    named = 0
    missing: list[str] = []
    for leaf in leaves:
        if leaf in table:
            named += 1
        else:
            missing.append(leaf)
    return named, missing


def apply_patch(case: Mapping[str, Any], patch: Mapping[str, float]) -> dict[str, Any]:
    """Return a validated deep copy of ``case`` with ``patch`` applied.

    ``patch`` maps registry paths to numbers.  Unknown paths, non-finite values and out-of-range
    values raise :class:`ParameterError` -- an AI assistant or a slider cannot write a value that
    the solver would reject later.
    """
    table = registry_by_path()
    clone = _deep_copy(case)
    for path, value in patch.items():
        if path not in table:
            raise ParameterError(f"unknown parameter {path!r}; not in the registry")
        spec = table[path]
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise ParameterError(f"{path}: value must be a number, got {type(value).__name__}")
        if not math.isfinite(float(value)):
            raise ParameterError(f"{path}: value must be finite")
        if spec.minimum is not None and value < spec.minimum:
            raise ParameterError(f"{path}: {value} < minimum {spec.minimum}")
        if spec.maximum is not None and value > spec.maximum:
            raise ParameterError(f"{path}: {value} > maximum {spec.maximum}")
        for node in _walk(clone, _split(path)):
            if isinstance(node, MutableMapping):
                raise ParameterError(f"{path}: cannot write through a container")
        _assign(clone, _split(path), float(value))
    return clone


def _deep_copy(node: Any) -> Any:
    if isinstance(node, Mapping):
        return {key: _deep_copy(value) for key, value in node.items()}
    if isinstance(node, list):
        return [_deep_copy(value) for value in node]
    return node


def _assign(root: Any, tokens: list[str], value: float) -> None:
    current = root
    for index, token in enumerate(tokens[:-1]):
        wildcard = token.endswith("[]")
        key = token[:-2] if wildcard else token
        node = current[key] if isinstance(current, MutableMapping) else current[int(key)]
        if wildcard:
            if not isinstance(node, list) or not node:
                raise ParameterError(f"{'.'.join(tokens)}: no list elements to patch")
            # patch every element: the registry demands uniform semantics
            for element in node:
                _assign(element, tokens[index + 1:], value)
            return
        current = node
    last = tokens[-1]
    if isinstance(current, MutableMapping):
        if last not in current:
            raise ParameterError(f"{'.'.join(tokens)}: not present in this case")
        current[last] = value
    else:
        raise ParameterError(f"{'.'.join(tokens)}: parent is not a mapping")


def to_chinese(path: str) -> str:
    """Chinese label for a registry path (falls back to the path itself)."""
    spec = registry_by_path().get(path)
    return spec.label_zh if spec else path
