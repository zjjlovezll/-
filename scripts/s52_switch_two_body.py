"""Put the design lowering into the turnout case as geometry: a two-body switch zone.

WHY
===
Round 211 measured that the corpus case carries no vertical offset at all: the right rail's station
table switches between stock, curved stock (``qjbg``), curved switch rail (``qjg``) and point rail
(``cxg``), but every one of those profiles is placed with its crown at the same height.  So the table
says *which* rail carries the wheel, not *how low* it sits -- and because only one rail exists at any
mileage, the 23 mm design lowering (降低值) has nowhere to live.

The lowering is a real, designed quantity: `Cal_RailBeam_230518.m` carries it as
``InpPar.RailBeam.Pos_Z.R2_zjg`` (see ``reports/turnout_lowering_2026-10-29/lowering.json``), 23 mm at
the blade tip tapering to 0 over 7.304 m.  A real turnout keeps **both** rails present through the
switch: the wheel rides the stock rail, and the blade only takes load once it has risen to full height.
The loader already supports this -- ``rail_templates[i]["bodies"]`` is a list, and each body carries its
own stations, ``s_lo_m`` / ``s_hi_m`` and ``y_window_m`` (``src/velch/vehicle.py:433``).  So this is a
case-build, not a solver change.

WHAT THIS SCRIPT DOES
=====================
For the diverging-side template only:

* **stock body** -- the original station list with the ``qjg`` entries rewritten to the plain stock
  profile (only the *file* changes; each station keeps its own lateral offset, because blade and stock
  share the same design line and differ only in height).  Sampling across the former blade zone then
  interpolates the stock surface, which is what the wheel actually runs on.
* **blade body** -- exactly the ``qjg`` stations, each given ``z_offset_m = -lowering(s)`` and bounded
  by ``s_lo_m`` / ``s_hi_m``, so it is only a candidate where the drawing says a blade exists.

DATUM (stated, not hidden)
==========================
The design table measures distance from the FSR, while the case's own blade zone is
60.95--70.92 m (9.97 m long against the design's 10.96 m).  The two axes cannot be reconciled from the
data at hand, so the lowering is anchored at the **first ``qjg`` station in this case** and shaped by
the design's distances from the tip.  A ±1 m datum shift moves *where* the transfer happens; it does not
change the 23 mm amplitude, which is the quantity P1 is asked to recover.

Recompute::

    PYTHONPATH=src python -X utf8 scripts/s52_switch_two_body.py
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parents[1]
DEFAULT_CASE = Path(r"F:/velch_data/validation/crh380a_m/case_diverging_R1100.json")
LOWERING_JSON = HERE / "reports" / "turnout_lowering_2026-10-29" / "lowering.json"
STOCK_FILE = "jbg-20200418-R.prr"
BLADE_MARK = "-qjg-"


def blade_schedule() -> list[tuple[float, float]]:
    """``[(distance from tip, lowering mm)]`` from the design table, largest turnout first."""
    data = json.loads(LOWERING_JSON.read_text(encoding="utf-8"))
    for entry in data["schedules"]["07(009)"]:
        if entry["feature"] == "blade":
            miles = [float(m) for m in entry["mileage_m"]]
            lowering = [float(v) for v in entry["lowering_mm"]]
            tip = miles[0]
            return [(m - tip, v) for m, v in zip(miles, lowering, strict=True)]
    raise SystemExit("no 'blade' schedule for 07(009) in the lowering table")


def lowering_mm(distance_from_tip_m: float, schedule) -> float:
    distances = np.array([d for d, _ in schedule], dtype=float)
    values = np.array([v for _, v in schedule], dtype=float)
    return float(np.interp(max(distance_from_tip_m, 0.0), distances, values, right=0.0))


def build(
    case_path: Path, *, side: str = "right", real_sections: bool = False,
    blade_datum_mm: float = 0.0, lowering_scale: float = 1.0,
) -> tuple[dict, dict]:
    raw = json.loads(case_path.read_text(encoding="utf-8"))
    schedule = blade_schedule()
    template = next(block for block in raw["rail_templates"] if block.get("id") == side)
    stations = template["stations"]

    blade = [st for st in stations if BLADE_MARK in Path(st["profile"]["file"]).name]
    if not blade:
        raise SystemExit(f"template {side!r} carries no blade station ({BLADE_MARK!r})")
    stock_source = next(
        st for st in stations if Path(st["profile"]["file"]).name == STOCK_FILE
    )
    tip_m = float(blade[0]["s_m"])
    end_m = float(blade[-1]["s_m"])

    stock = []
    for st in stations:
        if BLADE_MARK in Path(st["profile"]["file"]).name:
            replacement = dict(st)
            replacement["profile"] = dict(stock_source["profile"], y_offset_m=st["profile"]["y_offset_m"])
            stock.append(replacement)
        else:
            stock.append(st)

    # The blade carries the SAME surface as the stock rail, offset down by the design lowering.  Its
    # own `qjg` sections are narrow slices (`CN18-jg-0` is 4.0 mm wide at the tip), and the longitudinal
    # derivative between two such slices is undefined over most of the lateral window -- measured as
    # `ProfileError: longitudinal profile derivative is undefined at the contact point` once the blade
    # rises to full height and becomes a candidate contact body (round 215).  The lowering is a height
    # difference, so keeping the narrow section buys nothing for P1 and costs the passage.
    blade_body = []
    for st in blade:
        distance = float(st["s_m"]) - tip_m
        lowered = dict(st)
        if real_sections:
            # Keep the station's own `zjg`/`qjg` section (head width 3 mm at the tip, 72 mm at full
            # section) and only shift it down by the design lowering.  These are the drawn sections;
            # the stock-copy branch below exists because a narrow slice leaves the longitudinal
            # derivative undefined over part of the wheel's lateral window (see the comment above).
            lowered["profile"] = dict(
                st["profile"],
                z_offset_m=(blade_datum_mm - lowering_scale * lowering_mm(distance, schedule)) / 1000.0,
            )
        else:
            lowered["profile"] = dict(
                stock_source["profile"],
                y_offset_m=st["profile"]["y_offset_m"],
                z_offset_m=-lowering_scale * lowering_mm(distance, schedule) / 1000.0,
            )
        blade_body.append(lowered)

    template.pop("stations", None)
    template["bodies"] = [
        {"id": f"{side}:stock", "stations": stock},
        {
            "id": f"{side}:blade",
            "stations": blade_body,
            "s_lo_m": tip_m,
            "s_hi_m": end_m,
        },
    ]
    detail = {
        "side": side,
        "blade_zone_m": [tip_m, end_m],
        "blade_stations": len(blade_body),
        "stock_stations": len(stock),
        "schedule_mm": schedule,
    }
    return raw, detail


def verify(path: Path, detail: dict) -> list[dict]:
    """Sample both bodies where the blade lies and compare the gap to the design table."""
    from velch.vehicle import load_vehicle_case

    case = load_vehicle_case(path)
    rail = next(r for r in case.rails if r.template_id == detail["side"])
    if len(rail.bodies) != 2:
        raise SystemExit(f"expected two bodies, got {[b.id for b in rail.bodies]}")
    stock, blade = rail.bodies
    tip, end = detail["blade_zone_m"]
    rows = []
    for s in np.linspace(tip, end, 6):
        z_stock = float(np.max(np.asarray(stock.series.sample(float(s), 1.0).profile.z_m)))
        z_blade = float(np.max(np.asarray(blade.series.sample(float(s), 1.0).profile.z_m)))
        design = lowering_mm(float(s) - tip, detail["schedule_mm"])
        rows.append(
            {
                "s_m": float(s),
                "stock_crown_mm": z_stock * 1.0e3,
                "blade_crown_mm": z_blade * 1.0e3,
                "gap_mm": (z_stock - z_blade) * 1.0e3,
                "design_lowering_mm": design,
            }
        )
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", type=Path, default=DEFAULT_CASE)
    parser.add_argument("--side", default="right")
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--blade-datum-mm", type=float, default=0.0,
                        help="raise the blade sections by this much so a zero design lowering "
                             "puts the blade crown level with the stock crown")
    parser.add_argument("--lowering-scale", type=float, default=1.0,
                        help="multiply the design lowering; 1.0 is the design value, other values "
                             "exist only to test what a lowering inversion can resolve")
    parser.add_argument("--real-sections", action="store_true",
                        help="keep each blade station's own drawn section instead of copying the stock rail")
    args = parser.parse_args()

    raw, detail = build(
        args.case, side=args.side, real_sections=args.real_sections,
        blade_datum_mm=args.blade_datum_mm, lowering_scale=args.lowering_scale,
    )
    out = args.out or (HERE.parent / "scratch" / "s52" / "case_two_body_switch.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    raw["case_id"] = f"{raw.get('case_id', 'case')}_twobody_{args.side}"
    raw["purpose_detail"] = (
        f"{raw.get('purpose_detail', '')} | two-body switch zone on the {args.side} side: stock body "
        f"plus blade body lowered by the 07(009) design table (23 mm at the tip, zero at 7.304 m), "
        f"scale {args.lowering_scale:.3f}"
    ).strip(" |")
    out.write_text(json.dumps(raw), encoding="utf-8")

    rows = verify(out, detail)
    print(f"case            {out}")
    print(f"side            {detail['side']}   blade zone {detail['blade_zone_m'][0]:.2f} .. "
          f"{detail['blade_zone_m'][1]:.2f} m   stations stock {detail['stock_stations']} / "
          f"blade {detail['blade_stations']}")
    print()
    # The two profile families are digitised on their own crown datums -- the stock crown reads
    # +0.072 mm and the blade crown +0.134 mm where the design says the blade is at FULL height -- so
    # the absolute gap carries a constant datum offset of about -0.06 mm that has nothing to do with
    # the lowering.  Fit that one constant where the design says the lowering is zero and judge the
    # rest against it; anything else would confuse a digitising datum with the design profile.
    flat = [row for row in rows if row["design_lowering_mm"] <= 0.05]
    datum = float(np.mean([row["gap_mm"] - row["design_lowering_mm"] for row in flat])) if flat else 0.0
    print(f"  crown datum (measured where the design lowering is zero): {datum:+.3f} mm")
    print()
    print("  mileage   stock crown   blade crown   gap    design    residual")
    worst = 0.0
    for row in rows:
        residual = (row["gap_mm"] - datum) - row["design_lowering_mm"]
        worst = max(worst, abs(residual))
        print(f"  {row['s_m']:8.2f}  {row['stock_crown_mm']:+10.3f}  {row['blade_crown_mm']:+10.3f}"
              f"  {row['gap_mm']:7.3f}  {row['design_lowering_mm']:7.3f}  {residual:+8.3f}")
    print()
    print(f"worst |(gap - datum) - design| = {worst:.3f} mm")
    if worst > 0.05:
        print("VERDICT: the injected geometry does not follow the design table")
        return 2
    print("VERDICT: the blade sits below the stock rail by the design lowering")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
