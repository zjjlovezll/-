"""The run path: one setup, one port, and a launch state the run has to report.

Three things are pinned here, and each one is a defect that was live until round 312:

* **B053** -- the old route patched an already-loaded case, so the declared speed changed and the
  wheelset spin did not: ``|spin*r - travel| / travel = 0.333`` at 60 km/h.  The fix is ordering
  (write the speed into the file, then load), and ``test_patching_leaves_the_old_spin`` keeps the old
  route's behaviour visible so nobody reintroduces it as an optimisation.
* **the port has to be a port** -- an unknown name must fail with the legal list, and a value out of
  range must fail before any simulation, otherwise a typo silently runs a different experiment.
* **the launch state has to be reported** -- ``run.report_launch`` fills ``VehicleResult.launch`` and
  ``run.report_launch = false`` must leave it ``None`` exactly as before (bit-identity for every
  existing case).
"""
from __future__ import annotations

import dataclasses
import importlib.util
import pathlib

import numpy as np
import pytest

from velch.setup import (OVERRIDES, Setup, apply_overrides, check_kinematics, load_setup, resolve)
from velch.vehicle import load_vehicle_case
from velch.vehicle_solver import simulate_vehicle

ROOT = pathlib.Path(__file__).resolve().parents[1]
SETUP = ROOT / "setups" / "one_set_straight.json"


def _archive_module():
    spec = importlib.util.spec_from_file_location("velch_run_archive_test",
                                                  ROOT / "scripts" / "s99_run_archive.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _resolve(speed_kmh: float, tmp_path: pathlib.Path, ports=()):
    setup = load_setup(SETUP)
    ports = (f"speed.kmh={speed_kmh}", *ports)
    return resolve(setup, ports, out_dir=tmp_path)


def test_speed_port_rederives_the_spin(tmp_path):
    """``--set speed.kmh=60`` must land in travel *and* spin, both from the loader."""
    resolved = _resolve(60.0, tmp_path)
    case = resolved.case
    index = case.initial_v.index(max(case.initial_v))  # a wheelset spin is the largest entry
    travel = float(case.vehicle.travel_speed_m_s)
    radius = float(case.vehicle.nominal_wheel_radius_m)
    assert travel == pytest.approx(16.666666666666668, rel=0, abs=1e-12)
    assert float(case.initial_v[index]) * radius == pytest.approx(travel, rel=0, abs=1e-9)
    assert case.run.speed_profile["constant"]["speed_kmh"] == pytest.approx(60.0)
    assert check_kinematics(case) < 1e-12
    # and the parameter table says so, with the source of each number
    table = {row["parameter"]: row for row in resolved.table}
    assert table["speed.kmh"]["source"] == "override"
    assert table["wheelset.spin"]["source"].startswith("derived")


def test_patching_leaves_the_old_spin(tmp_path):
    """B053, deliberately reproduced: the archive route's ``apply_speed`` does not re-derive spin."""
    archive = _archive_module()
    resolved = _resolve(80.0, tmp_path)
    patched = archive.apply_speed(resolved.case, 60.0)
    index = patched.initial_v.index(max(patched.initial_v))
    travel = float(patched.vehicle.travel_speed_m_s)
    radius = float(patched.vehicle.nominal_wheel_radius_m)
    relative = abs(float(patched.initial_v[index]) * radius - travel) / travel
    assert travel == pytest.approx(16.666666666666668)
    assert relative == pytest.approx(1.0 / 3.0, rel=0, abs=1e-9)
    # and the guard refuses exactly that state, so the defect cannot reach a run again
    stale = dataclasses.replace(patched, initial_v=tuple(float(v) for v in patched.initial_v))
    with pytest.raises(ValueError, match="spin does not match"):
        check_kinematics(stale)


def test_unknown_or_out_of_range_port_is_refused():
    setup = load_setup(SETUP)
    with pytest.raises(ValueError, match="unknown parameter"):
        apply_overrides(setup, ["bogus.thing=1"])
    with pytest.raises(ValueError, match="legal names are"):
        apply_overrides(setup, ["speed=60"])
    with pytest.raises(ValueError, match="must be within"):
        apply_overrides(setup, ["speed.kmh=0"])
    with pytest.raises(ValueError, match="needs name=value"):
        apply_overrides(setup, ["speed.kmh"])
    with pytest.raises(ValueError, match="expected a boolean"):
        apply_overrides(setup, ["report_launch=maybe"])
    assert "speed.kmh" in OVERRIDES and "prebalance.seat_modal_scales" in OVERRIDES


def test_prebalance_ports_reach_the_case(tmp_path):
    """The pre-balance group is a port too: it decides where the vehicle starts, not a tolerance."""
    resolved = _resolve(80.0, tmp_path, ports=(
        "prebalance.seat_modal_scales=1,0.8",
        "prebalance.seat_lateral=false",
        "prebalance.equilibrate_vertical=false",
    ))
    case = resolved.case
    assert tuple(case.run.seat_modal_scales) == (1.0, 0.8)
    assert case.run.seat_lateral is False
    assert case.equilibrate_vertical is False


@pytest.mark.corpus
def test_launch_state_is_reportable_and_optional(tmp_path):
    """``report_launch`` fills ``result.launch``; without it the result is exactly as before."""
    resolved = _resolve(80.0, tmp_path)
    short = dataclasses.replace(resolved.case.run, duration_s=5.0e-4, output_step_s=2.5e-4)
    result = simulate_vehicle(dataclasses.replace(resolved.case, run=short))
    launch = result.launch
    assert launch is not None
    assert set(launch) >= {"modal_norm_m", "modal_residual_n", "vertical_preload_residual_n",
                           "spin_rad_s", "spin_relative_max", "balanced", "criteria"}
    assert launch["spin_relative_max"] <= 1.0e-3
    assert launch["modal_norm_m"] > 0.0
    assert launch["balanced"] is True
    assert np.isfinite(launch["modal_residual_n"])

    off = dataclasses.replace(short, report_launch=False)
    quiet = simulate_vehicle(dataclasses.replace(resolved.case, run=off))
    assert quiet.launch is None
    # the optional evaluate must not touch the trajectory: same frames, same positions
    assert np.array_equal(np.asarray(result.times_s), np.asarray(quiet.times_s))
    assert np.allclose(np.asarray(result.positions), np.asarray(quiet.positions), rtol=0, atol=0)
