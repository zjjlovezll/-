"""Read-only audit of the CRH380A_M geometry referenced by a Velch catalog."""
from __future__ import annotations

import json
import re
from pathlib import Path

from velch.profiles import load_profile
from velch.simpack_track_import import profile_series_from_catalog


CATALOG = Path(__file__).with_name("crh380a_m_track_catalog.json")
REPORT = Path(__file__).with_name("crh380a_m_database_audit.json")


def main() -> None:
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    root = Path(catalog["model_root"])
    wheelset = root / "mbs_db_substructure" / "CRH380A_M_Wheelset.spck"
    wheelset_text = wheelset.read_text(encoding="utf-8", errors="replace")
    wheel_names = re.findall(r"^rwpair\.wheel\.prof\.file\s*\([^)]*\)\s*=\s*'([^']+)'",
                             wheelset_text, re.M | re.I)
    wheel_names = sorted(set(wheel_names))
    wheel_checks = []
    for name in wheel_names:
        path = root / "wheel_rail_profiles" / name
        profile = load_profile(path, file_format="prr", surface="wheel_lower")
        wheel_checks.append({"name": name, "path": str(path), "sha256": profile.source_sha256,
                             "graph_points": len(profile.y_m), "collapsed_points": profile.collapsed_points})

    rows = catalog["profile_references"]
    files = sorted({r["path"] for r in rows if r["path"]})
    successes = []
    failures = []
    for name in files:
        try:
            profile = load_profile(Path(name), file_format="prr", surface="rail_top")
            successes.append({"path": name, "sha256": profile.source_sha256,
                              "graph_points": len(profile.y_m), "collapsed_points": profile.collapsed_points})
        except (OSError, ValueError) as exc:
            failures.append({"path": name, "error": str(exc)})
    stations = [r["station_m"] for r in rows if r["station_m"] is not None]
    coincident = catalog["coincident_stations"]
    first_event = next((x for x in coincident if x["distinct_contents"]), None)
    event_probe = None
    if first_event is not None:
        series = profile_series_from_catalog(catalog, first_event["rail"], first_event["side"])
        try:
            series.sample(first_event["station_m"])
            event_probe = "sampled_without_explicit_branch"
        except ValueError as exc:
            event_probe = f"rejected_without_explicit_branch: {exc}"
    carbody_text = Path(catalog["model"]).read_text(encoding="utf-8", errors="replace")
    speed = re.search(r"^subvar\.str\s*\(\s*\$_Speed\s*\)\s*=\s*'([^']+)'",
                      carbody_text, re.M)
    end_time = re.search(r"^slv\.integ\.tend\.time\s*\([^)]*\)\s*=\s*([^!\s]+)",
                         carbody_text, re.M)
    results_dir = Path(catalog["model"]).with_suffix(".output")
    candidate_results = [{"path": str(p), "bytes": p.stat().st_size}
                         for p in sorted(results_dir.glob("*.sbr"))] if results_dir.is_dir() else []
    report = {
        "schema_version": "velch-crh380a-m-database-audit-v1",
        "scope": "read-only substructure and profile audit; no Simpack or Velch vehicle integration run",
        "source_model": catalog["model"],
        "source_model_sha256": catalog["model_files"][0]["sha256"],
        "profile_set_sha256": catalog["summary"]["profile_set_sha256"],
        "model_chain": [r["path"] for r in catalog["model_files"]],
        "rail_profile_references": len(rows),
        "unique_rail_prr_files": len(files),
        "rail_prr_files_parsed": len(successes),
        "rail_prr_parse_failures": failures,
        "rail_graph_point_count_range": [min(x["graph_points"] for x in successes),
                                         max(x["graph_points"] for x in successes)] if successes else None,
        "station_range_m": [min(stations), max(stations)] if stations else None,
        "coincident_station_pairs": len(coincident),
        "distinct_coincident_station_pairs": sum(bool(x["distinct_contents"]) for x in coincident),
        "first_coincident_station_sampling": event_probe,
        "wheel_profiles_referenced_directly": wheel_checks,
        "active_track_reference": catalog["active_track_reference"],
        "configured_speed_expression": speed.group(1) if speed else None,
        "configured_end_time_s": float(end_time.group(1)) if end_time else None,
        "candidate_simpack_results": candidate_results,
        "geometry_input_gate": "passed_file_and_format_audit" if not failures and wheel_checks else "failed",
        "contact_location_gate": "not_run; coincident stations require active branch mapping",
        "vehicle_dynamics_gate": "not_run; carbody file has solver settings but runtime validity is unverified",
        "simpack_comparison_gate": "not_run; candidate SBR provenance is unverified",
    }
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("rail_profile_references", "unique_rail_prr_files",
                                             "rail_prr_files_parsed", "rail_prr_parse_failures",
                                             "station_range_m", "coincident_station_pairs",
                                             "distinct_coincident_station_pairs",
                                             "wheel_profiles_referenced_directly",
                                             "geometry_input_gate")}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
