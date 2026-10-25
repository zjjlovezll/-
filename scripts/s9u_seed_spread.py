"""How much does the band inversion move when only the random track changes?

The 6/8-within-2-dB result in `docs/BAND_CAPABILITY_2026-10-26.md` §11 comes from
ONE test realisation.  A single realisation cannot tell a property of the method
from a property of that draw, so this script re-runs the *test* track with three
different seeds (same spectrum shape, different phases) against the operator
already measured in `F:\\velch_tmp\\s9s\\operator.json`, and reports the per-band
recovered amplitude, error and the seed-to-seed spread.

Run:  python -X utf8 scripts/s9u_seed_spread.py
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
import s9t_band_average_analysis as s9t  # noqa: E402
import s9s_bandaverage_operator as s9s  # noqa: E402

WORK = pathlib.Path(r"F:\velch_tmp\s9u")
OPERATOR = pathlib.Path(r"F:\velch_tmp\s9s\operator.json")
SEEDS = (20261026, 777001, 424242)


def main() -> int:
    WORK.mkdir(parents=True, exist_ok=True)
    s9k.WORK = WORK
    s9s.WORK = WORK
    s9t.WORK = WORK
    state = json.loads(OPERATOR.read_text(encoding="utf-8"))
    labels = list(state["labels"])
    operator = np.array([state["matrix"][label] for label in labels], dtype=float)

    results = []
    for seed in SEEDS:
        label = f"test_{seed}"
        track = s9k.flat_track(seed=seed, scales=s9k.TEST_SCALES)
        truth = np.array([float(s9k.profile_band_rms(track)[name]) for name in labels], dtype=float)
        measured, _seconds, status = s9s.run_pair(track, label)
        if status != "numerically_checked":
            raise SystemExit(f"seed {seed} did not converge: {status}")
        response = np.array([float(measured[name]) for name in labels], dtype=float)
        unconstrained, *_ = np.linalg.lstsq(operator.T, response, rcond=None)
        constrained = s9t.non_negative(operator.T, response)
        predicted = operator.T @ truth
        error = float(np.linalg.norm(predicted - response) / np.linalg.norm(response))
        print(f"seed {seed}: superposition {error * 100:.1f} %")
        results.append({"seed": seed, "truth_um": (truth * 1e6).tolist(),
                        "full_um": (unconstrained * 1e6).tolist(),
                        "positive_um": (constrained * 1e6).tolist(),
                        "superposition": error})

    truth = np.array(results[0]["truth_um"], dtype=float)
    print(f"\n{'band':>10} {'truth um':>9} " + " ".join(f"{'seed' + str(index + 1):>9}" for index in range(len(results)))
          + f" {'spread':>7}")
    rows = []
    for position, label in enumerate(labels):
        values = [float(result["positive_um"][position]) for result in results]
        mean = float(np.mean(values))
        spread = float(np.std(values) / mean) if mean > 0 else float("nan")
        print(f"{label:>10} {truth[position]:9.3f} " + " ".join(f"{value:9.3f}" for value in values)
              + f" {spread * 100:6.1f}%")
        rows.append({"band": label, "truth_um": float(truth[position]), "positive_um": values,
                     "mean_um": mean, "spread_percent": spread * 100.0,
                     "mean_error_percent": (mean - float(truth[position])) / float(truth[position]) * 100.0})

    passing = [row for row in rows
               if abs(20.0 * math.log10(row["mean_um"] / row["truth_um"])) <= 2.0] if all(
        row["mean_um"] > 0 for row in rows) else []
    print(f"\nbands whose MEAN (three seeds) is within 2 dB: {len(passing)}/{len(rows)}")
    worst = max(rows, key=lambda row: abs(row["spread_percent"]))
    print(f"worst seed-to-seed spread: {worst['band']} {worst['spread_percent']:.1f} %")
    (WORK / "seed_spread.json").write_text(json.dumps({"seeds": list(SEEDS), "results": results, "rows": rows},
                                                      indent=2, ensure_ascii=False), encoding="utf-8")
    print("wrote", WORK / "seed_spread.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
