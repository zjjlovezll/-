"""Contracts shared by every tool: error codes, schemas, cost model, path jail."""

from __future__ import annotations

import math
import os
from enum import Enum
from pathlib import Path
from typing import Any, Iterable, Mapping

from velch.data_root import case_dir as _case_dir
from velch.ui.parameters import REGISTRY, ParameterError, apply_patch, registry_by_path

#: Every failure an agent can observe.  A closed set on purpose: a caller that has to
#: match on English prose is not an interface, and ``cli.py`` collapses gate misses and
#: malformed cases into the same exit code 2.
class ErrorCode(str, Enum):
    PARAMETER_REJECTED = "parameter_rejected"
    CASE_INVALID = "case_invalid"
    CASE_NOT_FOUND = "case_not_found"
    CASE_MUTATED = "case_mutated"
    JOB_NOT_FOUND = "job_not_found"
    JOB_NOT_FINISHED = "job_not_finished"
    ARTIFACT_INTEGRITY = "artifact_integrity"
    GATE_FAILED = "gate_failed"
    BUDGET_EXCEEDED = "budget_exceeded"
    SOLVER_ERROR = "solver_error"
    PATH_ESCAPE = "path_escape"
    TOOL_UNKNOWN = "tool_unknown"
    INVALID_ARGUMENT = "invalid_argument"


class AgentError(Exception):
    """A failure with a code, a human message and optional structured detail."""

    def __init__(self, code: ErrorCode, message: str, **detail: Any) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.detail = detail

    def as_dict(self) -> dict[str, Any]:
        return {"code": self.code.value, "message": self.message, "detail": self.detail}


# -- locations ---------------------------------------------------------------------

def repository_root() -> Path:
    """The Velch checkout root (``src/velch/agent/core.py`` -> four levels up)."""
    return Path(__file__).resolve().parents[3]


def case_root() -> Path:
    """Where the shipped cases live.

    ``VELCH_CASE_ROOT`` still wins (deployments point it at their own set); otherwise this is
    the shared answer from :mod:`velch.data_root`, so moving the corpus does not desynchronise
    the agent from the UI and the gates.
    """
    override = os.environ.get("VELCH_CASE_ROOT")
    if override:
        return Path(override).resolve()
    return _case_dir()


def agent_home() -> Path:
    """Agent state: derived cases, job directories, the revision ledger."""
    override = os.environ.get("VELCH_AGENT_HOME")
    home = Path(override).resolve() if override else repository_root() / ".agent"
    for name in ("variants", "jobs", "revisions"):
        (home / name).mkdir(parents=True, exist_ok=True)
    return home


def within_allowed(path: Path, roots: Iterable[Path]) -> Path:
    """Resolve ``path`` and refuse anything outside the allowed roots."""
    resolved = Path(path).expanduser().resolve()
    for root in roots:
        try:
            resolved.relative_to(Path(root).resolve())
        except ValueError:
            continue
        return resolved
    raise AgentError(ErrorCode.PATH_ESCAPE, f"{resolved} is outside the allowed roots",
                     allowed=[str(Path(root).resolve()) for root in roots])


# -- parameter contract ------------------------------------------------------------

#: The registry is the contract.  A tool may not accept a key the registry does not have,
#: and it may not accept ``a.b[]`` wildcards: ``parameters.py:302`` expands a bare ``[]``
#: over every element silently, which makes "soften the second layer" (a legal, common
#: ask) impossible to express and "soften every layer" easy to trigger by accident.
def parameter_schema() -> dict[str, Any]:
    """JSON Schema for a parameter patch, with the registry as the only key source."""
    return {
        "type": "array",
        "description": "Parameter edits. Paths come from velch.ui.parameters.REGISTRY; "
                       "values are SI and are range-checked before anything runs.",
        "items": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "enum": [spec.path for spec in REGISTRY],
                    "description": "Registry path. No '[]' wildcards are accepted.",
                },
                "value": {"type": "number", "description": "Value in the unit the registry states."},
            },
            "required": ["path", "value"],
            "additionalProperties": False,
        },
    }


#: ``run.*`` is not part of the parameter registry, yet the biggest cost lever lives
#: there (BDF + analytic Jacobian turns a 850 s run into 101 s).  Hiding it would make the
#: automation unable to reach performance; exposing it silently would let a caller change
#: physics without saying so, so every solver edit is echoed back with ``physics_changed``.
SOLVER_FIELDS: dict[str, tuple[type, float | None, float | None]] = {
    "duration_s": (float, 1e-6, 60.0),
    "x_start_m": (float, 0.0, 1000.0),
    "output_step_s": (float, 1e-6, 1e-1),
    "max_solver_step_s": (float, 1e-8, 1.0),
    "rtol": (float, 1e-12, 1e-1),
    "atol": (float, 1e-14, 1e-1),
    "maximum_penetration_m": (float, 1e-6, 1e-2),
    "maximum_abs_contact_slope": (float, 1e-3, 90.0),
}
SOLVER_CHOICES: dict[str, tuple[str | None, ...]] = {
    "method": ("DOP853", "Radau", "BDF"),
    "jacobian": (None, "sparse_fd", "analytic"),
}


def solver_schema() -> dict[str, Any]:
    properties: dict[str, Any] = {
        name: {"type": "number", "minimum": low, "maximum": high}
        for name, (_cast, low, high) in SOLVER_FIELDS.items()
    }
    for name, choices in SOLVER_CHOICES.items():
        properties[name] = {"enum": list(choices)}
    return {
        "type": "object",
        "description": "Solver settings (run block). Changing these changes the answer; "
                       "every edit is reported with physics_changed=true.",
        "properties": properties,
        "additionalProperties": False,
    }


def validate_solver_patch(raw: Mapping[str, Any]) -> dict[str, Any]:
    """Validate a ``run`` block edit; reject unknown keys and out-of-range values."""
    cleaned: dict[str, Any] = {}
    for name, value in raw.items():
        if name in SOLVER_CHOICES:
            if value not in SOLVER_CHOICES[name]:
                raise AgentError(ErrorCode.PARAMETER_REJECTED,
                                 f"run.{name} must be one of {SOLVER_CHOICES[name]}",
                                 field=f"run.{name}", value=value)
            cleaned[name] = value
            continue
        if name not in SOLVER_FIELDS:
            raise AgentError(ErrorCode.PARAMETER_REJECTED,
                             f"run.{name} is not an editable solver field",
                             field=f"run.{name}")
        _cast, low, high = SOLVER_FIELDS[name]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise AgentError(ErrorCode.PARAMETER_REJECTED,
                             f"run.{name} must be a number", field=f"run.{name}")
        number = float(value)
        if not math.isfinite(number):
            raise AgentError(ErrorCode.PARAMETER_REJECTED, f"run.{name} must be finite",
                             field=f"run.{name}")
        if (low is not None and number < low) or (high is not None and number > high):
            raise AgentError(ErrorCode.PARAMETER_REJECTED,
                             f"run.{name}={number} outside [{low}, {high}]",
                             field=f"run.{name}", minimum=low, maximum=high)
        cleaned[name] = number
    return cleaned


def normalise_patch(patch: Any) -> dict[str, float]:
    """Accept ``[{"path": ..., "value": ...}, ...]`` and return ``{path: value}``."""
    if patch is None:
        return {}
    if isinstance(patch, Mapping):
        items = [{"path": key, "value": value} for key, value in patch.items()]
    elif isinstance(patch, (list, tuple)):
        items = list(patch)
    else:
        raise AgentError(ErrorCode.INVALID_ARGUMENT,
                         "patch must be an object or a list of {path, value}")
    cleaned: dict[str, float] = {}
    table = registry_by_path()
    for item in items:
        if not isinstance(item, Mapping):
            raise AgentError(ErrorCode.INVALID_ARGUMENT, "each patch item must be an object")
        path = item.get("path")
        if not isinstance(path, str):
            raise AgentError(ErrorCode.INVALID_ARGUMENT, "patch item needs a string path")
        if "[]" in path:
            raise AgentError(
                ErrorCode.PARAMETER_REJECTED,
                "wildcard '[]' is not accepted: it expands over every element silently, so "
                "an edit meant for one layer hits all of them. Name the element explicitly.",
                field=path)
        if path not in table:
            raise AgentError(ErrorCode.PARAMETER_REJECTED,
                             f"unknown parameter {path!r}", field=path)
        if path in cleaned:
            raise AgentError(ErrorCode.INVALID_ARGUMENT, f"{path} appears twice in the patch",
                             field=path)
        value = item.get("value")
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise AgentError(ErrorCode.PARAMETER_REJECTED,
                             f"{path}: value must be a number", field=path)
        cleaned[path] = float(value)
    return cleaned


def apply_parameter_patch(raw: Mapping[str, Any], patch: Mapping[str, float]) -> dict[str, Any]:
    """Delegate to the UI's ``apply_patch`` so there is one write path, not two."""
    try:
        return apply_patch(raw, patch)
    except ParameterError as error:
        raise AgentError(ErrorCode.PARAMETER_REJECTED, str(error)) from error


# -- cost model --------------------------------------------------------------------

#: Measured on this machine.  Two anchors: the 1.2 s assembly took 331 949 nfev / 2 400
#: output samples (DOP853, ~850 s) and 110 461 (BDF + analytic, ~141 s); the 0.05 s frog
#: window took 11 038 / 100.  So cost is per output sample, and it varies with the case: the
#: assembly pays ~848 s by this formula against ~850 s measured, while the short frog window
#: is over-predicted by roughly 2x.  Over-predicting is the safe direction for a budget check
#: -- refusing a job that would have fit costs a retry, accepting one that will not fit costs
#: the whole wall clock -- but the band is wide on purpose and the true wall clock is reported
#: when the job finishes.
WALL_PER_NFEV_S = 2.56e-3
NFEV_PER_STEP = {"DOP853": 138.0, "Radau": 30.0, "BDF": 46.0}
BAND = (0.5, 2.2)


def predict_wall_s(duration_s: float, output_step_s: float, method: str) -> dict[str, float]:
    """Estimate the wall clock of a run: ``(point, low, high)``."""
    steps = max(1.0, float(duration_s) / max(1e-9, float(output_step_s)))
    per_step = NFEV_PER_STEP.get(method, NFEV_PER_STEP["DOP853"])
    point = steps * per_step * WALL_PER_NFEV_S
    return {"point": point, "low": point * BAND[0], "high": point * BAND[1],
            "basis": f"{steps:.0f} output samples x {per_step} nfev x {WALL_PER_NFEV_S:.3e} s"}


def describe_parameters() -> list[dict[str, Any]]:
    """The registry as rows: what a caller may edit, in what unit, within what range."""
    return [
        {
            "path": spec.path,
            "label_zh": spec.label_zh,
            "unit": spec.unit,
            "group": spec.group,
            "minimum": spec.minimum,
            "maximum": spec.maximum,
            "note": spec.note,
        }
        for spec in REGISTRY
    ]
