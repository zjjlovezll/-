"""A varying speed must be tracked by the wheel spin, and the gate must say so."""

from __future__ import annotations

import json
import pathlib

import pytest

from velch.vehicle import load_vehicle_case
from velch.vehicle_solver import simulate_vehicle

REPO = pathlib.Path(__file__).resolve().parents[1]
CASE = REPO / "examples" / "vehicle_v2" / "case.json"


def _derive(tmp_path, name, *, travel, profile, duration):
    raw = json.loads(CASE.read_text(encoding="utf-8"))
    raw["run"]["duration_s"] = duration
    raw["vehicle"]["travel_speed_m_s"] = travel
    if profile is not None:
        raw["run"]["speed_profile"] = profile
    for item in raw.get("wheels", []):
        spec = item.get("profile") or {}
        if "file" in spec and not pathlib.Path(spec["file"]).is_absolute():
            spec["file"] = str((CASE.parent / spec["file"]).resolve())
    for template in raw.get("rail_templates", []):
        for station in template.get("stations", []):
            spec = station.get("profile") or {}
            if "file" in spec and not pathlib.Path(spec["file"]).is_absolute():
                spec["file"] = str((CASE.parent / spec["file"]).resolve())
    path = tmp_path / f"{name}.json"
    path.write_text(json.dumps(raw, indent=2), encoding="utf-8")
    return path


def test_a_constant_profile_adds_no_gate_and_no_metric(tmp_path):
    """The seven-gate set must not grow for a constant profile.

    ``spin_tracking`` exists because a varying speed needs a servo; a constant profile has no
    servo and no lag, so reporting ``None`` and leaving the gate out is what keeps every archived
    manifest comparable.
    """

    case = load_vehicle_case(_derive(tmp_path, "constant", travel=2.0,
                                     profile={"constant": {"speed_m_s": 2.0}}, duration=0.01))
    result = simulate_vehicle(case)
    assert "spin_tracking" not in result.summary["gates"]
    assert result.summary["spin_tracking_max_m"] is None
    assert len(result.summary["gates"]) == 7


def test_a_ramp_is_tracked_within_the_gate(tmp_path):
    """A 2 -> 4 m/s ramp: the spin must follow inside 0.5 mm/s of slip at the tread.

    The servo gain is the wheelset inertia, so the time constant is 2 ms; over a 10 ms ramp the
    residual lag is ``v_dot * tau = 200 * 0.002 = 0.4 m/s`` of *angular* lag, which at 0.43 m is
    a 170 mm/s tread slip and would fail.  That is the honest bound: the gate is 0.5 mm/s, so the
    servo has to be much faster than the ramp -- hence ``SPIN_TIME_CONSTANT_S`` is 2 ms and the
    test ramp is deliberately at the edge of what the gate tolerates.
    """

    case = load_vehicle_case(_derive(tmp_path, "ramp", travel=2.0, duration=0.02, profile={"legs": [
        {"speed_m_s": 2.0, "duration_s": 0.010},
        {"speed_m_s": 4.0, "duration_s": 0.010},
    ]}))
    result = simulate_vehicle(case)
    summary = result.summary
    assert "spin_tracking" in summary["gates"]
    assert summary["spin_tracking_max_m"] is not None
    print("slip", summary["spin_tracking_max_m"], "relative", summary["spin_tracking_relative"],
          "status", summary["result_status"])
    assert summary["spin_tracking_relative"] <= 0.01
