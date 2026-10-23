"""The .spck reader must resolve symbols and expressions, and must not guess."""
from __future__ import annotations

from pathlib import Path

import pytest

from velch.simpack_model import SpckModel, SpckModelError, read_model, suspension_table

SAMPLE = """\
!file.version=3.6! Removing this line will make the file unreadable
version.number = 20210100
subvar.str (   $_PrimSpr_c_z  ) = '1176000'   ! 一系钢簧垂向刚度
subvar.txt (   $_PrimSpr_c_z  ) = ' 一系钢簧垂向刚度 [N/m] '
subvar.str (   $_Prim_Damp_c  ) = '4900000'   ! 一系垂向减震器节点接头刚度
subvar.txt (   $_Prim_Damp_c  ) = ' 一系垂向减震器节点接头刚度 [N/m] '
subvar.str (   $_Half         ) = '2'
subvar.str (   $_Derived      ) = '{ $G_PrimSusp.$_Prim_Damp_c/2 }'
subvar.str (   $_Broken       ) = '$G_Ghost.$_Missing + 1'
subvar.txt (   $_Broken       ) = ' 指向不存在的量 '
body.mass (   $B_BogieFrame   ) = $G_BogieFrame.$G_Mass.$_PrimSpr_c_z
force.type (   $F_PS_Damp_FL  ) = 6   ! Type
force.from (   $F_PS_Damp_FL  ) = $M_BogieFrame
force.to   (   $F_PS_Damp_FL  ) = $M_AxleGuide_FL
force.par ( 1 , $F_PS_Damp_FL ) = 0.0                    ! [m] Nominal length
force.par ( 3 , $F_PS_Damp_FL ) = $G_PrimSusp.$_Prim_Damp_c ! [N.s/m] Damping
joint.type (   $J_AxleGuide_FL ) = 2  ! Type
marker.pos ( 1 , $M_AxleGuide_FL ) = 0.0
"""


@pytest.fixture()
def sample(tmp_path: Path) -> Path:
    path = tmp_path / "sample.spck"
    path.write_text(SAMPLE, encoding="utf-8")
    return path


def test_literals_and_symbols_resolve(sample: Path) -> None:
    model = read_model(sample)
    assert model.subvariables["$_PrimSpr_c_z"] == 1_176_000.0
    assert model.subvariables["$_Prim_Damp_c"] == 4_900_000.0


def test_an_expression_is_evaluated_not_echoed(sample: Path) -> None:
    model = read_model(sample)
    assert model.subvariables["$_Derived"] == pytest.approx(2_450_000.0)


def test_a_missing_symbol_stays_unresolved_instead_of_becoming_zero(sample: Path) -> None:
    model = read_model(sample)
    assert "$_Broken" not in model.subvariables
    assert "$_Broken" in model.inventory()["unresolved"]


def test_counts_and_force_table(sample: Path) -> None:
    model = read_model(sample)
    counts = model.counts()
    assert counts["forces"] >= 1 and counts["joints"] >= 1 and counts["bodies"] >= 1
    inventory = model.inventory()
    force = next(item for item in inventory["forces"] if item["name"] == "$F_PS_Damp_FL")
    assert force["type"] == "6"
    assert force["from"] == "$M_BogieFrame"
    assert force["parameters"]["3"]["value"] == 4_900_000.0
    assert "Damping" in force["parameters"]["3"]["comment"]


def test_the_type_schema_is_reported_from_the_file(sample: Path) -> None:
    model = read_model(sample)
    schema = model.inventory()["force_types"]
    signature = next(iter(schema.values()))
    assert any("Damping" in entry for entry in signature)


def test_suspension_table_selects_by_name_or_comment(sample: Path) -> None:
    model = read_model(sample)
    symbols = {row[0] for row in suspension_table(model)}
    assert "$_PrimSpr_c_z" in symbols
    assert "$_Prim_Damp_c" in symbols


def test_a_file_without_subvariables_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "not-a-model.spck"
    path.write_text("version.number = 20210100\n", encoding="utf-8")
    with pytest.raises(SpckModelError, match="no subvariables"):
        SpckModel(path)


def test_a_missing_file_is_refused(tmp_path: Path) -> None:
    with pytest.raises(SpckModelError, match="no such model file"):
        SpckModel(tmp_path / "absent.spck")


def test_to_json_round_trips(sample: Path, tmp_path: Path) -> None:
    model = read_model(sample)
    target = model.to_json(tmp_path / "inventory.json")
    text = target.read_text(encoding="utf-8")
    assert "velch-spck-inventory-v1" in text
    assert "$_PrimSpr_c_z" in text
