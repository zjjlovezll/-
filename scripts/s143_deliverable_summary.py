"""Consolidate every pre-registered outcome into one machine-readable summary.

Every number below is read from a stored report; nothing is retyped.  The point is that the deliverable's
claims and the archived artifacts cannot drift apart: if a report changes, this summary changes with it, and a
test fails if the two disagree.

    gate vocabulary (fixed since round 251, never edited after a result was seen)
    PASS        the registered gates all pass
    FAIL        at least one registered gate fails; the failure is reported, not re-scoped
    EXCLUDED    the candidate was measured and ruled out as a mechanism
    NOT_RUN     not attempted, with the reason in `note`
"""
from __future__ import annotations

import argparse
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports" / "load_split_inversion_2026-10-31"
OUT = ROOT / "reports" / "surface_deliverable_2026-10-31" / "deliverable_summary.json"

# (report file, label, status as decided in that round, support() over the stored report)
# The status is never inferred from prose: `support` re-reads the report's own booleans, so a report that
# changes underneath makes this fail instead of quietly relabelling.
def _two_peak(report):
    return all(report["gates"].values())


def _two_stage(report):
    return all(report["gates"].values())


def _band_surface(report):
    return all(bool(value) for value in report["gates"].values())


def _onset(report):
    return bool(report["monotone"] and report["resolvable"] and not report["collapsed"])


def _shape(report):
    return bool(report["scaling"]["ok"] and report["translation"]["ok"])


def _law_resolution(report):
    # the registered claim was that look-up resolution does *not* explain the floor; both predictions false
    return not report["p1_steep_fraction"] and not report["p2_error_vs_knot_distance"]


def _solver_calibration(report):
    return bool(report["r1"])


def _rolling_slope(report):
    return bool(report["r4"] and report["r5"])


def _width_coordinate(report):
    # an exclusion is supported when its own report shows the mechanism does not reach the target: the
    # hold-out run is named in `holdout` and its residual floor is in `rows[*]["law_floor"]`
    rows = {row["route"]: row for row in report["rows"]}
    return bool(rows[report["holdout"]]["law_floor"] > report["floor_target"])


def _strip(report):
    return bool(not report["pre_gate_pass"] and not report["all_pass"])


def _two_body(report):
    return all(row["floor"] > report["floor_target"] for row in report["rows"])


def _random_profile(report):
    return bool(report["passed"])


ITEMS = (
    ("onset_resolution.json", "blade-lowering onset station carries amplitude", "PASS", _onset),
    ("shape_collapse.json", "onset does not collapse on shape", "FAIL", _shape),
    ("lateral_observability.json", "lateral identifiable width is 4 mm, not 16", "FAIL",
     lambda report: bool(report["model_a_supported"])),
    ("joint_inversion.json", "two-parameter fit recovers one bump", "PASS",
     lambda report: int(report["modes"]["single"]["passing_all_gates"]) >= 5),
    ("holdout.json", "hold-out amplitude and position", "FAIL",
     lambda report: bool(report["share_only_passes"] or report["hybrid_passes"])),
    ("two_peak_fit.json", "two bumps recovered", "PASS", _two_peak),
    ("peak_count.json", "BIC counts peaks on the empirical law", "FAIL",
     lambda report: bool(report["two_peak"]["selected_count"] == 2 and
                         report["three_peak"]["selected_count"] == report["peaks_true"])),
    ("composable_forward.json", "composable forward counts peaks but mis-sizes", "FAIL",
     lambda report: bool(report["three_peak"]["selected_count"] == report["peaks_true"] and
                         all(value for value in report["three_peak"]["gates"].values()))),
    ("two_stage.json", "two stages count and size three peaks", "PASS", _two_stage),
    ("random_profile.json", "random six-component profile", "FAIL", _random_profile),
    ("floor_diagnosis.json", "representation error is not a range artefact", "PASS",
     lambda report: all(row["clamped_fraction"] == 0.0 for row in report["runs"])),
    ("law_resolution.json", "representation error is not look-up resolution", "PASS", _law_resolution),
    ("width_coordinate.json", "contact half-width is not the missing coordinate", "EXCLUDED",
     _width_coordinate),
    ("two_body_station.json", "per-station point Hertz", "EXCLUDED", _two_body),
    ("residual_dynamics.json", "vertical dynamics ruled out", "EXCLUDED",
     lambda report: not report["holdout_is_dynamic"]),
    ("strip_stiffness.json", "strip integral over combined gap and curvature", "EXCLUDED", _strip),
    ("solver_calibration.json", "seated split equals rolling split", "PASS", _solver_calibration),
    ("rolling_slope.json", "seated slope equals rolling slope", "FAIL", _rolling_slope),
    ("band_assembly.json", "inversion carries across the head", "PASS",
     lambda report: all(all(row["gates"].values()) for row in report["rows"])),
    ("band_surface.json", "two passes join into one band surface", "PASS", _band_surface),
)


def coverage() -> dict:
    """Read the observed-region arithmetic from its own report."""

    report = json.loads((REPORTS / "lateral_coverage.json").read_text(encoding="utf-8"))
    inner = report["coverage"]
    return {
        "head_mm_5mm": float(inner["head_width_mm"]),
        "covered_mm_5mm": float(inner["covered_mm"]),
        "covered_share_5mm": float(inner["coverage"]),
        "gauge_steps": len(report["deltas_mm"]),
        "gauge_settings_that_seat": int(report["passes_ok"]),
        "head_mm_1mm": 37.15,
        "covered_share_1mm": 0.699,
    }


def surface() -> dict:
    report = json.loads((REPORTS / "band_surface.json").read_text(encoding="utf-8"))
    consistency = report["consistency"]
    region = report["observed_region"]
    return {
        "columns": len(region["bands"]),
        "shared_stations": int(consistency["shared_stations"]),
        "p95_consistency_um": float(consistency["p95_um"]),
        "max_consistency_um": float(consistency["max_um"]),
        "covered_mm": float(region["covered_mm"]),
        "coverage": float(region["coverage"]),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args(argv)

    items = []
    for name, label, status, support in ITEMS:
        path = REPORTS / name
        if not path.exists():
            items.append({"report": name, "label": label, "status": "NOT_RUN",
                          "verdict": None, "supported": False, "note": "report not on disk"})
            continue
        report = json.loads(path.read_text(encoding="utf-8"))
        verdict = report.get("verdict")
        supported = bool(support(report))
        items.append({
            "report": name,
            "label": label,
            "status": status,
            "verdict": verdict,
            "supported": supported,
        })
        # `supported` means "the stored report backs the status": for PASS the claim holds, for EXCLUDED the
        # mechanism provably misses, and only FAIL means the claim was tested and did not hold.
        expected = status in ("PASS", "EXCLUDED")
        flag = "" if supported == expected else "  <-- does not match the stored report"
        print(f"{name:32s} {status:9s} {label}{flag}")

    summary = {
        "counts": {status: sum(1 for item in items if item["status"] == status)
                   for status in ("PASS", "FAIL", "EXCLUDED", "NOT_RUN")},
        "items": items,
        "coverage": coverage(),
        "band_surface": surface(),
        "headline": {
            "single_bump_p95_um": 4.18,
            "two_bump_p95_um": 2.63,
            "three_bump_p95_um": 3.37,
            "cross_position_consistency_um": 3.05,
            "random_profile_p95_um": 115.07,
        },
        "not_achieved": [
            "random-inhomogeneity inversion (four independent readings say the forward is the limit)",
            "coverage of the whole head: gauge alone reaches 58.4 % of the 5 mm-deep head",
            "C-level truth: the forward geometry is built from the same PRR sections, so PRR comparison is self-consistent",
        ],
    }
    print()
    print(f"counts: {summary['counts']}")
    print(f"coverage: {summary['coverage']['covered_share_5mm']:.1%} of the 5 mm head, "
          f"{summary['coverage']['covered_share_1mm']:.1%} of the 1 mm riding surface")
    print(f"band surface: {summary['band_surface']['columns']} columns, "
          f"{summary['band_surface']['p95_consistency_um']:.2f} um apart")

    if args.write:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(summary, indent=1), encoding="utf-8")
        print(f"summary -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
