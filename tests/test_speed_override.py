"""A case that declares a constant speed profile must not be renamed without being re-timed.

B052: three "different" speeds (60/80/100 km/h) of the same case produced one onset time, because the
loader lets ``run.speed_profile`` win over ``vehicle.travel_speed_m_s`` and s99 only overrode the vehicle.
``apply_speed`` now rewrites both and records the profile speed, so a run cannot be labelled at a speed
its physics does not use.
"""

from __future__ import annotations

import dataclasses
import json
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import s99_run_archive as archive  # noqa: E402
from velch.vehicle import load_vehicle_case  # noqa: E402

CASE = ROOT / "vehicles" / "turnouts" / "CN60-1100-1_18" / "cases" / "straight_one_set.json"


@pytest.fixture(scope="module")
def case():
    return load_vehicle_case(CASE)


def test_the_constant_profile_is_rewritten_with_the_vehicle(case) -> None:
    assert case.run.speed_profile == {"constant": {"speed_kmh": 80.0}}
    slower = archive.apply_speed(case, 60.0)
    assert slower.run.speed_profile == {"constant": {"speed_kmh": 60.0}}
    assert slower.vehicle.travel_speed_m_s == pytest.approx(60.0 / 3.6)
    # the original object is untouched: apply_speed is a pure rebuild
    assert case.run.speed_profile == {"constant": {"speed_kmh": 80.0}}
    assert case.vehicle.travel_speed_m_s == pytest.approx(80.0 / 3.6)


def test_both_speeds_agree_after_the_override(case) -> None:
    faster = archive.apply_speed(case, 100.0)
    profile = faster.run.speed_profile["constant"]["speed_kmh"]
    assert profile == pytest.approx(faster.vehicle.travel_speed_m_s * 3.6)
    assert profile == pytest.approx(100.0)


def test_a_multi_leg_profile_is_refused_rather_than_flattened(case) -> None:
    legs = dataclasses.replace(
        case.run,
        speed_profile={"legs": [{"speed_kmh": 60.0, "duration_s": 0.5},
                                {"speed_kmh": 80.0, "duration_s": 0.5}]},
    )
    with pytest.raises(SystemExit) as excinfo:
        archive.apply_speed(dataclasses.replace(case, run=legs), 100.0)
    assert "multi-leg" in str(excinfo.value)


def test_an_archived_run_records_the_profile_speed(case) -> None:
    """The runs that matter for B052 are the archived ones: their meta has to name the profile speed."""

    runs = ROOT.parent / "scratch" / "runs"
    if not runs.is_dir():
        pytest.skip("no archive on this machine")
    checked = 0
    for meta_path in sorted(runs.glob("*/meta.json")):
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        if "profile_speed_kmh" not in meta:
            continue
        checked += 1
        assert meta["profile_speed_kmh"] == pytest.approx(meta["speed_kmh"]), meta_path
        if checked >= 3:
            break
    if checked == 0:
        pytest.skip("no archive written after B052 yet")


def test_the_materialised_schedule_is_rebuilt_too(case) -> None:
    """B052 has a second layer: the loader puts a SpeedSchedule on the case and the solver prefers it."""

    from velch.vehicle_solver import VehicleDynamics

    start = float(case.run.x_start_m)
    raw = VehicleDynamics(case)
    assert case.speed_schedule is not None
    # the declared 80 km/h wins over the vehicle block: x(0.819 s) = start + 22.222*0.819
    assert raw.x_at(0.819) == pytest.approx(start + 22.22222222222222 * 0.819, abs=1e-3)

    slower = archive.apply_speed(case, 60.0)
    fixed = VehicleDynamics(slower)
    assert slower.speed_schedule.legs[0].speed_m_s == pytest.approx(60.0 / 3.6)
    # and the rebuilt one drives it at 60: start + 16.667*0.819, i.e. 4.55 m behind
    assert fixed.x_at(0.819) == pytest.approx(start + (60.0 / 3.6) * 0.819, abs=1e-3)
    assert raw.x_at(0.819) - fixed.x_at(0.819) == pytest.approx(4.55, abs=2e-2)
