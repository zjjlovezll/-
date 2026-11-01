"""Delivery check: can this package run on a machine that is not this one?

Three things have to hold, and each is checked, not asserted in prose:

    D-ASSETS   every section the delivered cases reference exists *inside the repository* and its sha256 is
               recorded, so the bytes that produced every number in DELIVERABLE_SUMMARY are pinned
    D-PATHS    no delivered case points at an absolute path (``G:\\...`` / ``F:\\velch_data``); every reference
               goes through ``lib:``/``case:``/``data:`` and resolves under the package root
    D-SMOKE    the canonical one-set case seats and integrates 0.02 s with every produced gate true
               (eight since round 314: the seven numeric gates plus launch_balance; stationarity
               is produced only inside a reading window and this case declares none)
    D-SUMMARY  the delivered summary file still equals what the archived reports recompute to

Usage::

    python scripts/s144_delivery_check.py            # human table + one verdict line
    python scripts/s144_delivery_check.py --write     # also write the manifest
"""
from __future__ import annotations

import dataclasses
import hashlib
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

CASES = {
    "one_set": ROOT / "vehicles" / "turnouts" / "CN60-1100-1_18" / "cases" / "straight_one_set.json",
    "straight": ROOT / "vehicles" / "turnouts" / "CN60-1100-1_18" / "cases" / "straight.json",
    "diverging": ROOT / "vehicles" / "turnouts" / "CN60-1100-1_18" / "cases" / "diverging.json",
}
MANIFEST = ROOT / "reports" / "surface_deliverable_2026-10-31" / "delivery_manifest.json"
SMOKE_DURATION_S = 0.02
ABSOLUTE_MARKERS = ("G:\\", "F:\\", "C:\\", "/home/", "/mnt/")


def _sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _walk(node, key="profile"):
    """Yield every profile block in a case document, whatever its nesting."""
    if isinstance(node, dict):
        if key in node and isinstance(node[key], dict) and "file" in node[key]:
            yield node[key]
        for value in node.values():
            yield from _walk(value, key)
    elif isinstance(node, list):
        for value in node:
            yield from _walk(value, key)


def references() -> dict:
    """Every (case, file reference) pair the three delivered cases carry."""
    from velch.assets import resolve_asset

    rows = []
    for label, path in CASES.items():
        document = json.loads(path.read_text(encoding="utf-8"))
        for block in _walk(document):
            reference = block["file"]
            row = {"case": label, "reference": reference}
            absolute = any(marker in reference for marker in ABSOLUTE_MARKERS)
            row["absolute"] = absolute
            try:
                resolved = resolve_asset(reference, case_path=path, kind="rail profile").path
            except Exception as error:                          # noqa: BLE001 - reported, not raised
                row["error"] = f"{type(error).__name__}: {error}"
                row["inside_repo"] = False
                rows.append(row)
                continue
            resolved = pathlib.Path(resolved)
            row["inside_repo"] = resolved.is_file() and ROOT in resolved.resolve().parents
            row["path"] = str(resolved.relative_to(ROOT)) if row["inside_repo"] else str(resolved)
            if row["inside_repo"]:
                row["sha256"] = _sha256(resolved)
            rows.append(row)
    return {"cases": {k: str(v.relative_to(ROOT)) for k, v in CASES.items()}, "references": rows}


def asset_gate(report: dict) -> dict:
    rows = report["references"]
    missing = [row for row in rows if not row.get("inside_repo")]
    absolute = [row for row in rows if row.get("absolute")]
    unique = {row["path"]: row["sha256"] for row in rows if row.get("sha256")}
    return {
        "references": len(rows),
        "unique_files": len(unique),
        "missing_or_outside": len(missing),
        "absolute": len(absolute),
        "pass": not missing and not absolute,
        "missing": [row.get("reference") for row in missing][:8],
        "absolute_examples": [row["reference"] for row in absolute][:8],
    }


def smoke() -> dict:
    """Seat the canonical case, integrate the documented 0.02 s, and report every produced gate."""
    from velch.vehicle import load_vehicle_case
    from velch.vehicle_solver import VehicleDynamics, _seat, simulate_vehicle

    import numpy as np

    case = load_vehicle_case(CASES["one_set"])
    velocity = np.asarray(case.initial_v, dtype=float).copy()
    speed = float(case.vehicle.travel_speed_m_s)
    # `duration_s` must stay positive (the dataclass validates it); seating ignores it anyway
    dynamics = VehicleDynamics(case)
    state = np.asarray(case.initial_q, dtype=float).copy()
    for axle in range(1, 5):                     # rolling without slip at the seated speed
        index = dynamics.topology.require(f"wheelset{axle}", "spin")
        velocity[index] = speed / 0.43
    seated, residual = _seat(case, dynamics, state, velocity)
    short = dataclasses.replace(case, run=dataclasses.replace(case.run, duration_s=SMOKE_DURATION_S))
    result = simulate_vehicle(short)
    gates = dict(result.summary["gates"])
    return {
        "case": str(CASES["one_set"].relative_to(ROOT)),
        "duration_s": SMOKE_DURATION_S,
        "seat_residual_n": float(residual),
        "frames": int(len(result.times_s)),
        "gates": gates,
        "pass": bool(all(gates.values())) and float(residual) <= 1.0e-5,
    }


def summary() -> dict:
    """Recompute the delivered summary from the archived reports and compare with the copy on disk."""
    import s143_deliverable_summary as delivered                 # noqa: PLC0415 - scripts/ is on sys.path below

    stored = json.loads((ROOT / "reports" / "surface_deliverable_2026-10-31" / "deliverable_summary.json")
                        .read_text(encoding="utf-8"))
    recomputed = {"coverage": delivered.coverage(), "band_surface": delivered.surface(),
                  "counts": dict(stored["counts"])}
    same_coverage = recomputed["coverage"] == stored["coverage"]
    same_surface = recomputed["band_surface"] == stored["band_surface"]
    return {"coverage_matches": same_coverage, "band_surface_matches": same_surface,
            "counts": stored["counts"], "pass": same_coverage and same_surface}



WHEEL_DIR = ROOT.parent / "scratch" / "wheel_m9"
SECTION_DIR = "turnouts/CN60-1100-1_18/sections/"


def wheel_gate(path: pathlib.Path | None = None) -> dict:
    """Does an installable wheel carry the library it needs?

    A wheel is what leaves this machine, so the question is not "are the sections bundled somewhere" but
    "does the artifact that gets installed include them".  The gate inspects an existing wheel instead of
    building one: the build step needs a working temp directory and network-free setuptools, both of which
    are machine state rather than package state.  Build it once with::

        python -m pip wheel --no-deps -w ../scratch/wheel_m9 .

    Measured 2026-10-31: 463 065 B, 104 entries, none under ``vehicles/`` -> an installed copy cannot
    resolve a single ``lib:`` reference (``AssetRefError: not found under any known root``).
    """
    import zipfile

    wheel = path if path is not None else next(iter(sorted(WHEEL_DIR.glob("*.whl"))), None)
    if wheel is None or not wheel.is_file():
        return {"built": False, "ships_library": False, "pass": False,
                "reason": [f"no wheel in {WHEEL_DIR}; build one with python -m pip wheel --no-deps -w {WHEEL_DIR} ."]}
    with zipfile.ZipFile(wheel) as archive:
        names = archive.namelist()
    library = [name for name in names if name.startswith("vehicles/") or "_internal/vehicles/" in name]
    sections = [name for name in library if SECTION_DIR in name]
    return {
        "built": True,
        "wheel": wheel.name,
        "bytes": wheel.stat().st_size,
        "entries": len(names),
        "library_entries": len(library),
        "section_entries": len(sections),
        "library_inside_package": any("_internal/vehicles/" in name for name in names),
        "ships_library": len(library) >= 295,
        "pass": len(library) >= 295,
    }


def main(argv: list[str]) -> int:
    sys.path.insert(0, str(ROOT / "scripts"))
    report = references()
    assets = asset_gate(report)
    body = smoke()
    archive = summary()
    wheel = wheel_gate(pathlib.Path(argv[argv.index("--wheel") + 1]) if "--wheel" in argv else None)
    verdict = assets["pass"] and body["pass"] and archive["pass"] and wheel["pass"]

    print(f"cases           {len(report['cases'])}")
    print(f"[D-ASSETS]  references {assets['references']}  unique files {assets['unique_files']}"
          f"  missing/outside {assets['missing_or_outside']}  absolute {assets['absolute']}"
          f"  -> {'PASS' if assets['pass'] else 'FAIL'}")
    for reference in assets["missing"][:4]:
        print(f"            missing: {reference}")
    print(f"[D-PATHS]   absolute references {assets['absolute']}"
          f"  -> {'PASS' if assets['absolute'] == 0 else 'FAIL'}")
    print(f"[D-SMOKE]   {body['duration_s']:.3f} s  frames {body['frames']}"
          f"  seat residual {body['seat_residual_n']:.3e} N"
          f"  gates {sum(body['gates'].values())}/{len(body['gates'])}"
          f"  -> {'PASS' if body['pass'] else 'FAIL'}")
    print(f"[D-SUMMARY] coverage {'match' if archive['coverage_matches'] else 'DIFFERS'}"
          f"  band surface {'match' if archive['band_surface_matches'] else 'DIFFERS'}"
          f"  -> {'PASS' if archive['pass'] else 'FAIL'}")
    if wheel.get("built"):
        wheel_line = (f"{wheel['wheel']} {wheel['bytes']} B  entries {wheel['entries']}"
                      f"  library {wheel['library_entries']}  sections {wheel['section_entries']}")
        wheel_state = "PASS" if wheel["pass"] else "FAIL"
    else:
        wheel_line = "not built: " + " ".join(str(item) for item in wheel.get("reason", []))[:140]
        wheel_state = "FAIL"
    print(f"[D-WHEEL]   {wheel_line}  -> {wheel_state}")
    headline = ("the package carries everything it needs and reproduces its own headline" if verdict
                else "the package is not self-contained (see the failing line above)")
    print(f"VERDICT: {headline}")

    if "--write" in argv:
        payload = {"generated_by": "scripts/s144_delivery_check.py", "cases": report["cases"],
                   "assets": assets, "smoke": body, "summary": archive, "wheel": wheel,
                   "verdict": bool(verdict),
                   "references": [{k: row[k] for k in ("case", "path", "sha256") if k in row}
                                  for row in report["references"]]}
        MANIFEST.parent.mkdir(parents=True, exist_ok=True)
        MANIFEST.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"manifest -> {MANIFEST.relative_to(ROOT)}")
    return 0 if verdict else 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
