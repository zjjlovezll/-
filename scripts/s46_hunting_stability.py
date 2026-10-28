"""Is the curved state unstable, or merely slow?  Read the eigenvalues at the seated state.

Rounds 202-204 showed the net lateral force on R = 1100 m at 80 km/h growing from 53.5 % of
m v^2/R at 0.34 s to 135.3 % at 0.60 s, and to 190.1 % when the creep is at Kalker scale.  Time
integration says "it grows"; it does not say *which mode* grows, nor whether the growth is a
transient that would decay if the vehicle had one more physical ingredient (a yaw damper) or a
genuine instability of the state.

This script answers that by linearising the right-hand side at the seated state and asking for the
eigenvalues.  A positive real part is growth; the eigenvector says which coordinates carry it.
Cheap: seating is seconds, no integration, so the whole matrix over creep scale and yaw damping
fits in a couple of minutes.

Pre-registered before the runs (this docstring is the record):

    quantity     max real part of the eigenvalues of  d/dt [q, v] = [v, f(q,v)/m]
    sweep        creep in {frozen 5.0e5/1.0e6, Kalker 2.5e6/3.5e6}
                 x yaw damping c_yaw in {0, 2.0e4, 1.0e5, 5.0e5} N.m.s/rad
    reading      a configuration is *stable at this state* only if max Re(lambda) < 0;
                 the mode is named by the share of |eigenvector| carried by the yaw rows and the
                 lateral y rows of the wheelsets
    rule         no parameter is adopted from this script alone; it selects which ingredient
                 the time integration must then be run with

Usage::

    python -X utf8 scripts/s46_hunting_stability.py
"""

from __future__ import annotations

import importlib.util
import json
import pathlib
import sys

import numpy as np

from velch.jacobian import JacobianAssembler
from velch.vehicle import load_vehicle_case

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "reports" / "curve_hunting_2026-10-28"
SPEED_KMH = 80.0
RADIUS_M = 1100.0
WHEEL_RADIUS_M = 0.43
DEMAND_N = 21_842.4

CREEP = {"frozen": None, "kalker": "kalker"}          # None -> the case's own 5.0e5 / 1.0e6
YAW_DAMPING = {"c0": 0.0, "c2e4": 2.0e4, "c1e5": 1.0e5, "c5e5": 5.0e5}


def _builder():
    spec = importlib.util.spec_from_file_location(
        "s32_curved_station_table", ROOT / "scripts" / "s32_curved_station_table.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def seated_case(builder, *, creep: str | None, c_yaw: float, name: str):
    """Seat the curved case with only a yaw damper changed; nothing else moves."""
    path = builder.build(
        duration_s=0.01, radius_m=RADIUS_M, tangent_m=30.0, step_m=0.1, span_m=150.0,
        run_at_m=30.0, seat_at_m=30.0,
        creep_kalker=creep == "kalker",
        primary_lateral_damping=(0.0, c_yaw) if c_yaw else None,
        curvature_force=True,
    )
    case = load_vehicle_case(path)
    from velch.vehicle_solver import VehicleDynamics, _seat
    dynamics = VehicleDynamics(case)
    speed = float(case.vehicle.travel_speed_m_s)
    velocity = np.zeros(dynamics.dimension)
    for body in dynamics.topology.bodies:
        if "spin" in body.dof:
            velocity[dynamics.topology.require(body.id, "spin")] = speed / WHEEL_RADIUS_M
    seated, residual = _seat(case, dynamics, np.zeros(dynamics.dimension), velocity)
    return case, dynamics, seated, velocity, residual


def describe_modes(values, vectors, yaw_rows: list[int], y_rows: list[int]) -> list[dict]:
    """Turn eigenvalues into rows, sorted by growth rate, each with its yaw/lateral share.

    Kept separate from the dynamics so the contract itself is testable: sorted descending by real
    part, shares in [0, 1], and a frequency in Hz (a negative real part alone does not say whether
    a mode is a wobble or a drift -- 7 Hz and 0 Hz are different physics).
    """
    out = []
    for value, vector in zip(values, vectors):
        weight = np.abs(vector)
        total = float(weight.sum())
        out.append({
            "re": float(value.real),
            "im": float(value.imag),
            "frequency_hz": float(abs(value.imag) / (2.0 * np.pi)),
            "yaw_share": float(weight[yaw_rows].sum() / total) if total else 0.0,
            "lateral_share": float(weight[y_rows].sum() / total) if total else 0.0,
        })
    out.sort(key=lambda row: row["re"], reverse=True)
    return out


def _wheel_rows(topology) -> tuple[list[int], list[int]]:
    yaw_rows, y_rows = [], []
    for body in topology.bodies:
        if not body.id.startswith("wheelset"):
            continue
        if "yaw" in body.dof:
            yaw_rows.append(topology.require(body.id, "yaw"))
        if "y" in body.dof:
            y_rows.append(topology.require(body.id, "y"))
    return yaw_rows, y_rows


def modes(dynamics, q: np.ndarray, v: np.ndarray) -> list[dict]:
    """Eigenvalues of the linearisation at this state, with the wheelset content of each."""
    block = JacobianAssembler(dynamics).full(0.0, q, v)
    values, vectors = np.linalg.eig(block)
    yaw_rows, y_rows = _wheel_rows(dynamics.topology)
    return describe_modes(values, vectors, yaw_rows, y_rows)


def main(argv: list[str]) -> int:
    builder = _builder()
    rows = []
    for creep_label, creep in CREEP.items():
        for damping_label, c_yaw in YAW_DAMPING.items():
            case, dynamics, seated, velocity, residual = seated_case(
                builder, creep=creep, c_yaw=c_yaw,
                name=f"{creep_label}_{damping_label}")
            table = modes(dynamics, seated, velocity)
            top = table[0]
            rows.append({
                "creep": creep_label, "c_yaw_nm_s_rad": c_yaw,
                "seat_residual_n": residual,
                "max_real_part": top["re"],
                "top_frequency_hz": top["frequency_hz"],
                "top_yaw_share": top["yaw_share"],
                "top_lateral_share": top["lateral_share"],
                "stable": top["re"] < 0.0,
                "top_five": table[:5],
                "case": case.case_id,
            })
            print(f"{creep_label:<7} c_yaw {c_yaw:>8.0f}  seat {residual:.1e} N  "
                  f"max Re(lambda) {top['re']:+.4f} 1/s at {top['frequency_hz']:8.2f} Hz  "
                  f"yaw {top['yaw_share']:.2f} lat {top['lateral_share']:.2f}  "
                  f"{'STABLE' if top['re'] < 0 else 'GROWS'}")
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "hunting.json").write_text(
        json.dumps({"speed_kmh": SPEED_KMH, "radius_m": RADIUS_M, "demand_n": DEMAND_N,
                    "rows": rows}, indent=2) + "\n", encoding="utf-8")
    stable = [row for row in rows if row["stable"]]
    print()
    print(f"{len(stable)} of {len(rows)} configurations are stable at the seated state")
    print(f"report {OUT / 'hunting.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
