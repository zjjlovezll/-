"""Pin the lateral capability measurement that decides the curve question.

The archived record is the output of ``scripts/s43_running_equilibrium.py --capability``:
51 states (17 lateral offsets x 3 attack angles), each with the vertical rows re-seated so the
loads stay at one vehicle weight, reading the contact law's own net lateral force.

The claim these tests protect is narrow and numeric:

* the curving demand at R = 1100 m, 80 km/h is 21 842.4 N;
* the strongest state that keeps every wheel inside [0.625, 1.6] x share reaches only
  ~37 % of it (8.17 kN), so "eight wheels loaded, each in band" and "carry the curve" are
  mutually exclusive on a cant-free 1100 m curve;
* the first state that does reach the demand carries a full load transfer (a whole side at
  zero), which is 2.7x the physically required transfer.

If somebody re-runs the probe and the numbers move, these tests fail on purpose: the conclusion
is a measurement, not an opinion, and it must be re-argued rather than silently inherited.
"""

from __future__ import annotations

import json
import pathlib

RECORD = (pathlib.Path(__file__).resolve().parents[1]
          / "reports" / "curve_capability_2026-10-28" / "capability.json")


def _record() -> dict:
    return json.loads(RECORD.read_text(encoding="utf-8"))


def test_demand_is_the_one_the_gate_is_written_against() -> None:
    record = _record()
    assert record["radius_m"] == 1100.0
    assert abs(record["speed_kmh"] - 80.0) < 1e-9
    assert abs(record["demand_n"] - 21_842.4) < 1.0


def test_the_seat_leaves_lateral_rows_unbalanced() -> None:
    # The seat solves z (and wheelset yaw on a curve); it deliberately leaves y and roll alone,
    # so the state it returns is not a lateral equilibrium.  Recorded, not asserted as correct.
    record = _record()
    assert record["seat_residual_n"] < 1e-6
    assert max(abs(value) for value in record["unbalanced_lateral_rows_n"]) > 10_000.0


def test_the_band_admits_only_a_third_of_the_demand() -> None:
    record = _record()
    inside = [row for row in record["capability"] if row["in_band"]]
    assert inside, "no in-band state at all would be an even stronger claim"
    best = max(abs(row["sum_fy_n"]) for row in inside)
    fraction = best / record["demand_n"]
    assert 0.30 < fraction < 0.45, f"in-band capability moved to {fraction:.1%} of demand"
    # The strongest in-band point must still be short of the demand by a wide margin.
    assert best < 0.5 * record["demand_n"]


def test_reaching_the_demand_costs_a_whole_side_of_contact() -> None:
    record = _record()
    reaching = [row for row in record["capability"]
                if abs(row["sum_fy_n"]) >= record["demand_n"]]
    assert reaching, "the demand must be reachable somewhere, otherwise the sweep is too narrow"
    for row in reaching:
        assert row["in_band"] is False
        assert row["ratio_min"] < 0.10, (
            "reaching the curving demand requires unloading a side; if this ever happens inside "
            "the band the curve gate becomes satisfiable and the argument must be redone")
    cheapest = min(reaching, key=lambda row: abs(row["sum_fy_n"]))
    # Sum of per-wheel ratios is the vehicle weight in shares; with a whole side unloaded the
    # remaining wheels must carry ~2x, which is what the record shows.
    assert abs(cheapest["ratio_max"] - 2.0) < 0.05


def test_the_in_band_window_is_narrow() -> None:
    record = _record()
    offsets = sorted({row["offset_mm"] for row in record["capability"] if row["in_band"]})
    assert max(offsets) - min(offsets) <= 1.0, (
        "the lateral window that keeps all eight wheels in band must stay sub-millimetre")
