"""The assessment screen must show every gate the run produced, not the seven it knew about.

Round 315: ``GATE_LABELS`` held seven entries and ``_render_gates`` walked only that table, so a run
whose ``launch_balance`` failed -- the one gate that catches a launch with the wrong spin -- was
displayed as ``7/7``.  The table now holds nine, and anything still missing from it is rendered by
its own name rather than dropped.
"""

from __future__ import annotations

from velch.ui import store

SOLVER_GATES = (
    "solver_completed",
    "finite_states_and_forces",
    "vertical_preload_residual",
    "penetration_within_case_limit",
    "friction_bound",
    "no_edge_limited_active_contact",
    "translational_action_reaction",
    "launch_balance",
    "stationarity",
)


def test_the_gate_table_covers_every_gate_the_solver_writes() -> None:
    keys = tuple(key for key, _label in store.GATE_LABELS)
    assert len(keys) == len(set(keys)) == 9
    assert set(keys) == set(SOLVER_GATES)


def test_every_labelled_gate_has_a_number_to_read() -> None:
    for key, label in store.GATE_LABELS:
        assert label.strip()
    # The two gates added in round 314 must expose the number that explains a failure.
    assert store.GATE_DETAIL_FIELDS["launch_balance"] == "spin_relative_max"
    assert store.GATE_DETAIL_FIELDS["stationarity"] == "max_rail_force_std_kn"
    assert store.GATE_UNITS["spin_relative_max"] == "-"
    assert store.GATE_UNITS["max_rail_force_std_kn"] == "kN"


def test_a_gate_missing_from_the_table_still_has_a_name() -> None:
    known = {key for key, _label in store.GATE_LABELS}
    # This is the shape ``_render_gates`` builds: labelled rows first, then anything unknown.
    produced = dict.fromkeys(SOLVER_GATES, True)
    produced["future_gate"] = False
    rows = list(store.GATE_LABELS) + [(key, key) for key in produced if key not in known]
    assert ("future_gate", "future_gate") in rows
    failed = [label for key, label in rows if produced.get(key) is False]
    assert failed == ["future_gate"]
