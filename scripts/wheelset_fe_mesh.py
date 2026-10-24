"""Assemble a free-free wheelset .inp for a frequency extraction, from the STEP geometry.

Axle and wheel are meshed separately with quadratic tets (HXT, the only 3D algorithm that
survives this Pro/E B-rep), the wheel is rotated half a turn to make the second wheel, and
the two press fits are attached with *TIE between node sets picked by radius and axial
position. Tying beats welding: the wheel bore and the axle seat are separate surfaces, and
the fit is a bonded joint either way.

The second wheel is produced by rotating about the axle axis rather than mirroring it, so
element orientation survives and no connectivity has to be renumbered.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import gmsh
import numpy as np

STEP = r"G:\研究生\groh\CRH3C轮对模型(1)\CRH3C轮对模型\tuoche.stp"
WORK = Path(r"F:\velch_tmp\wheelset")
INP = WORK / "wheelset_modal.inp"
REPORT = WORK / "wheelset_modal.json"

ELEMENT_SIZE_MM = float(os.environ.get("WHEELSET_SIZE_MM", "30"))
STEEL = {"E_MPa": 210000.0, "nu": 0.3, "rho_t_mm3": 7.85e-9}
MODES = 40


def mesh_part(label: str, rank: int, centre_path: Path) -> dict[str, object]:
    """Mesh one volume and return its nodes, C3D10 connectivity and centre."""
    cache = WORK / f"{label}_{ELEMENT_SIZE_MM:g}mm.npz"
    if cache.exists():
        stored = np.load(cache)
        print(f"  {label}: cached  nodes {len(stored['node_tags']):7d}  "
              f"C3D10 {len(stored['element_nodes']):7d}")
        return {
            "centre": stored["centre"],
            "node_tags": stored["node_tags"],
            "coordinates": stored["coordinates"],
            "element_nodes": stored["element_nodes"],
            "volume_mm3": float(stored["volume_mm3"]),
        }
    gmsh.initialize()
    gmsh.option.setNumber("General.Terminal", 0)
    gmsh.model.add(label)
    gmsh.model.occ.importShapes(STEP)
    gmsh.model.occ.synchronize()
    masses = sorted(
        ((gmsh.model.occ.getMass(3, tag), tag) for _dim, tag in gmsh.model.getEntities(3)),
        reverse=True,
    )
    keep = masses[rank][1]
    for other, (_mass, tag) in enumerate(masses):
        if other != rank:
            gmsh.model.occ.remove([(3, tag)], recursive=True)
    gmsh.model.occ.synchronize()
    centre = np.array(gmsh.model.occ.getCenterOfMass(3, keep))
    volume = gmsh.model.occ.getMass(3, keep)

    gmsh.option.setNumber("Mesh.MeshSizeMax", ELEMENT_SIZE_MM)
    gmsh.option.setNumber("Mesh.MeshSizeMin", 10.0)
    gmsh.option.setNumber("Mesh.MeshSizeExtendFromBoundary", 0)
    gmsh.option.setNumber("Mesh.MeshSizeFromPoints", 0)
    gmsh.option.setNumber("Mesh.MeshSizeFromCurvature", 0)
    gmsh.option.setNumber("Mesh.ElementOrder", 2)
    gmsh.option.setNumber("Mesh.HighOrderOptimize", 2)
    gmsh.option.setNumber("Mesh.Algorithm3D", 10)  # HXT
    gmsh.model.mesh.generate(3)

    # Write the INP with gmsh's own exporter and read it back.  Its C3D10 node order is
    # Abaqus's; taking getElements() straight out of the API gives gmsh's order, and every
    # element then reports zero or negative volume.
    part_inp = WORK / f"{label}_{ELEMENT_SIZE_MM:g}mm.inp"
    gmsh.option.setNumber("Mesh.Format", 39)
    gmsh.write(str(part_inp))
    gmsh.finalize()

    node_tags: list[int] = []
    coordinates: list[tuple[float, float, float]] = []
    element_nodes: list[list[int]] = []
    section = ""
    for line in part_inp.read_text(encoding="ascii", errors="replace").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("*"):
            section = stripped.lower()
            continue
        if section.startswith("*node"):
            parts = stripped.split(",")
            if len(parts) >= 4:
                node_tags.append(int(parts[0]))
                coordinates.append((float(parts[1]), float(parts[2]), float(parts[3])))
        elif section.startswith("*element") and "c3d10" in section:
            element_nodes.append([int(value) for value in stripped.split(",")[1:]])
    node_tags = np.asarray(node_tags, dtype=int)
    coordinates = np.asarray(coordinates, dtype=float).reshape(-1, 3)
    element_nodes = np.asarray(element_nodes, dtype=int)
    if len(element_nodes) == 0 or element_nodes.shape[1] != 10:
        raise SystemExit(f"{label}: expected C3D10 rows, got shape {element_nodes.shape}")
    np.savez(
        cache,
        centre=centre,
        node_tags=node_tags,
        coordinates=coordinates,
        element_nodes=element_nodes,
        volume_mm3=volume,
    )
    return {
        "centre": centre,
        "node_tags": node_tags,
        "coordinates": coordinates,
        "element_nodes": element_nodes,
        "volume_mm3": volume,
    }


def main() -> int:
    WORK.mkdir(parents=True, exist_ok=True)
    print("meshing")
    axle = mesh_part("axle", 0, WORK / "axle_centre.json")
    wheel = mesh_part("wheel", 1, WORK / "wheel_centre.json")
    axle_axis_y = float(axle["centre"][1])

    spacing = 2.0 * float(wheel["centre"][1] - axle_axis_y)
    print(f"  wheel spacing {abs(spacing):.2f} mm (from the CAD centres)")

    # second wheel: half a turn about the axle axis, which is a rotation, not a mirror
    coordinates_r = wheel["coordinates"].copy()
    coordinates_r[:, 1] = 2.0 * axle_axis_y - coordinates_r[:, 1]
    coordinates_r[:, 2] = -coordinates_r[:, 2]

    parts = [
        ("AXLE", axle["coordinates"], axle["element_nodes"]),
        ("WHEEL_L", wheel["coordinates"], wheel["element_nodes"]),
        ("WHEEL_R", coordinates_r, wheel["element_nodes"]),
    ]

    nodes = []
    elements = []
    offsets = {}
    next_node = 1
    next_element = 1
    for name, coordinates, connectivity in parts:
        offsets[name] = next_node
        for index, xyz in enumerate(coordinates):
            nodes.append((next_node + index, xyz))
        next_node += len(coordinates)
        for row in connectivity:
            elements.append((next_element, row + offsets[name] - 1))
            next_element += 1

    all_coordinates = np.vstack([coordinates for _name, coordinates, _conn in parts])
    tag_lookup = {name: offsets[name] for name, _c, _e in parts}

    def pick(name: str, mask: np.ndarray) -> np.ndarray:
        coordinates = dict((part, coordinates) for part, coordinates, _conn in parts)[name]
        return np.nonzero(mask)[0] + tag_lookup[name]

    axle_xyz = axle["coordinates"]
    radius_axle = np.hypot(axle_xyz[:, 0] - axle["centre"][0], axle_xyz[:, 2] - axle["centre"][2])
    radius_wheel = np.hypot(wheel["coordinates"][:, 0] - wheel["centre"][0],
                            wheel["coordinates"][:, 2] - wheel["centre"][2])

    seat_band_left = np.abs(axle_xyz[:, 1] - float(wheel["centre"][1])) < 95.0
    right_y = 2.0 * axle_axis_y - float(wheel["centre"][1])
    seat_band_right = np.abs(axle_xyz[:, 1] - right_y) < 95.0
    # The bore and the seat are the same radius (both ≈95.5 mm), so the tie is a
    # cylindrical surface pair with no gap.  Taking the bore radius from a wide band put the
    # seat set on the seat chamfer instead, and ADJUST then dragged the bore 95 mm outboard.
    bore_band = (radius_wheel > 90.0) & (radius_wheel < 100.0)
    bore_radius = float(np.median(radius_wheel[bore_band]))
    surface = np.abs(radius_wheel - bore_radius) < 0.75
    print(f"  wheel bore radius {bore_radius:.2f} mm, {int((bore_band & surface).sum())} bore nodes")
    seat_surface = np.abs(radius_axle - bore_radius) < 0.75
    for side, band in (("L", seat_band_left), ("R", seat_band_right)):
        chosen = seat_surface & band
        print(f"  axle seat {side}: {int(chosen.sum())} nodes at r {bore_radius:.1f} mm")

    sets = {
        "SEAT_L": pick("AXLE", seat_surface & seat_band_left),
        "SEAT_R": pick("AXLE", seat_surface & seat_band_right),
        "BORE_L": pick("WHEEL_L", bore_band & surface),
        "BORE_R": pick("WHEEL_R", bore_band & surface),
    }
    for name, values in sets.items():
        print(f"  {name}: {len(values)} nodes")

    def wrapped(values, per_line: int = 8) -> list[str]:
        """Abaqus truncates any input line past 256 characters, so every long list wraps."""
        text = [str(int(value)) for value in values]
        return [", ".join(text[start:start + per_line]) for start in range(0, len(text), per_line)]

    lines = ["*HEADING", "Velch flexible wheelset, free-free, built from tuoche.stp", "*NODE"]
    for tag, xyz in nodes:
        lines.append(f"{tag}, {xyz[0]:.6f}, {xyz[1]:.6f}, {xyz[2]:.6f}")
    lines.append("*ELEMENT, TYPE=C3D10")
    for tag, row in elements:
        lines.append(f"{tag}, " + ", ".join(str(int(value)) for value in row))
    lines.append("*ELSET, ELSET=ALLEL, GENERATE")
    lines.append(f"1, {len(elements)}, 1")
    for name, values in sets.items():
        if len(values) == 0:
            raise SystemExit(f"node set {name} came out empty")
        lines.append(f"*NSET, NSET={name}")
        lines += wrapped(values)
    lines += [
        "*SOLID SECTION, ELSET=ALLEL, MATERIAL=STEEL",
        "*MATERIAL, NAME=STEEL",
        "*ELASTIC",
        f"{STEEL['E_MPa']:.1f}, {STEEL['nu']:.3f}",
        "*DENSITY",
        f"{STEEL['rho_t_mm3']:.4e}",
    ]
    for side in ("L", "R"):
        lines += [
            f"*SURFACE, NAME=SEAT_{side}_S, TYPE=NODE",
            f"SEAT_{side},",
            f"*SURFACE, NAME=BORE_{side}_S, TYPE=NODE",
            f"BORE_{side},",
            f"*TIE, NAME=PRESSFIT_{side}, ADJUST=YES, POSITION TOLERANCE=3.0",
            f"SEAT_{side}_S, BORE_{side}_S",
        ]
    lines += [
        "*STEP",
        "Extract the free-mode set of the wheelset",
        "*FREQUENCY, EIGENSOLVER=LANCZOS, NORMALIZATION=MASS",
        f"{MODES},",
        "*OUTPUT, FIELD",
        "*NODE OUTPUT",
        "U,",
        "*END STEP",
    ]
    INP = WORK / f"wheelset_modal_{ELEMENT_SIZE_MM:g}mm.inp"
    REPORT = WORK / f"wheelset_modal_{ELEMENT_SIZE_MM:g}mm.json"
    INP.write_text("\n".join(lines) + "\n", encoding="ascii")
    print(f"wrote {INP}  {INP.stat().st_size / 1e6:.1f} MB  "
          f"(nodes {len(nodes)}, elements {len(elements)})")

    REPORT.write_text(json.dumps({
        "source": STEP,
        "parts": {name: int(len(connectivity)) for name, _c, connectivity in parts},
        "nodes": len(nodes),
        "elements": len(elements),
        "dof": 3 * len(nodes),
        "element_size_mm": ELEMENT_SIZE_MM,
        "wheel_spacing_m": abs(spacing) / 1000.0,
        "mass_kg": sum(float(a["volume_mm3"]) * 7.85e-6 for a in (axle,)) + 2 * float(wheel["volume_mm3"]) * 7.85e-6,
        "tie_nodes": {name: int(len(values)) for name, values in sets.items()},
        "material": STEEL,
        "modes_requested": MODES,
        "dropped": "brake discs, bolts, springs, washers",
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
