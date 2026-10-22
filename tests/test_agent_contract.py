"""Contract tests for the machine-facing layer.

These test the promises an external caller depends on, not the solver: a shipped case is
never written, a wildcard patch is refused, a result without a manifest is refused, and a
run that finished but failed its gates is reported as such instead of as an error.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from velch.agent import call_tool, manifest
from velch.agent.core import AgentError, ErrorCode, predict_wall_s
from velch.agent.jobs import read_result, submit_run
from velch.agent.server import handle
from velch.data_root import case_dir

pytestmark = pytest.mark.corpus


CASE = str(case_dir() / "case_frog_N_strip05.json")


@pytest.fixture()
def agent_home(tmp_path, monkeypatch):
    """Point the agent's writable state at a temporary directory."""
    monkeypatch.setenv("VELCH_AGENT_HOME", str(tmp_path / "agent"))
    return tmp_path / "agent"


def test_manifest_is_self_consistent():
    payload = manifest()
    assert payload["schema_version"] == "velch-agent-tools-v1"
    names = [tool["name"] for tool in payload["tools"]]
    assert len(names) == len(set(names)) == 12
    for tool in payload["tools"]:
        assert tool["inputSchema"]["type"] == "object"
        assert tool["description"].strip()


def test_capabilities_reports_the_registry():
    envelope = call_tool("capabilities")
    assert envelope["ok"] is True
    assert envelope["data"]["parameter_count"] == 72
    assert set(envelope["data"]["tools"]) == {tool["name"] for tool in manifest()["tools"]}


def test_unknown_tool_is_an_envelope_not_an_exception():
    envelope = call_tool("no_such_tool")
    assert envelope["ok"] is False
    assert envelope["error"]["code"] == "tool_unknown"


def test_wildcard_patch_is_refused(agent_home):
    envelope = call_tool("derive_case", {"parent": CASE,
                                         "patch": [{"path": "support.layers[].k_z_n_per_m", "value": 1e7}]})
    assert envelope["ok"] is False
    assert envelope["error"]["code"] == "parameter_rejected"
    assert "'[]'" in envelope["error"]["message"]


def test_unknown_parameter_is_refused(agent_home):
    envelope = call_tool("derive_case", {"parent": CASE,
                                         "patch": [{"path": "vehicle.nonsense_kg", "value": 1.0}]})
    assert envelope["ok"] is False
    assert envelope["error"]["code"] == "parameter_rejected"


def test_duplicate_parameter_is_refused(agent_home):
    envelope = call_tool("derive_case", {
        "parent": CASE,
        "patch": [{"path": "vehicle.carbody.mass_kg", "value": 1.0},
                  {"path": "vehicle.carbody.mass_kg", "value": 2.0}]})
    assert envelope["ok"] is False
    assert envelope["error"]["code"] == "invalid_argument"


@pytest.mark.parametrize("solver_patch, code", [
    ({"method": "Euler"}, "parameter_rejected"),
    ({"rtol": -1.0}, "parameter_rejected"),
    ({"duration_s": 1e9}, "parameter_rejected"),
    ({"not_a_field": 1.0}, "parameter_rejected"),
])
def test_bad_solver_patch_is_refused(agent_home, solver_patch, code):
    envelope = call_tool("derive_case", {"parent": CASE, "solver_patch": solver_patch})
    assert envelope["ok"] is False
    assert envelope["error"]["code"] == code


def test_derive_leaves_the_parent_untouched_and_chains_the_ledger(agent_home):
    parent = Path(CASE).resolve()
    before = parent.read_bytes()
    first = call_tool("derive_case", {"parent": CASE, "tag": "unit-a",
                                      "patch": [{"path": "vehicle.carbody.mass_kg", "value": 36000.0}]})
    second = call_tool("derive_case", {"parent": CASE, "tag": "unit-b",
                                       "solver_patch": {"method": "BDF", "jacobian": "analytic"}})
    assert first["ok"] and second["ok"]
    assert parent.read_bytes() == before
    assert first["data"]["revision"] == "r0001"
    assert second["data"]["revision"] == "r0002"
    assert first["data"]["physics_changed"] is False
    assert first["data"]["comparable_to_parent"] is True
    assert second["data"]["physics_changed"] is True
    assert second["data"]["comparable_to_parent"] is False
    assert second["data"]["run"]["method"] == "BDF"
    assert second["data"]["run"]["jacobian"] == "analytic"

    ledger = [json.loads(line) for line in
              (agent_home / "revisions" / "ledger.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [row["revision"] for row in ledger] == ["r0001", "r0002"]
    assert ledger[1]["prev_ledger_sha256"] != ledger[0]["prev_ledger_sha256"]


def test_resampling_only_is_not_a_physics_change(agent_home):
    """output_step_s decides the written grid, not the trajectory.

    If it counted as a physics change, every resampled variant would be marked non-comparable and
    the acceptance smoke test would claim to have altered the model when it only asked for fewer
    rows in history.csv.
    """
    envelope = call_tool("derive_case", {"parent": CASE, "tag": "resample",
                                         "solver_patch": {"output_step_s": 0.001}})
    assert envelope["ok"], envelope
    assert envelope["data"]["physics_changed"] is False
    assert envelope["data"]["comparable_to_parent"] is True
    assert envelope["data"]["run"]["output_step_s"] == 0.001


def test_derived_case_has_absolute_profile_references(agent_home):
    envelope = call_tool("derive_case", {"parent": CASE, "tag": "abs",
                                         "patch": [{"path": "vehicle.carbody.mass_kg", "value": 34000.0}]})
    assert envelope["ok"]
    payload = json.loads(Path(envelope["data"]["path"]).read_text(encoding="utf-8"))
    references: list[str] = []

    def walk(node):
        if isinstance(node, dict):
            for key, value in node.items():
                if key == "file" and isinstance(value, str):
                    references.append(value)
                else:
                    walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(payload)
    assert references, "the case should reference at least one profile file"
    assert all(Path(name).is_absolute() for name in references), \
        "a derived case must not depend on being written next to its parent"


def test_read_case_refuses_a_path_outside_the_jail(agent_home):
    envelope = call_tool("read_case", {"case": "C:/Windows/win.ini"})
    assert envelope["ok"] is False
    assert envelope["error"]["code"] in {"path_escape", "case_invalid", "case_not_found"}


def _fake_job(home: Path, *, manifest: dict | None, status: str = "finished") -> Path:
    job_dir = home / "jobs" / "jtest-0001"
    output = job_dir / "out"
    output.mkdir(parents=True)
    (job_dir / "job.json").write_text(json.dumps({
        "job_id": "jtest-0001", "output_dir": str(output), "case_sha256": "0" * 64,
        "workers": 1, "created": "2026-10-22T00:00:00", "estimate": {"point": 1.0}}), encoding="utf-8")
    (job_dir / "state.json").write_text(json.dumps({
        "status": status, "exit_code": 0 if manifest else 2}), encoding="utf-8")
    if manifest is not None:
        (output / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        (output / "history.csv").write_text("time_s\n0.0\n", encoding="utf-8")
    return job_dir


def test_result_without_manifest_is_refused(agent_home):
    _fake_job(agent_home, manifest=None)
    with pytest.raises(AgentError) as caught:
        read_result("jtest-0001")
    assert caught.value.code is ErrorCode.ARTIFACT_INTEGRITY


def test_gate_failed_is_reported_as_a_state_not_an_error(agent_home):
    _fake_job(agent_home, manifest={"summary": {"result_status": "diverged",
                                                 "physics_validation_status": "failed"}})
    payload = read_result("jtest-0001")
    assert payload["status"] == "gate_failed"
    assert payload["quotable"] is False
    assert payload["note"]


def test_agent_import_stays_cheap():
    """Importing the agent must not drag the geometry/dynamics kernel in with it.

    This is the reason the layer exists in its own subpackage: a client that only wants to
    list cases or check a status should not pay half a second for the solver, and a broken
    kernel must not make the metadata tools unusable.
    """
    import subprocess
    import sys

    import velch

    source = str(Path(velch.__file__).resolve().parents[1])
    env = dict(os.environ, PYTHONPATH=source, PYTHONUTF8="1")
    program = ("import sys, velch.agent; "
               "print(int(any(name in sys.modules for name in "
               "('velch.vehicle_solver', 'velch.contact', 'velch.jacobian'))))")
    completed = subprocess.run([sys.executable, "-c", program], capture_output=True, text=True,
                               env=env, check=True)
    assert completed.stdout.strip() == "0", completed.stderr


def test_cost_model_is_monotone_and_banded():
    short = predict_wall_s(0.05, 5e-4, "DOP853")
    long = predict_wall_s(1.2, 5e-4, "DOP853")
    assert short["point"] < long["point"]
    assert short["low"] < short["point"] < short["high"]
    assert predict_wall_s(1.2, 5e-4, "BDF")["point"] < long["point"]


def test_budget_is_refused_before_anything_runs(agent_home):
    with pytest.raises(AgentError) as caught:
        submit_run(case_path=CASE, budget_s=1.0)
    assert caught.value.code is ErrorCode.BUDGET_EXCEEDED


def test_mcp_protocol_surface():
    initialized = handle({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
    assert initialized["result"]["protocolVersion"]
    listed = handle({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
    assert len(listed["result"]["tools"]) == 12
    called = handle({"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                     "params": {"name": "capabilities", "arguments": {}}})
    envelope = json.loads(called["result"]["content"][0]["text"])
    assert envelope["ok"] is True
    assert called["result"]["isError"] is False
    assert handle({"jsonrpc": "2.0", "method": "notifications/initialized"}) is None
    missing = handle({"jsonrpc": "2.0", "id": 4, "method": "no/such"})
    assert missing["error"]["code"] == -32601
