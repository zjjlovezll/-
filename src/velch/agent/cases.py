"""Case discovery, reading and derivation -- the only write path an agent gets.

A derived case is a *new* file under ``.agent/variants`` with its profile references
rewritten to absolute paths, so it loads from anywhere and never depends on being written
back into ``validation/crh380a_m``.  The parent file is read-only to this module: its bytes
and its sha256 are recorded before and re-checked after, and a mismatch is a hard error.

Why not ``CaseSpec.resolve()``: it writes the case into a ``TemporaryDirectory`` and
returns a :class:`VehicleCase` whose ``source_path`` points inside it, so by the time the
object reaches ``save_vehicle_result`` the directory is gone (``case/spec.py:143-158``) and
the save raises ``FileNotFoundError`` after the simulation has already been paid for.  The
optimiser path never saves, so the defect has stayed invisible; an agent that derives and
runs would hit it on the first job.
"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any, Mapping

from .core import (
    AgentError,
    ErrorCode,
    agent_home,
    apply_parameter_patch,
    case_root,
    normalise_patch,
    validate_solver_patch,
    within_allowed,
)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _absolutise(node: Any, base: Path) -> Any:
    """Rewrite every relative ``file`` reference against the parent case's directory."""
    if isinstance(node, dict):
        out: dict[str, Any] = {}
        for key, value in node.items():
            if key == "file" and isinstance(value, str):
                candidate = Path(value)
                out[key] = str(candidate if candidate.is_absolute() else (base / candidate))
            else:
                out[key] = _absolutise(value, base)
        return out
    if isinstance(node, list):
        return [_absolutise(item, base) for item in node]
    return node


def _summarise(raw: Mapping[str, Any], path: Path) -> dict[str, Any]:
    run = raw.get("run", {}) if isinstance(raw.get("run"), dict) else {}
    contact = raw.get("contact", {}) if isinstance(raw.get("contact"), dict) else {}
    rails = raw.get("rails") or raw.get("rail_templates") or []
    return {
        "case_id": raw.get("case_id") or path.stem,
        "path": str(path),
        "sha256": sha256_file(path),
        "method": run.get("method"),
        "jacobian": run.get("jacobian"),
        "duration_s": run.get("duration_s"),
        "x_start_m": run.get("x_start_m"),
        "output_step_s": run.get("output_step_s"),
        "rtol": run.get("rtol"),
        "normal_policy": contact.get("normal_policy"),
        "damping_policy": contact.get("damping_policy"),
        "support_compliance": bool(raw.get("support_compliance")),
        "rail_count": len(rails) if isinstance(rails, list) else None,
        "equilibrate_vertical": bool(raw.get("equilibrate_vertical", True)),
    }


def list_cases(*, limit: int = 40, pattern: str = "case_*.json") -> dict[str, Any]:
    """List shipped cases, newest-looking names first, with a cheap summary each."""
    root = case_root()
    paths = sorted(root.glob(pattern))
    entries = []
    for path in paths[: max(0, int(limit))]:
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            entries.append(_summarise(raw, path))
        except (OSError, json.JSONDecodeError) as error:  # a broken case must not break the list
            entries.append({"path": str(path), "error": f"{type(error).__name__}: {error}"})
    return {"root": str(root), "total": len(paths), "returned": len(entries), "cases": entries}


def _load(path: Path) -> tuple[dict[str, Any], Path]:
    resolved = within_allowed(path, [case_root(), agent_home(), Path.cwd()])
    if not resolved.exists():
        raise AgentError(ErrorCode.CASE_NOT_FOUND, f"no such case: {resolved}")
    try:
        raw = json.loads(resolved.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise AgentError(ErrorCode.CASE_INVALID, f"{resolved}: {error}") from error
    if not isinstance(raw, dict):
        raise AgentError(ErrorCode.CASE_INVALID, f"{resolved} is not a case object")
    return raw, resolved


def read_case(path: str | Path) -> dict[str, Any]:
    """Metadata for one case, plus the editable-and-set parameters it currently carries."""
    raw, resolved = _load(Path(path))
    summary = _summarise(raw, resolved)
    summary["run"] = raw.get("run", {})
    return summary


def materialise_case(path: str | Path, destination: Path) -> dict[str, Any]:
    """Copy a case to ``destination`` with absolute profile references.

    A job must keep running (and stay readable) even if the parent case is later edited, so
    the bytes it will simulate are frozen here, and the profile references are made
    absolute so the copy loads from a directory that is not the case's own.
    """
    raw, source = _load(Path(path))
    payload = _absolutise(raw, source.parent)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"path": str(destination), "sha256": sha256_file(destination),
            "case_id": payload.get("case_id") or destination.stem, "source": str(source)}


def _ledger_path() -> Path:
    return agent_home() / "revisions" / "ledger.jsonl"


def append_revision(entry: Mapping[str, Any]) -> str:
    """Append one line to the ledger; the file is append-only by convention and by test."""
    ledger = _ledger_path()
    previous = ledger.read_text(encoding="utf-8") if ledger.exists() else ""
    index = sum(1 for line in previous.splitlines() if line.strip()) + 1
    revision = f"r{index:04d}"
    record = {"revision": revision, "created": time.strftime("%Y-%m-%dT%H:%M:%S"),
              "prev_ledger_sha256": hashlib.sha256(previous.encode("utf-8")).hexdigest(),
              **dict(entry)}
    with ledger.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    return revision


def revisions(*, limit: int = 50) -> dict[str, Any]:
    """Read the ledger back (newest last, truncated to ``limit``)."""
    ledger = _ledger_path()
    if not ledger.exists():
        return {"count": 0, "entries": []}
    lines = [line for line in ledger.read_text(encoding="utf-8").splitlines() if line.strip()]
    entries = [json.loads(line) for line in lines[-max(0, int(limit)):]]
    return {"count": len(lines), "entries": entries}


SAMPLING_ONLY_SOLVER_KEYS = frozenset({"output_step_s"})
"""``run`` keys that change what is written, not what is computed.

Adaptive stepping is driven by ``rtol``/``atol``/``max_solver_step_s``; ``output_step_s`` only
decides how often the dense solution is sampled onto the history grid.  Treating it as a physics
change would make every resampled variant non-comparable for no reason, and would make the
acceptance smoke test claim it had altered the model.
"""


def derive_case(*, parent: str | Path, patch: Any = None, solver_patch: Any = None,
                note: str = "", tag: str = "") -> dict[str, Any]:
    """Create a new case from ``parent`` plus edits.  The parent is never modified.

    ``patch``  : list of ``{path, value}`` in registry paths (SI units).
    ``solver_patch`` : ``run`` block edits.  Edits that can move the trajectory are echoed with
    ``physics_changed=true``; changing only the output sampling is not such an edit.
    """
    edits = normalise_patch(patch)
    solver_edits = validate_solver_patch(solver_patch or {})
    if not edits and not solver_edits:
        raise AgentError(ErrorCode.INVALID_ARGUMENT,
                         "nothing to derive: pass patch and/or solver_patch")
    changes_physics = any(key not in SAMPLING_ONLY_SOLVER_KEYS for key in solver_edits)
    raw, parent_path = _load(Path(parent))
    parent_digest = sha256_file(parent_path)

    derived: dict[str, Any] = dict(raw)
    if edits:
        derived = apply_parameter_patch(derived, edits)
    if solver_edits:
        run = dict(derived.get("run") or {})
        run.update(solver_edits)
        derived["run"] = run
    derived = _absolutise(derived, parent_path.parent)

    slug = tag.strip() or time.strftime("%Y%m%d-%H%M%S")
    slug = "".join(character if character.isalnum() or character in "-_." else "-" for character in slug)
    base_id = str(derived.get("case_id") or parent_path.stem)
    derived["case_id"] = f"{base_id}__{slug}"
    out_path = agent_home() / "variants" / f"{derived['case_id']}.json"
    out_path.write_text(json.dumps(derived, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if sha256_file(parent_path) != parent_digest:  # pragma: no cover - hardware-level accident
        raise AgentError(ErrorCode.CASE_MUTATED, f"{parent_path} changed while deriving")

    revision = append_revision({
        "kind": "derive",
        "parent": str(parent_path),
        "parent_sha256": parent_digest,
        "out": str(out_path),
        "out_sha256": sha256_file(out_path),
        "patch": edits,
        "solver_patch": solver_edits,
        "physics_changed": changes_physics,
        "note": note,
    })
    return {
        "revision": revision,
        "path": str(out_path),
        "sha256": sha256_file(out_path),
        "case_id": derived["case_id"],
        "parent_sha256": parent_digest,
        "patch": edits,
        "solver_patch": solver_edits,
        "physics_changed": changes_physics,
        "comparable_to_parent": not changes_physics,
        "run": derived.get("run", {}),
    }
