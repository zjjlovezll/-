"""Probe the modal track's DOF layout so a vehicle case can be built against it."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from velch.track_models import TrackKernel, load_modal_track

BASE = Path(__file__).resolve().parent
MODAL = BASE / "track_modes_turnout.json"

data = json.loads(MODAL.read_text(encoding="utf-8"))
shape = data["rail_shapes"]["right"]
phi_z = np.asarray(shape["phi_z"], dtype=float)
phi_y = np.asarray(shape["phi_y"], dtype=float)
print("phi_z shape", phi_z.shape, "| phi_y max |abs|", float(np.max(np.abs(phi_y))))
print("station range", float(shape["station_m"][0]), "..", float(shape["station_m"][-1]))

modal = load_modal_track(MODAL, ["left", "right"])
print("mode_count", modal.mode_count)
print("stiffness shape", np.shape(modal.stiffness_n_m))
print("damping shape", np.shape(modal.damping_n_s_m))
print("frequencies", float(np.min(modal.frequencies_hz)), "..", float(np.max(modal.frequencies_hz)))
print("has sample()", hasattr(modal, "sample"))
print("attributes", [name for name in vars(modal)][:10])

kernel = TrackKernel(kind="modal", rails=(), modal=modal)
print("kernel dimension (2 rails)", kernel.dimension)
