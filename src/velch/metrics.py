"""Standard turnout / vehicle assessment indices from a saved run.

The solver writes one row per output sample with, for every rail contact,
``normal_n`` (the vertical wheel/rail force used as P) and ``fy_n`` (the lateral
force).  This module turns those into the indices a Chinese railway dynamics
report is actually judged on:

* 脱轨系数 ``Q/P = |fy| / P``                     limit 0.80 (GB/T 5599, 客车)
* 轮重减载率 ``ΔP/P̄``  with ``P̄ = (P_L + P_R)/2``  limit 0.60
* 轮轴横向力 ``H = |fy_L + fy_R|``                 limit ``10 + P0/3`` kN (P0 静轴重 kN)

Nothing here changes a run; it only reads ``history.csv``.  A run directory
(containing ``history.csv``) or the CSV itself is accepted.
"""

from __future__ import annotations

import csv
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable


class AssessmentError(ValueError):
    """Raised when the history cannot be assessed."""


@dataclass(frozen=True)
class AssessmentLimits:
    """Acceptance limits; defaults follow GB/T 5599 for passenger stock."""

    derailment_coefficient_max: float = 0.80
    wheel_load_reduction_max: float = 0.60
    lateral_force_base_n: float = 10.0e3
    lateral_force_axle_load_divisor: float = 3.0

    def lateral_force_limit_n(self, static_axle_load_n: float) -> float:
        return self.lateral_force_base_n + static_axle_load_n / self.lateral_force_axle_load_divisor


@dataclass
class AxleAssessment:
    axle_index: int
    samples: int
    normal_left_min_n: float
    normal_left_max_n: float
    normal_right_min_n: float
    normal_right_max_n: float
    derailment_coefficient: float
    derailment_side: str
    wheel_load_reduction: float
    lateral_force_n: float
    contact_lost_samples: int

    def as_dict(self) -> dict[str, object]:
        return {
            "axle_index": self.axle_index,
            "samples": self.samples,
            "normal_left_min_n": self.normal_left_min_n,
            "normal_left_max_n": self.normal_left_max_n,
            "normal_right_min_n": self.normal_right_min_n,
            "normal_right_max_n": self.normal_right_max_n,
            "derailment_coefficient": self.derailment_coefficient,
            "derailment_side": self.derailment_side,
            "wheel_load_reduction": self.wheel_load_reduction,
            "lateral_force_n": self.lateral_force_n,
            "contact_lost_samples": self.contact_lost_samples,
        }


@dataclass
class Assessment:
    history: str
    samples: int
    axles: list[AxleAssessment] = field(default_factory=list)
    limits: AssessmentLimits = field(default_factory=AssessmentLimits)
    static_axle_load_n: float = 0.0

    @property
    def derailment_coefficient(self) -> float:
        return max((a.derailment_coefficient for a in self.axles), default=0.0)

    @property
    def wheel_load_reduction(self) -> float:
        return max((a.wheel_load_reduction for a in self.axles), default=0.0)

    @property
    def lateral_force_n(self) -> float:
        return max((a.lateral_force_n for a in self.axles), default=0.0)

    def verdict(self, static_axle_load_n: float) -> dict[str, object]:
        limit_h = self.limits.lateral_force_limit_n(static_axle_load_n)
        checks = {
            "derailment_coefficient": (self.derailment_coefficient,
                                       self.limits.derailment_coefficient_max),
            "wheel_load_reduction": (self.wheel_load_reduction,
                                     self.limits.wheel_load_reduction_max),
            "axle_lateral_force_n": (self.lateral_force_n, limit_h),
        }
        return {
            "static_axle_load_n": static_axle_load_n,
            "checks": {name: {"value": value, "limit": limit, "pass": value <= limit}
                       for name, (value, limit) in checks.items()},
            "pass": all(value <= limit for value, limit in checks.values()),
        }

    def as_dict(self, static_axle_load_n: float) -> dict[str, object]:
        return {
            "history": self.history,
            "samples": self.samples,
            "limits": {
                "derailment_coefficient_max": self.limits.derailment_coefficient_max,
                "wheel_load_reduction_max": self.limits.wheel_load_reduction_max,
                "lateral_force_limit_n":
                    self.limits.lateral_force_limit_n(static_axle_load_n),
                "source": "GB/T 5599 passenger limits; lateral axle force 10 + P0/3 (kN)",
            },
            "axles": [a.as_dict() for a in self.axles],
            "maximum": {
                "derailment_coefficient": self.derailment_coefficient,
                "wheel_load_reduction": self.wheel_load_reduction,
                "axle_lateral_force_n": self.lateral_force_n,
            },
            "verdict": self.verdict(static_axle_load_n),
        }


def _resolve_history(path: Path) -> Path:
    resolved = path if path.suffix.lower() == ".csv" else path / "history.csv"
    if not resolved.is_file():
        raise AssessmentError(f"history not found: {resolved}")
    return resolved


def _columns(header: Iterable[str]) -> dict[str, int]:
    return {name: index for index, name in enumerate(header)}


def assess_history(path: str | Path, *, static_axle_load_n: float | None = None,
                   limits: AssessmentLimits | None = None) -> Assessment:
    """Read a saved run and compute the standard indices.

    ``static_axle_load_n`` only affects the lateral-force limit; when omitted the
    mean measured axle load of the run is used, which is the honest choice when
    the case carries no explicit static reference.
    """

    history = _resolve_history(Path(path))
    with history.open(newline="", encoding="utf-8") as handle:
        reader = csv.reader(handle)
        try:
            header = next(reader)
        except StopIteration as exc:  # pragma: no cover - empty file
            raise AssessmentError(f"empty history: {history}") from exc
        index = _columns(header)
        needed = {"axle_left_normal", "axle_right_normal", "axle_left_fy", "axle_right_fy"}
        found: dict[int, dict[str, int]] = {}
        for axle in range(1, 9):
            keys = {
                "axle_left_normal": f"axle{axle}_left_normal_n",
                "axle_right_normal": f"axle{axle}_right_normal_n",
                "axle_left_fy": f"axle{axle}_left_fy_n",
                "axle_right_fy": f"axle{axle}_right_fy_n",
                "axle_right_active": f"axle{axle}_right_active",
                "axle_left_active": f"axle{axle}_left_active",
            }
            if all(column in index for column in keys.values()):
                found[axle] = {key: index[column] for key, column in keys.items()}
            elif axle == 1:
                missing = sorted(set(keys) - {k for k, c in keys.items() if c in index})
                raise AssessmentError(
                    f"history lacks force columns for axle 1: {', '.join(missing)}")
        if not found:
            raise AssessmentError(f"history has no per-axle force columns: {history}")

        rows: list[list[str]] = list(reader)

    if not rows:
        raise AssessmentError(f"history has no samples: {history}")

    def value(row: list[str], column: int) -> float:
        try:
            out = float(row[column])
        except (IndexError, ValueError) as exc:
            raise AssessmentError(f"non-numeric sample in {history.name}") from exc
        return out if math.isfinite(out) else 0.0

    axles: list[AxleAssessment] = []
    total_load = 0.0
    for axle, columns in sorted(found.items()):
        normal_left = [value(row, columns["axle_left_normal"]) for row in rows]
        normal_right = [value(row, columns["axle_right_normal"]) for row in rows]
        fy_left = [value(row, columns["axle_left_fy"]) for row in rows]
        fy_right = [value(row, columns["axle_right_fy"]) for row in rows]
        active_right = [value(row, columns["axle_right_active"]) for row in rows]
        active_left = [value(row, columns["axle_left_active"]) for row in rows]

        derailment = 0.0
        side = "none"
        reduction = 0.0
        lateral = 0.0
        for p_l, p_r, q_l, q_r in zip(normal_left, normal_right, fy_left, fy_right):
            if p_l > 1.0:
                ratio = abs(q_l) / p_l
                if ratio > derailment:
                    derailment, side = ratio, "left"
            if p_r > 1.0:
                ratio = abs(q_r) / p_r
                if ratio > derailment:
                    derailment, side = ratio, "right"
            mean = 0.5 * (p_l + p_r)
            if mean > 1.0:
                reduction = max(reduction, (mean - min(p_l, p_r)) / mean)
            lateral = max(lateral, abs(q_l + q_r))

        lost = sum(1 for a in active_left if a < 0.5) + sum(1 for a in active_right if a < 0.5)
        total_load += sum(normal_left) + sum(normal_right)
        axles.append(AxleAssessment(
            axle_index=axle,
            samples=len(rows),
            normal_left_min_n=min(normal_left),
            normal_left_max_n=max(normal_left),
            normal_right_min_n=min(normal_right),
            normal_right_max_n=max(normal_right),
            derailment_coefficient=derailment,
            derailment_side=side,
            wheel_load_reduction=reduction,
            lateral_force_n=lateral,
            contact_lost_samples=lost,
        ))

    if static_axle_load_n is not None and static_axle_load_n <= 0.0:
        raise AssessmentError("static_axle_load_n must be positive")
    if static_axle_load_n is None:
        # total_load sums every axle over every sample; the mean measured axle load
        # is that sum divided by (axles * samples).
        static_axle_load_n = total_load / (len(axles) * len(rows))
    return Assessment(history=str(history), samples=len(rows), axles=axles,
                      limits=limits or AssessmentLimits(),
                      static_axle_load_n=static_axle_load_n)


def mean_axle_load_n(history_path: str | Path) -> float:
    """Mean measured axle load over the whole run (N)."""

    return assess_history(history_path).static_axle_load_n


def format_assessment(assessment: Assessment, static_axle_load_n: float) -> str:
    """Human-readable table for the console."""

    lines = [
        f"history: {assessment.history}",
        f"samples: {assessment.samples}   static axle load: {static_axle_load_n:,.0f} N",
        "",
        f"{'axle':>4} {'P_L min':>9} {'P_L max':>9} {'P_R min':>9} {'P_R max':>9} "
        f"{'Q/P':>7} {'side':>6} {'dP/P':>7} {'H kN':>8} {'lost':>5}",
    ]
    for axle in assessment.axles:
        lines.append(
            f"{axle.axle_index:>4} {axle.normal_left_min_n/1e3:>9.2f} {axle.normal_left_max_n/1e3:>9.2f} "
            f"{axle.normal_right_min_n/1e3:>9.2f} {axle.normal_right_max_n/1e3:>9.2f} "
            f"{axle.derailment_coefficient:>7.3f} {axle.derailment_side:>6} "
            f"{axle.wheel_load_reduction:>7.3f} {axle.lateral_force_n/1e3:>8.2f} "
            f"{axle.contact_lost_samples:>5}")
    verdict = assessment.verdict(static_axle_load_n)
    lines.append("")
    for name, check in verdict["checks"].items():
        mark = "PASS" if check["pass"] else "FAIL"
        lines.append(f"{mark}  {name:<26} {check['value']:.4g}  (limit {check['limit']:.4g})")
    lines.append("")
    lines.append("overall: " + ("PASS" if verdict["pass"] else "FAIL"))
    return "\n".join(lines)
