"""S2 acceptance run: the whole 1.2 s with BDF + analytic Jacobian.

Only the variants that matter for the gate are run, so this does not pay for the
DOP853 reference again (it is frozen at 850 s / 89.7 kN).
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from s2_analytic import _run  # noqa: E402

VARIANTS = [
    ("full_bdf_an_rtol1e-5", "BDF", "analytic", 1.2e0, 2.0e-3, 1.0e-5),
    ("full_bdf_an_rtol1e-6", "BDF", "analytic", 1.2e0, 2.0e-3, 1.0e-6),
]

print(f"{'variant':>24}{'wall s':>9}{'nfev':>8}{'peak kN':>10}{'maxpen um':>11}{'status':>24}")
for tag, method, jacobian, duration, max_step, rtol in VARIANTS:
    row = _run(tag, method, jacobian, duration, max_step, rtol)
    if "failed" in row:
        print(f"{tag:>24}{row['wall_s']:>9.1f}{'':>8}{'':>10}{'':>11}  FAILED {row['failed'][:70]}",
              flush=True)
    else:
        print(f"{tag:>24}{row['wall_s']:>9.1f}{row['nfev']:>8}{row['peak_kn']:>10.2f}"
              f"{row['max_pen_um']:>11.2f}{str(row['status']):>24}", flush=True)
