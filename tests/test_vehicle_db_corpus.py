"""车辆库与算例的接缝：`vehicle_ref` 必须与内联 `vehicle` 完全等价。

这些用例要读算例语料（1.4 GB 外置），所以整模块带 `corpus` 标记：没有语料的机器跳过而不是红。
逐位的整条 `history.csv` 比对在 `scripts/verify_vehicle_ref.py`（跑两遍真算），这里只比解析结果。
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from velch import vehicle_db
from velch.data_root import case_dir
from velch.vehicle import VehicleParameters, load_vehicle_case

pytestmark = pytest.mark.corpus

REPO = Path(__file__).resolve().parent.parent
CASE = case_dir() / "case_A_final_law.json"


def _case_without_vehicle(tmp_path: Path, **extra) -> Path:
    raw = json.loads(CASE.read_text(encoding="utf-8"))
    raw.pop("vehicle")
    raw["case_id"] = "vehicle_ref_case"
    raw.update(extra)
    path = tmp_path / "case.json"
    path.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    return path


def test_the_block_is_verbatim_from_the_calibrated_case() -> None:
    """车辆文件里的数字必须是算例里那一块的逐字复制（不是四舍五入的副本）。"""
    case_block = json.loads(CASE.read_text(encoding="utf-8"))["vehicle"]

    assert vehicle_db.load("CRH380A_M").block == case_block


def test_the_reference_resolves_to_the_same_parameters(tmp_path: Path) -> None:
    """引用解析出的 VehicleParameters 必须与内联那一块解析出的**完全相等**。"""
    path = _case_without_vehicle(tmp_path, vehicle_ref="CRH380A_M")

    inline = load_vehicle_case(CASE).vehicle
    referenced = load_vehicle_case(path).vehicle

    assert isinstance(referenced, VehicleParameters)
    assert referenced == inline


def test_the_reference_pins_the_vehicle_file(tmp_path: Path) -> None:
    """改车辆文件必须让产物校验失败，所以它的 sha256 要进 asset_hashes。"""
    case = load_vehicle_case(_case_without_vehicle(tmp_path, vehicle_ref="CRH380A_M"))

    keys = {Path(key).name for key in case.asset_hashes}

    assert "CRH380A_M.json" in keys


def test_a_case_without_any_vehicle_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="either 'vehicle' or 'vehicle_ref'"):
        load_vehicle_case(_case_without_vehicle(tmp_path))


def test_a_case_with_both_sources_is_rejected(tmp_path: Path) -> None:
    raw = json.loads(CASE.read_text(encoding="utf-8"))
    raw["vehicle_ref"] = "CRH380A_M"
    raw["case_id"] = "both"
    path = tmp_path / "case.json"
    path.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(ValueError, match="both 'vehicle' and 'vehicle_ref'"):
        load_vehicle_case(path)


def test_an_unknown_reference_says_what_it_looked_for(tmp_path: Path) -> None:
    from velch.vehicle_db import VehicleModelError

    path = _case_without_vehicle(tmp_path, vehicle_ref="NO_SUCH_CAR")

    with pytest.raises(VehicleModelError, match="not found"):
        load_vehicle_case(path)
