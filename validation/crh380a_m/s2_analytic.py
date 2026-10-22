"""S2 gate + matrix: is the analytic Jacobian right, and does BDF+analytic hold?

Two modes, both driven from the frozen full-run case so the physics is untouched.

  gate   -- compare `JacobianAssembler.blocks` against a central finite difference at
            the *equilibrated* state (the state BDF starts from and re-visits all the
            time).  A chain-rule error shows here as a per-column error near 1.0.
  matrix -- run DOP853 as the reference plus BDF+analytic at several (max_step, rtol)
            pairs, on a window or the whole 1.2 s, and print wall / nfev / peak.

Usage (PowerShell, from the Velch root):

    python -X utf8 validation\\crh380a_m\\s2_analytic.py gate
    python -X utf8 validation\\crh380a_m\\s2_analytic.py matrix --duration 0.05
    python -X utf8 validation\\crh380a_m\\s2_analytic.py matrix --duration 1.2
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "src"))

from velch.jacobian import frozen_geometry_error  # noqa: E402
from velch.model import RunSettings  # noqa: E402
from velch.vehicle import load_vehicle_case  # noqa: E402
from velch.vehicle_solver import (  # noqa: E402
    SimulationFailure,
    VehicleDynamics,
    _static_vertical_equilibrium,
    save_vehicle_result,
    simulate_vehicle,
)

BASE = HERE
SOURCE = BASE / "case_full12_cap05.json"
OUT = Path("F:/velch_tmp/s2")


def _equilibrated(case):
    """The static pose BDF starts from: same path the solver takes."""
    dynamics = VehicleDynamics(case)
    q = np.array(case.initial_q, dtype=float)
    v = np.array(case.initial_v, dtype=float)
    if case.equilibrate_vertical:
        q, residual = _static_vertical_equilibrium(case, dynamics, q, v)
        print(f"  static equilibrium residual {residual:+.3e} N")
    return dynamics, q, v


#: ``dq`` bound, ``dq`` worst-column bound, ``dq`` bad-column count bound per case.
#: These are *bounds on a known-open defect*, not an endorsement -- see the docstring
#: of :func:`compliant_gate`. Tightening them is the definition of "D4/C1 fixed".
COMPLIANT_GATE = (
    ("case_X_support.json", 1.0e-2, 1.5e0, 25.0),
    ("case_Y_full_support.json", 5.0e-2, 1.5e0, 25.0),
)


def compliant_gate() -> bool:
    """Bound the compliant-branch defect instead of letting it hide.

    The production gate below runs ``case_full12_cap05.json``, whose
    ``support_compliance`` is ``None`` -- which is exactly how two Jacobian defects
    (a wrong normalisation of the strip gradient and a spurious damping chain factor)
    survived a 325-test suite with 12 bad columns on every compliant case.

    Here ``dv`` must be exact (both defects that touched it are closed) while ``dq``
    is allowed a recorded residual: the roll/lateral cross-coupling at deep
    penetration, still open as D4/C1.  The numbers printed are the record.
    """
    print("\n--- compliant branch (support_compliance is not None) ---")
    print(f"{'case':>24}{'dq block':>11}{'dq col':>10}{'dq bad':>8}"
          f"{'dv block':>11}{'dv bad':>8}{'verdict':>11}")
    ok = True
    for name, dq_bound, column_bound, bad_bound in COMPLIANT_GATE:
        case = load_vehicle_case(BASE / name)
        dynamics, q, v = _equilibrated(case)
        try:
            assert case.support_compliance is not None, f"{name} is not a compliant case"
            report = frozen_geometry_error(dynamics, 0.0, q, v)
        finally:
            dynamics.close()
        dv_ok = (report["dv"] < 1.0e-6 and report["dv_worst_column"] < 1.0e-6
                 and report["dv_bad_columns"] == 0.0)
        dq_ok = (report["dq"] < dq_bound and report["dq_worst_column"] < column_bound
                 and report["dq_bad_columns"] <= bad_bound)
        good = dv_ok and dq_ok
        ok = ok and good
        print(f"{name:>24}{report['dq']:>11.2e}{report['dq_worst_column']:>10.2e}"
              f"{report['dq_bad_columns']:>8.0f}{report['dv']:>11.2e}"
              f"{report['dv_bad_columns']:>8.0f}{'BOUNDED' if good else 'FAIL':>11}")
    print("COMPLIANT", "BOUNDED (dq residual = open D4/C1)" if ok else "FAIL")
    return ok


def gate() -> int:
    case = load_vehicle_case(SOURCE)
    dynamics, q, v = _equilibrated(case)
    ok = True
    try:
        print(f"\n{'t s':>7}{'dq block':>11}{'dv block':>11}"
              f"{'dq col':>10}{'dv col':>10}{'bad cols':>10}{'verdict':>10}")
        for t_s in (0.0, 0.2, 0.45, 0.7, 1.0, 1.19):
            report = frozen_geometry_error(dynamics, t_s, q, v)
            dq = report["dq"]
            dv = report["dv"]
            dq_col = report["dq_worst_column"]
            dv_col = report["dv_worst_column"]
            bad = report["dq_bad_columns"] + report["dv_bad_columns"]
            good = dq_col < 1.0e-5 and dv_col < 1.0e-5 and bad == 0
            ok = ok and good
            print(f"{t_s:>7.2f}{dq:>11.2e}{dv:>11.2e}{dq_col:>10.2e}"
                  f"{dv_col:>10.2e}{bad:>10.0f}{'PASS' if good else 'FAIL':>10}")
    finally:
        dynamics.close()
    ok = compliant_gate() and ok
    print("\nGATE", "PASS" if ok else "FAIL")
    return 0 if ok else 1


def _run(tag: str, method: str, jacobian: str | None, duration: float,
         max_step: float, rtol: float, x_start: float | None = None) -> dict[str, object]:
    raw = json.loads(SOURCE.read_text(encoding="utf-8"))
    raw["case_id"] = f"s2_{tag}"
    raw["run"]["method"] = method
    raw["run"]["jacobian"] = jacobian
    raw["run"]["duration_s"] = duration
    raw["run"]["max_solver_step_s"] = max_step
    raw["run"]["rtol"] = rtol
    raw["run"]["atol"] = min(1.0e-8, rtol * 1.0e-2)
    if x_start is not None:
        # The frozen full run starts at x = 13.5 m, on plain straight track: a 0.05 s
        # window there never reaches a profile change and only ever sees the static
        # load.  The documented 0.05 s reference window is x = 69.0 .. 73.9 m, so the
        # start has to be movable for that comparison to be reproducible at all.
        raw["run"]["x_start_m"] = float(x_start)
    path = BASE / f"case_{raw['case_id']}.json"
    path.write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")
    case = load_vehicle_case(path)
    started = time.perf_counter()
    try:
        result = simulate_vehicle(case)
    except SimulationFailure as error:
        return {"tag": tag, "failed": f"{type(error).__name__}: {error}",
                "wall_s": time.perf_counter() - started}
    wall = time.perf_counter() - started
    save_vehicle_result(case, result, OUT / raw["case_id"])
    summary = dict(getattr(result, "summary", {}) or {})
    peaks = summary.get("peak_normal_force_n", {})
    # The vehicle solver nests the counter under ``summary["solver"]`` and spells the
    # depth ``max_penetration_m``; the flat ``nfev``/``maximum_penetration_m`` names
    # are what the single-body solver uses.
    max_pen = summary.get("max_penetration_m",
                          summary.get("maximum_penetration_m", float("nan")))
    rail = "axle1_right"
    peak = peaks.get(rail) if isinstance(peaks, dict) else None
    return {
        "tag": tag, "wall_s": wall,
        "nfev": (summary.get("solver") or {}).get("nfev", summary.get("nfev")),
        "peak_kn": (float(peak) / 1000.0) if peak is not None else float("nan"),
        "max_pen_um": float(max_pen) * 1e6 if max_pen is not None else float("nan"),
        "status": summary.get("result_status"),
    }


def matrix(duration: float, x_start: float | None = None) -> int:
    print(f"\nsource {SOURCE.name}  duration {duration} s  out {OUT}")
    if x_start is not None:
        print(f"window start x = {x_start:.3f} m")
    variants = [
        ("dop853", "DOP853", None, 1.0e-4, 1.0e-6),
        ("bdf_an_ms1e-4", "BDF", "analytic", 1.0e-4, 1.0e-6),
        ("bdf_an_ms5e-4", "BDF", "analytic", 5.0e-4, 1.0e-6),
        ("bdf_an_ms2e-3", "BDF", "analytic", 2.0e-3, 1.0e-6),
        ("bdf_an_rtol1e-4", "BDF", "analytic", 2.0e-3, 1.0e-4),
    ]
    print(f"\n{'variant':>16}{'wall s':>9}{'nfev':>8}{'peak kN':>10}"
          f"{'maxpen um':>11}{'status':>22}")
    rows = []
    for tag, method, jacobian, max_step, rtol in variants:
        row = _run(tag, method, jacobian, duration, max_step, rtol, x_start)
        rows.append(row)
        if "failed" in row:
            print(f"{tag:>16}{row['wall_s']:>9.1f}{'':>8}{'':>10}{'':>11}"
                  f"  FAILED {row['failed'][:60]}")
        else:
            print(f"{tag:>16}{row['wall_s']:>9.1f}{str(row['nfev']):>8}"
                  f"{row['peak_kn']:>10.2f}{row['max_pen_um']:>11.2f}"
                  f"{str(row['status']):>22}")
    print()
    for row in rows:
        print(" ", row)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="mode", required=True)
    sub.add_parser("gate")
    run_parser = sub.add_parser("matrix")
    run_parser.add_argument("--duration", type=float, default=0.05)
    run_parser.add_argument("--x-start", type=float, default=None,
                            help="override the case's window start (the documented "
                                 "0.05 s reference window is x = 69.0 m)")
    args = parser.parse_args()
    if args.mode == "gate":
        return gate()
    return matrix(args.duration, args.x_start)


if __name__ == "__main__":
    raise SystemExit(main())
