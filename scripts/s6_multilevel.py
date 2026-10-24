"""S6b: which accelerometer carries which wavelength?

One broadband irregularity, four accelerometer levels (wheelset, axle box, bogie frame, car body),
one run.  Per wavelength band it reports

    gain  G  = rms(acc in band) / rms(rail profile in band)      [(m/s^2)/m]
    coherence gamma^2 between the band-passed input and response  [-]  (how linear that band is)
    NEA      = sensor noise / G                                   [m]  (amplitude worth one noise unit)

NEA answers the only question that matters for inversion: for this band, how much track amplitude
is needed before the channel says anything above its own noise.  The assumed sensor noise is a
stated input, not a measurement: 0.01 m/s^2 (~1 mg) per band.
"""

import csv
import json
import shutil
import subprocess
import sys
from pathlib import Path

VELCH = Path(r"F:\ai道岔状态反演辨识\Velch")
DATA = Path(r"F:\velch_data\validation\crh380a_m")
WORK = Path(r"F:\velch_tmp\s6b")
sys.path.insert(0, str(VELCH / "src"))

import numpy as np  # noqa: E402
from scipy.signal import butter, coherence, filtfilt, welch  # noqa: E402

from velch.case.derive import absolutise_profile_paths  # noqa: E402
from velch.irregularity import write_tre  # noqa: E402
from velch.irregularity_gen import generate  # noqa: E402

BASE = Path(r"F:\velch_tmp\straight\case_straight_axlebox.json")
SPEED = 97.2222
BANDS_M = ((0.1, 0.2), (0.2, 0.5), (0.5, 1.0), (1.0, 2.0), (2.0, 5.0), (5.0, 10.0), (10.0, 25.0))
CHANNELS = {
    "轮对": "axle0_z_acc_m_per_s2",
    "轴箱": "axle1_box_left_z_acc_m_per_s2",
    "构架": "bogie0_z_acc_m_per_s2",
    "车体": "carbody_z_acc_m_per_s2",
}
NOISE_M_S2 = 0.01
TARGET_RMS_MM = 0.15


def build(base, track, length_m):
    WORK.mkdir(parents=True, exist_ok=True)
    tre = WORK / "broadband.tre"
    write_tre(tre, track, comment="s6b broadband")
    payload = json.loads(json.dumps(base))
    payload["case_id"] = "s6b_broadband"
    payload["irregularity"] = {"tre": str(tre), "start_m": 0.0, "end_m": 1.0e6,
                              "fade_m": 20.0, "scale": 1.0, "channels": ["vertical"]}
    absolutise_profile_paths(payload, DATA)
    path = WORK / "case_broadband.json"
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def run(path):
    out = WORK / "out"
    if out.exists():
        shutil.rmtree(out)
    done = subprocess.run([sys.executable, "-X", "utf8", "-m", "velch", "run-vehicle", str(path),
                           "--output", str(out), "--fast"],
                          cwd=VELCH, capture_output=True, text=True, encoding="utf-8",
                          errors="replace")
    if done.returncode != 0:
        raise SystemExit(f"run failed (exit {done.returncode}): {done.stderr[-600:]}")
    return out


def bandpass(values, fs, low, high, order=4):
    nyquist = 0.5 * fs
    if high >= 0.98 * nyquist:
        high = 0.98 * nyquist
    if low >= 0.98 * high:
        return np.zeros_like(values)
    b, a = butter(order, [low / nyquist, high / nyquist], btype="band")
    return filtfilt(b, a, values)


def main():
    base = json.loads(BASE.read_text(encoding="utf-8"))
    base.pop("initial_state", None)
    duration = float(base["run"]["duration_s"])
    fs = 1.0 / float(base["run"]["output_step_s"])

    track = generate(spectrum_name="german_low", length_m=400.0, step_m=0.005,
                     shortest_m=0.1, longest_m=25.0, seed=20261024)
    vertical = np.asarray(track.vertical_m, dtype=float)
    rms_before = float(np.sqrt(np.mean(vertical ** 2))) * 1000.0
    scale = (TARGET_RMS_MM * 1e-3) / (rms_before * 1e-3)
    track = type(track)(s_m=track.s_m, lateral_m=track.lateral_m, vertical_m=vertical * scale,
                        roll_rad=track.roll_rad, gauge_m=track.gauge_m, source="german_low x%.3f" % scale)
    print(f"profile: german_low 0.1-25 m, rms {rms_before:.4f} -> {TARGET_RMS_MM:.2f} mm "
          f"(scale {scale:.3f})")

    out = run(build(base, track, 400.0))
    with (out / "history.csv").open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    times = np.array([float(row["time_s"]) for row in rows])
    x_start = float(base["run"]["x_start_m"])
    mileage = x_start + SPEED * times
    profile_seen = np.interp(mileage, track.s_m, track.vertical_m)
    print(f"frames {len(times)}, mileage {mileage[0]:.1f}-{mileage[-1]:.1f} m, fs {fs:.0f} Hz")

    table = {}
    for name, column in CHANNELS.items():
        series = np.array([float(row[column]) for row in rows])
        entry = {}
        for low_m, high_m in BANDS_M:
            f_low, f_high = SPEED / high_m, SPEED / low_m
            if f_low >= 0.98 * 0.5 * fs:
                entry[f"{low_m:g}-{high_m:g}"] = None
                continue
            response = bandpass(series, fs, f_low, f_high)
            source = bandpass(profile_seen, fs, f_low, f_high)
            gain = float(np.sqrt(np.mean(response ** 2)) / max(np.sqrt(np.mean(source ** 2)), 1e-15))
            _, gamma = coherence(source, response, fs=fs, nperseg=min(256, len(times)))
            entry[f"{low_m:g}-{high_m:g}"] = {
                "f_lo": f_low, "f_hi": f_high, "gain": gain,
                "coherence": float(np.mean(gamma)),
                "nea_mm": 1e3 * NOISE_M_S2 / gain if gain > 0 else None,
            }
        table[name] = entry

    header = ["band m"] + [f"{name} G" for name in CHANNELS] + [f"{name} NEA" for name in CHANNELS]
    print("| " + " | ".join(header) + " |")
    print("|" + "---|" * len(header))
    for low_m, high_m in BANDS_M:
        key = f"{low_m:g}-{high_m:g}"
        cells = [key]
        for name in CHANNELS:
            value = table[name][key]
            cells.append("—" if value is None else f"{value['gain']:.0f}")
        for name in CHANNELS:
            value = table[name][key]
            cells.append("—" if value is None else f"{value['nea_mm'] * 1000:.1f} µm")
        print("| " + " | ".join(cells) + " |")
    print()
    print("coherence")
    for low_m, high_m in BANDS_M:
        key = f"{low_m:g}-{high_m:g}"
        cells = [key] + ["—" if table[name][key] is None else f"{table[name][key]['coherence']:.2f}"
                         for name in CHANNELS]
        print("| " + " | ".join(cells) + " |")
    (WORK / "s6b_table.json").write_text(json.dumps(table, indent=2), encoding="utf-8")
    print(f"written {WORK / 's6b_table.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
