"""Tests for the parameter registry: the Chinese labelling and validation contract of the UI."""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from velch.data_root import case_dir
from velch.ui.parameters import (
    REGISTRY,
    ParameterError,
    ParameterSpec,
    apply_patch,
    coverage,
    editable,
    registry_by_path,
    to_chinese,
)

CASE = case_dir() / "case_full12_cap05.json"


def _case() -> dict:
    return json.loads(CASE.read_text(encoding="utf-8"))


def _has_cjk(text: str) -> bool:
    return any("\u4e00" <= char <= "\u9fff" for char in text)


def test_registry_paths_unique_and_labelled():
    table = registry_by_path()
    assert len(table) == len(REGISTRY)
    for spec in REGISTRY:
        assert _has_cjk(spec.label_zh), spec.path
        assert spec.unit, spec.path
        assert _has_cjk(spec.group), spec.path


def test_spec_rejects_bad_range():
    with pytest.raises(ParameterError):
        ParameterSpec("a.b", "名称", "m", "分组", minimum=10.0, maximum=1.0)
    with pytest.raises(ParameterError):
        ParameterSpec("nodot", "名称", "m", "分组")
    with pytest.raises(ParameterError):
        ParameterSpec("a.b", "", "m", "分组")


def test_coverage_is_complete_on_the_reference_case():
    """Drift guard: a new editable field without a Chinese label fails here."""
    if not CASE.exists():
        pytest.skip("reference case not present")
    named, missing = coverage(_case())
    assert missing == []
    assert named > 60


def test_editable_resolves_real_values():
    case = _case()
    found = dict((spec.path, value) for spec, value in editable(case))
    assert found["vehicle.carbody.mass_kg"] == pytest.approx(34934.0)
    assert found["rail_templates[].support.k_z_n_m"] == [pytest.approx(5.0e7)] * 2


def test_apply_patch_copies_and_never_touches_the_input():
    case = _case()
    before = case["vehicle"]["travel_speed_m_s"]
    patched = apply_patch(case, {"vehicle.travel_speed_m_s": 27.0})
    assert case["vehicle"]["travel_speed_m_s"] == before
    assert patched["vehicle"]["travel_speed_m_s"] == pytest.approx(27.0)
    assert patched is not case


def test_apply_patch_wildcard_hits_every_element():
    case = _case()
    patched = apply_patch(case, {"rail_templates[].support.k_z_n_m": 4.5e7})
    for template in patched["rail_templates"]:
        assert template["support"]["k_z_n_m"] == pytest.approx(4.5e7)


@pytest.mark.parametrize(
    ("patch", "message"),
    [
        ({"vehicle.nope": 1.0}, "unknown parameter"),
        ({"contact.friction_coefficient": 9.0}, "maximum"),
        ({"contact.friction_coefficient": -1.0}, "minimum"),
        ({"contact.friction_coefficient": float("nan")}, "finite"),
        ({"contact.friction_coefficient": float("inf")}, "finite"),
        ({"contact.friction_coefficient": "0.3"}, "must be a number"),
        ({"contact.friction_coefficient": True}, "must be a number"),
    ],
)
def test_apply_patch_rejects_bad_edits(patch, message):
    with pytest.raises(ParameterError) as excinfo:
        apply_patch(_case(), patch)
    assert message in str(excinfo.value)


def test_to_chinese_maps_known_and_falls_back():
    assert to_chinese("vehicle.carbody.mass_kg") == "车体质量"
    assert to_chinese("vehicle.unknown.field") == "vehicle.unknown.field"
