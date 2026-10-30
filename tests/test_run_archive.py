"""The run archive is a contract: an id from inputs only, and an index with no duplicates.

Both properties are what make the archive usable as a surrogate training set later.  If the id were
not derived from the inputs, re-running one configuration would scatter duplicates through the index;
if ``write_index`` appended blindly, a rebuilt case would leave two rows claiming the same run and a
training set built from the index would weight that configuration twice.

No simulation runs here -- the helpers are pure, so this file stays at milliseconds.
"""
from __future__ import annotations

import importlib.util
import json
import sys
import pathlib

import pytest

SCRIPT = pathlib.Path(__file__).resolve().parents[1] / "scripts" / "s99_run_archive.py"


@pytest.fixture(scope="module")
def archive():
    spec = importlib.util.spec_from_file_location("s99_run_archive", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_a_run_id_depends_on_the_inputs_and_nothing_else(archive) -> None:
    first = archive.run_id_for("straight", 80.0, 0.85, 5e-4, "b39b697c" + "0" * 56)
    again = archive.run_id_for("straight", 80.0, 0.85, 5e-4, "b39b697c" + "0" * 56)
    assert first == again, "the same configuration must produce the same id"

    # The digest is the geometry: change one station of the case and the run is a different run.
    assert archive.run_id_for("straight", 80.0, 0.85, 5e-4, "a" * 64) != first
    # So are the sampling settings, because they change what the surrogate can learn.
    assert archive.run_id_for("straight", 60.0, 0.85, 5e-4, "b39b697c" + "0" * 56) != first
    assert archive.run_id_for("straight", 80.0, 0.20, 5e-4, "b39b697c" + "0" * 56) != first
    assert archive.run_id_for("straight", 80.0, 0.85, 1e-3, "b39b697c" + "0" * 56) != first


def test_the_index_replaces_a_repeated_run_instead_of_appending_it(archive, tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(archive, "OUT_ROOT", tmp_path)
    monkeypatch.setattr(archive, "INDEX", tmp_path / "index.jsonl")

    entry = {"run_id": "straight-080.00kmh-0.0100s-500us-b39b697c", "route": "straight",
             "speed_kmh": 80.0, "duration_s": 0.01, "frames": 21, "gates": {"solver_completed": True}}
    archive.write_index(entry)
    archive.write_index(entry)
    rows = [json.loads(line) for line in (tmp_path / "index.jsonl").read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 1, f"the same run was indexed {len(rows)} times"

    # A second configuration is a second row, and the index stays sorted by route then speed.
    other = dict(entry, run_id="straight-060.00kmh-0.0100s-500us-b39b697c", speed_kmh=60.0)
    archive.write_index(other)
    rows = [json.loads(line) for line in (tmp_path / "index.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [row["speed_kmh"] for row in rows] == [60.0, 80.0]


def test_a_malformed_note_is_refused_rather_than_dropped(archive, tmp_path, monkeypatch) -> None:
    """``--note purpose=x`` becomes metadata; a note without ``=`` has nowhere to go and must not
    silently vanish into the archive, because the note is how a sweep labels its parameters later."""
    monkeypatch.setattr(archive, "OUT_ROOT", tmp_path)
    monkeypatch.setattr(archive, "INDEX", tmp_path / "index.jsonl")
    monkeypatch.setattr(sys, "argv", ["s99_run_archive.py", "--route", "straight",
                                      "--duration", "0.01", "--note", "no-equals-sign"])
    with pytest.raises(SystemExit):
        archive.main()
