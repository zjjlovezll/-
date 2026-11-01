"""Round 315 patch: gate-9 coverage, launch evidence, one window validator, UI gate table.

Run from the repository root:  python -X utf8 scratch/patch_315.py
Every replacement asserts its anchor appears exactly once, so a silent no-op cannot pass.
"""
from __future__ import annotations

import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]


def patch(relative: str, pairs: list[tuple[str, str]]) -> None:
    path = ROOT / relative
    text = path.read_text(encoding="utf-8")
    for old, new in pairs:
        count = text.count(old)
        assert count == 1, f"{relative}: anchor found {count} times: {old[:80]!r}"
        text = text.replace(old, new, 1)
    path.write_text(text, encoding="utf-8")
    print(f"patched {relative}")


# ---------------------------------------------------------------- vehicle_solver
COVERAGE = '''def stationarity_coverage(stations: list[float] | tuple[float, ...],
                          window: tuple[float, float]) -> dict[str, float | bool | None]:
    """Does the kept sample span cover the declared window, up to one sample spacing?

    Gate 9 asks whether the reading window was *quiet*.  A run that only drove the first 0.44 m of a
    9 m window answers a different question, and it answered it with a pass: measured in round 315,
    41 of 41 frames lay inside ``[56, 65]`` m with 0.096 kN, while the window's other 8.56 m were
    never sampled.  Samples sit on a grid, so no run can hold a sample exactly on both ends; one
    spacing is the allowance, and it is read from the data rather than chosen.
    """
    low, high = float(window[0]), float(window[1])
    kept = sorted(float(station) for station in stations)
    if len(kept) < 2:
        return {"covered": False, "span_m": 0.0, "expected_span_m": high - low, "spacing_m": None}
    spacing = float(np.median(np.diff(kept)))
    span = kept[-1] - kept[0]
    expected = (high - low) - spacing
    return {"covered": bool(span >= expected - 1.0e-9), "span_m": span,
            "expected_span_m": expected, "spacing_m": spacing}


def stationarity_gate(force_std_kn: dict[str, float], samples: int, covered: bool = True) -> bool:
'''

patch("src/velch/vehicle_solver.py", [
    (
        "def stationarity_gate(force_std_kn: dict[str, float], samples: int) -> bool:\n",
        COVERAGE,
    ),
    (
        """    if not force_std_kn or samples < 3:
        return False""",
        """    if not force_std_kn or samples < 3 or not covered:
        return False""",
    ),
    (
        """        low, high = float(stationarity_window[0]), float(stationarity_window[1])
        keep = [i for i, station in enumerate(front_stations_m) if low <= station <= high]
        stationarity_samples = len(keep)
        force_std_kn = rail_force_std_kn(
            {rail_id: [values[i] for i in keep]
             for rail_id, values in force_samples.items()})
        max_force_std_kn = max(force_std_kn.values()) if force_std_kn else 0.0
        gates["stationarity"] = stationarity_gate(force_std_kn, stationarity_samples)""",
        """        low, high = float(stationarity_window[0]), float(stationarity_window[1])
        keep = [i for i, station in enumerate(front_stations_m) if low <= station <= high]
        stationarity_samples = len(keep)
        coverage = stationarity_coverage([front_stations_m[i] for i in keep], stationarity_window)
        stationarity_span_m = float(coverage["span_m"])
        stationarity_expected_span_m = coverage["expected_span_m"]
        stationarity_spacing_m = coverage["spacing_m"]
        stationarity_covered = bool(coverage["covered"])
        force_std_kn = rail_force_std_kn(
            {rail_id: [values[i] for i in keep]
             for rail_id, values in force_samples.items()})
        max_force_std_kn = max(force_std_kn.values()) if force_std_kn else 0.0
        gates["stationarity"] = stationarity_gate(force_std_kn, stationarity_samples,
                                                  stationarity_covered)""",
    ),
    (
        """        force_std_kn: dict[str, float] = {}
        max_force_std_kn: float | None = None
        stationarity_samples = 0""",
        """        force_std_kn: dict[str, float] = {}
        max_force_std_kn: float | None = None
        stationarity_samples = 0
        stationarity_span_m: float | None = None
        stationarity_expected_span_m: float | None = None
        stationarity_spacing_m: float | None = None
        stationarity_covered: bool | None = None""",
    ),
    (
        '''        "stationarity_samples": stationarity_samples,''',
        '''        "stationarity_samples": stationarity_samples,
        "stationarity_span_m": stationarity_span_m,
        "stationarity_expected_span_m": stationarity_expected_span_m,
        "stationarity_spacing_m": stationarity_spacing_m,
        "stationarity_covered": stationarity_covered,
        # Gate 8 is unconditional, so its evidence must be too: measured in round 315, one archive
        # carried ``launch_balance: true`` next to ``launch: null`` because the block was gated by
        # ``report_launch`` while the gate was not.  A gate reads this dict; the archive stores it.
        "launch": launch_report,''',
    ),
])

# ------------------------------------------------------------------------ model
patch("src/velch/model.py", [
    (
        """    seat_lateral: bool = False
    #: Mileage window, in metres, over which this run claims a quasi-static reading.  Gate 9 is
    #: computed inside it and nowhere else; ``None`` means the run makes no such claim and no gate
    #: is produced.  The distinction is measured, not stylistic: the frozen baseline moves 53.88 kN
    #: of load from ``stock`` to ``switch`` inside its first 0.015 s, so a whole-record standard
    #: deviation refuses it for doing exactly what a turnout does.  Declaring the window is what
    #: turns "the launch is quiet" from an assumption into a test.
    stationarity_window_m: tuple[float, float] | None = None
    \"\"\"Also put each wheelset where its own net lateral force vanishes.""",
        """    seat_lateral: bool = False
    \"\"\"Also put each wheelset where its own net lateral force vanishes.""",
    ),
    (
        """    frozen baseline keeps its numbers bit for bit.
    \"\"\"
    report_launch: bool = False""",
        """    frozen baseline keeps its numbers bit for bit.
    \"\"\"
    #: Mileage window, in metres, over which this run claims a quasi-static reading.  Gate 9 is
    #: computed inside it and nowhere else; ``None`` means the run makes no such claim and no gate
    #: is produced.  The distinction is measured, not stylistic: the frozen baseline moves 53.88 kN
    #: of load from ``stock`` to ``switch`` inside its first 0.015 s, so a whole-record standard
    #: deviation refuses it for doing exactly what a turnout does.  Declaring the window is what
    #: turns "the launch is quiet" from an assumption into a test, and the window has to be *reached*
    #: for the test to mean anything (round 315: 0.44 m of a 9 m window answered it).
    stationarity_window_m: tuple[float, float] | None = None
    report_launch: bool = False""",
    ),
    (
        """        if self.jacobian is not None and self.method == "DOP853":""",
        """        if self.stationarity_window_m is not None:
            window = tuple(float(value) for value in self.stationarity_window_m)
            if len(window) != 2 or not window[0] < window[1]:
                raise ValueError(
                    "run.stationarity_window_m needs two mileages with start < end, got "
                    f"{self.stationarity_window_m!r}")
            object.__setattr__(self, "stationarity_window_m", window)
        if self.jacobian is not None and self.method == "DOP853":""",
    ),
])

# ------------------------------------------------------------------------ setup
patch("src/velch/setup.py", [
    (
        """def load_setup(path: str | pathlib.Path) -> Setup:""",
        '''def _window(name: str, value: Any) -> tuple[float, float] | None:
    """Validate a reading window from any entry point.

    One validator, because a window typed backwards is a *configuration* error and nothing else.
    Measured in round 315 before this existed: the setup loader accepted ``[65, 56]`` (the run then
    failed as "physical"), accepted ``[56.0, 65.0, 70.0]`` by dropping the third, and raised
    ``IndexError`` for ``[56.0]`` -- three ways for a typo to become a physics conclusion.
    """
    if value is None:
        return None
    if isinstance(value, (int, float, str)):
        raise ValueError(f"{name} must be two mileages [start, end] or null, got {value!r}")
    parts = list(value)
    if len(parts) != 2:
        raise ValueError(f"{name} must be exactly two mileages [start, end], got {value!r}")
    low = _positive(f"{name}[0]", parts[0], 0.0, 1.0e4)
    high = _positive(f"{name}[1]", parts[1], 0.0, 1.0e4)
    if not low < high:
        raise ValueError(f"{name} needs start < end, got {value!r}")
    return (low, high)


def load_setup(path: str | pathlib.Path) -> Setup:''',
    ),
    (
        """        stationarity_window_m=(None if raw.get("stationarity_window_m") is None else
                               (float(raw["stationarity_window_m"][0]),
                                float(raw["stationarity_window_m"][1]))),""",
        """        stationarity_window_m=_window(f"{target}: stationarity_window_m",
                                     raw.get("stationarity_window_m")),""",
    ),
    (
        """    if setup.stationarity_window_m is None:
        run["stationarity_window_m"] = None
    else:
        run["stationarity_window_m"] = [float(setup.stationarity_window_m[0]),
                                        float(setup.stationarity_window_m[1])]""",
        """    if setup.stationarity_window_m is not None:
        # Only written when claimed: materialising a null key changed ``case_sha256`` and split the
        # archive id of an unchanged setup from its earlier runs (round 315).
        run["stationarity_window_m"] = [float(setup.stationarity_window_m[0]),
                                        float(setup.stationarity_window_m[1])]""",
    ),
    (
        """    case = load_vehicle_case(case_path)
    spin_relative = check_kinematics(case)""",
        """    case = load_vehicle_case(case_path)
    if resolved.stationarity_window_m is not None:
        low, high = (float(value) for value in resolved.stationarity_window_m)
        reach = resolved.duration_s * (resolved.speed_kmh / 3.6)
        if reach + 1.0e-9 < high - low:
            raise ValueError(
                f"the run is too short for the declared reading window: {reach:.3f} m of "
                f"{high - low:.3f} m at {resolved.speed_kmh:g} km/h for "
                f"{resolved.duration_s:g} s. Lengthen duration.s, narrow reading.window_m, or set "
                f"reading.window_m=none to run without a stationarity claim.")
    spin_relative = check_kinematics(case)""",
    ),
])

# --------------------------------------------------------------------------- s99
patch("scripts/s99_run_archive.py", [
    (
        """        "launch": None if launch is None else {""",
        """        "launch": None if launch is None else {""",
    ),
    (
        """        "stationarity_window_m": summary.get("stationarity_window_m"),
        "stationarity_samples": summary.get("stationarity_samples"),""",
        """        "stationarity_window_m": summary.get("stationarity_window_m"),
        "stationarity_samples": summary.get("stationarity_samples"),
        "stationarity_span_m": summary.get("stationarity_span_m"),
        "stationarity_expected_span_m": summary.get("stationarity_expected_span_m"),
        "stationarity_spacing_m": summary.get("stationarity_spacing_m"),
        "stationarity_covered": summary.get("stationarity_covered"),""",
    ),
])

# -------------------------------------------------------------------------- UI
patch("src/velch/ui/store.py", [
    (
        """#: The seven manifest gates, in the order the solver writes them, with the numeric
#: companion the manifest records for each so a failure can be read, not just seen.
GATE_LABELS: tuple[tuple[str, str], ...] = (
    ("solver_completed", "求解器收敛完成"),
    ("finite_states_and_forces", "状态与力全部有限"),
    ("vertical_preload_residual", "垂向预载残差"),
    ("penetration_within_case_limit", "侵入量在算例限值内"),
    ("friction_bound", "摩擦力在摩擦界内"),
    ("no_edge_limited_active_contact", "无边缘限幅有效接触"),
    ("translational_action_reaction", "平动作用-反力平衡"),
)""",
        """#: The manifest gates, in the order the solver writes them, with the numeric companion the
#: manifest records for each so a failure can be read, not just seen.  Nine since round 315: the
#: screen read only these seven and therefore showed a run whose ``launch_balance`` failed as
#: ``7/7`` -- the one gate that catches a launch with the wrong spin was invisible.  Unknown keys
#: are still rendered by name, so the next gate does not have to be added here to be seen.
GATE_LABELS: tuple[tuple[str, str], ...] = (
    ("solver_completed", "求解器收敛完成"),
    ("finite_states_and_forces", "状态与力全部有限"),
    ("vertical_preload_residual", "垂向预载残差"),
    ("penetration_within_case_limit", "侵入量在算例限值内"),
    ("friction_bound", "摩擦力在摩擦界内"),
    ("no_edge_limited_active_contact", "无边缘限幅有效接触"),
    ("translational_action_reaction", "平动作用-反力平衡"),
    ("launch_balance", "起点平衡（转速 + 预载）"),
    ("stationarity", "读数窗口平稳"),
)""",
    ),
    (
        """    "translational_action_reaction": "max_translation_balance_error_n",
}""",
        """    "translational_action_reaction": "max_translation_balance_error_n",
    "launch_balance": "spin_relative_max",
    "stationarity": "max_rail_force_std_kn",
}""",
    ),
    (
        """    "max_translation_balance_error_n": "N",
}""",
        """    "max_translation_balance_error_n": "N",
    "spin_relative_max": "-",
    "max_rail_force_std_kn": "kN",
}""",
    ),
])

patch("src/velch/ui/screen_assess.py", [
    (
        """    def _render_gates(self, run: store.RunInfo) -> None:
        self.gates.build([(key, label, self._gate_detail(key))
                          for key, label in store.GATE_LABELS])
        passed = 0
        known = 0
        for key, _label in store.GATE_LABELS:
            value = run.gates.get(key)
            self.gates.set(key, value, self._gate_detail(key))
            if value is None:
                continue
            known += 1
            passed += 1 if value else 0""",
        """    def _render_gates(self, run: store.RunInfo) -> None:
        # Every gate the run actually produced, labelled ones first and anything new by its own
        # name: a gate that is missing from the label table must still be visible, or a failing run
        # reads as a clean pass (round 315: launch_balance was invisible and 7/7 was shown).
        labelled = list(store.GATE_LABELS)
        known_keys = {key for key, _label in labelled}
        rows = labelled + [(key, key) for key in run.gates if key not in known_keys]
        self.gates.build([(key, label, self._gate_detail(key)) for key, label in rows])
        passed = 0
        known = 0
        for key, _label in rows:
            value = run.gates.get(key)
            self.gates.set(key, value, self._gate_detail(key))
            if value is None:
                continue
            known += 1
            passed += 1 if value else 0""",
    ),
    (
        """        failed = [label for key, label in store.GATE_LABELS if run.gates.get(key) is False]""",
        """        failed = [label for key, label in rows if run.gates.get(key) is False]""",
    ),
])

print("all patches applied")
