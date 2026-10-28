"""The five-speed sweep draws what it says it draws, and counts a speed as quantifiable only at its bar.

The round-194 result is one speed, so it is a point and not a capability.  This sweep repeats the whole
protocol at five speeds drawn from a seed, and the only number that means anything is how many of those five
reach the bar.  These tests pin the parts that must not drift: the draw is deterministic and inside the
declared range, a speed counts at exactly the pre-registered hit count rather than at any hit count, and the
per-band column counts predictions the same way the summary does.

Run:  pytest tests/test_speed_sweep.py -q
"""

from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import s42_speed_sweep as sweep  # noqa: E402


def _row(index: int, *, hits: int) -> dict:
    """One prediction row in the shape the estimator reports, with `hits` of eight inside the gate."""
    return {"band": f"b{index}", "bins": 4, "truth_um": 8.0, "recovered_um": 8.0,
            "error_db": 0.0, "within_gate": index < hits}


def test_the_draw_is_reproducible_and_inside_the_declared_range() -> None:
    speeds = sweep.draw_speeds()
    assert speeds == sweep.draw_speeds()          # same seed, same speeds, every time
    assert len(speeds) == sweep.SPEED_COUNT
    assert speeds == sorted(speeds)
    low, high = sweep.SPEED_RANGE_KMH
    assert all(low <= v <= high for v in speeds)
    assert all(round(v, 2) == v for v in speeds)


def test_a_speed_counts_only_at_the_pre_registered_hit_count() -> None:
    """Six of eight is short, seven of eight is the bar -- there is no partial credit at 6."""
    rows = [_row(i, hits=6) for i in range(8)]
    six = sweep.summarise({"tests": [{"seed": 1, "bands": rows}]}, 80.0)
    assert six["hits"] == 6 and six["quantifiable"] is False

    rows = [_row(i, hits=7) for i in range(8)]
    seven = sweep.summarise({"tests": [{"seed": 1, "bands": rows}]}, 80.0)
    assert seven["hits"] == 7 and seven["quantifiable"] is True


def test_summarise_reads_both_seeds_so_eight_predictions_are_counted() -> None:
    band = {"band": "0.1000-0.1316", "bins": 7, "truth_um": 8.0, "recovered_um": 8.1,
            "error_db": 0.1, "within_gate": True}
    report = {"tests": [{"seed": 1, "bands": [band] * 4}, {"seed": 2, "bands": [band] * 4}]}
    entry = sweep.summarise(report, 72.5)
    assert entry["predictions"] == 8 and entry["hits"] == 8
    assert entry["speed_kmh"] == 72.5


def test_per_band_counts_aggregate_every_speed_and_not_just_one() -> None:
    runs = [
        {"bands": [{"band": "a", "within_gate": True}, {"band": "b", "within_gate": False}]},
        {"bands": [{"band": "a", "within_gate": True}, {"band": "b", "within_gate": True}]},
    ]
    counts = sweep.per_band_counts(runs)
    assert counts["a"] == {"hits": 2, "predictions": 2}
    assert counts["b"] == {"hits": 1, "predictions": 2}


def test_the_bar_is_seven_of_eight_and_the_gate_is_two_db() -> None:
    """If either constant moves, every count in the report moves with it -- so pin both."""
    assert sweep.HITS_PER_SPEED == 8
    assert sweep.MIN_HITS == 7
    assert sweep.GATE_DB == 2.0
