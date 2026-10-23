"""The catalogue and the goal-status page must cover what the code can actually do."""
from __future__ import annotations

from pathlib import Path

import pytest

from velch.elements import PARAMETERS, describe_inventory, inventory
from velch.vehicle_db import list_models

DOCS = Path(__file__).resolve().parent.parent / "docs"


def _catalogue() -> str:
    path = DOCS / "ELEMENT_CATALOGUE_2026-10-23.md"
    assert path.is_file(), path
    return path.read_text(encoding="utf-8")


def test_every_supported_element_appears_in_the_catalogue() -> None:
    text = _catalogue()
    missing = [kind for kind in PARAMETERS if f"`{kind}`" not in text]
    assert not missing, f"catalogue does not mention: {missing}"


def test_the_catalogue_names_what_was_not_ported() -> None:
    text = _catalogue()
    for phrase in ("内部状态", "事件检测", "气室", "约束类", "User Routine"):
        assert phrase in text, f"catalogue hides '{phrase}'"


def test_the_goal_page_states_each_step_and_its_evidence() -> None:
    path = DOCS / "GOAL_STATUS_2026-10-23.md"
    text = path.read_text(encoding="utf-8")
    for step in ("① 代码稳定", "② bug", "③ UI", "④ 安装包", "⑤ 读 Simpack"):
        assert step in text, step
    assert "unvalidated_against_measurement_or_Simpack" in text


@pytest.mark.corpus
def test_the_inventory_counts_what_the_models_declare() -> None:
    models = {model.id: model for model in list_models()}
    assert models, "no vehicles found"
    named = [model for model in models.values() if inventory(model.raw)]
    assert named, "no vehicle declares elements"
    for model in named:
        counts = inventory(model.raw)
        declared = len((model.raw.get("topology") or {}).get("elements") or ())
        assert sum(counts.values()) == declared
        assert describe_inventory(counts)


@pytest.mark.corpus
def test_a_node_model_reports_its_axles() -> None:
    models = {model.id: model for model in list_models()}
    node = [model for model in models.values() if inventory(model.raw)]
    assert node, "no node model"
    for model in node:
        assert model.summary()["axle_count"] == 4, model.id
