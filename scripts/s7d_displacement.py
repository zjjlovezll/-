"""S7d: does a body-to-axle-box *relative displacement* observation fix the 2 m bias?

L5 in ``docs/LITERATURE_LOG.md`` records what Dai et al. (MSSP 235, 2025, 112958) actually did to
identify 0.1-100 m vertical track irregularity from accelerations: the long waves come from a laser
displacement gauge measuring the body-to-axle-box travel ``dr``, a channel that "bypasses the VMD and
the numerical integration".  Our S4/S7b/S7c results say the same thing from three directions -- short
waves are attenuated 1/6330, the two-band vertical operator is rank 2 of 4, and the residual error is
bias rather than noise.  So the hypothesis to test is not "a better estimator" but "one more
observation of a different kind".

The measurement is available in our own output: both bodies' vertical positions are already in
``history.csv``, so ``dr = z_carbody - z_axlebox`` needs no new physics, no differentiation and no
integration.  Same case, same two bands (0.1 m and 2.0 m), same 0.10 mm probe, same 6 phase
realisations, same Tikhonov lambda, same seed as S7b -- so ``V`` must reproduce S7b's numbers exactly,
which is the control that says the machinery was carried over without drift.

Two estimators, because mixing metres with m/s^2 makes the raw system meaningless:

* ``raw``      -- plain Tikhonov on physical units (what S7b did; reproduced here as the control);
* ``balanced`` -- every row scaled to unit norm first.  This is a *weighting choice* (each sensor
                  trusted equally in relative terms), not a neutral transform, and it is what
                  S7c section 6 said belongs in the estimator.  The verdict uses ``balanced``.

Criteria, fixed before running:

* ``D`` alone must beat ``V`` on the 2.0 m band, whose bias was -23.5 %;
* ``V+D`` must reach calibration < 30 % (V was 65.2 %) and must not push closure above V's 8.39 %;
* blind error must stay within 1.5x the calibration error of the same variant;
* errors are also reported as absolute RMS in micrometres, which is the convention L5 uses.

Usage:  python -X utf8 scripts/s7d_displacement.py
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
WORK = Path(r"F:\velch_tmp\s7d")
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

#: label -> tuple of (column, factor).  A channel is a linear combination of recorded columns, which
#: is how a *relative* measurement is expressed without inventing a state.
CHANNELS: dict[str, tuple[tuple[str, float], ...]] = {
    "V": (("axle1_box_left_z_acc_m_per_s2", 1.0),),
    "D": (("carbody_z_m", 1.0), ("axle1_box_left_z_m", -1.0)),
}
VARIANTS = (("V", ("V",)), ("D", ("D",)), ("V+D", ("V", "D")))


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
                                     roll_rad=zeros, gauge_m=zeros, source="s7d"))
    payload = json.loads(json.dumps(base))
    payload["case_id"] = f"s7d_{name}"
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
    for label, spec in CHANNELS.items():
        values = np.zeros(mask.sum())
        for column, factor in spec:
            if column not in rows[0]:
                raise SystemExit(f"history has no {column!r}")
            values += factor * np.array([float(row[column]) for row in rows])[mask]
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
    stack: dict[str, list[np.ndarray]] = {label: [] for label in CHANNELS}
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
    return np.vstack([blocks[label] for label in channels])


def stack_measured(blocks: dict[str, np.ndarray], channels: tuple[str, ...]) -> np.ndarray:
    return np.concatenate([blocks[label] for label in channels])


def balance(matrix: np.ndarray, measured: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Scale every row to unit norm: a weighting choice, stated as one."""
    norms = np.linalg.norm(matrix, axis=1)
    norms[norms == 0.0] = 1.0
    return matrix / norms[:, None], measured / norms


def invert(matrix: np.ndarray, measured: np.ndarray) -> np.ndarray:
    system = matrix.conj().T @ matrix + (LAMBDA ** 2) * np.eye(len(BANDS))
    return np.linalg.solve(system, matrix.conj().T @ measured)


def solve(matrix: np.ndarray, measured: np.ndarray, *, balanced: bool) -> np.ndarray:
    if balanced:
        matrix, measured = balance(matrix, measured)
    return invert(matrix, measured)


def relative(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.linalg.norm(a - b) / np.linalg.norm(b))


def per_band_error(recovered: np.ndarray, truth: np.ndarray) -> list[float]:
    return [float((abs(value.real) - abs(reference)) / abs(reference))
            for value, reference in zip(recovered, truth)]


def main() -> int:
    base = json.loads(BASE.read_text(encoding="utf-8"))
    base.pop("initial_state", None)
    # The S5e base case froze a 1-based axle-box topology; B026 moved the numbering to 0-based.
    for body in base.get("topology", {}).get("bodies", []):
        if body.get("kind") == "axlebox" and isinstance(body.get("axle"), int):
            body["axle"] = body["axle"] - 1
    length = float(base["run"]["duration_s"]) * SPEED + 30.0
    rng = np.random.default_rng(20261025)

    columns: dict[float, dict[str, np.ndarray]] = {}
    for band in BANDS:
        columns[band] = column(band, base, length, rng)
    blocks = {label: np.column_stack([columns[band][label] for band in BANDS])
              for label in CHANNELS}
    print("column magnitude per band:")
    for label, spec in CHANNELS.items():
        unit = "m/s^2" if "acc" in spec[0][0] else "m"
        print(f"  {label} ({unit}): "
              + "  ".join(f"{abs(value):12.4f}" for value in np.linalg.norm(blocks[label], axis=1)))

    truth = SHAPE * AMPLITUDE_M
    phase = float(rng.uniform(0.0, 2.0 * np.pi))
    tags = {band: phase for band in BANDS}
    target_blocks = measure(run("target", dict(zip(BANDS, truth)), tags, base, length))

    blind = BLIND_SHAPE * AMPLITUDE_M
    blind_phase = float(rng.uniform(0.0, 2.0 * np.pi))
    blind_blocks = measure(run("blind", dict(zip(BANDS, blind)),
                               {band: blind_phase for band in BANDS}, base, length))

    print("\n             estimator   rows  cond      calibration  closure   blind     band errors")
    rows_out = []
    closure_of: dict[str, float] = {}
    for name, channels in VARIANTS:
        matrix = assemble(blocks, channels)
        measured = stack_measured(target_blocks, channels)
        blind_matrix = assemble(blind_blocks, channels)
        for balanced in (False, True):
            label = "balanced" if balanced else "raw"
            recovered = solve(matrix, measured, balanced=balanced)
            calibration = relative(recovered, truth)
            closure_out = run("closure", dict(zip(BANDS, recovered.real)), tags, base, length)
            closure = (float("nan") if closure_out is None
                       else relative(measure(closure_out)["V"], target_blocks["V"]))
            blind_recovered = solve(matrix, stack_measured(blind_blocks, channels),
                                    balanced=balanced)
            blind_error = relative(blind_recovered, blind)
            if not balanced:
                closure_of[name] = closure
            cond_matrix = balance(matrix, measured)[0] if balanced else matrix
            cond = float(np.linalg.cond(cond_matrix))
            errors = per_band_error(recovered, truth)
            rows_out.append((name, label, len(channels) * len(BANDS), cond, calibration,
                             closure, blind_error, recovered, errors))
            print(f"  {name:4s}  {label:10s} {len(channels) * len(BANDS):4d}  {cond:9.2f}  "
                  f"{calibration:11.1%}  {closure:7.2%}  {blind_error:8.1%}   "
                  + "  ".join(f"{value:+.1%}" for value in errors))
    print("  truth  (mm)                                                                     "
          + "  ".join(f"{value * 1000:+.4f}" for value in truth))

    baseline = next(row for row in rows_out if row[0] == "V" and row[1] == "balanced")
    print("\njudgement (verdict uses the balanced estimator; closure compared against V)")
    for name, label, _n, _c, calibration, closure, blind, recovered, errors in rows_out:
        if label != "balanced":
            continue
        notes = []
        notes.append(f"2 m band {errors[1]:+.1%} (V was "
                     + f"{baseline[8][1]:+.1%})")
        notes.append("meets <30 %" if calibration < 0.30
                     else ("beats V" if calibration < baseline[4] else "no gain over V"))
        if name != "V" and not np.isnan(closure):
            notes.append("closure " + ("better" if closure < closure_of["V"] else "worse")
                         + f" than V's {closure_of['V']:.2%}")
        if blind > 1.5 * calibration:
            notes.append("blind exceeds 1.5x calibration")
        absolute = float(np.linalg.norm(np.abs(recovered.real) - truth))
        print(f"  {name:4s}  " + "; ".join(notes)
              + f"; absolute RMS error {absolute * 1e6:.1f} um on "
                f"{float(np.linalg.norm(truth)) * 1e6:.1f} um of signal")
    print("\n  reminder: the displacement row carries the quasi-static part the accelerometer cannot")
    print("  see, but it is one number per band -- it adds information about amplitude, not shape.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
