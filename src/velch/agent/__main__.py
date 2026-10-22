"""``python -m velch.agent`` -- the three entry points a shell, a test or an AI needs.

    manifest   the tool table as JSON (what ``tools/list`` returns)
    call       one tool from a JSON string, so any shell can drive the software
    doctor     self-check: registry, case root, writable home, ledger
    serve      MCP over stdio
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from .cases import list_cases, revisions
from .core import agent_home, case_root, describe_parameters, repository_root
from .server import serve
from .tools import call_tool_json, manifest

USAGE = __doc__ or ""


def _doctor() -> dict:
    """Prove the three things that break first: registry, case root, writable home."""
    checks: list[dict] = []
    parameters = describe_parameters()
    checks.append({"check": "registry", "ok": len(parameters) > 0, "detail": len(parameters)})
    root = case_root()
    checks.append({"check": "case_root", "ok": root.is_dir(), "detail": str(root)})
    home = agent_home()
    try:
        probe = home / ".write-probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        checks.append({"check": "agent_home", "ok": True, "detail": str(home)})
    except OSError as error:  # pragma: no cover - a read-only checkout
        checks.append({"check": "agent_home", "ok": False, "detail": f"{home}: {error}"})
    cases = list_cases(limit=1)
    check: dict = {"check": "cases", "ok": cases["total"] > 0, "detail": cases["total"]}
    if cases["total"] == 0:
        # "0 cases" is the first thing a packaged install shows; without the reason it reads like
        # a broken build rather than a missing corpus, so the same hint the UI prints goes here.
        from .. import data_root as data_root_module
        check["detail"] = f"0（算例根：{data_root_module.case_dir()}）"
        check["hint"] = data_root_module.hint()
    checks.append(check)
    ledger = revisions(limit=1)
    return {
        "software": str(repository_root()),
        "ok": all(item["ok"] for item in checks),
        "checks": checks,
        "ledger_entries": ledger["count"],
    }


def main(argv: list[str]) -> int:
    if not argv or argv[0] in {"-h", "--help", "help"}:
        print(USAGE.strip())
        return 0 if argv else 2
    command = argv[0]
    if command == "manifest":
        print(json.dumps(manifest(), ensure_ascii=False, indent=2))
        return 0
    if command == "call":
        if len(argv) < 2:
            print("usage: python -m velch.agent call '<json>'", file=sys.stderr)
            return 2
        envelope = call_tool_json(argv[1])
        print(envelope)
        return 0 if json.loads(envelope).get("ok") else 1
    if command == "doctor":
        report = _doctor()
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report["ok"] else 1
    if command == "serve":
        return serve()
    print(f"unknown command: {command}\n{USAGE.strip()}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
