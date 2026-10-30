"""Write and load the baseline straight case out of the turnout DB.

Both rails come from the same section file, mirrored, so the pair is symmetric by
construction -- the 13.2 mm crown-datum mismatch of the inherited case cannot occur.
Right rail keeps the three bodied lines (stock / blade+wing / point rail) so the design
lowering lives in the section geometry rather than in a z-offset table.

    python -X utf8 scripts/s85_db_case.py [--check]
"""
from __future__ import annotations

import argparse
import json
import pathlib
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "vehicles" / "turnouts" / "CN60-1100-1_18"
STOCK = "jbg-20200418-R.txt"
LINES = {
    "stock": "07(009)-Mileage-qjbg.txt",
    "blade": "07(009)-Mileage-zjg_zgyg_250722.txt",
    "frog": "07(009)-Mileage-cxg-250801.txt",
}


def lib(name: str) -> str:
    return f"lib:turnouts/CN60-1100-1_18/sections/{name}"


def read_table(name: str) -> list[tuple[float, str]]:
    rows: list[tuple[float, str]] = []
    for line in (DB / "mileage" / name).read_text(encoding="utf-8", errors="replace").splitlines():
        parts = line.replace("\t", " ").split()
        if len(parts) < 2:
            continue
        try:
            rows.append((float(parts[0]), parts[1]))
        except ValueError:
            continue
    return rows


def read_columns(path: Path) -> tuple[list[float], list[float]]:
    ys: list[float] = []
    zs: list[float] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        parts = line.replace(",", " ").split()
        if len(parts) < 2:
            continue
        try:
            y, z = float(parts[0]), float(parts[1])
        except ValueError:
            continue
        ys.append(y)
        zs.append(z)
    return ys, zs


def crown_y_m(file_name: str) -> float:
    """Lateral position of the rail crown, measured in the section file itself.

    These sections store ``z`` growing downward, so the running surface is the *minimum* z and the
    crown is the y at which it occurs.  This is the number that has to be cancelled when the pair is
    placed, and it differs per section (measured +6.915 mm for the stock profile), which is what made
    the inherited case 13.2 mm asymmetric.
    """
    ys, zs = read_columns(DB / "sections" / file_name)
    if not ys:
        return 0.0
    return ys[min(range(len(zs)), key=lambda i: zs[i])]


# The contact point of a 1:40 rail under an LMA tread is NOT the crown: measured by walking the
# crown outward from the wheel centre, the seat converges with eight wheels at exactly 1.000x share
# for every offset in 12.0-13.7 mm, and loses contact below 10 mm (1087 kN pressed on the shoulder)
# and above 14 mm (0.00 kN).  13.0 mm is the middle of that fitted window.  The earlier "symmetric
# crown" rule (offset 0) was wrong: it put the wheel on the field-side shoulder and tripped the slope
# guard at 50 m.
CROWN_OFFSET_M = 13.0e-3


def station_profile(file_name: str, *, side: int, y_sign: int) -> dict:
    # crown of the pair sits at side * 0.7465 m; the profile's own crown y is cancelled here.
    y_offset = side * (0.7465 + CROWN_OFFSET_M) - y_sign * crown_y_m(file_name)
    return {
        "file": lib(file_name),
        "format": "prr" if file_name.lower().endswith((".prr", ".prw")) else "txt",
        "units": "m",
        "y_sign": y_sign,
        "y_offset_m": y_offset,
        "z_sign": -1,
    }


def station(mileage: float, file_name: str, *, side: int, y_sign: int, tag: str) -> dict:
    return {
        "s_m": float(mileage),
        "id": f"{tag}{int(round(mileage * 1000)):08d}",
        "profile": station_profile(file_name, side=side, y_sign=y_sign),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="load and seat the case after writing it")
    ap.add_argument("--seat", action="store_true")
    args = ap.parse_args()

    wheel_source = Path(r"G:\研究生\动力学\CRH380A_纯刚性模型\database\database\wheel_rail_profiles\LMA.prw")
    wheel_target = DB / "sections" / wheel_source.name
    if not wheel_target.exists():
        shutil.copy2(wheel_source, wheel_target)
        print(f"copied wheel profile -> {wheel_target.name}")

    stock_rows = read_table(LINES["stock"])
    blade_rows = read_table(LINES["blade"])
    frog_rows = read_table(LINES["frog"])

    left = {
        "id": "left",
        "wheel_id": "L",
        "mass_y_kg": 120.0,
        "mass_z_kg": 120.0,
        "support": {"k_y_n_m": 3.0e7, "c_y_n_s_m": 2.0e4, "k_z_n_m": 5.0e7, "c_z_n_s_m": 4.0e4},
        "stations": [station(m, f, side=-1, y_sign=-1, tag="lf") for m, f in stock_rows],
    }
    right_stock = [station(m, f, side=1, y_sign=1, tag="rt") for m, f in stock_rows]
    right_bodies = [
        {
            "id": "stock",
            "stations": right_stock,
        },
        {
            "id": "blade",
            "stations": [
                station(m, f, side=1, y_sign=1, tag="bl")
                for m, f in blade_rows
                if 50.578 <= m <= 104.419
            ],
        },
        {
            "id": "frog",
            "stations": [
                station(m, f, side=1, y_sign=1, tag="fr") for m, f in frog_rows if 103.28 <= m <= 116.44
            ],
        },
    ]
    right = {
        "id": "right",
        "wheel_id": "R",
        "mass_y_kg": 120.0,
        "mass_z_kg": 120.0,
        "support": {"k_y_n_m": 3.0e7, "c_y_n_s_m": 2.0e4, "k_z_n_m": 5.0e7, "c_z_n_s_m": 4.0e4},
        "stations": right_stock,
        "bodies": right_bodies,
    }

    # station ids must be unique even where two table rows round to the same millimetre
    for stations in (
        left["stations"],
        right["stations"],
        *[body["stations"] for body in right_bodies],
    ):
        for position, item in enumerate(stations):
            prefix = "".join(ch for ch in item["id"] if ch.isalpha())
            item["id"] = f"{prefix}{position:05d}"

    base = json.loads(
        pathlib.Path(r"F:/velch_data/validation/crh380a_m/case_diverging_R1100.json").read_text(
            encoding="utf-8"
        )
    )
    case = dict(base)
    case["case_id"] = "turnout_cn60_1100_straight"
    case["purpose_detail"] = (
        "Baseline straight route of CN60-1100-1:18 from the local turnout DB. Right rail carries "
        "two extra bodies so the design lowering (blade 14.94 mm, point rail 13.70 mm) is section "
        "geometry, and every station cancels its own crown y so the pair is symmetric by construction."
    )
    case.pop("path", None)
    case.pop("initial_state", None)
    # The wheel surface is the one profile that must stay in WHEEL coordinates: its y is measured
    # from the wheel's own centre, and `lateral_offset_m` puts it on the axle.  Reusing the rail
    # helper here would subtract the rail crown (-0.6772 m) and land the tread 0.68 m outboard of the
    # axle -- measured 0.00 kN of contact at every sink from 0 to 20 mm, against 66.89 kN in the old
    # case at 0.2 mm.
    def wheel_profile(*, side: int, y_sign: int) -> dict:
        block = station_profile(wheel_source.name, side=side, y_sign=y_sign)
        block.pop("y_offset_m", None)
        block["z_offset_m"] = -0.43
        return block

    case["wheels"] = [
        {"id": "L", "lateral_offset_m": -0.7465, "profile": wheel_profile(side=-1, y_sign=-1)},
        {"id": "R", "lateral_offset_m": 0.7465, "profile": wheel_profile(side=1, y_sign=1)},
    ]
    case["rail_templates"] = [left, right]
    case["vehicle"]["travel_speed_m_s"] = 80.0 / 3.6
    case["run"] = {
        "method": "DOP853",
        "x_start_m": 40.0,
        "seat_x_start_m": 40.0,
        "duration_s": 0.02,
        "output_step_s": 0.0005,
        "max_solver_step_s": 1e-4,
        "rtol": 1e-6,
        "atol": 1e-8,
        "maximum_penetration_m": 0.003,
        "maximum_abs_contact_slope": 1.0,
    }
    out = DB / "cases" / "straight.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(case, ensure_ascii=False, indent=1) + chr(10)
    out.write_text(payload, encoding="utf-8", newline=chr(10))
    print(f"wrote {out} ({out.stat().st_size / 1e3:.0f} kB), crown stock {crown_y_m(STOCK) * 1e3:+.3f} mm")
    print(f"  stations: left {len(left['stations'])}, "
          + ", ".join(f"{body['id']} {len(body['stations'])}" for body in right_bodies))

    if not (args.check or args.seat):
        return 0
    from velch.vehicle import load_vehicle_case
    from velch.vehicle_solver import VehicleDynamics

    loaded = load_vehicle_case(out)
    dynamics = VehicleDynamics(loaded)
    print(f"loaded: dimension {dynamics.dimension}, rails {len(loaded.rails)}")
    for rail in loaded.rails:
        bodies = getattr(rail, "bodies", None) or ()
        print(f"  {rail.id:12s} bodies {1 + len(bodies)} {[getattr(b, 'id', '?') for b in bodies]}")
    if args.seat:
        import numpy as np
        from velch.vehicle_solver import _seat

        q0 = np.zeros(dynamics.dimension)
        seated, residual = _seat(loaded, dynamics, q0, np.zeros(dynamics.dimension))
        dynamics.placement_enabled = True
        _ = dynamics.evaluate(0.0, seated, np.zeros(dynamics.dimension))
        print(f"seat residual {residual:.3e} N")
        for rail_id, entry in dynamics.body_contacts.items():
            for body_id, response in entry.items():
                geometry = response.geometry
                pen = getattr(geometry, "penetration_m", float("nan")) if geometry else float("nan")
                print(
                    f"  {rail_id:12s} {body_id:8s} N {response.normal_force_n/1e3:8.2f} kN  "
                    f"pen {pen*1e6:8.2f} um"
                )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
