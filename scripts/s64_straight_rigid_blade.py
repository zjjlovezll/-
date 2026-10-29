"""Put the straight blade (直尖轨 `zjg`) on a RIGID straight track and measure where it takes load.

Why a separate builder.  The flexible diverging case carries the *curved* blade (`qjg`) and the carrier
is `local_compliant`; the through route needs the straight blade family (`zjg`, 73 sections, head width
3 mm at the tip) and no track states at all.  Both the geometry and the lowering are already in the
design data -- the blade lowering by mileage is
``50.000 -> 23.00, 50.578 -> 14.00, 52.889 -> 3.00, 55.280 -> 1.38, 56.569 -> 0.50, 57.304 -> 0.00``
from the Simpack ``Pos_Z`` table, and the section that sits at each mileage comes from
``07(009)-Mileage-zjg_zgyg_250722.txt``.

One datum trap, measured before writing anything: the ``WRProfile`` ``.txt`` sections are **23 mm
datum** (every family's own ``z`` runs up to +23.000 mm: `zjg-3` spans 14.935..23.000, `cxg-12.5`
spans 13.696..23.000), while the case's ``.prr`` sections are **crown-relative** (max ~0).  A station
built from a ``.txt`` section therefore needs ``z_offset = -0.023 m - lowering``; miss the 23 mm and
the blade would stand 23 mm proud of the stock rail and every result after that would be nonsense.

Pre-registered criterion, written before the first run: with the design lowering (scale 1.0) the blade
must first take load where the lowering falls below the 65.47 um static penetration, i.e. at the
mileage where ``lowering = 0.065 mm`` -- 57.24 m by this table -- inside +-0.20 m.  The output step is
5e-4 s = 11.1 mm at 80 km/h, so one sample is worth about 6.5 % of the lowering; that is the number
that decides whether the amplitude is invertible on a rigid track.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve()
ROOT = HERE.parents[1]
LOWERING_JSON = ROOT / "reports" / "turnout_lowering_2026-10-29" / "lowering.json"
PROFILE_ROOT = Path(
    "G:/研究生/SDITT-RW-FT-250728/SDITT-RW-FT-250728/WRProfile-07(009)-1_18"
)
BLADE_MILEAGE = PROFILE_ROOT / "07(009)-Mileage" / "07(009)-Mileage-zjg_zgyg_250722.txt"
STOCK_FILE = "jbg-20200418-R.prr"
TIP_M = 50.578
FULL_SECTION_M = 57.304
STATIC_PENETRATION_MM = 0.06547
GAUGE_M = 1.50649
STOCK_CROWN_MM = 0.072
DEFAULT_CASE = ROOT.parent / "scratch" / "s30" / "case_diverging_gauge.json"


def blade_schedule() -> list[tuple[float, float]]:
    data = json.loads(LOWERING_JSON.read_text(encoding="utf-8"))
    for entry in data["schedules"]["07(009)"]:
        if entry["feature"] == "blade":
            return [
                (float(m), float(v))
                for m, v in zip(entry["mileage_m"], entry["lowering_mm"], strict=True)
            ]
    raise SystemExit("no 'blade' schedule for 07(009) in the lowering table")


def lowering_mm(s_m: float, schedule: list[tuple[float, float]]) -> float:
    miles = np.array([m for m, _ in schedule], dtype=float)
    values = np.array([v for _, v in schedule], dtype=float)
    return float(np.interp(s_m, miles, values, left=values[0], right=0.0))


def onset_mileage_mm(schedule: list[tuple[float, float]], penetration_mm: float) -> float:
    """Mileage where the design lowering drops below a given penetration (monotone tail only)."""
    miles = np.array([m for m, _ in schedule], dtype=float)
    values = np.array([v for _, v in schedule], dtype=float)
    order = np.argsort(miles)
    return float(np.interp(-penetration_mm, -values[order], miles[order]))


def blade_stations(schedule: list[tuple[float, float]], *, scale: float, y_offset_m: float,
                   datum_mm: float) -> list[dict]:
    rows = [
        line.split()
        for line in BLADE_MILEAGE.read_text(encoding="utf-8", errors="replace").splitlines()
        if line.strip()
    ]
    stations: list[dict] = []
    for parts in rows:
        if len(parts) < 2 or "zjg" not in parts[1]:
            continue
        s_m = float(parts[0])
        if not (TIP_M - 1e-9 <= s_m <= FULL_SECTION_M + 1e-9):
            continue
        source = PROFILE_ROOT / "07(009)-zjg-20200418" / parts[1].replace(".prr", ".txt")
        if not source.exists():
            raise SystemExit(f"missing blade section {source}")
        stations.append(
            {
                "s_m": s_m,
                "id": f"blade{len(stations):04d}",
                "profile": {
                    "file": str(source),
                    "format": "txt",
                    "units": "m",
                    "y_sign": 1,
                    "z_sign": 1,
                    "y_offset_m": y_offset_m,
                    "z_offset_m": (datum_mm - 23.0 - scale * lowering_mm(s_m, schedule)) / 1000.0,
                },
            }
        )
    return stations


def build(case_path: Path, *, scale: float = 1.0, speed_kmh: float = 80.0,
          seat_at_m: float = 45.0, x_start_m: float = 45.0, duration_s: float = 0.60,
          output_step_s: float = 5e-4) -> tuple[dict, dict]:
    raw = json.loads(case_path.read_text(encoding="utf-8"))
    schedule = blade_schedule()
    template = next(block for block in raw["rail_templates"] if block.get("id") == "right")
    base = next(st for st in template["stations"] if abs(float(st["s_m"]) - 30.0) < 1e-9)
    # Use the base case's own right-hand offset (0.72656 m at 30 m), NOT ``left + gauge``.  The two
    # profile families put their crowns about 6.8 mm outboard of their own midpoints, so the offset
    # difference is 1.47956 m while the crown-to-crown gauge is 1.50649 m (B041, round 216).  Setting
    # the offset difference to the gauge put the wheels on the gauge corner and the seat refused with
    # "8 of 8 wheels carry load, lightest 21 531.3 N, heaviest 97 829.0 N".
    y_offset_m = float(base["profile"]["y_offset_m"])
    # The straight side needs no second profile library: the diverging case's right rail comes from the
    # SDITT family because the route curves away, and pairing it with the left family's plain rail leaves
    # the wheels ~16 mm inboard of the crowns (seat accepted at 1.5090 m, then the run drifted onto the
    # stock's gauge corner at x=53.7358969 m).  Mirroring the LEFT family is what the frozen straight
    # case does, so do that: same file, ``y_sign`` -1, offset simply negated.
    left_block = next(block for block in raw["rail_templates"] if block["id"] == "left")
    left_profile = dict(left_block["stations"][0]["profile"])
    y_offset_m = -float(left_profile["y_offset_m"])
    mirrored = {key: left_profile[key] for key in left_profile}
    mirrored["y_offset_m"] = y_offset_m

    stock: list[dict] = []
    for station in template["stations"]:
        s_m = float(station["s_m"])
        if not (30.0 - 1e-9 <= s_m <= 116.5):
            continue
        stock.append(
            {
                "s_m": s_m,
                "id": f"stock{len(stock):05d}",
                "profile": dict(base["profile"], y_offset_m=y_offset_m),
            }
        )

    # 0.072 mm is the stock rail's own crown (`jbg-20200418-R` max z); carrying it as the blade
    # datum is what makes the stock-to-blade gap equal the design lowering with zero residual.
    blade = blade_stations(schedule, scale=scale, y_offset_m=y_offset_m, datum_mm=STOCK_CROWN_MM)
    template.pop("stations", None)
    template["bodies"] = [
        {"id": "right:stock", "stations": stock},
        {
            "id": "right:blade",
            "stations": blade,
            "s_lo_m": float(blade[0]["s_m"]),
            "s_hi_m": float(blade[-1]["s_m"]),
        },
    ]
    # The left rail is the through route on the straight side and needs nothing: it already carries
    # 19 001 plain-rail stations.  Rebuilding it from the right-hand list (an earlier attempt)
    # mirrors the right profile and leaves the vehicle standing on one side -- measured as
    # "4 of 8 wheels carry load, heaviest 119 443.3 N".
    raw["track_dynamics"] = {"kind": "rigid"}
    raw["case_id"] = f"{raw.get('case_id', 'case')}_rigid_straight_blade_k{scale:.2f}"
    # `purpose` is a closed vocabulary in `VehicleCase`; the description goes in `purpose_detail`.
    raw["purpose_detail"] = (
        f"blade family zjg, lowering scale {scale:.2f}, stock {STOCK_FILE}; "
        f"seat at {seat_at_m} m, run {x_start_m} -> {x_start_m + speed_kmh / 3.6 * duration_s:.1f} m"
    )
    run = raw["run"]
    run.update(
        {
            "method": "DOP853",
            "x_start_m": x_start_m,
            "duration_s": duration_s,
            "output_step_s": output_step_s,
            "max_solver_step_s": 1e-4,
            "rtol": 1e-6,
            "atol": 1e-8,
        }
    )
    run["seat_x_start_m"] = seat_at_m
    raw["vehicle"]["travel_speed_m_s"] = speed_kmh / 3.6
    raw.pop("initial_state", None)
    detail = {
        "blade_zone_m": [float(blade[0]["s_m"]), float(blade[-1]["s_m"])],
        "blade_stations": len(blade),
        "stock_stations": len(stock),
        "y_offset_m": y_offset_m,
        "scale": scale,
        "design_onset_m": onset_mileage_mm(schedule, STATIC_PENETRATION_MM),
    }
    return raw, detail


def verify(path: Path, detail: dict) -> list[dict]:
    from velch.vehicle import load_vehicle_case

    case = load_vehicle_case(path)
    rail = next(r for r in case.rails if r.template_id == "right")
    stock = next(b for b in rail.bodies if b.id.endswith(":stock"))
    blade = next(b for b in rail.bodies if b.id.endswith(":blade"))
    schedule = blade_schedule()
    rows = []
    for s_m in (52.0, 53.5, 55.0, 56.0, 56.5, 57.0):
        z_stock = float(np.max(stock.series.sample(s_m, 1.0).profile.z_m)) * 1e3
        z_blade = float(np.max(blade.series.sample(s_m, 1.0).profile.z_m)) * 1e3
        design = detail["scale"] * lowering_mm(s_m, schedule)
        rows.append(
            {
                "s_m": s_m,
                "stock_crown_mm": z_stock,
                "blade_crown_mm": z_blade,
                "gap_mm": z_stock - z_blade,
                "design_lowering_mm": design,
                "residual_mm": (z_stock - z_blade) - design,
            }
        )
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", type=Path, default=DEFAULT_CASE)
    parser.add_argument("--lowering-scale", type=float, default=1.0)
    parser.add_argument("--speed-kmh", type=float, default=80.0)
    parser.add_argument("--seat-at", type=float, default=45.0)
    parser.add_argument("--x-start", type=float, default=45.0)
    parser.add_argument("--duration", type=float, default=0.60)
    parser.add_argument("--output-step", type=float, default=5e-4)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()

    raw, detail = build(
        args.case,
        scale=args.lowering_scale,
        speed_kmh=args.speed_kmh,
        seat_at_m=args.seat_at,
        x_start_m=args.x_start,
        duration_s=args.duration,
        output_step_s=args.output_step,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(raw), encoding="utf-8")
    print(f"case {args.out}")
    print(f"  blade zone {detail['blade_zone_m'][0]:.3f} .. {detail['blade_zone_m'][1]:.3f} m  "
          f"blade stations {detail['blade_stations']}  stock stations {detail['stock_stations']}  "
          f"y_offset {detail['y_offset_m']:.6f} m")
    print(f"  design onset (lowering = {STATIC_PENETRATION_MM:.5f} mm) at "
          f"{detail['design_onset_m']:.3f} m")
    rows = verify(args.out, detail)
    print("\n  s_m    stock crown   blade crown   gap      design    residual")
    worst = 0.0
    for row in rows:
        worst = max(worst, abs(row["residual_mm"]))
        print(f"  {row['s_m']:6.2f}  {row['stock_crown_mm']:+9.3f}  {row['blade_crown_mm']:+9.3f}  "
              f"{row['gap_mm']:+8.3f}  {row['design_lowering_mm']:8.3f}  {row['residual_mm']:+8.3f}")
    print(f"\n  worst |residual| {worst:.3f} mm  "
          f"{'OK' if worst < 0.10 else 'CHECK THE DATUM'}")
    if args.verify_only:
        return 0 if worst < 0.10 else 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
