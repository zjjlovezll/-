"""Demonstrate the observation layer on real artefacts (both branches).

Branch A (simulation-to-simulation): pair the Velch right-rail normal force with
Simpack's ``SRS_RWP_R_Pair`` Q on a common *station* axis.

Branch B (measured): there is no measured turnout data in this repository yet, so the
event-anchored path is demonstrated on the axle-box acceleration channel that the
solver would have to produce for a real comparison — the alignment itself is real, the
observed series is taken from the simulation and shifted, which is enough to show the
plumbing and *not* enough to claim agreement. The script says so in its output.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[2]
MCP_SRC = REPO_ROOT / "simpack-mcp-2021x" / "src"
for extra in (str(REPO_ROOT / "Velch" / "src"), str(MCP_SRC)):
    if extra not in sys.path:
        sys.path.insert(0, extra)

from velch.inverse import ChannelSpec, ObservationSet, align  # noqa: E402
from velch.io.history import read_history, write_history  # noqa: E402

MAT = (REPO_ROOT / "simpack-mcp-2021x" / "results"
       / "case_a47bc7d9e48f40b08628147bfab5c3f4" / "model.output" / "350.mat")
GROUP_PAIR = "timeInt/RS_result/SRS_S_R/SRS_S_WS_F/SRS_RWP_R/SRS_RWP_R_Pair"
GROUP_PATCH = "timeInt/RS_result/SRS_S_R/SRS_S_WS_F/SRS_RWP_R/SRS_RWP_R_1"
VELCH_RUN = HERE / "out_final_full1p2s"
WINDOW_M = (78.8, 82.2)
OUT = HERE / "demo_observation.json"


def simpack_side() -> tuple[np.ndarray, np.ndarray]:
    """Read the pair's station (ch_008) and the patch's normal force (ch_010).

    ``simpack_mcp.rwp.extract_rwp_channels`` reports channel statistics, not full
    series, so the demo reads the datasets directly; the channel *meaning* still comes
    from the documented tables (element 78: ch_008 = s; element 79: ch_010 = N).
    """

    import h5py

    with h5py.File(MAT, "r") as handle:
        station = np.asarray(handle[GROUP_PAIR]["ch_008"]["values"], float).ravel()
        force = np.asarray(handle[GROUP_PATCH]["ch_010"]["values"], float).ravel()
    if station.shape != force.shape:
        raise SystemExit("simpack channels have different lengths")
    # The pair's ch_008 spans 6.0 .. 122.667 m, the wheelset body spans 23.5 .. 140.167 m,
    # so the two origins differ by an offset that the model does not document. Rather
    # than hard-code it, the demo derives it from the data (see best_station_shift).
    return station, force


def best_station_shift(predicted: ObservationSet, observed: ObservationSet,
                       span_m: float = 20.0, step_m: float = 0.05) -> tuple[float, float]:
    """Find the station offset that minimises the force residual.

    Returns ``(shift_m, rms_at_shift)``. This is a *diagnostic of the comparator*, not a
    calibration: a large best shift means the two station axes need reconciling before
    any residual is interpreted.
    """

    force_name = "axle1_right_normal_n"
    index = predicted.names.index(force_name)
    pred_station = predicted.values[predicted.names.index("axle1_x_m")]
    obs_station = observed.values[observed.names.index("axle1_x_m")]
    pred_force = predicted.values[index]
    obs_force = observed.values[index]
    best = (0.0, float("inf"))
    for shift in np.arange(-span_m, span_m + 0.5 * step_m, step_m):
        moved = ObservationSet(
            (ChannelSpec("axle1_x_m", "m"),
             ChannelSpec(force_name, "N", sigma=1.0e3)),
            observed.axis, np.array([obs_station + shift, obs_force]), observed.axis_unit)
        try:
            alignment = align(predicted, moved, "station")
        except ObservationError:
            continue
        value = alignment.channel_metrics[force_name]["rms"]
        if value < best[1]:
            best = (float(shift), float(value))
    del pred_station
    return best


def main() -> int:
    table = read_history(VELCH_RUN)
    print(f"history schema     : {table.schema_version}")
    print(f"samples            : {table.samples}")
    print(f"channels           : {len(table.ordering)}")
    kinds = sorted({channel.kind for channel in table.channels.values()})
    print(f"channel kinds      : {kinds}")
    print(f"time span          : {table.time_s[0]:.4f} .. {table.time_s[-1]:.4f} s")

    x_velch = table["axle1_x_m"]
    f_velch = table["axle1_right_normal_n"]

    xs, fs = simpack_side()
    print(f"simpack pair       : {xs.shape[0]} samples, {xs[0]:.3f} .. {xs[-1]:.3f} m")

    # Branch A: write each side out as a two-channel table, then align by station.
    for side, (station, force) in {"velch": (x_velch, f_velch),
                                   "simpack": (xs, fs)}.items():
        time = table.time_s if side == "velch" else np.arange(station.shape[0], dtype=float)
        write_history(HERE / f"demo_obs_{side}.csv", _table(time, station, force))

    velch_obs = ObservationSet(
        (ChannelSpec("axle1_x_m", "m"),
         ChannelSpec("axle1_right_normal_n", "N", sigma=1.0e3)),
        table.time_s, np.array([x_velch, f_velch]), "s",
        {"side": "velch", "run": VELCH_RUN.name})
    sim_obs = ObservationSet(
        (ChannelSpec("axle1_x_m", "m"),
         ChannelSpec("axle1_right_normal_n", "N", sigma=1.0e3)),
        np.arange(xs.shape[0], dtype=float), np.array([xs, fs]), "-",
        {"side": "simpack", "group": GROUP_PATCH})

    print("\n--- simulation vs simulation (station alignment) ---")
    raw = align(velch_obs, sim_obs, "station")
    print(f"paired samples     : {raw.samples}")
    print(f"raw rms            : {raw.channel_metrics['axle1_right_normal_n']['rms'] / 1e3:.2f} kN")

    shift_m, shift_rms = best_station_shift(velch_obs, sim_obs)
    print(f"best station shift : {shift_m:+.2f} m (rms {shift_rms / 1e3:.2f} kN)")
    moved = ObservationSet(
        (ChannelSpec("axle1_x_m", "m"),
         ChannelSpec("axle1_right_normal_n", "N", sigma=1.0e3)),
        sim_obs.axis, np.array([sim_obs.values[0] + shift_m, sim_obs.values[1]]),
        sim_obs.axis_unit, dict(sim_obs.provenance))
    station_alignment = align(velch_obs, moved, "station")
    window = (station_alignment.axis >= WINDOW_M[0]) & (station_alignment.axis <= WINDOW_M[1])
    picked = _window(station_alignment, window)
    print(f"frog window pairs  : {picked['samples']}")
    print(f"peak velch/simpack : {picked['predicted_peak'] / 1e3:.2f} / "
          f"{picked['observed_peak'] / 1e3:.2f} kN")
    print(f"max |residual|     : {picked['max_abs'] / 1e3:.2f} kN")
    print(f"rms                : {picked['rms'] / 1e3:.2f} kN")
    print("note               : the force residual is reported, not interpreted; the "
          "station origins of the two models differ by the shift above.")

    # Branch B: event-anchored alignment on an acceleration channel the way a measured
    # campaign would use it. The "measured" series here is the prediction with its time
    # axis shifted by a known 20 ms, so the demo can state a *true* claim: the anchoring
    # recovers a known timing offset. It is not evidence of model agreement.
    acceleration = np.gradient(np.gradient(table["axle1_z_m"], table.time_s), table.time_s)
    specs = (ChannelSpec("axle1_acc_z", "m/s^2", sigma=1.0),)
    predicted = ObservationSet(specs, table.time_s, np.array([acceleration]), "s")

    shift_s = 0.02
    observed = ObservationSet(specs, table.time_s + shift_s,
                              np.array([acceleration]), "s")
    anchor_s = 0.6055  # the 82.368 m force peak of this run
    naive = align(predicted, observed, "time")
    anchored = align(predicted, observed, "event",
                     event_time_s=anchor_s + shift_s, event_anchor_s=anchor_s)
    print("\n--- measured-style (event anchoring) ---")
    print(f"injected offset    : {shift_s * 1e3:.1f} ms")
    print(f"acceleration range : {acceleration.min():.1f} .. {acceleration.max():.1f} m/s^2")
    print(f"naive max_abs      : {naive.channel_metrics['axle1_acc_z']['max_abs']:.1f} m/s^2")
    print(f"anchored max_abs   : {anchored.channel_metrics['axle1_acc_z']['max_abs']:.3f} m/s^2")
    print("note               : observed = prediction with its time axis shifted, so this "
          "proves the anchoring recovers a known offset; it is not evidence of agreement.")

    payload = {
        "history": {"schema": table.schema_version, "samples": table.samples,
                    "channels": len(table.ordering), "time_span_s":
                    [float(table.time_s[0]), float(table.time_s[-1])]},
        "simulation_vs_simulation": {
            "strategy": "station", "paired_samples": station_alignment.samples,
            "frog_window_m": list(WINDOW_M), "frog_window": picked},
        "measured_style": {
            "strategy": "event",
            "naive_max_abs_m_s2": naive.channel_metrics["axle1_acc_z"]["max_abs"],
            "anchored_max_abs_m_s2": anchored.channel_metrics["axle1_acc_z"]["max_abs"],
            "caveat": "observed series is the prediction shifted by 20 ms"},
    }
    OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nreport             : {OUT}")
    return 0


def _table(time: np.ndarray, station: np.ndarray, force: np.ndarray):
    from velch.io.history import HISTORY_SCHEMA, HistoryTable, classify

    names = ("time_s", "axle1_x_m", "axle1_right_normal_n")
    data = np.array([time, station, force], dtype=float)
    return HistoryTable(HISTORY_SCHEMA, time, {n: classify(n) for n in names},
                        data, "demo", names)


def _window(alignment, mask) -> dict[str, float]:
    subset = alignment.channel_metrics["axle1_right_normal_n"]
    force_index = alignment.observed.names.index("axle1_right_normal_n")
    observed = alignment.observed.values[force_index][mask]
    predicted = alignment.predicted[force_index][mask]
    delta = predicted - observed
    return {
        "samples": float(observed.size),
        "observed_peak": float(np.max(np.abs(observed))) if observed.size else float("nan"),
        "predicted_peak": float(np.max(np.abs(predicted))) if predicted.size else float("nan"),
        "max_abs": float(np.max(np.abs(delta))) if observed.size else float("nan"),
        "rms": float(np.sqrt(np.mean(delta ** 2))) if observed.size else float("nan"),
        "full_run_max_abs": subset["max_abs"],
    }


if __name__ == "__main__":
    raise SystemExit(main())
