"""Turn a Simpack track catalog into a Velch case — geometry from Simpack, physics from you.

What this module does, and what it refuses to do
-----------------------------------------------
The catalog (``velch inspect-simpack-track``) records *statements the Simpack model makes*: which
rail profile file sits at which mileage on which rail.  That is geometry, and it is safe to carry
over mechanically.

Everything else — masses, inertias, suspension stiffness and damping, contact stiffness, friction,
solver tolerances — decides the frozen gates (59 680.5769 N static load, 65.47 µm equilibrium,
89.68 / 170.61 kN peaks).  None of it can be read out of a ``.spck`` honestly, so this module takes
those values from a **template case you name** and only replaces the rail station table.

The output is therefore always "the template's physics, the Simpack model's rail geometry", and the
sidecar written next to it says exactly which file supplied which number.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence

SCHEMA_VERSION = "velch-simpack-case-v1"
CATALOG_SCHEMA = "velch-simpack-track-catalog-v1"


class SimpackCaseError(RuntimeError):
    """A catalog or template that cannot be turned into a case without guessing."""


@dataclass(frozen=True)
class CatalogStation:
    """One rail profile reference as the Simpack model states it."""

    rail: str
    side: str
    index: int
    station_m: float
    path: str
    sha256: str


@dataclass(frozen=True)
class CaseBuild:
    """What was written, and what the caller should say about it."""

    case_path: Path
    sidecar_path: Path
    station_count: int
    dropped_duplicates: int
    shift_m: float
    profile_set_sha256: str
    template: str
    model: str
    profiles_from: str = "simpack"

    def summary(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "case": str(self.case_path),
            "sidecar": str(self.sidecar_path),
            "station_count": self.station_count,
            "dropped_duplicates": self.dropped_duplicates,
            "shift_m": round(self.shift_m, 6),
            "profile_set_sha256": self.profile_set_sha256,
            "template": self.template,
            "simpack_model": self.model,
            "physics_source": "template case (explicit); Simpack supplies rail geometry only",
            "profiles_from": self.profiles_from,
            "simpack_dynamics_imported": False,
        }


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_catalog(path: str | Path) -> dict[str, Any]:
    catalog_path = Path(path)
    if not catalog_path.is_file():
        raise SimpackCaseError(f"catalog not found: {catalog_path}")
    try:
        catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise SimpackCaseError(f"{catalog_path} is not JSON: {error}") from error
    if catalog.get("schema_version") != CATALOG_SCHEMA:
        raise SimpackCaseError(
            f"{catalog_path} is {catalog.get('schema_version')!r}, expected {CATALOG_SCHEMA!r}")
    summary = catalog.get("summary") or {}
    if not summary.get("geometry_readable"):
        missing = summary.get("missing_profile_references", "?")
        raise SimpackCaseError(
            "the catalog says geometry_readable=false "
            f"(missing_profile_references={missing}); fix the model root before deriving a case")
    return catalog


def stations(catalog: dict[str, Any], *, side: str | None = None,
             rail: str | None = None) -> list[CatalogStation]:
    raw: Iterable[dict[str, Any]] = catalog.get("profile_references") or []
    chosen: list[CatalogStation] = []
    for entry in raw:
        if side is not None and entry.get("side") != side:
            continue
        if rail is not None and entry.get("rail") != rail:
            continue
        chosen.append(
            CatalogStation(
                rail=str(entry.get("rail", "")),
                side=str(entry.get("side", "")),
                index=int(entry.get("index", 0)),
                station_m=float(entry.get("station_m", 0.0)),
                path=str(entry.get("path", "")),
                sha256=str(entry.get("sha256", "")),
            )
        )
    chosen.sort(key=lambda item: (item.rail, item.station_m, item.index))
    if not chosen:
        raise SimpackCaseError(
            f"the catalog has no profile references for side={side!r} rail={rail!r}")
    return chosen


def _deduplicate(entries: Sequence[CatalogStation]) -> tuple[list[CatalogStation], int]:
    """Keep one station per mileage.

    The turnout model states two different surfaces at the same mileage (the switch blade and the
    stock rail).  ``ProfileSeries`` interpolates one surface per station, so a duplicate cannot be
    represented; the first one wins and the sidecar records how many were dropped, because that is
    a real loss of information rather than a tidy-up.
    """

    seen: dict[float, CatalogStation] = {}
    for entry in entries:
        key = round(entry.station_m, 9)
        seen.setdefault(key, entry)
    kept = sorted(seen.values(), key=lambda item: item.station_m)
    return kept, len(entries) - len(kept)


def _thin(entries: Sequence[CatalogStation], sample: int | None) -> list[CatalogStation]:
    if sample is None or sample <= 0 or sample >= len(entries):
        return list(entries)
    if sample == 1:
        return [entries[0]]
    step = (len(entries) - 1) / (sample - 1)
    picked = [entries[round(index * step)] for index in range(sample)]
    unique: list[CatalogStation] = []
    for entry in picked:
        if not unique or entry.station_m != unique[-1].station_m:
            unique.append(entry)
    return unique


def _template_profile(profile: dict[str, Any], path: str) -> dict[str, Any]:
    clone = dict(profile)
    clone["file"] = path
    return clone


def build_case(*, catalog_path: str | Path, template_path: str | Path, out_path: str | Path,
               side: str = "left", rail: str | None = None, sample: int | None = None,
               x_start_m: float, duration_s: float | None = None,
               case_id: str | None = None, keep_profiles: bool = False) -> CaseBuild:
    """Write a case whose rail geometry comes from the catalog and whose physics comes from a case.

    ``x_start_m`` is required and must lie inside the model's own mileage span, because the station
    mileages are imported unchanged: shifting them is what makes a rail stop covering the first
    wheel position.  The sidecar records the span the case actually covers.
    """

    catalog = load_catalog(catalog_path)
    catalog_file = Path(catalog_path)
    template_file = Path(template_path)
    if not template_file.is_file():
        raise SimpackCaseError(f"template case not found: {template_file}")
    template = json.loads(template_file.read_text(encoding="utf-8"))

    rail_templates = template.get("rail_templates") or []
    index_of = {str(item.get("id")): position for position, item in enumerate(rail_templates)}
    if side not in index_of:
        raise SimpackCaseError(
            f"template has no rail template named {side!r}; it has {sorted(index_of)}")
    position = index_of[side]
    target = rail_templates[position]
    if target.get("bodies"):
        raise SimpackCaseError(
            f"template rail {side!r} is split into bodies; pick a single-surface template so the "
            "catalog's station table maps one-to-one")

    chosen = stations(catalog, side=side, rail=rail)
    chosen, dropped = _deduplicate(chosen)
    chosen = _thin(chosen, sample)

    missing = [entry.path for entry in chosen if not Path(entry.path).is_file()]
    if missing:
        raise SimpackCaseError(
            f"{len(missing)} catalog profile files are gone from disk, e.g. {missing[0]}")

    # Mileages stay exactly as the model states them.  Shifting them is how a rail ends up covering
    # 13.5–163.5 m while the first wheel sits at 13.5 m and the contact solver finds nothing: one
    # side then carries twice the even share and the preload equilibrium fails.  If the requested
    # start is outside the model's own span, that is a question for the caller, not a silent shift.
    span_lo, span_hi = chosen[0].station_m, chosen[-1].station_m
    travel_s = float((template.get("vehicle") or {}).get("travel_speed_m_s", 0.0))
    window_s = float(duration_s if duration_s is not None else
                     (template.get("run") or {}).get("duration_s", 0.0))
    needed_hi = float(x_start_m) + travel_s * window_s
    if not (span_lo <= float(x_start_m) and needed_hi <= span_hi):
        raise SimpackCaseError(
            f"x_start {x_start_m} m + {needed_hi - float(x_start_m):.2f} m of travel leaves the "
            f"model's coverage {span_lo}–{span_hi} m (side {side!r}); pick a start inside it")
    shift = 0.0
    profile_template = dict((target.get("stations") or [{}])[0].get("profile") or {})
    if not profile_template:
        raise SimpackCaseError(f"template rail {side!r} has no profile metadata to inherit")

    # ``keep_profiles`` keeps the template's surface file and imports only the station *layout*.
    # The full import (default) mixes rail sections that were never calibrated against this vehicle,
    # and the run then fails the vertical preload equilibrium — loudly, in the summary.
    source_files = [str(profile_template.get("file", ""))] * len(chosen) if keep_profiles \
        else [entry.path for entry in chosen]
    new_stations = [
        {
            "id": f"SP{entry.index:03d}",
            "s_m": round(entry.station_m + shift, 6),
            "profile": _template_profile(profile_template, path),
        }
        for entry, path in zip(chosen, source_files)
    ]
    target["stations"] = new_stations

    run = dict(template.get("run") or {})
    run["x_start_m"] = float(x_start_m)
    if duration_s is not None:
        if duration_s <= 0:
            raise SimpackCaseError(f"duration_s must be positive, got {duration_s}")
        run["duration_s"] = float(duration_s)
    template["run"] = run
    template["case_id"] = case_id or f"simpack_{side}_{Path(template_file).stem}"
    # ``purpose`` is a closed vocabulary in VehicleCase (synthetic | engineering); a Simpack-derived
    # case is still an engineering case — the difference lives in ``purpose_detail`` and the sidecar.
    template["purpose"] = "engineering"
    if not template.get("parameter_source"):
        raise SimpackCaseError(f"{template_file} has no parameter_source to inherit")
    template["purpose_detail"] = (
        f"rail geometry from {catalog.get('model')} (side {side}); physics from "
        f"{template_file.name}. Generated by velch simpack-case.")

    out = Path(out_path)
    if out.suffix.lower() != ".json":
        raise SimpackCaseError(f"out_path must end with .json, got {out}")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(template, ensure_ascii=False, indent=2) + "\n",
                   encoding="utf-8", newline="\n")

    sidecar = out.with_suffix(".simpack.json")
    sidecar.write_text(json.dumps({
        "schema_version": SCHEMA_VERSION,
        "catalog": str(catalog_file),
        "catalog_sha256": _sha256(catalog_file),
        "simpack_model": catalog.get("model"),
        "simpack_model_root": catalog.get("model_root"),
        "profile_set_sha256": (catalog.get("summary") or {}).get("profile_set_sha256"),
        "template": str(template_file),
        "template_sha256": _sha256(template_file),
        "case": str(out),
        "case_sha256": _sha256(out),
        "side": side,
        "rail": rail,
        "shift_m": round(shift, 6),
        "model_mileage_span_m": [round(span_lo, 6), round(span_hi, 6)],
        "x_start_m": float(x_start_m),
        "duration_s": run.get("duration_s"),
        "station_count": len(new_stations),
        "dropped_duplicate_stations": dropped,
        "stations": [
            {"s_m": entry["s_m"], "profile": entry["profile"]["file"],
             "catalog_sha256": source.sha256}
            for entry, source in zip(new_stations, chosen)
        ],
        "from_simpack": (["station mileage", "rail side", "station count"] if keep_profiles
                         else ["rail profile file", "station mileage", "rail side"]),
        "profiles_from": "template" if keep_profiles else "simpack",
        "from_template": ["vehicle", "contact", "wheels", "track_dynamics",
                          "equilibrate_vertical", "run"],
        "simpack_dynamics_imported": False,
        "not_imported": ["rigid body dynamics", "flexible (modal) track", "solver settings",
                         "measured or reference results"],
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")

    return CaseBuild(
        case_path=out,
        sidecar_path=sidecar,
        station_count=len(new_stations),
        dropped_duplicates=dropped,
        shift_m=shift,
        profile_set_sha256=str((catalog.get("summary") or {}).get("profile_set_sha256")),
        template=str(template_file),
        model=str(catalog.get("model")),
        profiles_from="template" if keep_profiles else "simpack",
    )


def describe(catalog: dict[str, Any]) -> dict[str, Any]:
    """A short, quotable digest of what the catalog found — used by the CLI and the docs."""

    summary = dict(catalog.get("summary") or {})
    rails: dict[str, int] = {}
    for entry in catalog.get("profile_references") or []:
        key = f"{entry.get('rail')}:{entry.get('side')}"
        rails[key] = rails.get(key, 0) + 1
    mileages = [float(entry.get("station_m", 0.0))
                for entry in catalog.get("profile_references") or []]
    summary["rails"] = rails
    if mileages:
        summary["mileage_span_m"] = [round(min(mileages), 3), round(max(mileages), 3)]
    return summary
