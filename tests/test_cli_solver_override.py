"""The solver-override entry point: preset, patches and the derived case file.

The point of these tests is that a fast run stays *auditable*: the case bytes in the output
directory must describe the settings that actually ran, and the parent case must be untouched.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from velch.case.derive import (absolutise_profile_paths, relative_profile_references,
                               solver_override, write_derived_case)
from velch.cli import main
from velch.model import RunSettings

CASE = Path(__file__).resolve().parent.parent / "validation" / "crh380a_m" / "case_frog_N_strip05.json"

DECLARED = {
    "method": "DOP853", "x_start_m": 69.0, "duration_s": 0.05, "output_step_s": 5e-4,
    "max_solver_step_s": 1e-4, "rtol": 1e-6, "atol": 1e-8,
    "maximum_penetration_m": 0.005, "maximum_abs_contact_slope": 2.0,
    "contact_search_half_width_m": None, "body_hysteresis": False,
    "contact_seed_scope": "body", "jacobian": None, "refine_peak": False,
}


def test_fast_preset_touches_only_the_solver_keys():
    patch = solver_override(DECLARED, fast=True)
    assert patch == {"method": "BDF", "jacobian": "analytic", "rtol": 1.0e-4,
                     "max_solver_step_s": 1.0e-3}
    assert set(patch) <= set(DECLARED)


def test_explicit_arguments_beat_the_preset():
    patch = solver_override(DECLARED, fast=True, rtol=3e-5, method="Radau")
    assert patch["rtol"] == 3e-5
    assert patch["method"] == "Radau"
    assert patch["jacobian"] == "analytic"


def test_no_override_means_no_patch():
    assert solver_override(DECLARED) == {}
    assert solver_override(DECLARED, fast=False, method="DOP853") == {}


def test_jacobian_none_string_clears_the_field():
    declared = dict(DECLARED, method="BDF", jacobian="analytic")
    assert solver_override(declared, jacobian="none") == {"jacobian": None}


@pytest.mark.parametrize("kwargs", [{"rtol": 0.0}, {"rtol": -1e-6}, {"atol": 0.0},
                                    {"max_solver_step_s": -1.0}])
def test_non_positive_tolerances_are_rejected(kwargs):
    with pytest.raises(ValueError):
        solver_override(DECLARED, **kwargs)


def test_fast_preset_satisfies_run_settings(DECLARED=DECLARED):
    merged = dict(DECLARED, **solver_override(DECLARED, fast=True))
    settings = RunSettings(**merged)
    assert (settings.method, settings.jacobian) == ("BDF", "analytic")


def test_analytic_jacobian_with_dop853_is_rejected(DECLARED=DECLARED):
    merged = dict(DECLARED, jacobian="analytic")
    with pytest.raises(ValueError, match="implicit"):
        RunSettings(**merged)


def _tiny_case(tmp_path: Path) -> Path:
    payload = {
        "schema_version": "velch-vehicle-case-v2",
        "case_id": "tiny",
        "run": dict(DECLARED),
        "wheels": [{"id": "W", "lateral_offset_m": 0.75, "profile": {"file": "wheel.prr"}}],
        "rails": [{"id": "axle1_right", "profile": {"file": "profiles/right.prr"}}],
    }
    path = tmp_path / "case_tiny.json"
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def test_derived_case_patches_run_and_absolutises_profiles(tmp_path):
    source = _tiny_case(tmp_path)
    before = source.read_bytes()
    derived = write_derived_case(source, tmp_path / "out" / "case_used.json",
                                 run={"rtol": 1e-4, "max_solver_step_s": 1e-3})
    assert source.read_bytes() == before, "父算例一个字节都不能动"
    payload = json.loads(derived.read_text(encoding="utf-8"))
    assert payload["run"]["rtol"] == 1e-4
    assert payload["run"]["method"] == "DOP853", "未覆盖的键保持父算例声明"
    assert relative_profile_references(payload, tmp_path) == 0, "型面引用必须变成绝对路径"
    assert Path(payload["wheels"][0]["profile"]["file"]).is_absolute()
    assert payload["rails"][0]["profile"]["file"] == str(tmp_path / "profiles" / "right.prr")


def test_absolutise_leaves_absolute_references_alone(tmp_path):
    payload = {"a": {"file": str(tmp_path / "x.prr")}, "b": [{"file": "y.prr"}]}
    absolutise_profile_paths(payload, tmp_path)
    assert payload["a"]["file"] == str(tmp_path / "x.prr")
    assert payload["b"][0]["file"] == str(tmp_path / "y.prr")


def test_derived_case_handles_a_relative_source_path(tmp_path, monkeypatch):
    """`velch run-vehicle validation\\... --fast` passes a relative path; the derived case must
    still end up with absolute profile references (a relative base would leave them relative
    and the load would resolve them against the output directory)."""
    source = _tiny_case(tmp_path)
    monkeypatch.chdir(tmp_path)
    derived = write_derived_case(Path("case_tiny.json"), tmp_path / "out2" / "case_used.json",
                                 run={"rtol": 1e-4})
    payload = json.loads(derived.read_text(encoding="utf-8"))
    references = [payload["wheels"][0]["profile"]["file"],
                  payload["rails"][0]["profile"]["file"]]
    assert all(Path(value).is_absolute() for value in references)
    assert references[0] == str(tmp_path / "wheel.prr")


def test_derived_case_refuses_to_overwrite_the_source(tmp_path):
    source = _tiny_case(tmp_path)
    with pytest.raises(ValueError, match="source"):
        write_derived_case(source, source, run={"rtol": 1e-4})


def test_derived_case_refuses_an_existing_destination(tmp_path):
    source = _tiny_case(tmp_path)
    destination = tmp_path / "case_used.json"
    write_derived_case(source, destination, run={"rtol": 1e-4})
    with pytest.raises(ValueError, match="already exists"):
        write_derived_case(source, destination, run={"rtol": 1e-5})
    # --fast reruns into the same output directory, so the CLI passes overwrite=True
    write_derived_case(source, destination, run={"rtol": 1e-5}, overwrite=True)


def test_cli_rejects_dop853_with_an_analytic_jacobian_before_writing_anything(tmp_path):
    output = tmp_path / "run"
    code = main(["run-vehicle", str(CASE), "--output", str(output),
                 "--method", "DOP853", "--jacobian", "analytic"])
    assert code == 2
    assert not output.exists(), "校验失败时不应留下任何输出目录"
