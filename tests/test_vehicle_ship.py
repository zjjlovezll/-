"""The packaged build must find the vehicle library where PyInstaller actually puts it.

A PyInstaller 6 onedir bundle writes ``datas`` into ``_internal``, while
``velch.data_root.frozen_install_root()`` is the exe's own folder.  ``vehicle_db._root()``
used to look only at ``<install>/vehicles``, so a packaged build printed an empty library
and that reads as "the models were not shipped" instead of "they shipped one directory
deeper".  These tests pin both layouts, so the packaging change cannot silently regress.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from velch import data_root, vehicle_db

REPO = Path(__file__).resolve().parent.parent


def _fake_install(tmp_path: Path, *, where: str) -> Path:
    """Build a miniature install tree with one model, at ``where`` below the install folder."""

    install = tmp_path / "Velch"
    folder = install / where if where else install
    folder = folder / "vehicles"
    folder.mkdir(parents=True)
    payload = json.loads((REPO / "vehicles" / "CRH380A_M.json").read_text(encoding="utf-8"))
    (folder / "CRH380A_M.json").write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return install


@pytest.fixture()
def frozen(monkeypatch: pytest.MonkeyPatch):
    def _apply(install: Path) -> None:
        monkeypatch.setattr(data_root, "is_frozen", lambda: True)
        monkeypatch.setattr(data_root, "frozen_install_root", lambda: install)
        monkeypatch.setattr(data_root, "repository_root", lambda: install)
        monkeypatch.delenv("VELCH_VEHICLE_DIR", raising=False)

    return _apply


def test_the_library_is_found_next_to_the_executable(tmp_path: Path, frozen) -> None:
    install = _fake_install(tmp_path, where="")
    frozen(install)

    assert vehicle_db.vehicle_dir() == install / "vehicles"
    assert [model.id for model in vehicle_db.list_models()] == ["CRH380A_M"]


def test_the_library_is_found_inside_internal(tmp_path: Path, frozen) -> None:
    install = _fake_install(tmp_path, where="_internal")
    frozen(install)

    assert vehicle_db.vehicle_dir() == install / "_internal" / "vehicles"
    assert [model.id for model in vehicle_db.list_models()] == ["CRH380A_M"]


def test_the_environment_variable_still_wins(tmp_path: Path, frozen, monkeypatch: pytest.MonkeyPatch) -> None:
    install = _fake_install(tmp_path, where="")
    frozen(install)
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.setenv("VELCH_VEHICLE_DIR", str(elsewhere))

    assert vehicle_db.vehicle_dir() == elsewhere.resolve()


def test_the_shipped_library_carries_the_flexible_wheelset_set() -> None:
    """The modal set is data, not code: if it is not in the folder, the flexible vehicle is dead."""

    modes = REPO / "vehicles" / "modes" / "CRH3C_wheelset_fe.json"
    assert modes.is_file(), "vehicles/modes/CRH3C_wheelset_fe.json is missing"
    payload = json.loads(modes.read_text(encoding="utf-8"))
    assert payload["format"] == "velch-wheel-modes/1"
    assert len(payload["modes"]) == 33
