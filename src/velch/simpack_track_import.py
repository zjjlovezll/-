"""Read-only Simpack .spck rail geometry catalog for independent Velch models.

This parses a deliberately narrow, auditable subset of user model text. It
does not load Simpack rigid/flexible solver objects or infer private type codes.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

from .profiles import ProfileSeries, Station, load_profile


_SEARCH = re.compile(r"^searchpath\s*\([^)]*\)\s*=\s*'([^']+)'", re.I)
_SUBMODEL = re.compile(r"^substr\.file\s*\(\s*([^,)]+?)\s*\)\s*=\s*'([^']+)'", re.I)
_PROFILE = re.compile(
    r"^rail\.([rl])\.prof\.(file|s)\s*\(\s*(\d+)\s*,\s*([^,)]+?)\s*\)\s*=\s*(?:'([^']+)'|([^!\s]+))", re.I
)
_TRACK_ACTIVE = re.compile(r"^track\.active\s*=\s*(\S+)", re.I)
_TRACK_KIND = re.compile(r"^track\.(type|kind)\s*\(\s*([^,)]+?)\s*\)\s*=\s*([^!\s]+)", re.I)
_RAIL_BODY_MASS = re.compile(r"^body\.m\s*\(\s*(\$B_Rail[^,)]+)\s*\)\s*=\s*(.+?)\s*(?:!.*)?$", re.I)
_MODAL_FILE = re.compile(r"^body\.flx\.[\w.]*file\s*\(\s*([^,)]+?)\s*\)\s*=\s*'([^']+)'", re.I)


def _within(candidate: Path, root: Path) -> bool:
    return candidate == root or root in candidate.parents


def _resolve_reference(filename: str, parent: Path, paths: list[str], root: Path) -> Path | None:
    bases = [parent.parent, *(parent.parent / entry for entry in paths)]
    # Simpack databases store wheel and rail profiles in a typed directory.
    # A model can refer to a profile by basename without listing that directory
    # in its local searchpath statements.
    if Path(filename).suffix.lower() in {".prr", ".prw"}:
        bases.append(root / "wheel_rail_profiles")
    for base in bases:
        target = (base / filename).resolve()
        if _within(target, root) and target.is_file():
            return target
    return None


def inspect_simpack_track(model_path: str | Path, model_root: str | Path,
                          max_models: int = 32) -> dict[str, Any]:
    root = Path(model_root).resolve(strict=True)
    initial = Path(model_path).resolve(strict=True)
    if not _within(initial, root) or initial.suffix.lower() != ".spck":
        raise ValueError("model must be an existing .spck inside model_root")
    pending = [initial]
    visited: set[Path] = set()
    scanned: list[dict[str, Any]] = []
    links: list[dict[str, Any]] = []
    profiles: list[dict[str, Any]] = []
    active_track: str | None = None
    track_objects: dict[str, dict[str, str]] = {}
    rail_bodies: list[dict[str, str]] = []
    modal_references: list[dict[str, str]] = []
    hashes: dict[Path, str] = {}
    while pending:
        current = pending.pop(0)
        if current in visited:
            continue
        if len(visited) >= max_models:
            raise ValueError("model graph exceeds configured file bound")
        visited.add(current)
        digest = hashlib.sha256()
        search_paths: list[str] = []
        submodels: list[tuple[str, str]] = []
        entries: dict[tuple[str, str, int], dict[str, Any]] = {}
        with current.open("rb") as stream:
            for line_number, raw in enumerate(stream, 1):
                digest.update(raw)
                line = raw.decode("utf-8", errors="replace").strip()
                if not line or line.startswith("!"):
                    continue
                if match := _SEARCH.match(line):
                    search_paths.append(match.group(1))
                elif match := _SUBMODEL.match(line):
                    submodels.append((match.group(1).strip(), match.group(2)))
                elif match := _PROFILE.match(line):
                    side, field, index, rail, filename, numeric = match.groups()
                    entry = entries.setdefault((rail.strip(), side.lower(), int(index)), {})
                    if field.lower() == "file":
                        entry["filename"] = filename
                    else:
                        try:
                            position = float(numeric)
                            if not math.isfinite(position):
                                raise ValueError
                            entry["s_m"] = position
                        except (TypeError, ValueError):
                            entry["station_expression"] = numeric
                    entry[f"{field.lower()}_line"] = line_number
                elif match := _TRACK_ACTIVE.match(line):
                    if current == initial:
                        active_track = match.group(1)
                elif match := _TRACK_KIND.match(line):
                    field, object_name, raw_value = match.groups()
                    track_objects.setdefault(object_name.strip(), {})[field.lower()] = raw_value
                elif match := _RAIL_BODY_MASS.match(line):
                    rail_bodies.append({"source_model": str(current), "object": match.group(1).strip(),
                                        "mass_definition": match.group(2).strip(), "line": str(line_number)})
                elif match := _MODAL_FILE.match(line):
                    modal_references.append({"source_model": str(current), "object": match.group(1).strip(),
                                             "filename": match.group(2), "line": str(line_number)})
        scanned.append({"path": str(current), "sha256": digest.hexdigest(),
                        "size_bytes": current.stat().st_size})
        for object_name, filename in submodels:
            child = _resolve_reference(filename, current, search_paths, root)
            links.append({"parent": str(current), "object": object_name,
                          "filename": filename, "resolved": str(child) if child else None})
            if child is not None and child.suffix.lower() == ".spck" and child not in visited:
                pending.append(child)
        for (rail, side, index), entry in sorted(entries.items()):
            filename = entry.get("filename")
            if not filename:
                continue
            source = _resolve_reference(filename, current, search_paths, root)
            if source and source not in hashes:
                hashes[source] = hashlib.sha256(source.read_bytes()).hexdigest()
            profiles.append({"source_model": str(current), "rail": rail,
                             "side": "right" if side == "r" else "left",
                             "index": index, "filename": filename,
                             "station_m": entry.get("s_m"),
                             "station_expression": entry.get("station_expression"),
                             "path": str(source) if source else None,
                             "sha256": hashes.get(source) if source else None,
                             "file_line": entry.get("file_line"), "station_line": entry.get("s_line")})
    coincident: list[dict[str, Any]] = []
    grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in profiles:
        grouped[row["source_model"], row["rail"], row["side"]].append(row)
    for (source_model, rail, side), rows in grouped.items():
        previous = None
        for row in sorted(rows, key=lambda item: item["index"]):
            if previous and row["station_m"] is not None and row["station_m"] == previous["station_m"]:
                coincident.append({"source_model": source_model, "rail": rail, "side": side,
                                   "station_m": row["station_m"],
                                   "indices": [previous["index"], row["index"]],
                                   "distinct_contents": row["sha256"] != previous["sha256"]})
            previous = row
    identity = [{key: row.get(key) for key in ("source_model", "rail", "side", "index",
                                                "station_m", "sha256")} for row in profiles]
    geometry_sha = hashlib.sha256(json.dumps(identity, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    return {
        "schema_version": "velch-simpack-track-catalog-v1",
        "scope": "read-only model statements and profile references; no Simpack dynamic track import",
        "model": str(initial), "model_root": str(root), "active_track_reference": active_track,
        "model_files": scanned, "submodel_links": links, "track_object_raw_codes": track_objects,
        "rail_body_mass_definitions": rail_bodies, "modal_file_references": modal_references,
        "profile_references": profiles, "coincident_stations": coincident,
        "summary": {"scanned_models": len(scanned), "profile_references": len(profiles),
                    "unique_prr_files": len(hashes),
                    "missing_profile_references": sum(row["path"] is None for row in profiles),
                    "coincident_station_pairs": len(coincident),
                    "profile_set_sha256": geometry_sha,
                    "geometry_readable": bool(profiles) and all(row["path"] and row["station_m"] is not None for row in profiles),
                    "simpack_flexible_dynamics_imported": False,
                    "simpack_rigid_body_dynamics_imported": False},
    }


def profile_series_from_catalog(catalog: dict[str, Any], rail: str, side: str,
                                event_branches: dict[str, dict[str, str]] | None = None) -> ProfileSeries:
    """Read PRR geometry into Velch after the caller chooses a rail/side and events."""
    rows = [row for row in catalog["profile_references"] if row["rail"] == rail and row["side"] == side]
    if not rows:
        raise ValueError(f"no Simpack PRR references for {rail} / {side}")
    stations = []
    for row in sorted(rows, key=lambda item: item["index"]):
        if not row["path"] or row["station_m"] is None:
            raise ValueError(f"unresolved PRR reference at index {row['index']}")
        profile = load_profile(Path(row["path"]), file_format="prr", surface="rail_top")
        if profile.source_sha256 != row["sha256"]:
            raise ValueError(f"PRR changed after catalog creation: {row['path']}")
        stations.append(Station(float(row["station_m"]), profile,
                                f"{side}_{row['index']}_{row['filename']}"))
    return ProfileSeries(stations, event_branches)
