"""Find which simulated channels correspond to the measured sensor locations.

The measured campaign has strain-gauge force channels (CH01..CH06) and displacement channels
(CH09..CH15).  For a like-for-like comparison the simulation must produce the *same* quantities
at the *same* sections, so this probe looks for Simpack sensors / substitute variables on the
rails and reports their identifiers.
"""

from __future__ import annotations

import json
from pathlib import Path

import h5py
import numpy as np

OUTPUT = Path(r"H:\齿轨工况\坡度工况\matlab\VEH_GEAR0_FX_STR_RACKN_QY-Re1_cjy_whcl_zn_TE_USERFORCE_CG_120.output")
PLAIN = OUTPUT / "NoExt_zgzn_jdz6.2mm_SP_00.mat"
BASE = Path(__file__).resolve().parent


def text_of(group: h5py.Group) -> str:
    for key in ("name", "c_name"):
        if key in group and isinstance(group[key], h5py.Dataset):
            data = np.asarray(group[key][...]).ravel()
            if data.dtype.kind in ("u", "i"):
                text = "".join(chr(int(v)) for v in data if 30 <= int(v) < 0x3000)
                if text.strip():
                    return text.strip()
    return ""


def main() -> int:
    with h5py.File(PLAIN, "r") as handle:
        report: dict[str, object] = {}
        for container in ("sensorPosTrans", "sensorAccTrans", "sensorPosRot", "sensorAccRot",
                          "subvar", "forceOv", "forceForce"):
            if container not in handle["timeInt"]:
                continue
            group = handle["timeInt"][container]
            names = [k for k in group.keys() if isinstance(group[k], h5py.Group)]
            print(f"\n{container}: {len(names)} groups")
            labels = []
            for name in names[:40]:
                label = text_of(group[name])
                labels.append((name, label))
            for name, label in labels[:14]:
                print(f"  {name:<34} {label}")
            report[container] = {"count": len(names),
                                 "sample": [{"id": n, "label": l} for n, l in labels[:40]]}

        # substitute variables often carry rail-strain / contact definitions
        if "subvar" in handle["timeInt"]:
            sub = handle["timeInt"]["subvar"]
            hits = []
            for name in list(sub.keys())[:4000]:
                node = sub[name]
                if not isinstance(node, h5py.Group):
                    continue
                label = text_of(node)
                low = label.lower()
                if any(token in low for token in ("rail", "stress", "strain", "eps", "con",
                                                  "force", "fz", "q_", "jdz", "dvc")):
                    hits.append((name, label))
            print(f"\nsubvar hits with rail/force/strain tokens: {len(hits)}")
            for name, label in hits[:20]:
                print(f"  {name:<18} {label}")
            report["subvar_hits"] = [{"id": n, "label": l} for n, l in hits[:60]]

    (BASE / "rack_sensor_map.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
