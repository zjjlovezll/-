"""Analysis of the band-averaged operator without re-simulating anything.

`scripts/s9s_bandaverage_operator.py` writes the 8x8 matrix and leaves the test
pair on disk, but its superposition table printed the response columns scaled by
1e6, which reads like micrometres while it is (m/s^2).  This script re-reads
`operator.json` plus `out_test_plus` / `out_test_minus`, prints every quantity in
its own unit, and adds a non-negative inversion - the unconstrained least squares
returns a negative amplitude for 6.4-12.5 m, which is not a physical answer.

Run:  python -X utf8 scripts/s9t_band_average_analysis.py
"""

from __future__ import annotations

import json
import math
import pathlib
import sys

import numpy as np

REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))

import s9k_random_spectrum as s9k  # noqa: E402
import s9s_bandaverage_operator as s9s  # noqa: E402
from velch.io.history import read_history  # noqa: E402

WORK = pathlib.Path(r"F:\velch_tmp\s9s")


def differential_channel(label: str) -> tuple[np.ndarray, float]:
    series = {}
    for tag in ("plus", "minus"):
        history = read_history(WORK / f"out_{label}_{tag}" / "history.csv")
        names = list(history.ordering)
        series[tag] = np.asarray(history.data[names.index(s9k.CHANNEL)], dtype=float)
        rate = 1.0 / float(np.mean(np.diff(np.asarray(history.data[names.index("time_s")], dtype=float))))
    return 0.5 * (series["plus"] - series["minus"]), rate


def non_negative(matrix: np.ndarray, response: np.ndarray) -> np.ndarray:
    """Projected least squares: clamp to zero and refit on the active set."""

    active = np.ones(matrix.shape[1], dtype=bool)
    values = np.zeros(matrix.shape[1], dtype=float)
    for _ in range(matrix.shape[1] + 1):
        estimate, *_ = np.linalg.lstsq(matrix[:, active], response, rcond=None)
        values = np.zeros(matrix.shape[1], dtype=float)
        values[active] = estimate
        worst = int(np.argmin(values)) if np.any(values < 0.0) else -1
        if worst < 0 or not active[worst]:
            break
        active[worst] = False
    return values


def main() -> int:
    state = json.loads((WORK / "operator.json").read_text(encoding="utf-8"))
    labels = list(state["labels"])
    operator = np.array([state["matrix"][label] for label in labels], dtype=float)
    test = s9k.flat_track(seed=s9k.SEED_TEST, scales=s9k.TEST_SCALES)
    truth = np.array([float(s9k.profile_band_rms(test)[label]) for label in labels], dtype=float)
    difference, rate = differential_channel("test")
    measured = s9k.acceleration_band_rms(difference, rate)
    response = np.array([float(measured[label]) for label in labels], dtype=float)

    predicted = operator.T @ truth
    error = float(np.linalg.norm(predicted - response) / np.linalg.norm(response))
    correlation = float(np.corrcoef(predicted, response)[0, 1])
    print(f"superposition error = {error * 100:.1f} %   Pearson = {correlation:.3f}")
    print(f"{'band':>10} {'truth um':>9} {'pred m/s2':>10} {'meas m/s2':>10} {'meas/pred':>9}")
    for index, label in enumerate(labels):
        print(f"{label:>10} {truth[index] * 1e6:9.3f} {predicted[index]:10.4f} "
              f"{response[index]:10.4f} {response[index] / predicted[index]:9.2f}")

    diagonal = np.diag(operator).copy()
    unconstrained, *_ = np.linalg.lstsq(operator.T, response, rcond=None)
    constrained = non_negative(operator.T, response)
    print(f"\n{'band':>10} {'truth um':>9} {'diag dB':>8} {'full um':>9} {'full dB':>8} "
          f"{'pos um':>8} {'pos dB':>7}")
    rows = []
    for index, label in enumerate(labels):
        true = truth[index]
        diag_value = response[index] / diagonal[index]
        full_value = unconstrained[index]
        pos_value = constrained[index]
        diag_db = 20.0 * math.log10(abs(diag_value) / true)
        full_db = (20.0 * math.log10(abs(full_value) / true)) if full_value > 0 else float("nan")
        pos_db = (20.0 * math.log10(pos_value / true)) if pos_value > 0 else float("-inf")
        print(f"{label:>10} {true * 1e6:9.3f} {diag_db:8.2f} {full_value * 1e6:9.3f} {full_db:8.2f} "
              f"{pos_value * 1e6:8.3f} {pos_db:7.2f}")
        rows.append({"band": label, "truth_um": true * 1e6, "diagonal_db": diag_db,
                     "full_um": full_value * 1e6, "full_db": full_db,
                     "positive_um": pos_value * 1e6, "positive_db": pos_db})
    for name, key in (("diagonal", "diagonal_db"), ("full", "full_db"), ("non-negative", "positive_db")):
        good = sum(1 for row in rows if abs(row[key]) <= 2.0)
        print(f"within 2 dB: {name} {good}/{len(rows)}")
    state["analysis"] = {"superposition_error": error, "pearson": correlation, "rows": rows}
    (WORK / "analysis.json").write_text(json.dumps(state["analysis"], indent=2, ensure_ascii=False),
                                       encoding="utf-8")
    print("wrote", WORK / "analysis.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
