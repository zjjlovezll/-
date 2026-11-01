"""Pin what the 60 km/h reference says: the split is static, the measured station is not.

Round 305 un-suspended the physical locating gate at 80 km/h with a 0.011 m agreement.  Round 307 asked the
same question at 60 km/h, and the answer is different in a way that is worth pinning rather than smoothing
over:

* the ten coarse station rows come out **identical** to the 80 km/h sweep -- the seat is a static
  equilibrium, so the contact depths and the share do not depend on speed at all;
* the measured ``engage(5 %)`` station *does* depend on speed (58.000 m at 60, 58.156 m at 80), so the
  static reference of 58.145 m lands 0.145 m away at 60 km/h and fails the 0.10 m criterion that the
  80 km/h run met;
* 0.145 m is still inside the 0.20 m physical gate, with 55 mm to spare -- which is the whole reason the
  two thresholds are reported separately.

The fourth item is a regression on a defect this round introduced: ``verdict`` kept using the 80 km/h
reference at every speed, which turned the 60 km/h coarse-grid miss (0.062 m against 58.156) into a pass.  The error has to be computed
against the report's own ``measured_engage_5pct_m``, and the test checks that a hard-coded 80 km/h
reference would have hidden the miss.
"""

from __future__ import annotations

import json
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import s158_effective_gap as gap  # noqa: E402

REPORTS = ROOT / "reports" / "load_split_inversion_2026-10-31"
REPORT_80 = REPORTS / "effective_gap.json"
REPORT_60 = REPORTS / "effective_gap_60.json"
COARSE_M = tuple(round(57.4 + 0.2 * index, 3) for index in range(10))


def _load(path: pathlib.Path) -> dict:
    assert path.is_file(), f"missing report {path}"
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def reports() -> tuple[dict, dict]:
    return _load(REPORT_80), _load(REPORT_60)


def _rows_at(report: dict, stations: tuple[float, ...]) -> dict[float, dict]:
    wanted = {round(station, 3) for station in stations}
    rows = {round(row["station_m"], 3): row for row in report["stations"]}
    missing = sorted(wanted - set(rows))
    assert not missing, f"stations missing from the sweep: {missing}"
    return {station: rows[station] for station in sorted(wanted)}


def test_the_split_is_speed_independent(reports: tuple[dict, dict]) -> None:
    """A static seat cannot know how fast the vehicle is going, and the rows show it."""
    eighty, sixty = reports
    rows_80 = _rows_at(eighty, COARSE_M)
    rows_60 = _rows_at(sixty, COARSE_M)
    assert sixty["verdict"]["speed_kmh"] == pytest.approx(60.0)
    assert eighty["verdict"]["speed_kmh"] == pytest.approx(80.0)

    worst = 0.0
    for station in COARSE_M:
        for key in ("effective_gap_m", "depth_stock_m", "depth_blade_m", "share_measured"):
            worst = max(worst, abs(rows_60[station][key] - rows_80[station][key]))
    assert worst < 1e-12, f"the 60 and 80 km/h sweeps differ by {worst:.3e}"

    # ... and that equality is not vacuous: the sweep does move with the station.
    shares = [rows_80[station]["share_measured"] for station in COARSE_M]
    assert max(shares) - min(shares) > 0.5


def test_the_measured_station_does_depend_on_speed(reports: tuple[dict, dict]) -> None:
    """The one thing in this comparison that is not static."""
    eighty, sixty = reports
    reference_60 = sixty["verdict"]["measured_engage_5pct_m"]
    reference_80 = eighty["verdict"]["measured_engage_5pct_m"]
    assert reference_60 == pytest.approx(58.000, abs=1e-9)
    assert reference_80 == pytest.approx(58.156, abs=1e-9)
    assert abs(reference_80 - reference_60) > gap.STATION_TOLERANCE_M


def test_sixty_fails_the_reference_and_stays_inside_the_physical_gate(
    reports: tuple[dict, dict],
) -> None:
    _, sixty = reports
    verdict = sixty["verdict"]
    assert verdict["crossing_count"] == 1
    assert verdict["station_from_effective_m"] == pytest.approx(58.145, abs=5e-4)
    assert verdict["station_error_m"] == pytest.approx(0.145, abs=2e-3)
    assert verdict["H7_reference_station"] is False
    # Fails the refined criterion, passes the physical one with 55 mm of room.
    assert gap.STATION_TOLERANCE_M < verdict["station_error_m"] < 0.20


def test_the_error_uses_the_reports_own_reference(reports: tuple[dict, dict]) -> None:
    """Regression: a hard-coded 80 km/h reference reported 0.062 m at 60 km/h."""
    for report in reports:
        verdict = report["verdict"]
        expected = abs(verdict["station_from_effective_m"] - verdict["measured_engage_5pct_m"])
        assert verdict["station_error_m"] == pytest.approx(expected, abs=1e-12)

    # The defect was visible on the coarse grid, which is where it first fired: the 60 km/h sweep reported
    # its crossing against the 80 km/h reference and passed.  Recompute the coarse crossing here rather than
    # quoting it, so the arithmetic cannot drift away from the sweep it came from.
    rows = list(_rows_at(reports[1], COARSE_M).values())
    coarse = gap.crossings(rows, gap.gap_for_share(0.05))
    assert coarse == pytest.approx([58.094], abs=5e-4)
    hardcoded = abs(coarse[0] - 58.156)
    assert hardcoded == pytest.approx(0.062, abs=2e-3)
    assert hardcoded < gap.STATION_TOLERANCE_M, "the defect really did hide the miss"


def test_the_crown_gap_still_fails_and_eighty_is_unaffected(reports: tuple[dict, dict]) -> None:
    eighty, sixty = reports
    for report in reports:
        verdict = report["verdict"]
        assert verdict["H5_crown_is_effective"] is False
        assert verdict["worst_crown_minus_effective_um"] > 30.0
        assert verdict["closure_crown_max_fraction"] > 5.0 * verdict["closure_effective_max_fraction"]

    verdict = eighty["verdict"]
    assert verdict["H7_reference_station"] is True
    assert verdict["station_error_m"] == pytest.approx(0.011, abs=2e-3)
