"""力学元件库：把"一个力元"写成可实例化的类型，而不是每台车手写一遍雅可比。

Simpack 真正好用的地方就在这里——它把弹簧、减振器、衬套、止挡、空气簧、扭杆……做成有参数
界面、有单位、能报告力的**元件类型**，模型里只写"哪一个类型 + 哪几个参数 + 连在谁身上"。
在 0.4.26 之前我们只有一种拼装方式：在代码里手写 12 行 ``Connector``，或者在新拓扑里手写
``axial``/``torsional``。这一层把"有哪些元件、各自要哪些参数、参数合理范围"变成数据。

设计约束（三条，都是为了让"元件库"不是摆设）：

1. **元件只负责产生连接**（哪些坐标、系数多少、预载多少），不碰力律积分——组装仍然交给
   ``velch.topology`` 与求解器，这样 ``v2-node`` 与冻结布局共用一条装配路径。
2. **参数有单位与边界**，缺参数或越界要报出元件名和参数名，而不是抛一个 KeyError。
3. **新增一种元件 = 一个函数 + 一组测试**，不需要改求解器；这也是把 Simpack 的元件表
   一种一种搬过来的方式。

现在支持的元件（括号里是 Simpack 对应物）：

* ``spring``（Spring，只有刚度）
* ``damper``（Damper，只有阻尼）
* ``spring_damper``（Spring-Damper，并联）
* ``bushing``（Bushing，三向刚度/阻尼，允许对称交叉项——用特征分解成三个沿主方向的
  ``spring_damper``，所以不需要给求解器增加新的行结构）
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping, Sequence

import numpy as np

from .topology import LinkSpec, Topology, TopologyError, axial_spec

#: 每个元件的参数表：名字 → (单位, 是否必需)。
PARAMETERS: dict[str, dict[str, tuple[str, bool]]] = {
    # ``axial``/``torsional`` are the two raw kinds the first node table used; they stay
    # supported so an existing model keeps validating, but new files should name the element
    # they mean (spring, damper, spring_damper, bushing).
    "axial": {"stiffness": ("N/m", False), "damping": ("N·s/m", False),
              "preload_force": ("N", False)},
    "torsional": {"stiffness": ("N·m/rad", False), "damping": ("N·m·s/rad", False),
                  "preload_force": ("N·m", False)},
    "spring": {"stiffness": ("N/m", True), "preload_force": ("N", False)},
    "damper": {"damping": ("N·s/m", True)},
    "spring_damper": {"stiffness": ("N/m", True), "damping": ("N·s/m", True),
                      "preload_force": ("N", False)},
    "bushing": {"stiffness": ("N/m", True), "damping": ("N·s/m", False),
                "cross_stiffness": ("N/m", False)},
    # Nonlinear: the two rows below are this solver's first force laws that are not lines.
    "bump_stop": {"stiffness": ("N/m", True), "gap_m": ("m", False),
                  "transition_m": ("m", False), "preload_force": ("N", False)},
    # Data-driven: the curve someone measured, typed in as points.
    "force_table": {"points": ("m→N", True), "rate_points": ("m/s→N", False),
                    "preload_force": ("N", False)},
    "damper_blowoff": {"low_speed_damping": ("N·s/m", True),
                       "high_speed_damping": ("N·s/m", True),
                       "blowoff_speed": ("m/s", True)},
}


@dataclass(frozen=True)
class BumpStopLaw:
    """A gap, then a spring: the force element every Simpack vehicle uses at its travel limit.

    Compression is negative extension (the same sign the linear rows use), so the stop engages
    when ``extension < -gap_m``.

    With ``transition_m = 0`` the law is C0: the slope jumps from 0 to ``k`` at the gap, and the
    implicit integrator has to step over that corner. Setting ``transition_m = T`` replaces the
    corner with a quadratic ramp over the first ``T`` millimetres of travel, which is C1 at both
    ends (force and slope are continuous) -- that is what a rubber stop physically does. The ramp
    is **off by default**: it changes the force curve, so it must be a decision, not a default.
    """

    stiffness_n_m: float
    gap_m: float = 0.0
    transition_m: float = 0.0

    def _travel(self, extension: float) -> float:
        return max(0.0, -extension - self.gap_m)

    def force(self, extension: float, rate: float) -> float:
        travel = -extension - self.gap_m
        if travel <= 0.0:
            return 0.0
        ramp = self.transition_m
        if ramp > 0.0:
            # C1 blend: U(t) = k t^3/(6T) below T, and above it the linear branch is shifted by
            # kT/2 so that both F and dF/dt are continuous at t = T (the ramp consumes kT/2 N).
            if travel < ramp:
                return -self.stiffness_n_m * travel * travel / (2.0 * ramp)
            return -(self.stiffness_n_m * travel - 0.5 * self.stiffness_n_m * ramp)
        return -self.stiffness_n_m * travel

    def stiffness(self, extension: float) -> float:
        travel = -extension - self.gap_m
        if travel <= 0.0:
            return 0.0
        if self.transition_m > 0.0 and travel < self.transition_m:
            return self.stiffness_n_m * travel / self.transition_m
        return self.stiffness_n_m

    def damping(self, rate: float) -> float:
        return 0.0

    def potential(self, extension: float) -> float:
        travel = self._travel(extension)
        ramp = self.transition_m
        if ramp <= 0.0:
            return 0.5 * self.stiffness_n_m * travel * travel
        if travel < ramp:
            return self.stiffness_n_m * travel ** 3 / (6.0 * ramp)
        head = self.stiffness_n_m * ramp ** 2 / 6.0
        shifted = travel - 0.5 * ramp
        return head + 0.5 * self.stiffness_n_m * (shifted * shifted - 0.25 * ramp * ramp)


@dataclass(frozen=True)
class TableLaw:
    """Piecewise-linear force from measured points -- an air spring curve, a valve, a wear map.

    ``points`` are ``(extension_m, force_N)`` sorted by extension; the force between two points is
    linear and the slope there is exactly the secant slope, which is what the Jacobian uses.
    Outside the table the force is clamped and the slope is zero: beyond the last measured point we
    know the value, not the trend.

    ``rate_points`` (``(speed, force)``) adds a second, independent piecewise-linear damping
    channel, so a damper curve measured on a rig can be typed in as data.
    """

    points: tuple[tuple[float, float], ...]
    rate_points: tuple[tuple[float, float], ...] = ()

    def __post_init__(self) -> None:
        for name, table in (("points", self.points), ("rate_points", self.rate_points)):
            if table and len(table) < 2:
                raise ValueError(f"a table needs at least two {name}")
            keys = [float(pair[0]) for pair in table]
            if keys != sorted(keys):
                raise ValueError(f"{name} must be sorted by the first column")

    @staticmethod
    def _interpolate(table: tuple[tuple[float, float], ...], key: float) -> tuple[float, float]:
        """Return ``(value, slope)`` at ``key``; clamped outside, slope zero there."""

        if key <= table[0][0]:
            return float(table[0][1]), 0.0
        if key >= table[-1][0]:
            return float(table[-1][1]), 0.0
        for (x0, y0), (x1, y1) in zip(table, table[1:]):
            if key <= x1:
                if x1 == x0:
                    return float(y1), 0.0
                slope = (y1 - y0) / (x1 - x0)
                return float(y0 + slope * (key - x0)), float(slope)
        return float(table[-1][1]), 0.0  # pragma: no cover

    def force(self, extension: float, rate: float) -> float:
        value = 0.0
        if self.points:
            value += self._interpolate(self.points, extension)[0]
        if self.rate_points:
            value += self._interpolate(self.rate_points, rate)[0]
        return value

    def stiffness(self, extension: float) -> float:
        return self._interpolate(self.points, extension)[1] if self.points else 0.0

    def damping(self, rate: float) -> float:
        return self._interpolate(self.rate_points, rate)[1] if self.rate_points else 0.0

    def potential(self, extension: float) -> float:
        if not self.points:
            return 0.0
        total = 0.0
        for (x0, y0), (x1, y1) in zip(self.points, self.points[1:]):
            if extension <= x0:
                break
            span = min(extension, x1) - x0
            slope = (y1 - y0) / (x1 - x0) if x1 != x0 else 0.0
            total += y0 * span + 0.5 * slope * span * span
        return total


@dataclass(frozen=True)
class BlowoffDamperLaw:
    """Two slopes: below ``blowoff_speed`` the damper is stiff, above it the valve opens."""

    low_speed_n_s_m: float
    high_speed_n_s_m: float
    blowoff_speed_m_s: float

    def force(self, extension: float, rate: float) -> float:
        magnitude = abs(rate)
        low = min(magnitude, self.blowoff_speed_m_s)
        high = max(0.0, magnitude - self.blowoff_speed_m_s)
        value = self.low_speed_n_s_m * low + self.high_speed_n_s_m * high
        return value if rate >= 0.0 else -value

    def stiffness(self, extension: float) -> float:
        return 0.0

    def damping(self, rate: float) -> float:
        return (self.low_speed_n_s_m if abs(rate) <= self.blowoff_speed_m_s
                else self.high_speed_n_s_m)

    def potential(self, extension: float) -> float:
        return 0.0


@dataclass(frozen=True)
class ElementSpec:
    """A force element as written in a model file."""

    kind: str
    name: str
    from_body: str
    to_body: str | None
    from_point: tuple[float, float, float]
    to_point: tuple[float, float, float]
    direction: tuple[float, float, float]
    parameters: Mapping[str, Any]


def _point(spec: Mapping[str, Any], key: str) -> tuple[float, float, float]:
    raw = spec.get(key) or (0.0, 0.0, 0.0)
    if len(raw) != 3:
        raise TopologyError(f"element {spec.get('name')!r}: {key} must have three components")
    return (float(raw[0]), float(raw[1]), float(raw[2]))


def _end(spec: Mapping[str, Any], key: str) -> tuple[str | None, tuple[float, float, float]]:
    end = spec.get(key)
    if end is None:
        return None, (0.0, 0.0, 0.0)
    if not isinstance(end, Mapping) or "body" not in end:
        raise TopologyError(f"element {spec.get('name')!r}: {key} needs a 'body'")
    return str(end["body"]), _point(end, "point")


def _pairs(name: str, key: str, value: Any) -> tuple[tuple[float, float], ...]:
    """Validate a table parameter: a list of [x, y] pairs, finite, sorted by x."""

    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise TopologyError(f"element {name!r}: {key} must be a list of [x, y] pairs")
    pairs: list[tuple[float, float]] = []
    for item in value:
        if not isinstance(item, Sequence) or len(item) != 2:
            raise TopologyError(f"element {name!r}: each {key} entry must be [x, y]")
        x, y = float(item[0]), float(item[1])
        if not np.isfinite(x) or not np.isfinite(y):
            raise TopologyError(f"element {name!r}: {key} entries must be finite")
        pairs.append((x, y))
    keys = [pair[0] for pair in pairs]
    if len(keys) >= 2 and keys != sorted(keys):
        raise TopologyError(f"element {name!r}: {key} must be sorted by the first column")
    return tuple(pairs)


def parse(spec: Mapping[str, Any]) -> ElementSpec:
    """Validate one element dictionary by its type's parameter table."""

    kind = str(spec.get("kind") or "")
    if kind not in PARAMETERS:
        known = ", ".join(sorted(PARAMETERS))
        raise TopologyError(f"unknown element kind {kind!r}; known kinds: {known}")
    name = str(spec.get("name") or f"{kind}_{id(spec)}")
    from_body, from_point = _end(spec, "from")
    if from_body is None:
        raise TopologyError(f"element {name!r} needs a 'from' end")
    to_body, to_point = _end(spec, "to")
    direction = _point({"point": spec.get("direction") or (0.0, 0.0, 1.0)}, "point")
    if not any(direction):
        raise TopologyError(f"element {name!r}: direction must not be zero")

    parameters: dict[str, Any] = {}
    for key, (unit, required) in PARAMETERS[kind].items():
        value = spec.get(key)
        if value is None:
            if required:
                raise TopologyError(f"element {name!r} ({kind}) needs {key!r} [{unit}]")
            continue
        if key == "cross_stiffness":
            parameters[key] = value
            continue
        if key in {"points", "rate_points"}:
            parameters[key] = _pairs(name, key, value)
            continue
        number = float(value)
        if not np.isfinite(number) or number < 0.0:
            raise TopologyError(
                f"element {name!r}: {key} must be finite and non-negative [{unit}], got {value!r}")
        parameters[key] = number
    if kind in {"spring_damper", "damper"} and float(parameters.get("damping", 0.0)) <= 0.0:
        raise TopologyError(f"element {name!r} ({kind}) needs a positive damping")
    if kind in {"axial", "torsional"}:
        stiffness = float(parameters.get("stiffness", 0.0))
        damping = float(parameters.get("damping", 0.0))
        if stiffness <= 0.0 and damping <= 0.0:
            raise TopologyError(
                f"element {name!r} ({kind}) needs a positive stiffness or damping")
    if kind == "bushing":
        if float(parameters.get("stiffness", 0.0)) <= 0.0:
            raise TopologyError(f"element {name!r} (bushing) needs a positive stiffness")
    if kind == "bump_stop":
        if float(parameters.get("stiffness", 0.0)) <= 0.0:
            raise TopologyError(f"element {name!r} (bump_stop) needs a positive stiffness")
    if kind == "force_table" and len(parameters.get("points") or ()) < 2:
        raise TopologyError(
            f"element {name!r} (force_table) needs at least two 'points' [(m, N), ...]")
    if kind == "damper_blowoff":
        if float(parameters.get("low_speed_damping", 0.0)) <= 0.0:
            raise TopologyError(
                f"element {name!r} (damper_blowoff) needs a positive low_speed_damping")
        if float(parameters.get("high_speed_damping", 0.0)) <= 0.0:
            raise TopologyError(
                f"element {name!r} (damper_blowoff) needs a positive high_speed_damping")
        if float(parameters.get("blowoff_speed", 0.0)) <= 0.0:
            raise TopologyError(
                f"element {name!r} (damper_blowoff) needs a positive blowoff_speed")
    return ElementSpec(kind=kind, name=name, from_body=from_body, to_body=to_body,
                       from_point=from_point, to_point=to_point, direction=direction,
                       parameters=parameters)


def _axial(element: ElementSpec, topology: Topology, *, stiffness: float, damping: float,
           name: str, direction: Sequence[float], preload_force: float = 0.0,
           convention: Mapping[str, float] | None = None,
           law: object | None = None) -> LinkSpec:
    return axial_spec(topology, name, stiffness=stiffness, damping=damping,
                      direction=direction, from_body=element.from_body,
                      from_point=element.from_point, to_body=element.to_body,
                      to_point=element.to_point, preload_force=preload_force,
                      convention=convention, law=law)


def build(element: ElementSpec, topology: Topology,
          *, convention: Mapping[str, float] | None = None) -> list[LinkSpec]:
    """Turn one element into the connections the solver assembles.

    ``convention`` carries the topology's rotation-sign conventions (this solver's pitch is
    positive nose-down, so its pitch row is negated); the library must not decide that itself.
    """

    stiffness = float(element.parameters.get("stiffness", 0.0))
    damping = float(element.parameters.get("damping", 0.0))
    preload = float(element.parameters.get("preload_force", 0.0))
    if element.kind == "spring":
        if stiffness <= 0.0:
            raise TopologyError(f"element {element.name!r} (spring) needs a positive stiffness")
        return [_axial(element, topology, stiffness=stiffness, damping=0.0,
                       name=element.name, direction=element.direction,
                       preload_force=preload, convention=convention)]
    if element.kind == "damper":
        return [_axial(element, topology, stiffness=0.0, damping=damping,
                       name=element.name, direction=element.direction,
                       convention=convention)]
    if element.kind in {"spring_damper", "axial"}:
        return [_axial(element, topology, stiffness=stiffness, damping=damping,
                       name=element.name, direction=element.direction,
                       preload_force=preload, convention=convention)]
    if element.kind == "bushing":
        return _bushing(element, topology, stiffness=stiffness, damping=damping,
                        convention=convention)
    if element.kind == "force_table":
        law = TableLaw(points=tuple(element.parameters["points"]),
                       rate_points=tuple(element.parameters.get("rate_points") or ()))
        return [_axial(element, topology, stiffness=0.0, damping=0.0, name=element.name,
                       direction=element.direction,
                       preload_force=float(element.parameters.get("preload_force", 0.0)),
                       convention=convention, law=law)]
    if element.kind == "bump_stop":
        law = BumpStopLaw(stiffness_n_m=stiffness,
                          gap_m=float(element.parameters.get("gap_m", 0.0)),
                          transition_m=float(element.parameters.get("transition_m", 0.0)))
        return [_axial(element, topology, stiffness=0.0, damping=0.0, name=element.name,
                       direction=element.direction, preload_force=preload,
                       convention=convention, law=law)]
    if element.kind == "damper_blowoff":
        law = BlowoffDamperLaw(
            low_speed_n_s_m=float(element.parameters["low_speed_damping"]),
            high_speed_n_s_m=float(element.parameters["high_speed_damping"]),
            blowoff_speed_m_s=float(element.parameters["blowoff_speed"]))
        return [_axial(element, topology, stiffness=0.0, damping=0.0, name=element.name,
                       direction=element.direction, convention=convention, law=law)]
    raise TopologyError(f"element {element.name!r}: {element.kind!r} has no builder")  # pragma: no cover


def _bushing(element: ElementSpec, topology: Topology, *, stiffness: float, damping: float,
             convention: Mapping[str, float] | None = None) -> list[LinkSpec]:
    """A bushing as its principal directions: eigenvectors of the 3x3 stiffness matrix.

    Writing it this way keeps one row structure in the solver while still allowing the
    off-diagonal stiffness Simpack bushings accept.
    """

    cross = element.parameters.get("cross_stiffness") or {}
    if not isinstance(cross, Mapping):
        raise TopologyError(
            f"element {element.name!r}: cross_stiffness must be an object of axis pairs")
    axes = {"x": 0, "y": 1, "z": 2}
    matrix = np.zeros((3, 3), dtype=float)
    matrix[axes["x"], axes["x"]] = stiffness
    matrix[axes["y"], axes["y"]] = stiffness
    matrix[axes["z"], axes["z"]] = stiffness
    for key, value in cross.items():
        pair = str(key).split("-")
        if len(pair) != 2 or pair[0] not in axes or pair[1] not in axes:
            raise TopologyError(
                f"element {element.name!r}: cross_stiffness keys look like 'x-z', got {key!r}")
        i, j = axes[pair[0]], axes[pair[1]]
        matrix[i, j] = float(value)
        matrix[j, i] = float(value)
    if not np.allclose(matrix, matrix.T):
        raise TopologyError(f"element {element.name!r}: cross_stiffness must be symmetric")
    eigenvalues, eigenvectors = np.linalg.eigh(matrix)
    if float(np.min(eigenvalues)) < -1e-9:
        raise TopologyError(
            f"element {element.name!r}: stiffness matrix is not positive semi-definite "
            f"(eigenvalues {np.round(eigenvalues, 3).tolist()})")
    specs: list[LinkSpec] = []
    for index, (value, vector) in enumerate(zip(eigenvalues, eigenvectors.T)):
        if value <= 1e-9:
            continue
        try:
            specs.append(_axial(element, topology, stiffness=float(value), damping=damping,
                                name=f"{element.name}_p{index}",
                                direction=tuple(float(component) for component in vector),
                                convention=convention))
        except TopologyError:
            # A principal direction that neither body has (a bushing on x-less bodies, say)
            # contributes nothing to this model; the other directions still do.
            continue
    if not specs:
        raise TopologyError(f"element {element.name!r}: bushing yields no stiffness")
    return specs


def specs_for(block: Sequence[Mapping[str, Any]], topology: Topology,
              *, convention: Mapping[str, float] | None = None) -> list[LinkSpec]:
    """Build every element of a model's ``topology.elements`` list."""

    built: list[LinkSpec] = []
    seen: set[str] = set()
    for raw in block:
        element = parse(raw)
        if element.name in seen:
            raise TopologyError(f"duplicate element name {element.name!r}")
        seen.add(element.name)
        if element.kind == "torsional":
            # Torsional elements are declared with a rotation axis, not a direction; the
            # topology module already understands them, so keep that path unchanged.
            from .topology import torsional_spec
            axis = str(raw.get("axis") or "yaw")
            built.append(torsional_spec(topology, element.name,
                                        stiffness=float(element.parameters.get("stiffness", 0.0)),
                                        damping=float(element.parameters.get("damping", 0.0)),
                                        axis=axis, from_body=element.from_body,
                                        to_body=element.to_body))
            continue
        built.extend(build(element, topology, convention=convention))
    return built


def inventory(block: Mapping[str, Any]) -> dict[str, int]:
    """Count the elements a model declares, by type.

    ``block`` is a vehicle model (inline or the raw JSON of one). A model whose topology lives
    behind a ``vehicle_ref`` has nothing here, which is a fact worth showing rather than a zero.
    """

    topology = block.get("topology") or {}
    counts: dict[str, int] = {}
    for item in topology.get("elements") or ():
        if not isinstance(item, Mapping):
            continue
        kind = str(item.get("kind") or "?")
        counts[kind] = counts.get(kind, 0) + 1
    return counts


#: Model files written before the element library still name the two raw kinds; show the
#: element a reader knows, keeping the raw name so the line still matches the file.
_INVENTORY_NAMES = {"axial": "弹簧-阻尼(axial)", "torsional": "扭转(torsional)"}


def describe_inventory(counts: Mapping[str, int]) -> str:
    if not counts:
        return "（未声明元件）"
    return " · ".join(f"{_INVENTORY_NAMES.get(kind, kind)} {count}"
                      for kind, count in sorted(counts.items()))


def catalogue() -> list[dict[str, Any]]:
    """What this library offers, for ``velch vehicle`` and for the manual."""

    return [{"kind": kind,
             "parameters": [{"name": name, "unit": unit, "required": required}
                            for name, (unit, required) in table.items()]}
            for kind, table in PARAMETERS.items()]
