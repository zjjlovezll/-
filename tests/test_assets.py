"""One resolver for every file a case names, so a shipped case can name a shipped asset.

The rule these tests protect: a plain relative name still means "next to the case file"
(nothing about existing documents changes), and ``lib:`` means the installed vehicle library,
which is the only spelling that can reach the mode set inside the package.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from velch import assets, vehicle_db

REPO = Path(__file__).resolve().parent.parent
PORTABLE = REPO / "examples" / "portable" / "case_flexible.json"


def _tree(tmp_path: Path, *, in_lib: bool = True) -> tuple[Path, Path]:
    case = tmp_path / "cases" / "case.json"
    case.parent.mkdir(parents=True)
    case.write_text("{}", encoding="utf-8")
    (case.parent / "wheel.csv").write_text("0 0\n", encoding="utf-8")
    (case.parent / "sub").mkdir()
    (case.parent / "sub" / "rail.csv").write_text("0 0\n", encoding="utf-8")
    library = tmp_path / "lib"
    (library / "modes").mkdir(parents=True)
    (library / "modes" / "m.json").write_text("{}", encoding="utf-8")
    return case, library


def test_a_plain_relative_name_is_next_to_the_case(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    case, _library = _tree(tmp_path)
    monkeypatch.setattr(vehicle_db, "vehicle_dir", lambda: tmp_path / "lib")

    resolved = assets.resolve_asset("wheel.csv", case_path=case, kind="profile")
    assert resolved.path == case.parent / "wheel.csv"
    assert resolved.portable is True

    nested = assets.resolve_asset("sub/rail.csv", case_path=case, kind="profile")
    assert nested.path == case.parent / "sub" / "rail.csv"


def test_the_case_prefix_means_the_same_thing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    case, _library = _tree(tmp_path)
    monkeypatch.setattr(vehicle_db, "vehicle_dir", lambda: tmp_path / "lib")

    assert assets.resolve_asset("case:wheel.csv", case_path=case).path == case.parent / "wheel.csv"


def test_lib_reaches_the_vehicle_library_with_or_without_the_folder_name(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _case, library = _tree(tmp_path)
    monkeypatch.setattr(vehicle_db, "vehicle_dir", lambda: library)

    short = assets.resolve_asset("lib:modes/m.json")
    long = assets.resolve_asset("lib:vehicles/modes/m.json")

    assert short.path == library / "modes" / "m.json"
    assert long.path == short.path
    assert short.portable is True


def test_a_missing_absolute_path_says_it_is_not_portable(tmp_path: Path) -> None:
    missing = tmp_path / "gone" / "wheel.csv"

    with pytest.raises(assets.AssetRefError) as caught:
        assets.resolve_asset(str(missing), kind="profile")

    error = caught.value
    assert isinstance(error, FileNotFoundError)
    assert "not portable" in str(error)
    assert "lib:" in error.hint


def test_a_missing_relative_name_lists_the_roots_it_looked_in(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    case, library = _tree(tmp_path)
    monkeypatch.setattr(vehicle_db, "vehicle_dir", lambda: library)

    with pytest.raises(assets.AssetRefError) as caught:
        assets.resolve_asset("nowhere.csv", case_path=case, kind="profile")

    message = str(caught.value)
    assert "cannot resolve profile 'nowhere.csv'" in message
    assert str(case.parent) in message


def test_the_shipped_portable_case_names_the_mode_set_through_the_library() -> None:
    """The shipped demo is the proof that a package can run a flexible wheelset with no env vars."""

    payload = json.loads(PORTABLE.read_text(encoding="utf-8"))
    reference = payload["flexible_wheelset"]["file"]
    assert reference.startswith("lib:")

    resolved = assets.resolve_asset(reference, case_path=PORTABLE, kind="wheel mode set")
    assert resolved.path.name == "CRH3C_wheelset_fe.json"
    assert resolved.path.parent.name == "modes"
    assert resolved.path.is_file()
    assert resolved.portable is True
