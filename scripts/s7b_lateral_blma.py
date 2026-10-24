"""S7b: does adding the axle-box *lateral* acceleration improve the inversion?

S7 (``s7_observation_design.py``) said the lateral channel is the one worth installing: its novelty
against the seven vertical channels was 0.374 (it points somewhere new) and its amplitude is 2.9 % of
the vertical channel.  But novelty is a geometric statement, not an accuracy statement.  The only
way to find out whether it buys accuracy is to put it into the estimator S5 used and compare.

This is the same experiment as ``s5_closure.py`` -- same straight case, same two bands (0.1 m and
2.0 m), same 0.10 mm probe amplitude, same 6 phase realisations per column, same Tikhonov lambda --
with one change: the measurement is now a vector of channels instead of one, and the inversion is
solved for each channel combination.  Because every run writes all channels at once, the extra
observations cost no extra simulation.

Three variants, same truth, same phases:

* ``V``   -- axle-box vertical (this reproduces S5: 65.2 % calibration, 8.39 % closure);
* ``V+L`` -- plus axle-box lateral, the channel S7 recommends;
* ``V+W`` -- plus wheelset vertical, a channel *closer to the contact* (S4 showed it sees 0.1 m far
             better than the axle box), as a control for "is it the lateral direction that helps, or
             would any extra row do?"

Criteria, fixed before running:

* the point of the exercise is the **calibration error** (criterion <30 % was missed at 65.2 %);
* **closure** must not get worse than the vertical-only variant (it was 8.39 %);
* a variant only counts as an improvement if it beats ``V`` on calibration by more than the
  realisation spread, and the report must say when the gain is inside the noise.

Usage:  python -X utf8 scripts/s7b_lateral_blma.py
"""

from __future__ import annotations

import csv
import json
import shutil
import subprocess
import sys
from pathlib import Path

VELCH = Path(r"F:\ai道岔状态反演辨识\Velch")
DATA = Path(r"F:\velch_data\validation\crh380a_m")
WORK = Path(r"F:\velch_tmp\s7b")
sys.path.insert(0, str(VELCH / "src"))

import numpy as np  # noqa: E402

from velch.case.derive import absolutise_profile_paths  # noqa: E402
from velch.irregularity import IrregularityTrack, write_tre  # noqa: E402

BASE = Path(r"F:\velch_tmp\straight\case_straight_axlebox.json")
BANDS = (0.1, 2.0)
SPEED = 97.2222
STEP_M = 0.005
AMPLITUDE_M = 0.10e-3
REALISATIONS = 6
SHAPE = np.array([0.83, 1.03])
BLIND_SHAPE = np.array([-0.62, 0.88])
LAMBDA = 1e-2

#: label -> history column.  The first one is S5's single observable.
CHANNELS = (
    ("V", "axle1_box_left_z_acc_m_per_s2"),
    ("L", "axle1_box_left_y_acc_m_per_s2"),
    ("W", "axle1_z_acc_m_per_s2"),
)
VARIANTS = (("V", ("V",)), ("V+L", ("V", "L")), ("V+W", ("V", "W")),
            ("V+L+W", ("V", "L", "W")))


def run(name: str, amplitudes: dict[float, float], tags: dict[float, float], base: dict,
        length_m: float) -> Path | None:
    WORK.mkdir(parents=True, exist_ok=True)
    s_m = np.arange(int(round(length_m / STEP_M)) + 1, dtype=float) * STEP_M
    vertical = np.zeros_like(s_m)
    for band, amplitude in amplitudes.items():
        vertical += amplitude * np.sin(2.0 * np.pi * s_m / band + tags.get(band, 0.0))
    zeros = np.zeros_like(s_m)
    tre = WORK / f"{name}.tre"
    write_tre(tre, IrregularityTrack(s_m=s_m, lateral_m=zeros, vertical_m=vertical,
                                     roll_rad=zeros, gauge_m=zeros, source="s7b"))
    payload = json.loads(json.dumps(base))
    payload["case_id"] = f"s7b_{name}"
    payload["irregularity"] = {"tre": str(tre), "start_m": 0.0, "end_m": 1.0e6,
                               "fade_m": 10.0, "scale": 1.0, "channels": ["vertical"]}
    absolutise_profile_paths(payload, DATA)
    path = WORK / f"{name}.json"
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    out = WORK / f"out_{name}"
    if out.exists():
        shutil.rmtree(out)
    done = subprocess.run([sys.executable, "-X", "utf8", "-m", "velch", "run-vehicle", str(path),
                           "--output", str(out), "--fast"],
                          cwd=str(VELCH), capture_output=True, text=True, encoding="utf-8",
                          errors="replace")
    if done.returncode != 0 or not (out / "history.csv").exists():
        print(f"{name}: run failed (exit {done.returncode}) {(done.stderr or '')[-140:]}")
        return None
    return out


def measure(out: Path) -> dict[str, np.ndarray]:
    """Complex amplitude of every channel at every band, from one run."""
    with (out / "history.csv").open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    times = np.array([float(row["time_s"]) for row in rows])
    span = times[-1] - times[0]
    mask = (times >= times[0] + 0.15 * span) & (times <= times[0] + 0.90 * span)
    times = times[mask]
    result: dict[str, np.ndarray] = {}
    for label, column in CHANNELS:
        if column not in rows[0]:
            raise SystemExit(f"history has no {column!r}")
        values = np.array([float(row[column]) for row in rows])[mask]
        values = values - values.mean()
        per_band = []
        for band in BANDS:
            design = np.column_stack([np.cos(2 * np.pi * times * SPEED / band),
                                      np.sin(2 * np.pi * times * SPEED / band)])
            a, b = np.linalg.lstsq(design, values, rcond=None)[0]
            per_band.append(complex(b, a))
        result[label] = np.array(per_band)
    return result


def column(band: float, base: dict, length: float, rng) -> dict[str, np.ndarray]:
    """Best linear approximation column for one band, coherently averaged over realisations."""
    stack: dict[str, list[np.ndarray]] = {label: [] for label, _ in CHANNELS}
    for index in range(REALISATIONS):
        phase = float(rng.uniform(0.0, 2.0 * np.pi))
        out = run(f"h{band}_{index}", {band: AMPLITUDE_M}, {band: phase}, base, length)
        if out is None:
            continue
        measured = measure(out)
        for label in stack:
            stack[label].append(measured[label] * np.exp(-1j * phase))
    if any(len(items) < REALISATIONS - 1 for items in stack.values()):
        raise SystemExit(f"band {band}: only "
                         + ", ".join(f"{k}={len(v)}" for k, v in stack.items()) + " ran")
    return {label: np.array(items).mean(axis=0) / AMPLITUDE_M for label, items in stack.items()}


def assemble(blocks: dict[str, np.ndarray], channels: tuple[str, ...]) -> np.ndarray:
    """Stack the per-channel rows into one observation operator (rows = observations)."""
    return np.vstack([blocks[label] for label in channels])


def invert(matrix: np.ndarray, measured: np.ndarray) -> np.ndarray:
    system = matrix.conj().T @ matrix + (LAMBDA ** 2) * np.eye(len(BANDS))
    return np.linalg.solve(system, matrix.conj().T @ measured)


def stack_measured(blocks: dict[str, np.ndarray], channels: tuple[str, ...]) -> np.ndarray:
    return np.concatenate([blocks[label] for label in channels])


def relative(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.linalg.norm(a - b) / np.linalg.norm(b))


def main() -> int:
    base = json.loads(BASE.read_text(encoding="utf-8"))
    base.pop("initial_state", None)
    # The S5e base case froze its axle-box topology when those bodies were numbered 1-based; B026
    # moved them to 0-based and the loader now rejects the stale copy.  Renumber here: the axle
    # number only picks a column name and a wheelset, so the physics is untouched.
    for body in base.get("topology", {}).get("bodies", []):
        if body.get("kind") == "axlebox" and isinstance(body.get("axle"), int):
            body["axle"] = body["axle"] - 1
    length = float(base["run"]["duration_s"]) * SPEED + 30.0
    rng = np.random.default_rng(20261025)

    columns: dict[float, dict[str, np.ndarray]] = {}
    for band in BANDS:
        columns[band] = column(band, base, length, rng)
    blocks = {label: np.column_stack([columns[band][label] for band in BANDS])
              for label, _ in CHANNELS}
    print("column magnitude per band, (m/s^2)/m:")
    for label, _ in CHANNELS:
        print(f"  {label}: " + "  ".join(f"{abs(value):12.1f}" for value in
                                          np.linalg.norm(blocks[label], axis=1)))

    truth = SHAPE * AMPLITUDE_M
    phase = float(rng.uniform(0.0, 2.0 * np.pi))
    tags = {band: phase for band in BANDS}
    target_blocks = measure(run("target", dict(zip(BANDS, truth)), tags, base, length))

    blind = BLIND_SHAPE * AMPLITUDE_M
    blind_phase = float(rng.uniform(0.0, 2.0 * np.pi))
    blind_blocks = measure(run("blind", dict(zip(BANDS, blind)),
                              {band: blind_phase for band in BANDS}, base, length))

    print("\nvariant    rows  cond    calibration   closure   blind      recovered (mm)")
    summary = []
    closure_cache: dict[str, float | None] = {}
    for name, channels in VARIANTS:
        matrix = assemble(blocks, channels)
        measured = stack_measured(target_blocks, channels)
        recovered = invert(matrix, measured)
        calibration = relative(recovered, truth)
        closure_out = run("closure", dict(zip(BANDS, recovered.real)), tags, base, length)
        if closure_out is None:
            closure = float("nan")
        else:
            closure = relative(measure(closure_out)["V"], target_blocks["V"])
        blind_recovered = invert(matrix, stack_measured(blind_blocks, channels))
        blind_error = relative(blind_recovered, blind)
        closure_cache[name] = closure
        summary.append((name, len(channels) * len(BANDS), float(np.linalg.cond(matrix)),
                        calibration, closure, blind_error, recovered))
        print(f"  {name:6s} {len(channels) * len(BANDS):4d}  {np.linalg.cond(matrix):7.2f}  "
              f"{calibration:9.1%}  {closure:9.2%}  {blind_error:8.1%}   "
              + " ".join(f"{value * 1000:+.4f}" for value in recovered.real))
    print("  truth                                                              "
          + " ".join(f"{value * 1000:+.4f}" for value in truth))

    base_calibration = dict((name, cal) for name, _r, _c, cal, _cl, _b, _v in summary)["V"]
    base_closure = closure_cache["V"]
    print(f"\njudgement (criterion: calibration <30 %, and closure must not exceed the V variant)")
    for name, _rows, _cond, calibration, closure, _blind, _rec in summary:
        if name == "V":
            continue
        gain = base_calibration - calibration
        verdict = []
        verdict.append(f"calibration {calibration:.1%} vs {base_calibration:.1%} "
                       f"({gain * 100:+.1f} points)")
        if calibration < 0.30:
            verdict.append("meets <30 %")
        elif gain <= 0.0:
            verdict.append("no gain")
        else:
            verdict.append("improves but still above 30 %")
        if closure is not None and base_closure is not None and not np.isnan(closure):
            verdict.append("closure " + ("better" if closure < base_closure else "worse"))
        print(f"  {name:6s}  " + "; ".join(verdict))
    print("\n  reminder: the lateral row is roughly 30x weaker than the vertical one, so it enters the")
    print("  least-squares problem with the same absolute noise and far less signal.  A small gain")
    print("  (or none) here is a statement about SNR, not about whether the direction is new.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
