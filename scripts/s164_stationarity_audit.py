"""Audit every archived run for stationarity before any of its numbers may be quoted.

Round 310 withdrew the 60 km/h location row because that run's front-rail normal force swings from 0 to 208 kN
(standard deviation 34.75 kN) while the 80 and 100 km/h rows hold 0.07 and 0.51 kN.  The seven numerical gates do
not test that, so a run can pass all of them while its contact load is still ringing -- and any ``engage``,
``fit`` or ``gate`` read off such a run is an artefact of when the detector happened to cross.

This audit applies one pre-registered test to every archived run and quarantines the ones that fail it:

    stationary  <=>  max over rails of std(normal force) < 5 kN

with a second, diagnostic column recording the modal block's start and end norm, because the round-310 failure
mode was a modal transient that never decayed.  Nothing is rewritten: the archive index and the series files stay
as they are, and the report names what may be quoted.

Thresholds are fixed here, before the audit runs: 5 kN of force standard deviation (the 60 km/h row is 34.75,
the next worst legitimate row is 0.51), and a modal decay ratio below 0.5 over a window shorter than three
modal time constants is reported as "not settled" rather than as a gate failure.
"""

from __future__ import annotations

import json
import pathlib
import sys

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parent.parent
RUNS_DIR = ROOT.parent / "scratch" / "runs"
REPORT = ROOT / "reports" / "load_split_inversion_2026-10-31" / "stationarity_audit.json"

MAX_STD_KN = 5.0
MODAL_BLOCK = slice(102, 234)
TRACK_BLOCK = slice(86, 102)
DECAY_CEILING = 0.5


def is_stationary(max_std_kn: float) -> bool:
    """The pre-registered test, named on its own so a test can try to poison it."""

    return bool(float(max_std_kn) < MAX_STD_KN)


def audit(directory: pathlib.Path) -> dict:
    series = np.load(directory / "series.npz")
    meta = json.loads((directory / "meta.json").read_text(encoding="utf-8"))
    forces = series["normal_force_n"]
    positions = series["positions"]
    times = series["times"]
    rails = list(meta["rail_ids"])
    std = {rail: 1e-3 * float(forces[:, i].std()) for i, rail in enumerate(rails)}
    peak = max(std.values()) if std else float("nan")
    worst = max(std, key=std.get) if std else ""
    modal = positions[:, MODAL_BLOCK]
    modal_start = float(np.linalg.norm(modal[0]))
    modal_end = float(np.linalg.norm(modal[-1]))
    decay = None if modal_start <= 0.0 else modal_end / modal_start
    return {
        "run_id": directory.name,
        "route": meta.get("route"),
        "speed_kmh": float(meta.get("speed_kmh", float("nan"))),
        "duration_s": float(times[-1]),
        "frames": int(len(times)),
        "wall_s": float(meta.get("wall_s", float("nan"))),
        "max_rail_std_kn": peak,
        "worst_rail": worst,
        "rail_std_kn": std,
        "force_max_kn": 1e-3 * float(np.nanmax(forces)),
        "modal_norm_start_m": modal_start,
        "modal_norm_end_m": modal_end,
        "modal_decay": decay,
        "gates_all_true": bool(all(meta["gates"].values())) if isinstance(meta.get("gates"), dict) else None,
        "stationary": is_stationary(peak),
    }


def main() -> int:
    directories = sorted(p for p in RUNS_DIR.iterdir() if p.is_dir() and (p / "series.npz").is_file())
    rows = [audit(directory) for directory in directories]
    quarantined = [row["run_id"] for row in rows if not row["stationary"]]
    #: One answer per (route, speed): the longest archive of that pair, which is the one the gates read.
    by_route_speed: dict[str, dict] = {}
    for row in rows:
        key = f"{row['route']}|{row['speed_kmh']:g}"
        current = by_route_speed.get(key)
        if current is None or row["duration_s"] > current["duration_s"]:
            by_route_speed[key] = {"run_id": row["run_id"], "duration_s": row["duration_s"],
                                   "max_rail_std_kn": row["max_rail_std_kn"],
                                   "modal_decay": row["modal_decay"], "stationary": row["stationary"]}
    report = {
        "rows": rows,
        "constants": {"max_std_kn": MAX_STD_KN, "decay_ceiling": DECAY_CEILING,
                      "modal_block": [MODAL_BLOCK.start, MODAL_BLOCK.stop],
                      "track_block": [TRACK_BLOCK.start, TRACK_BLOCK.stop]},
        "verdict": {
            "runs": len(rows),
            "stationary": sum(1 for row in rows if row["stationary"]),
            "quarantined": quarantined,
            "all_gates_true_but_not_stationary": [row["run_id"] for row in rows
                                                  if not row["stationary"] and row["gates_all_true"]],
            "unsettled_modal": [row["run_id"] for row in rows
                                if row["modal_decay"] is not None and row["modal_decay"] > DECAY_CEILING],
            "by_route_speed": by_route_speed,
            "purpose": "name which archived runs may be quoted, before any round reads them again",
        },
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    print(f"{'run':>52} {'dur s':>7} {'maxStd kN':>10} {'worst rail':>14} {'modal decay':>12} {'ok':>4}")
    for row in sorted(rows, key=lambda item: (item["speed_kmh"], item["route"] or "", item["duration_s"])):
        decay = "n/a" if row["modal_decay"] is None else f"{row['modal_decay']:.3f}"
        print(f"{row['run_id'][:52]:>52} {row['duration_s']:7.3f} {row['max_rail_std_kn']:10.2f} "
              f"{row['worst_rail']:>14} {decay:>12} {'yes' if row['stationary'] else 'NO':>4}")
    print()
    v = report["verdict"]
    print(f"runs {v['runs']}   stationary {v['stationary']}   quarantined {len(v['quarantined'])}")
    for run_id in v["quarantined"]:
        print(f"  quarantined: {run_id}")
    print(f"gates true but not stationary: {v['all_gates_true_but_not_stationary']}")
    print(f"report -> {REPORT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
