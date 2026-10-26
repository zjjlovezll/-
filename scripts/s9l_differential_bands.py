"""Same question as S9-11, but with the differential that S7e used for the long waves.

S9-11 measured the per-band transfer from one random track and applied it to a differently
shaped one.  It failed, and the failure is informative: in 7 of 8 bands the band rms of the
excited run was indistinguishable from the band rms of a run with **no excitation at all**
(SNR ~0 dB), so the ratio had nothing to divide.  Recovered amplitudes came back equal to the
*calibration* track's amplitudes, not the test track's.

This script asks whether the differential pair fixes that.  For each track we run ``+A`` and
``−A`` and take ``(a(+A) − a(−A)) / 2``: whatever does not scale with the excitation -- the
start-up transient, the ring of the vehicle's own modes, the rail geometry -- is identical in
both runs and cancels exactly, because the case, speed and start mileage are the same.

Protocol:

1. calibration track (flat, 5 um per band): ``G(band)`` from the differential pair;
2. test track (same length, per-band amplitudes scaled by ``TEST_SCALES``): invert its
   differential pair with ``G`` and compare per band;
3. a zero-excitation differential (trivially zero) is not needed: the cancellation is exact by
   construction, so the honest check is the residual of a pair whose excitation is zero, run
   once as a control.

    python -X utf8 scripts/s9l_differential_bands.py
"""

from __future__ import annotations

import json
import pathlib
import sys
import time

import numpy as np

REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

import s9k_random_spectrum as s9k  # noqa: E402

from velch.io.history import read_history  # noqa: E402
from velch.vehicle import load_vehicle_case  # noqa: E402
from velch.vehicle_solver import save_vehicle_result, simulate_vehicle  # noqa: E402

WORK = pathlib.Path(r"F:\velch_tmp\s9l")
DURATION_S = 2.0


def scaled(track, factor: float, label: str):
    from velch.irregularity import IrregularityTrack

    values = np.asarray(track.vertical_m, dtype=float) * factor
    zeros = np.zeros_like(values)
    return IrregularityTrack(
        s_m=np.asarray(track.s_m, dtype=float), lateral_m=zeros, vertical_m=values,
        roll_rad=zeros, gauge_m=zeros, source=f"generated: {label} x {factor:+.0f}",
    )


def run_pair(track, label: str) -> tuple[dict[str, float], float, str]:
    """Run +A and −A, return the per-band rms of their half-difference."""

    series = {}
    statuses = []
    seconds = 0.0
    for sign, tag in ((1.0, "plus"), (-1.0, "minus")):
        variant = scaled(track, sign, label) if sign < 0 else track
        tre = s9k.write_track(variant, f"{label}_{tag}")
        case = s9k.build_case(tre, f"{label}_{tag}")
        doc = json.loads(case.read_text(encoding="utf-8"))
        doc["run"]["duration_s"] = DURATION_S
        case.write_text(json.dumps(doc, indent=2, ensure_ascii=False), encoding="utf-8")
        loaded = load_vehicle_case(case)
        started = time.perf_counter()
        result = simulate_vehicle(loaded)
        seconds += time.perf_counter() - started
        out = WORK / f"out_{label}_{tag}"
        out.mkdir(parents=True, exist_ok=True)
        history_path, manifest = save_vehicle_result(loaded, result, out)
        status = json.loads(pathlib.Path(manifest).read_text(encoding="utf-8"))["summary"]["result_status"]
        statuses.append(status)
        history = read_history(pathlib.Path(history_path))
        names = list(history.ordering)
        series[tag] = np.asarray(history.data[names.index(s9k.CHANNEL)], dtype=float)
        rate = 1.0 / float(np.mean(np.diff(np.asarray(history.data[names.index("time_s")], dtype=float))))
    difference = 0.5 * (series["plus"] - series["minus"])
    print(f"{label}: {2 * DURATION_S:.1f} s of simulation in {seconds:.0f} s -> {statuses}")
    for tag, status in zip(("plus", "minus"), statuses):
        if status != "numerically_checked":
            raise SystemExit(
                f"{label}/{tag} finished as {status!r}, not numerically_checked; the pair is"
                " unusable.  Returning statuses[0] is how a failed -A run passed silently."
            )
    return s9k.acceleration_band_rms(difference, rate), seconds, ",".join(statuses)



def run_against(first, second, label: str):
    """Run two concrete tracks and return the band rms of their half-difference.

    `run_pair` can only express the +A / -A pair.  The control needs +A against a track with
    no excitation at all: +0 against -0 is the same file twice, so it is zero by construction
    and cannot show what differencing fails to cancel.
    """
    series = {}
    statuses = []
    seconds = 0.0
    for tag, track in (("first", first), ("second", second)):
        tre = s9k.write_track(track, f"{label}_{tag}")
        case = s9k.build_case(tre, f"{label}_{tag}")
        doc = json.loads(case.read_text(encoding="utf-8"))
        doc["run"]["duration_s"] = DURATION_S
        case.write_text(json.dumps(doc, indent=2, ensure_ascii=False), encoding="utf-8")
        loaded = load_vehicle_case(case)
        started = time.perf_counter()
        result = simulate_vehicle(loaded)
        seconds += time.perf_counter() - started
        out = WORK / f"out_{label}_{tag}"
        out.mkdir(parents=True, exist_ok=True)
        history_path, manifest = save_vehicle_result(loaded, result, out)
        status = json.loads(pathlib.Path(manifest).read_text(encoding="utf-8"))["summary"]["result_status"]
        statuses.append(status)
        history = read_history(pathlib.Path(history_path))
        names = list(history.ordering)
        series[tag] = np.asarray(history.data[names.index(s9k.CHANNEL)], dtype=float)
        rate = 1.0 / float(np.mean(np.diff(np.asarray(history.data[names.index("time_s")], dtype=float))))
    for tag, status in zip(("first", "second"), statuses):
        if status != "numerically_checked":
            raise SystemExit(f"{label}/{tag} finished as {status!r}, not numerically_checked")
    difference = 0.5 * (series["first"] - series["second"])
    print(f"{label}: {2 * DURATION_S:.1f} s of simulation in {seconds:.0f} s -> {statuses}")
    return s9k.acceleration_band_rms(difference, rate), seconds, ",".join(statuses)


def main() -> int:
    WORK.mkdir(parents=True, exist_ok=True)
    calibration_track = s9k.flat_track(seed=s9k.SEED_CALIBRATION)
    test_track = s9k.flat_track(seed=s9k.SEED_TEST, scales=s9k.TEST_SCALES)

    calibration, seconds_calibration, _ = run_pair(calibration_track, "cal")
    test, seconds_test, _ = run_pair(test_track, "test")

    control_track = s9k.flat_track(seed=s9k.SEED_CALIBRATION)
    zero_track = type(control_track)(
        s_m=np.asarray(control_track.s_m, dtype=float),
        lateral_m=np.zeros_like(np.asarray(control_track.vertical_m, dtype=float)),
        vertical_m=np.zeros_like(np.asarray(control_track.vertical_m, dtype=float)),
        roll_rad=np.zeros_like(np.asarray(control_track.vertical_m, dtype=float)),
        gauge_m=np.zeros_like(np.asarray(control_track.vertical_m, dtype=float)),
        source="generated: no excitation (control)",
    )
    control, seconds_control, _ = run_against(control_track, zero_track, "control")

    truth_calibration = s9k.profile_band_rms(calibration_track)
    truth_test = s9k.profile_band_rms(test_track)

    print(f"\n{'band (m)':>12} {'G (m/s2)/m':>12} {'true um':>9} {'recovered':>10} {'error':>8} "
          f"{'dB':>6} {'control':>9}")
    report: dict[str, object] = {"bands": {}}
    for band in truth_calibration:
        gain = calibration[band] / truth_calibration[band] if truth_calibration[band] else float("nan")
        recovered = test[band] / gain if gain else float("nan")
        true = truth_test[band]
        error = (recovered - true) / true * 100.0 if true else float("nan")
        db = 20.0 * np.log10(recovered / true) if true and recovered > 0 else float("nan")
        print(f"{band:>12} {gain:12.4g} {true * 1e6:9.3f} {recovered * 1e6:10.3f} "
              f"{error:7.1f}% {db:6.2f} {control[band]:9.2e}")
        report["bands"][band] = {"gain": gain, "true_um": true * 1e6, "recovered_um": recovered * 1e6,
                                 "error_percent": error, "error_db": db, "control": control[band]}
    good = [entry for entry in report["bands"].values() if abs(entry["error_db"]) <= 2.0]
    print(f"\nquantitative (|dB| <= 2): {len(good)}/{len(report['bands'])} bands")
    report["summary"] = {"quantitative": len(good), "bands": len(report["bands"]),
                         "seconds": {"calibration": seconds_calibration, "test": seconds_test,
                                     "control": seconds_control},
                         "duration_s": DURATION_S}
    (WORK / "differential.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("wrote", WORK / "differential.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
