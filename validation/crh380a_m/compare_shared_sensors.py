"""The model has no rail strain gauge -- so compare the observables it *does* share.

Findings from ``probe_rack_sensors.py``: the model's 12 sensors are 8 axle-box accelerometers
(``$S_B_F.$S_F[L/R]`` ...) plus ``$S_cd1..4``; there is no rail-foot strain channel, so the
measured force channels (CH01..CH06, strain-bridge derived) have no simulated counterpart.
Accelerations and rail/sleeper displacements *are* shared.

This script computes, on both sides, the same amplitude statistics (peak-to-peak and p99.9 of the
passage window) so the two sensor families can be compared without inventing a scaling.
"""

from __future__ import annotations

import json
from pathlib import Path

import h5py
import numpy as np

from velch.io.measured import event_window, read_channel

OUTPUT = Path(r"H:\齿轨工况\坡度工况\matlab\VEH_GEAR0_FX_STR_RACKN_QY-Re1_cjy_whcl_zn_TE_USERFORCE_CG_120.output")
PLAIN = OUTPUT / "NoExt_zgzn_jdz6.2mm_SP_00.mat"
MEASURED = Path(r"E:\齿轨测试数据\加速度采集\30KMH-SP-1")
BASE = Path(__file__).resolve().parent


def series(group: h5py.Group, name: str) -> np.ndarray | None:
    if name not in group:
        return None
    node = group[name]
    if isinstance(node, h5py.Dataset):
        return np.asarray(node[...], dtype=float).ravel()
    if "values" in node:
        return np.asarray(node["values"][...], dtype=float).ravel()
    return None


def sensor_resultant(group: h5py.Group) -> np.ndarray | None:
    axes = [series(group, axis) for axis in ("x", "y", "z")]
    if all(axis is not None for axis in axes):
        return np.sqrt(sum(np.square(axis) for axis in axes))  # type: ignore[arg-type]
    single = series(group, "values")
    return single


def main() -> int:
    report: dict[str, object] = {"simulated": {}, "measured": {}}
    with h5py.File(PLAIN, "r") as handle:
        for container in ("sensorAccTrans", "sensorPosTrans"):
            group = handle[f"timeInt/{container}"]
            print(f"\n=== {container} ===")
            for name in sorted(group.keys()):
                node = group[name]
                if not isinstance(node, h5py.Group):
                    continue
                values = sensor_resultant(node)
                if values is None:
                    continue
                amplitude = float(values.max() - values.min())
                metric = float(np.percentile(np.abs(values - values.mean()), 99.9))
                print(f"  {name:<22} p-p {amplitude:12.6f}   p99.9(|dev|) {metric:12.6f}")
                report["simulated"].setdefault(container, {})[name] = {
                    "peak_to_peak": amplitude, "p999_deviation": metric, "samples": int(values.size)}

    print(f"\n=== measured accelerations: {MEASURED} ===")
    rows = {}
    for channel in range(1, 8):
        try:
            time, value = read_channel(MEASURED, channel, repair_clock=True)
        except Exception as error:  # noqa: BLE001 - report which channel is unavailable
            print(f"  CH{channel:02d}: unavailable ({error})")
            continue
        window = event_window(time, np.abs(value))
        inside = (time >= window[0]) & (time <= window[1])
        passage = value[inside] if inside.any() else value
        amplitude = float(passage.max() - passage.min())
        metric = float(np.percentile(np.abs(passage - passage.mean()), 99.9))
        print(f"  CH{channel:02d} p-p {amplitude:10.4f}  p99.9(|dev|) {metric:10.4f}"
              f"   window {window[0]:.2f}-{window[1]:.2f} s")
        rows[f"CH{channel:02d}"] = {"peak_to_peak": amplitude, "p999_deviation": metric,
                                    "window_s": [float(window[0]), float(window[1])]}
    report["measured"]["acceleration"] = rows
    report["note"] = ("the rack model carries no rail strain gauge; measured force channels "
                      "CH01..CH06 are strain-bridge derived and have no simulated counterpart")
    (BASE / "rack_shared_sensors.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
