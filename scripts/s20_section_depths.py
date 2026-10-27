"""Round 64: recompute the measured section depths with the windowed operator.

Round 60 published a median of 9.6-12.6 um using one operator at one speed.  Round 63 showed the 80 km/h
gain it used (2.087e4) was 23 % low because the projection averaged dead record in, that the windowed
gain is 2.721e4, and that it depends only on speed.  So the same measured amplitudes are divided by a
different number here, per section and at that section's own mean speed, and the difference is stated.

The probe design travels with every depth, so a number can never be quoted without how it was measured.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

REPO = Path(r"F:\ai道岔状态反演辨识\Velch")
S17_VERDICT = Path(r"F:\velch_tmp\verdict\order_tracking.json")
DESIGN_TABLE = Path(r"F:\velch_tmp\operator_design\verdict.json")
DATA = Path(r"F:\ai道岔状态反演辨识\75kmh数据")
OUTPUT = Path(r"F:\velch_tmp\order_tracking\section_depths.json")
DESIGN = "A_240"
ROUND60_MEDIAN_UM = 9.6


def gain_table() -> dict[float, float]:
    payload = json.loads(DESIGN_TABLE.read_text(encoding="utf-8"))
    rows = {}
    for row in payload["rows"]:
        if row.get("design_id") == DESIGN:
            rows[float(row["speed_kmh"])] = float(row["gain_per_m"])
    if len(rows) < 2:
        raise SystemExit(f"{DESIGN_TABLE} holds no {DESIGN} rows; run scripts/s19_operator_design.py")
    return dict(sorted(rows.items()))


def gain_at(table: dict[float, float], speed_kmh: float) -> tuple[float, str]:
    speeds = list(table)
    if speeds[0] <= speed_kmh <= speeds[-1]:
        return float(np.interp(speed_kmh, speeds, [table[s] for s in speeds])), "interpolated"
    nearest = speeds[0] if abs(speed_kmh - speeds[0]) < abs(speed_kmh - speeds[-1]) else speeds[-1]
    return float(table[nearest]), "extrapolated"


def section_speeds() -> dict[str, float]:
    """Mean speed inside each pre-registered section, straight off the record's own speed channel."""
    import s10_measured_corrugation as detector
    import s13_admission as gate

    files = sorted(DATA.glob("*.mat"))
    if not files:
        raise SystemExit(f"no .mat under {DATA}")
    data = gate.load(files[0])
    position_m = gate._flat(data["Vi_pks"]) * 1000.0
    speed_kmh = gate._flat(data["Vi_Speed"])
    if speed_kmh.size != position_m.size:
        raise SystemExit(f"speed has {speed_kmh.size} samples against {position_m.size} positions")
    means = {}
    for name, start_m, stop_m in detector.SECTIONS:
        # SECTIONS is ((name, start_m, stop_m), ...) in metres -- not dicts, and not kilometres.
        name = str(name)
        mask = (position_m >= start_m) & (position_m <= stop_m)
        means[str(name)] = float(np.mean(speed_kmh[mask])) if np.any(mask) else float("nan")
    return means


def main() -> int:
    table = gain_table()
    print("windowed operator (m/s^2 per m):")
    for speed, gain in table.items():
        print(f"  {speed:5.1f} km/h  {gain:.4e}")

    previous = json.loads(S17_VERDICT.read_text(encoding="utf-8"))
    rows = previous.get("section_depths_um") or []
    if not rows:
        raise SystemExit(f"{S17_VERDICT} has no section rows; run scripts/s17_order_tracking.py first")
    speeds = section_speeds()

    rebuilt = []
    for row in rows:
        name = str(row["section"])
        speed = speeds.get(name, float("nan"))
        gain, source = gain_at(table, speed) if np.isfinite(speed) else (float("nan"), "no-speed")
        amplitude = float(row["amplitude_m_per_s2"])
        rebuilt.append({
            "section": name,
            "column": int(row["column"]),
            "amplitude_m_per_s2": amplitude,
            "mean_speed_kmh": speed,
            "gain_per_m": gain,
            "gain_source": source,
            "depth_um": amplitude / gain * 1e6 if gain else float("nan"),
            "depth_um_at_single_gain": float(row["depth_um"]),
            "design": {"design_id": DESIGN, "wavelength_m": 0.0275,
                       "crossing_window": True, "periods": 240.0},
        })

    by_section: dict[str, list[float]] = {}
    for row in rebuilt:
        by_section.setdefault(row["section"], []).append(row["depth_um"])
    print("\nper section (mean of both axle-box columns):")
    print("| section | speed km/h | amplitude m/s^2 | gain (m/s^2)/m | depth um | single-gain um |")
    print("|---|---|---|---|---|---|")
    section_means = {}
    for name in sorted(by_section):
        depths = [value for value in by_section[name] if np.isfinite(value)]
        singles = [row["depth_um_at_single_gain"] for row in rebuilt if row["section"] == name]
        mean = float(np.mean(depths)) if depths else float("nan")
        section_means[name] = mean
        speed = speeds.get(name, float("nan"))
        gain, _ = gain_at(table, speed) if np.isfinite(speed) else (float("nan"), "")
        amplitude = float(np.mean([row["amplitude_m_per_s2"] for row in rebuilt
                                   if row["section"] == name]))
        print(f"| {name} | {speed:5.1f} | {amplitude:.4f} | {gain:.4e} | **{mean:5.1f}** | "
              f"{np.mean(singles):5.1f} |")

    depths = [value for value in section_means.values() if np.isfinite(value)]
    median = float(np.median(depths))
    verdict = {
        "design": {"design_id": DESIGN, "wavelength_m": 0.0275,
                   "crossing_window": True, "periods": 240.0},
        "rows": rebuilt,
        "section_mean_depth_um": section_means,
        "median_depth_um": median,
        "min_depth_um": float(min(depths)),
        "max_depth_um": float(max(depths)),
        "round60_median_um": ROUND60_MEDIAN_UM,
        "round60_bias_percent": (median / ROUND60_MEDIAN_UM - 1.0) * 100.0,
        "in_corrugation_range": all(5.0 <= value <= 400.0 for value in depths),
        "speeds_covered_kmh": [float(min(table)), float(max(table))],
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(verdict, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"\nmedian {median:.1f} um ({min(depths):.1f}-{max(depths):.1f}); round 60 said "
          f"{ROUND60_MEDIAN_UM:.1f} um -> {verdict['round60_bias_percent']:+.0f} %")
    print("VERDICT:", "IN_RANGE" if verdict["in_corrugation_range"] else "OUT_OF_RANGE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
