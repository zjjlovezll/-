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


def test_a_multi_leg_profile_is_carried_and_refused(tmp_path: Path) -> None:
    path = _derive(tmp_path, "legs", travel=2.0, profile={"legs": [
        {"speed_m_s": 2.0, "duration_s": 0.008},
        {"speed_m_s": 4.0, "duration_s": 0.007},
    ]})
    loaded = load_vehicle_case(path)
    assert loaded.speed_schedule is not None
    assert not loaded.speed_schedule.is_constant
    assert loaded.speed_schedule.duration_s == pytest.approx(0.015)
    with pytest.raises(SpeedScheduleError, match="not yet wired into the solver"):
        simulate_vehicle(loaded)
