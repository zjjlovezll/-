"""The 60 km/h archive is not a measurement: its modal block is still ringing when the run starts.

Rounds 304-309 built a three-speed table whose slowest row kept disagreeing (0.145 m against a 0.145 m that the
lateral registration could not explain).  Building the probe for the last two candidates turned up the reason:
**the 60 km/h run never settles.**  Its front-axle normal force swings between 0 and 208 kN (standard deviation
34.8 kN) where the 80 and 100 km/h runs hold 60.1 kN to within 0.07 and 0.51 kN, and its blade force crosses
1 kN nine times across the window where they cross once and stay.

The mechanism is visible in the state itself: the run starts with the modal (rail) block displaced
|modal| = 1.57e-02 m, 5.7 times the 2.8e-03 m the other two start from, and it is still at 1.18e-02 m half a
second later -- no decay.  That is the signature of the seat that needed ``seat_modal_scales = 0.8``: the run is
launched inside a large rail-mode transient, and 0.54 s is not long enough to leave it.

Claims, fixed before this script ran:

* **C1** -- the 60 km/h run is not stationary: the loaded rail's normal-force standard deviation exceeds 5 kN
  while both other runs stay under 1 kN, and its blade force crosses 1 kN more than twice;
* **C2** -- the cause is an unsettled modal block: its initial norm is at least twice the others' and its final
  norm is more than half its initial one, i.e. no decay over the window.

Consequences recorded here, not in prose elsewhere: the 60 km/h ``engage(5 %) = 58.000 m`` is withdrawn, the
0.145 m offset is withdrawn, and the claim that the offset shrinks with speed is withdrawn.  The valid table has
two speeds, not three -- and that is a data defect, not a tolerance question.
"""

from __future__ import annotations

import json
import pathlib
import sys

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import s162_engage_alternatives as base  # noqa: E402

REPORT = ROOT / "reports" / "load_split_inversion_2026-10-31" / "engage_chatter.json"

SPEEDS_KMH = (60.0, 80.0, 100.0)
WINDOW_M = (57.6, 58.4)
BLADE_ON_N = 1_000.0
MAX_STD_KN = 5.0
MAX_CROSSINGS = 2
MODAL_RATIO = 2.0
DECAY_FRACTION = 0.5
#: State layout for the one-set case: 86 vehicle, 16 track (8 rails x y,z), 132 modal (4 wheelsets x 33).
TRACK_BLOCK = slice(86, 102)
MODAL_BLOCK = slice(102, 234)


def upcrossings(signal: np.ndarray, threshold: float) -> int:
    above = signal >= threshold
    return int(np.sum(above[1:] & ~above[:-1]))


def stationarity(speed_kmh: float) -> dict:
    directory = base._run_dir(speed_kmh)
    series = np.load(directory / "series.npz")
    meta = json.loads((directory / "meta.json").read_text(encoding="utf-8"))
    times = series["times"]
    rails = list(meta["rail_ids"])
    forces = series["normal_force_n"]
    positions = series["positions"]
    station = float(meta["x_start_m"]) + base.AXLE_OFFSET_M + float(meta["speed_m_s"]) * times
    front = rails.index(base.RAIL_ID)
    modal = positions[:, MODAL_BLOCK]
    track = positions[:, TRACK_BLOCK]
    picks = [0, len(times) // 4, len(times) // 2, len(times) - 1]
    inside = (station >= WINDOW_M[0]) & (station <= WINDOW_M[1])
    blade = series["body_normal_force_n"][:, list(meta["body_labels"]).index(f"{base.RAIL_ID}/blade")]
    return {
        "run_id": directory.name,
        "frames": int(len(times)),
        "duration_s": float(times[-1]),
        "wall_s": float(meta.get("wall_s", float("nan"))),
        "force_std_kn": {rail: 1e-3 * float(forces[:, i].std()) for i, rail in enumerate(rails)},
        "force_min_max_kn": {
            rail: [1e-3 * float(forces[:, i].min()), 1e-3 * float(forces[:, i].max())]
            for i, rail in enumerate(rails)
        },
        "loaded_rail_std_kn": 1e-3 * float(forces[:, front].std()),
        "blade_upcrossings_over_1kn": upcrossings(blade[inside], BLADE_ON_N),
        "modal_norm_m": [float(np.linalg.norm(modal[i])) for i in picks],
        "track_norm_m": [float(np.linalg.norm(track[i])) for i in picks],
        "gates_all_true": bool(all(meta["gates"].values())) if isinstance(meta.get("gates"), dict) else None,
    }


def verdict(report: dict) -> dict:
    rows = report["rows"]
    sixty, eighty, hundred = rows["60"], rows["80"], rows["100"]
    others = [eighty["loaded_rail_std_kn"], hundred["loaded_rail_std_kn"]]
    modal_start = {key: rows[key]["modal_norm_m"][0] for key in rows}
    modal_end = {key: rows[key]["modal_norm_m"][-1] for key in rows}
    reference = float(np.median([modal_start["80"], modal_start["100"]]))
    ratio = modal_start["60"] / reference
    decay = modal_end["60"] / modal_start["60"]
    return {
        "c1_sixty_not_stationary": bool(sixty["loaded_rail_std_kn"] > MAX_STD_KN
                                        and max(others) < 1.0
                                        and sixty["blade_upcrossings_over_1kn"] > MAX_CROSSINGS),
        "loaded_rail_std_kn": {key: rows[key]["loaded_rail_std_kn"] for key in rows},
        "blade_upcrossings": {key: rows[key]["blade_upcrossings_over_1kn"] for key in rows},
        "modal_norm_start_m": modal_start,
        "modal_norm_end_m": modal_end,
        "modal_start_ratio_60_over_others": ratio,
        "modal_decay_60": decay,
        "c2_modal_transient_unsettled": bool(ratio >= MODAL_RATIO and decay > DECAY_FRACTION),
        "six_sixty_usable": bool(not (report["rows"]["60"]["loaded_rail_std_kn"] > MAX_STD_KN)),
        "valid_speeds_kmh": [speed for speed in SPEEDS_KMH if rows[f"{speed:g}"]["loaded_rail_std_kn"] < MAX_STD_KN],
        "withdrawn": [
            "60 km/h engage(5 %) = 58.000 m (round 304's physical column)",
            "the 0.145 m offset between 60 and 80 km/h",
            "the claim that the offset shrinks as speed falls",
        ],
        "gates_note": "all seven numerical gates are true for every row; stationarity is not one of them",
        "purpose": "decide whether the 60 km/h row is a measurement at all",
    }


def main() -> int:
    report = {"rows": {f"{speed:g}": stationarity(speed) for speed in SPEEDS_KMH}}
    report["constants"] = {
        "window_m": list(WINDOW_M),
        "blade_on_n": BLADE_ON_N,
        "max_std_kn": MAX_STD_KN,
        "max_crossings": MAX_CROSSINGS,
        "modal_ratio": MODAL_RATIO,
        "decay_fraction": DECAY_FRACTION,
        "track_block": [TRACK_BLOCK.start, TRACK_BLOCK.stop],
        "modal_block": [MODAL_BLOCK.start, MODAL_BLOCK.stop],
    }
    report["verdict"] = verdict(report)
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    print(f"{'speed':>7} {'frames':>7} {'std kN':>8} {'min-max kN':>18} {'up>1kN':>7} "
          f"{'modal0 m':>10} {'modal_end m':>12} {'decay':>7}")
    for speed in SPEEDS_KMH:
        row = report["rows"][f"{speed:g}"]
        low, high = row["force_min_max_kn"][base.RAIL_ID]
        print(f"{speed:7.1f} {row['frames']:7d} {row['loaded_rail_std_kn']:8.2f} [{low:7.2f},{high:8.2f}] "
              f"{row['blade_upcrossings_over_1kn']:7d} {row['modal_norm_m'][0]:10.3e} "
              f"{row['modal_norm_m'][-1]:12.3e} {row['modal_norm_m'][-1] / row['modal_norm_m'][0]:7.3f}")
    print()
    v = report["verdict"]
    print(f"C1 sixty not stationary {v['c1_sixty_not_stationary']}  std {v['loaded_rail_std_kn']}")
    print(f"modal start ratio       {v['modal_start_ratio_60_over_others']:.2f}x   decay {v['modal_decay_60']:.3f}")
    print(f"C2 modal unsettled      {v['c2_modal_transient_unsettled']}")
    print(f"valid speeds            {v['valid_speeds_kmh']}")
    print(f"report -> {REPORT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
