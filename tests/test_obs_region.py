"""M4: a single pass measures a band, not a surface -- pinned so the wording cannot drift.

One 0.40 s pass at 80 km/h drifts 0.14 mm laterally, so its contact band is ~16 mm wide on a head
that is 37 mm wide 1 mm below the crown and 61 mm at 5 mm.  Coverage of the head is 41.7 % / 25.7 %,
which is the pre-registered "contact band only": results may not say "surface".

The tests also pin the arithmetic that decides how many passes a surface claim would need
(0.9 * 37.15 / 16.0 = 2.09 -> at least three distinct lateral offsets), because that number is the
reason the next milestone is an ensemble rather than a longer run.

    PYTHONPATH=src python -m pytest tests/test_obs_region.py -q
"""
from __future__ import annotations

import json
import pathlib
import sys

import numpy as np
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import s111_obs_region as region  # noqa: E402

pytestmark = pytest.mark.corpus


@pytest.fixture(scope="module")
def measured():
    from velch.vehicle import load_vehicle_case

    # Recompute the run the stored report was made from, not merely the newest 0.40 s+ run: a later
    # run at another duration would make this test compare two different passes.
    report = region.OUT / "obs_region.json"
    if report.is_file():
        run_id = json.loads(report.read_text(encoding="utf-8"))["run_id"]
    else:
        run_id = region.latest_one_set_run()
    run_dir = region.RUNS / run_id
    meta = json.loads((run_dir / "meta.json").read_text(encoding="utf-8"))
    data = np.load(run_dir / "series.npz")
    case = load_vehicle_case(region.CASE)
    offsets = np.asarray(case.vehicle.axle_offsets_m, dtype=float)
    profiles = region.head_profiles(case)
    touched, visited = region.observed_cells(data, meta, profiles, offsets)

    band = []
    for cells in touched.values():
        per_station: dict[int, set[int]] = {}
        for bin_s, bin_y in cells:
            per_station.setdefault(bin_s, set()).add(bin_y)
        band.extend(len(bins) * region.Y_BIN_M * 1e3 for bins in per_station.values())

    readings = {}
    for depth in region.HEAD_DEPTHS_M:
        design_total = inside_total = 0
        for rail_id, cells in touched.items():
            lo, hi = visited[rail_id]
            design = region.design_cells(profiles[rail_id], depth, lo, hi)
            design_total += len(design)
            inside_total += len(cells & design)
        readings[depth] = inside_total / design_total
    return {"run_id": run_id, "band": np.array(band), "readings": readings, "profiles": profiles}


def test_the_band_is_about_sixteen_millimetres_not_the_whole_head(measured):
    assert np.median(measured["band"]) == pytest.approx(16.0, abs=1.5)
    head_1mm = region.head_width_mm(measured["profiles"]["axle1_right"], 1.0e-3)
    head_5mm = region.head_width_mm(measured["profiles"]["axle1_right"], 5.0e-3)
    assert head_1mm == pytest.approx(37.15, abs=0.5)
    assert head_5mm == pytest.approx(61.46, abs=0.5)
    assert np.median(measured["band"]) < 0.5 * head_1mm


def test_the_primary_coverage_is_a_quarter_and_the_verdict_is_a_band(measured):
    primary = measured["readings"][region.PRIMARY_DEPTH_M]
    assert primary == pytest.approx(0.257, abs=0.02)
    assert primary < 0.50, "the pre-registered verdict is 'contact band only'"
    # Deeper denominators cannot raise coverage: the head only widens.
    ordered = [measured["readings"][depth] for depth in sorted(measured["readings"])]
    assert ordered == sorted(ordered, reverse=True)


def test_three_lateral_offsets_would_be_needed_to_claim_a_surface(measured):
    head_1mm_mm = region.head_width_mm(measured["profiles"]["axle1_right"], 1.0e-3)
    band_mm = float(np.median(measured["band"]))
    assert int(np.ceil(0.9 * head_1mm_mm / band_mm)) == 3


def test_the_report_on_disk_agrees_with_the_recomputation(measured):
    path = region.OUT / "obs_region.json"
    if not path.exists():
        pytest.skip("run scripts/s111_obs_region.py --write to produce the report")
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["run_id"] == measured["run_id"]
    assert payload["verdict"] == "contact band only"
    assert payload["primary_coverage"] == pytest.approx(measured["readings"][region.PRIMARY_DEPTH_M],
                                                        abs=1e-9)
