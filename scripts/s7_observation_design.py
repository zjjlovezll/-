"""S7: which extra channels actually buy information, and which only add rows?

The question comes from S6d: seven vertical channels gave condition numbers 14.9–30.8 over four
random tracks, and the left/right axle boxes were *identical* because a straight symmetric case
excites both sides the same way.  A row that equals another row adds no rank, so the honest test is
not "does the matrix have fewer degrees of freedom" but:

    does this channel see something the others cannot?

Criteria, fixed before running anything (so the answer cannot be chosen after the fact):

* **worth installing** — the new row's *novelty* is at least 0.31, i.e. its angle to the subspace
  the baseline rows span leaves sin ≥ 0.31 (equivalently cos < 0.95).  A channel that repeats a
  direction already measured adds a row and no rank — that is the left/right axle-box case.
* **duplicate** — novelty below 0.31: a linear combination of channels already installed.
* **silent** — its own magnitude is under 0.1 % of the axle-box vertical channel, so the case never
  excites it and no verdict about information is possible.

The original plan also required "condition number drops ≥ 30 %".  That part is *structurally*
vacuous and was withdrawn before reading any result: appending a row to a matrix can never decrease
a singular value (AᵀA ⪯ AᵀA + bbᵀ), so the condition number of the augmented matrix necessarily
falls for **every** candidate, useful or not.  The column is still printed for continuity with S6d
and is labelled as non-evidence.

Channels are all read out of one simulation per seed: the axle box's vertical, lateral and
longitudinal accelerations plus its pitch acceleration (a 6-DOF body, so both are solved, not
differenced), the wheelset's vertical acceleration, and the four carbody corner accelerations
synthesised from the carbody's linear and angular accelerations (exact for a rigid body).

Bands: six, spanning 0.2–12.8 m (12 real coordinates per channel, so there is room for a new row
to be novel).  Two bands — the S6d pair — cannot answer this question at all: with four real
coordinates and seven baseline channels the baseline rows already span the whole space, so *every*
candidate has novelty exactly zero by construction.  The short end starts at 0.2 m because the
generated track carries no energy below 0.1 m and the writer emits at 2 kHz.

Usage:  python -X utf8 scripts/s7_observation_design.py
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

WORK = Path(r"F:\velch_tmp\s7")
BASE = Path(r"F:\velch_tmp\s6b")
SEEDS = (20261024, 7, 11)
BANDS = ((0.2, 0.4), (0.4, 0.8), (0.8, 1.6), (1.6, 3.2), (3.2, 6.4), (6.4, 12.8))
SOUND_M_S2 = 0.01
CORNERS = (("body_front_left", 6.0, 1.0), ("body_front_right", 6.0, -1.0),
           ("body_rear_left", -6.0, 1.0), ("body_rear_right", -6.0, -1.0))

#: The set every candidate is added to.  It is exactly S6d's seven channels.
BASELINE = ("box1L_z", "box1R_z", "wheelset0_z",
            "body_front_left", "body_front_right", "body_rear_left", "body_rear_right")

#: Candidate name -> history column it reads.  A name missing from the file is reported, not zeroed.
CANDIDATES = {
    "box1L_x": "axle1_box_left_x_acc_m_per_s2",
    "box1L_y": "axle1_box_left_y_acc_m_per_s2",
    "box1L_pitch": "axle1_box_left_pitch_acc_rad_per_s2",
}


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
    # The S6b case carries a frozen copy of the axle-box topology, written when axle boxes were
    # numbered 1-based; B026 moved them to 0-based like the wheelsets, and the loader now rejects
    # the stale copy.  Renumber it here rather than editing the frozen case: the axle number only
    # selects a column name and a wheelset, so the physics of this run is unchanged.
    for body in case.get("topology", {}).get("bodies", []):
        if body.get("kind") == "axlebox" and isinstance(body.get("axle"), int):
            body["axle"] = body["axle"] - 1
    case["irregularity"] = {**case.get("irregularity", {}), "tre": str(tre), "fade_m": 0.0}
    case["case_id"] = f"s7_s{seed}"
    path = WORK / f"case_s{seed}.json"
    path.write_text(json.dumps(case, indent=2, ensure_ascii=False), encoding="utf-8")
    done = subprocess.run([sys.executable, "-X", "utf8", "-m", "velch", "run-vehicle", str(path),
                           "--output", str(out), "--fast"], cwd=str(REPO),
                          capture_output=True, text=True, encoding="utf-8", errors="replace")
    if done.returncode != 0:
        print(f"  seed {seed}: run failed ({done.returncode})")
        print("   ", (done.stderr or done.stdout).strip().splitlines()[-1][:110])
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


def signals_for(history) -> dict[str, np.ndarray]:
    out: dict[str, np.ndarray] = {}
    z = history.get("axle1_box_left_z_acc_m_per_s2")
    if z is not None:
        out["box1L_z"] = z
    z = history.get("axle1_box_right_z_acc_m_per_s2")
    if z is not None:
        out["box1R_z"] = z
    z = history.get("axle1_z_acc_m_per_s2")
    if z is not None:
        out["wheelset0_z"] = z
    for name, column in CANDIDATES.items():
        values = history.get(column)
        if values is not None:
            out[name] = values
    az = history.get("carbody_z_acc_m_per_s2")
    roll = history.get("carbody_roll_acc_rad_per_s2")
    pitch = history.get("carbody_pitch_acc_rad_per_s2")
    if az is not None and roll is not None and pitch is not None:
        for label, dx, dy in CORNERS:
            out[label] = az + roll * dy - pitch * dx       # (alpha x r)_z for a rigid body
    return out


def similarity(row: np.ndarray, others: np.ndarray) -> float:
    """Largest |cos| between ``row`` and any row of ``others`` (both real, length 2*bands)."""
    if others.size == 0:
        return 0.0
    norm = np.linalg.norm(row)
    if norm == 0.0:
        return 1.0                                     # a silent channel is a copy of silence
    return float(np.max(np.abs(others @ row) / (np.linalg.norm(others, axis=1) * norm)))


def conditioning(rows: np.ndarray) -> float:
    """Condition number of the row set after putting every row on the unit sphere.

    Without that normalisation the number measures units, not geometry: a carbody corner
    acceleration is three orders of magnitude smaller than the axle box's, so its row drags the
    smallest singular value to ~1e-19 and the condition number reads 1e18 no matter how collinear
    the channels actually are.  Silent rows are dropped instead of contributing a zero.
    """
    norms = np.linalg.norm(rows, axis=1)
    keep = norms > 0.0
    if not keep.any():
        return float("inf")
    scaled = rows[keep] / norms[keep, None]
    singular = np.linalg.svd(scaled, compute_uv=False)
    if len(singular) == 0 or singular[-1] <= 0.0:
        return float("inf")
    return float(singular[0] / singular[-1])


def numerical_rank(rows: np.ndarray, tolerance: float = 1e-6) -> int:
    """How many independent directions a row set really spans.

    The condition number is the wrong headline here: two channels that measure the same thing on a
    symmetric case (the left and right axle boxes do) make it saturate at 1e15, and everything else
    disappears behind that.  Rank answers the question the sensor budget asks — *does installing
    this channel add a direction I could not already measure?*
    """
    norms = np.linalg.norm(rows, axis=1)
    keep = norms > 0.0
    if not keep.any():
        return 0
    singular = np.linalg.svd(rows[keep] / norms[keep, None], compute_uv=False)
    if len(singular) == 0 or singular[0] <= 0.0:
        return 0
    return int(np.sum(singular / singular[0] > tolerance))


def novelty(row: np.ndarray, others: np.ndarray) -> float:
    """Sine of the angle between ``row`` and the whole subspace the other rows span.

    This is the decisive number, and the reason is structural: appending a row to a matrix can
    never *decrease* a singular value (AᵀA ⪯ AᵀA + bbᵀ), so the condition number of the augmented
    matrix can only fall — every candidate "improves" it.  What is not automatic is whether the new
    row points anywhere new.  ``novelty = 1`` means orthogonal to everything already measured;
    ``0`` means a linear combination of existing rows, i.e. a wasted sensor.
    """
    if others.size == 0:
        return 1.0
    norm = float(np.linalg.norm(row))
    if norm == 0.0:
        return 0.0                                     # silent: no new direction to offer
    basis, _ = np.linalg.qr(others.T)                  # columns span the same subspace
    residual = row - basis @ (basis.T @ row)
    return float(np.linalg.norm(residual) / norm)


def main() -> int:
    WORK.mkdir(parents=True, exist_ok=True)
    case = json.loads((BASE / "case_broadband.json").read_text(encoding="utf-8"))
    x_start = float(case["run"]["x_start_m"])
    speed = float(case["vehicle"]["travel_speed_m_s"])
    offsets = case["vehicle"].get("axle_offsets_m") or [-9.375, -6.875, 6.875, 9.375]

    matrices: dict[str, tuple[np.ndarray, list[str]]] = {}
    conds: dict[str, list[float]] = {}
    ranks: dict[str, list[int]] = {}
    used: list[int] = []
    for seed in SEEDS:
        out = run(seed)
        if out is None:
            continue
        raw = np.genfromtxt(out / "history.csv", delimiter=",", names=True)
        history = {name: np.asarray(raw[name], dtype=float) for name in raw.dtype.names}
        times = history["time_s"]
        track = read_tre(WORK / f"track_s{seed}.tre")
        seen = np.interp(x_start + speed * times + float(offsets[0]),
                         track.s_m, track.vertical_m)
        signals = signals_for(history)
        matrix = np.zeros((len(signals), len(BANDS) * 2))       # real/imag per band
        for i, (label, signal) in enumerate(signals.items()):
            filtered = bandpass(signal, times, 0.5, 990.0)
            for j, (short, long_) in enumerate(BANDS):
                freq = speed / (0.5 * (short + long_))
                reference = amplitude(seen, times, freq)
                # amplitude() returns a magnitude; sign is kept by projecting onto the same basis
                basis = np.column_stack([np.cos(2 * np.pi * freq * times),
                                         np.sin(2 * np.pi * freq * times)])
                project, *_ = np.linalg.lstsq(basis, filtered, rcond=None)
                value = (project / reference) if reference > 0 else np.zeros(2)
                matrix[i, 2 * j:2 * j + 2] = value
        matrices[seed] = (matrix, list(signals))
        labels = list(signals)
        index = {label: i for i, label in enumerate(labels)}
        base = np.array([index[name] for name in BASELINE if name in index])
        conds.setdefault("baseline", []).append(conditioning(matrix[base]))
        ranks.setdefault("baseline", []).append(numerical_rank(matrix[base]))
        for candidate in CANDIDATES:
            if candidate not in index:
                continue
            rows = np.vstack([matrix[base], matrix[index[candidate]]])
            conds.setdefault(candidate, []).append(conditioning(rows))
            ranks.setdefault(candidate, []).append(numerical_rank(rows))
        used.append(seed)
        print(f"  seed {seed:>9}: baseline rank {ranks['baseline'][-1]:2d}/{len(BANDS) * 2}   "
              f"+x {ranks.get('box1L_x', [0])[-1]:2d}   "
              f"+y {ranks.get('box1L_y', [0])[-1]:2d}   "
              f"+pitch {ranks.get('box1L_pitch', [0])[-1]:2d}")
        if seed == SEEDS[-1] or len(used) == 1:
            print("    channels present:", ", ".join(labels))

    if not conds.get("baseline"):
        print("no run produced a history; nothing to judge")
        return 2

    base_rank = int(np.median(ranks["baseline"])) if ranks.get("baseline") else 0
    print(f"\nbaseline spans {base_rank} independent direction(s) out of {len(BANDS) * 2} possible,")
    print(f"over {len(used)} seeds (condition number {np.mean(conds['baseline']):.1e} — saturated")
    print("because the left and right axle boxes measure the same thing on a symmetric case).")
    print("\ncandidate       rank  ->  +1    novelty  rel.size   verdict")
    for candidate in CANDIDATES:
        values = ranks.get(candidate)
        if not values:
            print(f"  {candidate:12s}  (channel missing from the history)")
            continue
        cand_rank = int(np.median(values))
        sims, novs, sizes = [], [], []
        for seed in used:
            matrix, order = matrices[seed]
            index = {name: i for i, name in enumerate(order)}
            base_rows = np.array([matrix[index[name]] for name in BASELINE if name in index])
            row = matrix[index[candidate]]
            sims.append(similarity(row, base_rows))
            novs.append(novelty(row, base_rows))
            sizes.append(float(np.linalg.norm(row))
                         / max(float(np.linalg.norm(matrix[index["box1L_z"]])), 1e-300))
        sim, nov, size = max(sims), float(np.mean(novs)), float(np.mean(sizes))
        if size < 1e-3:
            verdict = "silent (this case never excites it)"
        elif nov >= 0.31 and size >= 0.01:
            verdict = "adds a direction, usable"
        elif nov >= 0.31:
            verdict = "adds a direction, but too weak"
        elif cand_rank > base_rank:
            verdict = "adds a thin direction, mostly a repeat"
        else:
            verdict = "duplicate of what is already there"
        print(f"  {candidate:12s} {base_rank:4d}  ->  {cand_rank:4d}   {nov:7.3f}  {size:8.3f}"
              f"   {verdict}")
    print("\n  reminder: this is one case — rigid track, straight, vertical irregularity only, three")
    print("  seeds of one band-limited spectrum.  A channel that reads silent here (pitch) is silent")
    print("  *for this excitation*, not in general: longitudinal levelling or braking excites it.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
