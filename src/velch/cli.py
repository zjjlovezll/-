"""Command line interface for bounded, auditable Velch research cases."""
from __future__ import annotations

import argparse
from dataclasses import asdict
import json
import sys
from pathlib import Path

from .contact_native import (ContactNativeUnavailable, HertzProbe, assess_spherical_hertz_probe,
                             inspect_contact_native, run_contact_hertz_probe)
from .model import load_case
from .profiles import load_profile
from .metrics import AssessmentError, assess_history, format_assessment
from .simpack_track_import import inspect_simpack_track
from .solver import SimulationFailure, save_result, simulate
from .vehicle import load_vehicle_case
from .vehicle_solver import save_vehicle_result, simulate_vehicle
from .parallel import run_vehicle_batch


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="velch", description="Reduced-order turnout wheel/rail dynamics")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="run one JSON case using its declared solver method")
    run.add_argument("case", type=Path)
    run.add_argument("--output", type=Path, required=True)
    vehicle_run = sub.add_parser("run-vehicle", help="run a v2 four-axle vehicle/turnout case")
    vehicle_run.add_argument("case", type=Path)
    vehicle_run.add_argument("--output", type=Path, required=True)
    vehicle_run.add_argument("--workers", type=int, default=1,
                             help="threads for the per-axle contact evaluation (1 = serial)")
    batch = sub.add_parser("run-vehicle-batch",
                           help="run several v2 cases in parallel worker processes")
    batch.add_argument("cases", type=Path, nargs="+")
    batch.add_argument("--output-root", type=Path, required=True)
    batch.add_argument("--jobs", type=int, default=1,
                       help="number of cases solved concurrently (use the physical core count)")
    batch.add_argument("--workers", type=int, default=1,
                       help="contact threads inside each case (keep 1 when jobs fill the cores)")
    inspect = sub.add_parser("inspect-profile", help="inspect a two-column TXT/CSV or Simpack PRR")
    inspect.add_argument("file", type=Path)
    inspect.add_argument("--format", choices=("txt", "csv", "prr"), required=True)
    inspect.add_argument("--surface", choices=("rail_top", "wheel_lower"), required=True)
    simpack_track = sub.add_parser("inspect-simpack-track", help="read-only .spck rail/PRR catalog; no dynamics import")
    simpack_track.add_argument("model", type=Path)
    simpack_track.add_argument("--model-root", type=Path, required=True)
    simpack_track.add_argument("--output", type=Path, required=True)
    native_status = sub.add_parser("contact-native-status", help="check official CONTACT Python interface and native DLL")
    native_status.add_argument("--contact-root", type=Path, required=True)
    native_status.add_argument("--output", type=Path)
    native_probe = sub.add_parser("contact-hertz-probe", help="run official CONTACT module-3 grid convergence probe")
    native_probe.add_argument("case", type=Path, help="JSON with SI-valued HertzProbe fields")
    native_probe.add_argument("--contact-root", type=Path, required=True)
    native_probe.add_argument("--grids", type=int, nargs="+", default=[16, 32, 64])
    native_probe.add_argument("--output", type=Path, required=True)
    assess = sub.add_parser("assess", help="standard indices (Q/P, 轮重减载率, 轮轴横向力) from a saved run")
    assess.add_argument("run", type=Path, help="run output directory containing history.csv, or the CSV itself")
    assess.add_argument("--static-axle-load-n", type=float, default=None,
                        help="static axle load for the lateral-force limit (default: mean measured)")
    assess.add_argument("--output", type=Path, help="write assessment JSON here")
    agent = sub.add_parser("agent", help="machine-facing tools: manifest, call, doctor, serve-mcp")
    agent.add_argument("action", choices=("manifest", "call", "doctor", "serve"),
                       help="manifest = the tool table; call = run one tool from JSON; "
                            "doctor = self-check; serve = MCP over stdio")
    agent.add_argument("payload", nargs="?", help="for 'call': {\"tool\": name, \"arguments\": {...}}")
    args = parser.parse_args(argv)
    try:
        if args.command == "agent":
            # The agent layer holds no state and loads in ~80 ms; importing it late keeps a
            # plain simulation run from paying for it.
            from .agent.__main__ import main as agent_main

            return agent_main([args.action, *([args.payload] if args.payload else [])])
        if args.command == "contact-native-status":
            report = inspect_contact_native(args.contact_root)
            if args.output:
                args.output.parent.mkdir(parents=True, exist_ok=True)
                args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            print(json.dumps(report, ensure_ascii=False, indent=2))
            return 0 if report["ready_to_attempt_native_load"] else 2
        if args.command == "contact-hertz-probe":
            grids = sorted(set(args.grids))
            if len(grids) < 2 or len(grids) != len(args.grids) or any(g < 16 or g > 256 for g in grids):
                raise ValueError("provide at least two distinct CONTACT grids in [16, 256]")
            raw = json.loads(args.case.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                raise ValueError("probe case must be a JSON object")
            probe = HertzProbe(**raw)
            results = [run_contact_hertz_probe(args.contact_root, probe, grid_n=g) for g in grids]
            reference = results[-1]
            for result in results:
                result["relative_to_finest_grid"] = {
                    name: abs(result[name] - reference[name]) / max(abs(reference[name]), 1e-12)
                    for name in ("normal_force_n", "tangent_x_n", "tangent_y_n", "patch_area_m2")
                }
            report = {
                "schema_version": "velch-contact-grid-study-v1",
                "interpretation": "native module-3 grid study; spherical analytic benchmark only when curvatures match; no Simpack or vehicle validation claim",
                "case": asdict(probe), "native": inspect_contact_native(args.contact_root),
                "results": results,
            }
            if abs(probe.effective_gap_curvature_x_per_m - probe.effective_gap_curvature_y_per_m) <= 1e-12 * max(probe.effective_gap_curvature_x_per_m, probe.effective_gap_curvature_y_per_m):
                report["analytic_benchmark"] = assess_spherical_hertz_probe(probe, results)
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            print(json.dumps({"report": str(args.output), "grids": grids,
                              "normal_force_n": [r["normal_force_n"] for r in results]},
                             ensure_ascii=False, indent=2))
            return 0
        if args.command == "inspect-simpack-track":
            report = inspect_simpack_track(args.model, args.model_root)
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            print(json.dumps({"catalog": str(args.output), "summary": report["summary"]},
                             ensure_ascii=False, indent=2))
            return 0 if report["summary"]["geometry_readable"] else 2
        if args.command == "inspect-profile":
            profile = load_profile(args.file, file_format=args.format, surface=args.surface)
            print(json.dumps({"source": profile.source, "sha256": profile.source_sha256,
                              "point_count": len(profile.y_m), "collapsed_points": profile.collapsed_points,
                              "y_range_m": [float(profile.y_m[0]), float(profile.y_m[-1])],
                              "z_range_m": [float(profile.z_m.min()), float(profile.z_m.max())]},
                             ensure_ascii=False, indent=2))
            return 0
        if args.command == "assess":
            assessment = assess_history(args.run, static_axle_load_n=args.static_axle_load_n)
            print(format_assessment(assessment, assessment.static_axle_load_n))
            if args.output:
                args.output.parent.mkdir(parents=True, exist_ok=True)
                args.output.write_text(
                    json.dumps(assessment.as_dict(assessment.static_axle_load_n),
                               ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            return 0 if assessment.verdict(assessment.static_axle_load_n)["pass"] else 2
        if args.command == "run-vehicle":
            case = load_vehicle_case(args.case)
            result = simulate_vehicle(case, contact_workers=args.workers)
            csv_path, manifest_path = save_vehicle_result(case, result, args.output)
            print(json.dumps({"history": str(csv_path), "manifest": str(manifest_path),
                              "summary": result.summary}, ensure_ascii=False, indent=2))
            return 0 if result.summary["result_status"] == "numerically_checked" else 2
        if args.command == "run-vehicle-batch":
            report = run_vehicle_batch([Path(p) for p in args.cases], args.output_root,
                                       jobs=args.jobs, workers=args.workers)
            print(json.dumps(report, ensure_ascii=False, indent=2))
            return 0 if all(item["result_status"] == "numerically_checked"
                            for item in report["cases"]) else 2
        case = load_case(args.case)
        result = simulate(case)
        csv_path, manifest_path = save_result(case, result, args.output)
        print(json.dumps({"history": str(csv_path), "manifest": str(manifest_path),
                          "summary": result.summary}, ensure_ascii=False, indent=2))
        return 0 if result.summary["result_status"] == "numerically_checked" else 2
    except (OSError, ValueError, TypeError, KeyError, SimulationFailure,
            ContactNativeUnavailable, AssessmentError) as exc:
        print(json.dumps({"status": "failed", "error_type": type(exc).__name__, "message": str(exc)},
                         ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
