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
import os
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


def resolve_case(route: str, case: str | None) -> tuple[pathlib.Path, str]:
    """Return the case file and the label that goes into ``run_id``.

    ``--route`` keeps the two packaged turnout cases; ``--case`` names any other case and the label
    becomes its file stem, so a new case cannot silently inherit an old run id.
    """
    if case:
        path = pathlib.Path(case)
        return path, path.stem
    return CASES[route], route


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


def apply_speed(case, speed_kmh: float):
    """Return ``case`` with its travel speed set to ``speed_kmh``, declared profile included.

    A case that declares ``run.speed_profile = {"constant": {...}}`` keeps that schedule: the loader
    lets the profile speed win over ``vehicle.travel_speed_m_s``.  Overriding only the vehicle therefore
    renames a run without changing its physics -- B052, found 2026-11-01 when three "different" speeds
    produced one onset time.  A multi-leg profile cannot be flattened silently, so it raises.
    """

    probe = getattr(case.run, "speed_profile", None)
    if probe is not None and (not isinstance(probe, dict) or "constant" not in probe):
        raise SystemExit(
            "this case declares a multi-leg speed_profile; --speed-kmh cannot override it without "
            "changing the schedule, so edit the case instead")
    schedule = {"constant": {"speed_kmh": float(speed_kmh)}} if probe is not None else probe
    run = dataclasses.replace(case.run, speed_profile=schedule)
    vehicle = dataclasses.replace(case.vehicle, travel_speed_m_s=float(speed_kmh) / 3.6)
    out = dataclasses.replace(case, vehicle=vehicle, run=run)
    # The loader materialises a SpeedSchedule on the case, and the solver prefers it over
    # cfg.travel_speed_m_s (vehicle_solver.py:149).  Rewriting the two blocks above is therefore not
    # enough -- B052 had a second layer that kept the run at the declared 80 km/h.  Rebuild it.
    materialised = getattr(out, "speed_schedule", None)
    if materialised is not None:
        from velch.speed import SpeedSchedule

        out = dataclasses.replace(
            out,
            speed_schedule=SpeedSchedule.constant(abs(float(speed_kmh)) / 3.6,
                                                  duration_s=float(out.run.duration_s)),
        )
    return out

def run_id_for(route: str, speed_kmh: float, duration_s: float, output_step_s: float,
               case_digest: str) -> str:
    return (f"{route}-{speed_kmh:06.2f}kmh-{duration_s:.4f}s-{output_step_s * 1e6:.0f}us-"
            f"{case_digest[:8]}")


def _index_lock():
    """Cross-process lock for the index file, used when a batch runs several cases at once.

    Only the read-modify-write of ``index.jsonl`` is serialised; the simulations overlap.  The lock is
    opt-in (``VELCH_INDEX_LOCK=1``) so a single run keeps the exact behaviour it had.
    """
    import contextlib
    if os.environ.get("VELCH_INDEX_LOCK") != "1":
        return contextlib.nullcontext()

    @contextlib.contextmanager
    def held():
        lock_path = INDEX.with_suffix(".lock")
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        handle = lock_path.open("a+b")
        try:
            if os.name == "nt":
                import msvcrt
                handle.seek(0)
                while True:
                    try:
                        msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
                        break
                    except OSError:
                        time.sleep(0.05)
                try:
                    yield
                finally:
                    handle.seek(0)
                    msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
                try:
                    yield
                finally:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        finally:
            handle.close()

    return held()


def write_index(entry: dict) -> None:
    """Replace this run's line if it is already indexed, otherwise append."""
    with _index_lock():
        _write_index_locked(entry)


def _write_index_locked(entry: dict) -> None:
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
    ap.add_argument("--case", default=None,
                    help="explicit case path; its file stem labels the run (e.g. straight_one_set)")
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

    case_path, route = resolve_case(args.route, args.case)
    case_digest = sha256_of(case_path)
    case = load_vehicle_case(case_path)
    speed_kmh = float(args.speed_kmh if args.speed_kmh is not None
                      else case.vehicle.travel_speed_m_s * 3.6)
    run_id = run_id_for(route, speed_kmh, args.duration, args.output_step, case_digest)
    out = OUT_ROOT / run_id
    if args.dry:
        print(f"run_id {run_id}\n  case {case_path} ({case_digest[:16]})\n  out  {out}")
        return 0

    case = apply_speed(case, speed_kmh)
    run = dataclasses.replace(case.run, duration_s=args.duration, output_step_s=args.output_step)
    started = time.perf_counter()
    result = simulate_vehicle(dataclasses.replace(case, run=run))
    wall_s = time.perf_counter() - started
    gates = (getattr(result, "summary", {}) or {}).get("gates") or {}
    notes: dict[str, str] = {}
    for item in args.note:
        if "=" not in item:
            raise SystemExit(f"--note needs KEY=VALUE, got {item!r}")
        key, value = item.split("=", 1)
        notes[key.strip()] = value.strip()
    entry = write_archive(result, case=case, case_path=case_path, case_digest=case_digest,
                          route=route, speed_kmh=speed_kmh, duration_s=args.duration,
                          output_step_s=args.output_step, wall_s=wall_s, notes=notes,
                          launch=getattr(result, "launch", None))
    print(f"{entry['run_id']}: frames {entry['frames']}  gates "
          f"{sum(bool(v) for v in entry['gates'].values())}/{len(entry['gates'])}  "
          f"wall {wall_s:.1f} s")
    for name, value in entry["gates"].items():
        print(f"  {name}: {value}")
    print(f"data -> {entry['path']}")
    return 0 if entry["gates"] and all(entry["gates"].values()) else 1


def write_archive(result, *, case, case_path, case_digest: str, route: str, speed_kmh: float,
                  duration_s: float, output_step_s: float, wall_s: float, notes: dict,
                  launch: dict | None = None, setup: str | None = None,
                  overrides: tuple[str, ...] = ()) -> dict:
    """Write one finished run into ``scratch/runs/<run_id>/`` and return its index row.

    The run id is derived from inputs only, so the same configuration cannot accumulate duplicates
    and a changed case cannot silently reuse an old id.  ``launch`` is what the integration started
    from (``run.report_launch``); it is written into ``meta.json`` because a run that did not start
    seated reads its own transient, and until round 311 the archive could not tell.
    """
    run_id = run_id_for(route, speed_kmh, duration_s, output_step_s, case_digest)
    out = OUT_ROOT / run_id
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
    # The lateral force is what any statement about drift has to be checked against, and it cannot be
    # reconstructed after the fact: script s106 could only read the normal-force split from an archived
    # run, so its sign-agreement gate was untestable.  Store it with the run.
    lateral = np.zeros((len(frames), len(rail_ids)))
    # Which part of the rail head was actually measured is the whole content of the observed region:
    # a wheel that runs along one lateral offset never sees the rest of the surface, and that cannot
    # be reconstructed after the fact.  Store the contact point and the band half width, with NaN
    # where no contact was alive (the gap is information; zero would read as a contact at y = 0).
    contact_y = np.full((len(frames), len(rail_ids)), np.nan)
    contact_b = np.full((len(frames), len(rail_ids)), np.nan)
    for index, frame in enumerate(frames):
        normals = []
        laterals = []
        for column, rail in enumerate(rail_ids):
            response = frame.get(rail)
            live = response is not None and response.active
            geometry = response.geometry if live else None
            normals.append(float(response.normal_force_n) if live else 0.0)
            laterals.append(float(response.wheel_force_y_n) if live else 0.0)
            if geometry is not None:
                contact_y[index, column] = float(geometry.y_m)
                contact_b[index, column] = float(geometry.half_width_m)
        normal[index] = normals
        lateral[index] = laterals
    arrays["normal_force_n"] = normal
    arrays["lateral_force_n"] = lateral
    arrays["contact_lateral_m"] = contact_y
    arrays["contact_half_width_m"] = contact_b
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

    gates = (getattr(result, "summary", {}) or {}).get("gates") or {}

    meta = {
        "run_id": run_id,
        "route": route,
        "case": str(case_path),
        "case_sha256": case_digest,
        "speed_kmh": speed_kmh,
        "speed_m_s": speed_kmh / 3.6,
        "profile_speed_kmh": (float(case.run.speed_profile["constant"]["speed_kmh"])
                              if case.run.speed_profile else None),
        "x_start_m": float(case.run.x_start_m),
        "seat_x_start_m": getattr(case.run, "seat_x_start_m", None),
        "duration_s": duration_s,
        "output_step_s": output_step_s,
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
        "python_notes": "positions/velocities/accelerations are SI; normal_force_n and lateral_force_n columns "
                         "follow rail_ids, body_normal_force_n columns follow body_labels",
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=1, ensure_ascii=False) + chr(10),
                                      encoding="utf-8")
    entry = {
        "run_id": run_id,
        "route": route,
        "speed_kmh": speed_kmh,
        "duration_s": duration_s,
        "output_step_s": output_step_s,
        "frames": int(arrays["times"].size),
        "gates": meta["gates"],
        "case_sha256": case_digest,
        # The index is how a training set gets built later, so the note that says which campaign a
        # run belongs to has to live here too; reading meta.json for every row would be worse.
        "notes": dict(meta.get("notes", {})),
        "wall_s": wall_s,
        "path": str(out),
    }
    entry["launch"] = None if launch is None else {
        "modal_norm_m": float(launch["modal_norm_m"]),
        "modal_residual_n": float(launch["modal_residual_n"]),
        "vertical_preload_residual_n": launch["vertical_preload_residual_n"],
        "spin_relative_max": float(launch["spin_relative_max"]),
        "balanced": bool(launch["balanced"]),
    }
    entry["setup"] = setup
    entry["overrides"] = list(overrides)
    write_index(entry)
    return entry


if __name__ == "__main__":
    raise SystemExit(main())
