"""Write a derived v2 case file, so a solver override stays reproducible.

Why a file and not an in-memory edit: ``save_vehicle_result`` snapshots the case bytes it was
handed and re-checks that hash at the end of the run.  Overriding ``run`` in memory would make
that snapshot describe settings the run never used — a manifest that looks auditable and is
not.  Writing the patched case next to the output keeps hash, snapshot and settings in
agreement by construction.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any


def absolutise_profile_paths(node: Any, base: Path) -> None:
    """Rewrite every relative ``"file"`` reference to an absolute path, in place.

    v2 cases reference some rail bodies relative to their own directory (the frog bodies use
    ``bodies/point_r07xxxxx.csv``), so a derived case written somewhere else must carry
    absolute references.  ``base`` must be the **resolved** directory of the original case.
    CWD is tried as a fallback for cases written with repo-relative paths.
    """
    base = Path(base).resolve()
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "file" and isinstance(value, str):
                candidate = Path(value)
                if not candidate.is_absolute():
                    for root in (base, Path.cwd()):
                        option = (root / candidate)
                        if option.exists():
                            candidate = option
                            break
                    else:
                        candidate = base / candidate
                node[key] = str(candidate)
            else:
                absolutise_profile_paths(value, base)
    elif isinstance(node, list):
        for item in node:
            absolutise_profile_paths(item, base)


def relative_profile_references(node: Any, base: Path) -> int:
    """Count relative ``"file"`` references (mirrors :func:`absolutise_profile_paths`)."""
    if isinstance(node, dict):
        total = 0
        for key, value in node.items():
            if key == "file" and isinstance(value, str):
                total += 0 if Path(value).is_absolute() else 1
            else:
                total += relative_profile_references(value, base)
        return total
    if isinstance(node, list):
        return sum(relative_profile_references(item, base) for item in node)
    return 0


def write_derived_case(source: Path, destination: Path, *, run: dict[str, Any] | None = None,
                       overwrite: bool = False) -> Path:
    """Copy ``source`` to ``destination`` with ``run`` replaced and profiles made absolute.

    The source file is never modified: it is read, patched in memory and written elsewhere.
    Returns the destination path.
    """
    source = Path(source).resolve()
    destination = Path(destination)
    if destination.resolve() == source:
        raise ValueError("refusing to overwrite the source case; pick another destination")
    if destination.exists() and not overwrite:
        raise ValueError(f"derived case already exists: {destination}")
    payload = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"case must be a JSON object: {source}")
    if run is not None:
        current = payload.get("run")
        merged = dict(current) if isinstance(current, dict) else {}
        merged.update(run)
        payload["run"] = merged
    absolutise_profile_paths(payload, source.parent)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                           encoding="utf-8")
    return destination


def solver_override(declared: dict[str, Any], *, fast: bool = False,
                    method: str | None = None, jacobian: str | None = None,
                    rtol: float | None = None, atol: float | None = None,
                    max_solver_step_s: float | None = None) -> dict[str, Any]:
    """Build the ``run`` patch for a solver override, with the fast preset as the base.

    ``fast`` is the measured 11x preset (``BDF`` + analytic Jacobian + ``rtol=1e-4`` +
    ``max_solver_step_s=1e-3``); every explicit argument wins over it.  Only changed keys are
    returned, so the derived case still shows what the parent declared for everything else.
    Validation happens in :class:`velch.model.RunSettings` once the case is loaded.
    """
    merged = dict(declared)
    if fast:
        merged.update({"method": "BDF", "jacobian": "analytic", "rtol": 1.0e-4,
                       "max_solver_step_s": 1.0e-3})
    if method is not None:
        merged["method"] = method
    if jacobian is not None:
        merged["jacobian"] = None if jacobian in ("none", "None") else jacobian
    if rtol is not None:
        merged["rtol"] = float(rtol)
    if atol is not None:
        merged["atol"] = float(atol)
    if max_solver_step_s is not None:
        merged["max_solver_step_s"] = float(max_solver_step_s)
    for name, value in (("rtol", merged.get("rtol")), ("atol", merged.get("atol")),
                        ("max_solver_step_s", merged.get("max_solver_step_s"))):
        if value is not None and (not math.isfinite(float(value)) or float(value) <= 0.0):
            raise ValueError(f"{name} must be a positive finite number")
    return {name: value for name, value in merged.items() if declared.get(name) != value}
