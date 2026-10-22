"""B2 measurement: does the adaptive solver already resolve contact onsets, or does
the 48.6 mm output spacing smear them?

Same case, same window, only ``run.output_step_s`` changes (5e-4 -> 5e-5).  If the
peak force / impulse / rms move by more than the oracle tolerance, an event-aware
integration has something to fix; if they do not, B2 is unnecessary work.

Run:  python -X utf8 validation/crh380a_m/probe_event_resolution.py
"""

from __future__ import annotations

import json
import pathlib
import shutil
import statistics
import subprocess
import sys

import numpy as np

BASE = pathlib.Path(__file__).resolve().parent
VELCH = BASE.parents[1]
PYTHON = sys.executable
SOURCE_CASE = BASE / "case_frog_N_strip05.json"


def run_case(tag: str, output_step: float) -> pathlib.Path:
    payload = json.loads(SOURCE_CASE.read_text(encoding="utf-8"))
    payload["id"] = f"B2_{tag}"
    payload.setdefault("run", {})["output_step_s"] = output_step
    case_path = BASE / f"case_B2_{tag}.json"
    case_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    out = BASE / f"out_B2_{tag}"
    if out.exists():
        shutil.rmtree(out)
    command = [
        PYTHON,
        "-X",
        "utf8",
        "-m",
        "velch",
        "run-vehicle",
        str(case_path),
        "--output",
        str(out),
    ]
    print(f"  running {tag} (output_step_s={output_step:g}) ...", flush=True)
    completed = subprocess.run(
        command, cwd=VELCH, capture_output=True, text=True, encoding="utf-8"
    )
    if completed.returncode != 0:
        print(completed.stdout[-2000:])
        print(completed.stderr[-3000:])
        raise SystemExit(f"run failed for {tag}")
    return out


def summarise(out: pathlib.Path) -> dict:
    history = out / "history.csv"
    with history.open(encoding="utf-8") as handle:
        header = handle.readline().strip().split(",")
    data = np.loadtxt(history, delimiter=",", skiprows=1)
    columns = {name: data[:, index] for index, name in enumerate(header)}
    time = columns["time_s"]

    channels = [name for name in header if name.endswith("_normal_n")]
    summary: dict = {
        "samples": int(time.size),
        "time_span_s": float(time[-1] - time[0]),
        "channels": {},
    }
    for name in channels:
        values = columns[name]
        impulse = float(np.trapezoid(np.abs(values), time))
        summary["channels"][name] = {
            "peak_n": float(values.max()),
            "min_n": float(values.min()),
            "rms_n": float(np.sqrt(np.mean(values * values))),
            "impulse_ns": impulse,
            "active_samples": int(np.count_nonzero(values > 1.0)),
        }
    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    block = manifest.get("summary", {})
    summary["nfev"] = block.get("nfev")
    summary["wall_s"] = block.get("wall_time_s")
    summary["numerically_checked"] = block.get("numerically_checked")
    return summary


def main() -> int:
    if not SOURCE_CASE.exists():
        print(f"missing source case {SOURCE_CASE}")
        return 1

    print("B2: output-resolution sensitivity of the frog window")
    coarse = summarise(run_case("coarse", 5.0e-4))
    fine = summarise(run_case("fine", 5.0e-5))

    print()
    print(f"  samples {coarse['samples']} -> {fine['samples']}")
    print(f"  nfev    {coarse['nfev']} -> {fine['nfev']}")
    print(f"  wall s  {coarse['wall_s']} -> {fine['wall_s']}")
    print()
    header = f"{'channel':<28}{'peak kN':>10}{'d %':>8}{'impulse d %':>13}{'rms d %':>10}{'active':>9}"
    print(header)
    rows = []
    worst_peak = 0.0
    worst_impulse = 0.0
    for name in sorted(coarse["channels"]):
        a = coarse["channels"][name]
        b = fine["channels"][name]
        d_peak = (
            (b["peak_n"] - a["peak_n"]) / a["peak_n"] * 100.0 if a["peak_n"] else 0.0
        )
        d_impulse = (
            (b["impulse_ns"] - a["impulse_ns"]) / a["impulse_ns"] * 100.0
            if a["impulse_ns"]
            else 0.0
        )
        d_rms = (b["rms_n"] - a["rms_n"]) / a["rms_n"] * 100.0 if a["rms_n"] else 0.0
        worst_peak = max(worst_peak, abs(d_peak))
        worst_impulse = max(worst_impulse, abs(d_impulse))
        print(
            f"{name:<28}{b['peak_n'] / 1e3:>10.3f}{d_peak:>8.3f}{d_impulse:>13.3f}"
            f"{d_rms:>10.3f}{a['active_samples']:>5}/{b['active_samples']:<3}"
        )
        rows.append(
            {
                "channel": name,
                "peak_n": b["peak_n"],
                "delta_peak_percent": d_peak,
                "delta_impulse_percent": d_impulse,
                "delta_rms_percent": d_rms,
                "active_coarse": a["active_samples"],
                "active_fine": b["active_samples"],
            }
        )

    out = {
        "source_case": SOURCE_CASE.name,
        "coarse": {k: v for k, v in coarse.items() if k != "channels"},
        "fine": {k: v for k, v in fine.items() if k != "channels"},
        "worst_abs_delta_peak_percent": worst_peak,
        "worst_abs_delta_impulse_percent": worst_impulse,
        "rows": rows,
    }
    path = BASE / "probe_event_resolution.json"
    path.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print()
    print(f"  worst |d peak| {worst_peak:.3f} %   worst |d impulse| {worst_impulse:.3f} %")
    print(f"  wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
