"""车辆库：文件格式与校验规则。这一份不需要算例语料，任何机器上都应该真跑。"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from velch import vehicle_db

REPO = Path(__file__).resolve().parent.parent
MODEL = REPO / "vehicles" / "CRH380A_M.json"


def _raw() -> dict:
    return json.loads(MODEL.read_text(encoding="utf-8"))


def _write(tmp_path: Path, raw: dict) -> Path:
    path = tmp_path / "vehicle.json"
    path.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    return path


def test_the_calibrated_vehicle_is_in_the_database() -> None:
    model = vehicle_db.load("CRH380A_M")

    assert model.id == "CRH380A_M"
    assert model.axle_count == 4
    assert model.raw["layout"]["state_dimension"] == 35
    assert model.status.startswith("unvalidated")
    assert model.path.name == "CRH380A_M.json"


def test_the_summary_matches_the_hand_computed_mass() -> None:
    model = vehicle_db.load("CRH380A_M")
    block = model.block

    # 34934 车体 + 2 x 3300 转向架 + 4 x 1780 轮对
    expected = (block["carbody"]["mass_kg"] + 2 * block["bogie"]["mass_kg"]
                + 4 * block["wheelset"]["mass_kg"])
    assert model.summary()["mass_total_kg"] == pytest.approx(expected, abs=0.1)
    assert model.summary()["travel_speed_m_s"] == pytest.approx(97.2222, abs=1e-4)


def test_the_model_declares_what_it_does_not_verify() -> None:
    """没标定就得说没标定，而且缺哪些物理要写出来——否则换车的人不知道边界在哪。"""
    raw = _raw()

    assert raw["physics_validation_status"] == "unvalidated_against_measurement_or_Simpack"
    assert raw["not_verified"], "not_verified must list the missing physics"
    assert any("轴箱" in item for item in raw["not_verified"])


@pytest.mark.parametrize("mutate,expected", [
    (lambda raw: raw["vehicle"]["primary"].__setitem__("k_z_n_m", -1.0), "must not be negative"),
    (lambda raw: raw["vehicle"]["carbody"].__setitem__("mass_kg", 0.0), "positive number"),
    (lambda raw: raw["layout"].__setitem__("bogies", 3), "2 bogies x 2 axles"),
    (lambda raw: raw["layout"].__setitem__("state_dimension", 40), "state_dimension must be 35"),
    (lambda raw: raw["wheels"][0].__setitem__("lateral_offset_m", 0.5), "either side of the centre"),
    (lambda raw: raw["wheels"][0].__setitem__("lateral_offset_m", -0.8), "symmetric"),
    (lambda raw: raw.pop("provenance"), "provenance is required"),
    (lambda raw: raw.__setitem__("physics_validation_status", ""), "physics_validation_status"),
    (lambda raw: raw["vehicle"].pop("secondary"), "vehicle.secondary is required"),
    (lambda raw: raw["vehicle"].__setitem__("travel_speed_m_s", 0.0), "must be positive"),
    (lambda raw: raw.__setitem__("schema_version", "something-else"), "schema_version"),
])
def test_broken_models_are_rejected(tmp_path: Path, mutate, expected: str) -> None:
    raw = _raw()
    mutate(raw)
    path = _write(tmp_path, raw)
    model = vehicle_db.VehicleModel(path=path, raw=raw)

    problems = vehicle_db.validate(model)

    assert any(expected in problem for problem in problems), problems


def test_the_index_lists_the_same_models_as_the_directory() -> None:
    listed = {model.id for model in vehicle_db.list_models()}
    indexed = {entry["id"] for entry in vehicle_db.index()["models"]}

    assert listed == indexed
    assert "CRH380A_M" in listed


def test_a_missing_model_says_where_it_looked() -> None:
    with pytest.raises(vehicle_db.VehicleModelError, match="not found"):
        vehicle_db.load("NO_SUCH_CAR")


def test_the_summary_report_shows_the_status_verbatim() -> None:
    text = vehicle_db.main_report(vehicle_db.list_models())

    assert "CRH380A_M" in text
    assert "35 自由度" in text
    assert "unvalidated_against_measurement_or_Simpack" in text
