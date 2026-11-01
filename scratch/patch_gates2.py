import pathlib

p = pathlib.Path("src/velch/vehicle_solver.py")
src = p.read_text(encoding="utf-8")
original = src


def sub(old: str, new: str, count: int = 1) -> None:
    global src
    found = src.count(old)
    assert found == count, f"expected {count}, found {found}: {old[:60]!r}"
    src = src.replace(old, new, count)


helpers = '''MAX_STATIONARY_FORCE_STD_KN = 5.0
PHYSICAL_GATE_NAMES = frozenset({"launch_balance", "stationarity"})


def launch_balance_gate(launch: dict | None) -> bool:
    """Gate 8, as a pure function so it can be tested without a simulation.

    The two numbers it reads are the ones the seater already reports: the vertical preload residual
    (same 0.1 N limit as ``vertical_preload_residual``) and the spin consistency
    ``|spin*r - travel| / travel`` (same 1e-3 limit as ``spin_tracking``).  The modal residual is
    deliberately *not* here: measured, it is the fixed point of the settle/seat alternation (~101 N at
    both 60 and 80 km/h, bit-identical at 400 rounds), a property of the compromise rather than of the
    run, and turning a number nobody calibrated into a gate is how a tolerance gets invented.
    """
    if launch is None:
        return False
    preload = launch.get("vertical_preload_residual_n")
    spin = launch.get("spin_relative_max")
    if preload is not None and float(preload) > 0.1:
        return False
    return spin is None or float(spin) <= 1.0e-3


def rail_force_std_kn(samples: dict[str, list[float]]) -> dict[str, float]:
    """Per-rail standard deviation of the normal force, converted to kN."""
    return {rail_id: (float(np.std(values)) / 1.0e3 if values else 0.0)
            for rail_id, values in samples.items()}


def stationarity_gate(force_std_kn: dict[str, float]) -> bool:
    """Gate 9: the worst rail must not be ringing above 5 kN."""
    worst = max(force_std_kn.values()) if force_std_kn else 0.0
    return bool(worst <= MAX_STATIONARY_FORCE_STD_KN)


def gates_result_status(gates: dict[str, bool]) -> tuple[str, list[str]]:
    """Three-way status: only physical gates failing is not a numerical failure."""
    failed = [name for name, ok in gates.items() if not ok]
    if not failed:
        return "numerically_checked", []
    if all(name in PHYSICAL_GATE_NAMES for name in failed):
        return "physical_gate_failed", failed
    return "numerical_gate_failed", failed
'''

anchor = "def _launch_report("
assert src.count(anchor) == 1
start = src.index("# Gates 8 and 9 (docs/LAUNCH_GATES_2026-11-01.md)")
end = src.index(anchor)
assert start < end
src = src[:start] + helpers + "\n\n" + src[end:]

# use the helpers in the summary
sub(
    "    launch_preload = (None if launch_report is None\n"
    "                      else launch_report.get(\"vertical_preload_residual_n\"))\n"
    "    launch_spin = (None if launch_report is None else launch_report.get(\"spin_relative_max\"))\n"
    "    gates[\"launch_balance\"] = bool(\n"
    "        (launch_preload is None or float(launch_preload) <= 0.1)\n"
    "        and (launch_spin is None or float(launch_spin) <= 1e-3))\n"
    "    force_std_kn = {rail.id: (float(np.std(force_samples[rail.id])) / 1.0e3\n"
    "                              if force_samples[rail.id] else 0.0)\n"
    "                    for rail in case.rails}\n"
    "    max_force_std_kn = max(force_std_kn.values()) if force_std_kn else 0.0\n"
    "    gates[\"stationarity\"] = bool(max_force_std_kn <= MAX_STATIONARY_FORCE_STD_KN)\n"
    "    failed_gates = [name for name, ok in gates.items() if not ok]\n"
    "    if not failed_gates:\n"
    "        result_status = \"numerically_checked\"\n"
    "    elif all(name in PHYSICAL_GATE_NAMES for name in failed_gates):\n"
    "        result_status = \"physical_gate_failed\"\n"
    "    else:\n"
    "        result_status = \"numerical_gate_failed\"\n",
    "    gates[\"launch_balance\"] = launch_balance_gate(launch_report)\n"
    "    force_std_kn = rail_force_std_kn(force_samples)\n"
    "    max_force_std_kn = max(force_std_kn.values()) if force_std_kn else 0.0\n"
    "    gates[\"stationarity\"] = stationarity_gate(force_std_kn)\n"
    "    result_status, failed_gates = gates_result_status(gates)\n",
)

import ast

ast.parse(src)
p.write_text(src, encoding="utf-8")
print("patched", len(src) - len(original), "chars")
for needle in ("def launch_balance_gate", "def rail_force_std_kn", "def stationarity_gate",
               "def gates_result_status", "gates[\"launch_balance\"] = launch_balance_gate",
               "result_status, failed_gates = gates_result_status(gates)"):
    print(("OK  " if needle in src else "MISS"), needle)
