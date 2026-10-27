"""The mileage written to disk must be the mileage the geometry was sampled at."""

from __future__ import annotations

import json
import pathlib

import numpy as np
import pytest

from velch.io.history import read_history
from velch.vehicle import load_vehicle_case
from velch.vehicle_solver import save_vehicle_result, simulate_vehicle, travel_mileage_m

REPO = pathlib.Path(__file__).resolve().parents[1]
CASE = REPO / "examples" / "vehicle_v2" / "case.json"


def _derive(tmp_path, name, *, duration, profile):
    raw = json.loads(CASE.read_text(encoding="utf-8"))
    raw["run"]["duration_s"] = duration
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


def test_the_written_mileage_is_the_sampled_mileage(tmp_path):
    """Two legs, two speeds: every written mileage must equal ``travel_mileage_m``.

    A run whose force path uses ``x_at`` while its file reports ``v*t`` produces a trail that
    does not belong to the geometry that was used -- and no gate can see it, because both are
    self-consistent.  This compares the artefact with the analytic distance.
    """

    case = load_vehicle_case(_derive(tmp_path, "two_legs", duration=0.02, profile={"legs": [
        {"speed_kmh": 80.0, "duration_s": 0.012},
        {"speed_kmh": 40.0, "duration_s": 0.008},
    ]}))
    out = tmp_path / "out"
    result = simulate_vehicle(case)
    save_vehicle_result(case, result, out)
    table = read_history(out / "history.csv")
    times = np.asarray(table["time_s"], dtype=float)
    first_axle = np.asarray(table["axle1_x_m"], dtype=float)
    offset = case.vehicle.axle_offsets_m[0]
    expected = np.asarray([travel_mileage_m(case, float(t)) + offset for t in times])
    assert np.array_equal(first_axle, expected)

    schedule = case.speed_schedule
    assert schedule is not None
    analytic = case.run.x_start_m + schedule.x_at(float(times[-1]))
    assert first_axle[-1] - offset == pytest.approx(analytic, abs=1e-12)
    assert result.summary["gates"]["spin_tracking"] is True
