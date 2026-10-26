"""Vehicle topology: which bodies exist, which degrees of freedom each carries, and the
linear elements that tie them together.

Two builders live here, and they answer the same question in two different ways:

``legacy_topology``
    Reproduces the frozen 5-DOF layout of :class:`velch.vehicle_solver.VehicleDynamics`
    exactly — same body order, same offsets, same element rows.  Nothing in the numeric
    path may change because of this module, so the rows are carried over verbatim from
    the hardcoded dictionaries that used to sit in ``_build_connectors``.

``node_topology``
    Derives the state vector from a node table (``topology.bodies``) and the element rows
    from *geometry* (``topology.elements``) instead of from a loop that knows about four
    axles and two bogies.  A body may carry any subset of ``x, y, z, roll, pitch, yaw``,
    which is what lets a six-degree-of-freedom body and the mined Simpack elements
    (anti-roll bar, traction rod, lateral damper) actually be assembled.

Sign conventions, stated once and tested:

* right handed axes: x along the track, y to the driver's right, z up;
* a positive rotation about an axis follows the right-hand rule;
* ``pitch_sign = -1`` because this solver (and Simpack) use the opposite pitch sense to
  the right-hand rule — a positive pitch is nose-down.  ``legacy_topology`` and the node
  layout both use the same sign, so the two agree element for element.

One element row is the generalised coordinate it springs along::

    delta = direction . [(u_a + theta_a x r_a) - (u_b + theta_b x r_b)]

so ``delta·(theta x r) = theta·(r x direction)`` gives the rotational coefficients
without a special case per axis.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Sequence

import numpy as np

#: Degrees of freedom a body may carry, in state-vector order.
DOF_ORDER: tuple[str, ...] = ("x", "y", "z", "roll", "pitch", "yaw")
#: The three that are translations, in the order they enter ``u``.
TRANSLATIONS: tuple[str, ...] = ("x", "y", "z")
#: The three that are rotations, in the order they enter ``theta``.
ROTATIONS: tuple[str, ...] = ("roll", "pitch", "yaw")

#: Legacy degrees of freedom per body kind, as frozen by the v2 layout.
LEGACY_DOF: dict[str, tuple[str, ...]] = {
    "wheelset": ("y", "z", "roll", "spin", "yaw"),
    "bogie": ("y", "z", "roll", "pitch", "yaw"),
    "carbody": ("y", "z", "roll", "pitch", "yaw"),
}
#: ``spin`` is a wheelset-only coordinate; it is not in :data:`DOF_ORDER` because no
#: element ever springs along it, but it occupies a slot in the state vector.
LEGACY_EXTRA: dict[str, float] = {"spin": 0.0}


class TopologyError(ValueError):
    """The node table cannot be turned into a state vector."""


@dataclass(frozen=True)
class Body:
    """One rigid body: what it is called, how big it is, and which coordinates it owns."""

    id: str
    kind: str
    dof: tuple[str, ...]
    mass_kg: float
    inertia: Mapping[str, float] = field(default_factory=dict)
    axle: int | None = None
    bogie: int | None = None

    def __post_init__(self) -> None:
        unknown = [name for name in self.dof if name not in DOF_ORDER and name != "spin"]
        if unknown:
            raise TopologyError(f"body {self.id!r} carries unknown degrees of freedom {unknown}")
        if len(set(self.dof)) != len(self.dof):
            raise TopologyError(f"body {self.id!r} repeats a degree of freedom")
        if self.mass_kg <= 0.0:
            raise TopologyError(f"body {self.id!r} has non-positive mass")
        if "spin" in self.dof and self.kind != "wheelset":
            raise TopologyError(f"body {self.id!r}: spin belongs to wheelsets")

    @property
    def width(self) -> int:
        return len(self.dof)


@dataclass(frozen=True)
class LinkSpec:
    """One linear spring-damper along a generalised coordinate.

    ``entries`` is the generalised coordinate as sparse coefficients: ``delta = sum(c_i q_i)``.
    ``preload_force`` is the force the element carries at ``delta = 0``; the solver turns it
    into a rest extension ``preload_force / stiffness`` exactly as it always has.
    """

    name: str
    axis: str
    stiffness: float
    damping: float
    entries: tuple[tuple[int, float], ...]
    preload_force: float = 0.0
    #: Optional force law for a nonlinear element. ``None`` means the linear
    #: ``-(k*extension + c*rate)`` row the solver has always assembled.
    law: object | None = None
    #: Generalised coordinate that senses the rate, when it differs from ``entries``.  Only
    #: used for the gyroscopic coupling of flexible-wheelset modes; ``None`` means "the same
    #: row", which is what every symmetric spring and damper wants.
    speed_entries: tuple[tuple[int, float], ...] | None = None

    @property
    def rest(self) -> float:
        return self.preload_force / self.stiffness if self.preload_force else 0.0

    def jacobian(self, dimension: int) -> np.ndarray:
        row = np.zeros(dimension)
        for index, coefficient in self.entries:
            row[index] += coefficient
        return row

    def speed_jacobian(self, dimension: int) -> np.ndarray:
        if self.speed_entries is None:
            return self.jacobian(dimension)
        row = np.zeros(dimension)
        for index, coefficient in self.speed_entries:
            row[index] += coefficient
        return row


@dataclass(frozen=True)
class Topology:
    """A state vector made of bodies, in order, plus the track block appended after them."""

    model: str
    bodies: tuple[Body, ...]
    offsets: Mapping[str, int]
    link_specs: tuple[LinkSpec, ...]
    track_offset: int
    pitch_sign: float = -1.0

    # -- lookups -----------------------------------------------------------------
    def body(self, body_id: str) -> Body:
        for candidate in self.bodies:
            if candidate.id == body_id:
                return candidate
        raise TopologyError(f"no body {body_id!r} in this topology")

    def offset(self, body_id: str) -> int:
        try:
            return self.offsets[body_id]
        except KeyError:
            raise TopologyError(f"no body {body_id!r} in this topology") from None

    def index(self, body_id: str, dof: str) -> int | None:
        """State index of ``dof`` on ``body_id``, or ``None`` when that body lacks it."""

        base = self.offset(body_id)
        for position, name in enumerate(self.body(body_id).dof):
            if name == dof:
                return base + position
        return None

    def require(self, body_id: str, dof: str) -> int:
        index = self.index(body_id, dof)
        if index is None:
            raise TopologyError(f"body {body_id!r} has no {dof!r} degree of freedom")
        return index

    def of_kind(self, kind: str) -> tuple[Body, ...]:
        return tuple(item for item in self.bodies if item.kind == kind)

    def wheelsets(self) -> tuple[Body, ...]:
        items = self.of_kind("wheelset")
        return tuple(sorted(items, key=lambda item: (item.axle if item.axle is not None else 0)))

    def bogies(self) -> tuple[Body, ...]:
        items = self.of_kind("bogie")
        return tuple(sorted(items, key=lambda item: (item.bogie if item.bogie is not None else 0)))

    def carbody(self) -> Body:
        items = self.of_kind("carbody")
        if len(items) != 1:
            raise TopologyError(f"a topology needs exactly one carbody, found {len(items)}")
        return items[0]

    def wheelset_id(self, axle: int) -> str:
        for item in self.wheelsets():
            if item.axle == axle:
                return item.id
        raise TopologyError(f"no wheelset for axle {axle}")

    def bogie_id(self, index: int) -> str:
        for item in self.bogies():
            if item.bogie == index:
                return item.id
        raise TopologyError(f"no bogie number {index}")

    # -- arrays ------------------------------------------------------------------
    @property
    def body_dimension(self) -> int:
        return self.track_offset

    def mass_array(self, track_mass: Sequence[float]) -> np.ndarray:
        values: list[float] = []
        for item in self.bodies:
            for dof in item.dof:
                if dof in ("x", "y", "z"):
                    values.append(item.mass_kg)
                elif dof == "spin":
                    values.append(float(item.inertia.get("spin", 0.0)))
                else:
                    values.append(float(item.inertia.get(dof, 0.0)))
            if any(not np.isfinite(value) or value <= 0.0 for value in values[-item.width:]):
                raise TopologyError(f"body {item.id!r} misses a positive mass or inertia")
        return np.array([*values, *track_mass], dtype=float)

    def signature(self) -> list[dict[str, Any]]:
        """Machine-readable summary, used by ``velch vehicle show`` and by tests."""

        return [
            {"id": item.id, "kind": item.kind, "offset": self.offsets[item.id],
             "dof": list(item.dof), "mass_kg": item.mass_kg}
            for item in self.bodies
        ]


def _add_translation(entries: dict[int, float], topology: Topology, body_id: str,
                     point: Sequence[float], direction: Sequence[float], sign: float,
                     *, convention: Mapping[str, float] | None = None) -> None:
    """Accumulate ``sign * direction . (u + theta x r)`` for one body at one anchor point."""

    body = topology.body(body_id)
    for position, name in enumerate(TRANSLATIONS):
        index = topology.index(body_id, name)
        # A zero component is not a connection: skip it so the emptiness check below can
        # tell "this element touches nothing here" from "it touches a coordinate by 0".
        if index is not None and direction[position]:
            entries[index] = entries.get(index, 0.0) + sign * float(direction[position])
    cross = np.cross(np.asarray(point, dtype=float), np.asarray(direction, dtype=float))
    for position, name in enumerate(ROTATIONS):
        index = topology.index(body_id, name)
        if index is not None and cross[position]:
            value = sign * float(cross[position])
            if convention and name in convention:
                value *= convention[name]
            entries[index] = entries.get(index, 0.0) + value
    if "spin" in body.dof and cross[0] and topology.index(body_id, "spin") is not None:
        # A wheelset's spin is a rotation about y; a direction with a y component therefore
        # couples to it.  No legacy element does, so this branch is normally dormant.
        index = topology.require(body_id, "spin")
        entries[index] = entries.get(index, 0.0) + sign * float(
            np.cross(np.asarray(point, dtype=float), np.asarray(direction, dtype=float))[1])


def axial_spec(topology: Topology, name: str, *, stiffness: float, damping: float,
               direction: Sequence[float],
               from_body: str, from_point: Sequence[float],
               to_body: str | None = None, to_point: Sequence[float] = (0.0, 0.0, 0.0),
               preload_force: float = 0.0,
               convention: Mapping[str, float] | None = None,
               law: object | None = None) -> LinkSpec:
    """A spring-damper between two anchor points, measured along ``direction``."""

    if stiffness <= 0.0 and damping <= 0.0 and law is None:
        raise TopologyError(f"element {name!r} needs a positive stiffness or damping")
    entries: dict[int, float] = {}
    _add_translation(entries, topology, from_body, from_point, direction, +1.0,
                     convention=convention)
    if to_body is not None:
        _add_translation(entries, topology, to_body, to_point, direction, -1.0,
                         convention=convention)
    if not entries:
        raise TopologyError(
            f"element {name!r} connects no degree of freedom in this topology "
            f"({from_body} -> {to_body}); widen the body's dof list or drop the element")
    return LinkSpec(name=name, axis="axial", stiffness=float(stiffness), damping=float(damping),
                    entries=tuple(sorted(entries.items())), preload_force=float(preload_force),
                    law=law)


def torsional_spec(topology: Topology, name: str, *, stiffness: float, damping: float,
                   axis: str, from_body: str, to_body: str | None = None,
                   preload_force: float = 0.0) -> LinkSpec:
    """A rotational spring-damper between two bodies about ``axis`` (``roll|pitch|yaw``)."""

    if axis not in ROTATIONS:
        raise TopologyError(f"element {name!r}: {axis!r} is not a rotation")
    if stiffness <= 0.0 and damping <= 0.0:
        raise TopologyError(f"element {name!r} needs a positive stiffness or damping")
    entries: dict[int, float] = {}
    index = topology.index(from_body, axis)
    if index is not None:
        entries[index] = entries.get(index, 0.0) + 1.0
    if to_body is not None:
        other = topology.index(to_body, axis)
        if other is not None:
            entries[other] = entries.get(other, 0.0) - 1.0
    if not entries:
        raise TopologyError(
            f"element {name!r} needs a {axis} degree of freedom on {from_body} or {to_body}")
    return LinkSpec(name=name, axis=axis, stiffness=float(stiffness), damping=float(damping),
                    entries=tuple(sorted(entries.items())), preload_force=float(preload_force))


# ---------------------------------------------------------------------------------
# Legacy: the frozen 5-DOF layout and the twelve element rows it has always used.
# ---------------------------------------------------------------------------------

def legacy_topology(cfg: Any, *, track_offset: int | None = None) -> Topology:
    """The v2 5-DOF layout, with the element rows copied verbatim from the frozen code.

    ``track_offset`` is filled in by :class:`VehicleDynamics` once the track kernel knows
    its own size; passing ``None`` leaves the vehicle block only (35 coordinates).
    """

    bodies: list[Body] = []
    offset = 0
    wheelset_inertia = {"roll": cfg.wheelset.roll_inertia_kg_m2,
                        "spin": cfg.wheelset.spin_inertia_kg_m2,
                        "yaw": cfg.wheelset.yaw_inertia_kg_m2}
    bogie_inertia = {"roll": cfg.bogie.roll_inertia_kg_m2,
                     "pitch": cfg.bogie.pitch_inertia_kg_m2,
                     "yaw": cfg.bogie.yaw_inertia_kg_m2}
    carbody_inertia = {"roll": cfg.carbody.roll_inertia_kg_m2,
                       "pitch": cfg.carbody.pitch_inertia_kg_m2,
                       "yaw": cfg.carbody.yaw_inertia_kg_m2}
    for axle in range(4):
        bodies.append(Body(id=f"wheelset{axle + 1}", kind="wheelset", dof=LEGACY_DOF["wheelset"],
                           mass_kg=cfg.wheelset.mass_kg, inertia=wheelset_inertia,
                           axle=axle, bogie=axle // 2))
    for index in range(2):
        bodies.append(Body(id=f"bogie{index + 1}", kind="bogie", dof=LEGACY_DOF["bogie"],
                           mass_kg=cfg.bogie.mass_kg, inertia=bogie_inertia,
                           bogie=index))
    bodies.append(Body(id="carbody", kind="carbody", dof=LEGACY_DOF["carbody"],
                       mass_kg=cfg.carbody.mass_kg, inertia=carbody_inertia))
    offsets: dict[str, int] = {}
    for item in bodies:
        offsets[item.id] = offset
        offset += item.width
    return Topology(model="v2-5dof", bodies=tuple(bodies), offsets=offsets, link_specs=(),
                    track_offset=offset if track_offset is None else track_offset,
                    pitch_sign=-1.0)


def legacy_link_specs(cfg: Any, topology: Topology) -> tuple[LinkSpec, ...]:
    """The twelve rows ``_build_connectors`` used to build by hand, as :class:`LinkSpec`s."""

    links: list[LinkSpec] = []

    def add(name: str, axis: str, k: float, c: float, entries: Mapping[int, float],
            preload: float = 0.0) -> None:
        links.append(LinkSpec(name=name, axis=axis, stiffness=float(k), damping=float(c),
                              entries=tuple(sorted(entries.items())),
                              preload_force=float(preload)))

    body = topology.offset("carbody")
    secondary = cfg.secondary
    secondary_preload = cfg.carbody.mass_kg * cfg.gravity_m_s2 / 4
    for bogie_index in range(2):
        bogie = topology.offset(f"bogie{bogie_index + 1}")
        x = cfg.bogie_half_spacing_m * (1 if bogie_index == 0 else -1)
        for side in (-1, 1):
            width = side * secondary.half_width_m
            label = f"secondary_b{bogie_index + 1}_{'L' if side < 0 else 'R'}"
            add(label + "_z", "z", secondary.k_z_n_m, secondary.c_z_n_s_m,
                {body + 1: 1, body + 2: width, body + 3: x,
                 bogie + 1: -1, bogie + 2: -width}, secondary_preload)
            add(label + "_y", "y", secondary.k_y_n_m, secondary.c_y_n_s_m,
                {body: 1, body + 2: -secondary.upper_anchor_height_m, body + 4: x,
                 bogie: -1, bogie + 2: secondary.lower_anchor_height_m})
        add(f"secondary_b{bogie_index + 1}_yaw", "yaw", secondary.k_yaw_nm_rad,
            secondary.c_yaw_nm_s_rad, {body + 4: 1, bogie + 4: -1})

    primary = cfg.primary
    primary_preload = (cfg.carbody.mass_kg / 2 + cfg.bogie.mass_kg) * cfg.gravity_m_s2 / 4
    for axle in range(4):
        bogie = topology.offset(f"bogie{axle // 2 + 1}")
        wheel = topology.offset(f"wheelset{axle + 1}")
        x = cfg.wheelbase_m / 2 * (1 if axle % 2 == 0 else -1)
        for side in (-1, 1):
            width = side * primary.half_width_m
            label = f"primary_a{axle + 1}_{'L' if side < 0 else 'R'}"
            add(label + "_z", "z", primary.k_z_n_m, primary.c_z_n_s_m,
                {bogie + 1: 1, bogie + 2: width, bogie + 3: x,
                 wheel + 1: -1, wheel + 2: -width}, primary_preload)
            add(label + "_y", "y", primary.k_y_n_m, primary.c_y_n_s_m,
                {bogie: 1, bogie + 2: -primary.upper_anchor_height_m, bogie + 4: x,
                 wheel: -1, wheel + 2: primary.lower_anchor_height_m})
        add(f"primary_a{axle + 1}_yaw", "yaw", primary.k_yaw_nm_rad,
            primary.c_yaw_nm_s_rad, {bogie + 4: 1, wheel + 4: -1})
    return tuple(links)


# ---------------------------------------------------------------------------------
# Node table: bodies and elements straight from the vehicle file.
# ---------------------------------------------------------------------------------

def node_topology(block: Mapping[str, Any], cfg: Any, *,
                  track_offset: int | None = None) -> Topology:
    """Build a topology from ``{"bodies": [...], "elements": [...]}``.

    ``bodies`` entries: ``id``, ``kind`` (wheelset|bogie|carbody), ``dof`` (subset of
    ``x, y, z, roll, pitch, yaw`` plus ``spin`` for wheelsets), ``mass_kg``, ``inertia``
    (roll/pitch/yaw/spin as needed), and ``axle``/``bogie`` numbers for the kinds that
    need them.  Masses may be written as ``"$vehicle.bogie.mass_kg"`` to inherit from the
    case's parameter block — that is how a node table keeps one source of truth for the
    numbers Simpack gave us without copying them twice.
    """

    if not isinstance(block, Mapping) or "bodies" not in block:
        raise TopologyError("a node topology needs a 'bodies' list")
    raw_bodies = block["bodies"]
    if not isinstance(raw_bodies, Sequence) or not raw_bodies:
        raise TopologyError("'bodies' must be a non-empty list")
    bodies: list[Body] = []
    offsets: dict[str, int] = {}
    offset = 0
    for raw in raw_bodies:
        if not isinstance(raw, Mapping):
            raise TopologyError("every body must be an object")
        dof = tuple(str(name) for name in raw.get("dof", ()))
        mass = _inherit(raw.get("mass_kg"), cfg)
        inertia_raw = raw.get("inertia", {}) or {}
        inertia = {str(name): _inherit(value, cfg) for name, value in inertia_raw.items()}
        if mass is None:
            raise TopologyError(f"body {raw.get('id')!r} needs a mass")
        body = Body(
            id=str(raw["id"]),
            kind=str(raw.get("kind", "carbody")),
            dof=dof,
            mass_kg=float(mass),
            inertia=inertia,
            axle=None if raw.get("axle") is None else int(raw["axle"]),
            bogie=None if raw.get("bogie") is None else int(raw["bogie"]),
        )
        if body.id in offsets:
            raise TopologyError(f"duplicate body id {body.id!r}")
        offsets[body.id] = offset
        offset += body.width
        bodies.append(body)

    # An axle box rides a wheelset, so its ``axle`` has to use the same numbering the wheelsets do.
    # Getting this wrong is not a crash: it shifts every column name of that body by one (a box on
    # axle 1 would be labelled ``axle2_box_left``) and the numbers stay plausible.
    wheelset_axles = {item.axle for item in bodies if item.kind == "wheelset" and item.axle is not None}
    for body in bodies:
        if body.kind != "axlebox":
            continue
        if body.axle is None:
            raise TopologyError(
                f"axle box {body.id!r} needs 'axle': the number of the wheelset it rides (0-based)")
        if wheelset_axles and body.axle not in wheelset_axles:
            raise TopologyError(
                f"axle box {body.id!r} rides axle {body.axle}, but the wheelsets are numbered "
                f"{sorted(wheelset_axles)}; axle numbers are 0-based, exactly like the wheelset's")

    topology = Topology(model="v2-node", bodies=tuple(bodies), offsets=offsets,
                        link_specs=(), track_offset=offset if track_offset is None else track_offset,
                        pitch_sign=float(block.get("pitch_sign", -1.0)))
    convention = {"pitch": topology.pitch_sign}
    # The element vocabulary lives in ``velch.elements``: one place that knows what a spring,
    # a damper, a bushing or a torsional link is and which parameters each needs.  Inherited
    # values (``"$vehicle.primary.k_z_n_m"``) are resolved here first, so the library only ever
    # sees numbers.
    from .elements import parse as parse_element, build as build_element

    links: list[LinkSpec] = []
    resolved: list[dict[str, Any]] = []
    for raw in block.get("elements", ()) or ():
        if not isinstance(raw, Mapping):
            raise TopologyError("every element must be an object")
        resolved.append({
            key: (_inherit(value, cfg) if isinstance(value, str) else value)
            for key, value in raw.items()
        })
    seen: set[str] = set()
    for raw in resolved:
        element = parse_element(raw)
        if element.name in seen:
            raise TopologyError(f"duplicate element name {element.name!r}")
        seen.add(element.name)
        if element.kind == "torsional":
            links.append(torsional_spec(
                topology, element.name,
                stiffness=float(element.parameters.get("stiffness", 0.0)),
                damping=float(element.parameters.get("damping", 0.0)),
                axis=str(raw.get("axis", "roll")),
                from_body=element.from_body, to_body=element.to_body,
                preload_force=float(element.parameters.get("preload_force", 0.0))))
        else:
            links.extend(build_element(element, topology, convention=convention))
    return Topology(model=topology.model, bodies=topology.bodies, offsets=topology.offsets,
                    link_specs=tuple(links), track_offset=topology.track_offset,
                    pitch_sign=topology.pitch_sign)


def _legacy_element_loop(block: Mapping[str, Any], topology: Topology, cfg: Any,
                         convention: Mapping[str, float]) -> list[LinkSpec]:
    """The first implementation, kept for reference while the library is young."""

    links: list[LinkSpec] = []
    for raw in block.get("elements", ()) or ():
        if not isinstance(raw, Mapping):
            raise TopologyError("every element must be an object")
        kind = str(raw.get("kind", "axial"))
        name = str(raw.get("name") or f"element{len(links) + 1}")
        stiffness = _inherit(raw.get("stiffness"), cfg)
        damping = _inherit(raw.get("damping", 0.0), cfg) or 0.0
        preload = _inherit(raw.get("preload_force", 0.0), cfg) or 0.0
        if kind == "axial":
            links.append(axial_spec(
                topology, name, stiffness=float(stiffness), damping=float(damping),
                direction=raw["direction"],
                from_body=str(raw["from"]["body"]), from_point=raw["from"].get("point", (0, 0, 0)),
                to_body=None if raw.get("to") is None else str(raw["to"]["body"]),
                to_point=(0, 0, 0) if raw.get("to") is None else raw["to"].get("point", (0, 0, 0)),
                preload_force=float(preload), convention=convention))
        elif kind == "torsional":
            links.append(torsional_spec(
                topology, name, stiffness=float(stiffness), damping=float(damping),
                axis=str(raw.get("axis", "roll")),
                from_body=str(raw["from"]["body"]),
                to_body=None if raw.get("to") is None else str(raw["to"]["body"]),
                preload_force=float(preload)))
        else:
            raise TopologyError(f"element {name!r}: unknown kind {kind!r}")
    return Topology(model=topology.model, bodies=topology.bodies, offsets=topology.offsets,
                    link_specs=tuple(links), track_offset=topology.track_offset,
                    pitch_sign=topology.pitch_sign)


def _inherit(value: Any, cfg: Any) -> Any:
    """Resolve ``"$vehicle.bogie.mass_kg"`` against the case's vehicle block."""

    if not isinstance(value, str) or not value.startswith("$"):
        return value
    node: Any = cfg
    for part in value.lstrip("$").split("."):
        if part == "vehicle" and not isinstance(node, dict):
            # ``$vehicle.x`` addresses the parameter block itself, wherever we started.
            continue
        if isinstance(node, dict):
            if part not in node:
                raise TopologyError(f"cannot resolve {value!r}: no key {part!r}")
            node = node[part]
            continue
        if node is None or not hasattr(node, part):
            raise TopologyError(f"cannot resolve {value!r}: no attribute {part!r}")
        node = getattr(node, part)
    return node


def topology_of(block: Mapping[str, Any] | None, cfg: Any, *,
                track_offset: int | None = None) -> Topology:
    """Build a topology from a case's ``topology`` block, defaulting to the legacy layout.

    Parameters are a plain mapping and the parameter block rather than a whole case, because
    :func:`velch.vehicle.load_vehicle_case` needs the state size *before* it can build one.
    """

    if block:
        return node_topology(block, cfg, track_offset=track_offset)
    legacy = legacy_topology(cfg, track_offset=track_offset)
    return Topology(model=legacy.model, bodies=legacy.bodies, offsets=legacy.offsets,
                    link_specs=legacy_link_specs(cfg, legacy),
                    track_offset=legacy.track_offset, pitch_sign=legacy.pitch_sign)


def topology_for(case: Any, *, track_offset: int | None = None) -> Topology:
    """Pick the builder the case asks for: node table when present, legacy otherwise."""

    return topology_of(getattr(case, "topology", None), case.vehicle,
                       track_offset=track_offset)


def remap_state(values, source: "Topology", target: "Topology") -> list[float]:
    """Carry a state vector from one topology to another, matching bodies and axes by name.

    A 35-coordinate initial state is a *balanced* guess for the same physical car; dropping it when
    the layout grows by an ``x`` coordinate throws that information away and leaves the static solve
    starting from zeros, which is why the first node-layout compliant-track runs reported
    "no seed converged".  Coordinates the target does not share with the source start at zero.
    """

    supplied = [float(x) for x in values]
    if len(supplied) != source.body_dimension:
        # Silence here is expensive.  Slicing a whole-state vector with this function drops the
        # track block, and the leftover is exactly one contact patch per rail (59 662 N at the
        # static seat) — which reads as a physical imbalance instead of as a truncated vector.
        # That fingerprint cost a whole night of misattribution (O010).
        raise TopologyError(
            f"remap_state takes the {source.body_dimension} body coordinates of the source "
            f"layout, but received {len(supplied)} values; call migrate_initial_state() for a "
            "whole state vector (body + track + modal)")

    out = [0.0] * target.body_dimension
    for body in target.bodies:
        source_body = next((b for b in source.bodies if b.id == body.id), None)
        if source_body is None:
            continue
        for axis in body.dof:
            if axis not in source_body.dof:
                continue          # a coordinate the source never had (the new x) starts at zero
            out[target.require(body.id, axis)] = supplied[source.require(body.id, axis)]
    return out


def migrate_initial_state(supplied, source: "Topology", target: "Topology", *,
                          tracks: int, modal_size: int = 0) -> list[float]:
    """Carry a *whole* state vector onto another layout: body by name, then track, then modal.

    ``remap_state`` deliberately handles only the body block; every caller that migrates a full
    ``initial_state.q`` has to stitch the other blocks back on itself, and getting that wrong
    silently zeroes a block.  This function is that stitch, in one place:

    * body coordinates are matched by (body id, axis), so a layout that gains an ``x`` keeps the
      balanced heights of the old one and starts the new coordinate at zero;
    * the track block is copied verbatim (the track layout does not depend on the vehicle);
    * modal coordinates are appended as zeros — a flexible wheelset that was rigid has no
      deflection to inherit.
    """

    values = [float(x) for x in supplied]
    full = source.body_dimension + tracks
    if len(values) == full:
        track_values = values[source.body_dimension:]
    elif len(values) == source.body_dimension:
        track_values = [0.0] * tracks
    else:
        raise TopologyError(
            f"initial_state has {len(values)} values; the source layout takes "
            f"{source.body_dimension} body ({full} with its {tracks} track coordinates)")
    return (remap_state(values[:source.body_dimension], source, target)
            + track_values
            + [0.0] * modal_size)
