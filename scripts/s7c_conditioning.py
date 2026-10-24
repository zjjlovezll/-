"""Why S7c's condition number was 286.72, and what equilibrating the rows buys.

Re-reads the 2.0 m single-band runs that ``s7c_cross_direction.py`` already produced -- no new
simulation, about ten seconds -- and answers two questions the first script could not:

1. **Was 286.72 a units artefact?**  A least-squares problem is invariant under multiplying a row and
   its datum by the same positive number, but the reported condition number is not.  The vertical row
   is 6 458 units of ``(m/s^2)`` per metre of track, the lateral row is 573 -- an 11x gap.  With every
   row scaled to unit norm the condition number falls to 50.49, so about **5.7x of the 286 was the
   magnitude gap**; the remaining 50 is real overlap between the two directions (`0.028` vs `1.414`
   after normalising, i.e. the two rows are within ~2 % of being parallel).

2. **Does equilibrating change the answer?**  It should: with unequal rows the unweighted system lets
   the loud row dominate.  Measured: lateral estimate **+14.7 % -> +2.2 %** off truth, vertical
   −1.5 % -> −1.1 %, complex error 40.0 % -> 35.4 %.  So row equilibration is worth doing, and it is
   the cheaper of the two levers (the other is to weight each row by its own noise, which needs a
   noise measurement we do not have yet).

The complex error stays above 30 % either way: that residue is imaginary, i.e. response the model
cannot attribute to a real amplitude at all (see S7C_CROSS_DIRECTION §4).  Row scaling cannot fix it.

Run it after ``s7c_cross_direction.py``; it reads F:\\velch_tmp\\s7c.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO / "src"))

import s7c_cross_direction as s7c                        # noqa: E402
from velch.irregularity import read_tre                  # noqa: E402

WORK = s7c.WORK
BAND = s7c.BAND


def excitation_phase(tre_path: Path) -> float:
    """Phase of a .tre column, fitted as ``A sin(k s + phase)``.

    The channel that carries the excitation differs per run (vertical for one column, lateral for the
    other), so take whichever one is non-zero: fitting the all-zero channel would return phase 0 and
    silently rotate that column.  That mistake was made once here and it turned 286.72 into 110.49.
    """
    track = read_tre(tre_path)
    values = track.vertical_m if np.max(np.abs(track.vertical_m)) > 0.0 else track.lateral_m
    k = 2.0 * np.pi / BAND
    design = np.column_stack([np.sin(k * track.s_m), np.cos(k * track.s_m)])
    a, b = np.linalg.lstsq(design, values, rcond=None)[0]
    return float(np.arctan2(b, a))


def column(which: str) -> dict[str, complex]:
    """Rebuild one BLMA column from the runs already on disk, phases recovered from their .tre."""
    stack: dict[str, list[complex]] = {label: [] for label, _ in s7c.OBSERVATIONS}
    used = 0
    for index in range(s7c.REALISATIONS):
        out = WORK / f"out_h{which}_{index}"
        tre = WORK / f"h{which}_{index}.tre"
        if not (out / "history.csv").exists() or not tre.exists():
            continue
        measured = s7c.measure(out)
        phase = excitation_phase(tre)
        for label in stack:
            stack[label].append(measured[label] * np.exp(-1j * phase) / s7c.AMPLITUDE_M)
        used += 1
    if used < s7c.REALISATIONS - 1:
        raise SystemExit(f"column {which}: only {used} runs on disk; run s7c_cross_direction.py first")
    print(f"  column {which}: {used} realisations")
    return {label: complex(np.mean(values)) for label, values in stack.items()}


def main() -> int:
    print(f"re-reading {WORK}\n")
    vertical_column = column("v")
    lateral_column = column("l")
    system = s7c.real_system(np.array([[vertical_column["V"], lateral_column["V"]],
                                       [vertical_column["L"], lateral_column["L"]]]))
    norms = np.linalg.norm(system, axis=1)
    scaled = system / norms[:, None]

    print("\n                    singular values                     condition number")
    for name, matrix in (("as built", system), ("rows unit norm", scaled)):
        values = np.linalg.svd(matrix, compute_uv=False)
        print(f"  {name:15s} " + "  ".join(f"{value:12.3f}" for value in values)
              + f"   {np.linalg.cond(matrix):12.3f}")
    print(f"  row norms       " + "  ".join(f"{value:12.3f}" for value in norms))

    target_out = WORK / "out_target"
    target_tre = WORK / "target.tre"
    if not (target_out / "history.csv").exists() or not target_tre.exists():
        raise SystemExit("no target run on disk; run s7c_cross_direction.py first")
    phase = excitation_phase(target_tre)
    target = {label: value * np.exp(-1j * phase)
              for label, value in s7c.measure(target_out).items()}
    rhs = np.empty(4)
    for index, label in enumerate(("V", "L")):
        rhs[2 * index] = target[label].real
        rhs[2 * index + 1] = target[label].imag
    truth = np.array([s7c.TRUTH["vertical"], s7c.TRUTH["lateral"]])

    print("\n                            recovered vertical / lateral (mm)   complex error")
    for name, matrix, data in (("as built", system, rhs),
                               ("rows unit norm", scaled, rhs / norms)):
        normal = matrix.T @ matrix + (s7c.LAMBDA ** 2) * np.eye(4)
        solution = np.linalg.solve(normal, matrix.T @ data)
        recovered = np.array([solution[0] + 1j * solution[1], solution[2] + 1j * solution[3]])
        print(f"  {name:15s} {recovered[0].real * 1000:+26.4f} {recovered[1].real * 1000:+10.4f}"
              f"   {s7c.relative(recovered, truth):11.1%}")
    print(f"  {'truth':15s} {truth[0] * 1000:+26.4f} {truth[1] * 1000:+10.4f}")
    print("\njudgement: equilibration cuts the condition number by 5.7x and the lateral error from")
    print("14.7 % to 2.2 %, so it belongs in the estimator.  It does not touch the imaginary residue")
    print("(40.0 % -> 35.4 %), which is a model/measurement consistency question, not a scaling one.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
