"""Does the 1.945 % long-wave calibration depend on the target's phase?

`scripts/s9_inversion.py` draws ONE target phase from the RNG, so its 1.945 %
calibration is a single draw.  The short-wave round learned that this matters
(three seeds moved 6/8 to 5/8), so the same question is asked here: replay the
target differential at three phases, reusing the already-measured H columns, and
report the calibration and per-band errors per phase.

The RNG's own phase is included first, so the published number must reproduce.

Run:  python -X utf8 scripts/s9y_longwave_phases.py [--phases 3]
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

import s9_inversion as inversion  # noqa: E402

WORK = pathlib.Path(r"F:\velch_tmp\s9i")
VARIANT = "V"


def main() -> int:
    count = 3
    if "--phases" in sys.argv:
        count = int(sys.argv[sys.argv.index("--phases") + 1])
    inversion.WORK = WORK
    protocol = inversion.protocol
    protocol.WORK = WORK
    protocol.BANDS = inversion.BANDS
    protocol.SPEED = inversion.SPEED
    protocol.DURATION_S = inversion.DURATION_S

    base = inversion.flexible_base()
    length = inversion.DURATION_S * inversion.SPEED + 30.0
    columns = inversion.load_columns()
    blocks = {label: np.column_stack([columns[str(band)][label] for band in inversion.BANDS])
              for label in protocol.CHANNELS}
    matrix = protocol.assemble(blocks, inversion.VARIANTS[VARIANT])
    truth = inversion.SHAPE * inversion.AMPLITUDE_M

    rng = np.random.default_rng(20261025)
    published = float(rng.uniform(0.0, 2.0 * np.pi))
    phases = [published] + [published + index * 2.0 * np.pi / count for index in range(1, count)]

    started = time.perf_counter()
    rows = []
    print(f"{'phase rad':>10} {'calibration':>12} {'band 20 m':>10} {'band 40 m':>10} {'recovered mm':>14}")
    for index, phase in enumerate(phases):
        label = f"phase{index}"
        target = protocol.differential(label, dict(zip(inversion.BANDS, truth)), float(phase), base, length)
        measured = protocol.stack_measured(target, inversion.VARIANTS[VARIANT])
        recovered = protocol.solve(matrix, measured, balanced=True)
        calibration = float(protocol.magnitude_error(recovered, truth))
        bands = [float(value) for value in protocol.per_band_error(recovered, truth)]
        recovered_mm = [float(abs(value) * 1e3) for value in recovered]
        print(f"{phase:10.4f} {calibration:11.1%} {bands[0]:+9.1%} {bands[1]:+9.1%} "
              + "/".join(f"{value:6.4f}" for value in recovered_mm), flush=True)
        rows.append({"phase_rad": float(phase), "calibration": calibration, "band_errors": bands,
                     "recovered_mm": recovered_mm,
                     "elapsed_s": time.perf_counter() - started})

    values = np.array([row["calibration"] for row in rows], dtype=float)
    print(f"\ncalibration over {len(rows)} phases: mean {values.mean():.3%} "
          f"min {values.min():.3%} max {values.max():.3%} spread {(values.max() - values.min()):.3%}")
    print(f"truth {truth[0] * 1e3:.4f} / {truth[1] * 1e3:.4f} mm")
    (WORK / "phases.json").write_text(json.dumps({"variant": VARIANT, "rows": rows,
                                                  "truth_mm": [float(value * 1e3) for value in truth]},
                                                 indent=2, ensure_ascii=False), encoding="utf-8")
    print("wrote", WORK / "phases.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
