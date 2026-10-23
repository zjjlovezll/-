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


# --- 车体几何：记录值必须与求解器真正用的数字自洽 -------------------------------------------

def test_the_recorded_geometry_agrees_with_the_numbers_the_solver_uses(tmp_path: Path) -> None:
    raw = _raw()
    geometry = raw["geometry"]
    block = raw["vehicle"]
    assert geometry["carbody"]["mass_kg"] == block["carbody"]["mass_kg"]
    assert geometry["bogies"]["distance_m"] == pytest.approx(2.0 * block["bogie_half_spacing_m"])
    assert geometry["bogies"]["wheelbase_m"] == pytest.approx(block["wheelbase_m"])
    # 空气簧上表面 −1.0 m、车体质心 −1.55 m → 求解器的相对锚高 0.55 m
    assert (geometry["secondary"]["air_spring_upper_z_m"] - geometry["carbody"]["cg_m"]["z"]
            == pytest.approx(block["secondary"]["upper_anchor_height_m"], abs=1e-3))
    # 空气簧下表面 −0.8 m、构架质心 −0.51 m → −0.29 m
    assert (geometry["secondary"]["air_spring_lower_z_m"] - geometry["bogies"]["cg_z_m"]
            == pytest.approx(block["secondary"]["lower_anchor_height_m"], abs=1e-3))
    assert vehicle_db.validate(vehicle_db.load(_write(tmp_path, raw))) == []


def test_geometry_that_contradicts_the_vehicle_block_is_refused(tmp_path: Path) -> None:
    raw = _raw()
    raw["geometry"]["carbody"]["mass_kg"] = 34000.0
    problems = vehicle_db.validate(vehicle_db.VehicleModel(path=tmp_path, raw=raw))
    assert any("geometry.carbody.mass_kg" in item and "disagrees" in item for item in problems)
    with pytest.raises(vehicle_db.VehicleModelError, match="geometry.carbody.mass_kg"):
        vehicle_db.load(_write(tmp_path, raw))


def test_a_carbody_centre_of_gravity_above_the_rail_is_refused(tmp_path: Path) -> None:
    raw = _raw()
    raw["geometry"]["carbody"]["cg_m"]["z"] = 0.4
    problems = vehicle_db.validate(vehicle_db.VehicleModel(path=tmp_path, raw=raw))
    assert any("cg_m.z must be below the rail top" in item for item in problems)
    with pytest.raises(vehicle_db.VehicleModelError, match="below the rail top"):
        vehicle_db.load(_write(tmp_path, raw))


def test_bogie_distance_must_be_twice_the_half_spacing(tmp_path: Path) -> None:
    raw = _raw()
    raw["geometry"]["bogies"]["distance_m"] = 17.0
    problems = vehicle_db.validate(vehicle_db.VehicleModel(path=tmp_path, raw=raw))
    assert any("must be twice" in item for item in problems)
    with pytest.raises(vehicle_db.VehicleModelError, match="must be twice"):
        vehicle_db.load(_write(tmp_path, raw))


def test_an_anchor_that_does_not_follow_from_the_frame_is_refused(tmp_path: Path) -> None:
    raw = _raw()
    raw["geometry"]["secondary"]["air_spring_upper_z_m"] = -1.20
    problems = vehicle_db.validate(vehicle_db.VehicleModel(path=tmp_path, raw=raw))
    assert any("implies" in item and "upper_anchor_height_m" in item for item in problems)
    with pytest.raises(vehicle_db.VehicleModelError, match="upper_anchor_height_m"):
        vehicle_db.load(_write(tmp_path, raw))


def test_the_report_names_the_carbody_geometry() -> None:
    text = vehicle_db.main_report([vehicle_db.load("CRH380A_M")])
    assert "车体几何" in text and "34934" in text and "-1.55" in text
    assert "定距 17.5" in text
