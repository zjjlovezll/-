"""S7e: does the body-to-axle-box displacement carry the *long*-wave information?

S7d measured the same channel in the 0.1 m and 2.0 m bands and it carried almost nothing:
``dr`` gets 0.48 % of a 0.1 m profile and 11.9 % of a 2.0 m one, because the secondary suspension
filters both.  That refuted "displacement rescues the short-wave band".

It also explains why Dai et al. (MSSP 235, 2025, 112958 -- L5) use it successfully: at 30-70 km/h
their useful band is 20-100 m, i.e. 0.08-0.9 Hz, at the car-body bounce mode.  At that wavelength
the body no longer follows the track, so ``dr`` becomes a large fraction of the profile.  We never
measured that band.  This script does: bands **20 m and 40 m** = 4.86 Hz and 2.43 Hz at 97.2 m/s.

**The first attempt at this failed as a measurement, and the failure is the design.**  With a 2 s
record the car covers 194 m of the real rail geometry, and that geometry has far more content at
2-5 Hz than a 0.1 mm probe: a run with *no probe at all* still fits 478 / 1040 m/m (``D``) and
17 211 / 60 537 (``V``).  So an absolute complex fit at those frequencies measures the case's own
geometry, not the probe.  The geometry contribution ``B`` is the same in every realisation --
same case, same start mileage, same speed -- while only the probe phase ``phi_k`` changes.  The
estimator is therefore a regression with an intercept:

    y_k(band) = A(band) * exp(i*phi_k) + B(band)      k = 1..8 realisations

``A`` is the response to the probe (divided by its amplitude), ``B`` the nuisance geometry term.
Eight realisations give 16 real equations for 4 real unknowns per band.  The residual of that fit
is printed, because when ``|B| >> |A|`` the answer is a small difference of large numbers and the
residual is the honest yardstick for it.

Prediction that can fail: ``D``'s transfer ratio ``|A|`` should be close to **1.0 m/m** and ``D``
alone should reach **< 10 %** calibration error.  If not, the displacement-channel line is dropped
for that band.

Usage:  python -X utf8 scripts/s7e_longwave.py
"""

from __future__ import annotations

import csv
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

VELCH = Path(r"F:\ai道岔状态反演辨识\Velch")
DATA = Path(r"F:\velch_data\validation\crh380a_m")
WORK = Path(r"F:\velch_tmp\s7e")
sys.path.insert(0, str(VELCH / "src"))

import numpy as np  # noqa: E402

from velch.case.derive import absolutise_profile_paths  # noqa: E402
from velch.irregularity import IrregularityTrack, write_tre  # noqa: E402

BASE = Path(r"F:\velch_tmp\straight\case_straight_axlebox.json")
BANDS = (20.0, 40.0)
SPEED = 97.2222
STEP_M = 0.005
DURATION_S = 2.0
AMPLITUDE_M = 0.10e-3
REALISATIONS = 8
SHAPE = np.array([0.83, 1.03])
BLIND_SHAPE = np.array([-0.62, 0.88])
LAMBDA = 1e-2

CHANNELS: dict[str, tuple[tuple[str, float], ...]] = {
    "V": (("axle1_box_left_z_acc_m_per_s2", 1.0),),
    "D": (("carbody_z_m", 1.0), ("axle1_box_left_z_m", -1.0)),
}
VARIANTS = (("V", ("V",)), ("D", ("D",)), ("V+D", ("V", "D")))

ELAPSED: list[float] = []


def _encode(block: dict[str, np.ndarray]) -> dict[str, list[list[float]]]:
    return {label: [[value.real, value.imag] for value in values] for label, values in block.items()}


def _decode(raw: dict[str, list[list[float]]]) -> dict[str, np.ndarray]:
    return {label: np.array([complex(real, imag) for real, imag in pairs])
            for label, pairs in raw.items()}


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
                                     roll_rad=zeros, gauge_m=zeros, source="s7e"))
    payload = json.loads(json.dumps(base))
    payload["case_id"] = f"s7e_{name}"
    payload["irregularity"] = {"tre": str(tre), "start_m": 0.0, "end_m": 1.0e6,
                               "fade_m": 10.0, "scale": 1.0, "channels": ["vertical"]}
    absolutise_profile_paths(payload, DATA)
    path = WORK / f"{name}.json"
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    out = WORK / f"out_{name}"
    if out.exists():
        shutil.rmtree(out)
    started = time.perf_counter()
    done = subprocess.run([sys.executable, "-X", "utf8", "-m", "velch", "run-vehicle", str(path),
                           "--output", str(out), "--fast"],
                          cwd=str(VELCH), capture_output=True, text=True, encoding="utf-8",
                          errors="replace")
    elapsed = time.perf_counter() - started
    ELAPSED.append(elapsed)
    if done.returncode != 0 or not (out / "history.csv").exists():
        print(f"{name}: run failed (exit {done.returncode}) {(done.stderr or '')[-140:]}",
              flush=True)
        return None
    print(f"{name}: {elapsed:6.1f} s", flush=True)
    return out


def measure(out: Path) -> dict[str, np.ndarray]:
    """Complex amplitude of every channel at every band, from one run (no baseline removed)."""
    with (out / "history.csv").open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    times = np.array([float(row["time_s"]) for row in rows])
    span = times[-1] - times[0]
    # Start at 30 % rather than 15 %: the first second of a 2 s record is still settling from the
    # state the case supplies, and that settling sits in the same 2-5 Hz band as the bands.
    mask = (times >= times[0] + 0.30 * span) & (times <= times[0] + 0.95 * span)
    times = times[mask]
    result: dict[str, np.ndarray] = {}
    for label, spec in CHANNELS.items():
        values = np.zeros(int(mask.sum()))
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


def column(band: float, base: dict, length: float, rng) -> tuple[dict, dict, dict]:
    """Phase regression with an intercept: separate the probe response from the case's geometry.

    ``y_k = A * exp(i*phi_k) + B`` over the realisations.  ``A`` is what the probe produced,
    ``B`` is the geometry both runs share, and the residual says how much the additive model
    missed (contact nonlinearity, realisation-to-realisation scatter).
    """
    phases: list[float] = []
    stacks: dict[str, list[np.ndarray]] = {label: [] for label in CHANNELS}
    for index in range(REALISATIONS):
        phase = float(rng.uniform(0.0, 2.0 * np.pi))
        out = run(f"h{band}_{index}", {band: AMPLITUDE_M}, {band: phase}, base, length)
        if out is None:
            continue
        measured = measure(out)
        phases.append(phase)
        for label in stacks:
            stacks[label].append(measured[label])
    if any(len(items) < REALISATIONS - 1 for items in stacks.values()):
        raise SystemExit(f"band {band}: only "
                         + ", ".join(f"{k}={len(v)}" for k, v in stacks.items()) + " ran")
    design = np.column_stack([np.exp(1j * np.array(phases)), np.ones(len(phases))])
    response: dict[str, np.ndarray] = {}
    nuisance: dict[str, np.ndarray] = {}
    residual: dict[str, np.ndarray] = {}
    for label, items in stacks.items():
        data = np.array(items)
        coefficients, *_ = np.linalg.lstsq(design, data, rcond=None)
        response[label] = coefficients[0] / AMPLITUDE_M
        nuisance[label] = coefficients[1]
        residual[label] = np.linalg.norm(data - design @ coefficients, axis=0)
    return response, nuisance, residual


def assemble(blocks: dict[str, np.ndarray], channels: tuple[str, ...]) -> np.ndarray:
    return np.vstack([blocks[label] for label in channels])


def stack_measured(blocks: dict[str, np.ndarray], channels: tuple[str, ...]) -> np.ndarray:
    return np.concatenate([blocks[label] for label in channels])


def balance(matrix: np.ndarray, measured: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
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


def magnitude_error(a: np.ndarray, b: np.ndarray) -> float:
    """Error on the moduli: the recovered vector still carries the imposed phase."""
    return float(np.linalg.norm(np.abs(a) - b) / np.linalg.norm(b))


def per_band_error(recovered: np.ndarray, truth: np.ndarray) -> list[float]:
    # Magnitudes, not real parts: the regression reference carries the imposed phase, so the
    # recovered vector is truth * exp(i*phase) and only its modulus is comparable.
    return [float((abs(value) - abs(reference)) / abs(reference))
            for value, reference in zip(recovered, truth)]


def differential(name: str, amplitudes: dict[float, float], phase: float, base: dict,
                 length: float) -> dict[str, np.ndarray]:
    """Response to the probe alone: run the same waveform at +phase and at +phase+pi and halve.

    ``y(phase) = H*A*exp(i*phase) + B`` and ``y(phase+pi) = -H*A*exp(i*phase) + B``, so the
    difference removes the case's own geometry ``B`` exactly instead of assuming it.
    """
    plus = run(f"{name}_plus", amplitudes, {band: phase for band in BANDS}, base, length)
    minus = run(f"{name}_minus", {band: -value for band, value in amplitudes.items()},
                {band: phase for band in BANDS}, base, length)
    if plus is None or minus is None:
        raise SystemExit(f"{name}: differential pair did not both run")
    first, second = measure(plus), measure(minus)
    return {label: (first[label] - second[label]) / 2.0 for label in CHANNELS}


def main() -> int:
    base = json.loads(BASE.read_text(encoding="utf-8"))
    base.pop("initial_state", None)
    for body in base.get("topology", {}).get("bodies", []):
        if body.get("kind") == "axlebox" and isinstance(body.get("axle"), int):
            body["axle"] = body["axle"] - 1
    base["run"]["duration_s"] = DURATION_S
    length = DURATION_S * SPEED + 30.0
    rng = np.random.default_rng(20261025)

    print(f"bands {BANDS} m -> " + ", ".join(f"{SPEED / band:.2f} Hz" for band in BANDS)
          + f"; {DURATION_S} s = {DURATION_S * SPEED:.0f} m of travel; "
          + f"{REALISATIONS} phases per band", flush=True)

    started = time.perf_counter()
    columns: dict[float, dict[str, np.ndarray]] = {}
    nuisances: dict[float, dict[str, np.ndarray]] = {}
    residuals: dict[float, dict[str, np.ndarray]] = {}
    cache = WORK / "columns.json"
    cached = None
    if cache.exists():
        try:
            payload = json.loads(cache.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            payload = None
        if (payload and payload.get("bands") == list(BANDS)
                and payload.get("amplitude") == AMPLITUDE_M
                and payload.get("realisations") == REALISATIONS
                and payload.get("duration_s") == DURATION_S):
            cached = payload
            print("reusing the column runs already on disk (16 simulations not repeated)",
                  flush=True)
    for band in BANDS:
        if cached is not None:
            entry = cached["columns"][str(band)]
            columns[band] = _decode(entry["response"])
            nuisances[band] = _decode(entry["nuisance"])
            residuals[band] = _decode(entry["residual"])
        else:
            columns[band], nuisances[band], residuals[band] = column(band, base, length, rng)
        print(f"\nband {band} m (nuisance |B| is the case's own geometry, |A| the probe answer):")
        for label, spec in CHANNELS.items():
            unit = "m/s^2" if "acc" in spec[0][0] else "m"
            print(f"  {label:2s} |A| = "
                  + "  ".join(f"{abs(value):10.4f}" for value in columns[band][label])
                  + f"   |B| = "
                  + "  ".join(f"{abs(value):10.1f}" for value in nuisances[band][label])
                  + f"   resid = "
                  + "  ".join(f"{abs(value):8.2f}" for value in residuals[band][label])
                  + f"   ({unit})", flush=True)
    if cached is None:
        cache.write_text(json.dumps({
            "bands": list(BANDS), "amplitude": AMPLITUDE_M,
            "realisations": REALISATIONS, "duration_s": DURATION_S,
            "columns": {str(band): {"response": _encode(columns[band]),
                                    "nuisance": _encode(nuisances[band]),
                                    "residual": _encode(residuals[band])}
                        for band in BANDS}}, indent=2), encoding="utf-8")
    print(f"\n{len(ELAPSED)} runs in {time.perf_counter() - started:.0f} s "
          f"(mean {np.mean(ELAPSED):.1f} s)" if ELAPSED else "", flush=True)

    blocks = {label: np.column_stack([columns[band][label] for band in BANDS])
              for label in CHANNELS}

    truth = SHAPE * AMPLITUDE_M
    phase = float(rng.uniform(0.0, 2.0 * np.pi))
    target_blocks = differential("target", dict(zip(BANDS, truth)), phase, base, length)

    blind = BLIND_SHAPE * AMPLITUDE_M
    blind_phase = float(rng.uniform(0.0, 2.0 * np.pi))
    blind_blocks = differential("blind", dict(zip(BANDS, blind)), blind_phase, base, length)

    print("\n             estimator   rows  cond      calibration  closure   blind     band errors")
    rows_out = []
    closure_of: dict[str, float] = {}
    for name, channels in VARIANTS:
        matrix = assemble(blocks, channels)
        measured = stack_measured(target_blocks, channels)
        for balanced in (False, True):
            label = "balanced" if balanced else "raw"
            recovered = solve(matrix, measured, balanced=balanced)
            calibration = magnitude_error(recovered, truth)
            closure_blocks = differential(f"closure_{name}_{label}",
                                          dict(zip(BANDS, np.abs(recovered))), phase, base, length)
            closure = float(np.linalg.norm(
                np.abs(stack_measured(closure_blocks, ("V",)))
                - np.abs(stack_measured(target_blocks, ("V",))))
                / np.linalg.norm(np.abs(stack_measured(target_blocks, ("V",)))))
            blind_recovered = solve(matrix, stack_measured(blind_blocks, channels),
                                    balanced=balanced)
            blind_error = magnitude_error(blind_recovered, blind)
            if not balanced:
                closure_of[name] = closure
            cond_matrix = balance(matrix, measured)[0] if balanced else matrix
            cond = float(np.linalg.cond(cond_matrix))
            errors = per_band_error(recovered, truth)
            rows_out.append((name, label, len(channels) * len(BANDS), cond, calibration,
                             closure, blind_error, recovered, errors))
            print(f"  {name:4s}  {label:10s} {len(channels) * len(BANDS):4d}  {cond:9.2f}  "
                  f"{calibration:11.1%}  {closure:7.2%}  {blind_error:8.1%}   "
                  + "  ".join(f"{value:+.1%}" for value in errors), flush=True)
    print("  truth  (mm)                                                                     "
          + "  ".join(f"{value * 1000:+.4f}" for value in truth))

    baseline = next(row for row in rows_out if row[0] == "V" and row[1] == "balanced")
    print("\njudgement (verdict uses the balanced estimator; closure compared against V)")
    for name, label, _n, _c, calibration, closure, blind, recovered, errors in rows_out:
        if label != "balanced":
            continue
        notes = ["band errors " + " / ".join(f"{value:+.1%}" for value in errors)]
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
    ratio = np.linalg.norm(blocks["D"], axis=1)
    print("\n  prediction was: D transfer ratio ~1.0 m/m and D alone < 10 %.")
    print("  measured D transfer ratio: "
          + "  ".join(f"{abs(value):8.4f}" for value in ratio)
          + " m/m over bands " + ", ".join(f"{band:g} m" for band in BANDS))
    print("  (|B| >> |A| means these bands are dominated by the case geometry; read the residuals)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
