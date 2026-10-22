"""Case parameters that are allowed to move during identification.

The forward solver only ever sees a frozen :class:`velch.vehicle.VehicleCase` whose
``case_sha256`` identifies exactly the numbers it ran with. Identification therefore
must not mutate a case: it holds a *spec* (the on-disk case plus the parameters under
study) and resolves a fresh case for every trial vector. That keeps every existing
run reproducible and makes each trial's provenance self-describing.

    spec = CaseSpec.from_path("case.json", (
        ParameterSpec.of("support_k_z", ("rail_templates", 0, "support", "k_z_n_m")),
        ParameterSpec.of("contact_r_star", ("contact", "effective_radius_m")),
    ))
    case = spec.resolve((0.1, -0.2))      # +10 % support stiffness, -20 % radius
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Sequence

from ..vehicle import VehicleCase, load_vehicle_case


class SpecError(ValueError):
    """A case spec or parameter vector is inconsistent."""


@dataclass(frozen=True)
class ParameterSpec:
    """One scalar case entry under study, parameterised multiplicatively.

    ``value(theta) = base * (1 + theta)``: a dimensionless unknown whose magnitude
    says "fraction of the nominal value". Multiplicative because every candidate
    here is a stiffness, a damping or a radius, all strictly positive, and because
    a unit step means the same thing for a 25 MN/m pad and a 380 MN/m ballast.
    """

    name: str
    path: tuple[str | int, ...]
    base: float | None = None
    bounds: tuple[float, float] = (-0.9, 9.0)
    note: str = ""

    def __post_init__(self) -> None:
        if not self.name:
            raise SpecError("parameter needs a name")
        if not self.path:
            raise SpecError(f"{self.name}: empty path")
        if self.base is not None and (not math.isfinite(self.base) or self.base <= 0.0):
            raise SpecError(f"{self.name}: base must be positive and finite, got {self.base}")
        low, high = self.bounds
        if not (math.isfinite(low) and math.isfinite(high) and low < high):
            raise SpecError(f"{self.name}: bounds must be finite and increasing")
        if low <= -1.0:
            raise SpecError(f"{self.name}: lower bound must keep the value positive")

    @classmethod
    def of(cls, name: str, path: Sequence[str | int], *, base: float | None = None,
           bounds: tuple[float, float] = (-0.9, 9.0), note: str = "") -> ParameterSpec:
        """A parameter whose base value is read from the case by :meth:`CaseSpec.from_path`."""

        return cls(name=name, path=tuple(path), base=base, bounds=bounds, note=note)

    def value(self, theta: float) -> float:
        if self.base is None:
            raise SpecError(f"{self.name}: base value was never resolved from a case")
        if not math.isfinite(theta):
            raise SpecError(f"{self.name}: theta must be finite")
        low, high = self.bounds
        if not low <= theta <= high:
            raise SpecError(f"{self.name}: theta {theta:g} outside bounds {self.bounds}")
        return self.base * (1.0 + theta)


@dataclass(frozen=True)
class CaseSpec:
    """An on-disk case together with the parameters that may move."""

    raw: dict[str, Any]
    source: Path
    parameters: tuple[ParameterSpec, ...]
    digest: str
    _absolutise: bool = field(default=True, repr=False)

    # ---------------------------------------------------------------- construction
    @classmethod
    def from_path(cls, path: str | Path,
                  parameters: Sequence[ParameterSpec] = ()) -> CaseSpec:
        target = Path(path).resolve(strict=True)
        raw = json.loads(target.read_bytes().decode("utf-8"))
        if raw.get("schema_version") != "velch-vehicle-v2":
            raise SpecError("unsupported vehicle case schema")
        resolved: list[ParameterSpec] = []
        for spec in parameters:
            base = spec.base
            if base is None:
                base = _lookup_positive(raw, spec.path, spec.name)
            resolved.append(ParameterSpec(name=spec.name, path=spec.path, base=base,
                                          bounds=spec.bounds, note=spec.note))
        names = [item.name for item in resolved]
        if len(set(names)) != len(names):
            raise SpecError(f"duplicate parameter names: {names}")
        digest = hashlib.sha256(target.read_bytes()).hexdigest()
        return cls(raw=raw, source=target, parameters=tuple(resolved), digest=digest)

    # --------------------------------------------------------------------- basics
    @property
    def names(self) -> tuple[str, ...]:
        return tuple(item.name for item in self.parameters)

    @property
    def nominal(self) -> tuple[float, ...]:
        return tuple(0.0 for _ in self.parameters)

    def values(self, theta: Sequence[float]) -> dict[str, float]:
        if len(theta) != len(self.parameters):
            raise SpecError(f"expected {len(self.parameters)} values, got {len(theta)}")
        return {spec.name: spec.value(float(value))
                for spec, value in zip(self.parameters, theta)}

    # -------------------------------------------------------------------- resolve
    def patched(self, theta: Sequence[float]) -> dict[str, Any]:
        """A deep copy of the case with the trial values written in."""

        if len(theta) != len(self.parameters):
            raise SpecError(f"expected {len(self.parameters)} values, got {len(theta)}")
        raw = copy.deepcopy(self.raw)
        for spec, value in zip(self.parameters, theta):
            _assign(raw, spec.path, spec.value(float(value)))
        raw["case_id"] = f"{self.raw.get('case_id', 'case')}@theta"
        raw["purpose_detail"] = (
            f"resolved from {self.source.name} (sha256 {self.digest[:12]}) at theta="
            + ",".join(f"{spec.name}:{float(value):+.4f}"
                       for spec, value in zip(self.parameters, theta)))
        return raw

    def resolve(self, theta: Sequence[float]) -> VehicleCase:
        """Write the patched case beside a temporary file and load it.

        Loading through the normal loader (rather than constructing ``VehicleCase``
        by hand) keeps profile parsing, hashing and validation on exactly the code
        path every other run uses; only the parameter values differ.
        """

        raw = self.patched(theta)
        _absolutise_assets(raw, self.source.parent)
        with tempfile.TemporaryDirectory(prefix="velch_case_") as folder:
            path = Path(folder) / "case.json"
            path.write_text(json.dumps(raw, indent=2, ensure_ascii=False) + "\n",
                            encoding="utf-8")
            case = load_vehicle_case(path)
        return case


def _lookup_positive(raw: dict[str, Any], path: tuple[str | int, ...], name: str) -> float:
    node: Any = raw
    for key in path:
        try:
            node = node[key]
        except (KeyError, IndexError, TypeError) as error:
            raise SpecError(f"{name}: path {path} not found in case") from error
    if isinstance(node, bool) or not isinstance(node, (int, float)):
        raise SpecError(f"{name}: path {path} is not a number")
    value = float(node)
    if not math.isfinite(value) or value <= 0.0:
        raise SpecError(f"{name}: base at {path} must be positive and finite, got {value}")
    return value


def _assign(raw: dict[str, Any], path: tuple[str | int, ...], value: float) -> None:
    node: Any = raw
    for key in path[:-1]:
        node = node[key]
    node[path[-1]] = value


def _absolutise_assets(raw: dict[str, Any], base: Path) -> None:
    """Make every profile path absolute so a relocated case still resolves."""

    def fix(spec: Any) -> None:
        if not isinstance(spec, dict):
            return
        if isinstance(spec.get("file"), str):
            candidate = Path(spec["file"])
            if not candidate.is_absolute():
                spec["file"] = str((base / candidate).resolve())
        # Stations carry their profile one level down: {"id": .., "profile": {...}}.
        fix(spec.get("profile"))

    for wheel in raw.get("wheels", ()):
        fix(wheel)
    for template in raw.get("rail_templates", ()):
        for station in template.get("stations", ()):
            fix(station)
        for body in template.get("bodies", ()):
            for station in body.get("stations", ()):
                fix(station)
