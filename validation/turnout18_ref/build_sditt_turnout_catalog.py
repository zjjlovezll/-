"""Assemble the SDITT 07(009) turnout profile library into a station-indexed catalog.

Why this exists: our own Simpack-derived catalog has ONE merged right-rail series plus a dummy left
rail, so it cannot express the diverging route (its left rail is simply absent).  SDITT ships the same
turnout (客专线(07)009) as per-rail-part Simpack .prr profiles plus Mileage maps, which *can* express
both routes.  This script turns that library into one JSON so the case builder never re-parses 2000
files.

Output: validation/turnout18_ref/sditt_turnout_catalog.json
  parts:  {part: {"versions": {date: [[station_m, relative_file], ...]}, "y_mm": [...], "z_mm": [...]}}
  stations: [{s_m, parts: {part: {"file", "y_mm": [lo, hi], "z_min_mm"}}}]
  coverage: per-part station spans, gaps, and which stations carry more than one part
"""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(r"G:\研究生\SDITT-RW-FT-250728\SDITT-RW-FT-250728\WRProfile-07(009)-1_18")
OUT = Path(__file__).resolve().parent / "sditt_turnout_catalog.json"

MEAS_LOCAL = re.compile(r"^(-?\d+(?:\.\d+)?)\s+(.+\.txt)\s*$")


def text_of(path: Path) -> str:
    raw = path.read_bytes()
    for encoding in ("utf-8", "gb18030", "latin-1"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("latin-1")


def prr_extent(path: Path) -> tuple[float, float, float]:
    """(y_lo_mm, y_hi_mm, z_min_mm) via velch's own PRR loader (proven on these files)."""
    from velch.profiles import load_profile

    graph = load_profile(path, file_format="prr", surface="rail_top")
    y_mm = graph.y_m * 1000.0
    z_mm = graph.z_m * 1000.0
    return (float(y_mm.min()), float(y_mm.max()), float(z_mm.min()))


def main() -> None:
    mileage_dir = ROOT / "07(009)-Mileage"
    parts: dict[str, dict] = {}
    for map_path in sorted(mileage_dir.glob("*.txt")):
        part = map_path.stem.replace("07(009)-Mileage-", "")
        entries: list[tuple[float, str]] = []
        for line in text_of(map_path).splitlines():
            match = MEAS_LOCAL.match(line.strip())
            if match:
                station = float(match.group(1))
                if station >= 1000.0:  # sentinel "end of track"
                    continue
                entries.append((station, match.group(2)))
        if entries:
            parts[part] = {"map": map_path.name, "stations": entries}

    # resolve file locations by searching the part's own folder
    folders = [p for p in ROOT.iterdir() if p.is_dir()]
    index: dict[str, Path] = {}
    for folder in folders:
        for file in folder.glob("*.prr"):
            index.setdefault(file.name, file)
        for file in folder.glob("*.txt"):
            index.setdefault(file.name, file)

    def resolve(name: str, part: str) -> Path | None:
        """The mileage maps name .txt twins; the cross-section data lives in the .prr sibling."""
        stem = Path(name).stem
        for candidate_name in (f"{stem}.prr", name):
            if candidate_name in index:
                return index[candidate_name]
        for folder in folders:
            for candidate_name in (f"{stem}.prr", name):
                candidate = folder / candidate_name
                if candidate.exists():
                    return candidate
        return None

    stations: dict[float, dict] = {}
    report: list[str] = []
    for part, info in parts.items():
        found = 0
        missing = 0
        spans: list[float] = []
        for station, name in info["stations"]:
            path = resolve(name, part)
            if path is None:
                missing += 1
                continue
            found += 1
            spans.append(station)
            if path.suffix.lower() == ".prr":
                y_lo, y_hi, z_min = prr_extent(path)
            else:
                y_lo, y_hi, z_min = (float("nan"),) * 3
            stations.setdefault(station, {}).setdefault(part, {
                "file": str(path),
                "y_mm": [round(y_lo, 3), round(y_hi, 3)],
                "z_min_mm": round(z_min, 3),
            })
        if spans:
            report.append(f"{part:<14} {len(spans):>3} stations "
                          f"{min(spans):8.3f} .. {max(spans):8.3f} m   "
                          f"resolved {found}  missing {missing}")

    multi = sorted(s for s, table in stations.items() if len(table) > 1)
    payload = {
        "source_root": str(ROOT),
        "turnout": "07(009)",
        "parts": {part: {"map": info["map"],
                         "stations": [[s, n] for s, n in info["stations"]]}
                  for part, info in parts.items()},
        "stations": {f"{s:.3f}": table for s, table in sorted(stations.items())},
        "summary": {
            "part_count": len(parts),
            "station_count": len(stations),
            "multi_part_stations": len(multi),
            "station_span_m": [min(stations), max(stations)] if stations else None,
        },
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")

    print("part            station span                     resolution")
    for line in report:
        print("  " + line)
    print(f"\nstations with >1 rail part: {len(multi)}")
    for station in multi[:12]:
        names = ", ".join(sorted(stations[station]))
        print(f"  {station:8.3f} m  {names}")
    if len(multi) > 12:
        print(f"  ... ({len(multi) - 12} more)")
    print(f"\nwritten: {OUT}  ({OUT.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
