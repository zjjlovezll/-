"""The alignment is geometry, not force: it moves where the rails *are*, not how stiff they are.

``run.curve_radius_m`` on its own only adds a lateral body force — the equivalent-straight track.
That is defensible down to about R = 700 m (a 10 m footprint's yaw displacement must stay inside
the flange clearance), and wrong below it: at R = 350 m the far axle is 1.17 m to the side of the
near one and a straight rail model has to drag it there through the flange.

``run.curve_geometry`` hands ``y(s) = s^2 / (2R)`` and ``dy/ds = s / R`` to the track kernel so the
contact geometry follows the design line.  It is off by default, and these tests pin both halves of
that promise: off changes nothing, on moves the rail and its transverse velocity by the analytic
amount.
"""
from __future__ import annotations

import json
import pathlib

import pytest

from velch.model import load_case
from velch.vehicle import load_vehicle_case
from velch.vehicle_solver import VehicleDynamics

CASE = pathlib.Path(__file__).resolve().parents[1] / "examples" / "vehicle_v2" / "case.json"
RADIUS = 350.0
X_START = 30.0
SPEED = 22.2222


def _absolutise(node):
    """Make every profile reference absolute: a copied case still resolves from any folder."""
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "file" and isinstance(value, str):
                path = pathlib.Path(value)
                if not path.is_absolute():
                    node[key] = str((CASE.parent / path).resolve())
            else:
                _absolutise(value)
    elif isinstance(node, list):
        for item in node:
            _absolutise(item)
    return node


def _with_run(tmp_path: pathlib.Path, name: str, **overrides) -> pathlib.Path:
    raw = json.loads(CASE.read_text(encoding="utf-8"))
    _absolutise(raw)
    raw["run"]["x_start_m"] = X_START
    raw["run"]["duration_s"] = 0.01
    raw["run"].update(overrides)
    raw.setdefault("meta", {})
    raw["case_id"] = f"curve_{name}"
    target = tmp_path / f"case_{name}.json"
    target.write_text(json.dumps(raw, indent=2, ensure_ascii=False), encoding="utf-8")
    return target


def _dynamics(path: pathlib.Path) -> VehicleDynamics:
    loaded = load_vehicle_case(path)
    return VehicleDynamics(loaded, contact_workers=1)


def _state(dynamics: VehicleDynamics):
    import numpy as np

    q = np.zeros(dynamics.dimension)
    v = np.zeros(dynamics.dimension)
    return q, v


def test_a_straight_case_has_no_placement(tmp_path):
    dynamics = _dynamics(_with_run(tmp_path, "straight"))
    assert dynamics.track.placement is None
    q, v = _state(dynamics)
    for rail_index in (0, 3):
        y, z, vy, vz = dynamics.track.local_state(q, v, rail_index, X_START + 5.0, SPEED)
        assert (y, z, vy, vz) == (0.0, 0.0, 0.0, 0.0)


def test_a_radius_without_curve_geometry_stays_equivalent_straight(tmp_path):
    dynamics = _dynamics(_with_run(tmp_path, "equivalent", curve_radius_m=RADIUS))
    assert dynamics.track.placement is None, "the body-force curve must not move the geometry"


def test_curve_geometry_moves_the_rail_and_its_transverse_velocity(tmp_path):
    dynamics = _dynamics(_with_run(tmp_path, "geometry", curve_radius_m=RADIUS,
                                   curve_geometry=True))
    assert dynamics.track.placement is not None
    q, v = _state(dynamics)
    gauge = 2.0 * abs(float(dynamics.case.wheels[0].lateral_offset_m))
    for s in (0.0, 2.05, 10.0):
        y, z, vy, vz = dynamics.track.local_state(q, v, 0, X_START + s, SPEED)
        assert y == pytest.approx(s * s / (2.0 * RADIUS), abs=1e-12)
        assert vy == pytest.approx(SPEED * s / RADIUS, rel=1e-12)
        # No cant in this case, so the two rails sit at the same height.
        assert z == pytest.approx(0.0, abs=1e-15)
        assert vz == pytest.approx(0.0, abs=1e-15)
        assert gauge > 1.0


def test_cant_raises_the_outer_rail_by_half_the_gauge(tmp_path):
    cant = 0.06
    dynamics = _dynamics(_with_run(tmp_path, "cant", curve_radius_m=RADIUS,
                                   curve_cant_m=cant, curve_geometry=True))
    q, v = _state(dynamics)
    rails = dynamics.case.rails
    right = next(i for i, rail in enumerate(rails) if "right" in str(rail.id).lower())
    left = next(i for i, rail in enumerate(rails) if "left" in str(rail.id).lower())
    half_gauge = abs(float(dynamics.case.wheels[0].lateral_offset_m))
    expected = half_gauge * (cant / (2.0 * half_gauge))
    _, right_z, _, _ = dynamics.track.local_state(q, v, right, X_START, SPEED)
    _, left_z, _, _ = dynamics.track.local_state(q, v, left, X_START, SPEED)
    assert right_z == pytest.approx(expected, rel=1e-12)
    assert left_z == pytest.approx(-expected, rel=1e-12)
    assert right_z - left_z == pytest.approx(cant, rel=1e-12), "the difference *is* the cant"


def test_the_elastic_displacement_is_added_on_top_of_the_alignment(tmp_path):
    """``q`` stays the elastic part, so potential and internal force see the same numbers."""
    import numpy as np

    dynamics = _dynamics(_with_run(tmp_path, "offset", curve_radius_m=RADIUS,
                                   curve_geometry=True))
    q, v = _state(dynamics)
    # Rail 0's lateral coordinate lives at the kernel's own offset, not at q[0].
    index = dynamics.track.offset
    q[index] = 3.0e-4
    v[index] = 1.0e-3
    y, _, vy, _ = dynamics.track.local_state(q, v, 0, X_START + 1.0, SPEED)
    assert y == pytest.approx(3.0e-4 + 1.0 / (2.0 * RADIUS), abs=1e-12)
    assert vy == pytest.approx(1.0e-3 + SPEED / RADIUS, rel=1e-9)
    assert np.isfinite(dynamics.track.internal_force(q, v)).all()
