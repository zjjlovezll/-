"""S7c: does the axle-box **lateral** acceleration let the inversion separate vertical from lateral?

S7b showed that adding the lateral channel to an experiment that excites **vertical** track only
changes nothing: with two bands and two unknowns the vertical channel already gives a square system,
so an extra row can only average noise, and the error is a bias.

That experiment never asked the lateral channel a question it can answer.  Lateral acceleration is
driven by **lateral alignment**, so the question has to have a lateral unknown in it.  This script
asks that question, and it is deliberately the cheapest version that can still be decisive:

    one band (2.0 m), two unknowns (vertical amplitude, lateral amplitude),
    two observations (box vertical acceleration, box lateral acceleration).

    variant V    1 complex observation -> 2 real equations for 4 real unknowns -> rank deficient
    variant L    1 complex observation -> same
    variant V+L  2 complex observations -> 4 real equations, 4 unknowns -> square

Pre-registered criterion, written before the run:

    * V and L alone must be **rank deficient** (rank < 4).  That is the statement "one channel cannot
      separate the two directions", and it is structural, not numerical -- it will hold.
    * The lateral channel is **worth installing** if V+L is full rank AND its calibration error on the
      two recovered amplitudes is < 30 %, with closure not worse than 30 %.
    * If V+L is full rank but the error stays above 30 %, the honest conclusion is: the lateral channel
      separates the directions in principle, but at 0.10 mm it cannot do so quantitatively.

Everything is measured with the S5/S7b machinery so the numbers stay comparable: same straight
axle-box case, same 0.10 mm probe, same BLMA (coherent average over random phases), same lambda.
"""

from __future__ import annotations

import csv
import json
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np

from velch.irregularity import IrregularityTrack, write_tre

VELCH = Path(r"F:\ai道岔状态反演辨识\Velch")
DATA = Path(r"F:\velch_data\validation\crh380a_m")
BASE = Path(r"F:\velch_tmp\straight\case_straight_axlebox.json")
WORK = Path(r"F:\velch_tmp\s7c")

BAND = 2.0                     # metres; long enough to survive the 0.005 m sampling, short enough
AMPLITUDE_M = 0.10e-3          # probe amplitude per column (0.10 mm)
REALISATIONS = 4               # per column; each run is ~15 s at this band
SPEED = 97.2222
STEP_M = 0.005
LAMBDA = 1e-2

TRUTH = {"vertical": 0.10e-3, "lateral": 0.06e-3}   # deliberately different, so separation is testable

OBSERVATIONS = (
    ("V", "axle1_box_left_z_acc_m_per_s2"),
    ("L", "axle1_box_left_y_acc_m_per_s2"),
)
VARIANTS = (("V", ("V",)), ("L", ("L",)), ("V+L", ("V", "L")))


def absolutise(payload: dict) -> None:
    """Profile paths resolve against the case file, so a case written to another folder needs them."""
    def walk(node):
        if isinstance(node, dict):
            for key, value in node.items():
                if key in ("file", "path", "profile") and isinstance(value, str):
                    candidate = (DATA / value)
                    if candidate.exists():
                        node[key] = str(candidate)
                else:
                    walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(payload)


def run(name: str, vertical: float, lateral: float, phase: float, base: dict,
        length_m: float) -> Path | None:
    WORK.mkdir(parents=True, exist_ok=True)
    s_m = np.arange(int(round(length_m / STEP_M)) + 1, dtype=float) * STEP_M
    vz = vertical * np.sin(2.0 * np.pi * s_m / BAND + phase)
    dy = lateral * np.sin(2.0 * np.pi * s_m / BAND + phase)
    zeros = np.zeros_like(s_m)
    tre = WORK / f"{name}.tre"
    write_tre(tre, IrregularityTrack(s_m=s_m, lateral_m=dy, vertical_m=vz,
                                     roll_rad=zeros, gauge_m=zeros, source="s7c"))
    payload = json.loads(json.dumps(base))
    payload["case_id"] = f"s7c_{name}"
    payload["irregularity"] = {"tre": str(tre), "start_m": 0.0, "end_m": 1.0e6,
                               "fade_m": 10.0, "scale": 1.0,
                               "channels": ["vertical", "lateral"] if lateral else ["vertical"]}
    absolutise(payload)
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
        print(f"{name}: run failed (exit {done.returncode}) {(done.stderr or '')[-160:]}")
        return None
    return out


def measure(out: Path) -> dict[str, complex]:
    """Complex amplitude of every observation channel at the single band."""
    with (out / "history.csv").open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    times = np.array([float(row["time_s"]) for row in rows])
    span = times[-1] - times[0]
    mask = (times >= times[0] + 0.15 * span) & (times <= times[0] + 0.90 * span)
    times = times[mask]
    design = np.column_stack([np.cos(2 * np.pi * times * SPEED / BAND),
                              np.sin(2 * np.pi * times * SPEED / BAND)])
    result: dict[str, complex] = {}
    for label, column in OBSERVATIONS:
        values = np.array([float(row[column]) for row in rows])[mask]
        values = values - values.mean()
        a, b = np.linalg.lstsq(design, values, rcond=None)[0]
        result[label] = complex(b, a)
    return result


def column(which: str, base: dict, length: float, rng) -> dict[str, complex]:
    """One BLMA column: the response to a unit amplitude of ``which`` direction."""
    stack: dict[str, list[complex]] = {label: [] for label, _ in OBSERVATIONS}
    amplitude = {"v": (AMPLITUDE_M, 0.0), "l": (0.0, AMPLITUDE_M)}
    moved = 0
    for index in range(REALISATIONS):
        phase = float(rng.uniform(0.0, 2.0 * np.pi))
        vertical, lateral = amplitude[which]
        out = run(f"h{which}_{index}", vertical, lateral, phase, base, length)
        if out is None:
            continue
        measured = measure(out)
        for label in stack:
            stack[label].append(measured[label] * np.exp(-1j * phase) / AMPLITUDE_M)
        moved += 1
    if moved < REALISATIONS - 1:
        raise SystemExit(f"column {which}: only {moved}/{REALISATIONS} runs succeeded")
    return {label: complex(np.mean(values)) for label, values in stack.items()}


def real_system(matrix: np.ndarray) -> np.ndarray:
    """(rows complex) -> real matrix acting on [Re a_v, Im a_v, Re a_l, Im a_l]."""
    rows = []
    for value in matrix:
        rows.append([value[0].real, -value[0].imag, value[1].real, -value[1].imag])
        rows.append([value[0].imag, value[0].real, value[1].imag, value[1].real])
    return np.asarray(rows, dtype=float)


def relative(recovered: np.ndarray, truth: np.ndarray) -> float:
    return float(np.linalg.norm(recovered - truth) / np.linalg.norm(truth))


def main() -> int:
    base = json.loads(BASE.read_text(encoding="utf-8"))
    base.pop("initial_state", None)
    for body in base.get("topology", {}).get("bodies", []):
        if body.get("kind") == "axlebox" and isinstance(body.get("axle"), int):
            body["axle"] = body["axle"] - 1
    length = float(base["run"]["duration_s"]) * SPEED + 30.0
    rng = np.random.default_rng(20261026)

    print(f"band {BAND} m, probe {AMPLITUDE_M * 1000:.2f} mm per direction, "
          f"{REALISATIONS} phase realisations per column\n")
    vertical_column = column("v", base, length, rng)
    lateral_column = column("l", base, length, rng)
    print("column magnitudes (m/s^2 per m of track), vertical- and lateral-excited:")
    for label, _ in OBSERVATIONS:
        print(f"  {label}: from vertical {abs(vertical_column[label]):10.1f}   "
              f"from lateral {abs(lateral_column[label]):10.1f}")

    # one common phase for both directions, removed from the target measurement, so the recovered
    # complex vector is directly comparable with the (real) truth
    common = float(rng.uniform(0.0, 2.0 * np.pi))
    target = measure(run("target", TRUTH["vertical"], TRUTH["lateral"], common, base, length))
    target = {label: value * np.exp(-1j * common) for label, value in target.items()}
    truth = np.array([TRUTH["vertical"], TRUTH["lateral"]], dtype=float)

    print("\nvariant  equations  rank  cond      calibration   closure   recovered vertical / lateral (mm)")
    for name, channels in VARIANTS:
        columns = np.array([[vertical_column[label], lateral_column[label]] for label in channels])
        measured = np.array([target[label] for label in channels])
        system = real_system(columns)
        rank = int(np.linalg.matrix_rank(system, tol=1e-6 * np.linalg.norm(system, 2)))
        rhs = np.empty(2 * len(channels))
        for index, value in enumerate(measured):
            rhs[2 * index] = value.real
            rhs[2 * index + 1] = value.imag
        normal = system.T @ system + (LAMBDA ** 2) * np.eye(4)
        solution = np.linalg.solve(normal, system.T @ rhs)
        recovered = np.array([solution[0] + 1j * solution[1], solution[2] + 1j * solution[3]])
        calibration = relative(recovered, truth)
        condition = (float(np.linalg.cond(system)) if system.shape[0] == system.shape[1]
                     else float("nan"))
        closure_out = run("closure", float(recovered[0].real), float(recovered[1].real),
                          common, base, length)
        if closure_out is None:
            closure = float("nan")
        else:
            again = measure(closure_out)
            again = {label: value * np.exp(-1j * common) for label, value in again.items()}
            top = np.linalg.norm(np.array([again[label] for label in channels]) - measured)
            bottom = np.linalg.norm(measured)
            closure = float(top / bottom)
        print(f"  {name:5s} {2 * len(channels):10d} {rank:5d} {condition:8.2f}  "
              f"{calibration:9.1%}  {closure:8.2%}   "
              f"{recovered[0].real * 1000:+.4f} / {recovered[1].real * 1000:+.4f}")
    print(f"  truth {'':22s}{'':10s}{'':9s}{'':9s}   "
          f"{truth[0] * 1000:+.4f} / {truth[1] * 1000:+.4f}")

    print("\njudgement (criteria fixed before the run)")
    print("  rank < 4  -> that observation set cannot separate vertical from lateral, structurally")
    print("  rank = 4 and calibration < 30 % and closure < 30 % -> the lateral channel is usable")
    print("  rank = 4 but calibration >= 30 % -> separates in principle, not quantitatively at 0.10 mm")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
