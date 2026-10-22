"""Extract the simulated rack-turnout contact history into a compact, comparable artefact.

Source: ``NoExt_zgzn_jdz6.2mm_SP_00.mat`` (Simpack HDF5, 12 001 samples at dt = 1 ms, mean speed
7.90 m/s = 28.5 km/h, uphill).  Produces ``rack_simpack_contact.json`` plus one CSV of the
frog-passage window so a measured run can be laid on the same axis later.

Channel meaning follows the documented Simpack element tables (78 pair / 79 patch / 80 Adv):
  pair ch_008 = station s [m];  ch_001 = Q [N];  ch_010 = Dz wheel lift [m];  ch_022 = patch count
  patch ch_010 = normal force N [N]
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import h5py
import numpy as np

OUTPUT = Path(r"H:\齿轨工况\坡度工况\matlab\VEH_GEAR0_FX_STR_RACKN_QY-Re1_cjy_whcl_zn_TE_USERFORCE_CG_120.output")
PLAIN = OUTPUT / "NoExt_zgzn_jdz6.2mm_SP_00.mat"
BASE = Path(__file__).resolve().parent
FRAME = "timeInt/RS_result/SRS_S_B_F/SRS_S_WS_F"


def channel(handle: h5py.File, path: str) -> np.ndarray | None:
    if path not in handle:
        return None
    node = handle[path]
    data = node["values"] if isinstance(node, h5py.Group) else node
    return np.asarray(data[...], dtype=float).ravel()


def main() -> int:
    with h5py.File(PLAIN, "r") as handle:
        time = channel(handle, "timeInt/time/values")
        if time is None:
            time = np.asarray(handle["timeInt/time"][...], dtype=float).ravel()

        wheelset_x = channel(handle, f"{FRAME}/../bodyPosTrans")  # placeholder, replaced below
        position = channel(handle, "timeInt/bodyPosTrans/SS_B_F__S_WS_F__B_WS/x/values")
        vertical = channel(handle, "timeInt/bodyPosTrans/SS_B_F__S_WS_F__B_WS/z/values")

        payload: dict[str, object] = {
            "source": str(PLAIN), "samples": int(time.size),
            "t0_s": float(time.min()), "t1_s": float(time.max()),
            "dt_s": float(np.median(np.diff(time))),
            "speed_m_s": float((position[-1] - position[0]) / (time[-1] - time[0])),
        }
        payload["wheelset_x_m"] = {"min": float(position.min()), "max": float(position.max())}
        if vertical is not None:
            payload["wheelset_z_m"] = {"min": float(vertical.min()), "max": float(vertical.max()),
                                      "peak_to_peak_m": float(vertical.max() - vertical.min())}

        sides = {}
        grade_slope = None
        station_axis = None
        z_resid = None
        if position is not None and vertical is not None:
            # the rack case is an uphill run: z carries the 12 % grade, so the *bounce* is the
            # residual against a straight line fitted in (x, z)
            coefficients = np.polyfit(position, vertical, 1)
            grade_slope = float(coefficients[0])
            z_resid = vertical - np.polyval(coefficients, position)
            payload["grade"] = {"slope": grade_slope,
                                "percent": 100.0 * grade_slope,
                                "bounce_peak_to_peak_m": float(z_resid.max() - z_resid.min()),
                                "bounce_min_m": float(z_resid.min()),
                                "bounce_max_m": float(z_resid.max())}
            print(f"grade {100.0 * grade_slope:.2f} %  (z climbed "
                  f"{vertical.max() - vertical.min():.3f} m over "
                  f"{position.max() - position.min():.3f} m)")
            print(f"bounce (z minus grade) peak-to-peak {1e3 * (z_resid.max() - z_resid.min()):.3f} mm")
            station_axis = position

        for side in ("L", "R"):
            pair = f"{FRAME}/SRS_RWP_{side}/SRS_RWP_{side}_Pair"
            station = channel(handle, f"{pair}/ch_008/values")
            force = channel(handle, f"{pair}/ch_001/values")
            lift = channel(handle, f"{pair}/ch_010/values")
            patches = channel(handle, f"{pair}/ch_022/values")
            if station is None or force is None:
                continue
            # station from the pair channel is authoritative; wheelset x matches within 1 mm
            peaks = {"max_n": float(force.max()), "min_n": float(force.min()),
                     "mean_n": float(force.mean())}
            index = int(np.argmax(force))
            peaks["peak_station_m"] = float(station[index])
            peaks["peak_time_s"] = float(time[index])
            if lift is not None:
                peaks["wheel_lift_peak_to_peak_m"] = float(lift.max() - lift.min())
            if patches is not None:
                peaks["patches_max"] = float(patches.max())
                peaks["two_patch_samples"] = int(np.count_nonzero(patches >= 2))
            sides[side] = {"station_m": station.tolist(), "force_n": force.tolist(),
                           "lift_m": (lift.tolist() if lift is not None else None),
                           "patches": (patches.tolist() if patches is not None else None),
                           "peaks": peaks}
            print(f"{side}: N {force.min() / 1e3:7.2f}..{force.max() / 1e3:7.2f} kN "
                  f"(peak at s={station[index]:.3f} m, t={time[index]:.4f} s), "
                  f"patches<= {peaks.get('patches_max')}, two-patch samples "
                  f"{peaks.get('two_patch_samples')}")

        payload["sides"] = {side: data["peaks"] for side, data in sides.items()}

        # window around the peak of the right rail, for the measured overlay
        right = sides.get("R")
        if right is not None:
            station = np.asarray(right["station_m"])
            force = np.asarray(right["force_n"])
            centre = float(payload["sides"]["R"]["peak_station_m"])
            mask = (station > centre - 3.0) & (station < centre + 3.0)
            window_rows = np.flatnonzero(mask)
            payload["window"] = {"centre_m": centre, "span_m": 6.0, "samples": int(window_rows.size)}

        # compact CSV (station, force, patch count, de-trended bounce) for the right rail
        csv_path = BASE / "rack_simpack_right.csv"
        station_values = np.asarray(right["station_m"], dtype=float)
        if station_axis is not None and z_resid is not None:
            bounce = np.interp(station_values, station_axis, z_resid)
        else:
            bounce = np.zeros_like(station_values)
        with csv_path.open("w", encoding="utf-8", newline="") as handle_csv:
            writer = csv.writer(handle_csv)
            writer.writerow(["station_m", "force_n", "patches", "wheel_lift_m", "bounce_m"])
            for s, f, p, dz, bz in zip(station_values, right["force_n"], right["patches"],
                                       right["lift_m"], bounce):
                writer.writerow([f"{s:.6f}", f"{f:.6f}", int(p), f"{dz:.9f}", f"{bz:.9f}"])

        for key in ("station_m", "force_n", "lift_m", "patches"):
            for side in sides.values():
                side.pop(key, None)
        payload["files"] = {"csv": str(csv_path)}

    (BASE / "rack_simpack_contact.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nwrote {BASE / 'rack_simpack_contact.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
