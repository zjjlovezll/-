"""Read the frog point-rail lowering (心轨降低值) back out of the case, and show a body would double it.

**Measured before building anything else**: this case's own station table already carries the frog
lowering.  Sampling the running surface against the design table over 103.200-104.600 m gives a
maximum residual of **0.205 mm** and an rms of **0.073 mm** over 45 stations (``--read-back``), so the
13.5 mm at 103.280 m and its fall to 0.0 at 104.425 m are *in the geometry*.  Round 208's conclusion
that "the lowering is not in the case" holds for the **blade** zone (50.6-60.9 m), not here.

Consequence: adding a point-rail body lowered by the design table **double counts** it, which is why
``build()`` is kept only as the tool that proves the double count (its injected crown sits 13.5 mm
below a surface that is already 13.5 mm low).  Use ``--read-back`` for the measurement.

Add the frog point rail (心轨) as a body and measure where it starts carrying load.

The switch zone is only half of a flexible turnout.  The other half is the frog: the point rail sits
``lowering`` below the running surface at its tip and rises to meet it.  The design table is already
extracted -- ``reports/turnout_lowering_2026-10-29/lowering.json``, feature ``frog``, 07(009):
16.0 mm at 103.200 m falling to 0.0 mm at 104.425 m (``Cal_RailBeam_230518.m InpPar.RailBeam.Pos_Z.R3``).

This script puts that geometry into a case:

* stations from ``07(009)-Mileage-cxg.txt`` (68 sections, 103.280-116.440 m), each pointing at its own
  drawn ``cxg`` section -- the point rail's head grows from 12.5 mm wide at the tip to full section;
* lateral placement by **interpolating the running rail's own ``y_offset_m``** at each of those
  mileages, so the point rail sits inside the same rail line the wheel rolls on instead of inventing a
  second line 0.75 m away;
* ``z_offset_m = -lowering(s) / 1000``, the same datum the blade uses (both families are drawn with the
  crown at +0.023000 m, measured in round 218).

**Pre-registered criterion**, written before the run: the point rail can only touch once its lowering is
smaller than the static penetration 65.47 um.  Between 104.123 m (1.4 mm) and 104.425 m (0.0 mm) the
slope is 1.4/0.302 = 4.636 mm/m, so the crossing is at ``104.425 - 0.06547/4.636 = 104.411 m``.  The
frog's first non-zero force must therefore appear at **104.41 +- 0.10 m**; earlier means the point rail
is being reached through the wheel's flange instead of its tread, later means it is buried too deep.

Run::

    PYTHONPATH=src python -X utf8 scripts/s63_frog_body.py --build-only
    PYTHONPATH=src python -X utf8 scripts/s63_frog_body.py --x-start 96 --duration 0.50
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parents[1]
DEFAULT_CASE = HERE.parent / "scratch" / "s60" / "case_gauge_real.json"
LOWERING_JSON = HERE / "reports" / "turnout_lowering_2026-10-29" / "lowering.json"
SECTION_ROOT = Path(
    "G:/研究生/SDITT-RW-FT-250728/SDITT-RW-FT-250728/WRProfile-07(009)-1_18"
)
MILEAGE_TABLE = SECTION_ROOT / "07(009)-Mileage" / "07(009)-Mileage-cxg.txt"
SECTION_DIR = SECTION_ROOT / "07(009)-cxg-20200422"
TURNOUT = "07(009)"
STATIC_PENETRATION_M = 65.47e-6
ONSET_M = 104.411
ONSET_TOLERANCE_M = 0.10
AXLE1_OFFSET_M = 10.0


def frog_schedule() -> tuple[list[float], list[float]]:
    """``(mileage, lowering_mm)`` for the point rail, from the design table."""
    data = json.loads(LOWERING_JSON.read_text(encoding="utf-8"))
    for entry in data["schedules"][TURNOUT]:
        if entry.get("feature") == "frog":
            miles = [float(v) for v in entry["mileage_m"]]
            lowering = [float(v) for v in entry["lowering_mm"]]
            return miles, lowering
    raise SystemExit(f"no 'frog' schedule for {TURNOUT} in the lowering table")


def resolve_section(name: str) -> Path:
    """Find a section file by name anywhere in the section library."""
    target = name.replace(".txt", ".prr")
    if Path(target).is_absolute():
        path = Path(target)
        if path.exists():
            return path
        raise SystemExit(f"section {target} does not exist")
    for candidate in sorted(SECTION_ROOT.rglob(Path(target).name)):
        if candidate.is_file():
            return candidate
    raise SystemExit(f"section {target} not found under {SECTION_ROOT}")


def frog_stations(
    stock_stations: list[dict], *, scale: float, surface: str = "stock",
    profile_template: dict | None = None,
) -> list[dict]:
    miles, lowering = frog_schedule()
    # The table ends with a sentinel row ``1000.000 jbg-...`` meaning "the stock rail carries on
    # for ever"; it is not a station (dropping it is why the first build reported a 1000 m station
    # outside the running rail's range).
    rows = [
        (float(line.split()[0]), line.split()[1])
        for line in MILEAGE_TABLE.read_text(encoding="utf-8").splitlines()
        if line.strip() and float(line.split()[0]) <= 500.0
        # Keep only the point rail's own family: the hand-back rows name a `jbg` section, which is
        # not part of this body (it ends where the point rail merges into the stock rail).
        and line.split()[1].startswith("07(009)-cxg")
    ]
    stock_s = np.array([float(st["s_m"]) for st in stock_stations], dtype=float)
    stock_y = np.array(
        [float(st["profile"].get("y_offset_m", 0.0)) for st in stock_stations], dtype=float
    )
    order = np.argsort(stock_s)
    stations: list[dict] = []
    for mileage, name in rows:
        if mileage < stock_s[order][0] or mileage > stock_s[order][-1]:
            raise SystemExit(
                f"cxg station {mileage:.3f} m is outside the running rail's own range "
                f"{stock_s[order][0]:.3f}-{stock_s[order][-1]:.3f} m"
            )
        drop_mm = scale * float(np.interp(mileage, miles, lowering, right=0.0))
        stations.append(
            {
                "s_m": mileage,
                "id": f"frog{mileage:08.3f}".replace(".", ""),
                "profile": {
                    # `surface="stock"` copies the running rail's own section and only lowers it.
                    # The drawn `cxg` slices are narrow and *shift sideways* as the point rail grows,
                    # so consecutive ones stop sharing lateral points and the longitudinal derivative
                    # raises `ProfileError: adjacent profiles have insufficient common lateral domain`
                    # (measured on the first attempt, at 116.590 m and again with the hand-back rows
                    # dropped).  The lowering is a height, so the stock surface answers the onset
                    # question; the point rail's own widening is deferred to the load-share work.
                    "file": str(resolve_section(name)) if surface == "drawn" else profile_template["file"],
                    "format": profile_template["format"],
                    "units": profile_template["units"],
                    "y_sign": profile_template["y_sign"],
                    "z_sign": profile_template["z_sign"],
                    "y_offset_m": float(np.interp(mileage, stock_s[order], stock_y[order])),
                    "z_offset_m": -drop_mm / 1000.0,
                },
            }
        )
    return stations


def build(case_path: Path, *, out: Path, side: str, scale: float, surface: str = "stock") -> dict:
    raw = json.loads(case_path.read_text(encoding="utf-8"))
    template = next(block for block in raw["rail_templates"] if block.get("id") == side)
    bodies = template.setdefault("bodies", [])
    if not bodies:
        raise SystemExit(
            f"template {side!r} has no bodies: build the two-body switch zone first "
            f"(scripts/s52_switch_two_body.py)"
        )
    stock = next(body for body in bodies if str(body.get("id", "")).endswith(":stock"))
    template_profile = dict(stock["stations"][0]["profile"])
    stations = frog_stations(
        stock["stations"], scale=scale, surface=surface, profile_template=template_profile
    )
    bodies.append(
        {
            "id": f"{side}:frog",
            "stations": stations,
            "s_lo_m": float(stations[0]["s_m"]),
            "s_hi_m": float(stations[-1]["s_m"]),
        }
    )
    raw["case_id"] = f"{raw.get('case_id', 'case')}_frog_{side}"
    raw["purpose_detail"] = (
        f"{raw.get('purpose_detail', '')} | point-rail body on the {side} side: drawn cxg sections at "
        f"their own mileages, lowered by the design frog table (16.0 mm at 103.200 m to 0.0 mm at "
        f"104.425 m), scale {scale:.3f}"
    ).strip(" |")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(raw), encoding="utf-8")
    return {
        "stations": len(stations),
        "s_lo_m": stations[0]["s_m"],
        "s_hi_m": stations[-1]["s_m"],
        "largest_drop_mm": max(-1000.0 * float(st["profile"]["z_offset_m"]) for st in stations),
    }


def run(case_path: Path, *, x_start: float, seat_at: float, duration: float, speed_kmh: float) -> int:
    from velch import vehicle_solver as solver_module
    from velch.vehicle import load_vehicle_case
    from velch.vehicle_solver import simulate_vehicle

    raw = json.loads(case_path.read_text(encoding="utf-8"))
    raw["run"] = dict(
        raw["run"],
        x_start_m=x_start,
        duration_s=duration,
        output_step_s=2.0e-3,
        seat_x_start_m=seat_at,
        method="BDF",
        jacobian="analytic",
    )
    raw["vehicle"]["travel_speed_m_s"] = speed_kmh / 3.6
    raw.pop("initial_state", None)
    target = HERE.parent / "scratch" / "s63" / "case_run.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(raw), encoding="utf-8")

    case = load_vehicle_case(target)
    speed = speed_kmh / 3.6
    print(f"case      x_start {x_start:.1f} m   seat {seat_at:.1f} m   {speed_kmh:.1f} km/h")
    print(f"criterion frog touches at {ONSET_M:.2f} m +- {ONSET_TOLERANCE_M:.2f} m")
    print()

    rows: list[tuple[float, float]] = []

    def record(t_s, rail_id, bodies) -> None:
        if not rail_id.startswith("axle1_"):
            return
        for body_id, force in bodies:
            if str(body_id).endswith(":frog"):
                rows.append((float(t_s), float(force)))

    saved = solver_module.BODY_CONTACT_HOOK
    solver_module.BODY_CONTACT_HOOK = record
    try:
        result = simulate_vehicle(case)
    finally:
        solver_module.BODY_CONTACT_HOOK = saved

    summary = result.summary or {}
    gates = summary.get("gates") or {}
    print(
        f"status    {summary.get('status')}   frames {len(result.times_s)}   "
        f"gates {sum(1 for ok in gates.values() if ok)}/{len(gates)}"
    )
    print()
    if not rows:
        print("the frog body never entered an evaluation -> nothing to read")
        return 2
    first = next(((t_s, force) for t_s, force in rows if force > 0.0), None)
    if first is None:
        last = rows[-1]
        print(
            f"frog never carried load in {last[0]:.3f} s -> the run stopped before {ONSET_M:.2f} m"
        )
        return 2
    t_onset, force = first
    axle_m = x_start + AXLE1_OFFSET_M + t_onset * speed
    error = axle_m - ONSET_M
    print(f"first frog load   t {t_onset:.3f} s   axle1 at {axle_m:.3f} m   F {force / 1.0e3:.3f} kN")
    print(f"criterion error   {error:+.3f} m   "
          f"({'PASS' if abs(error) <= ONSET_TOLERANCE_M else 'FAIL'} at +- {ONSET_TOLERANCE_M:.2f} m)")
    print()
    print("  axle1 at (m)   frog force (kN)")
    step = max(1, len(rows) // 16)
    for t_s, sample in rows[::step]:
        print(f"  {x_start + AXLE1_OFFSET_M + t_s * speed:11.2f}   {sample / 1.0e3:14.3f}")
    return 0 if abs(error) <= ONSET_TOLERANCE_M else 2


def read_back(case_path: Path, *, side: str) -> int:
    """Compare the case's own running surface with the design frog lowering, station by station."""
    from velch.vehicle import load_vehicle_case

    raw = json.loads(case_path.read_text(encoding="utf-8"))
    for block in raw["rail_templates"]:
        if block.get("id") == side:
            block["bodies"] = [b for b in (block.get("bodies") or []) if not str(b.get("id", "")).endswith(":frog")]
    stripped = HERE.parent / "scratch" / "s63" / "case_readback.json"
    stripped.parent.mkdir(parents=True, exist_ok=True)
    stripped.write_text(json.dumps(raw), encoding="utf-8")
    case = load_vehicle_case(stripped)
    rail = next(r for r in case.rails if str(r.id).endswith(side))
    stock = next(b for b in rail.bodies if str(b.id).endswith(":stock"))
    miles, lowering = frog_schedule()
    stations = [
        float(line.split()[0])
        for line in MILEAGE_TABLE.read_text(encoding="utf-8").splitlines()
        if line.strip() and float(line.split()[0]) <= 500.0 and line.split()[1].startswith("07(009)-cxg")
    ]
    window = [s for s in stations if miles[0] - 0.1 <= s <= miles[-1] + 0.2]
    residuals: list[float] = []
    for station in window:
        sample = stock.series.sample(station, 1.0)
        crown_mm = float(np.max(sample.profile.z_m)) * 1000.0
        design = float(np.interp(station, miles, lowering, right=0.0))
        residuals.append(crown_mm + design)
        print(f"  s {station:9.4f}  crown {crown_mm:+9.3f} mm   design {-design:+9.3f} mm   "
              f"residual {crown_mm + design:+7.3f}")
    print()
    worst = max(abs(value) for value in residuals)
    rms = float(np.sqrt(np.mean(np.square(residuals))))
    print(f"stations {len(residuals)}   max |residual| {worst:.3f} mm   rms {rms:.3f} mm")
    print("VERDICT: the case's own surface already carries the design frog lowering" if worst < 0.5
          else "VERDICT: the case surface does NOT follow the design frog lowering")
    return 0 if worst < 0.5 else 2


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", type=Path, default=DEFAULT_CASE)
    parser.add_argument("--out", type=Path, default=HERE.parent / "scratch" / "s63" / "case_frog.json")
    parser.add_argument("--side", default="right")
    parser.add_argument("--lowering-scale", type=float, default=1.0)
    parser.add_argument("--surface", choices=("stock", "drawn"), default="stock",
                        help="'stock' lowers a copy of the running surface (stable); 'drawn' keeps "
                             "the cxg slices, which stop sharing lateral points and fail the "
                             "longitudinal derivative")
    parser.add_argument("--build-only", action="store_true")
    parser.add_argument("--read-back", action="store_true",
                        help="compare the case's own running surface with the design frog "
                             "lowering; use this instead of building a second body")
    parser.add_argument("--x-start", type=float, default=96.0)
    parser.add_argument("--seat-at", type=float, default=45.0)
    parser.add_argument("--duration", type=float, default=0.50)
    parser.add_argument("--speed-kmh", type=float, default=80.0)
    args = parser.parse_args()

    if args.read_back:
        return read_back(args.case, side=args.side)

    info = build(
        args.case, out=args.out, side=args.side, scale=args.lowering_scale, surface=args.surface
    )
    print(f"case      written to {args.out}")
    for key, value in info.items():
        print(f"  {key:18s} {value}")
    print()
    if args.build_only:
        return 0
    return run(
        args.out,
        x_start=args.x_start,
        seat_at=args.seat_at,
        duration=args.duration,
        speed_kmh=args.speed_kmh,
    )


if __name__ == "__main__":
    raise SystemExit(main())
