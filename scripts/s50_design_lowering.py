"""Extract the turnout lowering-value design tables (P1 truth).

The lowering value (降低值) is the vertical distance by which the switch blade and the
long frog sit *below* the stock rail.  Round 207 looked for it in the section files and
did not find it there; this script records where it actually lives: the rail-beam
initial-geometry table in the SDITT MATLAB, `Cal_RailBeam_230518.m`.

Two independent statements of the same design are encoded here:

* the blade table (`InpPar.RailBeam.Pos_Z.R2_zjg`), active code, one per turnout;
* the long-frog table (`InpPar.RailBeam.Pos_Z.R3`), present but commented out for
  07(009) and empty for CN18, whose frog lowering is documented instead as three
  (section, theoretical, as-built) triples in `Bezier_InterpProfile_CN18_250813.m`.

All distances in the MATLAB are "distance from the FSR" and get `+50 m` inside the file,
so the absolute mileage below already includes that offset.

Run:  python -X utf8 scripts/s50_design_lowering.py
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Schedule:
    """A piecewise-linear lowering schedule: absolute mileage (m) and lowering (mm)."""

    turnout: str
    feature: str
    mileage_m: tuple[float, ...]
    lowering_mm: tuple[float, ...]
    source: str

    def at(self, mileage_m: float) -> float:
        """Lowering in mm at a mileage, clamped outside the table."""
        if not self.mileage_m:
            raise ValueError("empty schedule")
        if mileage_m <= self.mileage_m[0]:
            return self.lowering_mm[0]
        if mileage_m >= self.mileage_m[-1]:
            return self.lowering_mm[-1]
        return float(
            _interp(self.mileage_m, self.lowering_mm, mileage_m)
        )

    def first_mileage_below(self, threshold_mm: float) -> float | None:
        """First mileage at which the lowering drops to `threshold_mm` or below.

        This is the load-transfer point: until the lowering falls under the static
        contact penetration (65.47 um on the frozen case) the blade carries nothing.
        """
        for mileage, value in zip(self.mileage_m, self.lowering_mm):
            if value <= threshold_mm:
                return float(mileage)
        return None

    def is_monotone_non_increasing(self) -> bool:
        return all(
            b <= a + 1.0e-12 for a, b in zip(self.lowering_mm, self.lowering_mm[1:])
        )

    def as_dict(self) -> dict[str, object]:
        return {
            "turnout": self.turnout,
            "feature": self.feature,
            "mileage_m": list(self.mileage_m),
            "lowering_mm": list(self.lowering_mm),
            "source": self.source,
        }


def _interp(xs: tuple[float, ...], ys: tuple[float, ...], x: float) -> float:
    for i in range(len(xs) - 1):
        if xs[i] <= x <= xs[i + 1]:
            span = xs[i + 1] - xs[i]
            if span <= 0.0:
                return ys[i + 1]
            return ys[i] + (ys[i + 1] - ys[i]) * (x - xs[i]) / span
    return ys[-1]


FSR_OFFSET_M = 50.0
"""`Mileage_HeightRed_v0(:,1) = Mileage_HeightRed_v0(:,1)+50` in Cal_RailBeam_230518.m."""

# ---------------------------------------------------------------------------
# Blade (尖轨).  `Cal_RailBeam_230518.m`, InpPar.RailBeam.Pos_Z.R2_zjg, active code.
# ---------------------------------------------------------------------------
BLADE_DISTANCE_07 = (0.000, 0.578, 2.889, 5.280, 6.569, 7.304, 10.962)
BLADE_LOWERING_07 = (23.000, 14.000, 3.000, 1.375, 0.500, 0.000, 0.000)

# CN18 comment block: "Width, Height reduction value, Distance from the FSR"
#   2    16.0  0.485
#   22   4.4   3.307
#   28   2.8   4.11
#   37.8 0.1   5.881
#   38   0     5.913
BLADE_DISTANCE_CN18 = (0.485, 3.307, 4.110, 5.881, 5.913)
BLADE_LOWERING_CN18 = (16.000, 4.400, 2.800, 0.100, 0.000)

# As-built deviation, `Choose_zjgUnEven == 1` (尖轨降低值超差), mm on top of theoretical.
BLADE_AS_BUILT_DISTANCE = (0.000, 0.578, 2.889, 7.304, 10.962)
BLADE_AS_BUILT_DELTA = (0.900, -0.400, 1.900, 1.700, 0.000)

# ---------------------------------------------------------------------------
# Long frog (长心轨).  `Cal_RailBeam_230518.m`, InpPar.RailBeam.Pos_Z.R3 (commented out).
# ---------------------------------------------------------------------------
FROG_DISTANCE_07 = (
    53.200, 53.280, 53.360, 53.431, 53.589, 53.819, 54.123, 54.425,
)
FROG_LOWERING_07 = (16.000, 13.500, 11.060, 8.870, 4.000, 2.900, 1.400, 0.000)

# CN18 frog: three (section, theoretical, as-built) triples, Bezier_InterpProfile_CN18_250813.m
#   43-'CN18-cx-44.txt', 降低值（理论/实际）= 2.0/3.8 mm
#   54-'CN18-cx-55.txt', 降低值（理论/实际）= 0.4/2.7 mm
#   70-'CN18-cx-71.txt', 降低值（理论/实际）= 0.1/1.5 mm
# Mileages from CN18-Mileage-cx.txt; the lowering range 103.25..104.75 m is quoted in
# TIrr_WideFreq_v3.m:121 ("长心轨降低值范围内 103.25 (cxg_12.5) ~ 104.75 (cxg_61)").
FROG_CN18_SECTIONS = (("CN18-cx-44.txt", 104.379), ("CN18-cx-55.txt", 104.695), ("CN18-cx-71.txt", 105.153))
FROG_CN18_THEORETICAL_MM = (2.0, 0.4, 0.1)
FROG_CN18_AS_BUILT_MM = (3.8, 2.7, 1.5)
FROG_CN18_RANGE_M = (103.25, 104.75)

STATIC_PENETRATION_MM = 0.06547
"""Frozen static penetration (65.47 um): a lowering above this carries no load at all."""


def blade(turnout: str, *, as_built: bool = False) -> Schedule:
    if turnout == "07(009)":
        distance, lowering = BLADE_DISTANCE_07, BLADE_LOWERING_07
    elif turnout == "CN18":
        distance, lowering = BLADE_DISTANCE_CN18, BLADE_LOWERING_CN18
    else:
        raise ValueError(f"unknown turnout {turnout!r}; expected '07(009)' or 'CN18'")
    values = list(lowering)
    if as_built:
        values = [
            value + _interp(BLADE_AS_BUILT_DISTANCE, BLADE_AS_BUILT_DELTA, d)
            for value, d in zip(values, distance)
        ]
    return Schedule(
        turnout=turnout,
        feature="blade" + ("-as-built" if as_built else ""),
        mileage_m=tuple(FSR_OFFSET_M + d for d in distance),
        lowering_mm=tuple(values),
        source="Cal_RailBeam_230518.m InpPar.RailBeam.Pos_Z.R2_zjg"
        + (" + Choose_zjgUnEven" if as_built else ""),
    )


def frog(turnout: str, *, as_built: bool = False) -> Schedule:
    if turnout == "07(009)":
        return Schedule(
            turnout=turnout,
            feature="frog" + ("-as-built" if as_built else ""),
            mileage_m=tuple(FSR_OFFSET_M + d for d in FROG_DISTANCE_07),
            lowering_mm=FROG_LOWERING_07,
            source="Cal_RailBeam_230518.m InpPar.RailBeam.Pos_Z.R3 (commented out)",
        )
    if turnout == "CN18":
        return Schedule(
            turnout=turnout,
            feature="frog" + ("-as-built" if as_built else ""),
            mileage_m=tuple(m for _, m in FROG_CN18_SECTIONS),
            lowering_mm=FROG_CN18_AS_BUILT_MM if as_built else FROG_CN18_THEORETICAL_MM,
            source="Bezier_InterpProfile_CN18_250813.m:63-65 + CN18-Mileage-cx.txt",
        )
    raise ValueError(f"unknown turnout {turnout!r}; expected '07(009)' or 'CN18'")


def main() -> int:
    schedules = {
        "07(009)": [blade("07(009)"), blade("07(009)", as_built=True), frog("07(009)")],
        "CN18": [blade("CN18"), blade("CN18", as_built=True), frog("CN18"), frog("CN18", as_built=True)],
    }
    payload: dict[str, object] = {
        "fsr_offset_m": FSR_OFFSET_M,
        "static_penetration_mm": STATIC_PENETRATION_MM,
        "frog_cn18_lowering_range_m": list(FROG_CN18_RANGE_M),
        "schedules": {k: [s.as_dict() for s in v] for k, v in schedules.items()},
    }
    for turnout, items in schedules.items():
        for schedule in items:
            print(f"\n=== {turnout}  {schedule.feature}   ({schedule.source})")
            for mileage, value in zip(schedule.mileage_m, schedule.lowering_mm):
                print(f"   {mileage:9.3f} m  {value:8.3f} mm")
            transfer = schedule.first_mileage_below(STATIC_PENETRATION_MM)
            print(
                f"   monotone non-increasing: {schedule.is_monotone_non_increasing()}   "
                f"load transfer (lowering <= {STATIC_PENETRATION_MM * 1e3:.1f} um): "
                f"{'n/a' if transfer is None else f'{transfer:.3f} m'}"
            )
            if not schedule.is_monotone_non_increasing():
                raise SystemExit(f"{schedule.feature} lowering is not monotone")
    out = Path(__file__).resolve().parents[1] / "reports" / "turnout_lowering_2026-10-29"
    out.mkdir(parents=True, exist_ok=True)
    (out / "lowering.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    print(f"\nwritten: {out / 'lowering.json'}")

    cn18 = blade("CN18")
    span_m = cn18.mileage_m[-1] - cn18.mileage_m[0]
    for speed_kmh in (80.0, 160.0, 350.0):
        speed = speed_kmh / 3.6
        print(
            f"CN18 blade lowering ramp {span_m:.3f} m at {speed_kmh:5.1f} km/h -> "
            f"{speed / span_m:6.3f} Hz over {span_m / speed:5.3f} s"
        )
    print(
        f"design step at the tip: {cn18.lowering_mm[0]:.1f} mm = "
        f"{cn18.lowering_mm[0] / STATIC_PENETRATION_MM:.0f}x the static penetration "
        f"({STATIC_PENETRATION_MM * 1e3:.1f} um), so the blade carries nothing until the ramp ends"
    )
    assert math.isfinite(blade("CN18").at(50.7))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
