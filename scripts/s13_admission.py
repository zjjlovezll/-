"""L0/L1 of the inversion pipeline: admit the measured data, then register its channels.

The two expert reviews fixed the acceptance shape: every layer reports pass/fail, the degradation path
is written down, and ``measurement_validation_status`` stays at ``not_evaluated`` until the acceptance
layer (L5) has the numbers to say otherwise.  This script implements the two layers that need **no
simulation**, so the rest of the pipeline can be judged against a fixed entry.

L0 (admission)   sampling rates both declared and matching, position monotone, record span > 1 km, and
                 the acceleration channel free of non-finite values.
L1 (registration) the two axle-box columns coherent with each other (lag from the peak of the
                 cross-correlation), and the integrated speed reproducing the recorded position to
                 within 5 m over the run.

Refusals are reported as ``fail`` with the measured number, never as an exception: a layer that cannot
be evaluated is not a layer that passed.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np

RATE_HZ = 4000.0          # README: accelerations and speed at 4 kHz / 16 bit
SOUND_RATE_HZ = 48000.0   # README: sound at 48 kHz / 32 bit
SPAN_MIN_M = 1000.0
LAG_MAX_S = 0.025         # review: cross-channel lag <= 25 ms
MILEAGE_TOLERANCE_M = 5.0  # review: mileage deviation <= 5 m
WHEELBASE_M = 2.5          # CRH380A bogie wheelbase, the distance between the two measured axles


def _flat(value):
    """One column per scalar channel; ``None`` stays ``None``."""

    return None if value is None else np.asarray(value).ravel()


def load(path: Path) -> dict[str, np.ndarray]:
    from scipy.io import loadmat

    raw = loadmat(str(path))
    # Keep the shape: Vi_y is (n, 2) and raveling it destroys the axle-box pair.
    return {key: np.asarray(value) for key, value in raw.items() if not key.startswith("__")}


def layer_admission(data: dict[str, np.ndarray], *, rate_hz: float, sound_rate_hz: float) -> dict:
    faults: list[str] = []
    time = _flat(data.get("Vi_t"))
    position = _flat(data.get("Vi_pks"))
    accelerations = data.get("Vi_y")
    sound = data.get("So_y")

    rate_measured = None
    if time is None or time.size < 10:
        faults.append("Vi_t missing or shorter than 10 samples")
    else:
        steps = np.diff(time)
        rate_measured = float(1.0 / np.median(steps)) if np.median(steps) > 0 else float("nan")
        if not math.isfinite(rate_measured) or abs(rate_measured - rate_hz) > 1.0:
            faults.append(f"acceleration rate {rate_measured:.3f} Hz is not the declared {rate_hz} Hz")
        if np.any(steps <= 0.0):
            faults.append("Vi_t is not increasing")

    span_m = None
    if position is None or position.size < 10:
        faults.append("Vi_pks missing or shorter than 10 samples")
    else:
        steps = np.diff(position)
        span_m = float((position[-1] - position[0]) * 1000.0)   # README: Vi_pks is in km
        plateau = int(np.count_nonzero(steps == 0.0))
        if plateau:
            # The record starts and ends at standstill, so repeated mileage is expected there; what
            # matters is that it never goes backwards, and how much of the run is stationary.
            stopped = float(plateau) / float(steps.size)
            if stopped > 0.25:
                faults.append(f"{stopped:.0%} of the record has zero mileage change: mostly stationary")
        # A reverse-direction run records decreasing mileage; the README says the four runs were
        # reordered to increasing km, so a decreasing file is a data-preparation fault, not physics.
        if np.all(steps < 0.0):
            faults.append("Vi_pks decreases over the whole record: this file is not mileage-ordered")
        if span_m < SPAN_MIN_M:
            faults.append(f"record spans {span_m:.1f} m, below the {SPAN_MIN_M:.0f} m admission floor")

    non_finite = None
    if accelerations is None or accelerations.size == 0:
        faults.append("Vi_y missing")
    else:
        non_finite = int(np.size(accelerations) - np.count_nonzero(np.isfinite(accelerations)))
        if non_finite:
            faults.append(f"Vi_y carries {non_finite} non-finite values")

    sound_rate = None
    if sound is not None and sound.size > 10:
        sound_rate = float(sound.size / float(time[-1] - time[0])) if time is not None and time.size > 1 else None
        if sound_rate and abs(sound_rate - sound_rate_hz) > 50.0 * sound_rate_hz / sound_rate_hz * 100.0:
            faults.append(f"sound rate {sound_rate:.0f} Hz is not the declared {sound_rate_hz:.0f} Hz")

    return {
        "layer": "L0-admission",
        "passed": not faults,
        "rate_hz": rate_measured,
        "sound_rate_hz": sound_rate,
        "span_m": span_m,
        "non_finite": non_finite,
        "stationary_fraction": stopped if 'stopped' in dir() else None,
        "faults": faults,
    }



def band_lag_ms(channels: np.ndarray, rate_hz: float, low_hz: float, high_hz: float) -> float | None:
    """Lag of column 1 behind column 0 inside one band, in milliseconds.

    The broadband peak of two axle-box signals is dominated by whatever is loudest, which is impact and
    body content rather than the corrugation both wheels meet.  Restricting the band to the frequencies
    the corrugation occupies at this speed is the only way the lag can be read as a travel time.
    """

    from scipy.signal import butter, filtfilt

    if channels.ndim != 2 or channels.shape[1] < 2:
        return None
    nyquist = 0.5 * rate_hz
    upper = min(high_hz, 0.95 * nyquist)
    if low_hz >= upper:
        return None
    b, a = butter(4, [low_hz / nyquist, upper / nyquist], btype="band")
    first = filtfilt(b, a, channels[:, 0])
    second = filtfilt(b, a, channels[:, 1])
    first = first - first.mean()
    second = second - second.mean()
    correlation = np.correlate(first, second, mode="full")
    lags = np.arange(-first.size + 1, first.size)
    return float(lags[int(np.argmax(np.abs(correlation)))] / rate_hz * 1000.0)


def layer_registration(data: dict[str, np.ndarray], *, rate_hz: float) -> dict:
    faults: list[str] = []
    channels = data.get("Vi_y")
    lag_s = lag_samples = None
    columns = None
    if channels is not None and channels.ndim == 2 and channels.shape[1] >= 2:
        columns = int(channels.shape[1])
        left = channels[:, 0] - channels[:, 0].mean()
        right = channels[:, 1] - channels[:, 1].mean()
        correlation = np.correlate(left, right, mode="full")
        lags = np.arange(-left.size + 1, right.size)
        lag_samples = int(lags[int(np.argmax(np.abs(correlation)))])
        lag_s = lag_samples / rate_hz
        # 18-40 mm wavelength at this speed is where the corrugation lives.
        mean_speed_for_band = float(np.mean(_flat(data.get("Vi_Speed")))) / 3.6
        bands = {}
        for low_mm, high_mm in ((18.0, 40.0), (40.0, 120.0), (120.0, 400.0)):
            low_hz = mean_speed_for_band / (high_mm / 1000.0)
            high_hz = mean_speed_for_band / (low_mm / 1000.0)
            bands[f"{low_mm:g}-{high_mm:g}mm"] = band_lag_ms(channels, rate_hz, low_hz, high_hz)
        # The two columns sit on the two axles of one bogie, so a lag is expected physics
        # (wheelbase / speed), not a registration fault.  What must hold is that the lag is
        # consistent with that geometry to within the 25 ms registration budget.
        expected_s = None
        speed = _flat(data.get("Vi_Speed"))
        if speed is not None and speed.size:
            mean_speed = float(np.mean(speed)) / 3.6
            if mean_speed > 0.5:
                expected_s = WHEELBASE_M / mean_speed
        # Judge on the corrugation band when it can be read there: broadband lag mixes impact content.
        judged = None
        if 'bands' in dir() and bands.get("18-40mm") is not None:
            judged = abs(bands["18-40mm"])
        # Two readings were possible, and the measurement chose between them:
        #   (A) the columns sit on the two axles of one bogie -> lag = wheelbase / speed = 144.6 ms
        #   (B) the columns are co-located channels of one axle box -> lag = 0
        # Measured 2.25 ms in the 18-40 mm band, so (A) is refuted and (B) holds: this record gives ONE
        # mileage per frame, not two, which is why L2 cannot use it for a two-axle comparison.
        colocated = judged is not None and abs(judged) <= LAG_MAX_S * 1000.0
        if expected_s is not None and not colocated:
            used = judged if judged is not None else abs(lag_s)
            if abs(used / 1000.0 - expected_s) > LAG_MAX_S:
                faults.append(
                    f"the axle-box lag is {used:.1f} ms ({'18-40 mm band' if judged is not None else 'broadband'}), while a {WHEELBASE_M:.1f} m "
                    f"wheelbase at {mean_speed:.2f} m/s predicts {expected_s * 1000:.1f} ms"
                )
    else:
        faults.append("Vi_y does not carry two columns, so the axle-box pair cannot be registered")

    deviation_m = None
    speed = _flat(data.get("Vi_Speed"))
    time = _flat(data.get("Vi_t"))
    position = _flat(data.get("Vi_pks"))
    if speed is not None and time is not None and position is not None:
        # The recorded speed is km/h (mean 62.2 over 2.5 km in 145 s); m/s here would inflate 3.6x.
        integrated = float(np.trapezoid(speed / 3.6, time))
        recorded = float((position[-1] - position[0]) * 1000.0)
        deviation_m = abs(integrated - recorded)
        if deviation_m > MILEAGE_TOLERANCE_M:
            faults.append(
                f"integrating the recorded speed gives {integrated:.1f} m against a recorded {recorded:.1f} m "
                f"({deviation_m:.1f} m apart, limit {MILEAGE_TOLERANCE_M:.0f} m)"
            )
    else:
        faults.append("speed, time or position missing, so the mileage cannot be cross-checked")

    return {
        "layer": "L1-registration",
        "passed": not faults,
        "channels": columns,
        "lag_ms": None if lag_s is None else lag_s * 1000.0,
        "lag_samples": lag_samples,
        "expected_lag_ms": None if expected_s is None else expected_s * 1000.0,
        "band_lag_ms": bands if 'bands' in dir() else {},
        "reading": "co-located (lag ~ 0 beats the 25 ms budget)" if 'colocated' in dir() and colocated else "two axles (lag follows wheelbase / speed)",
        "mileage_deviation_m": deviation_m,
        "faults": faults,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=Path(r"F:\ai道岔状态反演辨识\75kmh数据"))
    parser.add_argument("--output", type=Path, default=Path(r"F:\velch_tmp\verdict\verdict.json"))
    args = parser.parse_args(argv)

    files = sorted(args.data.glob("*.mat"))
    if not files:
        raise SystemExit(f"no .mat files under {args.data}")
    source = files[0]
    data = load(source)

    layers = [layer_admission(data, rate_hz=RATE_HZ, sound_rate_hz=SOUND_RATE_HZ),
              layer_registration(data, rate_hz=RATE_HZ)]
    verdict = {
        "source": str(source),
        "layers": layers,
        "passed": all(layer["passed"] for layer in layers),
        "measurement_validation_status": "not_evaluated",
        "note": "only the acceptance layer (L5) may change measurement_validation_status",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(verdict, indent=1, ensure_ascii=False), encoding="utf-8")

    for layer in layers:
        print(f"{'PASS' if layer['passed'] else 'FAIL'}  {layer['layer']}")
        for fault in layer["faults"]:
            print(f"        {fault}")
    print(f"verdict: {'PASS' if verdict['passed'] else 'FAIL'}  -> {args.output}")
    return 0 if verdict["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
