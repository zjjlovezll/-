"""Process-level parallelism for independent vehicle cases.

One trajectory is a serial initial value problem: the state at t + dt needs the
state at t, so a single run cannot be split across cores.  The parallel axis is
therefore *cases* -- a sweep, a parametric study or one inversion batch.  Every
worker process loads its own case and writes its own output directory, so no
state is shared and the speed-up is close to the core count.
"""
from __future__ import annotations

import time
import traceback
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from .vehicle import load_vehicle_case
from .vehicle_solver import save_vehicle_result, simulate_vehicle


def _solve_case(payload: tuple[str, str, int]) -> dict:
    case_path, out_dir, workers = payload
    started = time.perf_counter()
    try:
        case = load_vehicle_case(Path(case_path))
        result = simulate_vehicle(case, contact_workers=workers)
        csv_path, manifest_path = save_vehicle_result(case, result, Path(out_dir))
    except Exception as exc:  # a failed case must not abort the other cases
        return {"case": case_path, "output": out_dir, "result_status": "failed",
                "error_type": type(exc).__name__, "message": str(exc),
                "wall_s": round(time.perf_counter() - started, 3),
                "traceback": traceback.format_exc(limit=3)}
    return {"case": case_path, "output": out_dir,
            "history": str(csv_path), "manifest": str(manifest_path),
            "result_status": result.summary["result_status"],
            "nfev": result.summary.get("solver", {}).get("nfev"),
            "wall_s": round(time.perf_counter() - started, 3)}


def run_vehicle_batch(case_paths, output_root, *, jobs: int = 1, workers: int = 1) -> dict:
    """Solve ``case_paths`` with up to ``jobs`` concurrent processes."""
    output_root = Path(output_root)
    output_root.mkdir(parents=True, exist_ok=True)
    payloads = [(str(Path(path)), str(output_root / Path(path).stem), int(workers))
                for path in case_paths]
    started = time.perf_counter()
    if jobs <= 1 or len(payloads) <= 1:
        cases = [_solve_case(item) for item in payloads]
    else:
        with ProcessPoolExecutor(max_workers=int(jobs)) as pool:
            cases = list(pool.map(_solve_case, payloads))
    serial = sum(item["wall_s"] for item in cases)
    return {
        "jobs": int(jobs),
        "contact_workers": int(workers),
        "case_count": len(payloads),
        "wall_s": round(time.perf_counter() - started, 3),
        "summed_case_wall_s": round(serial, 3),
        "effective_speedup": round(serial / max(1e-9, time.perf_counter() - started), 3),
        "cases": cases,
    }
