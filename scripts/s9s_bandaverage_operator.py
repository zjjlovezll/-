"""8x8 operator from *band-averaged* probes instead of one tone per band.

`scripts/s9m_band_matrix.py` probes each octave with a single tone at the band
centre and then regresses a broadband record on band rms.  The measured ratio
came out 1.15-1.92 for every band (`docs/BAND_CAPABILITY_2026-10-26.md` §10):
a tone is not the band average.  This script keeps the matrix idea but probes
each band with the same random-phase broadband track `s9l` calibrates with,
zeroed outside the probed band - so the probe's band rms *is* the band average.

It answers two questions at once:

* does the full matrix beat the diagonal once the probes are band averages?
* does any residual cross-band coupling remain after the axle-box fix (B027)?

Run:  python -X utf8 scripts/s9s_bandaverage_operator.py
"""

from __future__ import annotations

import json
import math
import pathlib
import sys
import time

import numpy as np

REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))

import s9k_random_spectrum as s9k  # noqa: E402
import s9l_differential_bands as s9l  # noqa: E402
from velch.io.history import read_history  # noqa: E402
from velch.vehicle import load_vehicle_case  # noqa: E402
from velch.vehicle_solver import save_vehicle_result, simulate_vehicle  # noqa: E402

WORK = pathlib.Path(r"F:\velch_tmp\s9s")
DURATION_S = 2.0


def band_labels() -> list[str]:
    bands = s9k.octave_bands()
    return [f"{short:g}-{long:g}" for short, long in bands]


def run_pair(track, label: str) -> tuple[dict[str, float], float, str]:
    """Same differential as s9l, but writing into this script's work directory."""

    series = {}
    statuses = []
    seconds = 0.0
    for sign, tag in ((1.0, "plus"), (-1.0, "minus")):
        variant = s9l.scaled(track, sign, label) if sign < 0 else track
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
    print(f"{label}: {2 * DURATION_S:.1f} s in {seconds:.0f} s -> {statuses}", flush=True)
    return s9k.acceleration_band_rms(difference, rate), seconds, statuses[0]


def main() -> int:
    WORK.mkdir(parents=True, exist_ok=True)
    s9k.WORK = WORK
    s9l.WORK = WORK
    labels = band_labels()
    count = len(labels)
    store = WORK / "operator.json"
    state: dict[str, object] = json.loads(store.read_text(encoding="utf-8")) if store.exists() else {}
    matrix: dict[str, list[float]] = state.setdefault("matrix", {})  # type: ignore[assignment]

    for index, label in enumerate(labels):
        if label in matrix:
            continue
        scales = [0.0] * count
        scales[index] = 1.0
        track = s9k.flat_track(seed=s9k.SEED_CALIBRATION, scales=tuple(scales))
        probe = s9k.profile_band_rms(track)
        if probe[label] <= 0.0:
            raise SystemExit(f"probe for {label} came out silent: {probe}")
        response, _seconds, status = run_pair(track, f"b{index:02d}")
        if status != "numerically_checked":
            raise SystemExit(f"probe {label} did not converge: {status}")
        matrix[label] = [float(response[name]) / float(probe[label]) for name in labels]
        state["labels"] = labels
        state["duration_s"] = DURATION_S
        state["probe"] = "random-phase flat track, one octave at a time, 5 um rms"
        store.write_text(json.dumps(state, indent=2), encoding="utf-8")
        print(f"probe {label:>10s}: " + " ".join(f"{value:9.2f}" for value in matrix[label]), flush=True)

    operator = np.array([matrix[label] for label in labels], dtype=float)
    print("\nM_band (rows = excited band, cols = response band), (m/s^2)/m")
    print("  " + " " * 10 + " ".join(f"{label:>9s}" for label in labels))
    for label, row in zip(labels, operator):
        print(f"  {label:>10s} " + " ".join(f"{value:9.1f}" for value in row))
    print(f"\ncond(M_band) = {np.linalg.cond(operator):.4g}")

    test = s9k.flat_track(seed=s9k.SEED_TEST, scales=s9k.TEST_SCALES)
    measured, _seconds, status = run_pair(test, "test")
    if status != "numerically_checked":
        raise SystemExit(f"test run did not converge: {status}")
    truth = np.array([float(s9k.profile_band_rms(test)[label]) for label in labels], dtype=float)
    response = np.array([float(measured[label]) for label in labels], dtype=float)

    predicted = operator.T @ truth
    error = float(np.linalg.norm(predicted - response) / np.linalg.norm(response))
    correlation = float(np.corrcoef(predicted, response)[0, 1])
    print(f"\nsuperposition error = {error * 100:.1f} %   Pearson = {correlation:.3f}")
    print(f"\n{'band':>10} {'truth um':>9} {'pred um':>8} {'meas um':>8} {'ratio':>6}")
    for index, label in enumerate(labels):
        print(f"{label:>10} {truth[index] * 1e6:9.3f} {predicted[index] * 1e6:8.3f} "
              f"{response[index] * 1e6:8.3f} {response[index] / predicted[index]:6.2f}")

    diagonal = np.diag(operator).copy()
    recovered_diagonal = response / diagonal
    recovered_full = np.linalg.lstsq(operator.T, response, rcond=None)[0]
    print(f"\n{'band':>10} {'truth um':>9} {'diag':>8} {'dB':>7} {'full':>8} {'dB':>7}")
    rows = []
    for index, label in enumerate(labels):
        true = truth[index]
        diag_value = recovered_diagonal[index]
        full_value = recovered_full[index]
        diag_db = 20.0 * math.log10(abs(diag_value) / true) if true > 0 and diag_value > 0 else float("nan")
        full_db = 20.0 * math.log10(abs(full_value) / true) if true > 0 and full_value > 0 else float("nan")
        print(f"{label:>10} {true * 1e6:9.3f} {diag_value * 1e6:8.3f} {diag_db:7.2f} "
              f"{full_value * 1e6:8.3f} {full_db:7.2f}")
        rows.append({"band": label, "truth_um": true * 1e6, "diagonal_um": diag_value * 1e6,
                     "diagonal_db": diag_db, "full_um": full_value * 1e6, "full_db": full_db})
    good_diag = sum(1 for row in rows if abs(row["diagonal_db"]) <= 2.0)
    good_full = sum(1 for row in rows if abs(row["full_db"]) <= 2.0)
    print(f"\nwithin 2 dB: diagonal {good_diag}/{count}, full matrix {good_full}/{count}")
    state["rows"] = rows
    state["superposition_error"] = error
    state["pearson"] = correlation
    state["good"] = {"diagonal": good_diag, "full": good_full, "bands": count}
    store.write_text(json.dumps(state, indent=2), encoding="utf-8")
    print("wrote", store)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
