"""A constant speed profile is the travel speed; a multi-leg one is refused, not guessed.

The equality test is the one that matters: the profile is supposed to be a *single source of
truth*, so the case that carries ``travel_speed_m_s: 99`` plus a constant profile at 2.0 m/s
must produce exactly the bytes of the case that carries 2.0 m/s and no profile at all.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from velch.speed import SpeedScheduleError
from velch.vehicle import load_vehicle_case
from velch.vehicle_solver import save_vehicle_result, simulate_vehicle

REPO = Path(__file__).resolve().parents[1]
CASE = REPO / "examples" / "vehicle_v2" / "case.json"
DURATION_S = 0.015


def _derive(tmp_path: Path, name: str, *, travel: float, profile: dict | None) -> Path:
    raw = json.loads(CASE.read_text(encoding="utf-8"))
    raw["run"]["duration_s"] = DURATION_S
    raw["vehicle"]["travel_speed_m_s"] = travel
    if profile is not None:
        raw["run"]["speed_profile"] = profile
    # the derived file lives elsewhere, so its relative profile names must become absolute
    for item in raw.get("wheels", []):
        spec = item.get("profile") or {}
        if "file" in spec and not Path(spec["file"]).is_absolute():
            spec["file"] = str((CASE.parent / spec["file"]).resolve())
    for template in raw.get("rail_templates", []):
        for station in template.get("stations", []):
            spec = station.get("profile") or {}
            if "file" in spec and not Path(spec["file"]).is_absolute():
                spec["file"] = str((CASE.parent / spec["file"]).resolve())
    target = tmp_path / f"{name}.json"
    target.write_text(json.dumps(raw, indent=2, ensure_ascii=False), encoding="utf-8")
    return target


def _run(case_path: Path, out: Path) -> tuple[str, str]:
    loaded = load_vehicle_case(case_path)
    result = simulate_vehicle(loaded)
    history_path, manifest_path = save_vehicle_result(loaded, result, out)
    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    digest = hashlib.sha256(Path(history_path).read_bytes()).hexdigest()
    return digest, manifest["summary"]["result_status"]


def test_a_constant_profile_overrides_the_travel_speed_it_replaces(tmp_path: Path) -> None:
    plain = _derive(tmp_path, "plain", travel=2.0, profile=None)
    profiled = _derive(tmp_path, "profiled", travel=99.0,
                       profile={"constant": {"speed_m_s": 2.0}})

    assert load_vehicle_case(profiled).vehicle.travel_speed_m_s == pytest.approx(2.0)
    assert load_vehicle_case(profiled).speed_schedule.is_constant

    first_hash, first_status = _run(plain, tmp_path / "out_plain")
    second_hash, second_status = _run(profiled, tmp_path / "out_profiled")
    assert first_status == second_status == "numerically_checked"
    assert first_hash == second_hash, "a constant profile must not change a single byte"


def test_a_multi_leg_profile_turns_the_spin_servo_on(tmp_path: Path) -> None:
    """A varying speed is allowed only because the spin now follows it.

    The refusal that used to live here was a placeholder: it existed because the spin was
    integrated from the contact force while the creep reference was a single number.  The servo
    removes that reason, so the assertion moves to "the servo is on" — and the gate that
    measures how well it does is checked in ``tests/test_spin_control.py``.
    """

    from velch.vehicle_solver import VehicleDynamics

    path = _derive(tmp_path, "legs", travel=2.0, profile={"legs": [
        {"speed_m_s": 2.0, "duration_s": 0.008},
        {"speed_m_s": 4.0, "duration_s": 0.007},
    ]})
    loaded = load_vehicle_case(path)
    assert loaded.speed_schedule is not None
    assert not loaded.speed_schedule.is_constant
    assert loaded.speed_schedule.duration_s == pytest.approx(0.015)
    dynamics = VehicleDynamics(loaded)
    try:
        assert dynamics.spin_control is True
    finally:
        dynamics.close()


def test_x_at_is_the_literal_it_replaces(tmp_path):
    """``x(t)`` must equal ``x_start + v*t`` to the last bit, for both directions.

    The whole point of routing mileage through the schedule is that a constant profile is a
    pass-through.  If the helper rounded, reordered the product or added the start point first,
    every geometry lookup would move by an ulp and the frozen baselines would drift for no
    physical reason.
    """

    from velch.vehicle_solver import VehicleDynamics

    for speed in (2.0, -2.0, 97.2222):
        case = _derive(tmp_path, f"x_{speed:.4f}.json", travel=speed, profile=None)
        loaded = load_vehicle_case(case)
        dynamics = VehicleDynamics(loaded)
        for t_s in (0.0, 1.0e-5, 0.0075, 0.015):
            literal = loaded.run.x_start_m + loaded.vehicle.travel_speed_m_s * t_s
            assert dynamics.x_at(t_s) == literal
            assert dynamics.speed_at(t_s) == loaded.vehicle.travel_speed_m_s


def test_the_force_path_reads_the_schedule_not_the_field(tmp_path):
    """A constant profile wins over the field even when the two disagree.

    ``travel_speed_m_s`` is 99 m/s in this case and the profile says 2 m/s, so the mileage has
    to advance at 2 m/s.  Reading the field anywhere in the force path would make the two
    numbers disagree and no gate would notice.
    """

    from velch.vehicle_solver import VehicleDynamics

    case = _derive(tmp_path, "override.json", travel=99.0,
                   profile={"constant": {"speed_m_s": 2.0}})
    loaded = load_vehicle_case(case)
    assert loaded.vehicle.travel_speed_m_s == pytest.approx(2.0)
    dynamics = VehicleDynamics(loaded)
    assert dynamics.speed_at(0.010) == pytest.approx(2.0)
    assert dynamics.x_at(0.010) == pytest.approx(loaded.run.x_start_m + 0.02)
