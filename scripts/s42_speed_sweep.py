"""Does the straight-route amplitude claim hold at randomly drawn speeds, or only at 70.32 km/h?

Round 194 produced 6 of 8 band amplitudes inside 2 dB at one speed (70.3206 km/h) with a calibration drawn
from the same spectral class.  One speed is a point, not a capability: this script repeats that whole protocol
at **five speeds drawn uniformly from 70-90 km/h**, and reports how many of them reach the same bar.

Why 70-90 km/h and not wider: the pipeline calibrates its short-wave operator per recorded speed and forbids
extrapolation between speeds (gate 5).  70-90 km/h brackets the four recorded steady speeds (39.9-75.7 km/h)
at their upper end and still lies inside one decade of corrugation wavelength.  A speed drawn outside it would
be an extrapolation dressed up as a random draw.

Pre-registered before the runs, and not adjusted afterwards:

* the protocol is **exactly** round 194's -- four log-spaced bands over 0.10-0.30 m, 24 harmonics each at 8 um
  rms, calibration seed 20261029 exciting one band at a time, test seeds 20261030/20261031 summing all four,
  the same channel, the same patch, the same 2 dB criterion against **each record's own band rms**;
* a speed counts as quantifiable only if **>= 7 of its 8 predictions** are inside 2 dB;
* the number reported is **how many of the five drawn speeds reach that bar**, plus the per-band hit table.

The implementation calls round 194's own estimator (`s38_spectral_bands.main`) with the module's speed
constant patched, so the protocol cannot drift between the two scripts: there is one implementation of the
calibration, the window and the projection.

Run:  python -X utf8 scripts/s42_speed_sweep.py            (about 20 minutes)
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import numpy as np

REPORT = Path(__file__).resolve().parents[1] / "reports" / "inversion_synthetic_2026-10-28"
TARGET = REPORT / "speed_sweep.json"
WORK = Path(__file__).resolve().parents[1].parent / "scratch" / "s42"

DRAW_SEED = 20261032
SPEED_RANGE_KMH = (70.0, 90.0)
SPEED_COUNT = 5
HITS_PER_SPEED = 8
MIN_HITS = 7
DURATION_S = 0.30
GATE_DB = 2.0


def draw_speeds() -> list[float]:
    """The five speeds, fixed by a seed so the draw cannot be repeated until a convenient set appears."""
    rng = np.random.default_rng(DRAW_SEED)
    return sorted(float(round(v, 2)) for v in rng.uniform(*SPEED_RANGE_KMH, SPEED_COUNT))


def spectral_module():
    """Round 194's estimator, loaded as a module so its speed constant can be set per draw."""
    path = Path(__file__).resolve().parent / "s38_spectral_bands.py"
    spec = importlib.util.spec_from_file_location("s38_spectral_bands", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["s38_spectral_bands"] = module
    spec.loader.exec_module(module)
    return module


def run_one(module, speed_kmh: float) -> dict:
    """Run the full round-194 protocol at one speed and read back its own report."""
    out = WORK / f"spectral_{speed_kmh:.2f}.json"
    module.SPEED_KMH = speed_kmh
    module.main(["--duration", str(DURATION_S), "--json", str(out)])
    report = json.loads(out.read_text(encoding="utf-8"))
    return report


def summarise(report: dict, speed_kmh: float) -> dict:
    bands = []
    for test in report["tests"]:
        for band in test["bands"]:
            bands.append({"seed": test["seed"], "band": band["band"], "bins": band["bins"],
                          "truth_um": band["truth_um"], "recovered_um": band["recovered_um"],
                          "error_db": band["error_db"], "within_gate": band["within_gate"]})
    hits = sum(1 for row in bands if row["within_gate"])
    return {"speed_kmh": speed_kmh, "hits": hits, "predictions": len(bands),
            "quantifiable": bool(hits >= MIN_HITS), "bands": bands,
            "gate_db": GATE_DB}


def per_band_counts(runs: list[dict]) -> dict[str, dict[str, int]]:
    """Hits per wave band across every drawn speed -- does the failure move with speed or stay put?"""
    counts: dict[str, dict[str, int]] = {}
    for entry in runs:
        for row in entry["bands"]:
            cell = counts.setdefault(row["band"], {"hits": 0, "predictions": 0})
            cell["predictions"] += 1
            cell["hits"] += int(row["within_gate"])
    return counts


def main() -> int:
    speeds = draw_speeds()
    if len(speeds) != SPEED_COUNT:
        raise SystemExit(f"drew {len(speeds)} speeds, expected {SPEED_COUNT}")
    WORK.mkdir(parents=True, exist_ok=True)
    module = spectral_module()
    print(f"draw seed {DRAW_SEED}: speeds {speeds} km/h, "
          f"{HITS_PER_SPEED} predictions each, bar {MIN_HITS}/{HITS_PER_SPEED} inside {GATE_DB} dB")

    runs = []
    for speed in speeds:
        report = run_one(module, speed)
        entry = summarise(report, speed)
        runs.append(entry)
        print(f"  {speed:6.2f} km/h  hits {entry['hits']}/{entry['predictions']}  "
              f"{'quantifiable' if entry['quantifiable'] else 'not quantifiable'}")

    per_band = per_band_counts(runs)

    summary = {
        "draw_seed": DRAW_SEED,
        "speed_range_kmh": list(SPEED_RANGE_KMH),
        "speeds_kmh": speeds,
        "hits_per_speed": HITS_PER_SPEED,
        "min_hits": MIN_HITS,
        "gate_db": GATE_DB,
        "quantifiable_speeds": sum(1 for entry in runs if entry["quantifiable"]),
        "speeds_drawn": len(runs),
        "total_hits": sum(entry["hits"] for entry in runs),
        "total_predictions": sum(entry["predictions"] for entry in runs),
        "per_band": per_band,
        "criterion": (f"a speed is quantifiable when >= {MIN_HITS} of {HITS_PER_SPEED} predictions are "
                      f"inside {GATE_DB} dB against that record's own band rms"),
        "reading": ("the count of quantifiable speeds is the capability; a single speed that reaches the bar "
                    "does not establish it, and the per-band column shows whether the failure moves with "
                    "speed or stays in the same band"),
    }
    result = {"summary": summary, "runs": runs}
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_text(json.dumps(result, indent=1) + "\n", encoding="utf-8")

    print(f"\nquantifiable speeds: {summary['quantifiable_speeds']}/{summary['speeds_drawn']}")
    print(f"total hits: {summary['total_hits']}/{summary['total_predictions']}")
    print("per band:")
    for band, cell in per_band.items():
        print(f"  {band} m  {cell['hits']}/{cell['predictions']}")
    print(f"written: {TARGET}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
