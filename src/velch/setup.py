"""One setup file, one entry point, one parameter port: the run path a case is supposed to use.

Why this exists
---------------
Until round 312 a run was "pick a case JSON, then maybe override the speed from a script".  That
route is what broke 60 km/h: ``scripts/s99_run_archive.py`` patched the *loaded* case
(``apply_speed``), and the wheelset spin is derived from ``travel_speed_m_s`` **inside the loader**
(``vehicle.py:605``), so the override produced a run whose declared speed was 60 km/h while its
wheelsets still turned as if at 80 (B053: ``|spin*r - travel| / travel = 0.333`` at the launch).
The run then started 5.7x further from equilibrium than the 80 km/h run on the same case and read
noise for the first 0.54 s.

So the rule here is the opposite of patching: **the speed is written into the case file and the case
is loaded again**.  Everything derived from the speed -- travel, wheelset spin, the creep reference,
the speed schedule -- is then computed once, by the one function that already knew how to do it.

What a setup file looks like
----------------------------
::

    {
      "label": "turnout_straight",
      "case": "vehicles/turnouts/CN60-1100-1_18/cases/straight_one_set.json",
      "speed_kmh": 80.0,
      "duration_s": 0.02,
      "output_step_s": 0.0005,
      "report_launch": true,
      "prebalance": {
        "equilibrate_vertical": true,
        "seat_lateral": true,
        "seat_modal_scales": [1.0, 0.8, 0.95, 1.05, 0.5]
      },
      "notes": {"campaign": "straight-pair"}
    }

``speed_kmh`` is the knob.  ``prebalance`` is the second knob group: it decides how the vehicle is
seated before the clock starts, and nothing in it is a tolerance -- a scale list is a list of
*starting points*, and the seat either closes to 0.1 N or the run says it did not.

Ports
-----
``apply_overrides`` accepts ``name=value`` strings on the command line, refuses unknown names (with
the list of legal ones) and refuses values outside the documented range, so a typo cannot silently
run something else.  ``--set speed.kmh=60`` is the whole of "change one parameter and run".
"""
from __future__ import annotations

import dataclasses
import hashlib
import json
import pathlib
from typing import Any

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]

#: Legal override names -> (dotted target, parser, allowed range).  Kept explicit so ``--set`` can
#: print the menu and so a misspelling is an error instead of a second parameter that does nothing.
OVERRIDES: dict[str, tuple[str, str, tuple[float, float] | None]] = {
    "speed.kmh": ("speed_kmh", "float", (0.1, 400.0)),
    "duration.s": ("duration_s", "float", (1.0e-6, 120.0)),
    "output_step.s": ("output_step_s", "float", (1.0e-9, 10.0)),
    "report_launch": ("report_launch", "bool", None),
    "label": ("label", "str", None),
    "prebalance.equilibrate_vertical": ("prebalance.equilibrate_vertical", "bool", None),
    "prebalance.seat_lateral": ("prebalance.seat_lateral", "bool", None),
    "prebalance.seat_modal_scales": ("prebalance.seat_modal_scales", "floats", None),
    "reading.window_m": ("stationarity_window_m", "window", (0.0, 1.0e4)),
    "start.x_m": ("start_x_m", "float", (0.0, 1.0e3)),
    "seat.start_m": ("seat_start_m", "float", (0.0, 1.0e3)),
}

#: Every key a setup file may carry.  Anything else is a typo, not an extension point.
SETUP_KEYS = ("label", "case", "speed_kmh", "duration_s", "output_step_s", "report_launch",
              "prebalance", "stationarity_window_m", "start_x_m", "seat_start_m", "notes")
PREBALANCE_KEYS = ("equilibrate_vertical", "seat_lateral", "seat_modal_scales")


@dataclasses.dataclass(frozen=True)
class Setup:
    """A resolved-by-file description of one run: which case, how fast, how long, how seated."""

    label: str
    case: str
    speed_kmh: float
    duration_s: float
    output_step_s: float
    report_launch: bool = True
    #: ``[start, end]`` mileage of the reading window, or ``None`` for no claim.  Gate 9 is only
    #: produced inside a declared window, so this is the one port that decides whether a run is
    #: allowed to say "these samples are a reading".
    stationarity_window_m: tuple[float, float] | None = None
    #: Mileage where the clock starts, and where the vehicle is seated; ``None`` keeps the case's
    #: own numbers.  These two are why a declared reading window can be reached at all: the case
    #: starts at 40 m (front axle 50 m), while the measurement window is the front axle's 56-65 m,
    #: so a run that does not say where it starts cannot be the run the window describes.
    start_x_m: float | None = None
    seat_start_m: float | None = None
    prebalance: dict[str, Any] = dataclasses.field(default_factory=dict)
    notes: dict[str, str] = dataclasses.field(default_factory=dict)
    source: str = ""

    @property
    def slug(self) -> str:
        return f"{self.label}-{self.speed_kmh:06.2f}kmh"


@dataclasses.dataclass(frozen=True)
class ResolvedRun:
    """What will actually run, plus the table of resolved parameters and where each came from."""

    setup: Setup
    case_path: pathlib.Path
    case: Any
    digest: str
    table: tuple[dict[str, Any], ...]
    overrides: tuple[str, ...]


def _positive(name: str, value: float, low: float, high: float) -> float:
    number = float(value)
    if not (low <= number <= high):
        raise ValueError(f"{name} must be within [{low}, {high}], got {value!r}")
    return number


def _window(name: str, value: Any) -> tuple[float, float] | None:
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


def load_setup(path: str | pathlib.Path) -> Setup:
    """Read and validate a setup file.  Unknown keys are refused, not ignored."""
    target = pathlib.Path(path)
    if not target.exists():
        raise ValueError(f"setup file not found: {target}")
    raw = json.loads(target.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"{target}: a setup file is a JSON object")
    unknown = sorted(set(raw) - set(SETUP_KEYS))
    if unknown:
        raise ValueError(f"{target}: unknown key(s) {unknown}; legal keys are {list(SETUP_KEYS)}")
    for required in ("label", "case", "speed_kmh"):
        if required not in raw:
            raise ValueError(f"{target}: missing required key {required!r}")
    prebalance = dict(raw.get("prebalance") or {})
    unknown_pre = sorted(set(prebalance) - set(PREBALANCE_KEYS))
    if unknown_pre:
        raise ValueError(f"{target}: unknown prebalance key(s) {unknown_pre}; "
                         f"legal keys are {list(PREBALANCE_KEYS)}")
    if "seat_modal_scales" in prebalance:
        prebalance["seat_modal_scales"] = [float(value) for value in prebalance["seat_modal_scales"]]
        if not prebalance["seat_modal_scales"]:
            raise ValueError(f"{target}: seat_modal_scales must not be empty")
        if prebalance["seat_modal_scales"][0] != 1.0:
            raise ValueError(f"{target}: seat_modal_scales must start at 1.0 (the untouched state is "
                             "always tried first), got %r" % (prebalance["seat_modal_scales"],))
    return Setup(
        label=str(raw["label"]),
        case=str(raw["case"]),
        speed_kmh=_positive("speed_kmh", raw["speed_kmh"], 0.1, 400.0),
        duration_s=_positive("duration_s", raw.get("duration_s", 0.02), 1.0e-6, 120.0),
        output_step_s=_positive("output_step_s", raw.get("output_step_s", 5.0e-4), 1.0e-9, 10.0),
        report_launch=bool(raw.get("report_launch", True)),
        stationarity_window_m=_window(f"{target}: stationarity_window_m",
                                     raw.get("stationarity_window_m")),
        start_x_m=(None if raw.get("start_x_m") is None
                   else _positive("start_x_m", raw["start_x_m"], 0.0, 1.0e3)),
        seat_start_m=(None if raw.get("seat_start_m") is None
                      else _positive("seat_start_m", raw["seat_start_m"], 0.0, 1.0e3)),
        prebalance=prebalance,
        notes={str(k): str(v) for k, v in (raw.get("notes") or {}).items()},
        source=str(target),
    )


def _parse(kind: str, text: str) -> Any:
    if kind == "float":
        return float(text)
    if kind == "str":
        return text
    if kind == "floats":
        return [float(part) for part in text.replace(";", ",").split(",") if part.strip()]
    if kind == "window":
        parts = [part for part in text.replace(";", ",").split(",") if part.strip()]
        if not parts or parts[0].strip().lower() in {"none", "off", "no"}:
            return None
        if len(parts) != 2:
            raise ValueError(f"expected two mileages (start,end) or 'none', got {text!r}")
        return [float(parts[0]), float(parts[1])]
    if kind == "bool":
        lowered = text.strip().lower()
        if lowered in {"1", "true", "yes", "on"}:
            return True
        if lowered in {"0", "false", "no", "off"}:
            return False
        raise ValueError(f"expected a boolean, got {text!r}")
    raise AssertionError(kind)


def apply_overrides(setup: Setup, assignments: list[str] | tuple[str, ...]) -> tuple[Setup, tuple[str, ...]]:
    """Return ``setup`` with ``name=value`` ports applied, and the ports that changed anything.

    A name that is not in :data:`OVERRIDES` is refused together with the legal list: a parameter port
    that silently does nothing is worse than no port at all (that is how ``--speed-kmh`` produced
    three "different" runs with one onset time, B052).
    """
    if not assignments:
        return setup, ()
    updated = dataclasses.asdict(setup)
    updated["prebalance"] = dict(updated["prebalance"])
    applied: list[str] = []
    for item in assignments:
        if "=" not in item:
            raise ValueError(f"--set needs name=value, got {item!r}")
        name, text = (part.strip() for part in item.split("=", 1))
        if name not in OVERRIDES:
            raise ValueError(f"unknown parameter {name!r}; legal names are {sorted(OVERRIDES)}")
        target, kind, limits = OVERRIDES[name]
        value = _parse(kind, text)
        if limits is not None and value is not None:
            if kind == "window":
                low, high = limits
                start, end = (_positive(name, part, low, high) for part in value)
                if not start < end:
                    raise ValueError(f"{name} needs start < end, got {text!r}")
                value = (start, end)
            else:
                value = _positive(name, value, *limits)
        if isinstance(target, str) and target.startswith("prebalance."):
            updated["prebalance"][target.split(".", 1)[1]] = value
        else:
            updated[target] = value
        applied.append(f"{name}={value}")
    source = setup.source
    rebuilt = Setup(**{**updated, "source": source})
    return rebuilt, tuple(applied)


def _write_case(setup: Setup, out_dir: pathlib.Path) -> tuple[pathlib.Path, str]:
    """Materialise the setup into a case file: the speed goes *into the file*, then it is loaded.

    That order is the whole point.  ``apply_speed`` patched a loaded case and left the wheelset spin
    at the old speed (B053), so the same function that knows how to derive the spin never ran.
    """
    base = pathlib.Path(setup.case)
    if not base.is_absolute():
        base = REPO_ROOT / base
    if not base.exists():
        raise ValueError(f"case not found: {base}")
    raw = json.loads(base.read_text(encoding="utf-8"))
    run = dict(raw.get("run") or {})
    profile = run.get("speed_profile")
    if profile is not None and not (isinstance(profile, dict) and "constant" in profile):
        raise ValueError(
            f"{base}: this case declares a multi-leg speed_profile; speed.kmh cannot re-point a "
            "schedule without changing its legs, so edit the case instead")
    run["speed_profile"] = {"constant": {"speed_kmh": float(setup.speed_kmh)}}
    run["duration_s"] = float(setup.duration_s)
    run["output_step_s"] = float(setup.output_step_s)
    run["report_launch"] = bool(setup.report_launch)
    if setup.stationarity_window_m is not None:
        # Only written when claimed: materialising a null key changed ``case_sha256`` and split the
        # archive id of an unchanged setup from its earlier runs (round 315).
        run["stationarity_window_m"] = [float(setup.stationarity_window_m[0]),
                                        float(setup.stationarity_window_m[1])]
    if setup.start_x_m is not None:
        run["x_start_m"] = float(setup.start_x_m)
    if setup.seat_start_m is not None:
        run["seat_x_start_m"] = float(setup.seat_start_m)
    prebalance = setup.prebalance
    if "equilibrate_vertical" in prebalance:
        raw["equilibrate_vertical"] = bool(prebalance["equilibrate_vertical"])
    if "seat_lateral" in prebalance:
        run["seat_lateral"] = bool(prebalance["seat_lateral"])
    if "seat_modal_scales" in prebalance:
        run["seat_modal_scales"] = [float(value) for value in prebalance["seat_modal_scales"]]
    raw["run"] = run
    raw["case_id"] = setup.slug
    detail = str(raw.get("purpose_detail") or "")
    stamp = (f"resolved by velch.setup from {pathlib.Path(setup.source).name} at "
             f"{setup.speed_kmh:g} km/h")
    raw["purpose_detail"] = f"{detail} | {stamp}" if stamp not in detail else detail
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{setup.slug}.json"
    text = json.dumps(raw, indent=1, ensure_ascii=False)
    path.write_text(text + "\n", encoding="utf-8")
    return path, hashlib.sha256(text.encode("utf-8")).hexdigest()


def check_kinematics(case, tolerance: float = 1.0e-3) -> float:
    """Refuse a case whose wheelset spin does not match the speed it is carried at.

    ``spin * r != travel`` is not a detail: the mismatch is booked as longitudinal creep, it
    saturates the friction circle and eats the lateral force through ``hypot``.  At 60 km/h carried
    at the 80 km/h spin the relative slip is 0.333 -- six times the ``spin_tracking`` gate's 1 % --
    and nothing before round 312 tested the *initial* state for it.
    """
    from .topology import topology_for

    topology = topology_for(case)
    travel = float(case.vehicle.travel_speed_m_s)
    radius = float(case.vehicle.nominal_wheel_radius_m)
    denominator = max(abs(travel), 1.0e-12)
    worst = 0.0
    for axle in range(len(case.vehicle.axle_offsets_m)):
        index = topology.require(f"wheelset{axle + 1}", "spin")
        spin = float(case.initial_v[index])
        worst = max(worst, abs(spin * radius - travel) / denominator)
    if worst > tolerance:
        raise ValueError(
            f"wheelset spin does not match the declared speed: |spin*r - travel|/travel = "
            f"{worst:.6f} > {tolerance:g}.  Reload the case after changing the speed instead of "
            "patching the loaded one (velch.setup.resolve does that).")
    return worst


def resolve(setup: Setup, overrides: list[str] | tuple[str, ...] = (),
            out_dir: str | pathlib.Path | None = None) -> ResolvedRun:
    """Turn a setup (plus ports) into a loaded case, and the parameter table of what will run."""
    from .vehicle import load_vehicle_case

    resolved, applied = apply_overrides(setup, overrides)
    directory = pathlib.Path(out_dir) if out_dir is not None else REPO_ROOT / "scratch" / "setups"
    case_path, digest = _write_case(resolved, directory)
    case = load_vehicle_case(case_path)
    if resolved.stationarity_window_m is not None:
        low, high = (float(value) for value in resolved.stationarity_window_m)
        reach = resolved.duration_s * (resolved.speed_kmh / 3.6)
        if reach + 1.0e-9 < high - low:
            raise ValueError(
                f"the run is too short for the declared reading window: {reach:.3f} m of "
                f"{high - low:.3f} m at {resolved.speed_kmh:g} km/h for "
                f"{resolved.duration_s:g} s. Lengthen duration.s, narrow reading.window_m, or set "
                f"reading.window_m=none to run without a stationarity claim.")
    spin_relative = check_kinematics(case)
    speed_ms = resolved.speed_kmh / 3.6
    radius = float(case.vehicle.nominal_wheel_radius_m)
    table = (
        {"parameter": "speed.kmh", "value": f"{resolved.speed_kmh:g}", "unit": "km/h",
         "source": "override" if any(port.startswith("speed.kmh") for port in applied) else "setup"},
        {"parameter": "travel", "value": f"{case.vehicle.travel_speed_m_s:.6f}", "unit": "m/s",
         "source": "derived from speed.kmh"},
        {"parameter": "wheelset.spin", "value": f"{speed_ms / radius:.6f}", "unit": "rad/s",
         "source": "derived: travel / r, checked to 1e-3"},
        {"parameter": "spin.relative_max", "value": f"{spin_relative:.3e}", "unit": "-",
         "source": "check_kinematics"},
        {"parameter": "duration.s", "value": f"{resolved.duration_s:g}", "unit": "s",
         "source": "override" if any(port.startswith("duration") for port in applied) else "setup"},
        {"parameter": "output_step.s", "value": f"{resolved.output_step_s:g}", "unit": "s",
         "source": "override" if any(port.startswith("output_step") for port in applied) else "setup"},
        {"parameter": "report_launch", "value": str(resolved.report_launch), "unit": "-",
         "source": "override" if any(port.startswith("report_launch") for port in applied)
                   else "setup"},
        {"parameter": "reading.window_m",
         "value": ("none" if resolved.stationarity_window_m is None else
                   f"{float(resolved.stationarity_window_m[0]):g}.."
                   f"{float(resolved.stationarity_window_m[1]):g}"),
         "unit": "m",
         "source": "override" if any(port.startswith("reading.") for port in applied)
                   else "setup"},
        {"parameter": "start.x_m",
         "value": ("case" if resolved.start_x_m is None else f"{resolved.start_x_m:g}"),
         "unit": "m",
         "source": "override" if any(port.startswith("start.") for port in applied) else "setup"},
        {"parameter": "seat.start_m",
         "value": ("case" if resolved.seat_start_m is None else f"{resolved.seat_start_m:g}"),
         "unit": "m",
         "source": "override" if any(port.startswith("seat.start") for port in applied)
                   else "setup"},
        {"parameter": "prebalance", "value": json.dumps(resolved.prebalance, ensure_ascii=False),
         "unit": "-", "source": "setup/override"},
        {"parameter": "case", "value": str(case_path), "unit": "-", "source": "materialised"},
        {"parameter": "case.sha256", "value": digest[:16], "unit": "-", "source": "materialised"},
    )
    return ResolvedRun(setup=resolved, case_path=case_path, case=case, digest=digest,
                       table=table, overrides=applied)


def render_table(rows: tuple[dict[str, Any], ...]) -> str:
    """Fixed-width table so a run log can be diffed against the setup that produced it."""
    width = max(len(str(row["parameter"])) for row in rows) + 2
    lines = [f"{'parameter':<{width}}{'value':<44}{'unit':<10}source"]
    for row in rows:
        value = str(row["value"])
        if len(value) > 42:
            value = value[:39] + "..."
        lines.append(f"{row['parameter']:<{width}}{value:<44}{row['unit']:<10}{row['source']}")
    return "\n".join(lines)
