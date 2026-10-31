"""Tests for the concurrent campaign runner (round 291, second half)."""

from __future__ import annotations

import json
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import s147_parallel_campaign as campaign  # noqa: E402
import s99_run_archive as archive  # noqa: E402

CASE = ROOT / "vehicles" / "turnouts" / "CN60-1100-1_18" / "cases" / "straight.json"


def test_one_job_per_case_with_a_deterministic_run_id():
    jobs = campaign.planned([CASE, CASE], 80.0, 0.02, 5e-4, {"campaign": "test"})
    assert len(jobs) == 2
    assert jobs[0]["run_id"] == jobs[1]["run_id"]  # same inputs, same id
    digest = archive.sha256_of(CASE)
    assert jobs[0]["run_id"].endswith(digest[:8])
    assert jobs[0]["route"] == "straight"


def test_the_command_carries_every_flag_the_archive_needs():
    jobs = campaign.planned([CASE], 60.0, 1.35, 5e-4, {"campaign": "test", "phase": "b"})
    argv = campaign.command(jobs[0])
    assert "--case" in argv and str(CASE) in argv
    assert argv[argv.index("--speed-kmh") + 1] == "60"
    assert argv[argv.index("--duration") + 1] == "1.3500"
    assert argv.count("--note") == 2
    assert "campaign=test" in argv and "phase=b" in argv


def test_the_workers_are_pinned_to_one_thread_and_take_the_lock():
    env = campaign.worker_environment()
    for name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
        assert env[name] == "1"
    assert env["VELCH_INDEX_LOCK"] == "1"


def test_the_index_lock_does_not_change_the_written_rows(tmp_path, monkeypatch):
    monkeypatch.setattr(archive, "OUT_ROOT", tmp_path)
    monkeypatch.setattr(archive, "INDEX", tmp_path / "index.jsonl")
    monkeypatch.setenv("VELCH_INDEX_LOCK", "1")
    archive.write_index({"run_id": "b", "route": "r", "speed_kmh": 80.0, "duration_s": 0.6})
    archive.write_index({"run_id": "a", "route": "r", "speed_kmh": 60.0, "duration_s": 0.6})
    archive.write_index({"run_id": "b", "route": "r", "speed_kmh": 80.0, "duration_s": 0.7})
    rows = [json.loads(line) for line in (tmp_path / "index.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [row["run_id"] for row in rows] == ["a", "b"]          # sorted, no duplicates
    assert rows[1]["duration_s"] == pytest.approx(0.7)            # the replacement won
    assert (tmp_path / "index.lock").exists()


def test_an_indexed_run_is_skipped_unless_forced(tmp_path, monkeypatch):
    rows = tmp_path / "index.jsonl"
    rows.write_text(json.dumps({"run_id": "already"}) + "\n", encoding="utf-8")
    monkeypatch.setattr(archive, "INDEX", rows)
    assert "already" in campaign.indexed()
    assert "not-there" not in campaign.indexed()
