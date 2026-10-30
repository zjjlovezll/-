"""The wheel profile's sampling distance must not decide the lateral force (B050).

Three things are pinned here, all measured on the one-set turnout case:

* resampling the 282-point wheel four times more finely lands on the *same polyline* (the geometry
  is unchanged, only the sampling) -- so a difference in the answer cannot be a difference in shape;
* the canonical one-set case points at that finer file, and the run that used it drifts 0.0999 mm in
  0.40 s against 0.7305 mm with the coarse sampling;
* ``seat_lateral`` stays off by default, because every frozen baseline was measured without it.
"""
from __future__ import annotations

import json
import pathlib
import sys

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import s101_one_set_case as builder  # noqa: E402  (needs the repo's scripts directory)
CASE = ROOT / "vehicles" / "turnouts" / "CN60-1100-1_18" / "cases" / "straight_one_set.json"
RUNS = ROOT.parent / "scratch" / "runs"


def _points(path: pathlib.Path) -> np.ndarray:
    lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    start = next(i for i, ln in enumerate(lines) if ln.strip().startswith("point.begin"))
    end = next(i for i, ln in enumerate(lines) if ln.strip().startswith("point.end"))
    rows = []
    for ln in lines[start + 1:end]:
        fields = ln.split("!")[0].split()
        if len(fields) >= 2:
            try:
                rows.append((float(fields[0]), float(fields[1])))
            except ValueError:
                continue
    return np.array(rows, dtype=float)


def test_the_dense_wheel_lies_on_the_original_polyline() -> None:
    dense = _points(builder.LIB / "LMA_x4.prw")
    coarse = _points(builder.WHEEL_SOURCE)
    assert dense.shape[0] == 4 * coarse.shape[0]

    # distance from every dense point to the nearest coarse segment, in the profile's own units
    def distance_to_polyline(points: np.ndarray, poly: np.ndarray, probe: int = 400) -> float:
        sample = points[np.linspace(0, points.shape[0] - 1, probe).astype(int)]
        worst = 0.0
        for point in sample:
            best = np.inf
            for a, b in zip(poly[:-1], poly[1:]):
                edge = b - a
                length = float(edge @ edge)
                if length <= 0.0:
                    continue
                t = float(np.clip((point - a) @ edge / length, 0.0, 1.0))
                best = min(best, float(np.hypot(*(point - (a + t * edge)))))
            worst = max(worst, best)
        return worst

    assert distance_to_polyline(dense, coarse) <= 1e-6


def test_the_canonical_case_uses_the_dense_wheel_and_no_lateral_seat() -> None:
    raw = json.loads(CASE.read_text(encoding="utf-8"))
    for wheel in raw["wheels"]:
        assert wheel["profile"]["file"].endswith("LMA_x4.prw")
        assert wheel["profile"]["format"] == "prr"
    assert not raw["run"].get("seat_lateral", False)


def test_the_dense_wheel_run_drifts_less_than_a_quarter_of_the_coarse_one() -> None:
    index = RUNS / "index.jsonl"
    if not index.is_file():
        return  # scratch is not shipped; the numeric claim lives in the doc
    rows = [json.loads(line) for line in index.read_text(encoding="utf-8").splitlines() if line.strip()]
    rows = [row for row in rows if "one_set" in str(row.get("route"))
            and abs(float(row.get("duration_s", 0.0)) - 0.40) < 1e-9]
    if len(rows) < 2:
        return
    newest = rows[-1]
    series = np.load(RUNS / newest["run_id"] / "series.npz")
    positions = series["positions"]
    meta = json.loads((RUNS / newest["run_id"] / "meta.json").read_text(encoding="utf-8"))
    from velch.vehicle import load_vehicle_case, topology_of

    case = load_vehicle_case(CASE)
    topology = topology_of(case.topology, case.vehicle)
    indices = [topology.require(f"wheelset{index}", "y") for index in range(1, 5)]
    start = positions[0, indices]
    drift = float(np.max(np.abs(positions[-1, indices] - start)))
    assert meta["duration_s"] == 0.40
    assert drift <= 0.25e-3, "the one-set run's lateral drift must stay well under a quarter millimetre"
