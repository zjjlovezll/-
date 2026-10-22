"""Add a general layered track (steel rail / fastening / sleeper / slab / subgrade).

The user's stage-3 spec is exactly this stack: 钢轨、扣件、轨枕、板下胶垫、轨道板.
Instead of one bespoke kernel per depth, the track is now a configurable stack:

    track_dynamics = {
        "kind": "layered",
        "layers": [                     # the stack *below* the rail, top to bottom
            {"mass_y_kg": 79,  "mass_z_kg": 79,  ...},   # sleeper
            {"mass_y_kg": 300, "mass_z_kg": 300, ...}    # track slab
        ]
    }

The rail sits on `rail_templates[i].support` (the pad). `layers[i].k/c` is the
spring *below* layer i, so:

    L=0  rail --pad--> ground            (identical to local_compliant)
    L=1  rail --pad--> sleeper --ballast--> ground   (identical to two_layer)
    L=2  rail --pad--> sleeper --ballast--> slab --subgrade--> ground

DOF order per rail: (y_rail, z_rail, y_L0, z_L0, y_L1, z_L1, ...) at
35 + 2 * (1 + L) * rail_index.
"""

from __future__ import annotations

import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2] / "src" / "velch"


def patch(name: str, pairs: list[tuple[str, str]]) -> None:
    path = ROOT / name
    text = path.read_text(encoding="utf-8")
    for old, new in pairs:
        if new in text:
            continue  # already applied: keep the patch idempotent
        if old not in text:
            raise SystemExit(f"{name}: anchor missing -> {old.splitlines()[0][:80]!r}")
        text = text.replace(old, new, 1)
    path.write_text(text, encoding="utf-8")
    print(f"patched {name}")


# ---------------------------------------------------------------- model.py
patch("model.py", [(
    '''@dataclass(frozen=True)
class WheelSuspension:''',
    '''@dataclass(frozen=True)
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
class WheelSuspension:''',
)])

# --------------------------------------------------------------- vehicle.py
patch("vehicle.py", [
    (
        'from .model import LinearSupport, RunSettings, Wheel',
        'from .model import LinearSupport, RunSettings, TrackLayer, Wheel',
    ),
    (
        '    support_compliance: SupportCompliance | None = None',
        '    support_compliance: SupportCompliance | None = None\n'
        '    track_layers: tuple[TrackLayer, ...] = ()',
    ),
    (
        '        if self.track_kind not in {"rigid", "local_compliant", "two_layer", "modal"}:\n'
        '            raise ValueError("unknown track dynamics kind")',
        '        if self.track_kind not in {"rigid", "local_compliant", "two_layer", "layered", "modal"}:\n'
        '            raise ValueError("unknown track dynamics kind")',
    ),
    (
        '        n = 35 + (2 * len(self.rails) if self.track_kind == "local_compliant"\n'
        '                  else 4 * len(self.rails) if self.track_kind == "two_layer"\n'
        '                  else self.modal_track.mode_count if self.modal_track else 0)',
        '        n = 35 + (2 * len(self.rails) if self.track_kind == "local_compliant"\n'
        '                  else 4 * len(self.rails) if self.track_kind == "two_layer"\n'
        '                  else 2 * (1 + len(self.track_layers)) * len(self.rails)\n'
        '                  if self.track_kind == "layered"\n'
        '                  else self.modal_track.mode_count if self.modal_track else 0)',
    ),
    (
        '    if track_kind not in {"rigid", "local_compliant", "two_layer", "modal"}:\n'
        '        raise ValueError("track_dynamics.kind must be rigid, local_compliant, two_layer or modal")',
        '    if track_kind not in {"rigid", "local_compliant", "two_layer", "layered", "modal"}:\n'
        '        raise ValueError("track_dynamics.kind must be rigid, local_compliant, two_layer, layered or modal")\n'
        '    layers = tuple(TrackLayer(**layer) for layer in track_spec.get("layers", []))',
    ),
    (
        '    n = 35 + (2 * len(rails) if track_kind == "local_compliant"\n'
        '              else 4 * len(rails) if track_kind == "two_layer"\n'
        '              else modal_track.mode_count if modal_track else 0)',
        '    n = 35 + (2 * len(rails) if track_kind == "local_compliant"\n'
        '              else 4 * len(rails) if track_kind == "two_layer"\n'
        '              else 2 * (1 + len(layers)) * len(rails) if track_kind == "layered"\n'
        '              else modal_track.mode_count if modal_track else 0)',
    ),
    (
        '                       hashlib.sha256(raw_bytes).hexdigest(), assets, compliance)',
        '                       hashlib.sha256(raw_bytes).hexdigest(), assets, compliance,\n'
        '                       layers)',
    ),
])

# --------------------------------------------------------- track_models.py
patch("track_models.py", [
    (
        '    def __init__(self, kind: str, rails: Sequence[Any], modal: ModalTrack | None = None):\n'
        '        if kind not in {"rigid", "local_compliant", "two_layer", "modal"}:\n'
        '            raise ValueError("track kind must be rigid, local_compliant, two_layer or modal")',
        '    def __init__(self, kind: str, rails: Sequence[Any], modal: ModalTrack | None = None,\n'
        '                 layers: Sequence[Any] = ()):\n'
        '        if kind not in {"rigid", "local_compliant", "two_layer", "layered", "modal"}:\n'
        '            raise ValueError("track kind must be rigid, local_compliant, two_layer, layered or modal")\n'
        '        if (kind == "layered") != bool(layers) and kind == "layered":\n'
        '            raise ValueError("layered track requires at least one layer below the rail")',
    ),
    (
        '        self.kind, self.rails, self.modal = kind, tuple(rails), modal',
        '        self.kind, self.rails, self.modal = kind, tuple(rails), modal\n'
        '        self.layers = tuple(layers)',
    ),
    (
        '        elif kind == "two_layer":\n'
        '            for rail in rails:',
        '        elif kind == "layered":\n'
        '            self.mass = np.array([\n'
        '                value\n'
        '                for rail in rails\n'
        '                for value in (rail.mass_y_kg, rail.mass_z_kg,\n'
        '                              *[item for layer in self.layers\n'
        '                                for item in (layer.mass_y_kg, layer.mass_z_kg)])\n'
        '            ])\n'
        '            self.state_names = [\n'
        '                f"{rail.id}_{label}_{axis}_m"\n'
        '                for rail in rails\n'
        '                for label in ["rail"] + [f"layer{k + 1}" for k in range(len(self.layers))]\n'
        '                for axis in ("y", "z")\n'
        '            ]\n'
        '        elif kind == "two_layer":\n'
        '            for rail in rails:',
    ),
    (
        '        if self.kind == "two_layer":\n'
        '            pos = 35 + 4 * rail_index\n'
        '            return float(q[pos]), float(q[pos + 1]), float(v[pos]), float(v[pos + 1])',
        '        if self.kind == "two_layer":\n'
        '            pos = 35 + 4 * rail_index\n'
        '            return float(q[pos]), float(q[pos + 1]), float(v[pos]), float(v[pos + 1])\n'
        '        if self.kind == "layered":\n'
        '            pos = 35 + 2 * (1 + len(self.layers)) * rail_index\n'
        '            return float(q[pos]), float(q[pos + 1]), float(v[pos]), float(v[pos + 1])',
    ),
    (
        '        if self.kind == "two_layer":\n'
        '            result = np.empty(self.dimension)',
        '        if self.kind == "layered":\n'
        '            result = np.zeros(self.dimension)\n'
        '            stride = 2 * (1 + len(self.layers))\n'
        '            for i, rail in enumerate(self.rails):\n'
        '                base = stride * i\n'
        '                springs = (rail.support, *self.layers)\n'
        '                for axis in (0, 1):\n'
        '                    for j, spring in enumerate(springs):\n'
        '                        here = base + 2 * j + axis\n'
        '                        below = here + 2 if j + 1 < len(springs) else None\n'
        '                        stiffness = spring.k_y_n_m if axis == 0 else spring.k_z_n_m\n'
        '                        damping = spring.c_y_n_s_m if axis == 0 else spring.c_z_n_s_m\n'
        '                        gap = q[35 + here] - (q[35 + below] if below is not None else 0.0)\n'
        '                        rate = v[35 + here] - (v[35 + below] if below is not None else 0.0)\n'
        '                        force = stiffness * gap + damping * rate\n'
        '                        result[here] -= force\n'
        '                        if below is not None:\n'
        '                            result[below] += force\n'
        '            return result\n'
        '        if self.kind == "two_layer":\n'
        '            result = np.empty(self.dimension)',
    ),
    (
        '        elif self.kind == "two_layer":\n'
        '            result[4 * rail_index] = -fy_n\n'
        '            result[4 * rail_index + 1] = -fz_n',
        '        elif self.kind == "two_layer":\n'
        '            result[4 * rail_index] = -fy_n\n'
        '            result[4 * rail_index + 1] = -fz_n\n'
        '        elif self.kind == "layered":\n'
        '            stride = 2 * (1 + len(self.layers))\n'
        '            result[stride * rail_index] = -fy_n\n'
        '            result[stride * rail_index + 1] = -fz_n',
    ),
    (
        '        if self.kind == "two_layer":\n'
        '            total = 0.0',
        '        if self.kind == "layered":\n'
        '            total = 0.0\n'
        '            stride = 2 * (1 + len(self.layers))\n'
        '            for i, rail in enumerate(self.rails):\n'
        '                base = stride * i\n'
        '                springs = (rail.support, *self.layers)\n'
        '                for axis in (0, 1):\n'
        '                    for j, spring in enumerate(springs):\n'
        '                        here = base + 2 * j + axis\n'
        '                        below = here + 2 if j + 1 < len(springs) else None\n'
        '                        stiffness = spring.k_y_n_m if axis == 0 else spring.k_z_n_m\n'
        '                        gap = q[35 + here] - (q[35 + below] if below is not None else 0.0)\n'
        '                        total += 0.5 * stiffness * gap ** 2\n'
        '            return float(total)\n'
        '        if self.kind == "two_layer":\n'
        '            total = 0.0',
    ),
    (
        '        if self.kind == "two_layer":\n'
        '            # The ground only carries what the ballast passes on.',
        '        if self.kind == "layered":\n'
        '            # The ground only carries what the bottom-most spring passes on.\n'
        '            stride = 2 * (1 + len(self.layers))\n'
        '            bottom = len(self.layers)\n'
        '            lateral = vertical = 0.0\n'
        '            for i, rail in enumerate(self.rails):\n'
        '                here = stride * i + 2 * bottom\n'
        '                spring = self.layers[-1]\n'
        '                lateral += spring.k_y_n_m * q[35 + here] + spring.c_y_n_s_m * v[35 + here]\n'
        '                vertical += (spring.k_z_n_m * q[35 + here + 1] +\n'
        '                             spring.c_z_n_s_m * v[35 + here + 1])\n'
        '            return lateral, vertical\n'
        '        if self.kind == "two_layer":\n'
        '            # The ground only carries what the ballast passes on.',
    ),
])

# ------------------------------------------------------- vehicle_solver.py
patch("vehicle_solver.py", [
    (
        '        self.track = TrackKernel(case.track_kind, case.rails, case.modal_track)',
        '        self.track = TrackKernel(case.track_kind, case.rails, case.modal_track, case.track_layers)',
    ),
    (
        '    elif case.track_kind == "modal":\n'
        '        indices += list(range(35, dynamics.dimension))',
        '    elif case.track_kind == "layered":\n'
        '        stride = 2 * (1 + len(case.track_layers))\n'
        '        for i in range(len(case.rails)):\n'
        '            indices += [35 + stride * i + 2 * j + 1\n'
        '                        for j in range(1 + len(case.track_layers))]\n'
        '    elif case.track_kind == "modal":\n'
        '        indices += list(range(35, dynamics.dimension))',
    ),
    (
        '        if case.track_kind in {"rigid", "local_compliant", "two_layer"}:',
        '        if case.track_kind in {"rigid", "local_compliant", "two_layer", "layered"}:',
    ),
    (
        '            elif case.track_kind == "two_layer":\n'
        '                for i in range(len(case.rails)):\n'
        '                    y_indices += [35 + 4 * i, 35 + 4 * i + 2]\n'
        '                    z_indices += [35 + 4 * i + 1, 35 + 4 * i + 3]',
        '            elif case.track_kind == "two_layer":\n'
        '                for i in range(len(case.rails)):\n'
        '                    y_indices += [35 + 4 * i, 35 + 4 * i + 2]\n'
        '                    z_indices += [35 + 4 * i + 1, 35 + 4 * i + 3]\n'
        '            elif case.track_kind == "layered":\n'
        '                stride = 2 * (1 + len(case.track_layers))\n'
        '                for i in range(len(case.rails)):\n'
        '                    for j in range(1 + len(case.track_layers)):\n'
        '                        y_indices.append(35 + stride * i + 2 * j)\n'
        '                        z_indices.append(35 + stride * i + 2 * j + 1)',
    ),
    (
        '    names += TrackKernel(case.track_kind, case.rails, case.modal_track).state_names',
        '    names += TrackKernel(case.track_kind, case.rails, case.modal_track,\n'
        '                         case.track_layers).state_names',
    ),
])
print("done")
