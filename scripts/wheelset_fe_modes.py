"""Turn the Abaqus tread dump into a `velch-wheel-modes/1` set.

Nodal diameters are measured from the shapes, not assumed: the radial component around the
tread ring is Fourier analysed and the dominant azimuthal order is the nodal diameter.  An
in-plane rotation has no radial content at all, so it is labelled `torsion` and counted as
nodal diameter 0 鈥?that is the same accounting the thesis table uses.

Frequencies stay in the CAD frame's axes (x longitudinal, y along the axle, z vertical),
because only the component directions matter downstream: the force mapping dots a contact
force with the shape.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

DUMP = Path(sys.argv[1])
OUT = Path(sys.argv[2])
FORMAT = "velch-wheel-modes/1"


def damping_ratio(nodal_diameter: int) -> float:
    if nodal_diameter == 0:
        return 1.0e-3
    if nodal_diameter == 1:
        return 1.0e-2
    return 1.0e-4


def classify(dump_mode: dict) -> tuple[int, str, float]:
    """Return (nodal diameter, label, radial share) for one mode."""
    radial, circum, axial = [], [], []
    for side in ("L", "R"):
        rows = np.asarray(dump_mode["nodes"][side], dtype=float)
        if rows.size == 0:
            continue
        theta = rows[:, 2]
        radial.append(rows[:, 3])
        circum.append(-rows[:, 5] * np.sin(theta) + rows[:, 6] * np.cos(theta))
        axial.append(rows[:, 4])
    radial = np.concatenate(radial)
    circum = np.concatenate(circum)
    axial = np.concatenate(axial)
    sizes = dict(radial=float(np.sqrt(np.mean(radial ** 2))),
                 circum=float(np.sqrt(np.mean(circum ** 2))),
                 axial=float(np.sqrt(np.mean(axial ** 2))))
    total = sum(value ** 2 for value in sizes.values()) ** 0.5
    share = sizes["radial"] / total if total > 0.0 else 0.0
    if sizes["circum"] > 4.0 * max(sizes["radial"], sizes["axial"]):
        return 0, "torsion", share
    measured = {side: dump_mode["harmonic"][side]["harmonic"] for side in ("L", "R")}
    if measured["L"] != measured["R"]:
        # the two wheels disagree; take the stronger radial side and say so in the label
        return max(measured.values()), "mixed", share
    diameter = measured["L"]
    if diameter == 0:
        if sizes["axial"] >= sizes["radial"]:
            return 0, "umbrella", share
        return 0, "axial-symmetric", share
    return diameter, "", share


def main() -> int:
    dump = json.loads(DUMP.read_text(encoding="utf-8"))
    keep = [item for item in dump["modes"] if item["frequency_hz"] > 1.0]

    # One node per degree of arc is more than the force mapping needs and keeps the shipped
    # file at a size git can hold; the raw ring has ~4200 nodes per wheel at this mesh size.
    PER_SIDE = 360
    node_keys: list[str] = []
    node_positions: list[list[float]] = []
    index_of: dict[str, int] = {}
    for side in ("L", "R"):
        rows = sorted(keep[0]["nodes"][side], key=lambda row: row[2])
        stride = max(1, int(len(rows) // PER_SIDE))
        for row in rows[::stride]:
            key = str(int(row[0]))
            if key not in index_of:
                index_of[key] = len(node_keys)
                node_keys.append(key)
                node_positions.append([0.0, 0.0, 0.0])
    coordinates = dump["coordinates"]
    for index, key in enumerate(node_keys):
        x, y, z = coordinates[key]
        node_positions[index] = [x / 1000.0, y / 1000.0, z / 1000.0]

    shapes = np.zeros((len(keep), len(node_keys), 3), dtype=float)
    modes = []
    for mode_index, mode in enumerate(keep):
        diameter, label, share = classify(mode)
        for side in ("L", "R"):
            for row in mode["nodes"][side]:
                column = index_of.get(str(int(row[0])))
                if column is None:
                    continue          # thinned out of the shipped ring
                shapes[mode_index, column] = [row[5], row[4], row[6]]  # CAD x, y, z in metres
        modes.append({
            "index": mode_index + 1,
            "frequency_hz": round(float(mode["frequency_hz"]), 4),
            "damping_ratio": damping_ratio(diameter),
            "nodal_diameter": diameter,
            "label": label,
        })

    # Degenerate travelling pairs are reported at the pair mean.  The FE split is 0.04-0.08 Hz
    # (0.01-0.1 %), which is mesh asymmetry, not geometry; the loader requires a travelling
    # pair to be exactly degenerate because a real axisymmetric wheel has no split at rest.
    families: list[list[int]] = []
    run: list[int] = []
    for position, item in enumerate(modes):
        if item["nodal_diameter"] > 0:
            previous = modes[run[-1]] if run else None
            if previous is not None and (
                    previous["nodal_diameter"] != item["nodal_diameter"]
                    or abs(item["frequency_hz"] - previous["frequency_hz"])
                    > 0.05 * max(previous["frequency_hz"], 1.0)):
                # two ND1 families can sit next to each other with no ND0 between them
                # (88.2 Hz first bending, 133.2 Hz in-phase deflection); a frequency jump
                # separates them just as reliably as a different nodal diameter.
                families.append(run)
                run = []
            run.append(position)
        elif run:
            families.append(run)
            run = []
    if run:
        families.append(run)
    drop: set[int] = set()
    for family in families:
        if len(family) < 2:
            drop.update(family)          # one half of a family that the 40-mode request cut off
            continue
        if len(family) % 2:
            drop.add(family[-1])
            family = family[:-1]
        mean = sum(modes[position]["frequency_hz"] for position in family) / float(len(family))
        for position in family:
            modes[position]["frequency_hz"] = round(mean, 4)
    if drop:
        print("  dropped %d unpaired mode(s): %s" % (
            len(drop), ", ".join("%.2f Hz" % modes[position]["frequency_hz"] for position in sorted(drop))))
        keep_index = [position for position in range(len(modes)) if position not in drop]
        modes = [modes[position] for position in keep_index]
        shapes = shapes[keep_index]
        for number, item in enumerate(modes):
            item["index"] = number + 1

    payload = {
        "format": FORMAT,
        "source": (f"Abaqus 2022 free-free frequency extraction of the CAD wheelset "
                   f"({Path(dump['odb']).name}), 20 mm quadratic tets, tread ring dump"),
        "radius_m": 0.460,
        "modes": modes,
        "nodes": node_positions,
        "shapes": shapes.tolist(),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    print(f"wrote {OUT}  {OUT.stat().st_size / 1e6:.2f} MB")
    print(f"  modes {len(modes)}   nodes {len(node_keys)}   shapes {shapes.shape}")
    print("  index  freq_Hz   ND  label")
    for item in modes:
        print(f"   {item['index']:4d} {item['frequency_hz']:9.2f}  {item['nodal_diameter']:2d}  "
              f"{item['label']}")
    pairs = {}
    for item in modes:
        if item["nodal_diameter"] > 0:
            pairs.setdefault(round(item["frequency_hz"], 1), []).append(item["nodal_diameter"])
    print("  degenerate families:", ", ".join(f"{freq} Hz ND{values[0]}脳{len(values)}"
                                              for freq, values in sorted(pairs.items())))
    return 0


if __name__ == "__main__":
    sys.exit(main())

