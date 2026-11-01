"""Gates 8 and 9: the state a run starts from, and whether its *reading* settled.

The seven numerical gates test what the integrator did.  They passed a 60 km/h archive whose
front-rail normal force swung between 0 and 208 kN, because none of the seven looks at the launch
or at the history they were computed from.

The first version of gate 9 used the whole record and the gate itself rejected it: the frozen
baseline moves 53.88 kN from ``stock`` to ``switch`` inside 0.015 s of legal switch transfer, and
four tests failed with ``physical_gate_failed``.  A whole-record standard deviation cannot tell
"started ringing" from "did a turnout".  So gate 9 is only produced inside a window the case
*declares* (``run.stationarity_window_m``), and a case that declares nothing makes no claim and
gets no gate -- the same rule ``spin_tracking`` already follows when there is no servo.
"""

from __future__ import annotations

import json
import pathlib

import numpy as np
import pytest

from velch.vehicle import load_vehicle_case
from velch.vehicle_solver import (
    MAX_STATIONARY_FORCE_STD_KN,
    gates_result_status,
    launch_balance_gate,
    rail_force_std_kn,
    simulate_vehicle,
    stationarity_gate,
)

ROOT = pathlib.Path(__file__).resolve().parents[1]
RUNS = ROOT.parent / "scratch" / "runs"
BASELINE = ROOT / "examples" / "vehicle_v2" / "case.json"


def _series(directory: pathlib.Path) -> tuple[np.ndarray, dict]:
    series = np.load(directory / "series.npz")
    meta = json.loads((directory / "meta.json").read_text(encoding="utf-8"))
    return series["normal_force_n"], meta


def _one(pattern: str) -> pathlib.Path:
    found = sorted(RUNS.glob(pattern))
    assert found, f"no archive matching {pattern}"
    return found[-1]


def _one_with_window(pattern: str) -> pathlib.Path:
    """The archive written under the current rule, not a superseded one from the same slug.

    Round 314's first attempt archived runs with the whole-record gate; those directories still
    exist and would otherwise be picked by name order, so select on the recorded window instead of
    on the directory name.
    """
    candidates = sorted(RUNS.glob(pattern))
    for directory in reversed(candidates):
        meta = json.loads((directory / "meta.json").read_text(encoding="utf-8"))
        if meta.get("stationarity_window_m") is not None:
            return directory
    raise AssertionError(f"no archive with a declared window matching {pattern}")


def _max_std(forces: np.ndarray) -> float:
    return max(rail_force_std_kn({str(i): list(forces[:, i])
                                  for i in range(forces.shape[1])}).values())


def test_gate_eight_reads_only_the_two_limits_it_names() -> None:
    quiet = {"vertical_preload_residual_n": 9.9e-08, "spin_relative_max": 0.0}
    assert launch_balance_gate(quiet) is True
    # The defect this gate exists for: the loaded case keeps the previous speed's spin.
    assert launch_balance_gate({**quiet, "spin_relative_max": 0.3333333}) is False
    assert launch_balance_gate({**quiet, "vertical_preload_residual_n": 0.11}) is False
    # No seater run at all is not a pass.
    assert launch_balance_gate(None) is False
    # A missing spin number cannot fail a gate the run never produced.
    assert launch_balance_gate({"vertical_preload_residual_n": 1.0e-7,
                                "spin_relative_max": None}) is True


def test_gate_nine_separates_the_ringing_archive_from_the_quiet_pair() -> None:
    ringing, _ = _series(_one("one_set_x46-060.00kmh-0.5400s-*"))
    quiet_60, meta_60 = _series(_one_with_window("one_set_straight-060.00kmh-0.0200s-*"))
    quiet_80, meta_80 = _series(_one_with_window("one_set_straight-080.00kmh-0.0200s-*"))
    ringing_std, quiet60_std, quiet80_std = (_max_std(ringing), _max_std(quiet_60),
                                             _max_std(quiet_80))
    print("std kN", ringing_std, quiet60_std, quiet80_std)
    # The archives were taken over the whole 0.54 s / 0.02 s records; gate 9 is applied inside a
    # declared window, so the counts here stand in for "the window had samples".
    assert stationarity_gate({"ringing": ringing_std}, 1081) is False
    assert stationarity_gate({"quiet60": quiet60_std, "quiet80": quiet80_std}, 41) is True
    assert ringing_std > 30.0 and quiet60_std < 1.0 and quiet80_std < 1.0
    # Both quiet archives declare where their reading window was.
    assert meta_60["stationarity_window_m"] == [56.0, 65.0]
    assert meta_80["stationarity_window_m"] == [56.0, 65.0]
    assert meta_60["stationarity_samples"] >= 3


def test_a_window_with_no_samples_fails_rather_than_passing_vacuously() -> None:
    assert stationarity_gate({"a": 0.01}, 0) is False
    assert stationarity_gate({"a": 0.01}, 2) is False
    assert stationarity_gate({}, 41) is False
    assert stationarity_gate({"a": 0.01}, 3) is True


def test_the_threshold_sits_in_the_measured_gap() -> None:
    assert MAX_STATIONARY_FORCE_STD_KN == 5.0
    # 7x below the smallest ringing run (34.75 kN) and 5x above the noisiest quiet one (0.51 kN):
    # the two bounds are on different sides of the same measured gap.
    assert MAX_STATIONARY_FORCE_STD_KN * 7.0 <= 35.0
    assert MAX_STATIONARY_FORCE_STD_KN >= 5.0 * 0.51


def test_the_status_names_which_kind_of_gate_failed() -> None:
    assert gates_result_status({"a": True, "b": True}) == ("numerically_checked", [])
    assert gates_result_status({"launch_balance": False, "stationarity": True}) == (
        "physical_gate_failed", ["launch_balance"])
    assert gates_result_status({"launch_balance": False, "friction_bound": False}) == (
        "numerical_gate_failed", ["launch_balance", "friction_bound"])


def test_a_case_that_declares_no_window_gets_no_stationarity_gate(tmp_path) -> None:
    """The frozen baseline: legal switch transfer, 53.88 kN of std, and no claim to measure."""
    raw = json.loads(BASELINE.read_text(encoding="utf-8"))
    raw["run"]["duration_s"] = 0.015
    raw["run"].pop("stationarity_window_m", None)
    for item in raw.get("wheels", []):
        spec = item.get("profile") or {}
        if "file" in spec and not pathlib.Path(spec["file"]).is_absolute():
            spec["file"] = str((BASELINE.parent / spec["file"]).resolve())
    for template in raw.get("rail_templates", []):
        for station in template.get("stations", []):
            spec = station.get("profile") or {}
            if "file" in spec and not pathlib.Path(spec["file"]).is_absolute():
                spec["file"] = str((BASELINE.parent / spec["file"]).resolve())
    target = tmp_path / "no_window.json"
    target.write_text(json.dumps(raw, indent=1), encoding="utf-8")
    assert raw["run"].get("stationarity_window_m") is None
    result = simulate_vehicle(load_vehicle_case(target))
    assert "stationarity" not in result.summary["gates"]
    assert result.summary["stationarity_window_m"] is None
    assert result.summary["result_status"] == "numerically_checked"


@pytest.mark.corpus
def test_a_run_archived_after_the_gates_carries_all_nine() -> None:
    directory = _one_with_window("one_set_straight-060.00kmh-0.0200s-*")
    meta = json.loads((directory / "meta.json").read_text(encoding="utf-8"))
    gates = meta["gates"]
    expected = {"solver_completed", "finite_states_and_forces", "vertical_preload_residual",
                "penetration_within_case_limit", "friction_bound",
                "no_edge_limited_active_contact", "translational_action_reaction",
                "launch_balance", "stationarity"}
    assert set(gates) == expected
    assert all(gates.values())
    assert meta["result_status"] == "numerically_checked"
    assert meta["failed_gates"] == []
    # The archive now carries the state the run started from, not just the gates it passed.
    assert meta["launch"]["spin_relative_max"] <= 1.0e-3
    assert meta["launch"]["balanced"] is True
    assert meta["max_rail_force_std_kn"] <= MAX_STATIONARY_FORCE_STD_KN
