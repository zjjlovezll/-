"""Numerical-noise control for the differential band estimate.

The reviewer (D9) pointed out that ``s9l``'s "control" pair is built from two
identical zero tracks, so its zero is structural and proves nothing about the
measurement.  This script measures the floor that *can* be measured: the same
excited track run twice with different integration tolerances.  Whatever differs
in the two channels is numerical, not physical, and it bounds how small a
per-band amplitude the differential method can resolve.

A first attempt varied ``max_solver_step_s`` (1e-3 vs 1.2e-3) and got
*bit-identical* channels, because the adaptive step is already limited far below
that cap by the contact stiffness - the cap never binds.  So the tolerance is
what must move.

Run:  python -X utf8 scripts/s9q_repeat_control.py
"""

from __future__ import annotations

import json
import pathlib
import sys
import time

import numpy as np

REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))

import s9k_random_spectrum as s9k  # noqa: E402
from velch.io.history import read_history  # noqa: E402
from velch.vehicle import load_vehicle_case  # noqa: E402
from velch.vehicle_solver import save_vehicle_result, simulate_vehicle  # noqa: E402

WORK = pathlib.Path(r"F:\velch_tmp\s9q")
DURATION_S = 2.0
RTOL = (1.0e-4, 3.0e-4)


def run(track, label: str, rtol: float) -> tuple[np.ndarray, float, float]:
    tre = s9k.write_track(track, label)
    case = s9k.build_case(tre, label)
    doc = json.loads(case.read_text(encoding="utf-8"))
    doc["run"]["duration_s"] = DURATION_S
    doc["run"]["rtol"] = rtol
    case.write_text(json.dumps(doc, indent=2, ensure_ascii=False), encoding="utf-8")
    loaded = load_vehicle_case(case)
    started = time.perf_counter()
    result = simulate_vehicle(loaded)
    seconds = time.perf_counter() - started
    out = WORK / f"out_{label}"
    out.mkdir(parents=True, exist_ok=True)
    history_path, manifest = save_vehicle_result(loaded, result, out)
    status = json.loads(pathlib.Path(manifest).read_text(encoding="utf-8"))["summary"]["result_status"]
    history = read_history(pathlib.Path(history_path))
    names = list(history.ordering)
    values = np.asarray(history.data[names.index(s9k.CHANNEL)], dtype=float)
    times = np.asarray(history.data[names.index("time_s")], dtype=float)
    print(f"{label} (rtol {rtol:g}): {seconds:.0f} s -> {status}, {values.size} samples")
    return values, 1.0 / float(np.mean(np.diff(times))), seconds


def main() -> int:
    WORK.mkdir(parents=True, exist_ok=True)
    track = s9k.flat_track(seed=s9k.SEED_CALIBRATION)
    first, rate, first_seconds = run(track, "rtol_a", RTOL[0])
    second, second_rate, second_seconds = run(track, "rtol_b", RTOL[1])
    if first.size != second.size:
        raise SystemExit(f"sample counts differ: {first.size} vs {second.size}")
    difference = 0.5 * (first - second)
    noise = s9k.acceleration_band_rms(difference, rate)
    signal = s9k.acceleration_band_rms(first, rate)
    truth = s9k.profile_band_rms(track)
    print(f"\n{'band (m)':>12} {'signal (m/s2)':>14} {'noise (m/s2)':>13} {'SNR dB':>8} "
          f"{'noise um':>9} {'truth um':>9}")
    report = {"rtol": list(RTOL), "duration_s": DURATION_S, "rate_hz": rate,
              "seconds": [first_seconds, second_seconds], "bands": {}}
    for band, value in signal.items():
        level = float(noise[band])
        snr = 20.0 * np.log10(value / level) if level > 0 else float("inf")
        gain = value / truth[band] if truth[band] else float("nan")
        noise_equivalent = level / gain if gain else float("nan")
        print(f"{band:>12} {value:14.4g} {level:13.4g} {snr:8.1f} "
              f"{noise_equivalent * 1e6:9.3f} {truth[band] * 1e6:9.3f}")
        report["bands"][band] = {"signal": value, "noise": level, "snr_db": snr,
                                 "noise_equivalent_um": noise_equivalent * 1e6,
                                 "truth_um": truth[band] * 1e6}
    worst = max(entry["noise_equivalent_um"] for entry in report["bands"].values())
    print(f"\nworst numerical equivalent amplitude: {worst:.3f} um")
    (WORK / "repeat_control.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print("wrote", WORK / "repeat_control.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
