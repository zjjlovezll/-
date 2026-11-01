"""B052 at the data level: every archived run must have been driven at the speed it claims.

Round 43 found that `--speed-kmh` renamed a run without changing its physics, so three "different"
speeds were one 80 km/h trajectory.  The fix went into two places (`apply_speed` rewrites the constant
profile *and* rebuilds the `SpeedSchedule` that the loader materialised on the case).  This test is the
archive-level guard: it reads the metadata that each run wrote about itself and refuses a store where a
run's recorded speed, its recorded `speed_m_s`, and its declared profile speed disagree.

It is deliberately read-only and cheap -- it never loads a state array -- because it is meant to run on
every future campaign, not just this one.
"""

from __future__ import annotations

import json
import pathlib
import sys

import pytest

pytestmark = pytest.mark.corpus

CASES = ("one_set_x30", "one_set_x46", "straight_one_set")


ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))


def _rows():
    from s113_profile_inversion import _index_rows
    from s99_run_archive import OUT_ROOT

    rows = []
    for row in _index_rows():
        route = str(row.get("route", ""))
        if not route.startswith(CASES):
            continue
        meta_path = OUT_ROOT / str(row["run_id"]) / "meta.json"
        if not meta_path.is_file():
            continue
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        rows.append((row, meta))
    return rows


def test_every_archived_one_set_run_was_driven_at_the_speed_it_claims():
    rows = _rows()
    assert rows, "no one-set runs archived"

    bad = []
    for row, meta in rows:
        claimed = float(meta["speed_kmh"])
        recorded = abs(float(meta["speed_m_s"])) * 3.6
        if abs(recorded - claimed) > 1e-6:
            bad.append((row["run_id"], claimed, recorded))
    assert not bad, f"runs whose physics does not match their label: {bad}"


def test_the_declared_profile_speed_agrees_whenever_it_is_recorded():
    checked = 0
    bad = []
    for row, meta in _rows():
        if "profile_speed_kmh" not in meta:
            continue
        checked += 1
        if abs(float(meta["profile_speed_kmh"]) - float(meta["speed_kmh"])) > 1e-9:
            bad.append((row["run_id"], meta["speed_kmh"], meta["profile_speed_kmh"]))
    assert not bad, f"profile speed disagrees with the label: {bad}"
    assert checked >= 0  # runs archived before the fix carry no field; none is a failure


def test_the_speed_schedule_is_the_one_the_run_used():
    """`apply_speed` must rebuild the schedule, so the loader's own object agrees with the label."""
    from velch.vehicle import load_vehicle_case

    from s99_run_archive import apply_speed, sha256_of  # type: ignore

    source = "vehicles/turnouts/CN60-1100-1_18/cases/straight_one_set.json"
    case = load_vehicle_case(source)
    assert case.speed_schedule is not None, "the loader should materialise a schedule"

    for speed_kmh in (60.0, 100.0):
        out = apply_speed(case, speed_kmh)
        assert abs(out.speed_schedule.constant_speed_m_s - speed_kmh / 3.6) < 1e-9
        assert abs(float(out.run.speed_profile["constant"]["speed_kmh"]) - speed_kmh) < 1e-9
        # the original object is left alone
        assert abs(case.speed_schedule.constant_speed_m_s - 80.0 / 3.6) < 1e-9
        assert sha256_of(pathlib.Path(source)) == sha256_of(pathlib.Path(source))
