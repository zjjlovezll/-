"""Extract selected, read-only vehicle topology statements from Simpack models.

This records model-file relationships, not proprietary solver equations or
runtime activation. Files are streamed and never modified.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

BASE = Path(r"H:\总的齿轨项目\总和1\直逆_修改降低值后设计 -上坡度\RACK_RAILWAY_VEHICLE - XNEW - M")
SOURCES = {
    "main": BASE / "main_model" / "VEH_GEAR0_FX_STR_RACKN_QY-Re1_cjy_whcl_zn_TE_USERFORCE_CG_120_cj1mm_segmented150_TE_STAGED.spck",
    "bogie_template": BASE / "database" / "DT_A_T_B_Re1_cjy.spck",
    "wheelset_template": BASE / "database" / "DT_A_T_WS_Re1_cjy.spck",
}
NEEDLES = {
    "main": {
        "front_bogie_template": "substr.file (                       $S_B_F",
        "rear_bogie_template": "substr.file (                       $S_B_R",
        "carbody_marker_parent": "marker.parent (                     $M_C_DummyBolster_F",
        "carbody_sender": "sender.ref (                        $COM_M_CB_DummyBolster_F",
    },
    "bogie_template": {
        "front_wheelset_template": "substr.file (                       $S_WS_F",
        "rear_wheelset_template": "substr.file (                       $S_WS_R",
        "primary_from": "force.from (                        $F_PS_SP_FR",
        "primary_to": "force.to (                          $F_PS_SP_FR",
        "primary_bogie_marker_parent": "marker.parent (                     $M_F_PS_SP_FR",
        "primary_axlebox_marker_parent": "marker.parent (                     $M_AB_FR_SP",
        "axlebox_wheelset_joint_from": "joint.from (                        $J_AB_FR",
        "axlebox_wheelset_joint_to": "joint.to (                          $J_AB_FR",
        "secondary_from": "force.from (                        $F_SS_R",
        "secondary_to": "force.to (                          $F_SS_R",
        "secondary_dummy_marker_parent": "marker.parent (                     $M_DUMMY_SS_R",
        "secondary_bogie_marker_parent": "marker.parent (                     $M_F_SS_R",
        "carbody_receiver": "receiver.priolist (       1 ,       $COM_M_DummyBolster_Attached",
        "receiver_target": "receiver.ref (                      $COM_M_DummyBolster_Attached",
    },
    "wheelset_template": {
        "wheel_rail_from": "force.from (                        $F_RWContact_RWP_R",
        "wheel_rail_to": "force.to (                          $F_RWContact_RWP_R",
        "rail_contact_marker_parent": "marker.parent (                     $M_B_Rail_R_ProfRef_RWP_R",
        "wheel_contact_marker_parent": "marker.parent (                     $M_B_WS_ProfRef_RWP_R",
        "fastener_from": "force.from (                        $F_Fastener_Force_R",
        "fastener_to": "force.to (                          $F_Fastener_Force_R",
        "sleeper_fastener_marker_parent": "marker.parent (                     $M_Sleeper_FastenerForce_R",
        "rail_fastener_marker_parent": "marker.parent (                     $M_Rail_R_Fastener",
    },
}


def inspect(path: Path, needles: dict[str, str]) -> dict:
    digest = hashlib.sha256()
    found: dict[str, dict[str, object]] = {}
    with path.open("rb") as stream:
        for line_number, raw in enumerate(stream, 1):
            digest.update(raw)
            if len(found) == len(needles):
                continue
            line = raw.decode("utf-8", errors="replace").rstrip("\r\n")
            for label, needle in needles.items():
                if label not in found and line.startswith(needle):
                    found[label] = {"line": line_number, "statement": line}
    missing = sorted(set(needles) - set(found))
    return {"path": str(path), "sha256": digest.hexdigest(), "size_bytes": path.stat().st_size,
            "statements": found, "missing": missing}


def main() -> int:
    report = {
        "evidence_type": "Simpack text model static topology",
        "scope": "named hierarchy, force endpoints, marker parent and sender/receiver; not solver mathematics",
        "files": {name: inspect(path, NEEDLES[name]) for name, path in SOURCES.items()},
    }
    report["passed"] = all(not item["missing"] for item in report["files"].values())
    target = Path(__file__).with_name("simpack_vehicle_topology_evidence.json")
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"passed": report["passed"], "missing":
                      {key: value["missing"] for key, value in report["files"].items()},
                      "output": str(target)}, ensure_ascii=False))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
