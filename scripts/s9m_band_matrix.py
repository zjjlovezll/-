"""Measure the per-band operator as a full 8x8 matrix, then invert a random spectrum with it.

S9-12 (`scripts/s9l_differential_bands.py`) used the **diagonal** transfer only: every band's
response was divided by its own gain.  Two of eight bands met the 2 dB criterion, and the quiet
bands (truth 2-3 um) all came back at 4-16 um no matter what the truth was.  That was read as a
"crosstalk floor", but a diagonal inversion cannot tell the difference between

  (a) there is no information about the quiet band, and
  (b) there is information, but it arrived under a neighbour's name.

This script separates the two.  For every octave band it emits a **single tone** at the band's
geometric centre wavelength, runs the ``+A / -A`` differential (so the start-up transient, the
ring of the vehicle's own modes and the rail geometry cancel exactly), and records the response
band rms in **all eight** bands.  Those eight numbers are one row of the operator ``M``:

    y_j = sum_i M[j, i] * r_i          M in (m/s^2)/m,  r in m

The off-diagonals are the leakage that the diagonal model threw away.  Then the same random test
track as S9-12 is inverted twice -- with ``diag(M)`` and with the full ``M`` -- and the two are
compared on the pre-registered 2 dB criterion.

Pre-registered reading:

  * full matrix passes where the diagonal fails  -> the earlier negative result was about the
    *model* (a diagonal one), not about the information; broadband whole-spectrum inversion is
    viable once the operator is measured properly.
  * both fail, and ``cond(M)`` is large          -> the leakage is real coupling, not relabelling;
    the quiet bands are genuinely below the floor and the conclusion of S9-12 stands.

    python -X utf8 scripts/s9m_band_matrix.py

Writes ``F:\\velch_tmp\\s9m\\matrix.json`` after every probe, so an interrupted run is still useful.
"""

from __future__ import annotations

import json
import math
import pathlib
import sys

import numpy as np

REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

import s9k_random_spectrum as s9k  # noqa: E402
import s9l_differential_bands as s9l  # noqa: E402

from velch.irregularity import IrregularityTrack  # noqa: E402

WORK = pathlib.Path(r"F:\velch_tmp\s9m")
PROBE_AMPLITUDE_M = 10.0e-6
DURATION_S = 2.0

# Both helpers write their own files, so point them at this run's directory.
s9k.WORK = WORK
s9l.WORK = WORK
s9k.DURATION_S = DURATION_S
s9l.DURATION_S = DURATION_S


def band_labels() -> list[str]:
    """Band keys in the order the helpers produce them."""
    return list(s9k.profile_band_rms(s9k.zero_track()))


def tone_track(short_m: float, long_m: float, amplitude_m: float) -> IrregularityTrack:
    """One sinusoid at the octave band's geometric centre wavelength."""
    wavelength = math.sqrt(short_m * long_m)
    step = float(s9k.TRE_STEP_M)
    count = int(round(float(s9k.LENGTH_M) / step)) + 1
    station = np.arange(count, dtype=float) * step
    vertical = amplitude_m * np.sin(2.0 * math.pi * station / wavelength)
    zeros = np.zeros_like(station)
    return IrregularityTrack(
        s_m=station,
        lateral_m=zeros.copy(),
        vertical_m=vertical,
        roll_rad=zeros.copy(),
        gauge_m=zeros.copy(),
        source=f"generated: tone {wavelength * 1000.0:.1f} mm, {amplitude_m * 1e6:.1f} um",
    )


def main() -> int:
    WORK.mkdir(parents=True, exist_ok=True)
    store = WORK / "matrix.json"
    state: dict[str, object] = json.loads(store.read_text(encoding="utf-8")) if store.exists() else {}
    labels = band_labels()
    bands = s9k.octave_bands()
    if len(labels) != len(bands):
        raise SystemExit(f"band count mismatch: {len(labels)} labels vs {len(bands)} octaves")

    matrix: dict[str, list[float]] = state.setdefault("matrix", {})  # type: ignore[assignment]
    for index, (short_m, long_m) in enumerate(bands):
        key = labels[index]
        if key in matrix:
            continue
        track = tone_track(short_m, long_m, PROBE_AMPLITUDE_M)
        response, seconds, status = s9l.run_pair(track, f"p{index:02d}")
        if status != "numerically_checked":
            raise SystemExit(f"probe {key} did not converge: {status}")
        # Reviewer D5: the probe's *peak* is PROBE_AMPLITUDE_M, so the gain per unit
        # input rms is this row times sqrt(2).  Stating it this way keeps every later
        # comparison (which regresses on band rms) on one convention.
        input_rms = PROBE_AMPLITUDE_M / math.sqrt(2.0)
        matrix[key] = [float(response[label]) / input_rms for label in labels]
        state["labels"] = labels
        state["probe_amplitude_m"] = PROBE_AMPLITUDE_M
        state["duration_s"] = DURATION_S
        store.write_text(json.dumps(state, indent=2), encoding="utf-8")
        print(f"probe {key:>10s} ({seconds:5.0f} s): "
              + " ".join(f"{value:9.2f}" for value in matrix[key]), flush=True)

    operator = np.array([matrix[label] for label in labels], dtype=float)
    print("\nM (rows = excited band, cols = response band), (m/s^2)/m")
    print("  " + " " * 10 + " ".join(f"{label:>9s}" for label in labels))
    for label, row in zip(labels, operator):
        print(f"  {label:>10s} " + " ".join(f"{value:9.1f}" for value in row))
    singular = np.linalg.svd(operator, compute_uv=False)
    condition = float(np.linalg.cond(operator))
    print(f"\ncond(M) = {condition:.4g}   singular = {np.array2string(singular, precision=3)}")
    state["singular_values"] = [float(value) for value in singular]
    state["condition_number"] = condition

    test = s9k.flat_track(seed=s9k.SEED_TEST, scales=s9k.TEST_SCALES)
    measured, seconds, status = s9l.run_pair(test, "test")
    if status != "numerically_checked":
        raise SystemExit(f"test run did not converge: {status}")
    truth = np.array([float(s9k.profile_band_rms(test)[label]) for label in labels], dtype=float)
    response = np.array([float(measured[label]) for label in labels], dtype=float)

    diagonal = np.diag(operator).copy()
    recovered_diagonal = response / diagonal
    recovered_full = np.linalg.solve(operator, response)

    rows = []
    for index, label in enumerate(labels):
        rows.append(
            {
                "band": label,
                "truth_um": truth[index] * 1e6,
                "diagonal_um": recovered_diagonal[index] * 1e6,
                "full_um": recovered_full[index] * 1e6,
                "diagonal_db": 20.0 * math.log10(abs(recovered_diagonal[index]) / truth[index]),
                "full_db": 20.0 * math.log10(abs(recovered_full[index]) / truth[index]),
            }
        )
    print(f"\n{'band':>10} {'truth':>8} {'diag-only':>10} {'dB':>7} {'full':>10} {'dB':>7}")
    for row in rows:
        print(f"  {row['band']:>10} {row['truth_um']:8.3f} {row['diagonal_um']:10.3f} "
              f"{row['diagonal_db']:+7.2f} {row['full_um']:10.3f} {row['full_db']:+7.2f}")
    passed_diagonal = sum(1 for row in rows if abs(row["diagonal_db"]) <= 2.0)
    passed_full = sum(1 for row in rows if abs(row["full_db"]) <= 2.0)
    print(f"\nwithin 2 dB: diagonal {passed_diagonal}/{len(rows)}, full matrix {passed_full}/{len(rows)}")

    state["test"] = {
        "bands": labels,
        "rows": rows,
        "within_2db_diagonal": passed_diagonal,
        "within_2db_full": passed_full,
        "seconds": seconds,
    }
    store.write_text(json.dumps(state, indent=2), encoding="utf-8")
    print("wrote", store)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
