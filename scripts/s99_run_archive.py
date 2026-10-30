"""Archive every turnout run so a surrogate model can be trained on it later.

The user's 2026-10-31 instruction is that repeated runs to refine the surface are allowed **provided the
data is kept** and can feed a surrogate model.  That turns "run the case again" into a data-collection
contract, and this script is the contract:

    scratch/runs/<run_id>/series.npz      times, positions, velocities, accelerations,
                                          per-rail normal force, per-body normal force
    scratch/runs/<run_id>/meta.json       speed, geometry window, solver settings, gates, wall clock
    scratch/runs/<run_id>/manifest.json   case sha256 + product sha256 + code HEAD + created_at
    scratch/runs/index.jsonl              one line per run, the only index a training set may come from

`run_id` is derived from *inputs only* (route, speed, duration, output step, case digest), so the same
configuration cannot accumulate duplicates and a changed case cannot silently reuse an old id.

    PYTHONPATH=src python -X utf8 scripts/s99_run_archive.py --list
    PYTHONPATH=src python -X utf8 scripts/s99_run_archive.py --route straight --speed-kmh 80 --duration 0.02
"""
from __future__ import annotations

import argparse
import dataclasses
import datetime as dt
import hashlib
import json
import pathlib
import time

import numpy as np

from velch.vehicle import load_vehicle_case
from velch.vehicle_solver import simulate_vehicle

CASES = {
    "straight": pathlib.Path("vehicles/turnouts/CN60-1100-1_18/cases/straight.json"),
    "diverging": pathlib.Path("vehicles/turnouts/CN60-1100-1_18/cases/diverging.json"),
}
ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT_ROOT = ROOT.parent / "scratch" / "runs"
INDEX = OUT_ROOT / "index.jsonl"


def sha256_of(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def code_head() -> str:
    head = ROOT / ".git" / "HEAD"
    try:
        text = head.read_text(encoding="utf-8").strip()
        if text.startswith("ref: "):
            return (ROOT / ".git" / text[5:]).read_text(encoding="utf-8").strip()
        return text
    except OSError:
        return "unknown"


def run_id_for(route: str, speed_kmh: float, duration_s: float, output_step_s: float,
               case_digest: str) -> str:
    return (f"{route}-{speed_kmh:06.2f}kmh-{duration_s:.4f}s-{output_step_s * 1e6:.0f}us-"
            f"{case_digest[:8]}")


def write_index(entry: dict) -> None:
    """Replace this run's line if it is already indexed, otherwise append."""
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    rows: list[dict] = []
    if INDEX.exists():
        for line in INDEX.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if row.get("run_id") != entry["run_id"]:
                rows.append(row)
    rows.append(entry)
    rows.sort(key=lambda row: (row.get("route", ""), float(row.get("speed_kmh", 0.0)),
                               float(row.get("duration_s", 0.0))))
    INDEX.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
                     encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--route", default="straight", choices=tuple(CASES))
    ap.add_argument("--speed-kmh", type=float, default=None, help="override travel_speed_m_s")
    ap.add_argument("--duration", type=float, default=0.02)
    ap.add_argument("--output-step", type=float, default=5e-4)
    ap.add_argument("--note", action="append", default=[], metavar="KEY=VALUE")
    ap.add_argument("--list", action="store_true", help="print the index and exit")
    ap.add_argument("--dry", action="store_true", help="resolve the run id and paths, run nothing")
    args = ap.parse_args()

    if args.list:
        if not INDEX.exists():
            print(f"no runs archived yet ({INDEX})")
            return 0
        rows = [json.loads(line) for line in INDEX.read_text(encoding="utf-8").splitlines() if line.strip()]
        print(f"{'run_id':<52}{'frames':>8}{'speed':>9}{'dur':>8}{'gates':>8}")
        for row in rows:
            gates = row.get("gates") or {}
            print(f"{row['run_id']:<52}{row.get('frames', 0):>8}"
                  f"{row.get('speed_kmh', 0.0):>9.2f}{row.get('duration_s', 0.0):>8.3f}"
                  f"{sum(bool(v) for v in gates.values()):>4}/{len(gates):<3}")
        print(f"{len(rows)} run(s) in {INDEX}")
        return 0

    case_path = CASES[args.route]
    case_digest = sha256_of(case_path)
    case = load_vehicle_case(case_path)
    speed_kmh = float(args.speed_kmh if args.speed_kmh is not None
                      else case.vehicle.travel_speed_m_s * 3.6)
    run_id = run_id_for(args.route, speed_kmh, args.duration, args.output_step, case_digest)
    out = OUT_ROOT / run_id
    if args.dry:
        print(f"run_id {run_id}\n  case {case_path} ({case_digest[:16]})\n  out  {out}")
        return 0

    vehicle = dataclasses.replace(case.vehicle, travel_speed_m_s=speed_kmh / 3.6)
    run = dataclasses.replace(case.run, duration_s=args.duration, output_step_s=args.output_step)
    started = time.perf_counter()
    result = simulate_vehicle(dataclasses.replace(case, vehicle=vehicle, run=run))
    wall_s = time.perf_counter() - started
    summary = getattr(result, "summary", {}) or {}
    gates = summary.get("gates") or {}

    out.mkdir(parents=True, exist_ok=True)
    arrays = {
        "times": np.asarray(result.times_s, dtype=float),
        "positions": np.asarray(result.positions, dtype=float),
        "velocities": np.asarray(result.velocities, dtype=float),
    }
    accelerations = getattr(result, "accelerations", None)
    if accelerations is not None:
        arrays["accelerations"] = np.asarray(accelerations, dtype=float)
    frames = result.contacts or []
    rail_ids = list(frames[0]) if frames else []
    normal = np.zeros((len(frames), len(rail_ids)))
    for index, frame in enumerate(frames):
        normals = []
        for rail in rail_ids:
            response = frame.get(rail)
            normals.append(float(response.normal_force_n) if response is not None and response.active else 0.0)
        normal[index] = normals
    arrays["normal_force_n"] = normal
    # The merged rail force cannot answer "how much is on the blade", which is the observable the
    # turnout inversion is built on, so the per-body split travels with the run.
    # The merged rail force cannot answer "how much is on the blade", which is the observable the
    # turnout inversion is built on, so the per-body split travels with the run.  Names come from
    # ``result.body_ids``: only the bodies active at a station report, so the ids cannot be
    # reconstructed from the rail's declared body list.
    history = getattr(result, "body_contacts", None) or ()
    id_history = getattr(result, "body_ids", None) or ()
    if len(history) != len(id_history):
        raise SystemExit(f"{len(history)} response frames but {len(id_history)} id frames")
    body_labels: list[str] = []
    for frame_ids in id_history:
        for rail_id, names in frame_ids.items():
            for name in names:
                label = f"{rail_id}/{name}"
                if label not in body_labels:
                    body_labels.append(label)
    body_normal = np.zeros((len(frames), len(body_labels)))
    column_of = {label: index for index, label in enumerate(body_labels)}
    for row, (frame, frame_ids) in enumerate(zip(history, id_history)):
        for rail_id, responses in frame.items():
            names = frame_ids.get(rail_id, ())
            if len(names) != len(responses):
                raise SystemExit(f"{rail_id}: {len(responses)} responses for {len(names)} body ids")
            for name, response in zip(names, responses):
                if response.active:
                    body_normal[row, column_of[f"{rail_id}/{name}"]] = float(response.normal_force_n)
    arrays["body_normal_force_n"] = body_normal
    np.savez_compressed(out / "series.npz", **arrays)

    notes: dict[str, str] = {}
    for item in args.note:
        if "=" not in item:
            raise SystemExit(f"--note needs KEY=VALUE, got {item!r}")
        key, value = item.split("=", 1)
        notes[key.strip()] = value.strip()

    meta = {
        "run_id": run_id,
        "route": args.route,
        "case": str(case_path),
        "case_sha256": case_digest,
        "speed_kmh": speed_kmh,
        "speed_m_s": speed_kmh / 3.6,
        "x_start_m": float(case.run.x_start_m),
        "seat_x_start_m": getattr(case.run, "seat_x_start_m", None),
        "duration_s": args.duration,
        "output_step_s": args.output_step,
        "max_solver_step_s": float(case.run.max_solver_step_s),
        "method": case.run.method,
        "rtol": float(case.run.rtol),
        "atol": float(case.run.atol),
        "track_kind": case.track_kind,
        "track_layers": len(case.track_layers or ()),
        "frames": int(arrays["times"].size),
        "dimension": int(arrays["positions"].shape[1]),
        "rail_ids": rail_ids,
        "body_labels": body_labels,
        "acceleration_names": list(getattr(result, "acceleration_names", ()) or ()),
        "gates": {str(k): bool(v) for k, v in gates.items()},
        "wall_s": wall_s,
        "notes": notes,
    }
    (out / "meta.json").write_text(json.dumps(meta, indent=1, ensure_ascii=False) + chr(10),
                                   encoding="utf-8")
    manifest = {
        "run_id": run_id,
        "created_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "code_head": code_head(),
        "case": str(case_path),
        "case_sha256": case_digest,
        "products": {name: sha256_of(out / name) for name in ("series.npz", "meta.json")},
        "python_notes": "positions/velocities/accelerations are SI; normal_force_n columns follow "
                         "rail_ids, body_normal_force_n columns follow body_labels",
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=1, ensure_ascii=False) + chr(10),
                                      encoding="utf-8")
    write_index({
        "run_id": run_id,
        "route": args.route,
        "speed_kmh": speed_kmh,
        "duration_s": args.duration,
        "output_step_s": args.output_step,
        "frames": int(arrays["times"].size),
        "gates": meta["gates"],
        "case_sha256": case_digest,
        "wall_s": wall_s,
        "path": str(out),
    })

    print(f"{run_id}: frames {arrays['times'].size}  gates "
          f"{sum(bool(v) for v in gates.values())}/{len(gates)}  wall {wall_s:.1f} s")
    for name, value in gates.items():
        print(f"  {name}: {value}")
    print(f"data -> {out}")
    return 0 if gates and all(bool(v) for v in gates.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
