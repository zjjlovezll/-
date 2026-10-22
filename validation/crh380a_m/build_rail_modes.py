"""Build a discretely supported rail beam and export the Velch modal exchange file.

Why: the single vertical DOF per rail (`local_compliant`) lumps the beam's load
sharing over 5-6 sleepers into one spring, which left the 30-60 Hz band 27% low
against Simpack. Literature on track model fidelity makes the same point from the
other side: a beam-on-elastic-foundation (Winkler) model misses the higher-frequency
response that a *discretely supported* rail reproduces, because the discrete supports
make the rail dispersion periodic and add the sleeper-bay content.

Model (60 kg/m rail, CRH380A_M turnout support):
    EI = 6.884e6 N m^2      (E = 214 GPa per SDITT, I = 3.217e-5 m^4)
    mu = 60.64 kg/m
    fasteners every 0.6 m, kz = 25e6 N/m each, damping ratio 0.10
    Euler-Bernoulli Hermite beam, 2 DOF per node, free-free ends

Output: `track_modes_turnout.json` (schema `velch-modal-track-v1`), modes with
frequencies up to `--max-hz`, shapes mass-normalised so the modal mass is 1 kg.
"""

from __future__ import annotations

import argparse
import json
import pathlib

import numpy as np
from scipy.linalg import eigh as generalized_eigh

EI = 6.884e6
MU = 60.64
SPACING = 0.6
PAD_KZ = 25e6
DAMPING_RATIO = 0.10


def beam_matrices(length: float, element: float) -> tuple[np.ndarray, np.ndarray]:
    count = int(round(length / element))
    nodes = count + 1
    dof = 2 * nodes
    stiffness = np.zeros((dof, dof))
    mass = np.zeros((dof, dof))
    ke = EI / element ** 3 * np.array([
        [12.0, 6.0 * element, -12.0, 6.0 * element],
        [6.0 * element, 4.0 * element ** 2, -6.0 * element, 2.0 * element ** 2],
        [-12.0, -6.0 * element, 12.0, -6.0 * element],
        [6.0 * element, 2.0 * element ** 2, -6.0 * element, 4.0 * element ** 2],
    ])
    me = MU * element / 420.0 * np.array([
        [156.0, 22.0 * element, 54.0, -13.0 * element],
        [22.0 * element, 4.0 * element ** 2, 13.0 * element, -3.0 * element ** 2],
        [54.0, 13.0 * element, 156.0, -22.0 * element],
        [-13.0 * element, -3.0 * element ** 2, -22.0 * element, 4.0 * element ** 2],
    ])
    for index in range(count):
        slots = [2 * index, 2 * index + 1, 2 * index + 2, 2 * index + 3]
        stiffness[np.ix_(slots, slots)] += ke
        mass[np.ix_(slots, slots)] += me
    for index in range(nodes):
        stiffness[2 * index, 2 * index] += PAD_KZ
    return stiffness, mass


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--length", type=float, default=150.0)
    parser.add_argument("--element", type=float, default=SPACING)
    parser.add_argument("--max-hz", type=float, default=320.0)
    parser.add_argument("--limit", type=int, default=60)
    parser.add_argument("--templates", default="left,right")
    parser.add_argument("--out", default="track_modes_turnout.json")
    args = parser.parse_args()

    stiffness, mass = beam_matrices(args.length, args.element)
    values, vectors = generalized_eigh(stiffness, mass)
    keep = values > 0.0
    omega = np.sqrt(values[keep])
    vectors = vectors[:, keep]
    # Mass-normalise: phi^T M phi = 1 kg  ->  modal mass 1 kg, k = omega^2.
    for column in range(vectors.shape[1]):
        vectors[:, column] /= np.sqrt(vectors[:, column] @ mass @ vectors[:, column])
    frequency = omega / (2.0 * np.pi)
    selected = np.where(frequency <= args.max_hz)[0][: args.limit]
    if selected.size == 0:
        raise SystemExit("no modes below the requested frequency")

    nodes = int(round(args.length / args.element)) + 1
    station = np.round(np.arange(nodes) * args.element, 9)
    vertical = vectors[0::2, :][:, selected].T           # (mode, station), m per unit q
    lateral = np.zeros_like(vertical)

    modes = [
        {
            "id": f"rail_vertical_{index + 1:02d}",
            "modal_mass_kg": 1.0,
            "frequency_hz": float(frequency[selected[index]]),
            "damping_ratio": DAMPING_RATIO,
        }
        for index in range(selected.size)
    ]
    shapes = {}
    for template in args.templates.split(","):
        shapes[template.strip()] = {
            "station_m": [float(value) for value in station],
            "phi_y": [list(map(float, row)) for row in lateral],
            "phi_z": [list(map(float, row)) for row in vertical],
        }
    payload = {
        "schema_version": "velch-modal-track-v1",
        "data_status": "velch_generated_discretely_supported_rail_beam",
        "normalization_note": (
            "Mass-normalised Euler-Bernoulli beam on 0.6 m fastener springs; "
            "EI=6.884e6 N m^2, mu=60.64 kg/m, kz=25e6 N/m per fastener, free-free ends, "
            "modal mass 1 kg, 10% modal damping. Generated, not exported from Simpack."
        ),
        "modes": modes,
        "rail_shapes": shapes,
    }
    target = pathlib.Path(__file__).resolve().parent / args.out
    target.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    print(f"wrote {target.name}: {selected.size} modes, "
          f"f = {frequency[selected[0]]:.2f} .. {frequency[selected[-1]]:.2f} Hz, "
          f"{nodes} stations, {target.stat().st_size / 1e6:.1f} MB")
    print("first six frequencies:", np.round(frequency[selected[:6]], 2).tolist())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
