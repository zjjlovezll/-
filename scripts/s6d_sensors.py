"""S6d: more sensors, and several random realisations of the same spectrum.

Sensors (all from one simulation each): two axle boxes, one wheelset, and four carbody corner
points synthesised from the carbody's linear + angular accelerations (a_corner = a_cg + alpha x r),
which is exact for a rigid body and needs no differencing.  Bands: 0.05-0.10 m and 1.0-4.0 m.

Each seed writes its own .tre (same spectrum, different random phases), so the spread printed here
is realisation-to-realisation scatter — the thing a single record cannot show.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import numpy as np

REPO = Path(r"F:\ai道岔状态反演辨识\Velch")
sys.path.insert(0, str(REPO / "src"))
from velch.irregularity import read_tre, write_tre  # noqa: E402
from velch.irregularity_gen import generate  # noqa: E402

WORK = Path(r"F:\velch_tmp\s6d")
BASE = Path(r"F:\velch_tmp\s6b")
SEEDS = (20261024, 7, 11, 13)
BANDS = ((0.05, 0.10), (1.0, 4.0))
SOUND = 0.01
CORNERS = (("front_left", 6.0, 1.0), ("front_right", 6.0, -1.0),
           ("rear_left", -6.0, 1.0), ("rear_right", -6.0, -1.0))


def run(seed: int) -> Path | None:
    out = WORK / f"out_s{seed}"
    out.mkdir(parents=True, exist_ok=True)
    if (out / "history.csv").exists():
        return out
    track = generate(spectrum_name="german_low", length_m=400.0, step_m=0.005,
                     shortest_m=0.1, longest_m=25.0, seed=seed)
    tre = WORK / f"track_s{seed}.tre"
    write_tre(tre, track, comment=f"seed {seed}")
    case = json.loads((BASE / "case_broadband.json").read_text(encoding="utf-8"))
    case["irregularity"] = {**case.get("irregularity", {}), "tre": str(tre)}
    case["case_id"] = f"s6d_s{seed}"
    path = WORK / f"case_s{seed}.json"
    path.write_text(json.dumps(case, indent=2, ensure_ascii=False), encoding="utf-8")
    done = subprocess.run([sys.executable, "-X", "utf8", "-m", "velch", "run-vehicle", str(path),
                           "--output", str(out), "--fast"], cwd=str(REPO),
                          capture_output=True, text=True, encoding="utf-8", errors="replace")
    if done.returncode != 0:
        print(f"  seed {seed}: run failed ({done.returncode}) {done.stderr.strip().splitlines()[-1][:90]}")
        return None
    return out


def bandpass(values, times, lo, hi):
    dt = float(np.median(np.diff(times)))
    spec = np.fft.rfft(values - values.mean())
    freqs = np.fft.rfftfreq(len(values), dt)
    spec[(freqs < lo) | (freqs > hi)] = 0.0
    return np.fft.irfft(spec, len(values))


def amplitude(signal, times, freq):
    basis = np.column_stack([np.cos(2 * np.pi * freq * times), np.sin(2 * np.pi * freq * times)])
    coef, *_ = np.linalg.lstsq(basis, signal, rcond=None)
    return float(np.hypot(*coef))


def sensors(history, times, case):
    """Named acceleration signals, including four synthesised carbody corners."""
    out = {}
    for name in history:
        if name.startswith("axle1_box_left") and name.endswith("_z_acc_m_per_s2"):
            out["box1L"] = history[name]
        elif name.startswith("axle1_box_right") and name.endswith("_z_acc_m_per_s2"):
            out["box1R"] = history[name]
        elif name == "axle0_z_acc_m_per_s2":
            out["wheelset0"] = history[name]
    az = history.get("carbody_z_acc_m_per_s2")
    roll = history.get("carbody_roll_acc_rad_per_s2")
    pitch = history.get("carbody_pitch_acc_rad_per_s2")
    if az is not None and roll is not None and pitch is not None:
        for label, dx, dy in CORNERS:
            out[label] = az + roll * dy - pitch * dx      # (alpha x r)_z, rigid body
    return out


def main() -> int:
    WORK.mkdir(parents=True, exist_ok=True)
    case = json.loads((BASE / "case_broadband.json").read_text(encoding="utf-8"))
    x_start = float(case["run"]["x_start_m"])
    speed = float(case["vehicle"]["travel_speed_m_s"])

    rows: dict[str, list[np.ndarray]] = {}
    conds: list[float] = []
    for seed in SEEDS:
        out = run(seed)
        if out is None:
            continue
        raw = np.genfromtxt(out / "history.csv", delimiter=",", names=True)
        history = {n: np.asarray(raw[n], dtype=float) for n in raw.dtype.names}
        times = history["time_s"]
        track = read_tre(WORK / f"track_s{seed}.tre")
        offsets = case["vehicle"].get("axle_offsets_m") or [-9.375, -6.875, 6.875, 9.375]
        seen = np.interp(x_start + speed * times + float(offsets[0]), track.s_m, track.vertical_m)
        signals = sensors(history, times, case)
        matrix = np.zeros((len(signals), len(BANDS)))
        for i, (label, signal) in enumerate(signals.items()):
            filtered = bandpass(signal, times, 0.5, 990.0)
            for j, (short, long_) in enumerate(BANDS):
                freq = speed / (0.5 * (short + long_))
                reference = amplitude(seen, times, freq)
                matrix[i, j] = amplitude(filtered, times, freq) / reference if reference > 0 else 0.0
                rows.setdefault(label, [np.zeros(len(BANDS)) for _ in SEEDS])
        gram = matrix.T @ matrix
        sv = np.linalg.svd(matrix, compute_uv=False)
        conds.append(float(sv[0] / sv[-1]) if sv[-1] > 0 else float("inf"))
        nea = np.sqrt(np.diag(SOUND ** 2 * np.linalg.inv(gram)))
        for i, label in enumerate(signals):
            rows[label][SEEDS.index(seed)] = matrix[i]
        print(f"  seed {seed:>9}: cond {conds[-1]:6.2f}  NEA {1e6 * nea[0]:7.2f} / {1e6 * nea[1]:7.2f} um")

    print("\nper-sensor |H| mean +- spread over seeds  (0.05-0.10 m / 1.0-4.0 m)")
    for label, per_seed in rows.items():
        values = np.array([v for v in per_seed if np.any(v)])
        if len(values) == 0:
            continue
        mean = values.mean(axis=0)
        spread = values.std(axis=0)
        print(f"  {label:12s} {mean[0]:11.1f} +- {spread[0]:8.1f}   {mean[1]:11.1f} +- {spread[1]:8.1f}")
    if conds:
        print(f"\ncondition number over {len(conds)} seeds: mean {np.mean(conds):.2f}, "
              f"min {np.min(conds):.2f}, max {np.max(conds):.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
