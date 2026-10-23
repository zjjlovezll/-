"""Independent rigid, local-compliant and reduced-modal turnout track kernels.

These are Velch formulations, not Simpack flexible-body file readers. A modal
model must provide its own audited mode masses, frequencies and contact shapes.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

import numpy as np


@dataclass(frozen=True)
class ModeShape:
    station_m: np.ndarray
    phi_y: np.ndarray
    phi_z: np.ndarray

    def sample(self, station_m: float) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        s = self.station_m
        if station_m < s[0] - 1e-10 or station_m > s[-1] + 1e-10:
            raise ValueError(f"modal shape station {station_m:.9g} m outside [{s[0]}, {s[-1]}]")
        station_m = min(max(station_m, float(s[0])), float(s[-1]))
        lower = min(max(int(np.searchsorted(s, station_m, side="right")) - 1, 0), len(s) - 2)
        span = s[lower + 1] - s[lower]
        weight = (station_m - s[lower]) / span
        py = (1 - weight) * self.phi_y[:, lower] + weight * self.phi_y[:, lower + 1]
        pz = (1 - weight) * self.phi_z[:, lower] + weight * self.phi_z[:, lower + 1]
        dpy = (self.phi_y[:, lower + 1] - self.phi_y[:, lower]) / span
        dpz = (self.phi_z[:, lower + 1] - self.phi_z[:, lower]) / span
        return py, pz, dpy, dpz


@dataclass(frozen=True)
class ModalTrack:
    source: Path
    mass_kg: np.ndarray
    frequency_hz: np.ndarray
    damping_ratio: np.ndarray
    shapes: dict[str, ModeShape]

    @property
    def mode_count(self) -> int:
        return len(self.mass_kg)

    @property
    def stiffness_n_m(self) -> np.ndarray:
        return self.mass_kg * (2 * math.pi * self.frequency_hz) ** 2

    @property
    def damping_n_s_m(self) -> np.ndarray:
        return 2 * self.damping_ratio * self.mass_kg * 2 * math.pi * self.frequency_hz


def load_modal_track(path: str | Path, template_ids: Sequence[str]) -> ModalTrack:
    """Load an explicit Velch modal exchange file; never guess Simpack .fbi data."""
    source = Path(path).resolve(strict=True)
    raw: dict[str, Any] = json.loads(source.read_text(encoding="utf-8-sig"))
    if raw.get("schema_version") != "velch-modal-track-v1":
        raise ValueError("unsupported modal track exchange schema")
    modes = raw.get("modes")
    if not isinstance(modes, list) or not modes:
        raise ValueError("modal track requires at least one mode")
    masses = np.asarray([mode["modal_mass_kg"] for mode in modes], dtype=float)
    frequencies = np.asarray([mode["frequency_hz"] for mode in modes], dtype=float)
    damping = np.asarray([mode["damping_ratio"] for mode in modes], dtype=float)
    if (not np.all(np.isfinite(masses)) or np.any(masses <= 0) or
        not np.all(np.isfinite(frequencies)) or np.any(frequencies <= 0) or
        not np.all(np.isfinite(damping)) or np.any((damping < 0) | (damping >= 1))):
        raise ValueError("modal mass/frequency must be positive; damping ratio must be in [0,1)")
    shape_data = raw.get("rail_shapes")
    if not isinstance(shape_data, dict) or set(shape_data) != set(template_ids):
        # The modal path carries ONE shared set of modal coordinates (``q[35:]``), so every rail in
        # the case moves together.  That is only defensible for a symmetric track: a turnout needs
        # the left and right rails to move independently, which this exchange format cannot express.
        # Failing loudly here beats silently modelling both rails as one body.
        available = sorted(shape_data) if isinstance(shape_data, dict) else []
        raise ValueError(
            "modal rail_shapes must match case rail template IDs exactly "
            f"(file has {available}, case asks {sorted(template_ids)}); the modal block is shared "
            "by all rails (single set of modal coordinates), so it cannot represent independent "
            "left/right rail motion -- use track_dynamics kind 'layered' for that"
        )
    shapes: dict[str, ModeShape] = {}
    for rail_id, definition in shape_data.items():
        s = np.asarray(definition["station_m"], dtype=float)
        py = np.asarray(definition["phi_y"], dtype=float)
        pz = np.asarray(definition["phi_z"], dtype=float)
        if (s.ndim != 1 or len(s) < 2 or not np.all(np.isfinite(s)) or
            not np.all(np.diff(s) > 0)):
            raise ValueError(f"{rail_id}: modal stations must be finite and strictly increasing")
        if (py.shape != (len(modes), len(s)) or pz.shape != py.shape or
            not np.all(np.isfinite(py)) or not np.all(np.isfinite(pz))):
            raise ValueError(f"{rail_id}: modal shape dimensions or values invalid")
        if not np.any(py) and not np.any(pz):
            # A zero-shape rail cannot receive contact work from any mode.
            pass
        s.setflags(write=False)
        py.setflags(write=False)
        pz.setflags(write=False)
        shapes[rail_id] = ModeShape(s, py, pz)
    for array in (masses, frequencies, damping):
        array.setflags(write=False)
    return ModalTrack(source, masses, frequencies, damping, shapes)


class TrackKernel:
    """Map rail contact forces to track coordinates using conjugate shapes."""

    def __init__(self, kind: str, rails: Sequence[Any], modal: ModalTrack | None = None,
                 layers: Sequence[Any] = (), offset: int = 35):
        if kind not in {"rigid", "local_compliant", "two_layer", "layered", "modal"}:
            raise ValueError("track kind must be rigid, local_compliant, two_layer, layered or modal")
        if (kind == "layered") != bool(layers) and kind == "layered":
            raise ValueError("layered track requires at least one layer below the rail")
        if (kind == "modal") != (modal is not None):
            raise ValueError("modal track kind requires exactly one modal exchange file")
        #: Index of the first track coordinate in the state vector.  It used to be the
        #: literal 35, which hardcoded a five-DOF vehicle; a node table may carry more
        #: coordinates, so the block starts wherever the vehicle block ends.
        self.offset = int(offset)
        self.kind, self.rails, self.modal = kind, tuple(rails), modal
        self.layers = tuple(layers)
        if kind == "rigid":
            self.mass = np.empty(0)
            self.state_names: list[str] = []
        elif kind == "local_compliant":
            self.mass = np.array([value for rail in rails for value in (rail.mass_y_kg, rail.mass_z_kg)])
            self.state_names = [f"{rail.id}_{axis}_m" for rail in rails for axis in ("y", "z")]
        elif kind == "layered":
            self.mass = np.array([
                value
                for rail in rails
                for value in (rail.mass_y_kg, rail.mass_z_kg,
                              *[item for layer in self.layers
                                for item in (layer.mass_y_kg, layer.mass_z_kg)])
            ])
            self.state_names = [
                f"{rail.id}_{label}_{axis}_m"
                for rail in rails
                for label in ["rail"] + [f"layer{k + 1}" for k in range(len(self.layers))]
                for axis in ("y", "z")
            ]
        elif kind == "two_layer":
            for rail in rails:
                if rail.support.sleeper_mass_y_kg <= 0.0 or rail.support.sleeper_mass_z_kg <= 0.0:
                    raise ValueError("two_layer track requires a positive sleeper mass")
                if rail.support.ballast_k_z_n_m <= 0.0:
                    raise ValueError("two_layer track requires a positive ballast stiffness")
            self.mass = np.array([
                value
                for rail in rails
                for value in (rail.mass_y_kg, rail.mass_z_kg,
                              rail.support.sleeper_mass_y_kg,
                              rail.support.sleeper_mass_z_kg)
            ])
            self.state_names = [
                f"{rail.id}_{layer}_{axis}_m"
                for rail in rails
                for layer in ("rail", "sleeper")
                for axis in ("y", "z")
            ]
        else:
            assert modal is not None
            self.mass = modal.mass_kg.copy()
            self.state_names = [f"track_mode{i + 1}_m" for i in range(modal.mode_count)]

    @property
    def dimension(self) -> int:
        return len(self.mass)

    def local_state(self, q: np.ndarray, v: np.ndarray, rail_index: int, x_m: float,
                    speed_m_s: float) -> tuple[float, float, float, float]:
        if self.kind == "rigid":
            return 0.0, 0.0, 0.0, 0.0
        if self.kind == "local_compliant":
            pos = self.offset + 2 * rail_index
            return float(q[pos]), float(q[pos + 1]), float(v[pos]), float(v[pos + 1])
        if self.kind == "two_layer":
            pos = self.offset + 4 * rail_index
            return float(q[pos]), float(q[pos + 1]), float(v[pos]), float(v[pos + 1])
        if self.kind == "layered":
            pos = self.offset + 2 * (1 + len(self.layers)) * rail_index
            return float(q[pos]), float(q[pos + 1]), float(v[pos]), float(v[pos + 1])
        assert self.modal is not None
        rail = self.rails[rail_index]
        py, pz, dpy, dpz = self.modal.shapes[rail.template_id].sample(x_m)
        eta, etadot = q[self.offset:], v[self.offset:]
        return (float(py @ eta), float(pz @ eta),
                float(py @ etadot + speed_m_s * (dpy @ eta)),
                float(pz @ etadot + speed_m_s * (dpz @ eta)))

    def internal_force(self, q: np.ndarray, v: np.ndarray) -> np.ndarray:
        if self.kind == "rigid":
            return np.empty(0)
        if self.kind == "local_compliant":
            result = np.empty(self.dimension)
            for i, rail in enumerate(self.rails):
                result[2 * i] = -rail.support.k_y_n_m * q[self.offset + 2 * i] - rail.support.c_y_n_s_m * v[self.offset + 2 * i]
                result[2 * i + 1] = -rail.support.k_z_n_m * q[36 + 2 * i] - rail.support.c_z_n_s_m * v[36 + 2 * i]
            return result
        if self.kind == "layered":
            result = np.zeros(self.dimension)
            stride = 2 * (1 + len(self.layers))
            for i, rail in enumerate(self.rails):
                base = stride * i
                springs = (rail.support, *self.layers)
                for axis in (0, 1):
                    for j, spring in enumerate(springs):
                        here = base + 2 * j + axis
                        below = here + 2 if j + 1 < len(springs) else None
                        stiffness = spring.k_y_n_m if axis == 0 else spring.k_z_n_m
                        damping = spring.c_y_n_s_m if axis == 0 else spring.c_z_n_s_m
                        gap = q[self.offset + here] - (q[self.offset + below] if below is not None else 0.0)
                        rate = v[self.offset + here] - (v[self.offset + below] if below is not None else 0.0)
                        force = stiffness * gap + damping * rate
                        result[here] -= force
                        if below is not None:
                            result[below] += force
            return result
        if self.kind == "two_layer":
            result = np.empty(self.dimension)
            for i, rail in enumerate(self.rails):
                base, out = self.offset + 4 * i, 4 * i
                for axis, pad_k, pad_c, ballast_k, ballast_c in (
                        (0, rail.support.k_y_n_m, rail.support.c_y_n_s_m,
                         rail.support.ballast_k_y_n_m, rail.support.ballast_c_y_n_s_m),
                        (1, rail.support.k_z_n_m, rail.support.c_z_n_s_m,
                         rail.support.ballast_k_z_n_m, rail.support.ballast_c_z_n_s_m)):
                    gap = q[base + axis] - q[base + 2 + axis]
                    rate = v[base + axis] - v[base + 2 + axis]
                    pad = pad_k * gap + pad_c * rate
                    result[out + axis] = -pad
                    result[out + 2 + axis] = (pad -
                        ballast_k * q[base + 2 + axis] -
                        ballast_c * v[base + 2 + axis])
            return result
        assert self.modal is not None
        return -self.modal.stiffness_n_m * q[self.offset:] - self.modal.damping_n_s_m * v[self.offset:]

    def contact_reaction(self, rail_index: int, x_m: float, fy_n: float, fz_n: float) -> np.ndarray:
        """Return generalized rail force opposing the wheel's y/z force."""
        result = np.zeros(self.dimension)
        if self.kind == "local_compliant":
            result[2 * rail_index] = -fy_n
            result[2 * rail_index + 1] = -fz_n
        elif self.kind == "two_layer":
            result[4 * rail_index] = -fy_n
            result[4 * rail_index + 1] = -fz_n
        elif self.kind == "layered":
            stride = 2 * (1 + len(self.layers))
            result[stride * rail_index] = -fy_n
            result[stride * rail_index + 1] = -fz_n
        elif self.kind == "modal":
            assert self.modal is not None
            py, pz, _, _ = self.modal.shapes[self.rails[rail_index].template_id].sample(x_m)
            result -= py * fy_n + pz * fz_n
        return result

    def potential_j(self, q: np.ndarray) -> float:
        if self.kind == "local_compliant":
            return float(sum(0.5 * (rail.support.k_y_n_m * q[self.offset + 2 * i] ** 2 +
                                    rail.support.k_z_n_m * q[36 + 2 * i] ** 2)
                             for i, rail in enumerate(self.rails)))
        if self.kind == "layered":
            total = 0.0
            stride = 2 * (1 + len(self.layers))
            for i, rail in enumerate(self.rails):
                base = stride * i
                springs = (rail.support, *self.layers)
                for axis in (0, 1):
                    for j, spring in enumerate(springs):
                        here = base + 2 * j + axis
                        below = here + 2 if j + 1 < len(springs) else None
                        stiffness = spring.k_y_n_m if axis == 0 else spring.k_z_n_m
                        gap = q[self.offset + here] - (q[self.offset + below] if below is not None else 0.0)
                        total += 0.5 * stiffness * gap ** 2
            return float(total)
        if self.kind == "two_layer":
            total = 0.0
            for i, rail in enumerate(self.rails):
                base = self.offset + 4 * i
                for axis, pad_k, ballast_k in (
                        (0, rail.support.k_y_n_m, rail.support.ballast_k_y_n_m),
                        (1, rail.support.k_z_n_m, rail.support.ballast_k_z_n_m)):
                    gap = q[base + axis] - q[base + 2 + axis]
                    total += 0.5 * pad_k * gap ** 2
                    total += 0.5 * ballast_k * q[base + 2 + axis] ** 2
            return float(total)
        if self.kind == "modal":
            assert self.modal is not None
            return float(0.5 * np.dot(self.modal.stiffness_n_m, q[self.offset:] ** 2))
        return 0.0

    def support_reaction(self, q: np.ndarray, v: np.ndarray,
                         wheel_contact_forces: Sequence[tuple[float, float]]) -> tuple[float, float] | None:
        if self.kind == "rigid":
            return -sum(force[0] for force in wheel_contact_forces), -sum(force[1] for force in wheel_contact_forces)
        if self.kind == "local_compliant":
            return (sum(rail.support.k_y_n_m * q[self.offset + 2 * i] + rail.support.c_y_n_s_m * v[self.offset + 2 * i]
                        for i, rail in enumerate(self.rails)),
                    sum(rail.support.k_z_n_m * q[36 + 2 * i] + rail.support.c_z_n_s_m * v[36 + 2 * i]
                        for i, rail in enumerate(self.rails)))
        if self.kind == "layered":
            # The ground only carries what the bottom-most spring passes on.
            stride = 2 * (1 + len(self.layers))
            bottom = len(self.layers)
            lateral = vertical = 0.0
            for i, rail in enumerate(self.rails):
                here = stride * i + 2 * bottom
                spring = self.layers[-1]
                lateral += spring.k_y_n_m * q[self.offset + here] + spring.c_y_n_s_m * v[self.offset + here]
                vertical += (spring.k_z_n_m * q[self.offset + here + 1] +
                             spring.c_z_n_s_m * v[self.offset + here + 1])
            return lateral, vertical
        if self.kind == "two_layer":
            # The ground only carries what the ballast passes on.
            lateral = vertical = 0.0
            for i, rail in enumerate(self.rails):
                base = self.offset + 4 * i
                lateral += (rail.support.ballast_k_y_n_m * q[base + 2] +
                            rail.support.ballast_c_y_n_s_m * v[base + 2])
                vertical += (rail.support.ballast_k_z_n_m * q[base + 3] +
                             rail.support.ballast_c_z_n_s_m * v[base + 3])
            return lateral, vertical
        return None
