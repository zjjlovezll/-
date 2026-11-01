"""One entry point: read a setup file, apply one parameter port, run, archive, report.

    python -X utf8 scripts/s172_run_case.py --dry
    python -X utf8 scripts/s172_run_case.py --set speed.kmh=60 --duration 0.02
    python -X utf8 scripts/s172_run_case.py --set speed.kmh=80 --set prebalance.seat_modal_scales=1,0.8

Why this script exists
----------------------
The user's 2026-11-01 instruction is that a run should be "change one small parameter and go", the
way a Simpack model is re-solved with a new speed.  Before this script the answer to "what did I
change?" was spread over four places: the case JSON (which carries the speed profile), the solver's
``apply_speed``-style overrides in scripts (which patch a *loaded* case and therefore never re-derive
the wheelset spin -- B053, the reason the 60 km/h run started 5.7x further from equilibrium), the
seat's modal-scale list, and the archive metadata (which recorded neither the spin nor the modal
block).

This script is the single path:

1. a setup file says which case, how fast, how long, how the vehicle is seated;
2. ``--set`` changes one named parameter, with the legal names printed by ``--help`` and unknown names
   refused;
3. ``velch.setup.resolve`` writes the speed **into the case file** and loads it again, so travel,
   spin, the creep reference and the schedule are all derived once by the loader;
4. ``velch.setup.check_kinematics`` refuses a case whose spin does not match its speed;
5. the run is archived by the same writer the archive has always used (``s99_run_archive``), with the
   launch state included and the setup and ports recorded in the index row.

The exit code is not "the solver returned": it is 0 only if every gate passed **and** the recorded
launch state was balanced.  A run that reads its own transient must not be quotable by accident.
"""
from __future__ import annotations

import argparse
import importlib.util
import pathlib
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from velch.setup import OVERRIDES, load_setup, render_table, resolve  # noqa: E402
from velch.vehicle_solver import simulate_vehicle  # noqa: E402


def _archive() -> object:
    """Load ``s99_run_archive`` as a module: the archive format has exactly one implementation."""
    path = ROOT / "scripts" / "s99_run_archive.py"
    spec = importlib.util.spec_from_file_location("velch_run_archive", path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _launch_lines(launch: dict | None) -> list[str]:
    if launch is None:
        return ["launch state: not recorded (report_launch = false)"]
    lines = [
        f"launch state  balanced: {launch['balanced']}",
        f"  |modal|            {launch['modal_norm_m']:.4e} m",
        f"  modal force residual {launch['modal_residual_n']:.4e} N  (reported, not gated: "
        f"{100.0 * float(launch.get('modal_residual_share') or 0.0):.3f} % of the wheel load; "
        "stationarity decides)",
        f"  vertical preload   {launch['vertical_preload_residual_n']} N  (limit "
        f"{launch['criteria']['vertical_preload_n']:g} N)",
        f"  spin consistency   {launch['spin_relative_max']:.3e}  (limit "
        f"{launch['criteria']['spin_relative']:g})",
        f"  travel {launch['travel_m_s']:.6f} m/s, r = {launch['wheel_radius_m']:.6f} m",
    ]
    return lines


def main() -> int:
    parser = argparse.ArgumentParser(
        description="run one case from a setup file",
        epilog="parameter ports: " + ", ".join(sorted(OVERRIDES)))
    parser.add_argument("--setup", default="setups/one_set_straight.json",
                        help="setup file (default: setups/one_set_straight.json)")
    parser.add_argument("--set", action="append", default=[], metavar="NAME=VALUE",
                        help="override one parameter; unknown names are refused")
    parser.add_argument("--duration", type=float, default=None,
                        help="shorthand for --set duration.s=...")
    parser.add_argument("--output-step", type=float, default=None,
                        help="shorthand for --set output_step.s=...")
    parser.add_argument("--out-dir", default=None,
                        help="where the materialised case is written (default scratch/setups)")
    parser.add_argument("--note", action="append", default=[], metavar="KEY=VALUE")
    parser.add_argument("--dry", action="store_true", help="print the parameter table and stop")
    args = parser.parse_args()

    ports = list(args.set)
    if args.duration is not None:
        ports.append(f"duration.s={args.duration}")
    if args.output_step is not None:
        ports.append(f"output_step.s={args.output_step}")

    setup = load_setup(ROOT / args.setup if not pathlib.Path(args.setup).is_absolute() else args.setup)
    resolved = resolve(setup, ports, out_dir=args.out_dir)
    print(f"setup {setup.source}")
    print(render_table(resolved.table))
    if resolved.overrides:
        print("ports applied: " + "  ".join(resolved.overrides))
    if args.dry:
        return 0

    notes: dict[str, str] = {}
    for item in args.note:
        if "=" not in item:
            raise SystemExit(f"--note needs KEY=VALUE, got {item!r}")
        key, value = item.split("=", 1)
        notes[key.strip()] = value.strip()

    started = time.perf_counter()
    result = simulate_vehicle(resolved.case)
    wall_s = time.perf_counter() - started
    gates = (getattr(result, "summary", {}) or {}).get("gates") or {}
    launch = getattr(result, "launch", None)
    for line in _launch_lines(launch):
        print(line)
    archive = _archive()
    # ``resolved.setup`` is the setup *after* the ports; the outer ``setup`` is the file as
    # written.  Reading the outer one labelled a 60 km/h run ``-080.00kmh`` -- two archives, one
    # name, and the label is the only thing the reader trusts.
    run = resolved.setup
    entry = archive.write_archive(
        result, case=resolved.case, case_path=resolved.case_path, case_digest=resolved.digest,
        route=run.label, speed_kmh=run.speed_kmh, duration_s=run.duration_s,
        output_step_s=run.output_step_s, wall_s=wall_s, notes=notes, launch=launch,
        setup=str(pathlib.Path(args.setup)), overrides=resolved.overrides)
    print(f"{entry['run_id']}: frames {entry['frames']}  gates "
          f"{sum(bool(v) for v in gates.values())}/{len(gates)}  wall {wall_s:.1f} s")
    for name, value in gates.items():
        print(f"  {name}: {value}")
    print(f"data -> {entry['path']}")
    balanced = launch is None or bool(launch["balanced"])
    if not balanced:
        print("REFUSED: the launch state is not balanced, so this run reads its own transient; "
              "the archive is kept but its numbers must not be quoted.")
    return 0 if (gates and all(bool(v) for v in gates.values()) and balanced) else 1


if __name__ == "__main__":
    raise SystemExit(main())
