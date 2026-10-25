"""Score the per-band operator against a random track, from stored runs only.

`scripts/s9m_band_matrix.py` spends about forty minutes of simulation to build an
8x8 operator: one tone at the centre of each octave band, and the response band
rms in every band.  This script answers the question that operator exists for --
does it predict a *broadband* random track? -- and it answers it from what is
already on disk (the matrix json plus the two test runs), in about a second.

Two things it fixes, both of which change the answer:

1. Orientation.  The stored matrix has **rows = excited band, columns = response
   band**, so the response to a track whose band amplitudes are ``r`` is
   ``M.T @ r``, not ``M @ r``.  Getting this wrong once produced a 67.7 %
   "superposition error" that was really an artefact of the transpose.
2. Convention.  One tone at the octave centre is not the octave average: inside
   a band the response rises steeply (short waves go as frequency squared), so a
   centre-tone operator under-predicts a band filled across its width.  That is
   why the operator is scored *and* its bias reported band by band, rather than
   only being inverted.

Run with PYTHONPATH=src;scripts.
"""

from __future__ import annotations

import json
import pathlib
import sys

import numpy as np

import s9k_random_spectrum as s9k

HERE = pathlib.Path(__file__).resolve().parents[1]
WORK = pathlib.Path(r"F:\velch_tmp\s9m")
MATRIX = WORK / "matrix.json"
CHANNEL = "axle1_box_left_z_acc_m_per_s2"
WITHIN_DB = 2.0


def load_matrix(path: pathlib.Path) -> tuple[list[str], np.ndarray]:
    state = json.loads(path.read_text(encoding="utf-8"))
    labels = list(state["labels"])
    matrix = np.array([state["matrix"][label] for label in labels], dtype=float)
    return labels, matrix


def differential_channel(folder: pathlib.Path) -> np.ndarray:
    """Half the difference of the +A and -A runs, i.e. the response to A alone."""
    from velch.io.history import read_history

    def read(name: str) -> tuple[np.ndarray, float]:
        table = read_history(folder / name / "history.csv")
        names = list(table.ordering)
        time = np.asarray(table.data[names.index("time_s")], float)
        values = np.asarray(table.data[names.index(CHANNEL)], float)
        return values, 1.0 / float(np.mean(np.diff(time)))

    plus, rate = read("out_test_plus")
    minus, _ = read("out_test_minus")
    return s9k.acceleration_band_rms(0.5 * (plus - minus), rate)


def score(labels: list[str], matrix: np.ndarray) -> int:
    response = differential_channel(WORK)
    measured = np.array([float(response[label]) for label in labels])
    profile = s9k.profile_band_rms(s9k.flat_track(seed=s9k.SEED_TEST, scales=s9k.TEST_SCALES))
    truth = np.array([float(profile[label]) for label in labels])

    predicted = matrix.T @ truth
    error = float(np.linalg.norm(predicted - measured) / np.linalg.norm(measured))

    print(f"{'band':>10} {'truth um':>9} {'predicted':>10} {'measured':>10} {'ratio':>7} {'dB':>7}")
    for index, label in enumerate(labels):
        ratio = measured[index] / predicted[index] if predicted[index] else float("nan")
        print(
            f"{label:>10} {truth[index] * 1e6:9.3f} {predicted[index]:10.4f} "
            f"{measured[index]:10.4f} {ratio:7.2f} {20 * np.log10(ratio):7.2f}"
        )
    print()
    print(
        f"superposition error = {error * 100:.1f} %   "
        f"Pearson = {np.corrcoef(predicted, measured)[0, 1]:.3f}"
    )
    print()

    best = 0
    for name, operator in (
        ("diagonal", np.diag(np.diag(matrix))),
        ("full", matrix),
    ):
        solution, *_ = np.linalg.lstsq(operator.T, measured, rcond=None)
        columns = []
        within = 0
        for index, label in enumerate(labels):
            estimate = abs(float(solution[index]))
            decibels = 20 * np.log10(estimate / truth[index]) if estimate > 0 else float("inf")
            within += abs(decibels) <= WITHIN_DB
            columns.append(f"{estimate * 1e6:8.2f}/{decibels:+6.2f}")
        best = max(best, within)
        print(f"{name:>9}: within {WITHIN_DB:.0f} dB {within}/{len(labels)} | " + " ".join(columns))
    print()
    print(f"verdict: {'a linear band operator can invert the spectrum' if best == len(labels) else 'no band operator here reproduces a broadband track'}")
    return 0


def main() -> int:
    if not MATRIX.exists():
        print(f"missing {MATRIX}: run scripts/s9m_band_matrix.py first", file=sys.stderr)
        return 2
    labels, matrix = load_matrix(MATRIX)
    print(f"operator from {MATRIX} (rows = excited band, columns = response band)")
    print(f"condition number {np.linalg.cond(matrix):.1f}")
    print()
    return score(labels, matrix)


if __name__ == "__main__":
    raise SystemExit(main())
