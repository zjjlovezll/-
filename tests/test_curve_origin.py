"""The design line is straight before its tangent (B039)."""

from __future__ import annotations

import json

import numpy as np
import pytest

from velch import data_root
from velch.vehicle import load_vehicle_case
from velch.vehicle_solver import VehicleDynamics, _arc_parameter_m

# This module loads case_A_final_law.json from the corpus, so it needs the marker.
pytestmark = pytest.mark.corpus

RADIUS_M = 1100.0
X_START_M = 30.0
TANGENT_M = 50.578


def _case(tmp_path, **run):
    raw = json.loads((data_root.case_dir() / "case_A_final_law.json").read_text(encoding="utf-8"))
    raw["run"].update({"curve_radius_m": RADIUS_M, "curve_geometry": True,
                       "duration_s": 0.01, "output_step_s": 0.01, "x_start_m": X_START_M})
    raw["run"].update(run)
    raw.pop("initial_state", None)
    path = tmp_path / "curve_origin.json"
    path.write_text(json.dumps(raw, indent=1), encoding="utf-8")
    return path


def test_the_arc_parameter_is_zero_before_the_tangent():
    run = type("Run", (), {"curve_radius_m": RADIUS_M, "curve_origin_m": TANGENT_M,
                           "x_start_m": X_START_M})()
    assert _arc_parameter_m(run, 30.0) == 0.0
    assert _arc_parameter_m(run, 50.0) == 0.0
    assert _arc_parameter_m(run, TANGENT_M) == 0.0
    assert _arc_parameter_m(run, TANGENT_M + 10.0) == pytest.approx(10.0)


def test_without_an_origin_the_old_meaning_is_kept():
    run = type("Run", (), {"curve_radius_m": RADIUS_M, "curve_origin_m": None,
                           "x_start_m": X_START_M})()
    assert _arc_parameter_m(run, 40.0) == pytest.approx(10.0)
    # Signed, so a body behind the start stays on the same arc with the opposite heading: that is
    # how every pre-existing case was built and they must stay bit-identical.
    assert _arc_parameter_m(run, 20.0) == pytest.approx(-10.0)


def test_both_sides_agree_and_are_straight_before_the_tangent(tmp_path):
    case_path = _case(tmp_path, curve_origin_m=TANGENT_M)
    case = load_vehicle_case(case_path)
    dynamics = VehicleDynamics(case)
    placement = dynamics.track.placement
    assert placement is not None

    # Track side: zero lateral offset and zero slope everywhere up to the tangent.
    for mileage in (30.0, 40.0, TANGENT_M):
        lateral, _, slope = placement(0, mileage)
        assert lateral == 0.0
        assert slope == 0.0

    # After the tangent it is the same arc as before, measured from the tangent.
    lateral, _, slope = placement(0, TANGENT_M + 10.0)
    assert lateral == pytest.approx(10.0 ** 2 / (2.0 * RADIUS_M))
    assert slope == pytest.approx(10.0 / RADIUS_M)

    # Vehicle side: the front axle at x_start + 10 m is still 20.578 m before the tangent and must sit
    # on the straight line, not on the mirror arc the old formula produced.
    from velch.vehicle_solver import _body_offset_m

    body = dynamics.topology.wheelsets()[0]
    mileage = X_START_M + _body_offset_m(case, dynamics.topology, body, np.zeros(dynamics.dimension))
    assert _arc_parameter_m(case.run, mileage) == 0.0


def test_an_origin_without_a_radius_is_refused(tmp_path):
    case_path = _case(tmp_path, curve_origin_m=TANGENT_M)
    raw = json.loads(case_path.read_text(encoding="utf-8"))
    raw["run"]["curve_radius_m"] = None
    case_path.write_text(json.dumps(raw, indent=1), encoding="utf-8")
    with pytest.raises(ValueError) as error:
        load_vehicle_case(case_path)
    assert "needs curve_radius_m" in str(error.value)


def test_an_origin_with_cant_is_refused(tmp_path):
    case_path = _case(tmp_path, curve_origin_m=TANGENT_M, curve_cant_m=0.107)
    with pytest.raises(ValueError) as error:
        load_vehicle_case(case_path)
    assert "cannot be combined with curve_cant_m" in str(error.value)
