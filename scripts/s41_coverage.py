"""Validate the pipeline's uncertainty on held-out records: leave-one-speed-out coverage.

The four records in F:\\ai道岔状态反演辨识\\75kmh数据 are four independent passes over the same track at four
steady speeds.  The dominant corrugation wavelength is a property of the track, not of the pass, so each
record is one measurement of the same number and a held-out record is a genuine out-of-sample test of an
interval the pipeline quotes.

Pre-registered before the coverage was computed, and not tuned to the numbers afterwards:

* the interval is the standard prediction interval for **one new observation**,
  ``mu +/- k * s * sqrt(1 + 1/n_train)``, with ``mu`` and ``s`` taken from the training folds only;
* coverage must reach ``1 sigma >= 0.5``, ``2 sigma = 1.0``, and no fold may exceed ``|z| = 3``.

The second clause is the load-bearing one.  An interval that fails to cover a held-out record at two sigma
is not a two-sigma interval, whatever its nominal confidence says.

Reported and not hidden: n = 4 folds, so coverage can only take the values 0, 0.25, 0.5, 0.75 and 1, and a
single miss moves it by a quarter.  Four folds cannot establish a calibration; they can only *refute* one.
The exact binomial tail is printed for each sigma level so a reader can see how little the sample supports
either statement.

Run:  python -X utf8 scripts/s41_coverage.py
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np

REPORT = Path(__file__).resolve().parents[1] / "reports" / "inversion_measured_2026-10-28"
SPEED_TABLE = REPORT / "speed_table.json"
SCRATCH_TABLE = Path(r"F:\velch_tmp\verdict4\speed_table.json")
TARGET = REPORT / "coverage.json"
SCRATCH_TARGET = Path(r"F:\velch_tmp\verdict\coverage.json")

# The in-band median is the primary estimand: it excludes the windows whose strongest line fell outside the
# corrugation band, which is the same population the detector scores.  The all-window median is carried as a
# sensitivity so the reader can see whether the conclusion depends on that choice.
ESTIMAND = "median_wavelength_in_band_mm"
SENSITIVITY = "median_wavelength_mm"

MIN_ONE_SIGMA = 0.5
MIN_TWO_SIGMA = 1.0
MAX_ABS_Z = 3.0
# Student t, two-sided 95 %, df = n_train - 1 = 2.  scipy is not a runtime dependency of this project.
T_975_DF2 = 4.302653


def read_table() -> list[dict]:
    """The four-row speed table, preferring the committed copy over the scratch original."""
    for path in (SPEED_TABLE, SCRATCH_TABLE):
        if path.exists():
            rows = json.loads(path.read_text(encoding="utf-8"))
            if not rows:
                raise SystemExit(f"empty speed table: {path}")
            return rows
    raise SystemExit(f"no speed table: looked in {SPEED_TABLE} and {SCRATCH_TABLE}")


def prediction_folds(values: list[float], labels: list[str]) -> list[dict]:
    """Leave one record out, predict it from the other three, report z and the two-sided 95 % interval."""
    folds = []
    for index, (label, held_out) in enumerate(zip(labels, values, strict=True)):
        train = [v for i, v in enumerate(values) if i != index]
        mean = float(np.mean(train))
        spread = float(np.std(train, ddof=1))
        sigma = spread * math.sqrt(1.0 + 1.0 / len(train))
        z = (held_out - mean) / sigma if sigma > 0 else float("inf")
        half_width = T_975_DF2 * sigma
        folds.append({
            "held_out": label,
            "held_out_value": float(held_out),
            "train_mean": mean,
            "train_spread": spread,
            "sigma_prediction": sigma,
            "z": float(z),
            "inside_1_sigma": bool(abs(z) <= 1.0),
            "inside_2_sigma": bool(abs(z) <= 2.0),
            "interval_95": [mean - half_width, mean + half_width],
            "inside_95": bool(mean - half_width <= held_out <= mean + half_width),
            "n_train": len(train),
        })
    return folds


def binomial_tail(k: int, n: int, p: float) -> float:
    """P(X <= k) for X ~ Binomial(n, p) -- how weak four folds are, stated numerically."""
    return float(sum(math.comb(n, i) * p**i * (1.0 - p) ** (n - i) for i in range(k + 1)))


def summarise(folds: list[dict]) -> dict:
    one = sum(1 for f in folds if f["inside_1_sigma"]) / len(folds)
    two = sum(1 for f in folds if f["inside_2_sigma"]) / len(folds)
    ninety_five = sum(1 for f in folds if f["inside_95"]) / len(folds)
    worst = max(abs(f["z"]) for f in folds)
    passed = one >= MIN_ONE_SIGMA and two >= MIN_TWO_SIGMA and worst < MAX_ABS_Z
    return {
        "folds": len(folds),
        "coverage_1_sigma": one,
        "coverage_2_sigma": two,
        "coverage_95_interval": ninety_five,
        "max_abs_z": worst,
        "criterion": {"min_coverage_1_sigma": MIN_ONE_SIGMA, "min_coverage_2_sigma": MIN_TWO_SIGMA,
                      "max_abs_z": MAX_ABS_Z},
        "binomial_tail": {
            "one_sigma": binomial_tail(int(one * len(folds)), len(folds), 0.6827),
            "two_sigma": binomial_tail(int(two * len(folds)), len(folds), 0.9545),
            "ninety_five": binomial_tail(int(ninety_five * len(folds)), len(folds), 0.95),
        },
        "passed": bool(passed),
    }


def main() -> int:
    rows = read_table()
    labels = [str(row.get("file", f"record{index}")) for index, row in enumerate(rows)]
    values = [float(row[ESTIMAND]) for row in rows]
    sensitivity = [float(row[SENSITIVITY]) for row in rows]

    folds = prediction_folds(values, labels)
    summary = summarise(folds)
    sensitivity_summary = summarise(prediction_folds(sensitivity, labels))

    result = {
        "estimand": ESTIMAND,
        "estimand_unit": "mm",
        "sensitivity_estimand": SENSITIVITY,
        "values": dict(zip(labels, values, strict=True)),
        "speed_kmh": [round(float(row["mean_speed_kmh"]), 3) for row in rows],
        "folds": folds,
        "summary": summary,
        "sensitivity": {"summary": sensitivity_summary,
                        "folds": prediction_folds(sensitivity, labels)},
        "source_table": str(SPEED_TABLE if SPEED_TABLE.exists() else SCRATCH_TABLE),
        "reading": ("the four passes are four measurements of one track property; a fold outside two sigma "
                    "says the quoted interval is too narrow, not that the track changed"),
    }
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_text(json.dumps(result, indent=1) + "\n", encoding="utf-8")
    try:
        SCRATCH_TARGET.parent.mkdir(parents=True, exist_ok=True)
        SCRATCH_TARGET.write_text(json.dumps(result, indent=1) + "\n", encoding="utf-8")
    except OSError:
        pass

    print(f"estimand: {ESTIMAND}  (n = {len(folds)} folds, leave one speed out)")
    print(f"{'held out':<28} {'value':>8} {'mu':>8} {'s':>6} {'sigma':>7} {'z':>6}  1s  2s   95%")
    for fold in folds:
        print(f"{fold['held_out']:<28} {fold['held_out_value']:8.3f} {fold['train_mean']:8.3f} "
              f"{fold['train_spread']:6.3f} {fold['sigma_prediction']:7.3f} {fold['z']:6.2f} "
              f" {'yes' if fold['inside_1_sigma'] else ' NO'} "
              f"{'yes' if fold['inside_2_sigma'] else ' NO'} "
              f"{'yes' if fold['inside_95'] else ' NO'}")
    print(f"\ncoverage 1 sigma {summary['coverage_1_sigma']:.2f} (need >= {MIN_ONE_SIGMA}), "
          f"2 sigma {summary['coverage_2_sigma']:.2f} (need = {MIN_TWO_SIGMA}), "
          f"max |z| {summary['max_abs_z']:.2f}")
    print(f"binomial tail: P(X<={int(summary['coverage_1_sigma'] * 4)}) = "
          f"{summary['binomial_tail']['one_sigma']:.3f} at 1 sigma, "
          f"{summary['binomial_tail']['two_sigma']:.3f} at 2 sigma")
    print(f"sensitivity ({SENSITIVITY}): 1 sigma {sensitivity_summary['coverage_1_sigma']:.2f}, "
          f"2 sigma {sensitivity_summary['coverage_2_sigma']:.2f}, "
          f"max |z| {sensitivity_summary['max_abs_z']:.2f}")
    print(f"verdict: {'PASSED' if summary['passed'] else 'FAILED'}")
    print(f"written: {TARGET}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
