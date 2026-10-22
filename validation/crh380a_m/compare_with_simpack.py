"""Compare the Velch CRH380A_M runs against the Simpack 350.sbr baseline.

Baseline: ``simpack-mcp-2021x/validation/CRH380A_M_2026-10-19/result_summary.json``
(2401 samples, 0.0005 s, front wheelset x 23.5 -> 140.167 m).

Only quantities that exist on both sides are compared: the vertical contact
force of the front wheelset on each side, sampled on the identical time grid.
The Simpack unit string was not exposed by Post/QSA; N is inferred from the
static equilibrium (see the report), not asserted.
"""
from __future__ import annotations

import csv
import json
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
VEH = HERE.parents[1]
BASE = VEH.parent / "simpack-mcp-2021x" / "validation" / "CRH380A_M_2026-10-19" / "result_summary.json"

SPEED_M_S = 350.0 / 3.6
X_START_M = 13.5
AXLE_OFFSET_M = {0: 8.75 + 1.25, 1: 8.75 - 1.25, 2: -8.75 + 1.25, 3: -8.75 - 1.25}


def load_history(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def series(rows: list[dict[str, str]], column: str) -> list[float]:
    return [float(r[column]) for r in rows]


def stats(values: list[float]) -> dict[str, float]:
    return {
        "n": len(values),
        "first": values[0],
        "last": values[-1],
        "min": min(values),
        "max": max(values),
        "mean": statistics.fmean(values),
    }


def fmt(value: float, width: int = 10, digits: int = 1) -> str:
    return f"{value:{width}.{digits}f}"


def main() -> int:
    base = json.loads(BASE.read_text(encoding="utf-8"))
    ch = base["channels"]
    print(f"baseline {BASE.name}: {base['sbr_sha256'][:16]}…  {base['sample_count']} samples, "
          f"t {base['time_first_s']} -> {base['time_last_s']:.6f} s")
    print(f"  carbody_x {ch['carbody_x']['first']} -> {ch['carbody_x']['last']:.6f}")
    print(f"  front_wheelset_x {ch['front_wheelset_x']['first']} -> {ch['front_wheelset_x']['last']:.6f}")
    print()

    for tag, out in (("A_plain", "out_A_1p2s"), ("B_turnout", "out_B_1p2s")):
        run = HERE / out
        manifest = json.loads((run / "manifest.json").read_text(encoding="utf-8"))
        summary = manifest["summary"]
        rows = load_history(run / "history.csv")
        print(f"=== run {tag} ({out}) ===")
        print(f"  case {summary['case_id']}  status {summary['result_status']}  dof {summary['total_dof']}  "
              f"track {summary['track_kind']}  samples {len(rows)}")
        print(f"  gates {sum(1 for v in summary['gates'].values() if v)}/{len(summary['gates'])} true: "
              f"{summary['gates']}")
        print(f"  max_penetration {summary['max_penetration_m']*1e3:.4f} mm  "
              f"friction_excess {summary['max_friction_excess_n']:.3g} N  "
              f"action_reaction {summary['max_translation_balance_error_n']:.3g} N  "
              f"preload {summary['vertical_preload_max_residual_n']:.3g} N")
        print(f"  edge-limited active samples {summary['edge_limited_active_output_samples']}  "
              f"nfev {summary['solver']['nfev']}")
        for rail in ("axle1_left", "axle1_right"):
            vals = series(rows, f"{rail}_normal_n")
            s = stats(vals)
            print(f"  {rail:12s} n={s['n']} first {fmt(s['first'])} last {fmt(s['last'])} "
                  f"min {fmt(s['min'])} max {fmt(s['max'])} mean {fmt(s['mean'])}")
        active = series(rows, "axle1_left_active")
        act_r = series(rows, "axle1_right_active")
        print(f"  active samples: left {int(sum(active))}/{len(active)}  right {int(sum(act_r))}/{len(act_r)}")
        print()

    # --- static load reconciliation ------------------------------------
    velch_static = stats(series(load_history(HERE / "out_A_1p2s" / "history.csv"),
                                "axle1_left_normal_n"))["first"]
    simpack_static = ch["front_left_contact_z"]["first"]
    print("=== static contact force (single wheel) ===")
    print(f"  Velch   {fmt(velch_static)} N   (48 654 kg / 8 = {48654*9.81/8:.1f} N)")
    print(f"  Simpack {fmt(simpack_static)} (unit not exposed; N assumed)")
    print(f"  difference {fmt(velch_static - simpack_static)} N  "
          f"({(velch_static - simpack_static)/simpack_static*100:+.2f} %)")
    print(f"  implied Simpack mass {simpack_static*8/9.81:.1f} kg vs Velch 48 654 kg "
          f"({simpack_static*8/9.81-48654:+.1f} kg)")
    print()

    # --- duplicate-station crossings -----------------------------------
    rows_b = load_history(HERE / "out_B_1p2s" / "history.csv")
    print("=== front wheelset crossing the ten duplicate stations (case B vs Simpack) ===")
    print("  station    idx        Velch R before/after   Sim R before/after    dR%      "
          "Velch L before/after   Sim L before/after    dL%")
    for cross in base["front_wheelset_x_crossings_of_duplicate_stations"]:
        i0, i1 = cross["sample_before"], cross["sample_after"]
        van_r = (float(rows_b[i0]["axle1_right_normal_n"]), float(rows_b[i1]["axle1_right_normal_n"]))
        van_l = (float(rows_b[i0]["axle1_left_normal_n"]), float(rows_b[i1]["axle1_left_normal_n"]))
        smp = cross["contact_z_at_bracketing_samples"]
        smp_r = smp["front_right_contact_z"]
        smp_l = smp["front_left_contact_z"]
        dr = ((van_r[0] - smp_r[0]) / smp_r[0] * 100, (van_r[1] - smp_r[1]) / smp_r[1] * 100)
        dl = ((van_l[0] - smp_l[0]) / smp_l[0] * 100, (van_l[1] - smp_l[1]) / smp_l[1] * 100)
        print(f"  {cross['station_model_length_unit']:8.4f}  {i0:4d}/{i1:<4d} "
              f"{van_r[0]:9.0f}/{van_r[1]:9.0f}  {smp_r[0]:9.0f}/{smp_r[1]:9.0f}  "
              f"{dr[0]:+6.1f}/{dr[1]:+6.1f}   "
              f"{van_l[0]:9.0f}/{van_l[1]:9.0f}  {smp_l[0]:9.0f}/{smp_l[1]:9.0f}  "
              f"{dl[0]:+6.1f}/{dl[1]:+6.1f}")
    print()
    print("  Simpack reference ranges")
    for key in ("front_left_contact_z", "front_right_contact_z"):
        c = ch[key]
        print(f"    {key:22s} min {fmt(c['min'])} max {fmt(c['max'])} first {fmt(c['first'])} last {fmt(c['last'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
