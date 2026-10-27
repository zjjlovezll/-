"""The axle box needs a rotational restraint, and a test that can see its absence.

Simpack attaches each axle box with ``joint.type = 2`` — a rotating arm.  The node
table only had translational bushings there, so the box kept a combination in which
it translates *and* rotates by exactly the amount that stretches no spring: a mode
with k = 0 and zeta = 0 at 13.094 Hz.  A 9 m/s^2 tone sat in every axle-box
acceleration channel from the first instant and never decayed, which is larger than
any irregularity signal these experiments measure.

These tests pin both halves: the elements are present and attached where the arm
is, and the linearised system no longer contains an undamped mode near 13 Hz.  The
second half deletes the elements again, so it fails the way the defect did rather
than merely asserting that a file contains a key.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pytest

from velch.data_root import case_dir
from velch.vehicle import load_vehicle_case
from velch.vehicle_solver import VehicleDynamics, _static_vertical_equilibrium
from velch.jacobian import JacobianAssembler

pytestmark = pytest.mark.corpus

REPO = Path(__file__).resolve().parents[1]
MODEL = REPO / "vehicles" / "CRH380A_M_axlebox.json"
BASE_CASE = "case_frog_N_strip05.json"
WINDOW_HZ = (12.5, 13.7)
DAMPING_FLOOR = 0.003


def _absolute(node, base: Path):
    if isinstance(node, dict):
        return {key: _absolute(value, base) for key, value in node.items()}
    if isinstance(node, list):
        return [_absolute(value, base) for value in node]
    if isinstance(node, str) and node.lower().endswith((".csv", ".txt", ".prr")):
        path = Path(node)
        return str(path if path.is_absolute() else (base / path).resolve())
    return node


def _case_with_axle_boxes(tmp_path: Path, *, drop_restraint: bool = False) -> Path:
    """A case that uses the axle-box vehicle, optionally with the restraint deleted."""
    source = case_dir() / BASE_CASE
    base = source.parent
    document = _absolute(json.loads(source.read_text(encoding="utf-8")), base)
    document.pop("vehicle", None)
    document.pop("topology", None)
    document["vehicle_ref"] = "CRH380A_M_axlebox"
    document["case_id"] = "case_axlebox_restraint"
    document.pop("initial_state", None)
    if drop_restraint:
        model = json.loads(MODEL.read_text(encoding="utf-8"))
        model["topology"]["elements"] = [
            element
            for element in model["topology"]["elements"]
            if not element["name"].startswith("box_roll_")
        ]
        stripped = tmp_path / "CRH380A_M_axlebox_without_roll.json"
        stripped.write_text(json.dumps(model, ensure_ascii=False), encoding="utf-8")
        document["vehicle_ref"] = "CRH380A_M_axlebox"
        case = tmp_path / "case_without_restraint.json"
        case.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
        return _inline_vehicle(case, stripped, tmp_path)
    case = tmp_path / "case_with_restraint.json"
    case.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
    return case


def _inline_vehicle(case: Path, model: Path, tmp_path: Path) -> Path:
    """Turn a vehicle reference into an inline copy so a doctored model can be used."""
    document = json.loads(case.read_text(encoding="utf-8"))
    doctored = json.loads(model.read_text(encoding="utf-8"))
    document.pop("vehicle_ref", None)
    document["vehicle"] = doctored["vehicle"]
    document["topology"] = doctored["topology"]
    inline = tmp_path / "case_inline.json"
    inline.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
    return inline


def _modes(case_path: Path) -> list[tuple[float, float]]:
    case = load_vehicle_case(case_path)
    dynamics = VehicleDynamics(case)
    q = np.array(case.initial_q, float)
    v = np.zeros_like(q)
    q, _ = _static_vertical_equilibrium(case, dynamics, q, v)
    q_block, v_block = JacobianAssembler(dynamics).blocks(0.0, q, v)
    n = dynamics.dimension
    state = np.zeros((2 * n, 2 * n))
    state[:n, n:] = np.eye(n)
    state[n:, :n] = q_block
    state[n:, n:] = v_block
    values = np.linalg.eigvals(state)
    return [
        (abs(value) / (2.0 * math.pi), -value.real / abs(value))
        for value in values
        if value.imag > 5.0
    ]


def _lowest_damping(modes, window: tuple[float, float]) -> float:
    inside = [zeta for frequency, zeta in modes if window[0] <= frequency <= window[1]]
    assert inside, f"no mode between {window[0]} and {window[1]} Hz"
    return min(inside)


def test_the_arm_joint_carries_a_roll_restraint_on_every_box():
    raw = json.loads(MODEL.read_text(encoding="utf-8"))
    elements = {element["name"]: element for element in raw["topology"]["elements"]}
    for axle in (1, 2, 3, 4):
        for side in ("L", "R"):
            element = elements[f"box_roll_{axle}{side}"]
            assert element["kind"] == "torsional"
            assert element["axis"] == "roll"
            assert element["stiffness"] > 0.0
            assert element["damping"] > 0.0
            assert element["from"]["body"] == f"axlebox{axle}{side}"
            assert element["to"]["body"] == f"bogie{(axle - 1) // 2 + 1}"


def test_the_box_vehicle_has_no_undamped_mode_near_thirteen_hertz(tmp_path):
    modes = _modes(_case_with_axle_boxes(tmp_path))
    assert _lowest_damping(modes, WINDOW_HZ) > DAMPING_FLOOR


def test_removing_the_restraint_brings_the_undamped_mode_back(tmp_path):
    """The test above must be able to fail; this is the state it was written against."""
    modes = _modes(_case_with_axle_boxes(tmp_path, drop_restraint=True))
    assert _lowest_damping(modes, WINDOW_HZ) < 1e-3


def test_the_longitudinal_vehicle_carries_the_same_restraint():
    raw = json.loads((REPO / "vehicles" / "CRH380A_M_axlebox_x.json").read_text(encoding="utf-8"))
    names = {element["name"] for element in raw["topology"]["elements"]}
    for axle in (1, 2, 3, 4):
        for side in ("L", "R"):
            assert f"box_roll_{axle}{side}" in names
