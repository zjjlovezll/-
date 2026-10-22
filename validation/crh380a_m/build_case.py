"""Build Velch v2 vehicle cases for the CRH380A_M Simpack model.

The vehicle parameters are transcribed from the Simpack text model
(CRH380A_M_Carbody/Bogie/Wheelset.spck subvariables). The rail geometry is
taken read-only from the track catalog produced by ``inspect-simpack-track``.
No Simpack solver mathematics is claimed here.

Two cases are written:

* ``case_A_plain.json``   both rails on one constant 60 kg section (control)
* ``case_B_turnout.json``  the real 236-station right-rail catalog, with the
  ten coincident stations resolved into explicit before/after branches

Usage::

    python build_case.py --mode plain
    python build_case.py --mode turnout
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

VEH = Path(__file__).resolve().parents[2]
CATALOG = VEH / "diagnostics" / "crh380a_m_track_catalog.json"
AUDIT = VEH / "diagnostics" / "crh380a_m_database_audit.json"
OUT_DIR = Path(__file__).resolve().parent

# ---------------------------------------------------------------------------
# Vehicle parameters, transcribed from the Simpack text model.
# Source: G:\研究生\动力学\CRH380A_纯刚性模型\database\database\mbs_db_substructure
#   CRH380A_M_Carbody.spck   $_CB_mass 34934  $_CB_Ixx 113200  $_CB_Iyy 1711800
#                            $_CB_Izz 1615300  $_CB_CG_z -1.55  $_CB_SecSpr_z -1.0
#   CRH380A_M_Bogie.spck     $_BF_mass 3300  Ixx 2673 Iyy 1807 Izz 3300
#                            $_BF_CG_z -0.51  $_BF_SecSpr_z -0.8  $_BF_SecSpr_y 2.46
#                            $_BF_PrimSpr_z -0.833  $_BF_PrimDamp_z -0.684
#                            $_PrimSpr_c_x/y 980000  c_z 1176000  _Prim_Damp_d 1e4
#                            $_SecSpr_c_x/y 160000  c_z 240000  _SecSpr_d_z 2e4
#                            $_SecDamp_AntiS_c 8850000  _d 2450000
#                            $_AxleGuide_mass 48.2  $_AxleGuide_Spr_z -0.585
#                            $_AxleGuide_BF_JOINT_c_x 13700000  _c_y 5490000
#   CRH380A_M_Wheelset.spck  $_WS_mass 1780  Ixx 949 Iyy 118 Izz 967
#                            $_WS_RWP_TrackGauge 1.435  TrackGaugeMeasPos 0.016
#                            $_WS_RWP_LatWheelDist 0.7465  NomWheelRadius 0.43
#                            $_WS_RWP_FricCoeff 0.4  YoungsModulus 2.1e11
#                            $_WS_RWP_PoissonNumber 0.28  ContactDamping 1e5
#                            rail.r/l.lat.dist 0.753  rail.sides 2
# ---------------------------------------------------------------------------
RAIL_LATERAL_DISTANCE_M = 0.753          # rail.r.lat.dist / rail.l.lat.dist
WHEEL_LATERAL_DISTANCE_M = 0.7465        # $_WS_RWP_LatWheelDist
GAUGE_M = 1.435                          # $_WS_RWP_TrackGauge
WHEEL_RADIUS_M = 0.43                    # $_WS_RWP_NomWheelRadius
SPEED_KMH = 350.0
SPEED_M_S = SPEED_KMH / 3.6

E_MODULUS = 2.1e11                       # $_WS_RWP_YoungsModulus
POISSON = 0.28                           # $_WS_RWP_PoissonNumber
EFFECTIVE_MODULUS = E_MODULUS / (2.0 * (1.0 - POISSON ** 2))   # 1.1392e11 Pa

VEHICLE = {
    "carbody": {
        "mass_kg": 34934.0,
        "roll_inertia_kg_m2": 113200.0,
        "pitch_inertia_kg_m2": 1711800.0,
        "yaw_inertia_kg_m2": 1615300.0,
    },
    "bogie": {
        "mass_kg": 3300.0,
        "roll_inertia_kg_m2": 2673.0,
        "pitch_inertia_kg_m2": 1807.0,
        "yaw_inertia_kg_m2": 3300.0,
    },
    "wheelset": {
        "mass_kg": 1780.0,
        "roll_inertia_kg_m2": 949.0,      # Ixx
        "spin_inertia_kg_m2": 118.0,      # Iyy
        "yaw_inertia_kg_m2": 967.0,       # Izz
    },
    "primary": {
        "k_y_n_m": 980000.0,              # $_PrimSpr_c_y
        "c_y_n_s_m": 0.0,
        "k_z_n_m": 1176000.0,             # $_PrimSpr_c_z
        "c_z_n_s_m": 10000.0,             # $_Prim_Damp_d
        # Not exposed by the .spck (the wheelset is guided by a stiff
        # axle-guide joint c_x 1.37e7 / c_y 5.49e6 plus traction rods).
        # Taken from the same train's MATLAB parameter set used by the
        # existing Velch v2 case, and flagged as an open item.
        "k_yaw_nm_rad": 1960000.0,
        "c_yaw_nm_s_rad": 0.0,
        "half_width_m": 1.0,              # $_WS_axle_length 2.0 / 2
        # height of the spring seat above each body centre of gravity
        "upper_anchor_height_m": -0.833 + 0.51,   # -0.323 (bogie frame side)
        "lower_anchor_height_m": -0.585,          # axle guide side
    },
    "secondary": {
        "k_y_n_m": 160000.0,              # $_SecSpr_c_y
        "c_y_n_s_m": 0.0,
        "k_z_n_m": 240000.0,              # $_SecSpr_c_z
        "c_z_n_s_m": 20000.0,             # $_SecSpr_d_z
        "k_yaw_nm_rad": 8850000.0,        # $_SecDamp_AntiS_c (anti-snake)
        "c_yaw_nm_s_rad": 2450000.0,      # $_SecDamp_AntiS_d
        "half_width_m": 1.23,             # $_BF_SecSpr_y 2.46 / 2
        "upper_anchor_height_m": -1.0 + 1.55,     # +0.55 (carbody side)
        "lower_anchor_height_m": -0.8 + 0.51,     # -0.29 (bogie side)
    },
    "bogie_half_spacing_m": 8.75,         # $_Bogie_Distance 17.5 / 2
    "wheelbase_m": 2.5,                   # $_Wheelset_Distance
    "wheel_center_height_m": WHEEL_RADIUS_M,
    "nominal_wheel_radius_m": WHEEL_RADIUS_M,
    "travel_speed_m_s": SPEED_M_S,
    "gravity_m_s2": 9.81,
    "drive_torque_per_wheelset_nm": 0.0,
}

CONTACT = {
    "normal_model": "hertz_effective_radius",
    "damping_model": "delta_half_velocity",
    "tangential_model": "sditt_cubic_saturation",
    "effective_modulus_pa": round(EFFECTIVE_MODULUS, 3),
    "effective_radius_m": 0.02,
    "normal_damping_n_s_m_1p5": 1000000.0,
    "friction_coefficient": 0.4,          # $_WS_RWP_FricCoeff
    "creep_stiffness_x_n": 1000000.0,
    "creep_stiffness_lateral_n": 500000.0,
    "reference_speed_floor_m_s": 0.1,
}

SUPPORT = {
    "k_y_n_m": 500000000.0,
    "c_y_n_s_m": 20000.0,
    "k_z_n_m": 400000000.0,
    "c_z_n_s_m": 10000.0,
}


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=("plain", "turnout"), required=True)
    ap.add_argument("--duration", type=float, default=0.05)
    ap.add_argument("--catalog", type=Path, default=CATALOG)
    ap.add_argument("--branches", choices=("forward", "inverted"), default="forward",
                    help="reading of the ten duplicate-mileage station pairs")
    args = ap.parse_args()

    cat = json.loads(args.catalog.read_text(encoding="utf-8"))
    audit = json.loads(AUDIT.read_text(encoding="utf-8"))
    refs = cat["profile_references"]
    left = sorted([r for r in refs if r["side"] == "left"], key=lambda r: r["index"])
    right = sorted([r for r in refs if r["side"] == "right"], key=lambda r: r["index"])
    wheel_ref = audit["wheel_profiles_referenced_directly"][0]
    wheel_prw = wheel_ref["path"]

    # --- wheels ---------------------------------------------------------
    wheels = []
    for wheel_id, sign in (("L", -1), ("R", 1)):
        wheels.append({
            "id": wheel_id,
            "lateral_offset_m": sign * WHEEL_LATERAL_DISTANCE_M,
            # PRW z is a radius offset from the nominal rolling circle (0 at the
            # tread, +0.028 at the flange tip). Velch wants the wheel surface
            # expressed in the wheel-centre frame (z = -radius), so the radius
            # is folded in here: z_local = -z_prw - 0.43.
            "profile": {"file": wheel_prw, "format": "prr", "units": "m", "y_sign": sign,
                        "z_sign": -1, "z_offset_m": -WHEEL_RADIUS_M},
        })

    # --- rail templates -------------------------------------------------
    def station(ref: dict, sid: str, sign: int) -> dict:
        return {
            "id": sid,
            "s_m": float(ref["station_m"]),
            "profile": {
                "file": ref["path"],
                "format": "prr",
                "units": "m",
                "y_sign": sign,
                "y_offset_m": sign * RAIL_LATERAL_DISTANCE_M,
                # PRR z grows downward from the running surface (0 at the crown,
                # +0.0299 at the head underside); Velch wants z up, 0 at the crown.
                "z_sign": -1,
            },
        }

    plain_file = left[0]["path"]
    if args.mode == "plain":
        left_stations = [
            {"id": "L0", "s_m": 0.0,
             "profile": {"file": plain_file, "format": "prr", "units": "m",
                         "y_sign": -1, "y_offset_m": -RAIL_LATERAL_DISTANCE_M, "z_sign": -1}},
            {"id": "L1", "s_m": 150.0,
             "profile": {"file": plain_file, "format": "prr", "units": "m",
                         "y_sign": -1, "y_offset_m": -RAIL_LATERAL_DISTANCE_M, "z_sign": -1}},
        ]
        right_stations = [
            {"id": "R0", "s_m": 0.0,
             "profile": {"file": plain_file, "format": "prr", "units": "m",
                         "y_sign": 1, "y_offset_m": RAIL_LATERAL_DISTANCE_M, "z_sign": -1}},
            {"id": "R1", "s_m": 150.0,
             "profile": {"file": plain_file, "format": "prr", "units": "m",
                         "y_sign": 1, "y_offset_m": RAIL_LATERAL_DISTANCE_M, "z_sign": -1}},
        ]
        branches = {}
        case_id = "crh380a_m_plain_section_350kmh"
        purpose = "engineering"
        purpose_detail = "CRH380A_M vehicle on one constant 60 kg rail section (control case)"
    else:
        left_stations = [station(r, f"L{r['index']:03d}", -1) for r in left]
        right_stations = [station(r, f"R{r['index']:03d}", 1) for r in right]
        branches = {}
        for pair in cat["coincident_stations"]:
            i, j = pair["indices"]
            key = str(float(pair["station_m"]))
            if args.branches == "inverted":
                # Sensitivity twin: at a duplicate mileage the later-listed
                # cross-section is taken to be the approach and the earlier one
                # the exit, i.e. the opposite of the default reading.
                branches[key] = {"before": f"R{j:03d}", "after": f"R{i:03d}"}
            else:
                branches[key] = {"before": f"R{i:03d}", "after": f"R{j:03d}"}
        case_id = "crh380a_m_turnout_350kmh"
        purpose = "engineering"
        purpose_detail = "CRH380A_M vehicle over the real 236-station turnout catalog"
        if args.branches == "inverted":
            case_id += "_branches_inverted"
            purpose_detail += " (inverted duplicate-mileage branch reading)"

    rail_templates = [
        {
            "id": "left", "wheel_id": "L",
            "mass_y_kg": 120.0, "mass_z_kg": 120.0, "support": SUPPORT,
            "stations": left_stations,
        },
        {
            "id": "right", "wheel_id": "R",
            "mass_y_kg": 120.0, "mass_z_kg": 120.0, "support": SUPPORT,
            "event_branches": branches,
            "stations": right_stations,
        },
    ]

    # --- initial state: 35 coordinates, seed a small tread penetration ---
    # LMA (PRW radius frame) against the 60 kg rail leaves a measured 0.265 mm
    # nominal gap at wheel_center_height = 0.43 m (see probe_contact.py), so the
    # seed has to sink past that gap or the preload solve starts in a flat
    # zero-contact region and its Jacobian is singular. The equilibrium itself is
    # whatever the static solve converges to.
    q = [0.0] * 35
    for axle in range(4):
        q[5 * axle + 1] = -0.0005

    case = {
        "schema_version": "velch-vehicle-v2",
        "case_id": case_id,
        "purpose": purpose,
        "purpose_detail": purpose_detail,
        "parameter_source": (
            "Simpack text model CRH380A_M_{Carbody,Bogie,Wheelset}.spck subvariables "
            "(masses, inertias, suspension stiffness/damping, rail geometry, contact "
            "material and friction); rail geometry read-only from "
            "diagnostics/crh380a_m_track_catalog.json"
        ),
        "source_evidence": {
            "simpack_model": r"G:\研究生\动力学\CRH380A_纯刚性模型\database\database\mbs_db_substructure\CRH380A_M_Carbody.spck",
            "simpack_sha256": audit.get("source_model_sha256"),
            "track_catalog": str(args.catalog),
            "track_catalog_sha256": sha256_of(args.catalog),
            "track_catalog_profile_set_sha256": audit.get("profile_set_sha256"),
            "wheel_profile_sha256": wheel_ref.get("sha256") or sha256_of(Path(wheel_prw)),
            "coincident_stations": [p["station_m"] for p in cat["coincident_stations"]],
            "declared_model_limits": [
                "rigid track: no rail mass, support stiffness or fastener compliance",
                "single equivalent rail per side per axle: no stock/switch/wing sub-rail split",
                "hertz_effective_radius normal law is a reduced-order substitute, not Simpack RWP",
                "no axlebox bodies (Simpack has four 48.2 kg axle guides on stiff joints)",
                "primary yaw stiffness is not exposed by the .spck; taken from Par_Vehicle_CRH380A_v6.m",
            ],
        },
        "vehicle": VEHICLE,
        "contact": CONTACT,
        "wheels": wheels,
        "rail_templates": rail_templates,
        "track_dynamics": {"kind": "rigid"},
        "equilibrate_vertical": True,
        "run": {
            "method": "DOP853",
            "x_start_m": 13.5,
            "duration_s": args.duration,
            "output_step_s": 0.0005,
            "max_solver_step_s": 0.0001,
            "rtol": 1e-6,
            "atol": 1e-8,
            "maximum_penetration_m": 0.003,
            "maximum_abs_contact_slope": 1.0,
        },
        "initial_state": {"q": q},
    }

    suffix = "" if args.branches == "forward" or args.mode == "plain" else "_branches_inverted"
    out = OUT_DIR / f"case_{'A_plain' if args.mode == 'plain' else 'B_turnout'}{suffix}.json"
    out.write_text(json.dumps(case, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"wrote {out}  ({out.stat().st_size:,} bytes)")
    print(f"  left stations {len(left_stations)}  right stations {len(right_stations)}  branches {len(branches)}")
    print(f"  duration {args.duration} s  speed {SPEED_KMH} km/h = {SPEED_M_S:.4f} m/s")
    print(f"  E_eff {EFFECTIVE_MODULUS:.4e} Pa  rails x4 axles = {2*4} patches, dof = 35")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
