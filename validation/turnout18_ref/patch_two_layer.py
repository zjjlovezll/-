"""Add a two-layer (rail + sleeper + ballast) track kernel to Velch.

S1-f proved a single lumped track DOF cannot hold both the frog peak and the
30-60 Hz band: one resonance cannot be tuned to do two jobs. The physical chain is

    rail (m_r) --(k_pad, c_pad)-- sleeper (m_s) --(k_ball, c_ball)-- ground

per rail and per axis. Eigenfrequencies: in phase ~32 Hz, out of phase ~190 Hz,
which are exactly the two bands the reference solver occupies.

DOF order per rail (starting at 35): (y_rail, z_rail, y_sleeper, z_sleeper).
Every new field on LinearSupport has a default, so existing cases are unaffected.
"""

from __future__ import annotations

import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2] / "src" / "velch"


def patch(name: str, pairs: list[tuple[str, str]]) -> None:
    path = ROOT / name
    text = path.read_text(encoding="utf-8")
    for old, new in pairs:
        if old not in text:
            raise SystemExit(f"{name}: anchor missing -> {old.splitlines()[0][:80]!r}")
        text = text.replace(old, new, 1)
    path.write_text(text, encoding="utf-8")
    print(f"patched {name}")


patch("model.py", [(
    '''class LinearSupport:
    k_y_n_m: float
    c_y_n_s_m: float
    k_z_n_m: float
    c_z_n_s_m: float

    def __post_init__(self) -> None:
        for name in ("k_y_n_m", "c_y_n_s_m", "k_z_n_m", "c_z_n_s_m"):
            _finite(name, getattr(self, name), nonnegative=True)''',
    '''class LinearSupport:
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
            _finite(name, getattr(self, name), nonnegative=True)''',
)])

patch("vehicle.py", [
    (
        '        if self.track_kind not in {"rigid", "local_compliant", "modal"}:\n'
        '            raise ValueError("unknown track dynamics kind")',
        '        if self.track_kind not in {"rigid", "local_compliant", "two_layer", "modal"}:\n'
        '            raise ValueError("unknown track dynamics kind")',
    ),
    (
        '        n = 35 + (2 * len(self.rails) if self.track_kind == "local_compliant"\n'
        '                  else self.modal_track.mode_count if self.modal_track else 0)',
        '        n = 35 + (2 * len(self.rails) if self.track_kind == "local_compliant"\n'
        '                  else 4 * len(self.rails) if self.track_kind == "two_layer"\n'
        '                  else self.modal_track.mode_count if self.modal_track else 0)',
    ),
    (
        '    if track_kind not in {"rigid", "local_compliant", "modal"}:\n'
        '        raise ValueError("track_dynamics.kind must be rigid, local_compliant or modal")',
        '    if track_kind not in {"rigid", "local_compliant", "two_layer", "modal"}:\n'
        '        raise ValueError("track_dynamics.kind must be rigid, local_compliant, two_layer or modal")',
    ),
    (
        '    n = 35 + (2 * len(rails) if track_kind == "local_compliant"\n'
        '              else modal_track.mode_count if modal_track else 0)',
        '    n = 35 + (2 * len(rails) if track_kind == "local_compliant"\n'
        '              else 4 * len(rails) if track_kind == "two_layer"\n'
        '              else modal_track.mode_count if modal_track else 0)',
    ),
])

patch("vehicle_solver.py", [
    (
        '    if case.track_kind == "local_compliant":\n'
        '        indices += [35 + 2 * i + 1 for i in range(len(case.rails))]',
        '    if case.track_kind == "local_compliant":\n'
        '        indices += [35 + 2 * i + 1 for i in range(len(case.rails))]\n'
        '    elif case.track_kind == "two_layer":\n'
        '        for i in range(len(case.rails)):\n'
        '            indices += [35 + 4 * i + 1, 35 + 4 * i + 3]',
    ),
    (
        '        if case.track_kind in {"rigid", "local_compliant"}:\n'
        '            y_indices = [5 * i for i in range(4)] + [20, 25, 30]\n'
        '            z_indices = [5 * i + 1 for i in range(4)] + [21, 26, 31]\n'
        '            if case.track_kind == "local_compliant":\n'
        '                y_indices += [35 + 2 * i for i in range(len(case.rails))]\n'
        '                z_indices += [35 + 2 * i + 1 for i in range(len(case.rails))]',
        '        if case.track_kind in {"rigid", "local_compliant", "two_layer"}:\n'
        '            y_indices = [5 * i for i in range(4)] + [20, 25, 30]\n'
        '            z_indices = [5 * i + 1 for i in range(4)] + [21, 26, 31]\n'
        '            if case.track_kind == "local_compliant":\n'
        '                y_indices += [35 + 2 * i for i in range(len(case.rails))]\n'
        '                z_indices += [35 + 2 * i + 1 for i in range(len(case.rails))]\n'
        '            elif case.track_kind == "two_layer":\n'
        '                for i in range(len(case.rails)):\n'
        '                    y_indices += [35 + 4 * i, 35 + 4 * i + 2]\n'
        '                    z_indices += [35 + 4 * i + 1, 35 + 4 * i + 3]',
    ),
])

patch("track_models.py", [
    (
        '        if kind not in {"rigid", "local_compliant", "modal"}:\n'
        '            raise ValueError("track kind must be rigid, local_compliant or modal")',
        '        if kind not in {"rigid", "local_compliant", "two_layer", "modal"}:\n'
        '            raise ValueError("track kind must be rigid, local_compliant, two_layer or modal")',
    ),
    (
        '        elif kind == "local_compliant":\n'
        '            self.mass = np.array([value for rail in rails for value in (rail.mass_y_kg, rail.mass_z_kg)])\n'
        '            self.state_names = [f"{rail.id}_{axis}_m" for rail in rails for axis in ("y", "z")]',
        '        elif kind == "local_compliant":\n'
        '            self.mass = np.array([value for rail in rails for value in (rail.mass_y_kg, rail.mass_z_kg)])\n'
        '            self.state_names = [f"{rail.id}_{axis}_m" for rail in rails for axis in ("y", "z")]\n'
        '        elif kind == "two_layer":\n'
        '            for rail in rails:\n'
        '                if rail.support.sleeper_mass_y_kg <= 0.0 or rail.support.sleeper_mass_z_kg <= 0.0:\n'
        '                    raise ValueError("two_layer track requires a positive sleeper mass")\n'
        '                if rail.support.ballast_k_z_n_m <= 0.0:\n'
        '                    raise ValueError("two_layer track requires a positive ballast stiffness")\n'
        '            self.mass = np.array([\n'
        '                value\n'
        '                for rail in rails\n'
        '                for value in (rail.mass_y_kg, rail.mass_z_kg,\n'
        '                              rail.support.sleeper_mass_y_kg,\n'
        '                              rail.support.sleeper_mass_z_kg)\n'
        '            ])\n'
        '            self.state_names = [\n'
        '                f"{rail.id}_{layer}_{axis}_m"\n'
        '                for rail in rails\n'
        '                for layer in ("rail", "sleeper")\n'
        '                for axis in ("y", "z")\n'
        '            ]',
    ),
    (
        '        if self.kind == "local_compliant":\n'
        '            pos = 35 + 2 * rail_index\n'
        '            return float(q[pos]), float(q[pos + 1]), float(v[pos]), float(v[pos + 1])',
        '        if self.kind == "local_compliant":\n'
        '            pos = 35 + 2 * rail_index\n'
        '            return float(q[pos]), float(q[pos + 1]), float(v[pos]), float(v[pos + 1])\n'
        '        if self.kind == "two_layer":\n'
        '            pos = 35 + 4 * rail_index\n'
        '            return float(q[pos]), float(q[pos + 1]), float(v[pos]), float(v[pos + 1])',
    ),
    (
        '        assert self.modal is not None\n'
        '        return -self.modal.stiffness_n_m * q[35:] - self.modal.damping_n_s_m * v[35:]',
        '        if self.kind == "two_layer":\n'
        '            result = np.empty(self.dimension)\n'
        '            for i, rail in enumerate(self.rails):\n'
        '                base = 35 + 4 * i\n'
        '                for axis, pad_k, pad_c, ballast_k, ballast_c in (\n'
        '                        (0, rail.support.k_y_n_m, rail.support.c_y_n_s_m,\n'
        '                         rail.support.ballast_k_y_n_m, rail.support.ballast_c_y_n_s_m),\n'
        '                        (1, rail.support.k_z_n_m, rail.support.c_z_n_s_m,\n'
        '                         rail.support.ballast_k_z_n_m, rail.support.ballast_c_z_n_s_m)):\n'
        '                    gap = q[base + axis] - q[base + 2 + axis]\n'
        '                    rate = v[base + axis] - v[base + 2 + axis]\n'
        '                    pad = pad_k * gap + pad_c * rate\n'
        '                    result[base + axis] = -pad\n'
        '                    result[base + 2 + axis] = (pad -\n'
        '                        ballast_k * q[base + 2 + axis] -\n'
        '                        ballast_c * v[base + 2 + axis])\n'
        '            return result\n'
        '        assert self.modal is not None\n'
        '        return -self.modal.stiffness_n_m * q[35:] - self.modal.damping_n_s_m * v[35:]',
    ),
    (
        '        if self.kind == "local_compliant":\n'
        '            result[2 * rail_index] = -fy_n\n'
        '            result[2 * rail_index + 1] = -fz_n',
        '        if self.kind == "local_compliant":\n'
        '            result[2 * rail_index] = -fy_n\n'
        '            result[2 * rail_index + 1] = -fz_n\n'
        '        elif self.kind == "two_layer":\n'
        '            result[4 * rail_index] = -fy_n\n'
        '            result[4 * rail_index + 1] = -fz_n',
    ),
    (
        '        if self.kind == "modal":\n'
        '            assert self.modal is not None\n'
        '            return float(0.5 * np.dot(self.modal.stiffness_n_m, q[35:] ** 2))\n'
        '        return 0.0',
        '        if self.kind == "two_layer":\n'
        '            total = 0.0\n'
        '            for i, rail in enumerate(self.rails):\n'
        '                base = 35 + 4 * i\n'
        '                for axis, pad_k, ballast_k in (\n'
        '                        (0, rail.support.k_y_n_m, rail.support.ballast_k_y_n_m),\n'
        '                        (1, rail.support.k_z_n_m, rail.support.ballast_k_z_n_m)):\n'
        '                    gap = q[base + axis] - q[base + 2 + axis]\n'
        '                    total += 0.5 * pad_k * gap ** 2\n'
        '                    total += 0.5 * ballast_k * q[base + 2 + axis] ** 2\n'
        '            return float(total)\n'
        '        if self.kind == "modal":\n'
        '            assert self.modal is not None\n'
        '            return float(0.5 * np.dot(self.modal.stiffness_n_m, q[35:] ** 2))\n'
        '        return 0.0',
    ),
    (
        '                        for i, rail in enumerate(self.rails)))\n'
        '        return None',
        '                        for i, rail in enumerate(self.rails)))\n'
        '        if self.kind == "two_layer":\n'
        '            # The ground only carries what the ballast passes on.\n'
        '            lateral = vertical = 0.0\n'
        '            for i, rail in enumerate(self.rails):\n'
        '                base = 35 + 4 * i\n'
        '                lateral += (rail.support.ballast_k_y_n_m * q[base + 2] +\n'
        '                            rail.support.ballast_c_y_n_s_m * v[base + 2])\n'
        '                vertical += (rail.support.ballast_k_z_n_m * q[base + 3] +\n'
        '                             rail.support.ballast_c_z_n_s_m * v[base + 3])\n'
        '            return lateral, vertical\n'
        '        return None',
    ),
])
print("done")
