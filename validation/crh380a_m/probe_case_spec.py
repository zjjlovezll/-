"""Smoke test: a resolved case differs only in the parameters it was asked to move.

    python probe_case_spec.py <case.json>
"""

from __future__ import annotations

import sys
from pathlib import Path

from velch.case.spec import CaseSpec, ParameterSpec

path = Path(sys.argv[1])
spec = CaseSpec.from_path(path, (
    ParameterSpec.of("support_k_z", ("rail_templates", 0, "support", "k_z_n_m")),
    ParameterSpec.of("contact_r_star", ("contact", "effective_radius_m")),
))
print("source     :", spec.source.name, spec.digest[:16])
print("parameters :", [(item.name, f"{item.base:.6g}") for item in spec.parameters])

nominal = spec.resolve(spec.nominal)
moved = spec.resolve((0.2, -0.1))
count = len(nominal.initial_q)
print(f"nominal    : states={count} track={nominal.track_kind} "
      f"k_z={nominal.rails[0].support.k_z_n_m:.6g} R*={nominal.contact.effective_radius_m:.6g}")
print(f"theta      : states={len(moved.initial_q)} track={moved.track_kind} "
      f"k_z={moved.rails[0].support.k_z_n_m:.6g} R*={moved.contact.effective_radius_m:.6g}")
print("sha differ :", nominal.case_sha256 != moved.case_sha256)
print("same assets:", nominal.asset_hashes == moved.asset_hashes)
