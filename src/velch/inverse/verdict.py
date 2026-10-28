"""One auditable verdict per inversion attempt: every layer's outcome, and the status it earns.

The reason this module exists rather than a paragraph in a document: a project-wide rule here is that
``measurement_validation_status`` may only be written by the acceptance layer, and that means it cannot be
a field somebody sets.  It is *derived* from the layer results by the rule below, so a script that has not
run the acceptance layer physically cannot claim it.

The layering follows the review that set the goal (L0 data admission, L1 registration, L2 calibration,
L3 inversion, L4 uncertainty, L5 acceptance).  Each layer reports ``passed`` / ``failed`` / ``skipped`` with
its own metrics; the verdict then states what may be claimed and -- when something failed -- which
degradation path was taken, because "the number is lower" and "the physics is wrong" are different answers
and only the verdict can keep them apart.
"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field
from pathlib import Path

LAYERS = ("L0_admission", "L1_registration", "L2_calibration", "L3_inversion", "L4_uncertainty",
          "L5_acceptance")
PASSED = "passed"
FAILED = "failed"
SKIPPED = "skipped"
STATUSES = (PASSED, FAILED, SKIPPED)

#: The only values ``measurement_validation_status`` may take, and what each one licenses.
STATUS_MEANINGS = {
    "not_evaluated": "no acceptance layer has run; nothing about the measurement may be claimed",
    "detection_only": "a detector reproduces the recorded sections, but no amplitude or profile claim holds",
    "consistent_with_recorded_section": "the inverted result agrees with a recorded section of track",
}
MEASUREMENT_STATUSES = tuple(STATUS_MEANINGS)


class VerdictError(ValueError):
    """Raised when a layer result or a verdict cannot be assembled."""


#: What a calibrated operator is valid *for*.
#:
#: Round 195 measured |H_tone / H_record| = 1.14-1.78 (that is 1.2-5.0 dB) between a 24-harmonic random
#: record and a pure tone at the same rms, and an eight-fold tone amplitude change moved |H| by 0.17 %.
#: So the operator is **class-calibrated**: an amplitude number means nothing without the excitation class
#: it was calibrated on, and "within 2 dB" without one is not a claim.
CALIBRATION_CLASS_FIELDS = ("harmonic_count", "band_edges_m", "rms_um", "crest_factor")

#: Metric keys that constitute an amplitude claim on a band.
AMPLITUDE_CLAIM_KEYS = ("band_amplitudes_um", "band_hit_rate", "band_errors_db")


def _is_blank(value) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, (list, tuple)):
        return not value
    return False


def calibration_class(*, harmonic_count, band_edges_m, rms_um, crest_factor) -> dict:
    """Assemble the class declaration for a calibrated operator, refusing anything incomplete."""
    values = {"harmonic_count": harmonic_count, "band_edges_m": band_edges_m,
              "rms_um": rms_um, "crest_factor": crest_factor}
    missing = [key for key, value in values.items() if _is_blank(value)]
    if missing:
        raise VerdictError(f"a calibration class needs {missing}; got {values}")
    if float(rms_um) <= 0.0:
        raise VerdictError(f"a calibration class needs a positive rms, got {rms_um}")
    if len(band_edges_m) != 2 or float(band_edges_m[0]) >= float(band_edges_m[1]):
        raise VerdictError(f"band_edges_m must be an increasing pair, got {band_edges_m}")
    return {"harmonic_count": int(harmonic_count),
            "band_edges_m": [float(band_edges_m[0]), float(band_edges_m[1])],
            "rms_um": float(rms_um), "crest_factor": float(crest_factor)}


@dataclass
class LayerResult:
    name: str
    status: str
    metrics: dict = field(default_factory=dict)
    notes: str = ""
    evidence: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.name not in LAYERS:
            raise VerdictError(f"unknown layer {self.name!r}: layers are {list(LAYERS)}")
        if self.status not in STATUSES:
            raise VerdictError(f"unknown status {self.status!r}: statuses are {list(STATUSES)}")
        if self.status == FAILED and not self.notes:
            raise VerdictError(f"layer {self.name} failed without saying why")
        if self.status != SKIPPED and not self.metrics:
            # A layer that "passed" with no numbers is the failure mode this whole project keeps hitting.
            raise VerdictError(f"layer {self.name} reports {self.status} but carries no metrics")
        claims = [key for key in AMPLITUDE_CLAIM_KEYS if key in self.metrics]
        if claims and self.status == PASSED:
            declared = self.metrics.get("calibration_class")
            missing = [name for name in CALIBRATION_CLASS_FIELDS
                       if not isinstance(declared, dict) or _is_blank(declared.get(name))]
            if missing:
                raise VerdictError(
                    f"layer {self.name} claims a band amplitude ({', '.join(claims)}) without a "
                    f"declared calibration class; missing {missing}.  A calibrated operator is only "
                    "valid inside the excitation class it was calibrated on: a 24-harmonic record and a "
                    "pure tone at the same rms differ by 1.2-5.0 dB per band, so an undeclared "
                    "'within 2 dB' is not a claim.")

    def as_dict(self) -> dict:
        return {"name": self.name, "status": self.status, "metrics": _plain(self.metrics),
                "notes": self.notes, "evidence": list(self.evidence)}


def _plain(value):
    """Make a metrics tree JSON-serialisable without silently stringifying numbers."""
    import numpy as np

    if isinstance(value, dict):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if isinstance(value, np.ndarray):
        return _plain(value.tolist())
    return value


@dataclass
class Verdict:
    record: str
    layers: list[LayerResult] = field(default_factory=list)
    physics_validation_status: str = "unvalidated_against_measurement_or_Simpack"
    degradation: list[str] = field(default_factory=list)
    version: str = ""

    def add(self, result: LayerResult) -> None:
        for existing in self.layers:
            if existing.name == result.name:
                raise VerdictError(f"layer {result.name} reported twice")
        self.layers.append(result)
        self.layers.sort(key=lambda item: LAYERS.index(item.name))

    def layer(self, name: str) -> LayerResult | None:
        for result in self.layers:
            if result.name == name:
                return result
        return None

    @property
    def measurement_validation_status(self) -> str:
        """Derived, never set: this is the rule the goal's first criterion asked for."""
        acceptance = self.layer("L5_acceptance")
        if acceptance is None or acceptance.status != PASSED:
            # A failed acceptance layer still licenses the weaker detection claim when it did find the
            # sections -- it bound the same layer twice under two names before this.
            if acceptance is not None and acceptance.status == FAILED and acceptance.metrics.get("detected"):
                return "detection_only"
            return "not_evaluated"
        if acceptance.metrics.get("consistent_with_recorded_section") is True:
            return "consistent_with_recorded_section"
        return "not_evaluated"

    def as_dict(self) -> dict:
        return {
            "version": self.version,
            "record": self.record,
            "layers": [result.as_dict() for result in self.layers],
            "measurement_validation_status": self.measurement_validation_status,
            "measurement_validation_meaning": STATUS_MEANINGS[self.measurement_validation_status],
            "physics_validation_status": self.physics_validation_status,
            "degradation": list(self.degradation),
        }

    def write(self, path: str | Path) -> Path:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(self.as_dict(), indent=1), encoding="utf-8")
        return target


def write_table(path: str | Path, rows: list[dict], columns: list[str]) -> Path:
    """Write one of the two flat tables the acceptance layer must produce."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in columns})
    return target
