import pathlib

p = pathlib.Path("src/velch/vehicle_solver.py")
src = p.read_text(encoding="utf-8")
original = src


def sub(old: str, new: str, count: int = 1) -> None:
    global src
    found = src.count(old)
    assert found == count, f"expected {count} occurrences, found {found}: {old[:70]!r}"
    src = src.replace(old, new, count)


# 1. the two constants, above the launch report helpers
anchor = "def _launch_report("
assert src.count(anchor) == 1
src = src.replace(
    anchor,
    "# Gates 8 and 9 (docs/LAUNCH_GATES_2026-11-01.md).  The seven numerical gates say nothing about\n"
    "# the state a run starts from or whether it settled, so both were added rather than replacing\n"
    "# anything.  Neither threshold is new: 0.1 N is the preload limit already used by\n"
    "# ``vertical_preload_residual``, 1e-3 is the ``spin_tracking`` limit, and 5 kN sits 7x below the\n"
    "# smallest ringing archive (34.75 kN at 60 km/h) and 100x above the noisiest quiet one (0.51 kN),\n"
    "# while legitimate 60 um bump runs measure 0.2-0.8 kN.\n"
    "MAX_STATIONARY_FORCE_STD_KN = 5.0\n"
    "PHYSICAL_GATE_NAMES = frozenset({\"launch_balance\", \"stationarity\"})\n"
    "\n\n"
    + anchor,
    1,
)

# 2. the launch report is computed unconditionally
sub(
    "    launch_report = (_launch_report(case, dynamics, q, v, static_residual_n)\n"
    "                     if bool(getattr(run, \"report_launch\", False)) else None)\n",
    "    # Computed unconditionally: the launch balance is gate 8 now, and a gate a run can switch off\n"
    "    # with a flag is not a gate.  ``report_launch`` decides only whether the block is reported.\n"
    "    launch_report = _launch_report(case, dynamics, q, v, static_residual_n)\n",
)

# 3. per-rail force samples for gate 9
sub(
    "    active = {rail.id: 0 for rail in case.rails}\n",
    "    active = {rail.id: 0 for rail in case.rails}\n"
    "    force_samples: dict[str, list[float]] = {rail.id: [] for rail in case.rails}\n",
)

sub(
    "            peak_normal[rail.id] = max(peak_normal[rail.id], response.normal_force_n)\n"
    "            active[rail.id] += int(response.active)\n",
    "            peak_normal[rail.id] = max(peak_normal[rail.id], response.normal_force_n)\n"
    "            force_samples[rail.id].append(float(response.normal_force_n))\n"
    "            active[rail.id] += int(response.active)\n",
)

# 4. the two gates and the three-way status
sub(
    "    if spin_tracking_relative is not None:\n"
    "        gates[\"spin_tracking\"] = bool(spin_tracking_relative <= 0.01)\n",
    "    if spin_tracking_relative is not None:\n"
    "        gates[\"spin_tracking\"] = bool(spin_tracking_relative <= 0.01)\n"
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
)

sub(
    "        \"result_status\": \"numerically_checked\" if all(gates.values()) else \"numerical_gate_failed\",\n",
    "        \"result_status\": result_status,\n"
    "        \"failed_gates\": failed_gates,\n"
    "        \"max_rail_force_std_kn\": max_force_std_kn,\n"
    "        \"rail_force_std_kn\": force_std_kn,\n"
    "        \"stationary_force_std_limit_kn\": MAX_STATIONARY_FORCE_STD_KN,\n",
)

# 5. the reported block still honours the flag
sub(
    "                         launch=launch_report)\n",
    "                         launch=(launch_report\n"
    "                                 if bool(getattr(run, \"report_launch\", False)) else None))\n",
)

import ast

ast.parse(src)
p.write_text(src, encoding="utf-8")
print("patched", len(src) - len(original), "chars")
for needle in ("MAX_STATIONARY_FORCE_STD_KN = 5.0", "force_samples[rail.id].append",
               "gates[\"launch_balance\"]", "gates[\"stationarity\"]", "result_status = result_status"):
    print(("OK  " if needle in src else "MISS"), needle)
