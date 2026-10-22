"""Where the corpus lives: the three-step resolution order, pinned.

The validation corpus (1.4 GB) does not ship with the package, so its location has to be
resolvable without editing code.  These tests fix the precedence and the failure behaviour,
because a silent fallback to the in-repository path would make every gate read an empty
directory and *pass* -- no cases means nothing to contradict.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from velch import data_root


@pytest.fixture()
def sandbox(tmp_path, monkeypatch) -> Path:
    """A fake repository root, so the real marker file never leaks into a test."""

    root = tmp_path / "Velch"
    root.mkdir()
    monkeypatch.setattr(data_root, "REPOSITORY_ROOT", root)
    monkeypatch.delenv("VELCH_DATA_ROOT", raising=False)
    return root


def test_default_is_the_in_repository_directory(sandbox: Path) -> None:
    assert data_root.data_root() == sandbox / "validation"
    assert data_root.case_dir() == sandbox / "validation" / "crh380a_m"
    assert data_root.explain()["source"] == "repository default"


def test_environment_wins_over_the_marker(sandbox: Path, tmp_path, monkeypatch) -> None:
    (sandbox / data_root.MARKER_NAME).write_text(
        json.dumps({"data_root": str(tmp_path / "from-marker")}), encoding="utf-8"
    )
    monkeypatch.setenv("VELCH_DATA_ROOT", str(tmp_path / "from-env"))
    assert data_root.data_root() == (tmp_path / "from-env").resolve()
    assert data_root.explain()["source"] == "environment VELCH_DATA_ROOT"


def test_marker_is_honoured_including_a_written_bom(sandbox: Path, tmp_path) -> None:
    """PowerShell 5.1 writes UTF-8 *with* a BOM; the marker must still parse."""

    target = tmp_path / "moved" / "validation"
    target.mkdir(parents=True)
    (sandbox / data_root.MARKER_NAME).write_bytes(
        b"\xef\xbb\xbf" + json.dumps({"data_root": str(target)}).encode("utf-8")
    )
    assert data_root.data_root() == target.resolve()
    assert data_root.explain()["source"] == "marker .velch-data.json"


def test_marker_may_be_relative_to_its_own_directory(sandbox: Path) -> None:
    (sandbox / "corpus").mkdir()
    (sandbox / data_root.MARKER_NAME).write_text(
        json.dumps({"data_root": "corpus"}), encoding="utf-8"
    )
    assert data_root.data_root() == (sandbox / "corpus").resolve()


@pytest.mark.parametrize(
    "payload",
    ["", "not json", "[]", '{"data_root": ""}', '{"data_root": 42}', "{}"],
)
def test_a_broken_marker_falls_back_instead_of_raising(sandbox: Path, payload: str) -> None:
    (sandbox / data_root.MARKER_NAME).write_text(payload, encoding="utf-8")
    assert data_root.data_root() == sandbox / "validation"
    assert data_root.explain()["source"] == "repository default"


def test_case_path_refuses_to_guess(sandbox: Path) -> None:
    with pytest.raises(FileNotFoundError):
        data_root.case_path("case_does_not_exist.json")


def test_the_real_checkout_resolves_to_a_populated_directory() -> None:
    """Guards the checkout that is actually in use, not a sandbox."""

    cases = data_root.case_dir()
    if not cases.is_dir():
        pytest.skip(f"corpus not present at {cases}")
    assert (cases / "case_full12_cap05.json").is_file()
    assert len(list(cases.glob("case_*.json"))) > 100
