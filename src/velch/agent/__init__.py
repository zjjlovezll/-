"""A machine-facing layer over Velch: derive a case, run it, read the result.

Four rules hold for everything in this package, and each one exists because of a specific
failure already seen in the code it wraps:

* **Do not import the kernel we drive.** Geometry and dynamics load in ~0.5 s and a run can
  take minutes; the agent process must stay cheap so it can be started on demand, and a
  simulation failure must not take the agent down with it.
* **A simulation is a child process.** ``submit_run`` is the only place a run happens.
* **A shipped case is never modified.** ``derive_case`` writes a new file and records it in
  an append-only ledger; the parent's sha256 is re-checked afterwards.
* **Failures carry a code, not an exit status.** ``cli.py`` returns 2 for a bad argument, an
  invalid case and a failed numerical gate alike; an agent cannot branch on that.

State lives under ``.agent/`` (``variants/``, ``jobs/``, ``revisions/``) and is relocatable
through ``VELCH_AGENT_HOME``; cases come from ``validation/crh380a_m`` unless
``VELCH_CASE_ROOT`` says otherwise.
"""

from __future__ import annotations

from .cases import derive_case, list_cases, read_case, revisions
from .core import (
    AgentError,
    ErrorCode,
    agent_home,
    case_root,
    describe_parameters,
    parameter_schema,
    predict_wall_s,
    solver_schema,
)
from .jobs import cancel_job, job_status, list_jobs, read_result, submit_run
from .tools import TOOLS, ToolSpec, call_tool, call_tool_json, manifest

__all__ = [
    "AgentError",
    "ErrorCode",
    "TOOLS",
    "ToolSpec",
    "agent_home",
    "call_tool",
    "call_tool_json",
    "cancel_job",
    "case_root",
    "derive_case",
    "describe_parameters",
    "job_status",
    "list_cases",
    "list_jobs",
    "manifest",
    "parameter_schema",
    "predict_wall_s",
    "read_case",
    "read_result",
    "revisions",
    "solver_schema",
    "submit_run",
]
