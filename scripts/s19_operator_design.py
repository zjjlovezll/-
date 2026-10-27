"""Round 63: does a fixed probe design make the operator design-independent?

Round 62 left two effects tangled: the gain falls 32 % from 40 to 80 km/h, and the *same* speed read
2.755e4 through one probe design against 2.115e4 through another (-23 %).  The second is a measurement
artefact if the difference is only how much dead record surrounds the patch -- the projection then averages
zeros into the answer.  This measures both with the projection restricted to the crossing interval:

* design A: 240 periods, leading axle entering at the patch's leading edge;
* design B: 790 periods, leading axle entering at the edge too (so only the length differs).

If A and B now agree, the 23 % was bookkeeping and the remaining spread is the speed effect.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

import s16_operator as operator

WORK = Path(r"F:\velch_tmp\operator_design")
DESIGNS = {"A_240": 240.0, "B_790": 790.0}
SPEEDS_KMH = (40.0, 50.0, 60.0, 70.8, 80.0)
WAVELENGTH_M = 0.0275
PATCH_START_M = 40.0          # 30 m rail origin + 10 m leading-axle offset
FRONT_AXLE_M = 10.0


def measure(design: str, periods: float, speed_kmh: float) -> dict:
    patch_length = periods * WAVELENGTH_M
    duration = (patch_length + 1.5) / (speed_kmh / 3.6)
    return operator.model_gain(
        WORK / f"{design}_v{speed_kmh:05.1f}", duration_s=round(duration, 3),
        speed_kmh=speed_kmh, patch_start_m=PATCH_START_M, periods=periods,
        crossing_window=True,
    )


def main() -> int:
    WORK.mkdir(parents=True, exist_ok=True)
    rows = []
    cache = WORK / "designs.json"
    if cache.exists():
        rows = json.loads(cache.read_text(encoding="utf-8"))["rows"]
    done = {(row["design_id"], float(row["speed_kmh"])) for row in rows}

    for design, periods in DESIGNS.items():
        for speed in SPEEDS_KMH:
            if (design, speed) in done:
                print(f"  {design} {speed:5.1f} km/h: cached")
                continue
            measurement = measure(design, periods, speed)
            row = {"design_id": design, "periods": periods, **measurement}
            rows.append(row)
            cache.write_text(json.dumps({"rows": rows}, indent=1), encoding="utf-8")
            print(f"  {design} {speed:5.1f} km/h: gain {measurement['gain_per_m']:.4e} "
                  f"({measurement['amplitude_m_per_s2']:.4f} m/s^2, {measurement['status']})")

    by_design: dict[str, dict[float, float]] = {}
    for row in rows:
        by_design.setdefault(row["design_id"], {})[float(row["speed_kmh"])] = float(row["gain_per_m"])

    print("\ndesign comparison at each speed:")
    worst = 0.0
    for speed in SPEEDS_KMH:
        pair = {design: by_design.get(design, {}).get(speed) for design in DESIGNS}
        if None in pair.values():
            continue
        ratio = pair["A_240"] / pair["B_790"] - 1.0
        worst = max(worst, abs(ratio))
        print(f"  {speed:5.1f} km/h: A {pair['A_240']:.4e}  B {pair['B_790']:.4e}  "
              f"A/B-1 = {ratio:+.1%}")

    for design, table in by_design.items():
        speeds = sorted(table)
        if len(speeds) > 1:
            span = table[speeds[0]] / table[speeds[-1]] - 1.0
            print(f"  {design}: gain falls {span:+.1%} from {speeds[0]:.0f} to {speeds[-1]:.0f} km/h")

    verdict = {
        "designs": {design: periods for design, periods in DESIGNS.items()},
        "rows": rows,
        "worst_design_difference": worst,
        "design_independent": bool(worst < 0.10),
    }
    (WORK / "verdict.json").write_text(json.dumps(verdict, indent=1), encoding="utf-8")
    print(f"\nworst design difference {worst:+.1%} -> "
          f"{'design-independent within 10 %' if verdict['design_independent'] else 'still design-dependent'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
