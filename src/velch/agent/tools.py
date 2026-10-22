"""The tool table: one declaration per capability, exported three ways.

A tool is declared exactly once, here, and the same declaration feeds the MCP ``tools/list``
response, the ``velch agent manifest`` command and the generated contract document.  Three
hand-maintained copies would drift, and a drifted schema is worse than no schema: the caller
believes it validated something.

Every response is an envelope ``{"ok": bool, "data": ..., "error": ...}``; ``ok=false``
always carries a closed-set ``code``.  One deliberate exception: a run that finished but
failed its numerical gates returns ``ok=true`` with ``data.status == "gate_failed"``, because
the artifacts exist and are readable; calling it an error would push the caller towards
retrying a run that already produced everything it is going to produce.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable, Mapping

from velch import __version__
from .cases import derive_case, list_cases, read_case, revisions
from .core import (
    AgentError,
    ErrorCode,
    case_root,
    describe_parameters,
    parameter_schema,
    predict_wall_s,
    solver_schema,
)
from .jobs import cancel_job, job_status, list_jobs, read_result, submit_run

Handler = Callable[..., dict[str, Any]]


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    input_schema: dict[str, Any]
    handler: Handler

    def as_mcp(self) -> dict[str, Any]:
        return {"name": self.name, "description": self.description, "inputSchema": self.input_schema}


def _schema(properties: Mapping[str, Any] | None = None, required: tuple[str, ...] = ()) -> dict[str, Any]:
    return {"type": "object", "properties": dict(properties or {}), "required": list(required),
            "additionalProperties": False}


_CASE = {"type": "string", "description": "Case JSON path (shipped case or derived variant)."}
_JOB = {"type": "string", "description": "Job id from submit_run."}


def _capabilities() -> dict[str, Any]:
    parameters = describe_parameters()
    return {
        "software": "Velch turnout dynamics",
        "version": __version__,
        "case_root": str(case_root()),
        "parameter_count": len(parameters),
        "parameter_groups": sorted({row["group"] for row in parameters}),
        "solvers": ["DOP853", "Radau", "BDF"],
        "jacobians": [None, "sparse_fd", "analytic"],
        "tools": [spec.name for spec in TOOLS],
        "limits": {
            "sync_wall_s": 60.0,
            "budget_wall_s": 900.0,
            "note": "A run longer than the budget is refused, not truncated. Jobs above "
                    "the sync limit return a job id instead of blocking the call.",
        },
        "guarantees": [
            "A shipped case is never modified: derive_case writes a new file.",
            "A result without manifest.json is refused, not returned.",
            "physics_changed=true means the run is not comparable with its parent.",
        ],
    }


def _predict(case: str) -> dict[str, Any]:
    payload = read_case(case)
    run = payload.get("run") or {}
    estimate = predict_wall_s(run.get("duration_s", 0.0), run.get("output_step_s", 5e-4),
                             run.get("method", "DOP853"))
    return {"case": payload["case_id"], "method": run.get("method"),
            "jacobian": run.get("jacobian"), "estimate": estimate}


TOOLS: tuple[ToolSpec, ...] = (
    ToolSpec("capabilities",
             "What this software can do: parameters, solvers, cases root, limits and guarantees. "
             "Call this first; it is cheap and needs no arguments.",
             _schema(), lambda **_: _capabilities()),
    ToolSpec("parameters",
             "The editable parameter registry: 72 paths with units and hard ranges. Every path "
             "here is accepted by derive_case; nothing else is.",
             _schema(), lambda **_: {"schema": parameter_schema(),
                                     "solver_schema": solver_schema(),
                                     "parameters": describe_parameters()}),
    ToolSpec("list_cases",
             "List the shipped cases with a one-line summary each.",
             _schema({"limit": {"type": "integer", "minimum": 1, "maximum": 200},
                      "pattern": {"type": "string"}}),
             lambda limit=40, pattern="case_*.json", **_: list_cases(limit=limit, pattern=pattern)),
    ToolSpec("read_case",
             "Read one case: its run block, contact law, whether support compliance is on, and "
             "the sha256 that identifies its bytes.",
             _schema({"case": _CASE}, ("case",)),
             lambda case, **_: read_case(case)),
    ToolSpec("derive_case",
             "Create a new case from a parent plus edits. This is the only write path: the "
             "parent is never touched, and the child is recorded in an append-only ledger.",
             _schema({"parent": _CASE,
                      "patch": {"type": "array", "items": {"type": "object"}},
                      "solver_patch": {"type": "object"},
                      "note": {"type": "string"}, "tag": {"type": "string"}}, ("parent",)),
             lambda parent, patch=None, solver_patch=None, note="", tag="", **_:
             derive_case(parent=parent, patch=patch, solver_patch=solver_patch, note=note, tag=tag)),
    ToolSpec("revisions",
             "The revision ledger: every derivation, oldest first, each line chained by hash.",
             _schema({"limit": {"type": "integer", "minimum": 1, "maximum": 500}}),
             lambda limit=50, **_: revisions(limit=limit)),
    ToolSpec("predict_run",
             "Estimated wall clock for a case before running it: point, low, high and the basis.",
             _schema({"case": _CASE}, ("case",)), lambda case, **_: _predict(case)),
    ToolSpec("submit_run",
             "Run a case. Short runs return the result; long runs return a job id to poll.",
             _schema({"case": _CASE, "workers": {"type": "integer", "minimum": 1, "maximum": 64},
                      "budget_s": {"type": "number", "minimum": 1.0, "maximum": 86400.0},
                      "background": {"type": "boolean"}}, ("case",)),
             lambda case, workers=1, budget_s=900.0, background=None, **_:
             submit_run(case_path=case, workers=workers, budget_s=budget_s, background=background)),
    ToolSpec("job_status", "Status of one job, derived from its files rather than a counter.",
             _schema({"job": _JOB}, ("job",)), lambda job, **_: job_status(job)),
    ToolSpec("list_jobs", "Recent jobs, newest first.",
             _schema({"limit": {"type": "integer", "minimum": 1, "maximum": 200}}),
             lambda limit=20, **_: list_jobs(limit=limit)),
    ToolSpec("cancel_job", "Stop a running job. A finished job is reported, not rewritten.",
             _schema({"job": _JOB}, ("job",)), lambda job, **_: cancel_job(job)),
    ToolSpec("read_result",
             "Artifacts and summary of a finished job. Refused when manifest.json is missing.",
             _schema({"job": _JOB}, ("job",)), lambda job, **_: read_result(job)),
)

_BY_NAME = {spec.name: spec for spec in TOOLS}


def manifest() -> dict[str, Any]:
    """The self-description, used by MCP tools/list and by ``velch agent manifest``."""
    return {"schema_version": "velch-agent-tools-v1", "name": "velch", "version": __version__,
            "tools": [spec.as_mcp() for spec in TOOLS]}


def call_tool(name: str, arguments: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Dispatch one call and always return an envelope; never raise at this boundary."""
    spec = _BY_NAME.get(name)
    if spec is None:
        return {"ok": False, "error": AgentError(
            ErrorCode.TOOL_UNKNOWN, f"no such tool: {name}", available=sorted(_BY_NAME)).as_dict()}
    try:
        data = spec.handler(**dict(arguments or {}))
    except AgentError as error:
        return {"ok": False, "error": error.as_dict()}
    except TypeError as error:  # wrong argument names or types from an over-eager caller
        return {"ok": False, "error": AgentError(ErrorCode.INVALID_ARGUMENT, str(error)).as_dict()}
    except Exception as error:  # never let an unexpected failure escape as a traceback
        return {"ok": False, "error": AgentError(
            ErrorCode.SOLVER_ERROR, f"{type(error).__name__}: {error}").as_dict()}
    return {"ok": True, "data": data}


def call_tool_json(payload: str) -> str:
    """Parse ``{"tool": name, "arguments": {...}}`` and answer with an envelope string."""
    try:
        request = json.loads(payload)
    except json.JSONDecodeError as error:
        return json.dumps({"ok": False, "error": AgentError(
            ErrorCode.INVALID_ARGUMENT, f"invalid JSON: {error}").as_dict()}, ensure_ascii=False)
    if not isinstance(request, dict) or "tool" not in request:
        return json.dumps({"ok": False, "error": AgentError(
            ErrorCode.INVALID_ARGUMENT, "expected {\"tool\": name, \"arguments\": {...}}").as_dict()},
            ensure_ascii=False)
    return json.dumps(call_tool(str(request["tool"]), request.get("arguments") or {}),
                      ensure_ascii=False)
