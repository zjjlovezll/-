"""Assemble the one canonical turnout DB: CN60-1100-1:18 straight, self-contained.

The data set on `G:` has seven mileage tables for the same turnout, including superseded
revisions (``cxg`` vs ``cxg-250801``, ``zjg_zgyg`` vs ``_250720`` vs ``_250722``) and a
curved-side family (``qjg_cgyg``).  This script fixes **one** straight-line set, copies only
the section files those tables reference, and writes an index that records both the choice
and what it superseded -- so "which geometry is the baseline" stops being a question.

    python -X utf8 scripts/s84_turnout_database.py

Outputs ``vehicles/turnouts/CN60-1100-1_18/{mileage,sections,index.json}``.
"""
from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "vehicles" / "turnouts" / "CN60-1100-1_18"
SOURCE = Path(r"G:\研究生\SDITT-RW-FT-250728\SDITT-RW-FT-250728\WRProfile-07(009)-1_18")
MILEAGE = SOURCE / "07(009)-Mileage"

#: Canonical set.  Each entry: family -> (table, why this revision).
CANONICAL: dict[str, tuple[str, str]] = {
    "qjbg": ("07(009)-Mileage-qjbg.txt", "only revision; 76 stations 0.000-1000.0 m"),
    "zjg_zgyg": (
        "07(009)-Mileage-zjg_zgyg_250722.txt",
        "latest of three; 160 stations 50.578-104.419 m (blade 3-72 mm, then wing rail)",
    ),
    "cxg": (
        "07(009)-Mileage-cxg-250801.txt",
        "latest; 66 stations 103.280-116.440 m (point rail 12.5-72 mm)",
    ),
}

#: Tables present on the source and deliberately NOT used, with the reason.
SUPERSEDED: dict[str, str] = {
    "07(009)-Mileage-zjg_zgyg.txt": "undated master, wider station range; superseded by _250722",
    "07(009)-Mileage-zjg_zgyg_250720.txt": "superseded by _250722 the next day",
    "07(009)-Mileage-cxg.txt": "2020-04-22 revision, superseded by cxg-250801",
    "07(009)-Mileage-qjg_cgyg.txt": "curved-side family (曲尖轨+曲翼轨), needed only for the diverging route",
}


@dataclass(frozen=True)
class Station:
    mileage_m: float
    file_name: str


def read_table(path: Path) -> list[Station]:
    stations: list[Station] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        parts = line.replace("\t", " ").split()
        if len(parts) < 2:
            continue
        try:
            mileage = float(parts[0])
        except ValueError:
            continue
        stations.append(Station(mileage, parts[1]))
    return stations


def index_source_files() -> dict[str, Path]:
    index: dict[str, Path] = {}
    for path in SOURCE.rglob("*"):
        if path.suffix.lower() in {".txt", ".prr"} and path.is_file():
            index.setdefault(path.name, path)
    return index


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    if not MILEAGE.is_dir():
        print(f"source mileage folder missing: {MILEAGE}")
        return 2
    present = sorted(p.name for p in MILEAGE.glob("*.txt"))
    print(f"mileage tables on source: {len(present)}")
    for name in present:
        print(f"  {'IN USE ' if any(t[0] == name for t in CANONICAL.values()) else 'skip   '} {name}")

    (DB / "mileage").mkdir(parents=True, exist_ok=True)
    (DB / "sections").mkdir(parents=True, exist_ok=True)
    source_index = index_source_files()

    families: dict[str, object] = {}
    copied: dict[str, dict[str, object]] = {}
    missing: list[str] = []
    for family, (table_name, note) in CANONICAL.items():
        table = MILEAGE / table_name
        stations = read_table(table)
        shutil.copy2(table, DB / "mileage" / table_name)
        unique = sorted({s.file_name for s in stations})
        for name in unique:
            source = source_index.get(name)
            if source is None:
                missing.append(name)
                continue
            target = DB / "sections" / name
            if name not in copied:
                shutil.copy2(source, target)
                copied[name] = {
                    "file": name,
                    "bytes": target.stat().st_size,
                    "sha256": sha256(target),
                    "source": str(source),
                }
        families[family] = {
            "table": table_name,
            "note": note,
            "stations": len(stations),
            "mileage_range_m": [stations[0].mileage_m, stations[-1].mileage_m] if stations else [],
            "section_files": len(unique),
        }
        print(
            f"{family:10s} stations {len(stations):4d}  sections {len(unique):4d}  "
            f"{families[family]['mileage_range_m']}  <- {table_name}"
        )

    total_bytes = sum(int(v["bytes"]) for v in copied.values())
    index = {
        "schema_version": "velch-turnout-db-v1",
        "id": "CN60-1100-1_18",
        "name": "18 号单开道岔 CN60-1100-1:18（直向基准）",
        "number": 18,
        "curve_radius_m": 1100.0,
        "lateral_speed_limit_kmh": 80.0,
        "gauge_m": 1.435,
        "rows": families,
        "sections": copied,
        "section_count": len(copied),
        "section_bytes": total_bytes,
        "missing_sections": missing,
        "superseded_tables": SUPERSEDED,
        "provenance": {
            "source_root": str(SOURCE),
            "mileage_folder": str(MILEAGE),
            "note": (
                "Only the three tables in `rows` are canonical.  The section files are copied "
                "verbatim (byte-identical, sha256 recorded) so the case no longer depends on G:."
            ),
        },
        "status": "geometry_only_not_yet_seated",
    }
    (DB / "index.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    print(
        f"\nDB: {DB}\n  sections {len(copied)} ({total_bytes/1e6:.1f} MB), "
        f"tables {len(CANONICAL)}, missing {len(missing)}"
    )
    return 0 if not missing else 1


if __name__ == "__main__":
    raise SystemExit(main())
