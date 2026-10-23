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
}


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
    return ElementSpec(kind=kind, name=name, from_body=from_body, to_body=to_body,
                       from_point=from_point, to_point=to_point, direction=direction,
                       parameters=parameters)


def _axial(element: ElementSpec, topology: Topology, *, stiffness: float, damping: float,
           name: str, direction: Sequence[float], preload_force: float = 0.0,
           convention: Mapping[str, float] | None = None) -> LinkSpec:
    return axial_spec(topology, name, stiffness=stiffness, damping=damping,
                      direction=direction, from_body=element.from_body,
                      from_point=element.from_point, to_body=element.to_body,
                      to_point=element.to_point, preload_force=preload_force,
                      convention=convention)


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


def catalogue() -> list[dict[str, Any]]:
    """What this library offers, for ``velch vehicle`` and for the manual."""

    return [{"kind": kind,
             "parameters": [{"name": name, "unit": unit, "required": required}
                            for name, (unit, required) in table.items()]}
            for kind, table in PARAMETERS.items()]
