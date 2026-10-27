"""S9-2 / S9-3: what changes when the wheelset is elastic, on two windows.

Two cases, each run twice — rigid wheelset and 33-mode elastic wheelset — with everything else
held fixed (same vehicle, same track, same tolerances, same fast preset):

* the frog window (0.05 s through the crossing), where the wheel-rail force is the quantity of
  interest;
* the straight window (0.4 s of plain track), where the acceleration spectrum is.

Reported per variant: the eight per-rail contact peaks, the largest penetration, the equation
solve count, the modal amplitude actually reached, and the peak frequencies of the axle-box
vertical acceleration.  The point of the comparison is not "flexible is better"; it is to see
whether these two windows excite the wheel's own elasticity at all — the thesis puts the elastic
additions at 345 and 378 Hz, and our free-free modes start at 76.8 Hz with the first travelling
pair at 88.2.

Usage:
    python -X utf8 scripts/s9_compare.py [--work F:\\velch_tmp\\s9]
"""
from __future__ import annotations

import argparse
import copy
import json
import time
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
MODES = REPO / "vehicles" / "modes" / "CRH3C_wheelset_fe.json"
FROG = Path(r"F:\velch_data\validation\crh380a_m\case_frog_N_strip05.json")
STRAIGHT = Path(r"F:\velch_tmp\straight\case_straight_axlebox.json")
FAST = {"method": "BDF", "jacobian": "analytic", "rtol": 1e-4, "max_solver_step_s": 1e-3}


def absolute(node, base: Path) -> None:
    if isinstance(node, dict):
        if isinstance(node.get("file"), str) and not Path(node["file"]).is_absolute():
            node["file"] = str((base / node["file"]).resolve())
        for value in node.values():
            absolute(value, base)
    elif isinstance(node, list):
        for value in node:
            absolute(value, base)


def build(base: Path, target: Path, flexible: bool, duration: float | None) -> Path:
    raw = json.loads(base.read_text(encoding="utf-8"))
    absolute(raw, base.parent)
    # A case that freezes its own node topology may predate the 0-based axle numbering (B026).
    for body in raw.get("topology", {}).get("bodies", []):
        if body.get("kind") == "axlebox" and isinstance(body.get("axle"), int) and body["axle"] >= 1:
            body["axle"] -= 1
    raw["case_id"] = target.stem
    raw.setdefault("run", {}).update(FAST)
    if duration is not None:
        raw["run"]["duration_s"] = duration
    if flexible:
        raw["flexible_wheelset"] = {"source": "file", "file": str(MODES), "axles": [1, 2, 3, 4]}
    else:
        raw.pop("flexible_wheelset", None)
    # A long run needs its own start mileage kept; nothing else is touched.
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    return target


def history_row(history, name: str) -> np.ndarray:
    index = history.ordering.index(name)
    return np.asarray(history.data[index], dtype=float)


def peaks(history) -> dict[str, float]:
    out = {}
    for name in history.channels:
        if name.endswith("_normal_n"):
            values = history_row(history, name)
            out[name] = float(values.max())
    return out


def penetration(history) -> float:
    worst = 0.0
    for name in history.channels:
        if name.endswith("_penetration_m"):
            worst = max(worst, float(history_row(history, name).max()))
    return worst


def spectral_peaks(history, name: str, count: int = 4) -> list[tuple[float, float]]:
    values = history_row(history, name)
    times = history_row(history, "time_s")
    if values.size < 16:
        return []
    step = float(np.mean(np.diff(times)))
    window = values - values.mean()
    spectrum = np.abs(np.fft.rfft(window * np.hanning(values.size))) / values.size
    frequencies = np.fft.rfftfreq(values.size, d=step)
    # Skip the first bin: a remaining offset is not a frequency of interest.
    order = np.argsort(spectrum[1:])[::-1][:count] + 1
    return [(float(frequencies[i]), float(spectrum[i])) for i in order]


def run_case(case: Path, out: Path):
    from velch.vehicle import load_vehicle_case
    from velch.vehicle_solver import simulate_vehicle, save_vehicle_result

    loaded = load_vehicle_case(case)
    started = time.perf_counter()
    result = simulate_vehicle(loaded)
    elapsed = time.perf_counter() - started
    out.mkdir(parents=True, exist_ok=True)
    _history, manifest_path = save_vehicle_result(loaded, result, out)
    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    return loaded, result, elapsed, manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--work", default=r"F:\velch_tmp\s9")
    args = parser.parse_args()
    work = Path(args.work)

    from velch.io.history import read_history

    for label, base, duration in (("frog", FROG, None), ("straight", STRAIGHT, 0.4)):
        rows = {}
        for variant, flexible in (("rigid", False), ("flexible", True)):
            case = build(base, work / f"case_{label}_{variant}.json", flexible, duration)
            out = work / f"out_{label}_{variant}"
            loaded, result, elapsed, manifest = run_case(case, out)
            history = read_history(out / "history.csv")
            modal = 0.0
            for name in history.channels:
                if "_mode" in name and name.endswith("_q") and "_per_s" not in name:
                    modal = max(modal, float(np.abs(history_row(history, name)).max()))
            rows[variant] = {
                "coordinates": len(loaded.initial_q),
                "status": manifest["summary"]["result_status"],
                "gates": sum(1 for value in manifest["summary"]["gates"].values() if value),
                "seconds": round(elapsed, 1),
                "penetration_um": round(penetration(history) * 1e6, 3),
                "modal_q_max_m": modal,
                "peaks": peaks(history),
                "frames": int(history.samples),
            }
            box = "axle1_box_left_z_acc_m_per_s2"
            rows[variant]["box_peaks"] = (
                spectral_peaks(history, box) if box in history.channels else [])
            rows[variant]["box_rms_g"] = (
                float(np.sqrt(np.mean(history_row(history, box) ** 2)) / 9.81)
                if box in history.channels else None)

        print(f"\n=== {label} ===")
        for variant in ("rigid", "flexible"):
            row = rows[variant]
            print(f"{variant:9s} coords {row['coordinates']:4d}  {row['status']:20s} "
                  f"gates {row['gates']}/7  {row['seconds']:6.1f}s  "
                  f"max penetration {row['penetration_um']:8.3f} um  "
                  f"max |q_modal| {row['modal_q_max_m']:.3e} m")
            top = sorted(row["peaks"].items(), key=lambda item: -item[1])[:8]
            print("          peaks kN: " + "  ".join(
                f"{name.replace('_normal_n', '')}={value / 1e3:.2f}" for name, value in top))
            if row["box_peaks"]:
                print(f"          axlebox rms {row['box_rms_g']:.3f} g, spectral peaks: "
                      + "  ".join(f"{freq:.1f}Hz({mag * 1e3:.2f})"
                                  for freq, mag in row["box_peaks"]))
        shared = set(rows["rigid"]["peaks"]) & set(rows["flexible"]["peaks"])
        worst = max((abs(rows["flexible"]["peaks"][n] - rows["rigid"]["peaks"][n])
                     / max(rows["rigid"]["peaks"][n], 1e-9), n) for n in shared)
        print(f"          worst relative change over {len(shared)} contact channels: "
              f"{worst[0] * 100:.2f} % ({worst[1]})")

    (work / "summary.json").write_text(json.dumps({"ok": True}, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

